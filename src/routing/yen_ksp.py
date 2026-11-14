"""
Yen's K-Shortest Path Algorithm for Solana Multi-Hop DEX Routing.
Finds top K candidate loopless paths connecting source and destination tokens across multiple DEX liquidity pools.
"""

import heapq
import copy
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from src.routing.graph import DexGraph, Edge
from src.dex.amm_pool import SwapResult


@dataclass
class RouteHop:
    pool_id: str
    dex_name: str
    token_in: str
    token_out: str
    fee_bps: float
    pool: Any = None  # Reference to BasePool


@dataclass
class RoutePath:
    path_id: str
    hops: List[RouteHop]
    total_fee_bps: float
    spot_rate: float
    log_cost: float

    def simulate_execution(self, amount_in: float) -> Tuple[float, float, List[SwapResult]]:
        """
        Simulate sequential execution through all hops in this route.
        Returns: (final_amount_out, aggregate_price_impact, hop_results)
        """
        current_amount = amount_in
        total_price_impact = 0.0
        hop_results: List[SwapResult] = []

        for hop in self.hops:
            res = hop.pool.get_amount_out(hop.token_in, current_amount)
            hop_results.append(res)
            # Accumulate slippage impact: 1 - prod(1 - impact_i)
            total_price_impact = 1.0 - (1.0 - total_price_impact) * (1.0 - res.price_impact)
            current_amount = res.amount_out

        return current_amount, total_price_impact, hop_results

    def describe(self) -> str:
        steps = [f"{h.token_in} -[{h.dex_name}]-> {h.token_out}" for h in self.hops]
        return " => ".join(steps)


class YenKSP:
    """
    Computes top K loopless paths from source to target token.
    Uses negative log price weights: w = -ln(spot_rate).
    Shortest path in log-weight corresponds to highest compounding exchange rate!
    """
    def __init__(self, graph: DexGraph):
        self.graph = graph

    def dijkstra_shortest_path(self, source: str, target: str,
                               excluded_edges: Set[Tuple[str, str, str]] = None,
                               excluded_nodes: Set[str] = None) -> Optional[List[Edge]]:
        """
        Dijkstra on log weights with exclusions.
        excluded_edges: set of (token_in, pool_id, token_out)
        excluded_nodes: set of token symbols
        """
        if excluded_edges is None:
            excluded_edges = set()
        if excluded_nodes is None:
            excluded_nodes = set()

        # Priority queue: (dist, current_node, path_edges)
        pq: List[Tuple[float, str, List[Edge]]] = [(0.0, source, [])]
        best_dist: Dict[str, float] = {source: 0.0}

        while pq:
            cost, u, path = heapq.heappop(pq)

            if u == target:
                return path

            if cost > best_dist.get(u, float('inf')):
                continue

            for edge in self.graph.get_edges(u):
                v = edge.token_out
                if v in excluded_nodes:
                    continue
                edge_sig = (edge.token_in, edge.pool.pool_id, edge.token_out)
                if edge_sig in excluded_edges:
                    continue

                w = edge.log_weight
                new_cost = cost + w

                if new_cost < best_dist.get(v, float('inf')):
                    best_dist[v] = new_cost
                    heapq.heappush(pq, (new_cost, v, path + [edge]))

        return None

    def find_k_shortest_paths(self, source: str, target: str, k: int = 5, max_hops: int = 4) -> List[RoutePath]:
        """
        Yen's algorithm finding up to K paths, restricted to max_hops.
        """
        if source == target:
            return []

        # Find first shortest path A[0]
        first_edges = self.dijkstra_shortest_path(source, target)
        if not first_edges or len(first_edges) > max_hops:
            return []

        A: List[List[Edge]] = [first_edges]
        # Candidate paths B
        B: List[Tuple[float, List[Edge]]] = []

        for i in range(1, k):
            prev_path = A[i - 1]

            # The spur node ranges from the first node to the second to last node in the previous path
            for j in range(len(prev_path)):
                spur_node = prev_path[j].token_in
                root_path = prev_path[:j]

                excluded_edges: Set[Tuple[str, str, str]] = set()
                excluded_nodes: Set[str] = set()

                for p in A:
                    if len(p) > j and p[:j] == root_path:
                        edge_to_exclude = p[j]
                        excluded_edges.add((edge_to_exclude.token_in,
                                            edge_to_exclude.pool.pool_id,
                                            edge_to_exclude.token_out))

                # Exclude root path nodes except spur_node to avoid cycles
                for edge in root_path:
                    if edge.token_in != spur_node:
                        excluded_nodes.add(edge.token_in)

                spur_path = self.dijkstra_shortest_path(spur_node, target, excluded_edges, excluded_nodes)

                if spur_path:
                    total_candidate = root_path + spur_path
                    if len(total_candidate) <= max_hops:
                        # Calculate total log cost
                        cand_cost = sum(e.log_weight for e in total_candidate)
                        # Add to B if not already present
                        if not any(b_path == total_candidate for _, b_path in B):
                            heapq.heappush(B, (cand_cost, total_candidate))

            if not B:
                break

            # Pop best candidate
            _, best_candidate = heapq.heappop(B)
            A.append(best_candidate)

        # Convert edge paths into RoutePath objects
        result_paths: List[RoutePath] = []
        for idx, edges in enumerate(A):
            hops: List[RouteHop] = []
            total_fee = 0.0
            compounded_rate = 1.0
            log_cost = 0.0

            for e in edges:
                hops.append(RouteHop(
                    pool_id=e.pool.pool_id,
                    dex_name=e.pool.dex_name,
                    token_in=e.token_in,
                    token_out=e.token_out,
                    fee_bps=e.pool.fee_bps,
                    pool=e.pool
                ))
                total_fee += e.pool.fee_bps
                compounded_rate *= e.spot_rate
                log_cost += e.log_weight

            result_paths.append(RoutePath(
                path_id=f"route_{source}_{target}_{idx+1}",
                hops=hops,
                total_fee_bps=total_fee,
                spot_rate=compounded_rate,
                log_cost=log_cost
            ))

        return result_paths
