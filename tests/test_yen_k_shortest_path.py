import pytest
from src.routing.graph import DexGraph
from src.routing.yen_ksp import YenKSP


def test_yen_ksp_finds_multiple_paths():
    graph = DexGraph.create_default_solana_market()
    yen = YenKSP(graph)

    # Find top 4 paths from SOL to USDC
    paths = yen.find_k_shortest_paths("SOL", "USDC", k=4)
    assert len(paths) >= 2

    # Paths must be sorted in order of non-decreasing log cost (best rate first)
    costs = [p.log_cost for p in paths]
    assert costs == sorted(costs)

    # Each path must start at SOL and end at USDC
    for p in paths:
        assert p.hops[0].token_in == "SOL"
        assert p.hops[-1].token_out == "USDC"


def test_yen_ksp_multi_hop_compounding():
    graph = DexGraph.create_default_solana_market()
    yen = YenKSP(graph)

    # Test route from BONK to JUP (multi-hop required)
    paths = yen.find_k_shortest_paths("BONK", "JUP", k=3)
    assert len(paths) >= 1

    best_path = paths[0]
    out, impact, hop_res = best_path.simulate_execution(100000.0)
    assert out > 0.0
    assert len(hop_res) >= 1
