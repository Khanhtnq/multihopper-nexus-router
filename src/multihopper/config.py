"""
MultiHopper Protocol Configuration & Official Program Identifiers.
Sourced from official MultiHopper documentation and deployment specifications.
"""

from typing import Dict, Any, List
from dataclasses import dataclass


# Official On-Chain Program IDs
PROGRAM_IDS = {
    "MULTI_HOPPER_CORE": "3jLoS2wbNgtKzieUUxwg6Xhdv6gbZkHDtPWA9ZAgspFh",
    "ORCHESTRATOR": "4TPCmR2uN3hDM1FbTsf7ZtFXwXGSz4u1Kxv5YHj6eruX",
    "TRANSFER_HOOK_GUARD": "2JEv3pD6nczEvn1xDXaEzehkJofPPjoQQpnW5nGY3r52",
    "TOKEN_2022_PROGRAM": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "RAYDIUM_CLMM_PROGRAM": "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
    "ORCA_WHIRLPOOL_PROGRAM": "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
}

# Default integrator rewards wallet (provided by Superteam submitter)
DEFAULT_INTEGRATOR_WALLET = "6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf"

# Protocol Fee Parameters
PROTOCOL_FEES = {
    "PERCENT_FEE_BPS": 50,           # 0.50% total commercial fee
    "INTEGRATOR_SPLIT_BPS": 25,      # 0.25% instant integrator revenue share (50% of percent fee)
    "PROTOCOL_REVENUE_BPS": 25,      # 0.25% protocol share funding prize pool
    "SCREENING_FEE_SOL_PER_WALLET": 0.002,  # TRM Labs screening fee (2,000,000 lamports)
    "BASE_RENT_EXEMPT_LAMPORTS": 890880,    # getMinimumBalanceForRentExemption(0)
    "KEEPER_EXECUTION_FEE_SOL": 0.0005,     # per hop keeper gas funding
}

# Per-Hop Flat Fee Tiers (based on USD hop amount)
FEE_TIERS = [
    {"max_usd": 100.0, "flat_fee_route_sol": 0.0002, "flat_fee_hop_sol": 0.0001},
    {"max_usd": 1000.0, "flat_fee_route_sol": 0.0005, "flat_fee_hop_sol": 0.0002},
    {"max_usd": 10000.0, "flat_fee_route_sol": 0.0015, "flat_fee_hop_sol": 0.0005},
    {"max_usd": 100000.0, "flat_fee_route_sol": 0.0050, "flat_fee_hop_sol": 0.0010},
    {"max_usd": float('inf'), "flat_fee_route_sol": 0.0150, "flat_fee_hop_sol": 0.0025},
]

# Superteam Earn Prize Pool Milestones
SUPERTEAM_POOL_CONFIG = {
    "MIN_QUALIFYING_VOLUME_USD": 100000.0,      # $100k threshold to qualify
    "INITIAL_AWARD_MIN_AGGREGATE_USD": 2000000.0, # $2M aggregate triggers $5k guarantee
    "BASE_PRIZE_POOL_USD": 5000.0,
    "MAX_PRIZE_POOL_USD": 50000.0,
    "VOLUME_INCREMENT_PER_1K_USD": 400000.0,     # Every $400k unlocks another $1,000
    "MAX_POOL_VOLUME_USD": 20000000.0,           # $20M unlocks maximum $50,000 pool
}
