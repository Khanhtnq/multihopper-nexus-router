import pytest
from src.dex.amm_pool import OrderbookCFMMPool


def test_orderbook_cfmm_oracle_anchoring():
    pool = OrderbookCFMMPool(
        pool_id="phoenix_test",
        dex_name="Phoenix",
        token_a="SOL",
        token_b="USDC",
        oracle_price=150.0,
        pool_capacity=200000.0,
        fee_bps=2.0,
        inventory_skew_coeff=0.00002
    )
    spot = pool.get_spot_price("SOL")
    # fee 2 bps = 0.02%
    assert pytest.approx(spot, rel=1e-5) == 150.0 * (1.0 - 0.0002)


def test_orderbook_inventory_skew():
    pool = OrderbookCFMMPool(
        pool_id="phoenix_test",
        dex_name="Phoenix",
        token_a="SOL",
        token_b="USDC",
        oracle_price=150.0,
        pool_capacity=200000.0,
        fee_bps=2.0,
        inventory_skew_coeff=0.00005
    )
    # Increasing trade size must decay execution price due to inventory skew penalty
    res_1 = pool.get_amount_out("SOL", 1.0)
    res_100 = pool.get_amount_out("SOL", 100.0)

    assert res_1.effective_rate > res_100.effective_rate
    assert res_100.price_impact > res_1.price_impact
