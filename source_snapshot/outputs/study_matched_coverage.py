"""Descriptive matched-coverage analysis of completed whole-record comparisons.

Run after the main study: python outputs/study_matched_coverage.py
The point-method ranking uses estimated margins and a training-only energy
scale, never complete-reference losses. This batch comparison is not a
calibration procedure or a guarantee about future confidence or outcomes.
"""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
BASELINES = ["complete_case", "uniform", "seasonal_profile", "historical_donor"]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def key(row):
    return row["meter"], row["model_a"], row["model_b"], int(row["seed"])


def main():
    source = OUT / "study_period_comparisons.csv"
    summary_file = OUT / "study_summary.json"
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    source_hash = digest(source)
    assert summary.get("completed_utc"), "Wait for the completed main study"
    expected_hash = summary["artifacts"][source.name]["sha256"]
    assert source_hash == expected_hash, "Period CSV differs from completed-study hash"
    scales = {(m["cohort"], m["meter"]): max(m["training_mean_kwh"] ** 2, 1e-12)
              for m in summary["meters"]}
    groups = defaultdict(lambda: defaultdict(list))
    with source.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if float(row["total_tolerance"]) != 0:
                continue
            method = row["method"]
            if method not in ["paired_bounds", *BASELINES]:
                continue
            group = (row["cohort"], int(row["gap_hours"]), row["pattern"],
                     int(row["block_hours"]), 0.0)
            groups[group][method].append(row)

    records = []
    totals = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for group, methods in sorted(groups.items()):
        cohort, gap, pattern, block, tau = group
        paired = methods["paired_bounds"]
        paired_by_key = {key(r): r for r in paired}
        assert len(paired_by_key) == len(paired), "Duplicate primary comparison"
        n = len(paired)
        target = sum(int(r["decision"]) != 0 for r in paired)
        paired_wrong = sum(int(r["wrong_decision"]) for r in paired)
        for method in BASELINES:
            candidates = methods[method]
            assert len(candidates) == n
            assert {key(r) for r in candidates} == set(paired_by_key)
            for r in candidates:
                assert abs(float(r["mean_lower_or_point"]) - float(r["mean_upper_or_point"])) <= 1e-10
                assert abs(float(r["true_mean_gap"]) - float(paired_by_key[key(r)]["true_mean_gap"])) <= 1e-10
            # Strict ties remain abstentions; an exact requested coverage may
            # therefore be unavailable, which is reported instead of hidden.
            eligible = [r for r in candidates if int(r["decision"]) != 0]
            ranked = sorted(eligible, key=lambda r: (
                -abs(float(r["mean_lower_or_point"])) / scales[(cohort, r["meter"])],
                *key(r)))
            selected = ranked[:target]
            wrong = sum(int(r["wrong_decision"]) for r in selected)
            matching = sum(int(paired_by_key[key(r)]["decision"]) == int(r["decision"])
                           for r in selected)
            unresolved = sum(int(paired_by_key[key(r)]["decision"]) == 0 for r in selected)
            opposite = len(selected) - matching - unresolved
            assert matching + unresolved + opposite == len(selected)
            threshold = (abs(float(selected[-1]["mean_lower_or_point"]))
                         / scales[(cohort, selected[-1]["meter"])]) if selected else None
            rec = {
                "cohort": cohort, "gap_hours": gap, "pattern": pattern,
                "block_hours": block, "total_tolerance": tau, "method": method,
                "comparisons": n, "paired_decisions": target,
                "paired_coverage": target / n, "paired_wrong_decisions": paired_wrong,
                "baseline_available_decisions": len(eligible),
                "selected_decisions": len(selected), "selected_coverage": len(selected) / n,
                "coverage_exactly_matched": len(selected) == target,
                "wrong_decisions": wrong,
                "error_among_selected": wrong / len(selected) if selected else None,
                "minimum_selected_normalized_margin": threshold,
                "baseline_all_decisions_wrong": sum(int(r["wrong_decision"]) for r in eligible),
                "selected_with_matching_paired_certificate": matching,
                "selected_paired_unresolved": unresolved,
                "selected_with_opposite_certificate": opposite,
                "fraction_matching_paired_certificate": matching / len(selected) if selected else None,
                "fraction_paired_unresolved": unresolved / len(selected) if selected else None,
                "fraction_opposite_certificate": opposite / len(selected) if selected else None,
            }
            records.append(rec)
            t = totals[cohort][method]
            for outkey, value in [
                ("comparisons", n), ("paired_decisions", target),
                ("paired_wrong_decisions", paired_wrong),
                ("selected_decisions", len(selected)), ("wrong_decisions", wrong),
                ("baseline_available_decisions", len(eligible)),
                ("baseline_all_decisions_wrong", rec["baseline_all_decisions_wrong"]),
                ("selected_with_matching_paired_certificate", matching),
                ("selected_paired_unresolved", unresolved),
                ("selected_with_opposite_certificate", opposite),
                ("groups", 1), ("groups_with_exact_match", int(len(selected) == target))]:
                t[outkey] += value
    for methods in totals.values():
        for t in methods.values():
            t["paired_coverage"] = t["paired_decisions"] / t["comparisons"]
            t["selected_coverage"] = t["selected_decisions"] / t["comparisons"]
            t["error_among_selected"] = t["wrong_decisions"] / t["selected_decisions"] if t["selected_decisions"] else None
            for fraction, count in [
                ("fraction_matching_paired_certificate", "selected_with_matching_paired_certificate"),
                ("fraction_paired_unresolved", "selected_paired_unresolved"),
                ("fraction_opposite_certificate", "selected_with_opposite_certificate")]:
                t[fraction] = t[count] / t["selected_decisions"] if t["selected_decisions"] else None

    with (OUT / "study_matched_coverage.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    result = {
        "description": "Whole-record point-method comparison at the paired method's scenario-specific coverage.",
        "setting": "Exact totals only; separate cohort/gap/pattern/block groups; same seed/pair/meter universe.",
        "selection_score": "Absolute estimated point MSE difference divided by squared training-mean hourly kWh.",
        "tie_break": "Ascending meter, model_a, model_b, integer seed.",
        "oracle_use": "Complete-reference outcomes only assess selected decisions; they do not rank or set the selection threshold.",
        "scope": "Descriptive batch selective evaluation; no calibrated confidence, independent-trial inference, or future-risk claim.",
        "dependence": "Seeds/model pairs/scenarios are dependent; deterministic high-demand masks repeat across seeds as in main design.",
        "certificate_overlap": "Among each baseline's selected comparisons, counts distinguish matching paired certificate, paired unresolved, and opposite paired certificate. Unresolved means lacking a strict certificate under the same numerical decision rule, not an observed error or necessarily an opposite feasible ordering.",
        "source_period_sha256": source_hash,
        "source_summary_sha256": digest(summary_file),
        "script_sha256": digest(Path(__file__)),
        "python": platform.python_version(),
        "rows": len(records), "cohorts": totals,
    }
    (OUT / "study_matched_coverage.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
