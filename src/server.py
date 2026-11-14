"""
FastAPI Server for MultiHopper Nexus Router.
Exposes REST endpoints for:
- DEX Multi-Hop Split Routing & Convex Optimization
- Bellman-Ford Cyclic Arbitrage Scanner
- MultiHopper Protocol Fee Estimation & Route Creation
- Swaps-with-Hooks Pipeline
- Superteam Earn Revenue & Prize Pool Simulator
"""

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os

from src.routing.graph import DexGraph, SOLANA_TOKENS
from src.routing.yen_ksp import YenKSP
from src.routing.convex_optimizer import ConvexSplitOptimizer
from src.routing.arbitrage import BellmanFordArbitrageScanner
from src.multihopper.client import MultiHopperClient
from src.multihopper.revenue_calculator import RevenueCalculator
from src.multihopper.webhook import WebhookManager
from src.pipeline.swaps_with_hooks import SwapsWithHooksPipeline

app = FastAPI(
    title="MultiHopper Nexus Router API",
    description="Solana Multi-Hop Smart Order Routing & Arbitrage Engine with MultiHopper Protocol Integration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instances
dex_graph = DexGraph.create_default_solana_market()
multihopper_client = MultiHopperClient()
pipeline = SwapsWithHooksPipeline(dex_graph, multihopper_client)
arbitrage_scanner = BellmanFordArbitrageScanner(dex_graph)


# Models
class RouteRequest(BaseModel):
    token_in: str = Field(default="SOL", example="SOL")
    token_out: str = Field(default="USDC", example="USDC")
    amount_in: float = Field(default=10.0, example=10.0)
    k_paths: int = Field(default=4, example=4)


class SwapsWithHooksRequest(BaseModel):
    token_in: str = "SOL"
    token_out: str = "USDC"
    amount_in: float = 5.0
    source_owner: str = "6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf"
    recipient_wallet: Optional[str] = "H4iZ7C2Z1rXgQ2Xy9J4K6M3P8T9W1V5L2B8N4M7K9L2P"
    destinations: Optional[List[Dict[str, Any]]] = None
    custom_hops: int = 3


class MultiHopperEstimateRequest(BaseModel):
    token_mint: str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    amount_tokens: float = 1000.0
    source_owner: str = "6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf"
    hops: int = 3
    destinations_count: int = 1


@app.get("/api/tokens")
def get_tokens():
    return {symbol: {"symbol": t.symbol, "mint": t.mint, "decimals": t.decimals, "name": t.name}
            for symbol, t in SOLANA_TOKENS.items()}


@app.post("/api/route")
def calculate_route(req: RouteRequest):
    if req.token_in not in SOLANA_TOKENS or req.token_out not in SOLANA_TOKENS:
        raise HTTPException(status_code=400, detail="Unknown token symbol.")
    if req.token_in == req.token_out:
        raise HTTPException(status_code=400, detail="Token in and token out must be distinct.")

    yen = YenKSP(dex_graph)
    paths = yen.find_k_shortest_paths(req.token_in, req.token_out, k=req.k_paths)
    if not paths:
        raise HTTPException(status_code=404, detail="No route found between selected tokens.")

    optimizer = ConvexSplitOptimizer(paths)
    result = optimizer.optimize_split(req.amount_in)

    return {
        "token_in": result.token_in,
        "token_out": result.token_out,
        "amount_in": result.total_amount_in,
        "amount_out": result.total_amount_out,
        "blended_rate": result.blended_rate,
        "blended_price_impact_pct": result.blended_price_impact * 100.0,
        "single_route_out": result.single_route_out,
        "gain_over_single_route": result.gain_over_single_route,
        "gain_percent": result.gain_percent,
        "allocations": [
            {
                "route_id": a.route.path_id,
                "weight_pct": round(a.weight * 100.0, 2),
                "amount_in": a.amount_in,
                "amount_out": a.amount_out,
                "effective_rate": a.effective_rate,
                "price_impact_pct": round(a.price_impact * 100.0, 4),
                "path_description": a.route.describe(),
                "hops": [
                    {
                        "pool_id": h.pool_id,
                        "dex_name": h.dex_name,
                        "token_in": h.token_in,
                        "token_out": h.token_out,
                        "fee_bps": h.fee_bps
                    } for h in a.route.hops
                ]
            } for a in result.allocations
        ]
    }


@app.get("/api/arbitrage")
def scan_arbitrage(base_token: str = "SOL"):
    opps = arbitrage_scanner.find_arbitrage_cycles(base_token)
    return {
        "base_token": base_token,
        "total_opportunities_found": len(opps),
        "cycles": [
            {
                "cycle_id": o.cycle_id,
                "tokens": o.tokens,
                "gross_profit_ratio": o.gross_profit_ratio,
                "optimal_input_amount": o.optimal_input_amount,
                "expected_output_amount": o.expected_output_amount,
                "net_profit_amount": o.net_profit_amount,
                "net_profit_usd": o.net_profit_usd,
                "estimated_gas_cost_sol": o.estimated_gas_cost_sol,
                "roi_percent": o.roi_percent,
                "is_executable": o.is_executable,
                "hops": [
                    {
                        "pool_id": h.pool_id,
                        "dex_name": h.dex_name,
                        "token_in": h.token_in,
                        "token_out": h.token_out,
                        "fee_bps": h.fee_bps
                    } for h in o.hops
                ]
            } for o in opps[:10]
        ]
    }


@app.post("/api/multihopper/estimate")
def estimate_multihopper(req: MultiHopperEstimateRequest):
    dest_list = [{"wallet": f"dest_{i}", "share": 1.0} for i in range(req.destinations_count)] if req.destinations_count > 1 else None
    quote = multihopper_client.estimate_transfer(
        token_mint=req.token_mint,
        amount_tokens=req.amount_tokens,
        source_owner=req.source_owner,
        destinations=dest_list,
        hops=req.hops
    )
    return quote


@app.post("/api/pipeline/swaps-with-hooks")
def execute_pipeline(req: SwapsWithHooksRequest):
    exec_res = pipeline.execute_swap_and_route(
        token_in=req.token_in,
        token_out=req.token_out,
        amount_in=req.amount_in,
        source_owner=req.source_owner,
        recipient_wallet=req.recipient_wallet,
        destinations=req.destinations,
        custom_hops=req.custom_hops
    )
    return {
        "execution_id": exec_res.execution_id,
        "status": exec_res.status,
        "dex_swapped_output": exec_res.dex_routing.total_amount_out,
        "blended_price_impact_pct": exec_res.dex_routing.blended_price_impact * 100.0,
        "multihopper_transfer_id": exec_res.multihopper_transfer_id,
        "integrator_revenue_usd": exec_res.integrator_revenue_usd,
        "multihopper_quote": exec_res.multihopper_quote,
        "destinations": exec_res.destinations,
        "webhook_payload": exec_res.webhook_payload
    }


@app.get("/api/revenue/calculator")
def get_revenue_calculation(
    your_volume_usd: float = 1500000.0,
    top3_volume_usd: float = 5000000.0,
    aggregate_competition_volume_usd: float = 8000000.0
):
    sim = RevenueCalculator.calculate_winner_share(
        your_qualifying_volume_usd=your_volume_usd,
        top3_volumes_usd=[top3_volume_usd * 0.5, top3_volume_usd * 0.3, top3_volume_usd * 0.2],
        aggregate_competition_volume_usd=aggregate_competition_volume_usd
    )
    return sim


# Mount static files if docs directory exists
docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
if os.path.exists(docs_dir):
    app.mount("/", StaticFiles(directory=docs_dir, html=True), name="docs")
