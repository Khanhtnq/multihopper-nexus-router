import pytest
from src.multihopper.client import MultiHopperClient
from src.multihopper.config import PROTOCOL_FEES, FEE_TIERS


def test_multihopper_percent_fee_schedule():
    client = MultiHopperClient()
    # 10 SOL transfer (at $150/SOL = $1,500)
    quote = client.estimate_transfer(
        token_mint="So11111111111111111111111111111111111111112",
        amount_tokens=10.0,
        source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
        hops=3
    )
    # Total commercial percent fee is 50 bps = 0.50%
    assert quote["percentFeeBps"] == 50
    assert quote["percentFeeTokens"] == 0.05  # 10.0 * 0.005
    assert quote["netHopAmountTokens"] == 9.95

    # Integrator receives exactly 50% of the percent fee = 0.025 SOL
    assert quote["integratorShareTokens"] == 0.025


def test_multihopper_tier_selection_and_flat_fees():
    client = MultiHopperClient()
    # $50 transfer -> should fall into Tier 0 (max $100)
    q_low = client.estimate_transfer(
        token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        amount_tokens=50.0,
        source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
        hops=3,
        price_usd_per_token=1.0
    )
    assert q_low["tierIndex"] == 0
    # Tier 0 flat fees: route 0.0002 + 3 * 0.0001 = 0.0005 SOL
    assert pytest.approx(q_low["totalFlatFeeSol"], rel=1e-5) == 0.0005

    # $50,000 transfer -> Tier 3 (max $100,000)
    q_high = client.estimate_transfer(
        token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        amount_tokens=50000.0,
        source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
        hops=4,
        price_usd_per_token=1.0
    )
    assert q_high["tierIndex"] == 3
    # Tier 3: route 0.0050 + 4 * 0.0010 = 0.0090 SOL
    assert pytest.approx(q_high["totalFlatFeeSol"], rel=1e-5) == 0.0090


def test_multihopper_upfront_sol_requirements():
    client = MultiHopperClient()
    quote = client.estimate_transfer(
        token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        amount_tokens=100.0,
        source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
        hops=3
    )
    # Required upfront SOL must include: totalFlatFee + screening + keeperFunding + rent
    sol_dict = quote["sol"]
    assert sol_dict["requiredSolUpFront"] > sol_dict["screeningFeeSol"]
    assert sol_dict["screeningFeeSol"] == 0.004  # 0.002 * 2 (source + recipient)
    assert sol_dict["requiredSolUpFrontLamports"] == int(sol_dict["requiredSolUpFront"] * 1e9)
