"""Independent endpoint LP checks for sharp scalar certificate acquisition.

No production compact solver is imported. All polytopes and legal batches are
explicit below. Numerical checks support implementation, not historical priority.
Run: python work/risk_adaptivity_revision/general/check_general_lp.py
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import time
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linprog

TOL = 1e-8
OPTIONS = {"primal_feasibility_tolerance": 1e-9,
           "dual_feasibility_tolerance": 1e-9,
           "ipm_optimality_tolerance": 1e-10}


class LP:
    def __init__(self, n):
        self.n = n
        self.inequalities = []
        self.rhs = []
        self.equalities = []
        self.eq_rhs = []

    def row(self, entries):
        row = np.zeros(self.n)
        for k, value in entries:
            row[k] += value
        return row

    def le(self, entries, rhs):
        self.inequalities.append(self.row(entries))
        self.rhs.append(rhs)
        return len(self.rhs) - 1

    def eq(self, entries, rhs):
        self.equalities.append(self.row(entries))
        self.eq_rhs.append(rhs)

    def polytope(self, instance, start):
        for row, rhs in zip(instance["A"], instance["b"]):
            self.le([(start+i, x) for i, x in enumerate(row)], rhs)

    def solve(self, objective):
        start = time.perf_counter()
        result = linprog(np.asarray(objective),
            A_ub=np.asarray(self.inequalities) if self.rhs else None,
            b_ub=np.asarray(self.rhs) if self.rhs else None,
            A_eq=np.asarray(self.equalities) if self.eq_rhs else None,
            b_eq=np.asarray(self.eq_rhs) if self.eq_rhs else None,
            bounds=[(None, None)] * self.n, method="highs", options=OPTIONS)
        seconds = time.perf_counter() - start
        if not result.success:
            raise RuntimeError(result.message)
        ineq_res = max(0.0, float(np.max(np.asarray(self.inequalities) @ result.x - self.rhs))) if self.rhs else 0.0
        eq_res = float(np.max(np.abs(np.asarray(self.equalities) @ result.x - self.eq_rhs))) if self.eq_rhs else 0.0
        assert max(ineq_res, eq_res) <= TOL
        result.audit = dict(seconds=seconds, variables=self.n,
            inequalities=len(self.rhs), equalities=len(self.eq_rhs),
            max_inequality_violation=ineq_res, max_equality_residual=eq_res)
        return result


def endpoint_lp(instance, queried, fixed=None):
    """Max sharp width over fibers, optionally fixing some coordinate answers."""
    n = len(instance["c"])
    lp = LP(2*n)
    lp.polytope(instance, 0)
    lp.polytope(instance, n)
    for j in queried:
        lp.eq([(j, 1), (n+j, -1)], 0)
    for j, value in (fixed or {}).items():
        lp.eq([(j, 1)], value)
        lp.eq([(n+j, 1)], value)
    c = np.asarray(instance["c"])
    result = lp.solve(np.r_[-c, c])
    return -float(result.fun), result


def hardest_record(instance, budget):
    n = len(instance["c"])
    c = np.asarray(instance["c"])
    batches = list(itertools.combinations(range(n), budget))
    # Exact-budget sets dominate smaller ones because all coordinates are eligible.
    m = len(batches)
    eta = n+2*n*m
    lp = LP(eta+1)
    lp.polytope(instance, 0)
    eta_rows = []
    for k, Q in enumerate(batches):
        u, v = n+2*n*k, n+2*n*k+n
        lp.polytope(instance, u)
        lp.polytope(instance, v)
        for j in Q:
            lp.eq([(u+j, 1), (j, -1)], 0)
            lp.eq([(v+j, 1), (j, -1)], 0)
        eta_rows.append(lp.le([(eta, 1)]+[(u+j, -c[j]) for j in range(n)]
                             +[(v+j, c[j]) for j in range(n)], 0))
    obj = np.zeros(eta+1)
    obj[eta] = -1
    result = lp.solve(obj)
    rho = -float(result.fun)
    y = result.x[:n]
    weights = -np.asarray(result.ineqlin.marginals)[eta_rows]
    assert np.min(weights) >= -TOL and abs(np.sum(weights)-1) <= TOL

    # An independent upper-bound solve fixes the extracted dual batch weights,
    # maximizes all endpoint contrasts simultaneously at a common feasible record,
    # and does NOT impose the eta constraints from the first LP.
    upper = LP(eta)
    upper.polytope(instance, 0)
    upper_obj = np.zeros(eta)
    fixed_widths, fixed_batch_worst = [], []
    endpoint_checks = []
    for k, Q in enumerate(batches):
        u, v = n+2*n*k, n+2*n*k+n
        upper.polytope(instance, u)
        upper.polytope(instance, v)
        for j in Q:
            upper.eq([(u+j, 1), (j, -1)], 0)
            upper.eq([(v+j, 1), (j, -1)], 0)
        upper_obj[u:u+n] = -weights[k]*c
        upper_obj[v:v+n] = weights[k]*c
        width, witness = endpoint_lp(instance, Q, {j:y[j] for j in Q})
        fixed_widths.append(width)
        worst, _ = endpoint_lp(instance, Q)
        fixed_batch_worst.append(worst)
        endpoint_checks.append({"query": list(Q), "width_at_hard_record": width,
            "worst_width": worst, "batch_probability": float(weights[k]),
            "upper_endpoint": witness.x[:n].tolist(),
            "lower_endpoint": witness.x[n:].tolist()})
    upper_result = upper.solve(upper_obj)
    upper_value = -float(upper_result.fun)
    assert abs(upper_value-rho) <= TOL
    assert abs(min(fixed_widths)-rho) <= TOL
    return dict(mean_value=rho, hard_record=y.tolist(),
        min_width_at_hard_record=min(fixed_widths),
        dual_policy_worst_mean=upper_value, primal_dual_gap=abs(upper_value-rho),
        hard_record_gap=abs(min(fixed_widths)-rho),
        best_deterministic_batch_width=min(fixed_batch_worst),
        batch_checks=endpoint_checks, hardest_lp=result.audit,
        fixed_policy_upper_lp=upper_result.audit)


def two_query(instance):
    n = len(instance["c"])
    c = np.asarray(instance["c"])
    output = []
    for first in range(n):
        second_queries = [j for j in range(n) if j != first]
        eta, t = 2*n*(n-1), 2*n*(n-1)+1
        lp = LP(t+1)
        for k, second in enumerate(second_queries):
            u, v = 2*n*k, 2*n*k+n
            lp.polytope(instance, u)
            lp.polytope(instance, v)
            lp.eq([(u+first, 1), (t, -1)], 0)
            lp.eq([(v+first, 1), (t, -1)], 0)
            lp.eq([(u+second, 1), (v+second, -1)], 0)
            lp.le([(eta, 1)]+[(u+j, -c[j]) for j in range(n)]
                  +[(v+j, c[j]) for j in range(n)], 0)
        objective = np.zeros(t+1)
        objective[eta] = -1
        result = lp.solve(objective)
        value = -float(result.fun)
        answer = float(result.x[t])
        conditional = [endpoint_lp(instance, [first, j], {first:answer})[0]
                       for j in second_queries]
        assert abs(min(conditional)-value) <= TOL
        output.append(dict(first_query=first, worst_width=value,
            worst_first_answer=answer, second_queries=second_queries,
            conditional_widths_at_witness=conditional, audit=result.audit))
    return dict(optimal_deterministic_adaptive_width=min(x["worst_width"] for x in output),
                first_query_checks=output)


def box(n, c, extras=(), name="box"):
    A = np.r_[np.eye(n), -np.eye(n)].tolist()
    b = ([1.0]*n)+([0.0]*n)
    for row, value in extras:
        A.append(row)
        b.append(value)
    return dict(name=name, A=A, b=b, c=c)


def cases():
    triangle = dict(name="capacity_triangle", A=[[-1,0,0],[1,0,0],[0,-1,0],[-1,1,0],[0,0,-1],[1,0,1]],
                    b=[0,1,0,0,0,1], c=[1,1,1])
    yield triangle
    yield box(4, [1,-2,.5,3], name="box4_signed")
    yield box(4, [0,1,2,4], [([1,1,1,1],1)], "simplex4")
    yield box(5, [1,-1,2,-2,.5], [([1,1,1,0,0],1.4),([0,1,0,1,1],1.6)], "overlap5")
    yield box(4, [1,2,-1,-2], [([1,1,1,1],2),([-1,-1,-1,-1],-2)], "fixed_total4")
    yield box(4, [1,2,-1,-2], [([1,1,0,0],1),([-1,-1,0,0],-1),([-1,0,1,0],0),([0,-1,0,1],0)], "coupled4")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("verification.json"))
    args = parser.parse_args()
    all_results = []
    for instance in cases():
        start = time.perf_counter()
        mean = hardest_record(instance, 2)
        adaptive = two_query(instance)
        assert mean["mean_value"] <= adaptive["optimal_deterministic_adaptive_width"]+TOL
        assert adaptive["optimal_deterministic_adaptive_width"] <= mean["best_deterministic_batch_width"]+TOL
        all_results.append(dict(instance=instance, mean=mean, two_query=adaptive,
                                total_seconds=time.perf_counter()-start))
    first = all_results[0]
    assert abs(first["mean"]["mean_value"]-.5) <= TOL
    assert np.allclose([x["worst_width"] for x in first["two_query"]["first_query_checks"]], [.5,1,1], atol=TOL)
    report = dict(status="passed", python=platform.python_version(), numpy=np.__version__,
        scipy=scipy.__version__, machine=platform.platform(),
        tolerance=TOL, highs_options=OPTIONS, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope="Six constructed polytopes, coordinate queries, hard budget two. No forecasting data, no exhaustive adaptive-policy enumeration, no hardware comparison. Times are one execution each; first run includes solver initialization.",
        cases=all_results,
        max_primal_dual_gap=max(x["mean"]["primal_dual_gap"] for x in all_results),
        max_hard_record_gap=max(x["mean"]["hard_record_gap"] for x in all_results))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status":report["status"], "cases":len(all_results),
        "max_primal_dual_gap":report["max_primal_dual_gap"],
        "max_hard_record_gap":report["max_hard_record_gap"],
        "rows":[[r["instance"]["name"], r["mean"]["mean_value"],
                 r["two_query"]["optimal_deterministic_adaptive_width"],
                 r["mean"]["best_deterministic_batch_width"]] for r in all_results]}, indent=2))


if __name__ == "__main__":
    main()
