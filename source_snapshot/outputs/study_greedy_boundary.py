"""Adversarial boundary checks for the implemented greedy recovery baseline.

Run: python outputs/study_greedy_boundary.py

These constructed instances check an algorithmic limitation; they are not
additional empirical forecasting results. The oracle enumerates all query
subsets and evaluates paired squared losses at feasible simplex vertices.
"""
import itertools
import hashlib
import json
import math
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from study_recovery import Block, baseline_queries, optimal_queries, worst_width


def squared_loss_interval(coefficients, queries, energy=3.0):
    """Independent bounds after feasible zero answers, via original MSEs.

    With total energy E, the remaining feasible simplex has E-scaled unit-vector
    vertices. Forecasts A=0, B=N*c/2 are nonnegative for these instances and
    realize c=2*(B-A)/N. Evaluating loss differences at all vertices avoids
    reusing the implementation's coefficient-range formula.
    """
    n = len(coefficients)
    a = [0.0] * n
    b = [n * c / 2.0 for c in coefficients]
    values = []
    for remaining in set(range(n)) - set(queries):
        y = [energy * float(i == remaining) for i in range(n)]
        values.append(math.fsum((ai - yi) ** 2 - (bi - yi) ** 2
                                for ai, bi, yi in zip(a, b, y)) / n)
    if not values:
        raise ValueError("zero answers cannot exhaust a positive-energy block")
    return min(values), max(values)


def squared_loss_width(coefficients, queries, energy=3.0):
    lower, upper = squared_loss_interval(coefficients, queries, energy)
    return upper - lower


def exhaustive_oracle(coefficients, budget):
    return min((squared_loss_width(coefficients, queries), len(queries), queries)
               for count in range(budget + 1)
               for queries in itertools.combinations(range(len(coefficients)), count))


def case_record(epsilon):
    cs = (0.0, epsilon / 2.0, epsilon, 1.0, 1.0)
    blocks = (Block(tuple(range(5)), cs, 3.0),)
    greedy = baseline_queries(blocks, 2, "greedy_width_reduction")
    exact = optimal_queries(blocks, 2)
    initial = worst_width(blocks, ())
    gw, ow = worst_width(blocks, greedy), worst_width(blocks, exact)
    return {
        "epsilon": epsilon,
        "coefficients": cs,
        "budget": 2,
        "energy": 3.0,
        "forecast_a": [0.0] * 5,
        "forecast_b": [2.5 * c for c in cs],
        "initial_direct_loss_interval": squared_loss_interval(cs, ()),
        "greedy_queries_zero_based": greedy,
        "exact_queries_zero_based": exact,
        "initial_width": initial,
        "greedy_width": gw,
        "exact_width": ow,
        "direct_loss_greedy_width": squared_loss_width(cs, greedy),
        "direct_loss_exact_width": squared_loss_width(cs, exact),
        "greedy_to_optimal_reduction_ratio": (initial - gw) / (initial - ow),
        "greedy_to_optimal_residual_ratio": gw / ow if ow > 0 else None,
        "residual_ratio_note": "undefined when optimal width is zero" if ow == 0 else "positive optimum",
    }


class GreedyBoundaryTests(unittest.TestCase):
    def test_exact_zero_reduction_counterexample_and_realizable_forecasts(self):
        result = case_record(0.0)
        self.assertEqual(result["greedy_queries_zero_based"], (0, 1))
        self.assertEqual(result["exact_queries_zero_based"], (3, 4))
        self.assertEqual(result["greedy_width"], 3.0)
        self.assertEqual(result["exact_width"], 0.0)
        self.assertEqual(result["greedy_to_optimal_reduction_ratio"], 0.0)
        self.assertEqual(result["direct_loss_greedy_width"], 3.0)
        self.assertEqual(result["direct_loss_exact_width"], 0.0)
        self.assertEqual(exhaustive_oracle(result["coefficients"], 2), (0.0, 2, (3, 4)))

    def test_tie_free_family_with_positive_optimum(self):
        for epsilon in (0.4, 0.1, 0.01, 0.001, 2.0 ** -16):
            with self.subTest(epsilon=epsilon):
                result = case_record(epsilon)
                self.assertEqual(result["greedy_queries_zero_based"], (0, 1))
                self.assertEqual(result["exact_queries_zero_based"], (3, 4))
                self.assertEqual(result["greedy_width"], 3.0 * (1.0 - epsilon))
                self.assertEqual(result["exact_width"], 3.0 * epsilon)
                self.assertAlmostEqual(result["direct_loss_greedy_width"], 3.0 * (1.0 - epsilon), places=13)
                self.assertAlmostEqual(result["direct_loss_exact_width"], 3.0 * epsilon, places=13)
                oracle = exhaustive_oracle(result["coefficients"], 2)
                self.assertAlmostEqual(oracle[0], 3.0 * epsilon, places=13)
                self.assertEqual(oracle[2], (3, 4))
                self.assertAlmostEqual(result["greedy_to_optimal_residual_ratio"], (1.0 - epsilon) / epsilon, places=10)
                lower, upper = result["initial_direct_loss_interval"]
                constant = -2.5 - 1.5625 * epsilon ** 2
                self.assertAlmostEqual(lower, constant, places=13)
                self.assertAlmostEqual(upper, constant + 3.0, places=13)
                self.assertLess(lower, 0.0)
                self.assertGreater(upper, 0.0)

    def test_each_greedy_choice_is_unique_for_positive_epsilon(self):
        cs = (0.0, 1.0 / 16.0, 1.0 / 8.0, 1.0, 1.0)
        for chosen, next_choice in (((), 0), ((0,), 1)):
            costs = {i: squared_loss_width(cs, chosen + (i,))
                     for i in range(5) if i not in chosen}
            self.assertTrue(all(costs[next_choice] < value
                                for i, value in costs.items() if i != next_choice))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GreedyBoundaryTests)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    if not outcome.wasSuccessful():
        sys.exit(1)
    root = Path(__file__).resolve().parent
    report = {
        "scope": "constructed algorithmic boundary, not dataset performance or a certification advantage claim",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "tests_run": outcome.testsRun,
        "all_passed": outcome.wasSuccessful(),
        "independent_oracle": "All 16 query subsets of size at most two; direct paired MSE at feasible simplex vertices after zero query answers",
        "source_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ("study_greedy_boundary.py", "study_recovery.py")},
        "bruteforce_checked": {
            "instances": 6,
            "epsilon_values": [0.0, 0.4, 0.1, 0.01, 0.001, 2.0 ** -16],
            "query_subsets_per_instance": 16,
            "query_subsets_total": 96,
            "simplex_vertices_per_instance": 55,
            "simplex_vertices_total": 330,
        },
        "cases": [case_record(e) for e in (0.0, 0.4, 0.1, 0.01, 0.001)],
    }
    target = root / "study_greedy_boundary.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("RESULT_FILE", str(target))
