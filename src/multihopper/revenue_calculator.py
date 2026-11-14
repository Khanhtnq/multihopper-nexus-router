"""
MultiHopper Revenue & Superteam Earn Prize Pool Calculator.
Faithfully computes:
1. Ongoing Integrator Revenue: 0.25% of full-fee volume ($2,500 per $1M).
2. Dynamic Competition Prize Pool: Scales from $5,000 to $50,000 based on aggregate qualifying volume.
3. Proportional Winner Distribution: Prize = Total Funded Pool * (Your Volume / Top 3 Combined Volume).
"""

from typing import Dict, Any, List
from src.multihopper.config import PROTOCOL_FEES, SUPERTEAM_POOL_CONFIG


class RevenueCalculator:
    """
    Mathematical revenue and prize simulator for MultiHopper integrators.
    """
    @staticmethod
    def calculate_integrator_earnings(volume_usd: float) -> Dict[str, Any]:
        """
        Calculates the instant 0.25% revenue share for any routed volume.
        Customers pay 0.5% (50 bps) total fee, 50% of which (0.25% or 25 bps)
        is atomically routed to the integrator rewards wallet on-chain.
        """
        gross_fee_usd = volume_usd * (PROTOCOL_FEES["PERCENT_FEE_BPS"] / 10000.0)
        integrator_share_usd = volume_usd * (PROTOCOL_FEES["INTEGRATOR_SPLIT_BPS"] / 10000.0)
        protocol_share_usd = volume_usd * (PROTOCOL_FEES["PROTOCOL_REVENUE_BPS"] / 10000.0)

        return {
            "volume_usd": volume_usd,
            "gross_fee_usd": gross_fee_usd,
            "integrator_share_usd": integrator_share_usd,
            "protocol_share_usd": protocol_share_usd,
            "rate_per_million_usd": 2500.0,
            "integrator_split_percent": 0.25
        }

    @staticmethod
    def calculate_prize_pool(aggregate_volume_usd: float) -> float:
        """
        Calculates the unlocked prize pool size:
        - Must reach $2,000,000 aggregate for base $5,000 pool.
        - Every additional $400,000 unlocks another $1,000.
        - At $20,000,000 aggregate, max $50,000 pool is unlocked.
        """
        cfg = SUPERTEAM_POOL_CONFIG
        if aggregate_volume_usd < cfg["INITIAL_AWARD_MIN_AGGREGATE_USD"]:
            return 0.0

        excess_volume = aggregate_volume_usd - cfg["INITIAL_AWARD_MIN_AGGREGATE_USD"]
        additional_increments = int(excess_volume / cfg["VOLUME_INCREMENT_PER_1K_USD"])
        pool = cfg["BASE_PRIZE_POOL_USD"] + (additional_increments * 1000.0)
        return min(pool, cfg["MAX_PRIZE_POOL_USD"])

    @staticmethod
    def calculate_winner_share(
        your_qualifying_volume_usd: float,
        top3_volumes_usd: List[float],
        aggregate_competition_volume_usd: float
    ) -> Dict[str, Any]:
        """
        Calculates eligibility, competition prize share, and total return.
        Requirement: Product must generate >= $100,000 qualifying production volume.
        """
        cfg = SUPERTEAM_POOL_CONFIG
        is_qualified = your_qualifying_volume_usd >= cfg["MIN_QUALIFYING_VOLUME_USD"]
        funded_pool = RevenueCalculator.calculate_prize_pool(aggregate_competition_volume_usd)

        # Combined volume of top three products
        sorted_top3 = sorted(top3_volumes_usd, reverse=True)[:3]
        top3_combined = sum(sorted_top3)

        if not is_qualified or top3_combined <= 0 or funded_pool <= 0:
            prize_share_usd = 0.0
            volume_share_pct = 0.0
        else:
            volume_share_pct = (your_qualifying_volume_usd / top3_combined) * 100.0
            prize_share_usd = funded_pool * (your_qualifying_volume_usd / top3_combined)

        earnings = RevenueCalculator.calculate_integrator_earnings(your_qualifying_volume_usd)
        total_payout_usd = earnings["integrator_share_usd"] + prize_share_usd

        return {
            "your_volume_usd": your_qualifying_volume_usd,
            "is_qualified": is_qualified,
            "funded_pool_usd": funded_pool,
            "top3_combined_volume_usd": top3_combined,
            "volume_share_among_winners_pct": volume_share_pct,
            "prize_share_usd": prize_share_usd,
            "integration_revenue_usd": earnings["integrator_share_usd"],
            "total_payout_usd": total_payout_usd,
            "effective_yield_bps": (total_payout_usd / your_qualifying_volume_usd * 10000.0) if your_qualifying_volume_usd > 0 else 0.0
        }
