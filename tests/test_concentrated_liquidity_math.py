import pytest
import math
from src.dex.amm_pool import ConcentratedLiquidityPool


def test_concentrated_liquidity_spot_and_ticks():
    # Orca Whirlpool: P = 150.0, range [100.0, 200.0], L = 500,000, fee = 5 bps
    pool = ConcentratedLiquidityPool(
        pool_id="orca_test_clmm",
        dex_name="Orca Whirlpool",
        token_a="SOL",
        token_b="USDC",
        liquidity=500000.0,
        current_price=150.0,
        price_lower=100.0,
        price_upper=200.0,
        fee_bps=5.0
    )
    spot = pool.get_spot_price("SOL")
    assert pytest.approx(spot, rel=1e-4) == 150.0 * (1.0 - 0.0005)

    # Inverted spot for USDC
    spot_usdc = pool.get_spot_price("USDC")
    assert pytest.approx(spot_usdc, rel=1e-4) == (1.0 / 150.0) * (1.0 - 0.0005)


def test_clmm_swap_formula_and_impact():
    pool = ConcentratedLiquidityPool(
        pool_id="orca_test_clmm",
        dex_name="Orca Whirlpool",
        token_a="SOL",
        token_b="USDC",
        liquidity=500000.0,
        current_price=150.0,
        price_lower=100.0,
        price_upper=200.0,
        fee_bps=5.0
    )
    # 10 SOL swap
    res = pool.get_amount_out("SOL", 10.0)
    assert res.amount_out > 0.0
    # Spot is ~149.925 -> 10 SOL should yield slightly less due to price movement
    assert 1400.0 < res.amount_out < 1500.0
    assert res.fee_amount == 10.0 * 0.0005

    # Reverse swap (USDC -> SOL)
    res_b = pool.get_amount_out("USDC", 1500.0)
    assert res_b.amount_out > 0.0
    assert 9.0 < res_b.amount_out < 10.0


def test_clmm_boundary_clamping():
    pool = ConcentratedLiquidityPool(
        pool_id="orca_test_clmm",
        dex_name="Orca Whirlpool",
        token_a="SOL",
        token_b="USDC",
        liquidity=1000.0,  # small liquidity to force boundary hit
        current_price=150.0,
        price_lower=140.0,
        price_upper=160.0,
        fee_bps=5.0
    )
    # Huge trade that exceeds lower tick boundary
    res = pool.get_amount_out("SOL", 100000.0)
    assert res.amount_out > 0.0
    # Sqrt_p_next must not exceed sqrt_p_lower
    assert res.next_state["price_next"] >= 140.0
