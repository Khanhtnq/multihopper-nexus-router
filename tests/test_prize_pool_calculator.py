import pytest
from src.multihopper.revenue_calculator import RevenueCalculator


def test_qualification_volume_threshold():
    # If product does not reach $100k, not qualified
    sim_unqualified = RevenueCalculator.calculate_winner_share(
        your_qualifying_volume_usd=99999.0,
        top3_volumes_usd=[500000.0, 300000.0, 200000.0],
        aggregate_competition_volume_usd=5000000.0
    )
    assert sim_unqualified["is_qualified"] is False
    assert sim_unqualified["prize_share_usd"] == 0.0

    # Exactly $100k qualifies
    sim_qualified = RevenueCalculator.calculate_winner_share(
        your_qualifying_volume_usd=100000.0,
        top3_volumes_usd=[500000.0, 300000.0, 100000.0],
        aggregate_competition_volume_usd=5000000.0
    )
    assert sim_qualified["is_qualified"] is True
    assert sim_qualified["prize_share_usd"] > 0.0


def test_exact_50k_cap_at_20m_aggregate():
    # Milestone test: $20M aggregated unlocks the maximum $50,000 pool
    pool_20m = RevenueCalculator.calculate_prize_pool(20000000.0)
    assert pool_20m == 50000.0

    # Intermediate milestone: $11M aggregate funds $27,000 pool
    pool_11m = RevenueCalculator.calculate_prize_pool(11000000.0)
    # $11M - $2M = $9M -> 9M / 400k = 22.5 -> 22 increments * $1000 = $22,000 + $5,000 = $27,000!
    assert pool_11m == 27000.0
