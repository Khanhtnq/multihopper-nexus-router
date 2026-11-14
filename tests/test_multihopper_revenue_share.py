import pytest
from src.multihopper.revenue_calculator import RevenueCalculator


def test_revenue_share_rate():
    # Sourced from challenge: "$2,500 for every $1 million routed (0.25% of full-fee volume)"
    res_1m = RevenueCalculator.calculate_integrator_earnings(1000000.0)
    assert res_1m["integrator_share_usd"] == 2500.0
    assert res_1m["gross_fee_usd"] == 5000.0
    assert res_1m["protocol_share_usd"] == 2500.0

    res_10m = RevenueCalculator.calculate_integrator_earnings(10000000.0)
    assert res_10m["integrator_share_usd"] == 25000.0


def test_prize_pool_scaling_curve():
    # < $2M aggregate volume -> $0 funded pool
    assert RevenueCalculator.calculate_prize_pool(1500000.0) == 0.0

    # Exactly $2M aggregate volume -> $5,000 base pool
    assert RevenueCalculator.calculate_prize_pool(2000000.0) == 5000.0

    # $4M aggregate volume -> $2M + 5 * $400k = $5,000 + 5 * $1,000 = $10,000
    assert RevenueCalculator.calculate_prize_pool(4000000.0) == 10000.0

    # $8M aggregate volume -> $2M + 15 * $400k = $5,000 + 15 * $1,000 = $20,000
    assert RevenueCalculator.calculate_prize_pool(8000000.0) == 20000.0

    # $20M aggregate volume -> capped at $50,000 max pool
    assert RevenueCalculator.calculate_prize_pool(20000000.0) == 50000.0
    assert RevenueCalculator.calculate_prize_pool(30000000.0) == 50000.0


def test_winner_proportional_distribution():
    # If your product generates $800k out of $2M top-3 volume (40%), you receive 40% of the funded pool!
    sim = RevenueCalculator.calculate_winner_share(
        your_qualifying_volume_usd=800000.0,
        top3_volumes_usd=[800000.0, 700000.0, 500000.0],
        aggregate_competition_volume_usd=4000000.0  # funds $10,000 pool
    )
    assert sim["is_qualified"] is True
    assert sim["funded_pool_usd"] == 10000.0
    assert sim["top3_combined_volume_usd"] == 2000000.0
    assert sim["volume_share_among_winners_pct"] == 40.0
    assert sim["prize_share_usd"] == 4000.0  # 40% of $10,000
    assert sim["integration_revenue_usd"] == 2000.0  # 0.25% of $800k
    assert sim["total_payout_usd"] == 6000.0
