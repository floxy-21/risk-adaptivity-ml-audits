"""Independent synthetic verification of optional interval-total recovery.

Run in the study's NumPy/SciPy environment:
    python outputs/study_interval_total_recovery.py

Every oracle optimizes the original linear objective with scipy.optimize
linprog(method='highs'), using independent total inequalities and fixed
query-answer bounds. Query subsets are exhaustively enumerated for at most
eight coordinates. This is numerical verification, not an empirical meter
study or a proof of operational savings.
"""
import hashlib
import itertools
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linprog

from interval_total_recovery import IntervalTotalBlock as Block, optimal_queries, worst_width
from study_recovery import Block as ExactBlock, optimal_queries as exact_queries, worst_width as exact_width


COUNTS = {"lp_calls": 0, "exhaustive_instances": 0, "exhaustive_query_subsets": 0,
          "conditional_answer_checks": 0, "exact_total_comparisons": 0,
          "invalid_input_checks": 0}
ERRORS = {"solver_vs_exhaustive_lp": 0.0, "subset_width_vs_lp": 0.0,
          "conditional_exceeds_zero_answer_width": 0.0, "conditional_formula_vs_lp": 0.0,
          "exact_total_reduction": 0.0}


def check_close(observed, expected, key):
    error = abs(observed - expected)
    ERRORS[key] = max(ERRORS[key], error)
    if error > 1e-8 * max(1.0, abs(expected)):
        raise AssertionError((key, observed, expected, error))


def lp_width(blocks, answers):
    ids = [i for block in blocks for i in block.indices]
    if not ids:
        return 0.0
    position = {i: j for j, i in enumerate(ids)}
    cs = np.zeros(len(ids))
    matrix, limits = [], []
    for block in blocks:
        row = np.zeros(len(ids))
        for i, c in zip(block.indices, block.coefficients):
            row[position[i]] = 1.0
            cs[position[i]] = c
        matrix.extend((row, -row))
        limits.extend((block.upper, -block.lower))
    bounds = [(answers[i], answers[i]) if i in answers else (0.0, None) for i in ids]
    low = linprog(cs, A_ub=matrix, b_ub=limits, bounds=bounds, method="highs")
    high = linprog(-cs, A_ub=matrix, b_ub=limits, bounds=bounds, method="highs")
    COUNTS["lp_calls"] += 2
    if not low.success or not high.success:
        raise AssertionError(("unexpected infeasible LP", low.message, high.message, answers))
    return -high.fun - low.fun


def zero_or_complete_answers(blocks, queries):
    answers = {i: 0.0 for i in queries}
    for block in blocks:
        if set(block.indices).issubset(answers):
            answers[block.indices[-1]] = block.lower
    return answers


def exhaustive_check(blocks, budget):
    ids = sorted(i for block in blocks for i in block.indices)
    assert len(ids) <= 8
    oracle = math.inf
    minimum_count = None
    for size in range(min(budget, len(ids)) + 1):
        for query in itertools.combinations(ids, size):
            width = lp_width(blocks, zero_or_complete_answers(blocks, query))
            COUNTS["exhaustive_query_subsets"] += 1
            check_close(worst_width(blocks, query), width, "subset_width_vs_lp")
            if width < oracle - 1e-9:
                oracle, minimum_count = width, size
    solution = optimal_queries(blocks, budget)
    assert solution.used_budget <= budget
    assert solution.used_budget == minimum_count
    check_close(solution.worst_case_width, oracle, "solver_vs_exhaustive_lp")
    check_close(worst_width(blocks, solution.queries), oracle, "solver_vs_exhaustive_lp")
    assert solution == optimal_queries(blocks, budget), "nondeterministic tie handling"
    COUNTS["exhaustive_instances"] += 1
    return {"budget": budget, "coordinates": len(ids), "queries": solution.queries,
            "solver_width": solution.worst_case_width, "exhaustive_lp_width": oracle}


def conditional_check(block):
    ids = block.indices
    for size in range(len(ids) + 1):
        for query in itertools.combinations(ids, size):
            retained = [c for i, c in zip(ids, block.coefficients) if i not in query]
            if not query:
                sums = [0.0]
            elif not retained:
                sums = sorted(set((block.lower, (block.lower + block.upper) / 2, block.upper)))
            else:
                sums = sorted(set((0.0, block.lower, block.upper / 4, block.upper / 2,
                                   3 * block.upper / 4, block.upper)))
            previous = math.inf
            maximum = worst_width((block,), query)
            for recovered_sum in sums:
                # Both concentrated and distributed answers; width must depend
                # on their sum only, although the objective offset can differ.
                distributions = ([{i: recovered_sum / len(query) for i in query},
                                  {i: recovered_sum if j == 0 else 0.0 for j, i in enumerate(query)}]
                                 if query else [{}])
                for answers in distributions:
                    observed = lp_width((block,), answers)
                    if retained:
                        lo, hi = max(0.0, block.lower - recovered_sum), block.upper - recovered_sum
                        small, large = min(retained), max(retained)
                        expected = max(lo * large, hi * large) - min(lo * small, hi * small)
                    else:
                        expected = 0.0
                    check_close(observed, expected, "conditional_formula_vs_lp")
                    excess = max(0.0, observed - maximum)
                    ERRORS["conditional_exceeds_zero_answer_width"] = max(ERRORS["conditional_exceeds_zero_answer_width"], excess)
                    assert excess < 1e-8
                    assert observed <= previous + 1e-8
                    previous = observed
                    COUNTS["conditional_answer_checks"] += 1


def expect_invalid(function):
    try:
        function()
    except ValueError:
        COUNTS["invalid_input_checks"] += 1
    else:
        raise AssertionError("invalid input was accepted")


def run():
    rng = np.random.default_rng(941820)
    named = [
        ("singleton_uncertain", (Block((0,), (2,), 1, 3),)),
        ("constant_positive", (Block((0, 1, 2), (2, 2, 2), 1, 3),)),
        ("constant_negative", (Block((0, 1), (-2, -2), 1, 3),)),
        ("mixed_sign", (Block((0, 1, 2), (-3, .5, 2), 1, 4),)),
        ("positive", (Block((0, 1, 2), (1, 2, 3), 1, 4),)),
        ("negative", (Block((0, 1, 2), (-3, -2, -1), 1, 4),)),
        ("zero_energy", (Block((0, 1), (-5, 7), 0, 0),)),
        ("zero_coefficients", (Block((0, 1), (0, 0), 1, 4),)),
        ("zero_lower", (Block((0, 1, 2), (-1, 0, 2), 0, 4),)),
        ("exact_total", (Block((0, 1, 2), (-1, 0, 2), 3, 3),)),
        ("two_blocks", (Block((0, 2), (-2, 1), 1, 3), Block((5, 8), (2, 2), 1, 2))),
    ]
    named_results = []
    for name, blocks in named:
        n = sum(len(block.indices) for block in blocks)
        for budget in sorted(set((0, 1, max(0, n - 1), n, n + 2))):
            named_results.append({"name": name, **exhaustive_check(blocks, budget)})
        if len(blocks) == 1:
            conditional_check(blocks[0])

    # Necessary boundary behavior: constant coefficients do not erase total
    # uncertainty, and the last record can require a query.
    assert optimal_queries(named[0][1], 0).worst_case_width == 4.0
    assert optimal_queries(named[0][1], 1).queries == (0,)
    assert optimal_queries(named[1][1], 2).used_budget == 0
    assert optimal_queries(named[1][1], 3).queries == (0, 1, 2)
    assert optimal_queries((), 10).worst_case_width == 0

    for case in range(36):
        n = int(rng.integers(1, 9))
        cuts = sorted(set([0, n] + rng.integers(1, n + 1, size=2).tolist()))
        blocks = []
        for start, end in zip(cuts, cuts[1:]):
            if start == end:
                continue
            cs = tuple(float(c) / 2 for c in rng.integers(-8, 9, size=end - start))
            lower = float(rng.integers(0, 9)) / 2
            upper = lower + float(rng.integers(0, 9)) / 4
            blocks.append(Block(tuple(range(start, end)), cs, lower, upper))
        exhaustive_check(tuple(blocks), int(rng.integers(0, n + 1)))
        exact_blocks = tuple(Block(b.indices, b.coefficients, b.upper, b.upper) for b in blocks)
        old_blocks = tuple(ExactBlock(b.indices, b.coefficients, b.upper) for b in blocks)
        for budget in (0, n // 2, n):
            old_q = exact_queries(old_blocks, budget)
            new = optimal_queries(exact_blocks, budget)
            check_close(new.worst_case_width, exact_width(old_blocks, old_q), "exact_total_reduction")
            COUNTS["exact_total_comparisons"] += 1

    bad_blocks = [
        lambda: Block((0,), (1,), -1, 2), lambda: Block((0,), (1,), 3, 2),
        lambda: Block((0,), (1,), float("nan"), 2), lambda: Block((0,), (1,), 0, float("inf")),
        lambda: Block((0,), (float("nan"),), 0, 1), lambda: Block((0,), (float("inf"),), 0, 1),
        lambda: Block((0, 0), (1, 2), 0, 1), lambda: Block((-1,), (1,), 0, 1),
        lambda: Block((0.5,), (1,), 0, 1), lambda: Block((True,), (1,), 0, 1),
        lambda: Block((), (), 0, 1), lambda: Block((0,), (), 0, 1),
        lambda: Block(None, (1,), 0, 1), lambda: Block((0,), (1,), False, 1),
    ]
    for function in bad_blocks:
        expect_invalid(function)
    good = Block((0, 1), (1, 2), 0, 2)
    for budget in (-1, 1.5, True, float("inf")):
        expect_invalid(lambda budget=budget: optimal_queries((good,), budget))
    for function in (
        lambda: optimal_queries((good, good), 1), lambda: optimal_queries(("bad",), 1),
        lambda: worst_width((good,), (0, 0)), lambda: worst_width((good,), (3,)),
        lambda: worst_width((good,), (True,)), lambda: worst_width((good,), (0.0,)),
        lambda: optimal_queries((Block((0,), (1e308,), 0, 3),), 0),
    ):
        expect_invalid(function)

    root = Path(__file__).resolve().parent
    report = {
        "scope": "Synthetic numerical verification of a separate interval-total batch solver; no operational-savings or dataset-performance claim",
        "completed_utc": datetime.now(timezone.utc).isoformat(), "all_passed": True,
        "seed": 941820, "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
        "solver": "scipy.optimize.linprog(method='highs') for independent extrema",
        "counts": COUNTS, "maximum_absolute_errors": ERRORS, "named_cases": named_results,
        "source_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ("interval_total_recovery.py", "study_interval_total_recovery.py", "study_recovery.py")},
    }
    target = root / "study_interval_total_recovery.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "named_cases"}, indent=2))
    print("RESULT_FILE", target)


if __name__ == "__main__":
    run()
