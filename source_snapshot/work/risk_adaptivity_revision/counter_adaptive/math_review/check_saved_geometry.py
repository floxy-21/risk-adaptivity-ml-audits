"""Independently audit a saved pilot/continuation counter geometry file.

No production geometry code is imported. All exact comparisons below use
the stored binary floats interpreted as rational numbers. Finite-game
reoptimization and selected conditional LPs use separately assembled LPs.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from check_counter_adaptive import (conditional_coefficients, conditional_lp,
                                    exact_envelope, span, width)

HERE = Path(__file__).resolve().parent
BATCHES = list(itertools.combinations(range(1, 6), 2))
TOL = 2e-8


def rational_weights(raw):
    w = [F.from_float(max(0.0, float(x))) for x in raw]
    total = sum(w)
    assert total > 0
    return [x/total for x in w]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("geometry", type=Path)
    p.add_argument("--full", action="store_true", help="Check every saved case; otherwise use up to 36 fixed evenly spaced cases")
    p.add_argument("--lp-cases", type=int, default=12, help="Evenly spaced cases for independent conditional LP checks")
    p.add_argument("--output", type=Path, default=HERE/"saved_geometry_verification.json")
    args = p.parse_args()
    started = time.perf_counter()
    obj = json.loads(args.geometry.read_text(encoding="utf-8"))
    cases = obj["cases"]
    indices = list(range(len(cases))) if args.full else sorted(set(np.linspace(0, len(cases)-1, min(36, len(cases)), dtype=int).tolist()))
    lp_indices = set(np.linspace(0, len(indices)-1, min(args.lp_cases, len(indices)), dtype=int).tolist())
    counts = {"cases": 0, "exact_batch_columns": 0, "finite_games_reoptimized": 0,
              "conditional_lps": 0, "certified_adaptive_guarantees": 0,
              "certified_strong_separations": 0, "exact_vs_generous_matrix_changes": 0}
    errors = {"A": 0.0, "V": 0.0, "normalization": 0.0, "conditional_lp": 0.0,
              "conditional_primal_residual": 0.0, "mean_value_vs_checked": 0.0,
              "primal_vs_adverse_upper": 0.0, "claimed_upper_understatement": 0.0}
    witnesses = []
    for rank, idx in enumerate(indices):
        row = cases[idx]; geom = row["geometry"]
        c = [F.from_float(float(z)) for z in row["c_normalized"]]
        original = [F.from_float(float(z)) for z in row["c"]]
        cr = max(original)-min(original)
        raw_normalized = [(v-min(original))/cr for v in original] if cr else [F(0)]*6
        errors["normalization"] = max(errors["normalization"], max(abs(float(a-b)) for a,b in zip(c,raw_normalized)))
        env = {k: exact_envelope(c, k) for k in range(1,6)}
        A = min(z[0] for z in env.values())
        selected_A = env[geom["first"]][0]
        errors["A"] = max(errors["A"], abs(float(A)-geom["A"]), abs(float(selected_A)-geom["A"]))
        assert abs(float(A)-geom["A"]) <= TOL
        assert float(selected_A-A) <= TOL
        for k in range(1,6):
            assert abs(float(env[k][0])-geom["first_worst"][k-1]) <= TOL
            t = F.from_float(float(geom["first_adverse_answers"][k-1]))
            assert 0 <= t <= 1
            val = min(a*t+b*(1-t) for a,b in env[k][2].values())
            assert abs(float(val)-geom["first_worst"][k-1]) <= TOL
        # Verify strengthened greedy's choice under its declared 1e-12 tie rule.
        greedy_scores = [max(span(c,0,k),span(c,k,6)) for k in range(1,6)]
        greedy_candidates = [i+1 for i,v in enumerate(greedy_scores) if float(v-min(greedy_scores)) <= 1.0001e-12]
        assert geom["greedy_first"] in greedy_candidates
        assert float(env[geom["greedy_first"]][0]-min(env[k][0] for k in greedy_candidates)) <= TOL
        # Reconstruct widths at every concentration record, all ten batches.
        V = [[width(c,[F(i==j) for i in range(6)],Q) for Q in BATCHES] for j in range(6)]
        rawV = [[width(raw_normalized,[F(i==j) for i in range(6)],Q) for Q in BATCHES] for j in range(6)]
        errors["V"] = max(errors["V"], max(abs(float(V[i][q])-geom["V"][i][q]) for i in range(6) for q in range(10)))
        assert errors["V"] <= TOL
        dets = [max(V[i][q] for i in range(6)) for q in range(10)]
        assert abs(float(min(dets))-geom["det_value"]) <= TOL
        assert abs(float(dets[geom["det_batch_index"]])-geom["det_value"]) <= TOL
        probs = rational_weights(geom["mean_weights"])
        checked_mean = max(sum(V[i][q]*probs[q] for q in range(10)) for i in range(6))
        errors["mean_value_vs_checked"] = max(errors["mean_value_vs_checked"], abs(float(checked_mean)-geom["mean_value"]))
        assert abs(float(checked_mean)-geom["mean_checked"]) <= TOL
        for entry in geom["precision"]:
            tau = F.from_float(float(entry["fraction"]))
            eps = F.from_float(1e-9)
            generous = [[int(V[i][q] <= tau+eps) for q in range(10)] for i in range(6)]
            actual = [[int(rawV[i][q] <= tau) for q in range(10)] for i in range(6)]
            counts["exact_vs_generous_matrix_changes"] += sum(generous[i][q] != actual[i][q] for i in range(6) for q in range(10))
            weights = rational_weights(entry["weights"])
            # Exact feasible rational adverse completion distribution. The
            # raw-coefficient matrix checks the original contrast, not just
            # the saved rounded normalization.
            upper = max(sum(weights[i]*actual[i][q] for i in range(6)) for q in range(10))
            errors["claimed_upper_understatement"] = max(errors["claimed_upper_understatement"], float(upper)-entry["upper"])
            assert float(upper) <= entry["upper"]+TOL
            S = np.asarray(generous,dtype=float)
            primal = linprog(np.r_[np.zeros(10),-1], A_ub=np.c_[-S,np.ones(6)],
                             b_ub=np.zeros(6), A_eq=[np.r_[np.ones(10),0]], b_eq=[1],
                             bounds=[(0,None)]*10+[(0,1)], method="highs")
            assert primal.success
            errors["primal_vs_adverse_upper"] = max(errors["primal_vs_adverse_upper"],abs(-primal.fun-entry["upper"]))
            assert abs(-primal.fun-entry["upper"]) <= TOL
            # Check the implemented selected first cut's exact guarantee in
            # the original coefficient scale, rather than relying on margin.
            raw_selected_A = exact_envelope(raw_normalized,geom["first"])[0]
            if entry["adaptive_guarantee"]:
                assert raw_selected_A <= tau
                counts["certified_adaptive_guarantees"] += 1
            if entry["separation_le_70"]:
                assert raw_selected_A <= tau and upper <= F(7,10)
                counts["certified_strong_separations"] += 1
            counts["finite_games_reoptimized"] += 1
            if entry["fraction"] == .5:
                witnesses.append({"id":row["id"],"A_exact_original_coefficients":str(raw_selected_A),
                                  "adverse_upper_exact_original_coefficients":str(upper),
                                  "weights_exact":list(map(str,weights)),
                                  "adaptive_guarantee":entry["adaptive_guarantee"],
                                  "separation_le_70":entry["separation_le_70"]})
        if rank in lp_indices:
            for k in range(1,6):
                for j in range(1,6):
                    if j == k:
                        continue
                    a,b = conditional_coefficients(c,k,j)
                    for t in [F(0),F(1,2),F(1)]:
                        val,residual = conditional_lp(c,k,j,t,F(1))
                        errors["conditional_lp"] = max(errors["conditional_lp"],abs(val-float(a*t+b*(1-t))))
                        errors["conditional_primal_residual"] = max(errors["conditional_primal_residual"],residual)
                        assert abs(val-float(a*t+b*(1-t))) <= TOL
                        counts["conditional_lps"] += 1
        counts["cases"] += 1; counts["exact_batch_columns"] += 10
        if (rank+1)%300 == 0:
            print(f"independent geometry {rank+1}/{len(indices)}",flush=True)
    report = {"status":"PASS", "scope":"Exact rational envelope and adverse distributions for every checked saved geometry; independent finite-game primal and conditional LP checks",
              "geometry_path":str(args.geometry),"geometry_sha256":hashlib.sha256(args.geometry.read_bytes()).hexdigest(),
              "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "available_cases":len(cases),"full":args.full,"counts":counts,"maximum_errors":errors,
              "comparison_tolerance":TOL,"lp_sample_indices":[indices[i] for i in sorted(lp_indices)],
              "runtime_seconds":time.perf_counter()-started,"primary_exact_witnesses":witnesses}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "primary_exact_witnesses"},indent=2))


if __name__ == "__main__":
    main()
