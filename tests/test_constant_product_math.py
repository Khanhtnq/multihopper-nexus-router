import pytest
from src.dex.amm_pool import ConstantProductPool


def test_constant_product_spot_price():
    # Reserve A: 1000 SOL, Reserve B: 150,000 USDC, fee: 25 bps (0.25%)
    pool = ConstantProductPool(
        pool_id="pool_test_amm",
        dex_name="Raydium AMM",
        token_a="SOL",
        token_b="USDC",
        reserve_a=1000.0,
        reserve_b=150000.0,
        fee_bps=25.0
    )
    # Spot price without fee = 150.0; with 25 bps fee = 150.0 * 0.9975 = 149.625
    spot_a = pool.get_spot_price("SOL")
    assert pytest.approx(spot_a, rel=1e-4) == 149.625

    spot_b = pool.get_spot_price("USDC")
    assert pytest.approx(spot_b, rel=1e-4) == (1000.0 / 150000.0) * 0.9975


def test_constant_product_swap_invariants():
    pool = ConstantProductPool(
        pool_id="pool_test_amm",
        dex_name="Raydium AMM",
        token_a="SOL",
        token_b="USDC",
        reserve_a=1000.0,
        reserve_b=150000.0,
        fee_bps=25.0
    )
    k_initial = pool.reserve_a * pool.reserve_b

    # Small trade: 1 SOL
    res = pool.get_amount_out("SOL", 1.0)
    assert res.amount_out > 0.0
    assert res.amount_out < 150.0
    assert res.fee_amount == 0.0025
    assert res.price_impact > 0.0
    assert res.price_impact < 0.01  # < 1% impact for 1 SOL in 1000 SOL pool

    # Invariant check: (reserve_in + net_in) * (reserve_out - out) >= k_initial
    net_in = 1.0 - 0.0025
    k_after = (pool.reserve_a + net_in) * (pool.reserve_b - res.amount_out)
    assert pytest.approx(k_after, rel=1e-6) == k_initial


def test_constant_product_slippage_monotonicity():
    pool = ConstantProductPool(
        pool_id="pool_test_amm",
        dex_name="Raydium AMM",
        token_a="SOL",
        token_b="USDC",
        reserve_a=1000.0,
        reserve_b=150000.0,
        fee_bps=25.0
    )
    # As amount_in increases, effective rate must decrease (slippage increases)
    res_1 = pool.get_amount_out("SOL", 1.0)
    res_10 = pool.get_amount_out("SOL", 10.0)
    res_100 = pool.get_amount_out("SOL", 100.0)

    assert res_1.effective_rate > res_10.effective_rate > res_100.effective_rate
    assert res_1.price_impact < res_10.price_impact < res_100.price_impact
