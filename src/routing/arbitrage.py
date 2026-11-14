"""
Bellman-Ford Cyclic Arbitrage Scanner for Solana DEX Pools.
Detects cross-pool triangular and multi-hop arbitrage opportunities:
    Cycle Profit Factor = Prod_{i=1}^n [ Spot_i * (1 - fee_bps_i / 10000) ] > 1.0
In log-space: Sum_{i=1}^n -ln(Spot_i * (1 - fee_bps_i / 10000)) < 0.0 (Negative Cycle).
"""

import math
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from scipy.optimize import minimize_scalar
from src.routing.graph import DexGraph, Edge
from src.dex.amm_pool import BasePool


@dataclass
class ArbitrageHop:
    pool_id: str
    dex_name: str
    token_in: str
    token_out: str
    fee_bps: float
    pool: BasePool


@dataclass
class ArbitrageOpportunity:
    cycle_id: str
    tokens: List[str]
    hops: List[ArbitrageHop]
    gross_profit_ratio: float
    optimal_input_amount: float
    expected_output_amount: float
    net_profit_amount: float
    net_profit_usd: float
    estimated_gas_cost_sol: float
    roi_percent: float
    is_executable: bool

    def describe(self) -> str:
        cycle_str = " -> ".join(self.tokens)
        return (f"[{self.cycle_id}] {cycle_str} | "
                f"Optimal In: {self.optimal_input_amount:.4f} {self.tokens[0]} | "
                f"Net Profit: +{self.net_profit_amount:.4f} ({self.roi_percent:.2f}%)")


class BellmanFordArbitrageScanner:
    """
    Scans the Solana DEX liquidity graph for cyclic arbitrage opportunities.
    """
    def __init__(self, graph: DexGraph, sol_price_usd: float = 150.0):
        self.graph = graph
        self.sol_price_usd = sol_price_usd

    def find_arbitrage_cycles(self, base_token: str = "SOL", max_cycle_len: int = 4) -> List[ArbitrageOpportunity]:
        nodes = list(self.graph.nodes.keys())
        if base_token not in nodes:
            return []

        # Flatten all directed edges in graph
        all_edges: List[Edge] = []
        for u in nodes:
            all_edges.extend(self.graph.get_edges(u))

        # Bellman-Ford on negative log weights
        dist: Dict[str, float] = {n: float('inf') for n in nodes}
        pred_edge: Dict[str, Optional[Edge]] = {n: None for n in nodes}
        dist[base_token] = 0.0

        V = len(nodes)
        for _ in range(V - 1):
            relaxed = False
            for edge in all_edges:
                u, v = edge.token_in, edge.token_out
                w = edge.log_weight
                if dist[u] != float('inf') and dist[u] + w < dist[v] - 1e-9:
                    dist[v] = dist[u] + w
                    pred_edge[v] = edge
                    relaxed = True
            if not relaxed:
                break

        # Check for negative weight cycles
        opportunities: List[ArbitrageOpportunity] = []
        visited_cycles: set = set()

        for edge in all_edges:
            u, v = edge.token_in, edge.token_out
            w = edge.log_weight

            if dist[u] != float('inf') and dist[u] + w < dist[v] - 1e-9:
                # Negative cycle detected! Trace back to find cycle nodes
                cycle_edges: List[Edge] = []
                curr = u
                visited_nodes = {}
                step = 0

                # Walk back V steps to ensure inside the cycle
                for _ in range(V):
                    pe = pred_edge[curr]
                    if pe is None:
                        break
                    curr = pe.token_in

                # Now curr is guaranteed to be in the cycle, trace the loop
                start_node = curr
                loop_edges: List[Edge] = []
                while True:
                    pe = pred_edge[curr]
                    if pe is None:
                        break
                    loop_edges.append(pe)
                    curr = pe.token_in
                    if curr == start_node or len(loop_edges) > max_cycle_len:
                        break

                loop_edges.reverse()

                if len(loop_edges) >= 2 and loop_edges[0].token_in == loop_edges[-1].token_out:
                    cycle_key = tuple(e.pool.pool_id for e in loop_edges)
                    if cycle_key not in visited_cycles:
                        visited_cycles.add(cycle_key)
                        opp = self._evaluate_cycle(loop_edges)
                        if opp:
                            opportunities.append(opp)

        # Also search explicit triangular cycles from base_token
        triangular_opps = self._search_triangular_cycles(base_token)
        for opp in triangular_opps:
            cycle_key = tuple(h.pool_id for h in opp.hops)
            if cycle_key not in visited_cycles:
                visited_cycles.add(cycle_key)
                opportunities.append(opp)

        # Sort by net profit amount descending
        opportunities.sort(key=lambda o: o.net_profit_amount, reverse=True)
        return opportunities

    def _search_triangular_cycles(self, base_token: str) -> List[ArbitrageOpportunity]:
        """Exhaustively checks 2-hop and 3-hop cycles anchored at base_token."""
        results: List[ArbitrageOpportunity] = []
        edges_out = self.graph.get_edges(base_token)

        for e1 in edges_out:
            t1 = e1.token_out
            if t1 == base_token:
                continue

            for e2 in self.graph.get_edges(t1):
                t2 = e2.token_out
                # 2-hop cycle: base -> t1 -> base (reverse edge across different pool)
                if t2 == base_token and e1.pool.pool_id != e2.pool.pool_id:
                    opp = self._evaluate_cycle([e1, e2])
                    if opp and opp.is_executable:
                        results.append(opp)
                    continue

                # 3-hop cycle: base -> t1 -> t2 -> base
                for e3 in self.graph.get_edges(t2):
                    if e3.token_out == base_token:
                        # Ensure not using same pool back-to-back
                        if e1.pool.pool_id != e2.pool.pool_id and e2.pool.pool_id != e3.pool.pool_id:
                            opp = self._evaluate_cycle([e1, e2, e3])
                            if opp and opp.is_executable:
                                results.append(opp)

        return results

    def _evaluate_cycle(self, edges: List[Edge]) -> Optional[ArbitrageOpportunity]:
        start_token = edges[0].token_in
        end_token = edges[-1].token_out
        if start_token != end_token:
            return None

        # Calculate gross profit ratio
        compounded_rate = 1.0
        for e in edges:
            compounded_rate *= e.spot_rate

        hops = [
            ArbitrageHop(
                pool_id=e.pool.pool_id,
                dex_name=e.pool.dex_name,
                token_in=e.token_in,
                token_out=e.token_out,
                fee_bps=e.pool.fee_bps,
                pool=e.pool
            )
            for e in edges
        ]
        tokens = [e.token_in for e in edges] + [end_token]

        # Optimization function for sizing
        def sim_cycle(x_in: float) -> float:
            curr = x_in
            for h in hops:
                res = h.pool.get_amount_out(h.token_in, curr)
                curr = res.amount_out
            return curr

        # Solana gas fee: 5000 lamports base + 15000 lamports priority compute budget
        gas_cost_sol = 0.000020
        # If trading non-SOL base, convert gas to base token
        gas_in_base = gas_cost_sol if start_token == "SOL" else (gas_cost_sol * self.sol_price_usd)

        # Upper bound search
        max_search = 1000.0 if start_token in ["SOL", "USDC", "USDT"] else 100000000.0

        def neg_net_profit(x_in: float) -> float:
            if x_in <= 1e-6:
                return 0.0
            out = sim_cycle(x_in)
            net = out - x_in - gas_in_base
            return -net

        res = minimize_scalar(neg_net_profit, bounds=(0.01, max_search), method='bounded')
        optimal_in = float(res.x) if res.success else 1.0
        expected_out = sim_cycle(optimal_in)
        net_profit = expected_out - optimal_in - gas_in_base
        roi_pct = (net_profit / optimal_in * 100.0) if optimal_in > 0 else 0.0

        # USD calculation
        if start_token == "SOL":
            net_profit_usd = net_profit * self.sol_price_usd
        elif start_token in ["USDC", "USDT"]:
            net_profit_usd = net_profit
        else:
            net_profit_usd = net_profit * 0.000025  # rough BONK peg

        is_executable = (net_profit > 0 and compounded_rate > 1.0001)

        cycle_id = f"arb_{start_token}_{len(hops)}hop_{abs(hash(tuple(h.pool_id for h in hops))) % 10000:04d}"

        return ArbitrageOpportunity(
            cycle_id=cycle_id,
            tokens=tokens,
            hops=hops,
            gross_profit_ratio=compounded_rate,
            optimal_input_amount=optimal_in,
            expected_output_amount=expected_out,
            net_profit_amount=net_profit,
            net_profit_usd=net_profit_usd,
            estimated_gas_cost_sol=gas_cost_sol,
            roi_percent=roi_pct,
            is_executable=is_executable
        )
