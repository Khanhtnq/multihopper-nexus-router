"""
DEX Liquidity MultiGraph and Solana Token registry.
"""

import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from src.dex.amm_pool import (
    BasePool,
    ConstantProductPool,
    ConcentratedLiquidityPool,
    DynamicBinPool,
    OrderbookCFMMPool
)


@dataclass
class TokenInfo:
    symbol: str
    mint: str
    decimals: int
    name: str


# Real Solana Token Mints
SOLANA_TOKENS: Dict[str, TokenInfo] = {
    "SOL": TokenInfo("SOL", "So11111111111111111111111111111111111111112", 9, "Solana Native"),
    "USDC": TokenInfo("USDC", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 6, "USD Coin"),
    "USDT": TokenInfo("USDT", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", 6, "Tether USD"),
    "BONK": TokenInfo("BONK", "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", 5, "Bonk"),
    "JUP": TokenInfo("JUP", "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", 6, "Jupiter"),
    "RAY": TokenInfo("RAY", "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", 6, "Raydium"),
    "ORCA": TokenInfo("ORCA", "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE", 6, "Orca"),
    "WIF": TokenInfo("WIF", "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", 6, "dogwifhat"),
}


@dataclass
class Edge:
    pool: BasePool
    token_in: str
    token_out: str

    @property
    def spot_rate(self) -> float:
        return self.pool.get_spot_price(self.token_in)

    @property
    def log_weight(self) -> float:
        rate = self.spot_rate
        if rate <= 0:
            return float('inf')
        return -math.log(rate)


class DexGraph:
    """
    Multigraph of Solana liquidity pools connecting token mints.
    Allows multiple parallel pools (Raydium, Orca, Meteora) between identical token pairs.
    """
    def __init__(self):
        self.nodes: Dict[str, TokenInfo] = {}
        self.adjacency: Dict[str, List[Edge]] = {}
        self.pools: Dict[str, BasePool] = {}

    def add_token(self, token: TokenInfo):
        self.nodes[token.symbol] = token
        if token.symbol not in self.adjacency:
            self.adjacency[token.symbol] = []

    def add_pool(self, pool: BasePool):
        self.pools[pool.pool_id] = pool
        if pool.token_a not in self.adjacency:
            self.adjacency[pool.token_a] = []
        if pool.token_b not in self.adjacency:
            self.adjacency[pool.token_b] = []

        # Directed edges both ways
        self.adjacency[pool.token_a].append(Edge(pool, pool.token_a, pool.token_b))
        self.adjacency[pool.token_b].append(Edge(pool, pool.token_b, pool.token_a))

    def get_edges(self, token: str) -> List[Edge]:
        return self.adjacency.get(token, [])

    @classmethod
    def create_default_solana_market(cls) -> "DexGraph":
        """
        Creates a realistic Solana ecosystem graph with authentic pools across:
        Raydium, Orca, Meteora, Phoenix, Lifinity.
        """
        g = cls()
        for t in SOLANA_TOKENS.values():
            g.add_token(t)

        # 1. SOL/USDC Pools (High Liquidity)
        # Raydium CLMM SOL/USDC: ~$150.0 / SOL
        g.add_pool(ConcentratedLiquidityPool(
            pool_id="ray_clmm_sol_usdc",
            dex_name="Raydium CLMM",
            token_a="SOL", token_b="USDC",
            liquidity=450000.0, current_price=150.0,
            price_lower=120.0, price_upper=190.0, fee_bps=5.0
        ))
        # Orca Whirlpool SOL/USDC: ~$150.15 / SOL
        g.add_pool(ConcentratedLiquidityPool(
            pool_id="orca_whirl_sol_usdc",
            dex_name="Orca Whirlpool",
            token_a="SOL", token_b="USDC",
            liquidity=520000.0, current_price=150.15,
            price_lower=115.0, price_upper=195.0, fee_bps=4.0
        ))
        # Meteora DLMM SOL/USDC: ~$150.10 / SOL
        g.add_pool(DynamicBinPool(
            pool_id="meteora_dlmm_sol_usdc",
            dex_name="Meteora DLMM",
            token_a="SOL", token_b="USDC",
            active_bin_price=150.10, bin_step_bps=10.0,
            bin_liquidity_depth=80.0, base_fee_bps=6.0, volatility_fee_bps=2.0
        ))
        # Phoenix Orderbook CFMM SOL/USDC: ~$150.05 / SOL
        g.add_pool(OrderbookCFMMPool(
            pool_id="phoenix_sol_usdc",
            dex_name="Phoenix",
            token_a="SOL", token_b="USDC",
            oracle_price=150.05, pool_capacity=300000.0, fee_bps=2.0
        ))

        # 2. SOL/USDT Pools
        g.add_pool(ConstantProductPool(
            pool_id="ray_amm_sol_usdt",
            dex_name="Raydium AMM",
            token_a="SOL", token_b="USDT",
            reserve_a=20000.0, reserve_b=3000000.0, fee_bps=25.0
        ))
        g.add_pool(DynamicBinPool(
            pool_id="meteora_dlmm_sol_usdt",
            dex_name="Meteora DLMM",
            token_a="SOL", token_b="USDT",
            active_bin_price=150.02, bin_step_bps=12.0,
            bin_liquidity_depth=50000.0, base_fee_bps=8.0, volatility_fee_bps=3.0
        ))

        # 3. USDC/USDT Stable Peg Pool
        g.add_pool(ConcentratedLiquidityPool(
            pool_id="orca_whirl_usdc_usdt",
            dex_name="Orca Whirlpool",
            token_a="USDC", token_b="USDT",
            liquidity=2500000.0, current_price=1.0002,
            price_lower=0.995, price_upper=1.005, fee_bps=1.0
        ))

        # 4. SOL/BONK Pools: 1 SOL = ~6,000,000 BONK (BONK = ~$0.000025)
        g.add_pool(ConstantProductPool(
            pool_id="ray_amm_sol_bonk",
            dex_name="Raydium AMM",
            token_a="SOL", token_b="BONK",
            reserve_a=15000.0, reserve_b=90000000000.0, fee_bps=25.0
        ))
        g.add_pool(ConcentratedLiquidityPool(
            pool_id="orca_whirl_sol_bonk",
            dex_name="Orca Whirlpool",
            token_a="SOL", token_b="BONK",
            liquidity=120000000.0, current_price=6000000.0,
            price_lower=4500000.0, price_upper=7500000.0, fee_bps=8.0
        ))

        # 5. USDC/BONK Pools: 1 USDC = ~40,000 BONK
        g.add_pool(DynamicBinPool(
            pool_id="meteora_dlmm_usdc_bonk",
            dex_name="Meteora DLMM",
            token_a="USDC", token_b="BONK",
            active_bin_price=40000.0, bin_step_bps=20.0,
            bin_liquidity_depth=40000.0, base_fee_bps=10.0, volatility_fee_bps=5.0
        ))

        # 6. SOL/JUP Pools: 1 SOL = ~150 JUP (JUP = ~$1.00)
        g.add_pool(ConcentratedLiquidityPool(
            pool_id="meteora_dlmm_sol_jup",
            dex_name="Meteora DLMM",
            token_a="SOL", token_b="JUP",
            liquidity=850000.0, current_price=150.0,
            price_lower=110.0, price_upper=200.0, fee_bps=6.0
        ))
        g.add_pool(ConstantProductPool(
            pool_id="ray_amm_sol_jup",
            dex_name="Raydium AMM",
            token_a="SOL", token_b="JUP",
            reserve_a=10000.0, reserve_b=1500000.0, fee_bps=25.0
        ))

        # 7. USDC/JUP Pools: 1 JUP = ~1.00 USDC
        g.add_pool(OrderbookCFMMPool(
            pool_id="phoenix_jup_usdc",
            dex_name="Phoenix",
            token_a="JUP", token_b="USDC",
            oracle_price=1.00, pool_capacity=200000.0, fee_bps=3.0
        ))

        # 8. SOL/WIF Pools: 1 SOL = ~50 WIF (WIF = ~$3.00)
        g.add_pool(ConcentratedLiquidityPool(
            pool_id="ray_clmm_sol_wif",
            dex_name="Raydium CLMM",
            token_a="SOL", token_b="WIF",
            liquidity=320000.0, current_price=50.0,
            price_lower=35.0, price_upper=75.0, fee_bps=8.0
        ))
        g.add_pool(ConstantProductPool(
            pool_id="ray_amm_sol_wif",
            dex_name="Raydium AMM",
            token_a="SOL", token_b="WIF",
            reserve_a=8000.0, reserve_b=400000.0, fee_bps=25.0
        ))

        return g
