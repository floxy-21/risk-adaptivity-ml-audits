"""Independent LP checks of the classification examples; no forecast fitting.

The universal theorem is proved in theorem_proof.tex. This program checks its
constructed examples by separately minimizing and maximizing the affine target
over query fibers, then solves finite games used in the analytic lower bounds.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import platform
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
TOL = 2e-8
N_FIBERS = 0
MAX_ABS_ERROR = 0.0
MAX_PRIMAL_RESIDUAL = 0.0


def width(A, h, c, y, Q, expected):
    global N_FIBERS, MAX_ABS_ERROR, MAX_PRIMAL_RESIDUAL
    n = len(c)
    E = np.eye(n)[list(Q)] if Q else None
    rhs = np.asarray(y)[list(Q)] if Q else None
    lo = linprog(c, A_ub=A, b_ub=h, A_eq=E, b_eq=rhs,
                 bounds=[(None, None)] * n, method="highs")
    hi = linprog(-np.asarray(c), A_ub=A, b_ub=h, A_eq=E, b_eq=rhs,
                 bounds=[(None, None)] * n, method="highs")
    assert lo.success and hi.success, (lo.message, hi.message)
    for solution in (lo.x, hi.x):
        residual = max(0.0, float(np.max(A @ solution - h)))
        if Q:
            residual = max(residual, float(np.max(np.abs(E @ solution - rhs))))
        MAX_PRIMAL_RESIDUAL = max(MAX_PRIMAL_RESIDUAL, residual)
    value = float(-hi.fun - lo.fun)
    error = abs(value - float(expected))
    MAX_ABS_ERROR = max(MAX_ABS_ERROR, error)
    assert error <= TOL * max(1.0, abs(float(expected))), (value, expected)
    N_FIBERS += 1
    return value


def three_problem(l, h):
    d = h-l
    A = np.array([[-1, 0, 0], [1, 0, 0], [0, -1, 0],
                  [-d, 1, 0], [0, 0, -1], [d, 0, 1]], dtype=float)
    rhs = np.array([0, 1, 0, l, 0, h], dtype=float)
    return A, rhs, np.array([h, 1, 1], dtype=float)


def K_problem(K):
    n = 2*K-1
    rows = list(-np.eye(n))
    rhs = [0.0]*n
    row = np.zeros(n)
    row[:K-1] = 1
    rows.append(row)
    rhs.append(1.0)
    for j in range(K-1):
        row = np.zeros(n)
        row[j] = -1
        row[K-1+j] = 1
        rows.append(row)
        rhs.append(0.0)
    row = np.zeros(n)
    row[:K-1] = 1
    row[-1] = 1
    rows.append(row)
    rhs.append(1.0)
    return np.array(rows), np.array(rhs), np.ones(n)


def finite_game(payoffs):
    """Rows are batches, columns are adversarial records; minimize max risk."""
    payoffs = np.asarray(payoffs, dtype=float)
    m, r = payoffs.shape
    objective = np.r_[np.zeros(m), 1.0]
    inequalities = np.c_[payoffs.T, -np.ones(r)]
    equality = np.r_[np.ones(m), 0.0][None, :]
    result = linprog(objective, A_ub=inequalities, b_ub=np.zeros(r),
                     A_eq=equality, b_eq=[1.0],
                     bounds=[(0.0, None)]*m+[(None, None)], method="highs")
    assert result.success, result.message
    return float(result.fun)


def run():
    start = time.perf_counter()
    rng = np.random.default_rng(20261011)
    # General three-coordinate converse: independently check the two residual
    # capacities and the all-b/c-zero competitor across four scales/offsets.
    converse_rows = []
    for l, h in [(0.0, 1.0), (1.0, 3.0), (1.5, 3.5), (0.0, 0.01)]:
        A, rhs, c = three_problem(l, h)
        for a in np.linspace(0, 1, 9):
            cap_b, cap_c = l+(h-l)*a, h-(h-l)*a
            for b_fraction, c_fraction in itertools.product([0, .5, 1], repeat=2):
                y = np.array([a, cap_b*b_fraction, cap_c*c_fraction])
                width(A, rhs, c, y, (0, 1), cap_c)
                width(A, rhs, c, y, (0, 2), cap_b)
            width(A, rhs, c, [a, 0, 0], (1, 2), h)
        m = (l+h)/2
        converse_rows.append({"l": l, "h": h, "mean_optimum": m,
                              "adaptive_squared_risk": m*m,
                              "batch_squared_lower_bound": (l*l+h*h)/2,
                              "adaptive_precision_failure_at_midpoint": 0,
                              "batch_precision_failure_lower_bound": .5})

    # Exact rational identities and independent endpoint LPs for the K family.
    K_rows = []
    for K in range(2, 9):
        A, rhs, c = K_problem(K)
        n = len(c)
        batches = [tuple(i for i in range(n) if i != omit) for omit in range(n)]
        vertex_payoffs = []
        precision_payoffs = []
        for omit, Q in enumerate(batches):
            vertex_row, precision_row = [], []
            for j in range(K):
                av = [Fraction(int(i == j)) for i in range(K)]
                yv = [*av[:-1], *([Fraction(0)]*K)]
                exact_v = av[omit]+av[-1] if omit < K-1 else av[omit-(K-1)]
                v = width(A, rhs, c, [float(x) for x in yv], Q, exact_v)
                vertex_row.append(v)

                ap = [Fraction(1, 2*K) if i == j else
                      Fraction(2*K-1, 2*K*(K-1)) for i in range(K)]
                assert sum(ap) == 1
                yp = [*ap[:-1], *([Fraction(0)]*K)]
                exact_p = ap[omit]+ap[-1] if omit < K-1 else ap[omit-(K-1)]
                p = width(A, rhs, c, [float(x) for x in yp], Q, exact_p)
                expected_success = omit == K-1+j
                assert (exact_p <= Fraction(1, K)) == expected_success
                assert (p <= 1/K) == expected_success
                precision_row.append(float(not expected_success))
            vertex_payoffs.append(vertex_row)
            precision_payoffs.append(precision_row)

        games = {}
        for power in (1, 2, 4):
            value = finite_game(np.asarray(vertex_payoffs)**power)
            assert abs(value-1/K) < TOL
            games[f"batch_moment_{power}_lower_game"] = value
        failure = finite_game(precision_payoffs)
        assert abs(failure-(1-1/K)) < TOL
        games["batch_precision_success_upper_game"] = 1-failure

        # Directly evaluate the adaptive rule on rational feasible records,
        # including the exact hard record (all capacities equal, b=0).
        records = [([Fraction(1, K)]*K, [Fraction(0)]*K)]
        for _ in range(24):
            masses = rng.integers(1, 20, size=K).tolist()
            total = sum(masses)
            a = [Fraction(v, total) for v in masses]
            b = [a_j*Fraction(int(rng.integers(0, 11)), 10) for a_j in a]
            records.append((a, b))
        max_adaptive = 0.0
        for a, b in records:
            j = min(range(K), key=lambda j: (a[j], j))
            Q = tuple(i for i in range(n) if i != K-1+j)
            y = [*a[:-1], *b]
            v = width(A, rhs, c, [float(x) for x in y], Q, a[j])
            max_adaptive = max(max_adaptive, v)
            assert a[j] <= Fraction(1, K)
        assert abs(max_adaptive-1/K) < TOL
        K_rows.append({"K": K, "coordinates": n, "hard_budget": n-1,
                       "batches_enumerated": n, **games,
                       "adaptive_max_width_on_25_checked_records": max_adaptive,
                       "analytic_adaptive_squared_risk": 1/K**2,
                       "analytic_adaptive_fourth_moment_risk": 1/K**4,
                       "analytic_adaptive_precision_success": 1.0})

    result = {"status": "passed", "scope": "Constructed mathematical examples; not empirical forecasting improvements or a numerical proof of the universal theorem.",
              "fiber_endpoint_pairs_checked": N_FIBERS,
              "endpoint_LPs_solved": 2*N_FIBERS,
              "absolute_tolerance": TOL,
              "comparison_rule": "absolute error <= tolerance * max(1, abs(analytic width))",
              "maximum_absolute_width_discrepancy": MAX_ABS_ERROR,
              "maximum_endpoint_primal_constraint_residual": MAX_PRIMAL_RESIDUAL,
              "K_family": K_rows, "three_coordinate_converse": converse_rows,
              "finite_games_solved": len(K_rows)*4,
              "elapsed_seconds": time.perf_counter()-start,
              "python": platform.python_version(), "numpy": np.__version__,
              "scipy": scipy.__version__, "solver": "scipy.optimize.linprog(method='highs')",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE / "classification_verification.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("K_family", "three_coordinate_converse")}, indent=2))


if __name__ == "__main__":
    run()
