# MultiHopper Nexus Router

[![Solana](https://img.shields.io/badge/Solana-Mainnet--Beta-9945FF?style=flat&logo=solana)](https://solana.com)
[![MultiHopper](https://img.shields.io/badge/MultiHopper-Integrated-00F0FF?style=flat)](https://dev-docs.multihopper.com)
[![Tests](https://img.shields.io/badge/Tests-35%20Passed%20(0%20Mocks)-00FFA3?style=flat)](https://github.com/Khanhtnq/multihopper-nexus-router)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Flagship Solana Multi-Hop Smart Order Routing & Arbitrage Engine built for the Superteam Earn MultiHopper Build & Route Challenge ($5,000 - $50,000 USDC + Revenue Share).**

Live Dashboard: **[https://khanhtnq.github.io/multihopper-nexus-router/](https://khanhtnq.github.io/multihopper-nexus-router/)**  
Demo Video: **`demo_video.mp4`** (1080p H.264 60fps)

---

## 1. Executive Summary

**MultiHopper Nexus Router** solves the critical friction points in Solana DeFi execution and programmable capital management:
1. **DEX Liquidity Fragmentation & Toxic Slippage:** Large trades routed through a single DEX suffer catastrophic price impact. Nexus mathematically decomposes trades into optimal split paths across **Raydium AMM**, **Raydium CLMM**, **Orca Whirlpool**, **Meteora DLMM**, and **Phoenix Orderbook CFMM** using **Yen's K-Shortest Path** and **SLSQP Convex Split Optimization**.
2. **Post-Swap Privacy & Treasury Dispersion ("Swaps with Hooks"):** Standard swaps leave transparent, easily linkable footprints on-chain. Nexus automatically pipes swapped outputs into the **MultiHopper Protocol** (`3jLoS2wbNgtKzieUUxwg6Xhdv6gbZkHDtPWA9ZAgspFh`) for keeper-executed, scheduled multi-hop transfers or multi-destination payouts to up to 20 treasury wallets with built-in **TRM Labs** screening.
3. **Turnkey Business Model & Instant Integration Revenue:** Earns **0.25% instant on-chain revenue share ($2,500 per $1M volume routed)**, atomically deposited directly to the integrator wallet (`6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf`), while competing for the volume-scaled Superteam prize pool ($5,000 to $50,000 USDC).

---

## 2. System Architecture

```
                    ┌────────────────────────────────────────────────────────┐
                    │               User / Autonomous AI Agent               │
                    └──────────────────────────┬─────────────────────────────┘
                                               │
                                      Trade / Transfer Intent
                                               │
                                               ▼
                    ┌────────────────────────────────────────────────────────┐
                    │              MultiHopper Nexus Router API              │
                    └──────────┬─────────────────────────────┬───────────────┘
                               │                             │
                 ┌─────────────┴─────────────┐ ┌─────────────┴───────────────┐
                 │  Solana DEX Routing Engine│ │    MultiHopper Core SDK     │
                 │  - Yen's KSP Algorithm    │ │  - Vault Locking Mechanics  │
                 │  - Convex SLSQP Splitting │ │  - Token2022 Wrapper Mint   │
                 │  - Bellman-Ford Arbitrage │ │  - TRM Compliance Screening │
                 └─────────────┬─────────────┘ └─────────────┬───────────────┘
                               │                             │
         ┌─────────────────────┼──────────────────┐          │
         ▼                     ▼                  ▼          ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────┐   ┌─────────────────┐
│  Raydium CLMM   │   │ Orca Whirlpool  │   │ Meteora │   │ MultiHopper     │
│  (Tick Arrays)  │   │ (Concentrated L)│   │ (DLMM)  │   │ Core Protocol   │
└─────────────────┘   └─────────────────┘   └─────────┘   └────────┬────────┘
                                                                   │
                                                      Keeper Network & Orchestrator
                                                                   │
                                                      ┌────────────┴────────────┐
                                                      ▼                         ▼
                                              Private Hop 1..N          Multi-Destination
                                              Scheduled Hops            (Up to 20 Wallets)
```

### Verified MultiHopper On-Chain Deployments
- **MultiHopper Core Program ID:** `3jLoS2wbNgtKzieUUxwg6Xhdv6gbZkHDtPWA9ZAgspFh`
- **Orchestrator Program ID:** `4TPCmR2uN3hDM1FbTsf7ZtFXwXGSz4u1Kxv5YHj6eruX`
- **Transfer Hook Guard Program ID:** `2JEv3pD6nczEvn1xDXaEzehkJofPPjoQQpnW5nGY3r52`
- **Token2022 Program ID:** `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`

---

## 3. Mathematical Foundations

### 3.1. Graph Representation in Logarithmic Cost Space
Let $G = (V, E)$ be the Solana liquidity multigraph where vertices $V$ represent token mints and edges $E$ represent DEX liquidity pools. Each directed edge $e = (u, v)$ with spot exchange rate $R_e$ and fee $\phi_e$ is assigned logarithmic weight:

$$w_e = -\ln\left( R_e \cdot (1 - \phi_e) \right)$$

Finding the maximum compounding exchange rate path $\prod_{e \in P} R_e (1 - \phi_e)$ is mathematically equivalent to finding the shortest path minimizing $\sum_{e \in P} w_e$.

### 3.2. Yen's K-Shortest Path Algorithm
Computes top $K$ loopless candidate paths $P_1, P_2, \dots, P_K$ without cycles:
1. $P_1$ is computed using Dijkstra on the logarithmic edge weights.
2. For $i = 1$ to $K-1$, spur nodes and root paths are evaluated by systematically masking edges to identify loopless alternative candidate paths, stored in a min-heap priority queue.

### 3.3. SLSQP Convex Split Route Optimizer
Given total input amount $X$, candidate paths $P_1, \dots, P_M$, and non-linear output functions $\text{Out}_i(x)$ (concave due to liquidity depletion and slippage curves):

$$\max_{w_1, \dots, w_M} \sum_{i=1}^M \text{Out}_i(w_i \cdot X)$$

$$\text{subject to } \sum_{i=1}^M w_i = 1.0, \quad 0 \le w_i \le 1.0$$

Solved via Sequential Least Squares Programming (SLSQP).

### 3.4. Bellman-Ford Cyclic Arbitrage Detection
Identifies negative weight cycles in $G$:

$$\sum_{e \in C} -\ln\left( R_e \cdot (1 - \phi_e) \right) < 0 \iff \prod_{e \in C} R_e \cdot (1 - \phi_e) > 1.0$$

Optimal trade sizing $x^*$ is determined by maximizing net profit accounting for Solana base and priority compute gas costs:

$$\max_{x} \left[ \text{CycleSim}(x) - x - \text{GasCost}_{\text{SOL}} \right]$$

### 3.5. MultiHopper Fee Schedule & Revenue Formula
- **Total Commercial Percent Fee:** $0.50\%$ ($50$ bps) on full-rate transfers.
- **Integrator Revenue Share:** $50\%$ of percent fee = $0.25\%$ ($25$ bps) atomically disbursed to `6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf` in the same transaction.
- **Revenue Rate:** $\$2,500$ USD per $\$1,000,000$ volume routed.
- **Superteam Prize Pool Formula:**
  - Qualification threshold: $\ge \$100,000$ qualifying production volume.
  - Base pool: $\$5,000$ at $\$2,000,000$ aggregate volume.
  - Scaling: $+\$1,000$ per additional $\$400,000$ volume up to $\$50,000$ max pool at $\$20,000,000$ aggregate volume.
  - Winner Prize Share:
    $$\text{Prize} = \text{Funded Pool} \times \frac{\text{Your Volume}}{\sum \text{Top 3 Combined Volume}}$$

---

## 4. Test Suite & Verification

The test suite runs **35 comprehensive mathematical & integration tests with 0 mocks**:

```bash
pytest -v
```

### Test Breakdown
- `tests/test_constant_product_math.py`: Constant-product $x \cdot y = k$ invariant, spot price, monotonicity of slippage.
- `tests/test_concentrated_liquidity_math.py`: CLMM $L$ virtual liquidity, $\sqrt{P}$ tick transitions, price boundaries.
- `tests/test_dlmm_bin_math.py`: Meteora DLMM discrete bin crossing, volatility fee accumulation.
- `tests/test_orderbook_cfmm_math.py`: Phoenix/Lifinity oracle price anchoring, inventory skew decay.
- `tests/test_yen_k_shortest_path.py`: Yen's KSP multi-hop loopless routing and compounding.
- `tests/test_convex_split_optimizer.py`: Split order optimization proving $\sum \text{Out}_i(w_i X) \ge \text{SingleRouteOut}$.
- `tests/test_arbitrage_bellman_ford.py`: Negative-cycle detection, gas cost subtraction, optimal capital sizing.
- `tests/test_multihopper_fee_schedule.py`: 50 bps percent fee, flat fee tier boundaries, upfront SOL calculation.
- `tests/test_multihopper_revenue_share.py`: 0.25% revenue split, prize pool milestone curve, proportional distribution.
- `tests/test_multihopper_client_flow.py`: Full lifecycle (`estimate` $\to$ `create` $\to$ `prepare` $\to$ `confirm_broadcast`).
- `tests/test_multihopper_multi_destination.py`: Up to 20 recipient dispersion, mutual exclusivity validation.
- `tests/test_webhook_hmac_verification.py`: HMAC-SHA256 signature verification and anti-tampering.
- `tests/test_swaps_with_hooks_pipeline.py`: End-to-end DEX swap $\to$ MultiHopper Core execution $\to$ TRM screening $\to$ webhook receipt.
- `tests/test_prize_pool_calculator.py`: $\$100k$ threshold gating, $\$11M \to \$27k$ pool, $\$20M \to \$50k$ pool.
- `tests/test_solana_transaction_builder.py`: Compact-u16 encoding, PDA derivation, Solana wire message serialization.

---

## 5. Quickstart & Installation

```bash
# Clone the repository
git clone https://github.com/Khanhtnq/multihopper-nexus-router.git
cd multihopper-nexus-router

# Install Python dependencies
pip install -r requirements.txt

# Run all 35 tests
pytest

# Launch API server & Web Dashboard
python -m uvicorn src.server:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` or load `docs/index.html` in any browser.

---

## 6. Superteam Earn Submission Details

- **Challenge:** MultiHopper Build & Route Challenge | Up to $50,000 + Revenue Share
- **Listing URL:** `https://superteam.fun/earn/listing/multihopper-build-and-route-challenge-up-to-dollar50000-revenue-share-1`
- **Solana Wallet:** `6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf`
- **Repository:** `https://github.com/Khanhtnq/multihopper-nexus-router`
- **Live Demo Dashboard:** `https://khanhtnq.github.io/multihopper-nexus-router/`
- **Submission Spec File:** `SUPERTEAM_SUBMISSION_READY.json`
