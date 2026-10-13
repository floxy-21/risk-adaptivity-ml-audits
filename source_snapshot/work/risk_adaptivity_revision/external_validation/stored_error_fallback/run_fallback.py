"""Fixed-budget escalation at unchanged error allowance and precision.

No network, forecasting, model training, hidden targets or recorded responses.
"""
from __future__ import annotations
import csv
from fractions import Fraction as F
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location("fallback_robust", ROOT/"math/robust_two_query.py")
robust = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = robust
spec.loader.exec_module(robust)
DELTA = F(1, 100)
TAU = F(1, 2)
TOL = 2e-8


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model(coefficients):
    A = np.zeros((2, 11)); A[0, :6] = 1; A[1, :6] = -1
    queries = np.zeros((5, 11))
    for k in range(5):
        queries[k, :k+1] = 1; queries[k, 6+k] = 1
    return robust.Model(A, np.array([1., -1.]), np.r_[list(map(float, coefficients)), np.zeros(5)], queries,
                        [(0., None)]*6+[(-float(DELTA), float(DELTA))]*5)


def exact_system(c, batch):
    n = 22
    f = [-v for v in c]+[F(0)]*5+list(c)+[F(0)]*5
    A = []; b = []
    for offset in (0, 11):
        row = [F(0)]*n
        for i in range(6): row[offset+i] = F(1)
        A.extend([row, [-v for v in row]]); b.extend([F(1), F(-1)])
    equalities = []
    for boundary in batch:
        row = [F(0)]*n
        for i in range(boundary): row[i] = F(1); row[11+i] = F(-1)
        row[6+boundary-1] = F(1); row[17+boundary-1] = F(-1)
        equalities.append(row)
    boxes = ([(F(0), F(1))]*6+[(-DELTA, DELTA)]*5)*2
    return f, A, b, equalities, [F(0)]*len(equalities), boxes


def certify(case, c, batch, proposal):
    f,A,b,E,h,boxes = exact_system(c,batch)
    solution = linprog(list(map(float,f)), A_ub=np.array(A,dtype=float),b_ub=list(map(float,b)),
                       A_eq=np.array(E,dtype=float),b_eq=list(map(float,h)),
                       bounds=[tuple(map(float,pair)) for pair in boxes],method="highs",
                       options={"primal_feasibility_tolerance":1e-9,"dual_feasibility_tolerance":1e-9})
    assert solution.success, solution.message
    lam = [min(F(0), F.from_float(float(v))) for v in solution.ineqlin.marginals]
    nu = [F.from_float(float(v)) for v in solution.eqlin.marginals]
    residual = [f[j]-sum(row[j]*v for row,v in zip(A,lam))-sum(row[j]*v for row,v in zip(E,nu))
                for j in range(22)]
    row_term = sum(v*w for v,w in zip(lam,b))+sum(v*w for v,w in zip(nu,h))
    correction = sum(min(r*lo,r*hi) for r,(lo,hi) in zip(residual,boxes))
    upper = -(row_term+correction)
    assert abs(float(-solution.fun)-proposal) <= TOL
    proof = {"id":case["id"],"system_id":case["system_id"],"delta_exact":str(DELTA),
             "query_boundaries":list(batch),"queries":len(batch),
             "original_coefficients_exact":[str(F.from_float(float(v))) for v in case["c"]],
             "normalized_coefficients_exact":list(map(str,c)),
             "variable_order":"u[6 increments,5 errors],v[6 increments,5 errors]",
             "objective":list(map(str,f)),"A_ub":[list(map(str,r)) for r in A],"b_ub":list(map(str,b)),
             "A_eq":[list(map(str,r)) for r in E],"b_eq":list(map(str,h)),
             "bounds":[list(map(str,pair)) for pair in boxes],
             "inequality_multipliers":list(map(str,lam)),"equality_multipliers":list(map(str,nu)),
             "stationarity_residual":list(map(str,residual)),"row_term_exact":str(row_term),
             "residual_box_correction_exact":str(correction),"certified_upper_exact":str(upper),
             "threshold_exact":str(TAU),"certified_margin_exact":str(TAU-upper),
             "proposal_width":proposal,"box_bounded_LP_width":float(-solution.fun),
             "passes_exactly":upper<=TAU,"scope":"Rigorous fixed-batch worst-width upper bound, not an exact optimal value"}
    return proof


def main():
    start = time.perf_counter()
    lock = json.loads((HERE/"protocol_lock.json").read_text())
    for entry in lock["inputs"].values():
        assert digest(ROOT/entry["path"].replace("\\","/")) == entry["sha256"]
    half = json.loads((ROOT/"replay/half_witnesses.json").read_text())
    geometry = {r["id"]:r for r in json.loads((ROOT/"replay/geometry.json").read_text())["cases"]}
    positives = json.loads((ROOT/"stored_error_sensitivity/exact_certificates/certificates.json").read_text())["certificates"]
    two = {r["id"]:r for r in positives if F(r["delta_exact"])==DELTA}
    assert len(half)==29 and len(two)==22
    rows=[]; cases=[]; certificates=[]; failed_certificates=[]; prescriptions=[]
    for witness in half:
        case=geometry[witness["id"]]
        raw=[F.from_float(float(v)) for v in case["c"]]
        scale=max(raw)-min(raw); assert scale>0
        c=[v/scale for v in raw]
        m=model(c)
        by_budget=[]
        for q in lock["budgets"]:
            candidates=[]
            for batch in itertools.combinations(range(1,6),q):
                width=robust.worst_batch(m,[b-1 for b in batch])[0]
                rows.append({"id":case["id"],"system_id":case["system_id"],"budget":q,
                             "batch":";".join(map(str,batch)),"worst_width_over_W0":width,
                             "numerically_passes":width<=float(TAU)+TOL})
                candidates.append((width,batch))
            minimum=min(x[0] for x in candidates)
            chosen=min((batch,width) for width,batch in candidates if width<=minimum+TOL)
            by_budget.append({"budget":q,"minimum_numerical_width":minimum,
                              "selected_batch":list(chosen[0]),"selected_batch_width":chosen[1]})
        passing=None
        for best in by_budget:
            if best["selected_batch_width"]<=float(TAU)+TOL:
                proof=certify(case,c,best["selected_batch"],best["selected_batch_width"])
                if proof["passes_exactly"]:
                    passing=proof;certificates.append(proof);break
                failed_certificates.append(proof)
        assert passing is not None, "No rigorously certified fixed fallback at any budget"
        prior=two.get(case["id"])
        policy={"id":case["id"],"system_id":case["system_id"],"delta_exact":str(DELTA),
                "threshold_over_W0_exact":str(TAU),"original_coefficients_exact":list(map(str,raw)),
                "normalized_coefficients_exact":list(map(str,c)),"exact_total":True,
                "selection_uses_hidden_answers":False}
        if prior:
            # Existing support indexes are one-based, as recorded by its exporter.
            policy.update({"policy_type":"existing_two_query_adaptive_support","hard_query_budget":2,
                           "first_query":prior["first"],"second_query_candidates":prior["seconds"],
                           "support_certified_upper_exact":prior["certified_upper_exact"],
                           "source":"../stored_error_sensitivity/exact_certificates/certificates.json"})
        else:
            policy.update({"policy_type":"fixed_batch_fallback","hard_query_budget":passing["queries"],
                           "query_boundaries":passing["query_boundaries"],
                           "batch_certified_upper_exact":passing["certified_upper_exact"],
                           "source":"fixed_batch_certificates.json"})
        prescriptions.append(policy)
        cases.append({"id":case["id"],"system_id":case["system_id"],"model_a":case["model_a"],
                      "model_b":case["model_b"],"existing_two_query_certificate":prior is not None,
                      "budget_results":by_budget,"minimum_certified_fixed_budget":passing["queries"],
                      "certified_fixed_batch":passing["query_boundaries"],
                      "fixed_certified_upper_exact":passing["certified_upper_exact"],
                      "hybrid_hard_query_budget":policy["hard_query_budget"]})
    with (HERE/"all_batches.csv").open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    total=sum(p["hard_query_budget"] for p in prescriptions)
    fixed_total=sum(p["queries"] for p in certificates)
    report={"status":"PASS","scope":"Post-analysis guaranteed hard-budget escalation, not a revised two-query result or measured request saving",
            "cases":29,"evaluated_fixed_batches":len(rows),"fixed_batch_certificates":len(certificates),
            "original_two_query_passes":len(two),"fallback_cases":29-len(two),
            "fixed_budget_counts":{str(q):sum(r["minimum_certified_fixed_budget"]==q for r in cases) for q in lock["budgets"]},
            "hybrid_budget_counts":{str(q):sum(r["hybrid_hard_query_budget"]==q for r in cases) for q in lock["budgets"]},
            "total_hybrid_reserved_queries":total,"mean_hybrid_reserved_queries":total/29,
            "maximum_hybrid_reserved_queries":max(p["hard_query_budget"] for p in prescriptions),
            "total_fixed_reserved_queries":fixed_total,
            "reserved_budget_reduction_exact":str(F(fixed_total-total,fixed_total)),
            "reserved_budget_reduction_percent":100*(fixed_total-total)/fixed_total,
            "minimum_fixed_certificate_margin_exact":str(min(F(p["certified_margin_exact"]) for p in certificates)),
            "failed_certificate_attempts":len(failed_certificates),
            "numerical_tolerance":TOL,"seconds":time.perf_counter()-start,"script_sha256":digest(Path(__file__))}
    exports={"cases.json":cases,"fixed_batch_certificates.json":{"schema":"fixed-batch-rational-dual-box-v1","certificates":certificates},
             "failed_certificate_attempts.json":failed_certificates,"prescriptions.json":prescriptions,"report.json":report}
    for name,content in exports.items():
        (HERE/name).write_text(json.dumps(content,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
