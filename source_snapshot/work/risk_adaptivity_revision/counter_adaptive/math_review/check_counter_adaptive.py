"""Independent formula, finite-game and LP checks for exact prefix queries.

This checker imports no production counter-study code. Fractions determine the
constructed example's envelope and threshold matrix exactly; HiGHS provides
independent fiber/conditional LP checks and finite-game solutions.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import platform
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
TOL = 2e-8


def span(c, lo, hi):
    z = c[lo:hi]
    return max(z) - min(z)


def conditional_coefficients(c, k, j):
    """g(t) = alpha*t + beta*(E-t); cuts use 1-based prefix lengths."""
    n = len(c)
    if j < k:
        return max(span(c, 0, j), span(c, j, k)), span(c, k, n)
    return span(c, 0, k), max(span(c, k, j), span(c, j, n))


def exact_envelope(c, k, E=F(1)):
    lines = {j: conditional_coefficients(c, k, j)
             for j in range(1, len(c)) if j != k}
    candidates = {F(0), E}
    for (a, b), (aa, bb) in itertools.combinations(lines.values(), 2):
        if (a-b) != (aa-bb):
            t = E*(bb-b)/((a-b)-(aa-bb))
            if 0 <= t <= E:
                candidates.add(t)
    evaluated = [(min(a*t+b*(E-t) for a, b in lines.values()), t)
                 for t in candidates]
    value, witness = max(evaluated)
    return value, witness, lines


def width(c, y, Q):
    cuts = (0,) + tuple(Q) + (len(c),)
    return sum(sum(y[a:b])*span(c, a, b)
               for a, b in zip(cuts[:-1], cuts[1:]))


def fiber_lp(c, y, Q):
    n = len(c)
    M = np.array([[float(i < k) for i in range(n)] for k in (*Q, n)])
    rhs = M @ np.asarray(y, dtype=float)
    c = np.asarray(c, dtype=float)
    lo = linprog(c, A_eq=M, b_eq=rhs, bounds=(0, None), method="highs")
    hi = linprog(-c, A_eq=M, b_eq=rhs, bounds=(0, None), method="highs")
    assert lo.success and hi.success
    return -hi.fun-lo.fun


def conditional_lp(c, k, j, t, E):
    n = len(c)
    # Two feasible endpoint records, same first answer, same second answer.
    M = []
    rhs = []
    for offset in (0, n):
        z = np.zeros(2*n); z[offset:offset+n] = 1
        M.append(z); rhs.append(float(E))
        z = np.zeros(2*n); z[offset:offset+k] = 1
        M.append(z); rhs.append(float(t))
    z = np.zeros(2*n); z[:j] = 1; z[n:n+j] = -1
    M.append(z); rhs.append(0)
    obj = np.r_[-np.asarray(c, dtype=float), np.asarray(c, dtype=float)]
    result = linprog(obj, A_eq=M, b_eq=rhs,
                     bounds=(0, None), method="highs")
    assert result.success
    residual = max(0.0, float(np.max(np.abs(np.asarray(M)@result.x-rhs))),
                   float(-np.min(result.x)))
    return -result.fun, residual


def finite_game(success):
    S = np.asarray(success, dtype=float)
    ns, nq = S.shape
    primal = linprog(np.r_[np.zeros(nq), -1],
                     A_ub=np.c_[-S, np.ones(ns)], b_ub=np.zeros(ns),
                     A_eq=[np.r_[np.ones(nq), 0]], b_eq=[1],
                     bounds=[(0, None)]*nq+[(0, 1)], method="highs")
    dual = linprog(np.r_[np.zeros(ns), 1],
                   A_ub=np.c_[S.T, -np.ones(nq)], b_ub=np.zeros(nq),
                   A_eq=[np.r_[np.ones(ns), 0]], b_eq=[1],
                   bounds=[(0, None)]*ns+[(0, 1)], method="highs")
    assert primal.success and dual.success
    weights = np.maximum(dual.x[:-1], 0)
    weights /= weights.sum()
    # Feasible normalized adverse distribution gives an upper bound even if
    # solver objective is not trusted. Exact reconstruction below is separate.
    upper = float(np.max(weights @ S))
    return primal, dual, weights, upper


def main():
    start = time.perf_counter()
    c = list(map(F, (0, 0, 1, 1, 0, 1)))
    batches = list(itertools.combinations(range(1, 6), 2))
    env = {k: exact_envelope(c, k) for k in range(1, 6)}
    A = min(v[0] for v in env.values())
    assert A == F(1, 2)
    concentration = [[F(i == j) for i in range(6)] for j in range(6)]
    widths = [[width(c, y, Q) for Q in batches] for y in concentration]
    S = [[int(w <= F(1, 2)) for w in row] for row in widths]
    primal, dual, weights, upper = finite_game(S)
    assert abs(upper-.5) <= 1e-12
    rational_weights = [F(float(x)).limit_denominator(1000000) for x in weights]
    assert min(rational_weights) >= 0 and sum(rational_weights) == 1
    exact_upper = max(sum(w*S[i][q] for i, w in enumerate(rational_weights))
                      for q in range(len(batches)))
    assert exact_upper == F(1, 2)
    # Analytic all-record lower bound is tested on a dense rational simplex grid.
    rational_pi = [F(float(x)).limit_denominator(1000000) for x in primal.x[:-1]]
    assert min(rational_pi) >= 0 and sum(rational_pi) == 1
    grid_success = F(1)
    grid_records = 0
    for bars in itertools.combinations(range(13), 5):
        z = (-1,) + bars + (13,)
        y = [F(z[i+1]-z[i]-1, 8) for i in range(6)]
        assert sum(y) == 1
        val = sum(p for p, Q in zip(rational_pi, batches)
                  if width(c, y, Q) <= F(1, 2))
        grid_success = min(grid_success, val)
        grid_records += 1
    assert grid_success == F(1, 2)

    rng = np.random.default_rng(20261012)
    all_c = [c] + [[F(int(x), 7) for x in rng.integers(-9, 10, 6)]
                   for _ in range(7)]
    max_error = max_residual = 0.0
    conditional_count = fiber_count = 0
    for cc in all_c:
        for k in range(1, 6):
            for j in range(1, 6):
                if j == k:
                    continue
                a, b = conditional_coefficients(cc, k, j)
                for t in map(lambda x: F(x, 4), range(5)):
                    actual, residual = conditional_lp(cc, k, j, t, F(1))
                    expected = float(a*t+b*(1-t))
                    max_error = max(max_error, abs(actual-expected))
                    max_residual = max(max_residual, residual)
                    assert abs(actual-expected) <= TOL*max(1, abs(expected))
                    conditional_count += 1
        for raw in [rng.integers(0, 10, 6) for _ in range(4)]:
            y = [F(int(x), int(sum(raw))) for x in raw]
            for Q in batches:
                actual = fiber_lp(cc, y, Q)
                expected = float(width(cc, y, Q))
                max_error = max(max_error, abs(actual-expected))
                assert abs(actual-expected) <= TOL*max(1, abs(expected))
                fiber_count += 1
    report = {
        "status": "PASS",
        "scope": "Independent constructed prefix-query formula and game checks; no empirical study rerun",
        "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
        "coefficients": list(map(str, c)), "E": "1", "budget": 2,
        "tau": "1/2", "batches": batches,
        "exact_adaptive_value": str(A),
        "first_cut_values": {str(k): {"value": str(v[0]), "hard_answer": str(v[1]),
                                         "conditional_lines": {str(j): list(map(str, ab)) for j, ab in v[2].items()}}
                             for k, v in env.items()},
        "concentration_success_matrix": S,
        "finite_game_primal": float(-primal.fun), "finite_game_dual": float(dual.fun),
        "normalized_dual_upper_bound": upper, "exact_rational_upper_bound": str(exact_upper),
        "rational_adverse_weights": list(map(str, rational_weights)),
        "batch_distribution": {str(Q): str(p) for p, Q in zip(rational_pi, batches) if p},
        "rational_simplex_grid_records": grid_records, "grid_minimum_success": str(grid_success),
        "grid_scope": "Grid supports debugging only; analytic proof establishes continuum lower bound",
        "conditional_lps": conditional_count, "fiber_lps": 2*fiber_count,
        "max_absolute_width_discrepancy": max_error,
        "max_conditional_primal_residual": max_residual,
        "comparison_tolerance": TOL,
        "runtime_seconds": time.perf_counter()-start,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (HERE/"verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
