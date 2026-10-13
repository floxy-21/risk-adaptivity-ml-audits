"""Fixed-level readout-error sensitivity of all 29 frozen external half cases.

No network, refitting, physical-device accuracy assumption, or response replay.
"""
from __future__ import annotations
import csv
from fractions import Fraction
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import platform
import sys
import time
import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location("robust_two_query", ROOT/"math/robust_two_query.py")
robust = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = robust
spec.loader.exec_module(robust)
BATCHES = list(itertools.combinations(range(5), 2))
TOL = 2e-8
CHECKS = []
original_solve = robust.solve


def checked_solve(c, A, b, E, f, bounds):
    r = original_solve(c, A, b, E, f, bounds)
    c = np.asarray(c)
    stationarity = c.copy()
    dual_objective = 0.
    residual = 0.
    if len(A):
        A = np.asarray(A); b = np.asarray(b)
        stationarity -= A.T@r.ineqlin.marginals
        dual_objective += b@r.ineqlin.marginals
        residual = max(residual, float(np.max(A@r.x-b)))
    if len(E):
        E = np.asarray(E); f = np.asarray(f)
        stationarity -= E.T@r.eqlin.marginals
        dual_objective += f@r.eqlin.marginals
        residual = max(residual, float(np.max(np.abs(E@r.x-f))))
    stationarity -= r.lower.marginals+r.upper.marginals
    for i, (lo, hi) in enumerate(bounds):
        if lo is not None:
            dual_objective += lo*r.lower.marginals[i]
            residual = max(residual, lo-r.x[i])
        if hi is not None:
            dual_objective += hi*r.upper.marginals[i]
            residual = max(residual, r.x[i]-hi)
    CHECKS.append({"primal_residual": max(0., residual),
                   "stationarity_residual": float(np.max(np.abs(stationarity))),
                   "absolute_primal_dual_gap": float(abs(r.fun-dual_objective))})
    return r


robust.solve = checked_solve


def make_model(c, delta):
    # x_1,...,x_6 followed by fixed e_1,...,e_5; retained endpoints exact.
    A = np.zeros((2, 11)); A[0, :6] = 1.; A[1, :6] = -1.
    queries = np.zeros((5, 11))
    for k in range(5):
        queries[k, :k+1] = 1.; queries[k, 6+k] = 1.
    return robust.Model(A, np.array([1., -1.]), np.r_[c, np.zeros(5)], queries,
                        [(0., None)]*6+[(-delta, delta)]*5)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    begin = time.perf_counter()
    lock = json.loads((HERE/"protocol_lock.json").read_text())
    assert sha(HERE/"PROTOCOL.txt") == lock["protocol_sha256"]
    geom = ROOT/"replay/geometry.json"; wit = ROOT/"replay/half_witnesses.json"
    assert sha(geom) == lock["geometry_sha256"] and sha(wit) == lock["half_witnesses_sha256"]
    assert sha(ROOT/"math/robust_two_query.py") == lock["solver_sha256"]
    witnesses = json.loads(wit.read_text())
    all_cases = {row["id"]:row for row in json.loads(geom.read_text())["cases"]}
    assert len(witnesses) == 29
    rows = []; ledgers = []; input_rows = []
    for witness in witnesses:
        source = all_cases[witness["id"]]
        # Positive rescaling only. Exact E normalization divides all widths by E.
        c_original = np.array(source["c"])
        coefficient_range = float(np.ptp(c_original))
        c = c_original/coefficient_range
        input_rows.append({"id":source["id"], "c_original":c_original.tolist(),
                           "coefficient_range":coefficient_range, "c_scaled":c.tolist(),
                           "original_total":source["E"], "adverse_weights":witness["adverse_weights"]})
        previous_A = previous_D = -float("inf")
        for delta in lock["deltas"]:
            first_check = len(CHECKS)
            model = make_model(c, delta)
            initial = robust.worst_batch(model, ())[0]
            det = [robust.worst_batch(model, q)[0] for q in BATCHES]
            firsts = [robust.first_query_value(model, k) for k in range(5)]
            best = min(firsts, key=lambda z:(z["value"],z["first"]))
            seconds = [j for j in range(5) if j != best["first"]]
            supports = [(j,) for j in seconds]+list(itertools.combinations(seconds, 2))
            support_values = [robust.first_query_value(model, best["first"], list(s)) for s in supports]
            support = min(support_values, key=lambda z:(z["value"],len(z["seconds"]),z["seconds"]))
            # Check the inherited adverse profiles numerically too. The exact
            # upper-bound transfer follows set inclusion, not these float LPs.
            weights = np.array([float(Fraction(w)) for w in witness["adverse_weights"]])
            adverse_widths = []
            for h in range(6):
                record = np.zeros(11); record[h] = 1.
                adverse_widths.append([robust.worst_batch(model, q, record)[0] for q in BATCHES])
            adverse_widths = np.array(adverse_widths)
            # Potential tolerance-boundary successes count conservatively as successes.
            upper_check = float(np.max(weights@(adverse_widths <= .5+TOL)))
            A = best["value"]; D = min(det)
            assert abs(initial-1.) <= TOL
            assert abs(support["value"]-A) <= TOL
            assert A >= previous_A-TOL and D >= previous_D-TOL
            assert upper_check <= .5+TOL
            zero_A_discrepancy = zero_D_discrepancy = None
            if delta == 0:
                zero_A_discrepancy = abs(A-float(Fraction(witness["A_over_W0"])))
                zero_D_discrepancy = abs(D-float(Fraction(witness["D_over_W0"])))
                assert max(zero_A_discrepancy,zero_D_discrepancy) <= TOL
            checks = CHECKS[first_check:]
            row = {"id":source["id"],"system_id":source["system_id"],
                   "pair":source["model_a"]+"/"+source["model_b"],"delta":delta,
                   "initial_width_over_original_W0":initial,
                   "tau_original":.5,"tau_half_new":.5*initial,
                   "adaptive_worst_width_over_original_W0":A,
                   "deterministic_batch_worst_width_over_original_W0":D,
                   "adaptive_threshold_margin":.5-A,
                   "adaptive_guarantee":A <= .5+TOL,
                   "adaptive_guarantee_half_new":A <= .5*initial+TOL,
                   "deterministic_batch_guarantee":D <= .5+TOL,
                   "best_first_query":best["first"]+1,
                   "sparse_second_queries":";".join(str(s+1) for s in support["seconds"]),
                   "support_value":support["value"],"support_discrepancy":abs(support["value"]-A),
                   "half_lower_check":support["value"] <= .5+TOL,
                   "inherited_exact_batch_upper":.5,"numeric_adverse_upper_check":upper_check,
                   "zero_A_discrepancy":zero_A_discrepancy,"zero_D_discrepancy":zero_D_discrepancy,
                   "LP_count":len(checks),
                   **{key:max(z[key] for z in checks) for key in checks[0]}}
            rows.append(row)
            ledgers.append({**row,"first_query_LPs":firsts,"support_LPs":support_values,
                            "deterministic_batch_widths":det,"batch_queries":[[a+1,b+1] for a,b in BATCHES],
                            "zero_error_adverse_widths":adverse_widths.tolist(),
                            "adverse_profile_weights":witness["adverse_weights"]})
            previous_A, previous_D = A, D
    groups=[]
    for delta in lock["deltas"]:
        subset=[r for r in rows if r["delta"]==delta]
        groups.append({"delta":delta,"cases":len(subset),
                       "adaptive_guaranteed":sum(r["adaptive_guarantee"] for r in subset),
                       "deterministic_batch_guaranteed":sum(r["deterministic_batch_guarantee"] for r in subset),
                       "half_lower_numerically_verified":sum(r["half_lower_check"] for r in subset),
                       "adverse_upper_retained_exact":29,
                       "initial_width_changed":sum(abs(r["initial_width_over_original_W0"]-1)>TOL for r in subset),
                       "adaptive_width_min_median_max":[float(x) for x in np.quantile([r["adaptive_worst_width_over_original_W0"] for r in subset],[0,.5,1])],
                       "adaptive_threshold_margin_min":min(r["adaptive_threshold_margin"] for r in subset),
                       "per_system":[{"system_id":s,"cases":sum(r["system_id"]==s for r in subset),
                                      "adaptive_guaranteed":sum(r["system_id"]==s and r["adaptive_guarantee"] for r in subset)} for s in [1,2,7]]})
    report={"status":"PASS","scope":"Illustrative post-analysis bounded stored-readout sensitivity, not device-calibrated physical accuracy or response replay",
            "protocol":lock,"cases":29,"evaluations":len(rows),"LP_count":len(CHECKS),
            "comparison_tolerance":TOL,"solver_primal_dual_tolerance":1e-9,
            "max_numerical_residuals":{key:max(z[key] for z in CHECKS) for key in CHECKS[0]},
            "max_zero_error_A_discrepancy":max(r["zero_A_discrepancy"] or 0 for r in rows),
            "max_zero_error_D_discrepancy":max(r["zero_D_discrepancy"] or 0 for r in rows),
            "max_Helly_support_discrepancy":max(r["support_discrepancy"] for r in rows),
            "groups":groups,"seconds":time.perf_counter()-begin,
            "python":platform.python_version(),"numpy":np.__version__,"scipy":scipy.__version__,
            "script_sha256":sha(Path(__file__))}
    with (HERE/"case_ledger.csv").open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    for filename,content in [("inputs.json",input_rows),("witnesses.json",ledgers),("report.json",report)]:
        (HERE/filename).write_text(json.dumps(content,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
