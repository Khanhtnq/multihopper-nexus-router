import pytest
from src.dex.amm_pool import DynamicBinPool


def test_dlmm_spot_price_and_volatility_fee():
    pool = DynamicBinPool(
        pool_id="meteora_test_dlmm",
        dex_name="Meteora DLMM",
        token_a="SOL",
        token_b="USDC",
        active_bin_price=150.0,
        bin_step_bps=10.0,
        bin_liquidity_depth=10000.0,
        base_fee_bps=6.0,
        volatility_fee_bps=4.0
    )
    # Total fee = 6 + 4 = 10 bps (0.10%)
    assert pool.fee_bps == 10.0
    spot = pool.get_spot_price("SOL")
    assert pytest.approx(spot, rel=1e-5) == 150.0 * (1.0 - 0.0010)


def test_dlmm_bin_crossing_progression():
    pool = DynamicBinPool(
        pool_id="meteora_test_dlmm",
        dex_name="Meteora DLMM",
        token_a="SOL",
        token_b="USDC",
        active_bin_price=150.0,
        bin_step_bps=10.0,
        bin_liquidity_depth=50.0,  # 50 SOL capacity per bin
        base_fee_bps=6.0,
        volatility_fee_bps=2.0
    )
    # Small trade within single bin (10 SOL < 50 SOL)
    res_small = pool.get_amount_out("SOL", 10.0)
    assert res_small.next_state["bins_crossed"] == 1

    # Large trade crossing multiple bins (120 SOL > 50 SOL * 2)
    res_large = pool.get_amount_out("SOL", 120.0)
    assert res_large.next_state["bins_crossed"] >= 3
    # Effective rate of large trade must be lower than small trade
    assert res_large.effective_rate < res_small.effective_rate
