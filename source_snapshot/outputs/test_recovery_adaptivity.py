"""Independent exact integer-grid check of the deterministic adaptivity result.

Run with Python 3.10+; no external packages. The adaptive oracle permits every
unqueried coordinate, including the last coordinate of a block, and stopping
before the hard budget. Answers are every feasible nonnegative integer value.
The independent fixed-batch oracle enumerates query sets and complete worlds.
These finite checks supplement, and do not replace, the continuous proof.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import platform
import random
import time
from functools import lru_cache
from fractions import Fraction
from pathlib import Path


def width(blocks, energies):
    return sum(e * (max(c) - min(c)) if c else 0
               for c, e in zip(blocks, energies))


def adaptive_oracle(blocks, energies, budget):
    """Min over deterministic adaptive decisions, max over feasible answers."""
    @lru_cache(None)
    def solve(cs, es, b):
        best = width(cs, es)  # Stopping is allowed.
        if b == 0:
            return best
        for g, coeffs in enumerate(cs):
            for j in range(len(coeffs)):
                remaining = coeffs[:j] + coeffs[j + 1:]
                next_cs = cs[:g] + (remaining,) + cs[g + 1:]
                # A final coordinate is determined, not freely answerable zero.
                answers = range(es[g] + 1) if remaining else (es[g],)
                worst = 0
                for answer in answers:
                    next_es = es[:g] + (es[g] - answer,) + es[g + 1:]
                    worst = max(worst, solve(next_cs, next_es, b - 1))
                best = min(best, worst)
        return best
    return solve(blocks, energies, budget), solve.cache_info().currsize


def compositions(total, length):
    if length == 0:
        return [()] if total == 0 else []
    if length == 1:
        return [(total,)]
    return [(v,) + tail for v in range(total + 1)
            for tail in compositions(total - v, length - 1)]


def fixed_batch_oracle(blocks, energies, budget):
    """Enumerate batches and worlds without using the zero-answer formula."""
    coordinates = [(g, j) for g, c in enumerate(blocks)
                   for j in range(len(c))]
    worlds = list(itertools.product(*(compositions(e, len(c))
                  for c, e in zip(blocks, energies))))
    best = width(blocks, energies)
    for k in range(min(budget, len(coordinates)) + 1):
        for requested in itertools.combinations(coordinates, k):
            requested = set(requested)
            worst = 0
            for world in worlds:
                updated = 0
                for g, c in enumerate(blocks):
                    kept = [j for j in range(len(c)) if (g, j) not in requested]
                    if kept:
                        residual = sum(world[g][j] for j in kept)
                        updated += residual * (max(c[j] for j in kept)
                                              - min(c[j] for j in kept))
                worst = max(worst, updated)
            best = min(best, worst)
    return best


def sorted_window_dp(blocks, energies, budget):
    """Independent implementation of the proposed finite allocation formula."""
    dp = [0] * (budget + 1)  # At-most, rather than exact, resource budget.
    for c, e in zip(blocks, energies):
        c = tuple(sorted(c))
        if not c:
            continue
        costs = []
        for k in range(min(budget, len(c) - 1) + 1):
            remaining = len(c) - k
            costs.append(e * min(c[s + remaining - 1] - c[s]
                                 for s in range(k + 1)))
        dp = [min(dp[b - k] + costs[k]
                  for k in range(min(b, len(costs) - 1) + 1))
              for b in range(budget + 1)]
    return dp[budget]


def run():
    start = time.perf_counter()
    cases = []
    # Exhaust all 3^4 ordered coefficient vectors, all residual E in {0,1,2},
    # and budgets 0 through 5: includes enough budget to query every coordinate.
    for c in itertools.product((-2, 0, 3), repeat=4):
        for e in (0, 1, 2):
            for b in range(6):
                cases.append(((c,), (e,), b, "single_exhaustive"))
    # Exhaust two blocks, including zero-energy blocks, ties and both signs.
    for c in itertools.product((-1, 0, 2), repeat=4):
        for es in itertools.product((0, 1, 2), repeat=2):
            for b in range(6):
                cases.append(((c[:2], c[2:]), es, b, "two_block_exhaustive"))
    # Unequal block sizes and singleton blocks, selected before outcomes.
    rng = random.Random(21094)
    for _ in range(120):
        sizes = rng.choice(((1, 3), (2, 3), (3, 3), (1, 1, 3)))
        cs = tuple(tuple(rng.randint(-4, 4) for _ in range(m)) for m in sizes)
        es = tuple(rng.randrange(4) for _ in sizes)
        b = rng.randrange(sum(sizes) + 2)
        cases.append((cs, es, b, "random_extended"))
    states = 0
    groups = {}
    discrepancies = []
    for cs, es, b, group in cases:
        av, nstates = adaptive_oracle(cs, es, b)
        bv = fixed_batch_oracle(cs, es, b)
        dv = sorted_window_dp(cs, es, b)
        states += nstates
        groups[group] = groups.get(group, 0) + 1
        if av != bv or bv != dv:
            discrepancies.append({"blocks": cs, "energies": es, "budget": b,
                                  "adaptive": av, "batch": bv, "window_dp": dv})
    # Randomized expected-minimax is a different criterion. This exact boundary
    # example refutes extending the deterministic equality to that criterion.
    # c=(0,1,2,3), query first two or last two equiprobably, B=2.
    random_example_worlds = 0
    for e in (1, 2):
        deterministic, _ = adaptive_oracle(((0, 1, 2, 3),), (e,), 2)
        assert deterministic == e
        for y in compositions(e, 4):
            expected_width = Fraction(sum(y[:2]) + sum(y[2:]), 2)
            assert expected_width == Fraction(e, 2)
            random_example_worlds += 1
    report = {
        "status": "passed" if not discrepancies else "failed",
        "claim": "Deterministic adaptive minimax width equals fixed-batch optimum",
        "scope": "Integer-grid independent finite checks; not a proof of the continuous theorem",
        "seed": 21094,
        "cases": len(cases),
        "case_groups": groups,
        "adaptive_bellman_states": states,
        "integer_comparison_max_absolute_error": max(
            (max(abs(x["adaptive"] - x["batch"]),
                 abs(x["batch"] - x["window_dp"])) for x in discrepancies), default=0),
        "failures": discrepancies,
        "edge_cases": ["zero total", "constant contrast", "negative contrasts",
                       "repeated coefficients", "singleton blocks", "last-coordinate queries",
                       "early stopping", "budget exceeds number of useful queries"],
        "randomized_expected_minimax_claim_tested": False,
        "randomized_counterexample": {
            "coefficients": [0, 1, 2, 3], "budget": 2,
            "equal_mixture_batches": [[0, 1], [2, 3]],
            "deterministic_minimax_width": "E",
            "randomized_expected_width_for_every_world": "E/2",
            "integer_worlds_checked": random_example_worlds,
            "meaning": "Do not extend the deterministic corollary to expected randomized width"
        },
        "python": platform.python_version(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "elapsed_seconds": round(time.perf_counter() - start, 3),
    }
    destination = Path(__file__).with_suffix(".json")
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if discrepancies:
        raise AssertionError("Adaptive/fixed/formula discrepancy")


if __name__ == "__main__":
    run()
