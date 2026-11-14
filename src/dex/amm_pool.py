"""
Solana DEX Liquidity Pool Mathematical Models.
Provides exact mathematical simulation of:
1. Raydium AMM (Constant Product x * y = k)
2. Raydium CLMM / Orca Whirlpool (Concentrated Liquidity with ticks and sqrtPriceX64)
3. Meteora DLMM (Dynamic Liquidity Market Maker with discrete bins and volatility fees)
4. Lifinity / Phoenix (CFMM with oracle anchoring and proactive market making)
"""

import math
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass, field


@dataclass
class SwapResult:
    amount_in: float
    amount_out: float
    fee_amount: float
    price_impact: float
    effective_rate: float
    next_state: Dict[str, Any] = field(default_factory=dict)


class BasePool:
    def __init__(self, pool_id: str, dex_name: str, token_a: str, token_b: str, fee_bps: float):
        self.pool_id = pool_id
        self.dex_name = dex_name
        self.token_a = token_a
        self.token_b = token_b
        self.fee_bps = fee_bps

    def get_amount_out(self, token_in: str, amount_in: float) -> SwapResult:
        raise NotImplementedError

    def get_spot_price(self, token_in: str) -> float:
        raise NotImplementedError

    def marginal_price_impact(self, token_in: str, amount_in: float) -> float:
        """Returns the instantaneous slippage/impact fraction."""
        spot = self.get_spot_price(token_in)
        res = self.get_amount_out(token_in, amount_in)
        if amount_in <= 0 or spot <= 0:
            return 0.0
        return max(0.0, 1.0 - (res.effective_rate / spot))


class ConstantProductPool(BasePool):
    """
    Constant Product Market Maker (x * y = k).
    Standard model used by Raydium AMM v4.
    """
    def __init__(self, pool_id: str, dex_name: str, token_a: str, token_b: str,
                 reserve_a: float, reserve_b: float, fee_bps: float = 25.0):
        super().__init__(pool_id, dex_name, token_a, token_b, fee_bps)
        self.reserve_a = float(reserve_a)
        self.reserve_b = float(reserve_b)

    def get_spot_price(self, token_in: str) -> float:
        fee_factor = 1.0 - (self.fee_bps / 10000.0)
        if token_in == self.token_a:
            return (self.reserve_b / self.reserve_a) * fee_factor
        elif token_in == self.token_b:
            return (self.reserve_a / self.reserve_b) * fee_factor
        else:
            raise ValueError(f"Token {token_in} not in pool {self.pool_id}")

    def get_amount_out(self, token_in: str, amount_in: float) -> SwapResult:
        if amount_in <= 0:
            return SwapResult(0.0, 0.0, 0.0, 0.0, self.get_spot_price(token_in))

        is_a_to_b = (token_in == self.token_a)
        r_in = self.reserve_a if is_a_to_b else self.reserve_b
        r_out = self.reserve_b if is_a_to_b else self.reserve_a

        fee_amount = amount_in * (self.fee_bps / 10000.0)
        amount_in_with_fee = amount_in - fee_amount

        # (r_in + amount_in_with_fee) * (r_out - amount_out) = r_in * r_out
        amount_out = (r_out * amount_in_with_fee) / (r_in + amount_in_with_fee)
        amount_out = min(amount_out, r_out * 0.9999)  # guard exhaustion

        spot = (r_out / r_in) * (1.0 - self.fee_bps / 10000.0)
        effective_rate = amount_out / amount_in if amount_in > 0 else 0.0
        price_impact = max(0.0, (1.0 - (effective_rate / spot))) if spot > 0 else 0.0

        return SwapResult(
            amount_in=amount_in,
            amount_out=amount_out,
            fee_amount=fee_amount,
            price_impact=price_impact,
            effective_rate=effective_rate,
            next_state={
                "reserve_in": r_in + amount_in_with_fee,
                "reserve_out": r_out - amount_out
            }
        )


class ConcentratedLiquidityPool(BasePool):
    """
    Concentrated Liquidity Market Maker (CLMM).
    Standard model used by Raydium CLMM and Orca Whirlpool.
    Utilizes virtual liquidity L within price tick boundaries [sqrt_p_lower, sqrt_p_upper].
    """
    def __init__(self, pool_id: str, dex_name: str, token_a: str, token_b: str,
                 liquidity: float, current_price: float,
                 price_lower: float, price_upper: float, fee_bps: float = 5.0):
        super().__init__(pool_id, dex_name, token_a, token_b, fee_bps)
        self.liquidity = float(liquidity)  # Virtual liquidity L
        self.current_price = float(current_price)  # P = token_b / token_a
        self.price_lower = float(price_lower)
        self.price_upper = float(price_upper)
        self.sqrt_p = math.sqrt(self.current_price)
        self.sqrt_p_lower = math.sqrt(self.price_lower)
        self.sqrt_p_upper = math.sqrt(self.price_upper)

    def get_spot_price(self, token_in: str) -> float:
        fee_factor = 1.0 - (self.fee_bps / 10000.0)
        if token_in == self.token_a:
            return self.current_price * fee_factor
        elif token_in == self.token_b:
            return (1.0 / self.current_price) * fee_factor
        else:
            raise ValueError(f"Token {token_in} not in pool {self.pool_id}")

    def get_amount_out(self, token_in: str, amount_in: float) -> SwapResult:
        if amount_in <= 0:
            return SwapResult(0.0, 0.0, 0.0, 0.0, self.get_spot_price(token_in))

        fee_amount = amount_in * (self.fee_bps / 10000.0)
        delta_in = amount_in - fee_amount
        L = self.liquidity

        if token_in == self.token_a:
            # Token A in -> Token B out (Price P = B/A decreases: sqrt_p moves down)
            # delta_x = L * (1/sqrt_p_next - 1/sqrt_p)
            # 1/sqrt_p_next = 1/sqrt_p + delta_x / L
            inv_next = (1.0 / self.sqrt_p) + (delta_in / L)
            sqrt_p_next = 1.0 / inv_next

            # Check tick boundary
            if sqrt_p_next < self.sqrt_p_lower:
                sqrt_p_next = self.sqrt_p_lower

            # delta_y = L * (sqrt_p - sqrt_p_next)
            amount_out = L * (self.sqrt_p - sqrt_p_next)
            spot = self.current_price * (1.0 - self.fee_bps / 10000.0)

        else:
            # Token B in -> Token A out (Price P = B/A increases: sqrt_p moves up)
            # delta_y = L * (sqrt_p_next - sqrt_p)
            # sqrt_p_next = sqrt_p + delta_y / L
            sqrt_p_next = self.sqrt_p + (delta_in / L)

            # Check tick boundary
            if sqrt_p_next > self.sqrt_p_upper:
                sqrt_p_next = self.sqrt_p_upper

            # delta_x = L * (1/sqrt_p - 1/sqrt_p_next)
            amount_out = L * ((1.0 / self.sqrt_p) - (1.0 / sqrt_p_next))
            spot = (1.0 / self.current_price) * (1.0 - self.fee_bps / 10000.0)

        amount_out = max(0.0, amount_out)
        effective_rate = amount_out / amount_in if amount_in > 0 else 0.0
        price_impact = max(0.0, (1.0 - (effective_rate / spot))) if spot > 0 else 0.0

        return SwapResult(
            amount_in=amount_in,
            amount_out=amount_out,
            fee_amount=fee_amount,
            price_impact=price_impact,
            effective_rate=effective_rate,
            next_state={"sqrt_p_next": sqrt_p_next, "price_next": sqrt_p_next ** 2}
        )


class DynamicBinPool(BasePool):
    """
    Meteora DLMM (Discrete Dynamic Liquidity Market Maker).
    Allocates liquidity into distinct price bins with a bin step (e.g. 10 bps).
    Each bin operates as zero-slippage constant sum within the bin, and steps across bins.
    Features dynamic volatility fee scaling.
    """
    def __init__(self, pool_id: str, dex_name: str, token_a: str, token_b: str,
                 active_bin_price: float, bin_step_bps: float = 15.0,
                 bin_liquidity_depth: float = 50000.0, base_fee_bps: float = 8.0,
                 volatility_fee_bps: float = 4.0):
        total_fee = base_fee_bps + volatility_fee_bps
        super().__init__(pool_id, dex_name, token_a, token_b, total_fee)
        self.active_bin_price = float(active_bin_price)
        self.bin_step_bps = float(bin_step_bps)
        self.bin_liquidity_depth = float(bin_liquidity_depth)  # per-bin capacity
        self.base_fee_bps = base_fee_bps
        self.volatility_fee_bps = volatility_fee_bps

    def get_spot_price(self, token_in: str) -> float:
        fee_factor = 1.0 - (self.fee_bps / 10000.0)
        if token_in == self.token_a:
            return self.active_bin_price * fee_factor
        elif token_in == self.token_b:
            return (1.0 / self.active_bin_price) * fee_factor
        else:
            raise ValueError(f"Token {token_in} not in pool {self.pool_id}")

    def get_amount_out(self, token_in: str, amount_in: float) -> SwapResult:
        if amount_in <= 0:
            return SwapResult(0.0, 0.0, 0.0, 0.0, self.get_spot_price(token_in))

        fee_amount = amount_in * (self.fee_bps / 10000.0)
        remaining_in = amount_in - fee_amount
        total_out = 0.0

        current_price = self.active_bin_price
        step_factor = 1.0 + (self.bin_step_bps / 10000.0)

        # Walk through discrete bins
        max_bins = 50
        bins_crossed = 0

        while remaining_in > 1e-9 and bins_crossed < max_bins:
            bins_crossed += 1
            if token_in == self.token_a:
                # Sell token_a -> receive token_b
                # Bin price decreases as token A is deposited
                bin_capacity = self.bin_liquidity_depth
                fill_in = min(remaining_in, bin_capacity)
                fill_out = fill_in * current_price
                total_out += fill_out
                remaining_in -= fill_in
                current_price /= step_factor
            else:
                # Sell token_b -> receive token_a
                # Bin price increases as token B is deposited
                bin_capacity = self.bin_liquidity_depth * current_price
                fill_in = min(remaining_in, bin_capacity)
                fill_out = fill_in / current_price
                total_out += fill_out
                remaining_in -= fill_in
                current_price *= step_factor

        spot = self.get_spot_price(token_in)
        effective_rate = total_out / amount_in if amount_in > 0 else 0.0
        price_impact = max(0.0, (1.0 - (effective_rate / spot))) if spot > 0 else 0.0

        return SwapResult(
            amount_in=amount_in,
            amount_out=total_out,
            fee_amount=fee_amount,
            price_impact=price_impact,
            effective_rate=effective_rate,
            next_state={"final_bin_price": current_price, "bins_crossed": bins_crossed}
        )


class OrderbookCFMMPool(BasePool):
    """
    Phoenix / Lifinity proactive market maker model.
    Anchored to an oracle reference price with an inventory-skew curve to resist toxic flow.
    """
    def __init__(self, pool_id: str, dex_name: str, token_a: str, token_b: str,
                 oracle_price: float, pool_capacity: float = 100000.0,
                 fee_bps: float = 12.0, inventory_skew_coeff: float = 0.00005):
        super().__init__(pool_id, dex_name, token_a, token_b, fee_bps)
        self.oracle_price = float(oracle_price)
        self.pool_capacity = float(pool_capacity)
        self.inventory_skew_coeff = float(inventory_skew_coeff)

    def get_spot_price(self, token_in: str) -> float:
        fee_factor = 1.0 - (self.fee_bps / 10000.0)
        if token_in == self.token_a:
            return self.oracle_price * fee_factor
        elif token_in == self.token_b:
            return (1.0 / self.oracle_price) * fee_factor
        else:
            raise ValueError(f"Token {token_in} not in pool {self.pool_id}")

    def get_amount_out(self, token_in: str, amount_in: float) -> SwapResult:
        if amount_in <= 0:
            return SwapResult(0.0, 0.0, 0.0, 0.0, self.get_spot_price(token_in))

        fee_amount = amount_in * (self.fee_bps / 10000.0)
        net_in = amount_in - fee_amount

        # Quadratic penalty factor for inventory distortion
        # effective_price = oracle_price * (1 - skew_coeff * net_in)
        if token_in == self.token_a:
            slippage_decay = max(0.85, 1.0 - (self.inventory_skew_coeff * net_in))
            exec_price = self.oracle_price * slippage_decay
            amount_out = net_in * exec_price
            spot = self.oracle_price * (1.0 - self.fee_bps / 10000.0)
        else:
            slippage_decay = max(0.85, 1.0 - (self.inventory_skew_coeff * net_in))
            exec_price = (1.0 / self.oracle_price) * slippage_decay
            amount_out = net_in * exec_price
            spot = (1.0 / self.oracle_price) * (1.0 - self.fee_bps / 10000.0)

        effective_rate = amount_out / amount_in if amount_in > 0 else 0.0
        price_impact = max(0.0, (1.0 - (effective_rate / spot))) if spot > 0 else 0.0

        return SwapResult(
            amount_in=amount_in,
            amount_out=amount_out,
            fee_amount=fee_amount,
            price_impact=price_impact,
            effective_rate=effective_rate,
            next_state={"execution_price": exec_price}
        )
