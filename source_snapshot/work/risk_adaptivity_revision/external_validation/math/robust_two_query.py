"""Small-polytope LP prototype for fixed bounded stored-readout uncertainty.

These are constructed numerical checks, not an external-meter experiment.
The complete latent record, including readout errors, precedes randomization.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import itertools
import json
import platform
from pathlib import Path
import time

import numpy as np
import scipy
from scipy.optimize import linprog


@dataclass
class Model:
    A: np.ndarray
    b: np.ndarray
    c: np.ndarray
    queries: np.ndarray
    bounds: list


def solve(objective, inequalities, rhs, equalities, eqrhs, bounds):
    return_result = linprog(
        objective,
        A_ub=np.asarray(inequalities) if inequalities else None,
        b_ub=np.asarray(rhs) if rhs else None,
        A_eq=np.asarray(equalities) if equalities else None,
        b_eq=np.asarray(eqrhs) if eqrhs else None,
        bounds=bounds,
        method="highs",
        options={"primal_feasibility_tolerance": 1e-9,
                 "dual_feasibility_tolerance": 1e-9},
    )
    if not return_result.success:
        raise RuntimeError(return_result.message)
    return return_result


def copies(model, count, extra=0):
    n = len(model.c); size = count*n+extra
    inequalities = []; rhs = []
    for index in range(count):
        for row, value in zip(model.A, model.b):
            expanded = np.zeros(size)
            expanded[index*n:(index+1)*n] = row
            inequalities.append(expanded); rhs.append(float(value))
    return size, inequalities, rhs, list(model.bounds)*count


def worst_batch(model, batch, record=None):
    """Global worst width, or sharp width at one complete latent record."""
    n = len(model.c)
    size, inequalities, rhs, bounds = copies(model, 2)
    objective = np.r_[-model.c, model.c]
    equalities = []; eqrhs = []
    for query in batch:
        row = model.queries[query]
        if record is None:
            equalities.append(np.r_[row, -row]); eqrhs.append(0.)
        else:
            answer = float(row@record)
            equalities.append(np.r_[row, np.zeros(n)]); eqrhs.append(answer)
            equalities.append(np.r_[np.zeros(n), row]); eqrhs.append(answer)
    result = solve(objective, inequalities, rhs, equalities, eqrhs, bounds)
    return float(-result.fun), result.x[:n].copy(), result.x[n:].copy()


def first_query_value(model, first, seconds=None, fixed_answer=None):
    """Exact LP formulation for max_t min_j g_ij(t), up to LP tolerances."""
    n = len(model.c)
    if seconds is None:
        seconds = [j for j in range(len(model.queries)) if j != first]
    size, inequalities, rhs, bounds = copies(model, 2*len(seconds), 2)
    eta, answer = size-2, size-1
    objective = np.zeros(size); objective[eta] = -1.
    equalities = []; eqrhs = []
    for index, second in enumerate(seconds):
        u = 2*index*n; v = u+n
        width = np.zeros(size)
        width[u:u+n] = -model.c; width[v:v+n] = model.c; width[eta] = 1.
        inequalities.append(width); rhs.append(0.)
        for offset in [u, v]:
            row = np.zeros(size)
            row[offset:offset+n] = model.queries[first]; row[answer] = -1.
            equalities.append(row); eqrhs.append(0.)
        row = np.zeros(size)
        row[u:u+n] = model.queries[second]; row[v:v+n] = -model.queries[second]
        equalities.append(row); eqrhs.append(0.)
    bounds += [(0., None), (None, None) if fixed_answer is None else (fixed_answer, fixed_answer)]
    result = solve(objective, inequalities, rhs, equalities, eqrhs, bounds)
    return {"value": float(-result.fun), "adverse_first_answer": float(result.x[answer]),
            "variables": size, "first": int(first), "seconds": list(map(int, seconds))}


def mean_hardest(model, batches):
    """Enumerative mean-risk LP and its randomized-batch multipliers."""
    n = len(model.c)
    size, inequalities, rhs, bounds = copies(model, 1+2*len(batches), 1)
    eta = size-1
    objective = np.zeros(size); objective[eta] = -1.
    equalities = []; eqrhs = []; width_rows = []
    for index, batch in enumerate(batches):
        u = (1+2*index)*n; v = u+n
        width = np.zeros(size)
        width[u:u+n] = -model.c; width[v:v+n] = model.c; width[eta] = 1.
        width_rows.append(len(inequalities)); inequalities.append(width); rhs.append(0.)
        for query in batch:
            for offset in [u, v]:
                row = np.zeros(size)
                row[offset:offset+n] = model.queries[query]
                row[:n] -= model.queries[query]
                equalities.append(row); eqrhs.append(0.)
    # eta is free: its width constraints already bound the optimum below.
    # A redundant eta>=0 bound can absorb dual mass at zero-width optima.
    result = solve(objective, inequalities, rhs, equalities, eqrhs, bounds+[(None, None)])
    probabilities = -result.ineqlin.marginals[width_rows]
    assert probabilities.min() >= -1e-8 and abs(probabilities.sum()-1) <= 1e-8
    record = result.x[:n]
    widths = [worst_batch(model, q, record)[0] for q in batches]
    assert min(widths) >= -result.fun-2e-8
    return {"value": float(-result.fun), "variables": size,
            "record": record.tolist(), "batch_probabilities": probabilities.tolist(),
            "minimum_batch_width_at_record": min(widths)}


def meter_model(coefficients, observed_total=1., storage_error=0., relative_increment_error=0.):
    """Declared sensitivity model; not an unconditional manufacturer claim.

    Relative allowance applies to true increments: (1-alpha)x <= m <=
    (1+alpha)x. Storage error concerns accumulated reported m only.
    """
    c = np.asarray(coefficients, dtype=float)
    assert c.shape == (6,)
    alpha = float(relative_increment_error)
    assert 0 <= alpha < 1 and storage_error >= 0
    use_separate_increment = alpha != 0.
    n = 18 if use_separate_increment else 12
    meter_offset = 6 if use_separate_increment else 0
    start = 12 if use_separate_increment else 6
    err_start = start+1
    target = np.zeros(n); target[:6] = c
    bounds = [(0., None)]*start+[(None, None)]*(n-start)
    bounds[start] = (-storage_error, storage_error)
    for k in range(5):
        bounds[err_start+k] = (-storage_error, storage_error)
    A = []; b = []
    total = np.zeros(n); total[meter_offset:meter_offset+6] = 1.; total[start] = 1.
    A += [total, -total]; b += [observed_total+storage_error, -observed_total+storage_error]
    if use_separate_increment:
        for h in range(6):
            lower = np.zeros(n); lower[h] = 1-alpha; lower[meter_offset+h] = -1.
            upper = np.zeros(n); upper[h] = -(1+alpha); upper[meter_offset+h] = 1.
            A += [lower, upper]; b += [0., 0.]
    queries = np.zeros((5, n))
    for k in range(1, 6):
        queries[k-1, meter_offset:meter_offset+k] = 1.
        queries[k-1, start] = 1.; queries[k-1, err_start+k-1] = 1.
    return Model(np.asarray(A), np.asarray(b), target, queries, bounds)


def three_coordinate():
    return Model(np.array([[-1., 1., 0.], [1., 0., 1.]]), np.array([0., 1.]),
                 np.ones(3), np.eye(3), [(0., 1.), (0., None), (0., None)])


def analyze_constructed(name, model):
    begin = time.perf_counter()
    batches = list(itertools.combinations(range(len(model.queries)), 2))
    initial = worst_batch(model, [])[0]
    deterministic = [worst_batch(model, q)[0] for q in batches]
    firsts = [first_query_value(model, k) for k in range(len(model.queries))]
    best = min(firsts, key=lambda item: (item["value"], item["first"]))
    # Independently test the Helly pair reduction at the chosen first query.
    seconds = [j for j in range(len(model.queries)) if j != best["first"]]
    supports = [(j,) for j in seconds]+list(itertools.combinations(seconds, 2))
    pair_values = [first_query_value(model, best["first"], list(s)) for s in supports]
    sparse = min(pair_values, key=lambda item: (item["value"], len(item["seconds"]), item["seconds"]))
    assert abs(sparse["value"]-best["value"]) <= 2e-8
    mean = mean_hardest(model, batches)
    return {"name": name, "latent_dimension": len(model.c), "initial_width": initial,
            "best_deterministic_batch_worst_width": min(deterministic),
            "optimal_deterministic_adaptive": best,
            "sparse_Helly_successors": sparse,
            "Helly_sparse_value_discrepancy": abs(sparse["value"]-best["value"]),
            "mean_hardest_record": mean,
            "seconds": time.perf_counter()-begin}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("prototype_checks.json"))
    args = parser.parse_args()
    specifications = [("three-coordinate exact", three_coordinate())]
    coeff = [0., 0., 1., 1., 0., 1.]
    for delta, alpha in [(0., 0.), (.001, 0.), (.01, 0.), (0., .01), (.001, .01)]:
        specifications.append((f"constructed meter delta={delta} alpha={alpha}",
                               meter_model(coeff, storage_error=delta, relative_increment_error=alpha)))
    # Coupled boxes with arbitrary scalar readouts check the Helly reduction
    # beyond cumulative simplexes. The seed and case count are fixed here.
    rng = np.random.default_rng(20261012)
    for index in range(12):
        n = 3+index % 4
        A = rng.normal(size=(n+2, n))
        b = .25+rng.random(n+2)
        c = rng.normal(size=n)
        queries = rng.normal(size=(5, n))
        specifications.append((f"constructed coupled polytope {index}",
            Model(A, b, c, queries, [(-1., 1.)]*n)))
    cases = [analyze_constructed(name, model) for name, model in specifications]
    for row in cases[:2]:
        assert abs(row["optimal_deterministic_adaptive"]["value"]-.5) <= 1e-8
        assert abs(row["best_deterministic_batch_worst_width"]-1.) <= 1e-8
        assert abs(row["mean_hardest_record"]["value"]-.5) <= 1e-8
    report = {"status": "PASS", "scope": "Constructed LP prototype checks; no real-meter evidence or human validation",
              "python": platform.python_version(), "scipy": scipy.__version__,
              "platform": platform.platform(), "LP_tolerance": 1e-9,
              "comparison_tolerance": 2e-8, "coupled_polytope_seed": 20261012, "cases": cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "cases": [{"name":r["name"],
        "initial_width":r["initial_width"], "A":r["optimal_deterministic_adaptive"]["value"],
        "D":r["best_deterministic_batch_worst_width"], "rho":r["mean_hardest_record"]["value"],
        "Helly_difference":r["Helly_sparse_value_discrepancy"], "seconds":r["seconds"]}
        for r in cases]}, indent=2))


if __name__ == "__main__":
    main()
