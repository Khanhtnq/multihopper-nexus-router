import pytest
from src.routing.graph import DexGraph
from src.routing.yen_ksp import YenKSP
from src.routing.convex_optimizer import ConvexSplitOptimizer


def test_convex_split_optimizer_improvement():
    graph = DexGraph.create_default_solana_market()
    yen = YenKSP(graph)
    paths = yen.find_k_shortest_paths("SOL", "USDC", k=4)
    assert len(paths) >= 2

    optimizer = ConvexSplitOptimizer(paths)

    # Large trade volume (e.g. 500 SOL) where slippage makes splitting across pools strictly superior!
    result = optimizer.optimize_split(500.0)

    # Allocation weights must sum to 1.0
    weight_sum = sum(a.weight for a in result.allocations)
    assert pytest.approx(weight_sum, abs=1e-4) == 1.0

    # Total amount out must be >= single route output
    assert result.total_amount_out >= result.single_route_out
    assert result.gain_over_single_route >= 0.0

    # For 500 SOL across multiple parallel CLMM/DLMM pools, convex split should distribute non-trivially
    non_zero_allocs = [a for a in result.allocations if a.weight > 0.05]
    assert len(non_zero_allocs) >= 2


def test_convex_split_zero_and_small_amounts():
    graph = DexGraph.create_default_solana_market()
    yen = YenKSP(graph)
    paths = yen.find_k_shortest_paths("SOL", "USDC", k=3)

    optimizer = ConvexSplitOptimizer(paths)
    res_zero = optimizer.optimize_split(0.0)
    assert res_zero.total_amount_out == 0.0

    res_small = optimizer.optimize_split(0.1)
    assert res_small.total_amount_out > 0.0
    assert res_small.blended_rate > 100.0
