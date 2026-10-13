"""Independent LP/QP checks of the experimental bound implementations.

Run from project root: python outputs/study_independent_audit.py
This does not rerun the empirical study or modify its results.
"""
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "outputs"))
import numpy as np
import scipy
from scipy.optimize import linprog, minimize
from run_energy_rank_study import bounds, individual_extrema, P0, P1
from energy_rank_bounds import EnergyBlock, bound_pairwise_mse


def main():
    rng = np.random.default_rng(21093)
    max_lp_error = max_projection_error = max_vertex_error = 0.0
    max_generic_lp_error = 0.0
    for case in range(150):
        truth = rng.uniform(0, 10, 24)
        pred = rng.normal(3, 4, (4, 24))
        mask = np.zeros(24, dtype=bool)
        mask[rng.choice(24, int(rng.integers(1, 24)), replace=False)] = True
        bs = int(rng.choice([6, 24]))
        tau = float(rng.choice([0, 0.01, 0.05]))
        visible = truth.copy()
        visible[mask] = np.nan
        totals = truth.reshape(-1, bs).sum(axis=1)
        low, high, _, _ = bounds(pred, visible, totals, bs, tau)
        missing, observed = np.flatnonzero(mask), ~mask
        matrix, rhs, energy_blocks = [], [], []
        for start in range(0, 24, bs):
            idx = np.arange(start, start + bs)
            miss = idx[mask[idx]]
            if not len(miss):
                continue
            E, total = truth[miss].sum(), truth[idx].sum()
            L, U = max(0, E - tau * total), E + tau * total
            energy_blocks.append(EnergyBlock(miss.tolist(),float(L),float(U)))
            a = np.isin(missing, miss).astype(float)
            matrix.extend([a, -a])
            rhs.extend([U, -L])
        for pair, (a, b) in enumerate(zip(P0, P1)):
            reference = bound_pairwise_mse(pred[a],pred[b],
                [None if mask[i] else float(truth[i]) for i in range(24)],energy_blocks)
            c = 2 * (pred[b] - pred[a]) / 24
            k = (np.sum(pred[a] ** 2 - pred[b] ** 2)
                 + np.sum(24 * c[observed] * truth[observed])) / 24
            for direction, expected, reference_value in [(1, low[pair],reference.lower), (-1, high[pair],reference.upper)]:
                res = linprog(direction * c[missing], A_ub=matrix, b_ub=rhs,
                              bounds=(0, None), method="highs")
                assert res.success, res.message
                error = abs(k + direction * res.fun - expected)
                max_lp_error = max(max_lp_error, error)
                assert error < 1e-7, (case, pair, error)
                reference_error = abs(k + direction * res.fun - reference_value)
                max_generic_lp_error = max(max_generic_lp_error,reference_error)
                assert reference_error < 1e-7, (case,pair,reference_error)

        m = int(rng.integers(1, 13))
        p = rng.normal(3, 4, (4, m))
        L = float(rng.uniform(0, 20))
        U = L + float(rng.uniform(0, 10))
        low, high = individual_extrema(p, L, U)
        vertices = [np.eye(m)[i] * E for E in [L, U] for i in range(m)]
        for j in range(4):
            expected = max(np.sum((p[j] - v) ** 2) for v in vertices)
            error = abs(expected - high[j])
            max_vertex_error = max(max_vertex_error, error)
            assert error < 1e-7, (case, j, error)
            res = minimize(
                lambda x: np.sum((p[j] - x) ** 2),
                np.full(m, (L + U) / (2 * m)),
                jac=lambda x: 2 * (x - p[j]), bounds=[(0, None)] * m,
                constraints=[
                    {"type": "ineq", "fun": lambda x: x.sum() - L,
                     "jac": lambda x: np.ones(m)},
                    {"type": "ineq", "fun": lambda x: U - x.sum(),
                     "jac": lambda x: -np.ones(m)}],
                method="SLSQP", options={"ftol": 1e-10, "maxiter": 200})
            assert res.success, res.message
            error = abs(res.fun - low[j])
            max_projection_error = max(max_projection_error, error)
            assert error < 1e-6, (case, j, error)

    result = {
        "seed": 21093, "random_cases": 150,
        "paired_lp_solves": 1800, "individual_qp_solves": 600,
        "max_lp_absolute_error": float(max_lp_error),
        "generic_endpoint_comparisons":1800,
        "max_generic_lp_absolute_error":float(max_generic_lp_error),
        "max_projection_absolute_error": float(max_projection_error),
        "max_vertex_absolute_error": float(max_vertex_error),
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "scipy": scipy.__version__},
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "study_script_sha256": hashlib.sha256(
            (ROOT / "outputs/run_energy_rank_study.py").read_bytes()).hexdigest(),
        "generic_solver_sha256":hashlib.sha256((ROOT/'outputs/energy_rank_bounds.py').read_bytes()).hexdigest(),
        "note": "Independent numerical validation, not formal interval arithmetic."
    }
    (ROOT / "outputs/study_independent_audit.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
