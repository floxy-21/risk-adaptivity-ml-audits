#!/usr/bin/env python3
"""Independent exact/LP verifier for the constructed two-target boundary family.

Run with the standard library only:
    python verify_boundary.py --solver-free --output exact_report.json
Run the additional SciPy/HiGHS checks:
    python verify_boundary.py --output numeric_report.json

Every coordinate has cost one; a batch contains at most two coordinates.
Exact adverse-record endpoints come from enumerating vertices of the three-
coordinate (t,u,v) polytope with Fraction arithmetic, plus exact cube extrema.
The LP implementation instead optimizes all m+3 coordinates directly. Whole-
interval LPs use two endpoint vectors with equality of their queried answers;
they maximize their target difference without sampling the first answer.
This is a mathematical construction, not an empirical application study.
"""

from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction as F
from functools import lru_cache
import hashlib
from itertools import combinations
import json
from pathlib import Path
import time


BASE_INEQUALITIES = (
    ((-1, 0, 0), 0), ((1, 0, 0), 1),
    ((0, -1, 0), 0), ((-1, 1, 0), 0),
    ((0, 0, -1), 0), ((1, 0, 1), 1),
)


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), F(0))


def solve_square(rows, rhs):
    """Exact Gaussian elimination; return None for singular active sets."""
    n = len(rhs)
    aug = [[F(v) for v in row] + [F(r)] for row, r in zip(rows, rhs)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if aug[r][col]), None)
        if pivot is None:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [v / scale for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col]:
                factor = aug[r][col]
                aug[r] = [x - factor * y for x, y in zip(aug[r], aug[col])]
    return tuple(row[-1] for row in aug)


@lru_cache(maxsize=None)
def base_vertices(observations):
    """Enumerate every feasible vertex after base-coordinate observations."""
    equalities = []
    for k, value in observations:
        row = tuple(int(j == k) for j in range(3))
        equalities.append((row, value))
    constraints = list(BASE_INEQUALITIES) + equalities
    vertices = set()
    for active in combinations(constraints, 3):
        x = solve_square([a for a, _ in active], [b for _, b in active])
        if x is None:
            continue
        if any(dot(a, x) > b for a, b in BASE_INEQUALITIES):
            continue
        if any(dot(a, x) != b for a, b in equalities):
            continue
        vertices.add(x)
    if not vertices:
        raise AssertionError(f"No vertices for feasible observations {observations}")
    return tuple(sorted(vertices))


def family(m):
    assert m >= 3
    h = F(m * (2 * m + 3), 4)
    big_m = h - m
    a = tuple(F(j) + F(1, 4) for j in range(1, m + 1))
    b = tuple(F(m + 1 - j) + F(1, 4) for j in range(1, m + 1))
    d = tuple(x - y for x, y in zip(a, b))
    p = F(m * m // 4)
    assert sum(a) == sum(b) == h
    assert sum(x for x in d if x > 0) == p
    assert sum(x for x in d if x < 0) == -p
    return {
        "m": m, "H": h, "M": big_m, "a": a, "b": b, "d": d, "P": p,
        "names": ("t", "u", "v") + tuple(f"z{j}" for j in range(1, m + 1)),
        "coefficients": ((big_m, F(m), F(0)) + a,
                         (-big_m, F(0), F(m)) + b,
                         (2 * big_m, F(m), F(-m)) + d),
        "constants": (F(0), big_m, -big_m),
        "initial_widths": (2 * h, 2 * h, 2 * (h + p)),
    }


def exact_endpoints(fam, target, query, record):
    coefficients = fam["coefficients"][target]
    observations = tuple((k, record[k]) for k in query if k < 3)
    values = [dot(coefficients[:3], v) + fam["constants"][target]
              for v in base_vertices(observations)]
    low, high = min(values), max(values)
    for k in range(3, len(coefficients)):
        c = coefficients[k]
        if k in query:
            low += c * record[k]
            high += c * record[k]
        else:
            low += min(F(0), c)
            high += max(F(0), c)
    return low, high


def all_queries(n):
    return tuple(q for size in range(3) for q in combinations(range(n), size))


def is_success(widths, initial, tau, targets=3):
    return all(w <= tau * total for w, total in zip(widths[:targets], initial[:targets]))


def branch_widths(fam, j, s):
    h, m, p = fam["H"], fam["m"], fam["P"]
    return (h - fam["a"][j - 1] + m * s,
            h - fam["b"][j - 1] + m * (1 - s),
            F(m) + 2 * p - abs(fam["d"][j - 1]))


def coverage_certificate(fam, tau, support):
    """Exact closed-interval sweep, also checking every breakpoint itself."""
    h, m = fam["H"], fam["m"]
    intervals = []
    for j in support:
        low = max(F(0), (m + h - fam["b"][j - 1] - 2 * h * tau) / m)
        high = min(F(1), (2 * h * tau - h + fam["a"][j - 1]) / m)
        assert low <= high
        assert branch_widths(fam, j, low)[2] <= fam["initial_widths"][2] * tau
        intervals.append((j, low, high))
    breaks = sorted({F(0), F(1)} | {x for _, low, high in intervals for x in (low, high)})
    points = sorted(set(breaks + [(a + b) / 2 for a, b in zip(breaks, breaks[1:])]))
    multiplicities = [(s, sum(low <= s <= high for _, low, high in intervals)) for s in points]
    minimum = min(count for _, count in multiplicities)
    assert minimum >= 1
    return {"intervals": intervals, "minimum_coverage_multiplicity": minimum,
            "number_of_breakpoints_and_midpoints_checked": len(points),
            "uniform_success_lower_bound": F(minimum, len(support))}


class LpVerifier:
    def __init__(self, tolerance=1e-7):
        import scipy
        from scipy.optimize import linprog
        self.linprog = linprog
        self.scipy_version = scipy.__version__
        self.tolerance = tolerance
        self.counts = Counter()
        self.max_endpoint_discrepancy = 0.0
        self.max_width_discrepancy = 0.0
        self.max_endpoint_case = None
        self.max_width_case = None

    def solve(self, objective, a_ub, b_ub, bounds, category, a_eq=None, b_eq=None):
        self.counts[category] += 1
        result = self.linprog(objective, A_ub=a_ub, b_ub=b_ub,
                              A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs",
                              options={"primal_feasibility_tolerance": 1e-9,
                                       "dual_feasibility_tolerance": 1e-9})
        if not result.success:
            raise AssertionError(f"LP failed ({category}): {result.message}")
        return result.fun

    @staticmethod
    def inequalities(n, offset=0, dimension=None):
        dimension = dimension or n
        row1 = [0.0] * dimension
        row2 = [0.0] * dimension
        row1[offset], row1[offset + 1] = -1.0, 1.0
        row2[offset], row2[offset + 2] = 1.0, 1.0
        return [row1, row2], [0.0, 1.0]

    def endpoints(self, fam, target, query, record, category):
        c = list(map(float, fam["coefficients"][target]))
        bounds = [(0.0, 1.0)] * len(c)
        for k in query:
            bounds[k] = (float(record[k]), float(record[k]))
        aub, bub = self.inequalities(len(c))
        offset = float(fam["constants"][target])
        low = self.solve(c, aub, bub, bounds, category) + offset
        high = -self.solve([-v for v in c], aub, bub, bounds, category) + offset
        return low, high

    def check_endpoints(self, fam, target, query, record, exact, category):
        actual = self.endpoints(fam, target, query, record, category)
        label = {"m": fam["m"], "target": target + 1,
                 "query": [fam["names"][k] for k in query], "record_t": record[0]}
        discrepancy = max(abs(x - float(y)) for x, y in zip(actual, exact))
        if discrepancy > self.max_endpoint_discrepancy:
            self.max_endpoint_discrepancy, self.max_endpoint_case = discrepancy, label
        assert discrepancy <= self.tolerance, (label, actual, exact)
        self.check_width(actual[1] - actual[0], exact[1] - exact[0], label)

    def check_width(self, actual, exact, label):
        discrepancy = abs(actual - float(exact))
        if discrepancy > self.max_width_discrepancy:
            self.max_width_discrepancy, self.max_width_case = discrepancy, label
        assert discrepancy <= self.tolerance, (label, actual, exact)

    def whole_fiber_width(self, fam, target, query, interval, category, expected):
        """Maximize target(x+)−target(x−) with identical queried answers."""
        coefficients = list(map(float, fam["coefficients"][target]))
        n = len(coefficients)
        aub1, bub1 = self.inequalities(n, 0, 2 * n)
        aub2, bub2 = self.inequalities(n, n, 2 * n)
        bounds = [(0.0, 1.0)] * (2 * n)
        bounds[0] = bounds[n] = tuple(map(float, interval))
        aeq = []
        for k in query:
            row = [0.0] * (2 * n)
            row[k], row[n + k] = 1.0, -1.0
            aeq.append(row)
        objective = [-v for v in coefficients] + coefficients
        width = -self.solve(objective, aub1 + aub2, bub1 + bub2, bounds, category,
                            aeq or None, [0.0] * len(aeq) if aeq else None)
        label = {"m": fam["m"], "target": target + 1,
                 "query": [fam["names"][k] for k in query], "interval": interval,
                 "category": category}
        self.check_width(width, expected, label)
        return width


def verify_family(m, solver):
    fam = family(m)
    h, p = fam["H"], fam["P"]
    initial = fam["initial_widths"]
    tau_lower, tau_upper = F(1, 2) - 1 / (8 * h), F(1, 2) + 1 / (8 * h)
    queries = all_queries(m + 3)
    counts = Counter()
    lp_before = Counter(solver.counts) if solver else Counter()
    origin = (F(0),) * (m + 3)
    initial_endpoints = []
    for target in range(3):
        endpoints = exact_endpoints(fam, target, (), origin)
        counts["exact_endpoint_pairs"] += 1
        assert endpoints[1] - endpoints[0] == initial[target]
        expected = (F(0), 2 * h) if target < 2 else (-h - p, h + p)
        assert endpoints == expected
        initial_endpoints.append(endpoints)
        if solver:
            solver.check_endpoints(fam, target, (), origin, endpoints, "initial_endpoint_LPs")

    incidence_half = []
    incidence_upper = []
    minimum_non_designated_ratio = None
    smallest_non_designated_case = None
    maximum_designated_ratio = F(0)
    success_counts = Counter()
    for i in range(1, m + 1):
        record = (F(2 * i - 1, 2 * m),) + (F(0),) * (m + 2)
        row_half, row_upper = [], []
        for query in queries:
            counts["adverse_record_query_pairs"] += 1
            widths = []
            for target in range(3):
                endpoints = exact_endpoints(fam, target, query, record)
                counts["exact_endpoint_pairs"] += 1
                widths.append(endpoints[1] - endpoints[0])
                if solver:
                    solver.check_endpoints(fam, target, query, record, endpoints,
                                           "adverse_fiber_endpoint_LPs")
            success2 = is_success(widths, initial, F(1, 2), 2)
            success3 = is_success(widths, initial, F(1, 2), 3)
            expected_success = query == (0, i + 2)
            assert success2 == success3 == expected_success, (m, i, query, widths)
            success_counts[f"size_{len(query)}_two_target"] += int(success2)
            success_counts[f"size_{len(query)}_three_target"] += int(success3)
            if expected_success:
                assert is_success(widths, initial, tau_lower)
                maximum_designated_ratio = max(maximum_designated_ratio,
                                               max(w / total for w, total in zip(widths, initial)))
            else:
                ratio = max(widths[k] / initial[k] for k in range(2))
                assert ratio >= tau_upper, (m, i, query, widths, ratio, tau_upper)
                if minimum_non_designated_ratio is None or ratio < minimum_non_designated_ratio:
                    minimum_non_designated_ratio = ratio
                    smallest_non_designated_case = {
                        "adverse_record": i, "query": [fam["names"][k] for k in query],
                        "widths": widths, "max_first_two_normalized_widths": ratio}
            if len(query) == 2 and query[0] == 0 and query[1] >= 3:
                j = query[1] - 2
                assert tuple(widths) == branch_widths(fam, j, record[0])
                counts["adverse_t_z_formula_checks"] += 3
                row_half.append(int(success3))
                row_upper.append(int(is_success(widths, initial, tau_upper)))
        incidence_half.append(row_half)
        incidence_upper.append(row_upper)
    assert incidence_half == [[int(i == j) for j in range(m)] for i in range(m)]
    assert incidence_upper == [[int(abs(i - j) <= 1) for j in range(m)] for i in range(m)]

    branch_maxima = []
    for j in range(1, m + 1):
        interval = (F(j - 1, m), F(j, m))
        query = (0, j + 2)
        endpoint_widths = []
        for s in interval:
            record = (s,) + (F(0),) * (m + 2)
            widths = []
            for target in range(3):
                endpoints = exact_endpoints(fam, target, query, record)
                counts["exact_endpoint_pairs"] += 1
                widths.append(endpoints[1] - endpoints[0])
            assert tuple(widths) == branch_widths(fam, j, s)
            counts["branch_endpoint_formula_checks"] += 3
            endpoint_widths.append(widths)
        maxima = tuple(max(row[k] for row in endpoint_widths) for k in range(3))
        assert maxima[:2] == (h - F(1, 4), h - F(1, 4))
        assert is_success(maxima, initial, tau_lower)
        if solver:
            for target in range(3):
                solver.whole_fiber_width(fam, target, query, interval,
                                        "whole_branch_width_LPs", maxima[target])
        branch_maxima.append({"j": j, "interval": interval, "width_maxima": maxima})

    # All checks below range over the whole first-answer interval, not a grid.
    # Every queried z coordinate cancels in a fiber difference; observed u or v
    # cancels as well, so these widths do not depend on those observed values.
    fixed_checks = [
        ("scalar_half_T1_t_u", 0, (0, 1), h, F(1, 2)),
        ("scalar_half_T2_t_v", 1, (0, 2), h, F(1, 2)),
        ("third_target_t_only", 2, (0,), F(m) + 2 * p, tau_lower),
        ("scalar_band_T1_t_zm", 0, (0, m + 2), h - F(1, 4), tau_lower),
        ("scalar_band_T2_t_z1", 1, (0, 3), h - F(1, 4), tau_lower),
    ]
    for target in range(3):
        fixed_checks.append((f"three_fixed_t_u_v_T{target + 1}", target, (0, 1, 2),
                             h if target < 2 else 2 * p, F(1, 2)))
        fixed_checks.append((f"three_fixed_t_z1_zm_T{target + 1}", target, (0, 3, m + 2),
                             h - F(3, 2) if target < 2 else F(m) + 2 * p - 2 * (m - 1),
                             tau_lower))
    fixed_reports = []
    for label, target, query, expected_width, threshold in fixed_checks:
        exact_widths = []
        for s in (F(0), F(1, 2), F(1)):
            record = (s,) + (F(0),) * (m + 2)
            endpoints = exact_endpoints(fam, target, query, record)
            counts["exact_endpoint_pairs"] += 1
            exact_widths.append(endpoints[1] - endpoints[0])
        assert max(exact_widths) == expected_width, (label, exact_widths, expected_width)
        assert expected_width <= initial[target] * threshold
        if solver:
            solver.whole_fiber_width(fam, target, query, (F(0), F(1)),
                                    "whole_interval_fixed_query_width_LPs", expected_width)
        fixed_reports.append({"name": label, "target": target + 1,
                              "query": [fam["names"][k] for k in query],
                              "worst_width": expected_width,
                              "normalized_worst_width": expected_width / initial[target],
                              "threshold_checked": threshold})

    # A simple all-m rational certificate: P <= m^2/4, H-m-P >= m(m-1)/4
    # >= 3/2, whereas the band-lower-endpoint correction (H+P)/(4H) <= 1/2.
    assert p <= F(m * m, 4)
    assert h - m - p >= F(m * (m - 1), 4) >= F(3, 2)
    assert p <= h
    assert (h + p) / (4 * h) <= F(1, 2)
    assert F(m) + 2 * p <= initial[2] * tau_lower
    continuum = coverage_certificate(fam, tau_lower, tuple(range(1, m + 1)))
    assert continuum["uniform_success_lower_bound"] == F(1, m)
    endpoint_support = tuple(sorted(set(range(1, m + 1, 2)) | {m}))
    endpoint_coverage = coverage_certificate(fam, tau_upper, endpoint_support)
    assert endpoint_coverage["uniform_success_lower_bound"] > F(1, m)
    assert len(endpoint_support) == m // 2 + 1
    assert counts["adverse_record_query_pairs"] == m * len(queries)

    return {
        "m": m, "dimension": m + 3, "H": h, "M": fam["M"], "P": p,
        "a": fam["a"], "b": fam["b"], "d": fam["d"],
        "initial_endpoints": initial_endpoints, "initial_widths": initial,
        "legal_query_sets_by_size": dict(Counter(map(len, queries))),
        "legal_query_sets_total": len(queries), "adverse_record_count": m,
        "actual_exact_check_counts": dict(counts),
        "actual_LP_counts": dict(solver.counts - lp_before) if solver else {},
        "adverse_success_counts_at_half": dict(success_counts),
        "adverse_t_z_success_incidence_at_half": incidence_half,
        "adverse_t_z_success_incidence_at_upper_endpoint": incidence_upper,
        "minimum_non_designated_max_first_two_normalized_widths": minimum_non_designated_ratio,
        "minimum_non_designated_case": smallest_non_designated_case,
        "maximum_designated_max_three_normalized_widths": maximum_designated_ratio,
        "threshold_band": {"lower_inclusive": tau_lower, "upper_exclusive": tau_upper},
        "adaptive_branch_maxima": branch_maxima,
        "fixed_query_whole_interval_checks": fixed_reports,
        "uniform_batch_continuum_lower_bound_at_band_lower_endpoint": continuum,
        "upper_endpoint_counterexample": {
            "support_j": endpoint_support, "uniform_mixture": True,
            "coverage": endpoint_coverage, "strictly_beats_one_over_m": True},
        "certified_optimal_values_throughout_threshold_band": {
            "adaptive_success": F(1), "randomized_nonadaptive_success": F(1, m)},
        "passed": True,
    }


def rational_json(obj):
    if isinstance(obj, F):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): rational_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [rational_json(v) for v in obj]
    return obj


def proof_input_parameters(sizes):
    """Explicit mathematical input, canonically hashed independently of output."""
    return rational_json({
        "certificate_schema": "two-target-boundary-v1",
        "family_sizes": sizes,
        "base_inequalities_A_x_le_b": BASE_INEQUALITIES,
        "all_coordinate_bounds": [0, 1],
        "coordinate_query_cost": 1,
        "batch_budget": 2,
        "families": [
            {"m": m, "coefficients": family(m)["coefficients"],
             "constants": family(m)["constants"],
             "adverse_records": [(F(2 * i - 1, 2 * m),) + (F(0),) * (m + 2)
                                 for i in range(1, m + 1)],
             "adaptive_branch_intervals": [(F(j - 1, m), F(j, m))
                                           for j in range(1, m + 1)],
             "threshold_band_lower_inclusive": F(1, 2) - 1 / (8 * family(m)["H"]),
             "threshold_band_upper_exclusive": F(1, 2) + 1 / (8 * family(m)["H"])}
            for m in sizes],
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True, help="JSON report output path")
    parser.add_argument("--solver-free", action="store_true", help="Use Fraction certificates only")
    parser.add_argument("--m", type=int, nargs="+", default=[3, 5, 10], help="Family sizes (default: 3 5 10)")
    args = parser.parse_args()
    if any(m < 3 for m in args.m):
        parser.error("Every m must be at least 3")
    started = time.perf_counter()
    solver = None if args.solver_free else LpVerifier()
    families = []
    for m in args.m:
        families.append(verify_family(m, solver))
        print(f"m={m}: exact certificates passed" + ("; LP checks passed" if solver else ""), flush=True)
    proof_inputs = proof_input_parameters(args.m)
    input_bytes = json.dumps(proof_inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report = {
        "status": "PASS",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "proof_input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "proof_input_hash_encoding": "UTF-8 JSON, sort_keys=True, separators=(',', ':'), exact rational strings",
        "proof_input_parameters": proof_inputs,
        "description": "Independent verification of a constructed adaptive versus batch family",
        "mode": "solver-free exact rational" if args.solver_free else "exact rational plus SciPy/HiGHS",
        "family_sizes": args.m, "fraction_encoding": "exact numerator/denominator strings",
        "all_checks_passed": True, "elapsed_seconds": time.perf_counter() - started,
        "rational_base_vertex_cache": base_vertices.cache_info()._asdict(),
        "families": families,
        "scope": "No empirical application data or manuscript claims are validated by this verifier.",
    }
    if solver:
        report["numerical_verification"] = {
            "solver": "scipy.optimize.linprog(method='highs')",
            "scipy_version": solver.scipy_version,
            "LP_counts_by_category": dict(solver.counts),
            "actual_total_LPs": sum(solver.counts.values()),
            "absolute_comparison_tolerance": solver.tolerance,
            "primal_feasibility_tolerance": 1e-9,
            "dual_feasibility_tolerance": 1e-9,
            "maximum_endpoint_discrepancy": solver.max_endpoint_discrepancy,
            "maximum_endpoint_discrepancy_case": solver.max_endpoint_case,
            "maximum_width_discrepancy": solver.max_width_discrepancy,
            "maximum_width_discrepancy_case": solver.max_width_case,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rational_json(report), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output.resolve()}", flush=True)
    if solver:
        print(f"Actual LP count: {sum(solver.counts.values())}; "
              f"maximum endpoint discrepancy: {solver.max_endpoint_discrepancy:.3g}; "
              f"maximum width discrepancy: {solver.max_width_discrepancy:.3g}", flush=True)


if __name__ == "__main__":
    main()
