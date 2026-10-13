"""Post-analysis feedback triage at the unchanged half-width threshold.

Geometry is classified before any replay file is opened. All comparisons use
exact rational arithmetic on the serialized binary64 forecast coefficients.
The vertex game supplies an upper bound on continuum batch success, except
where an explicit all-completion lower guarantee proves equality.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import time
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
BATCHES = list(itertools.combinations(range(1, 6), 2))
CLASS_NAMES = ["batch_suffices", "feedback_required", "adaptive_not_guaranteed"]
METRICS = ["success_0.5", "relative_width", "scaled_width", "winner_probability", "requests"]


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ran(c, a, b):
    return max(c[a:b]) - min(c[a:b])


def batch_profile(c, cuts):
    """Independent segment-range calculation, one entry per concentration record."""
    ans = [F(0)] * 6
    boundaries = [0, *cuts, 6]
    for a, b in zip(boundaries, boundaries[1:]):
        ans[a:b] = [ran(c, a, b)] * (b - a)
    return ans


def conditional(c, k, j):
    """Worst widths within the observed prefix and suffix, respectively."""
    cuts = sorted((k, j))
    profiles = batch_profile(c, cuts)
    return max(profiles[:k]), max(profiles[k:])


def worst_envelope(c, k):
    ab = [(j, *conditional(c, k, j)) for j in range(1, 6) if j != k]
    answers = {F(0), F(1)}
    for (_, a, b), (_, aa, bb) in itertools.combinations(ab, 2):
        slope = (a-b) - (aa-bb)
        if slope:
            t = (bb-b)/slope
            if 0 <= t <= 1:
                answers.add(t)
    value, adverse = max((min(a*t+b*(1-t) for _, a, b in ab), t) for t in answers)
    return value, adverse


def finite_upper(profiles, tau):
    """Exact adverse-mixture verification following a numerical LP solve."""
    success = [[int(p[i] <= tau) for p in profiles] for i in range(6)]
    M = np.array(success, dtype=float)
    solved = linprog(
        np.r_[np.zeros(6), 1.0],
        A_ub=np.c_[M.T, -np.ones(10)], b_ub=np.zeros(10),
        A_eq=[np.r_[np.ones(6), 0.0]], b_eq=[1.0],
        bounds=[(0, None)]*7, method="highs",
        options={"primal_feasibility_tolerance": 1e-9, "dual_feasibility_tolerance": 1e-9},
    )
    assert solved.success, solved.message
    weights = [F(float(max(0, x))).limit_denominator(1000000) for x in solved.x[:6]]
    mass = sum(weights)
    weights = [x/mass for x in weights]
    upper = max(sum(weights[i]*success[i][j] for i in range(6)) for j in range(10))
    assert abs(float(upper)-solved.fun) < 1e-9
    # The dual of the adverse-profile LP independently supplies a matching
    # primal mixture on the finite game. It does NOT prove a continuum lower bound.
    batch = [F(float(max(0, -x))).limit_denominator(1000000) for x in solved.ineqlin.marginals]
    bmass = sum(batch)
    batch = [x/bmass for x in batch]
    lower = min(sum(batch[j]*success[i][j] for j in range(10)) for i in range(6))
    assert lower == upper
    return upper, weights, batch


def half_cover(c, first, tau):
    intervals = []
    for j in range(1, 6):
        if j == first:
            continue
        a, b = conditional(c, first, j)
        lo, hi = F(0), F(1)
        if a == b:
            if b > tau:
                continue
        elif a > b:
            hi = min(hi, (tau-b)/(a-b))
        else:
            lo = max(lo, (tau-b)/(a-b))
        if lo <= hi:
            intervals.append((lo, hi, j))
    full = [v for v in intervals if v[:2] == (F(0), F(1))]
    if full:
        return [min(v[2] for v in full)]
    prefix = max((v for v in intervals if v[0] == 0), key=lambda v: (v[1], -v[2]))
    suffix = min((v for v in intervals if v[1] == 1), key=lambda v: (v[0], v[2]))
    assert prefix[1] >= suffix[0]
    return [prefix[2], suffix[2]]


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def counts(rows, field):
    keys = sorted({r[field] for r in rows})
    return [{field:k, "total":sum(r[field] == k for r in rows),
             **{name:sum(r[field] == k and r["class"] == name for r in rows) for name in CLASS_NAMES}}
            for k in keys]


def policy_summary(replay, groups):
    ans = []
    for name, ids in groups.items():
        grouped = defaultdict(list)
        for (case, policy), row in replay.items():
            if case in ids:
                grouped[policy].append(row)
        for policy, rows in sorted(grouped.items()):
            ans.append({"group":name, "policy":policy, "cases":len(rows),
                        **{m:sum(float(r[m]) for r in rows)/len(rows) for m in METRICS}})
    return ans


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--geometry", type=Path, nargs="+", required=True)
    p.add_argument("--replay", type=Path, nargs="+", required=True)
    p.add_argument("--output-dir", type=Path, default=HERE)
    args = p.parse_args()
    started = time.perf_counter()
    rows = []; plans = []; seen = set(); max_v_error = max_a_error = max_u_error = 0.0
    classification_mismatch = []; saved_batch_not_exact_optimal = []
    near_threshold = []
    for source in args.geometry:
        for case in json.loads(source.read_text(encoding="utf-8"))["cases"]:
            assert case["id"] not in seen
            seen.add(case["id"])
            c = [F.from_float(x) for x in case["c"]]
            initial_range = max(c)-min(c)
            assert initial_range > 0 and case["E"] > 0
            tau = initial_range/2
            profiles = [batch_profile(c, q) for q in BATCHES]
            worst = [max(v) for v in profiles]
            best = min(worst)
            envelopes = [worst_envelope(c, k)[0] for k in range(1, 6)]
            adaptive = min(envelopes)
            optimal_first = envelopes.index(adaptive)+1
            category = "batch_suffices" if best <= tau else ("feedback_required" if adaptive <= tau else "adaptive_not_guaranteed")
            upper, adverse, mixture = finite_upper(profiles, tau)
            assert (upper == 1) == (best <= tau)
            cover = half_cover(c, optimal_first, tau) if adaptive <= tau else []
            if category == "feedback_required":
                assert F(1, 2) <= upper < 1 and len(cover) == 2
            g = case["geometry"]
            saved = next(v for v in g["precision"] if v["fraction"] == .5)
            saved_class = "batch_suffices" if g["det_value"] <= .5 else ("feedback_required" if saved["adaptive_guarantee"] else "adaptive_not_guaranteed")
            if saved_class != category:
                classification_mismatch.append(case["id"])
            max_v_error = max(max_v_error, max(abs(float(profiles[j][i]/initial_range)-g["V"][i][j]) for i in range(6) for j in range(10)))
            max_a_error = max(max_a_error, abs(float(adaptive/initial_range)-g["A"]))
            max_u_error = max(max_u_error, abs(float(upper)-saved["upper"]))
            selected = g["det_batch_index"]
            if worst[selected] != best:
                saved_batch_not_exact_optimal.append({"id":case["id"], "difference":float((worst[selected]-best)/initial_range)})
            # The deployed hybrid reuses the recorded, prespecified deterministic
            # policy only if THAT policy is itself rationally certified at tau.
            hybrid_policy = "det_batch" if worst[selected] <= tau else "adaptive"
            if category == "batch_suffices":
                assert hybrid_policy == "det_batch"
                assert envelopes[g["first"]-1] <= tau
            if abs(float((best-tau)/initial_range)) < 1e-8 or abs(float((adaptive-tau)/initial_range)) < 1e-8:
                near_threshold.append(case["id"])
            plan = {"id":case["id"], "class":category, "threshold_over_W0":"1/2",
                    "recommendation":{"batch_suffices":"batch", "feedback_required":"adaptive", "adaptive_not_guaranteed":"escalate"}[category],
                    "best_batch_worst_over_W0_exact":str(best/initial_range),
                    "adaptive_worst_over_W0_exact":str(adaptive/initial_range)}
            if category == "batch_suffices":
                plan.update(query_hour_boundaries=list(BATCHES[selected]),
                            query_semantics="hours after this case's six-hour block start",
                            selected_batch_worst_over_W0_exact=str(worst[selected]/initial_range))
            elif category == "feedback_required":
                plan.update(first_query_hour_boundary=optimal_first,
                            second_query_rule="Choose (alpha*t + beta*(1-t), boundary) lexicographically minimum; t is the first retrieved prefix energy divided by the known six-hour total.",
                            second_query_lines=[{"boundary":j,"alpha_exact":str(a/initial_range),"beta_exact":str(b/initial_range)}
                                                for j in range(1,6) if j != optimal_first for a,b in [conditional(c,optimal_first,j)]],
                            continuum_batch_optimum_exact=str(upper),
                            constructive_half_cover_second_queries=cover)
            else:
                plan["action_scope"]="The two-query deterministic precision guarantee fails. Consider a larger budget or a different required precision; neither is evaluated here."
            plans.append(plan)
            rows.append({"id":case["id"], "meter":case["meter"], "day":case["day"], "phase":case["phase"],
                         "pair":case["model_a"]+" / "+case["model_b"], "start_hour":case["start_hour"],
                         "class":category, "best_batch_worst_over_W0":float(best/initial_range),
                         "adaptive_worst_over_W0":float(adaptive/initial_range),
                         "best_batch_worst_over_W0_exact":str(best/initial_range),
                         "adaptive_worst_over_W0_exact":str(adaptive/initial_range),
                         "implemented_adaptive_worst_over_W0_exact":str(envelopes[g["first"]-1]/initial_range),
                         "finite_profile_upper":float(upper), "finite_profile_upper_exact":str(upper),
                         "continuum_batch_success_exact":str(upper) if upper == 1 or (upper == F(1,2) and adaptive <= tau) else "not established",
                         "exact_adverse_weights":";".join(map(str, adverse)),
                         "finite_game_batch_weights":";".join(map(str, mixture)),
                         "finite_game_success_columns":";".join("".join(str(int(x <= tau)) for x in profile) for profile in profiles),
                         "fixed_query_hour_boundaries":";".join(map(str,BATCHES[selected])),
                         "first_query":optimal_first, "cover_second_queries":";".join(map(str,cover)),
                         "hybrid_policy":hybrid_policy})
    assert len(rows) == 4914
    # All geometry-based assignments are complete before opening replay data.
    replay = {}
    for source in args.replay:
        with source.open(newline="", encoding="utf-8") as file:
            for r in csv.DictReader(file):
                key = r["id"], r["policy"]
                assert key not in replay
                replay[key] = r
    assert len(replay) == len(rows)*5
    for r in rows:
        base = replay[r["id"], r["hybrid_policy"]].copy()
        base["policy"] = "post_analysis_hybrid"
        replay[r["id"], "post_analysis_hybrid"] = base
    groups = {"all":set(seen), **{n:{r["id"] for r in rows if r["class"] == n} for n in CLASS_NAMES},
              "exact_half":{r["id"] for r in rows if r["class"] == "feedback_required" and r["finite_profile_upper_exact"] == "1/2"}}
    for meter in sorted({r["meter"] for r in rows}):
        groups["feedback_required/"+meter] = {r["id"] for r in rows if r["meter"] == meter and r["class"] == "feedback_required"}
    summary = policy_summary(replay, groups)
    distribution = []
    for category in CLASS_NAMES:
        subset = [r for r in rows if r["class"] == category]
        for value, number in sorted(Counter(r["finite_profile_upper_exact"] for r in subset).items(), key=lambda item:F(item[0])):
            distribution.append({"class":category,"upper_exact":value,"cases":number})
    report = {
        "status":"PASS", "analysis_status":"post-analysis; threshold unchanged; no outcome-based geometry selection",
        "threshold":.5, "threshold_definition":"terminal width <= half initial width",
        "cases":len(rows), "counts":dict(Counter(r["class"] for r in rows)),
        "percentages":{name:100*sum(r["class"] == name for r in rows)/len(rows) for name in CLASS_NAMES},
        "batch_information_rounds":1, "adaptive_information_rounds":2, "readings_per_policy":2,
        "hybrid_feedback_cases":sum(r["hybrid_policy"] == "adaptive" for r in rows),
        "hybrid_precision_equivalence":{
            "status":"PASS", "cases_checked":len(rows),
            "statement":"For every feasible completion in each case, the hybrid and original adaptive policy have identical half-width success indicators: both guarantee success where the fixed batch is substituted, and they execute the identical adaptive rule elsewhere.",
            "unnecessary_feedback_cases":sum(r["hybrid_policy"] == "det_batch" for r in rows),
            "scope":"Preserves the precision-success indicator, not terminal width, winner certification, measured latency, or monetary costs."
        },
        "certified_feedback_required_cases":len(groups["feedback_required"]),
        "exact_half_cases":len(groups["exact_half"]),
        "by_meter":counts(rows,"meter"), "by_pair":counts(rows,"pair"), "by_phase":counts(rows,"phase"),
        "finite_profile_upper_distribution":distribution,
        "numerical_checks":{
            "rational_coefficients":"exact fractions of serialized binary64 original c coefficients",
            "batch_columns_checked":len(rows)*10, "first_query_envelopes_checked":len(rows)*5,
            "finite_games_with_exact_primal_dual_equality":len(rows),
            "max_saved_normalized_vertex_difference":max_v_error,
            "max_saved_adaptive_difference":max_a_error, "max_saved_finite_upper_difference":max_u_error,
            "saved_classification_mismatches":classification_mismatch,
            "saved_batch_not_exact_optimal_due_to_original_tie_tolerance":saved_batch_not_exact_optimal,
            "cases_with_any_optimum_within_1e-8_of_primary_threshold":near_threshold,
            "LP_primal_dual_tolerance":1e-9,
            "rational_adverse_mixture_checks":"nonnegative, unit mass, all ten batch columns, exact matching finite-game lower value",
        },
        "replay_summary":summary,
        "inputs":{str(p):digest(p) for p in [*args.geometry,*args.replay]},
        "analysis_code_sha256":digest(Path(__file__)),
        "limitations":[
            "A retrospective access-protocol replay, not measured retrieval time, monetary cost, or a field deployment.",
            "Only three meters; tasks and model-pair results are dependent.",
            "Feedback triage and the hybrid are post-analysis, not a prespecified confirmatory endpoint.",
            "A finite-profile upper bound below one proves no randomized batch guarantees success; values above one half are not claimed exact on the continuum.",
            "The last class refers to the deterministic adaptive worst-width optimum. No optimal subunit adaptive success probability is claimed.",
            "The original 10% prevalence screen for strong <=70% batch upper bounds remains unmet; this diagnostic does not redefine it.",
            "Avoiding the feedback round does not reduce the two-reading budget; hardware timing and transaction prices are unmeasured."
        ],
        "seconds":time.perf_counter()-started,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir/"case_ledger.csv",rows)
    write_csv(args.output_dir/"policy_summary.csv",summary)
    write_csv(args.output_dir/"batch_upper_distribution.csv",distribution)
    (args.output_dir/"recommendations.json").write_text(json.dumps({"scope":"post-analysis geometry-only prescriptions; threshold fixed at half initial width", "readings":2, "plans":plans},indent=2),encoding="utf-8")
    (args.output_dir/"report.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ["status","cases","counts","percentages","hybrid_feedback_cases","finite_profile_upper_distribution","seconds"]},indent=2))


if __name__ == "__main__":
    main()
