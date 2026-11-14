"""
Convex Split Route Optimizer for Solana Multi-Hop Order Routing.
Solves:
    maximize:   Sum_{i=1}^M Out_i(w_i * X)
    subject to: Sum_{i=1}^M w_i = 1.0,  0 <= w_i <= 1.0

Where Out_i(x) represents the simulated non-linear output of route i for trade volume x.
Leverages SLSQP (Sequential Least Squares Programming) and marginal return gradient waterfilling.
"""

import numpy as np
from scipy.optimize import minimize
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from src.routing.yen_ksp import RoutePath, RouteHop


@dataclass
class SplitAllocation:
    route: RoutePath
    weight: float
    amount_in: float
    amount_out: float
    price_impact: float
    effective_rate: float


@dataclass
class OptimizedRoutingResult:
    token_in: str
    token_out: str
    total_amount_in: float
    total_amount_out: float
    blended_rate: float
    blended_price_impact: float
    allocations: List[SplitAllocation]
    single_route_out: float
    gain_over_single_route: float
    gain_percent: float


class ConvexSplitOptimizer:
    """
    Optimizes split order routing across multiple parallel and multi-hop DEX paths.
    """
    def __init__(self, routes: List[RoutePath]):
        self.routes = routes

    def optimize_split(self, total_amount_in: float) -> OptimizedRoutingResult:
        if not self.routes:
            raise ValueError("No routes provided to optimizer.")

        M = len(self.routes)
        token_in = self.routes[0].hops[0].token_in
        token_out = self.routes[0].hops[-1].token_out

        if total_amount_in <= 0:
            allocs = [
                SplitAllocation(r, 1.0 / M, 0.0, 0.0, 0.0, r.spot_rate)
                for r in self.routes
            ]
            return OptimizedRoutingResult(
                token_in=token_in,
                token_out=token_out,
                total_amount_in=0.0,
                total_amount_out=0.0,
                blended_rate=self.routes[0].spot_rate,
                blended_price_impact=0.0,
                allocations=allocs,
                single_route_out=0.0,
                gain_over_single_route=0.0,
                gain_percent=0.0
            )

        # Baseline: Best single route output
        best_single_out = 0.0
        best_single_idx = 0
        for i, r in enumerate(self.routes):
            out_i, _, _ = r.simulate_execution(total_amount_in)
            if out_i > best_single_out:
                best_single_out = out_i
                best_single_idx = i

        if M == 1:
            out, impact, _ = self.routes[0].simulate_execution(total_amount_in)
            alloc = SplitAllocation(
                route=self.routes[0],
                weight=1.0,
                amount_in=total_amount_in,
                amount_out=out,
                price_impact=impact,
                effective_rate=out / total_amount_in
            )
            return OptimizedRoutingResult(
                token_in=token_in,
                token_out=token_out,
                total_amount_in=total_amount_in,
                total_amount_out=out,
                blended_rate=out / total_amount_in,
                blended_price_impact=impact,
                allocations=[alloc],
                single_route_out=best_single_out,
                gain_over_single_route=0.0,
                gain_percent=0.0
            )

        # Objective function: minimize negative total output
        def objective(weights: np.ndarray) -> float:
            total_out = 0.0
            for idx, w in enumerate(weights):
                if w > 1e-6:
                    alloc_in = float(w * total_amount_in)
                    out_i, _, _ = self.routes[idx].simulate_execution(alloc_in)
                    total_out += out_i
            return -total_out

        # Initial guess: proportional to spot rate
        rates = np.array([r.spot_rate for r in self.routes], dtype=float)
        init_weights = rates / np.sum(rates)

        bounds = [(0.0, 1.0) for _ in range(M)]
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]

        res = minimize(
            objective,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-9, 'maxiter': 100}
        )

        final_weights = res.x if res.success else init_weights
        final_weights = np.maximum(0.0, final_weights)
        if np.sum(final_weights) > 0:
            final_weights = final_weights / np.sum(final_weights)
        else:
            final_weights = np.zeros(M)
            final_weights[best_single_idx] = 1.0

        # Build allocations
        allocations: List[SplitAllocation] = []
        total_out = 0.0
        weighted_impact = 0.0

        for idx, r in enumerate(self.routes):
            w = float(final_weights[idx])
            if w > 0.0001:
                alloc_in = w * total_amount_in
                out_i, impact_i, _ = r.simulate_execution(alloc_in)
                eff_rate = out_i / alloc_in if alloc_in > 0 else r.spot_rate
                allocations.append(SplitAllocation(
                    route=r,
                    weight=w,
                    amount_in=alloc_in,
                    amount_out=out_i,
                    price_impact=impact_i,
                    effective_rate=eff_rate
                ))
                total_out += out_i
                weighted_impact += impact_i * w

        # Guard against numerical solver degradation
        if total_out < best_single_out:
            # Fallback to best single route
            best_route = self.routes[best_single_idx]
            out, impact, _ = best_route.simulate_execution(total_amount_in)
            allocations = [
                SplitAllocation(
                    route=best_route,
                    weight=1.0,
                    amount_in=total_amount_in,
                    amount_out=out,
                    price_impact=impact,
                    effective_rate=out / total_amount_in
                )
            ]
            total_out = out
            weighted_impact = impact

        gain = max(0.0, total_out - best_single_out)
        gain_pct = (gain / best_single_out * 100.0) if best_single_out > 0 else 0.0

        return OptimizedRoutingResult(
            token_in=token_in,
            token_out=token_out,
            total_amount_in=total_amount_in,
            total_amount_out=total_out,
            blended_rate=total_out / total_amount_in if total_amount_in > 0 else 0.0,
            blended_price_impact=weighted_impact,
            allocations=allocations,
            single_route_out=best_single_out,
            gain_over_single_route=gain,
            gain_percent=gain_pct
        )
