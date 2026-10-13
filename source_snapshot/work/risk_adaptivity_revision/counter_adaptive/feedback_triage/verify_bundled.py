"""Verify the bundled feedback-triage ledger and algebraic policy certificates.

This does not regenerate forecast geometry or reopen fine meter answers.
Use analyze.py with regenerated geometry/replay for that independent calculation.
"""
import argparse
from collections import Counter
import csv
from fractions import Fraction as F
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=HERE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with (args.input_dir/"case_ledger.csv").open(newline="",encoding="utf-8") as f:
        cases = list(csv.DictReader(f))
    report = json.loads((args.input_dir/"report.json").read_text())
    plans = json.loads((args.input_dir/"recommendations.json").read_text())["plans"]
    plans = {p["id"]:p for p in plans}
    assert len(cases) == len(plans) == len({r["id"] for r in cases}) == 4914
    histogram = Counter(); distributions = Counter(); max_policy_error = F(0)
    for r in cases:
        d, a, upper = map(F,[r["best_batch_worst_over_W0_exact"],r["adaptive_worst_over_W0_exact"],r["finite_profile_upper_exact"]])
        category = "batch_suffices" if d <= F(1,2) else ("feedback_required" if a <= F(1,2) else "adaptive_not_guaranteed")
        assert r["class"] == category and a <= d
        histogram[category] += 1
        distributions[category,str(upper)] += 1
        adverse = list(map(F,r["exact_adverse_weights"].split(";")))
        mixture = list(map(F,r["finite_game_batch_weights"].split(";")))
        columns = [[int(bit) for bit in text] for text in r["finite_game_success_columns"].split(";")]
        assert len(adverse) == 6 and len(mixture) == len(columns) == 10
        assert min(adverse) >= 0 and min(mixture) >= 0 and sum(adverse) == sum(mixture) == 1
        assert all(len(c) == 6 and set(c) <= {0,1} for c in columns)
        bound = max(sum(x*w for x,w in zip(c,adverse)) for c in columns)
        lower = min(sum(columns[j][i]*mixture[j] for j in range(10)) for i in range(6))
        assert lower == upper == bound
        assert (upper == 1) == (category == "batch_suffices")
        plan = plans[r["id"]]
        assert plan["class"] == category
        assert F(plan["best_batch_worst_over_W0_exact"]) == d
        assert F(plan["adaptive_worst_over_W0_exact"]) == a
        if category == "batch_suffices":
            assert plan["recommendation"] == "batch"
            assert len(set(plan["query_hour_boundaries"])) == 2
            assert all(1 <= q <= 5 for q in plan["query_hour_boundaries"])
            assert F(plan["selected_batch_worst_over_W0_exact"]) <= F(1,2)
            assert F(r["implemented_adaptive_worst_over_W0_exact"]) <= F(1,2)
            assert r["hybrid_policy"] == "det_batch"
        elif category == "feedback_required":
            assert plan["recommendation"] == "adaptive" and upper == F(1,2)
            assert plan["continuum_batch_optimum_exact"] == r["continuum_batch_success_exact"] == "1/2"
            k = plan["first_query_hour_boundary"]
            lines = [(z["boundary"],F(z["alpha_exact"]),F(z["beta_exact"])) for z in plan["second_query_lines"]]
            assert {z[0] for z in lines} == set(range(1,6))-{k}
            candidates = {F(0),F(1)}
            for (_,x,y),(_,xx,yy) in itertools.combinations(lines,2):
                slope = x-y-xx+yy
                if slope:
                    t = (yy-y)/slope
                    if 0 <= t <= 1:
                        candidates.add(t)
            envelope = max(min(x*t+y*(1-t) for _,x,y in lines) for t in candidates)
            assert envelope == a <= F(1,2)
            cover = plan["constructive_half_cover_second_queries"]
            assert len(set(cover)) == 2
            intervals = []
            for j,x,y in lines:
                if j not in cover:
                    continue
                left,right = F(0),F(1)
                if x == y:
                    assert y <= F(1,2)
                elif x > y:
                    right = min(right,(F(1,2)-y)/(x-y))
                else:
                    left = max(left,(F(1,2)-y)/(x-y))
                assert 0 <= left <= right <= 1
                intervals.append((left,right))
            intervals.sort()
            assert intervals[0][0] == 0 and intervals[-1][1] == 1 and intervals[0][1] >= intervals[1][0]
        else:
            assert plan["recommendation"] == "escalate" and a > F(1,2)
            assert r["continuum_batch_success_exact"] == "not established"
        if category != "batch_suffices":
            assert r["hybrid_policy"] == "adaptive"
    assert histogram == Counter(report["counts"]) == Counter(batch_suffices=4371,feedback_required=290,adaptive_not_guaranteed=253)
    assert report["hybrid_precision_equivalence"]["status"] == "PASS"
    assert report["hybrid_precision_equivalence"]["unnecessary_feedback_cases"] == 4371
    for row in report["finite_profile_upper_distribution"]:
        assert distributions[row["class"],row["upper_exact"]] == row["cases"]
    assert report["numerical_checks"]["saved_classification_mismatches"] == []
    with (args.input_dir/"policy_summary.csv").open(newline="",encoding="utf-8") as f:
        summaries = {(r["group"],r["policy"]):r for r in csv.DictReader(f)}
    assert float(summaries["feedback_required","adaptive"]["success_0.5"]) == 1
    assert abs(float(summaries["feedback_required","det_batch"]["success_0.5"])-282/290) < 1e-12
    assert float(summaries["all","post_analysis_hybrid"]["success_0.5"]) == float(summaries["all","adaptive"]["success_0.5"])
    result = {"status":"PASS","cases":len(cases),"counts":dict(histogram),
              "finite_games_verified_exactly":len(cases),"adaptive_policy_envelopes_and_half_covers_verified_exactly":histogram["feedback_required"],
              "hybrid_pointwise_precision_equivalence_cases_verified":len(cases),
              "scope":"Bundled triage ledger, exact rational finite-game primal/dual certificates, policy recommendations and adaptive envelope/half-cover algebra; does not reconstruct source coefficients or replay raw readings."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
