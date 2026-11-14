import pytest
from src.pipeline.swaps_with_hooks import SwapsWithHooksPipeline


def test_swaps_with_hooks_pipeline_execution():
    pipeline = SwapsWithHooksPipeline()

    # User executes swap of 5 SOL -> USDC with 3-hop privacy transfer
    res = pipeline.execute_swap_and_route(
        token_in="SOL",
        token_out="USDC",
        amount_in=5.0,
        source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
        recipient_wallet="H4iZ7C2Z1rXgQ2Xy9J4K6M3P8T9W1V5L2B8N4M7K9L2P",
        custom_hops=3
    )

    assert res.status == "SETTLED_AND_CONFIRMED"
    assert res.dex_routing.total_amount_out > 700.0  # 5 SOL * ~$150 > 700 USDC
    assert res.dex_routing.blended_price_impact >= 0.0
    assert res.multihopper_transfer_id.startswith("trf_")
    assert res.integrator_revenue_usd > 0.0
    assert res.webhook_payload["event"] == "transfer.settled"


def test_swaps_with_hooks_multi_destination_split():
    pipeline = SwapsWithHooksPipeline()

    # User swaps 10 SOL and disburses proceeds across 3 treasury addresses (50%, 30%, 20%)
    destinations = [
        {"wallet": "Treasury_Alpha", "share": 0.5},
        {"wallet": "Treasury_Beta", "share": 0.3},
        {"wallet": "Treasury_Gamma", "share": 0.2},
    ]

    res = pipeline.execute_swap_and_route(
        token_in="SOL",
        token_out="USDC",
        amount_in=10.0,
        source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
        destinations=destinations,
        custom_hops=2
    )

    assert len(res.destinations) == 3
    total_tokens = sum(d["amountTokens"] for d in res.destinations)
    assert pytest.approx(total_tokens, rel=1e-5) == res.dex_routing.total_amount_out
    assert pytest.approx(res.destinations[0]["amountTokens"], rel=1e-3) == total_tokens * 0.5
