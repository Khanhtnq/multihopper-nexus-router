import pytest
from src.routing.graph import DexGraph
from src.routing.arbitrage import BellmanFordArbitrageScanner
from src.dex.amm_pool import ConstantProductPool


def test_arbitrage_scanner_finds_profitable_cycles():
    graph = DexGraph.create_default_solana_market()

    # Introduce a slight cross-market price discrepancy to create an authentic arbitrage opportunity:
    # Pool A: SOL/USDC at 150.0
    # Add Pool B: SOL/USDC at 152.0 (Orca vs Raydium spread)
    graph.add_pool(ConstantProductPool(
        pool_id="ray_arbitrage_sol_usdc",
        dex_name="Raydium Spread AMM",
        token_a="SOL",
        token_b="USDC",
        reserve_a=5000.0,
        reserve_b=760000.0,  # 760,000 / 5,000 = 152.0 spot
        fee_bps=5.0
    ))

    scanner = BellmanFordArbitrageScanner(graph, sol_price_usd=150.0)
    opps = scanner.find_arbitrage_cycles("SOL")

    assert len(opps) > 0
    best_opp = opps[0]
    assert best_opp.tokens[0] == "SOL"
    assert best_opp.tokens[-1] == "SOL"
    assert best_opp.optimal_input_amount > 0.0
    assert best_opp.gross_profit_ratio > 1.0


def test_arbitrage_gas_cost_accounting():
    graph = DexGraph.create_default_solana_market()
    scanner = BellmanFordArbitrageScanner(graph, sol_price_usd=150.0)
    opps = scanner.find_arbitrage_cycles("SOL")

    for o in opps:
        # Gas cost must be strictly positive (5000 base + priority compute fee)
        assert o.estimated_gas_cost_sol > 0.0
        # Net profit must equal expected_out - optimal_in - gas
        expected_net = o.expected_output_amount - o.optimal_input_amount - o.estimated_gas_cost_sol
        assert pytest.approx(o.net_profit_amount, rel=1e-4) == expected_net
