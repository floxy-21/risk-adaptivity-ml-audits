"""Exploratory reviewer-requested comparisons of exact and greedy recovery.

Run only after study_recovery.py commits its final summary. This describes
dependent historical cases; no p-values, IID trial intervals, or superiority
claim for actual resolution follow from the worst-case-width objective.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
CASE = "study_recovery_cases.csv"
DETAIL = "study_recovery_pair_seed.csv"
OPT, GREEDY = "optimal_minimax_width", "greedy_width_reduction"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def distribution(values, tolerance=1e-10):
    values = np.asarray(values, dtype=float)
    assert np.isfinite(values).all()
    if not len(values):
        return {"n": 0}
    return {"n": len(values), "mean": float(values.mean()),
            "quantiles": dict(zip(["min", "p10", "p25", "median", "p75", "p90", "max"],
                                  np.quantile(values, [0, .1, .25, .5, .75, .9, 1]).tolist())),
            "positive": int((values > tolerance).sum()),
            "zero_within_tolerance": int((np.abs(values) <= tolerance).sum()),
            "negative": int((values < -tolerance).sum()), "sign_tolerance": tolerance}


def summarize_units(rows, keys):
    units = rows.groupby(keys, sort=True).agg(
        cases=("initial_width", "size"), before_resolved=("before_resolved", "sum"),
        optimal_resolved=("optimal_resolved", "sum"), greedy_resolved=("greedy_resolved", "sum"),
        initial_width=("initial_width", "sum"),
        optimal_actual_width=("optimal_actual_width", "sum"),
        greedy_actual_width=("greedy_actual_width", "sum"),
        optimal_worst_width=("optimal_worst_width", "sum"),
        greedy_worst_width=("greedy_worst_width", "sum"),
        optimal_queries=("optimal_query_count", "sum"),
        greedy_queries=("greedy_query_count", "sum"))
    positive = units.initial_width > 0
    return {"number_of_units": len(units),
            "units_with_zero_initial_width": int((~positive).sum()),
            "resolution_gain_optimal_minus_greedy": distribution(
                (units.optimal_resolved - units.greedy_resolved) / units.cases),
            "resolution_gain_optimal_minus_no_recovery": distribution(
                (units.optimal_resolved - units.before_resolved) / units.cases),
            "normalized_worst_width_improvement_greedy_minus_optimal": distribution(
                (units.loc[positive, "greedy_worst_width"] -
                 units.loc[positive, "optimal_worst_width"]) / units.loc[positive, "initial_width"]),
            "normalized_actual_width_improvement_greedy_minus_optimal": distribution(
                (units.loc[positive, "greedy_actual_width"] -
                 units.loc[positive, "optimal_actual_width"]) / units.loc[positive, "initial_width"]),
            "mean_queries_optimal_minus_greedy": distribution(
                (units.optimal_queries - units.greedy_queries) / units.cases)}


def describe(rows):
    opt, greedy = rows.optimal_resolved, rows.greedy_resolved
    positive = rows.initial_width > 0
    unresolved = rows[~rows.before_resolved]
    uopt, ug = unresolved.optimal_resolved, unresolved.greedy_resolved
    return {"dependent_cases": len(rows), "meters": int(rows.meter.nunique()),
            "both_resolved": int((opt & greedy).sum()),
            "optimal_only_resolved": int((opt & ~greedy).sum()),
            "greedy_only_resolved": int((~opt & greedy).sum()),
            "neither_resolved": int((~opt & ~greedy).sum()),
            "pooled_before_resolution": float(rows.before_resolved.mean()),
            "pooled_optimal_resolution": float(opt.mean()),
            "pooled_greedy_resolution": float(greedy.mean()),
            "initially_unresolved_conditional_view": {
                "dependent_cases": len(unresolved),
                "optimal_resolved": int(uopt.sum()), "greedy_resolved": int(ug.sum()),
                "optimal_only_resolved": int((uopt & ~ug).sum()),
                "greedy_only_resolved": int((~uopt & ug).sum()),
                "pooled_optimal_resolution": float(uopt.mean()) if len(unresolved) else None,
                "pooled_greedy_resolution": float(ug.mean()) if len(unresolved) else None,
                "scope": "Conditioned only on the original audit being unresolved; supplementary to all-case results"},
            "case_distribution": {
                "resolution_gain_optimal_minus_greedy": distribution(opt.astype(int) - greedy.astype(int)),
                "normalized_worst_width_improvement_greedy_minus_optimal": distribution(
                    (rows.loc[positive, "greedy_worst_width"] - rows.loc[positive, "optimal_worst_width"]) /
                    rows.loc[positive, "initial_width"]),
                "normalized_actual_width_improvement_greedy_minus_optimal": distribution(
                    (rows.loc[positive, "greedy_actual_width"] - rows.loc[positive, "optimal_actual_width"]) /
                    rows.loc[positive, "initial_width"]),
                "queries_optimal_minus_greedy": distribution(rows.optimal_query_count - rows.greedy_query_count),
                "cases_with_zero_initial_width": int((~positive).sum())},
            "meter_distribution": summarize_units(rows, ["meter"]),
            "meter_seed_distribution": summarize_units(rows, ["meter", "mask_seed"])}


def main():
    inputs = [CASE, DETAIL, "study_recovery.json", "study_summary.json"]
    hashes = {name: digest(OUT / name) for name in inputs}
    recovery = json.loads((OUT / "study_recovery.json").read_text(encoding="utf-8"))
    main_summary = json.loads((OUT / "study_summary.json").read_text(encoding="utf-8"))
    assert "mlp" in main_summary["design"]["models"]
    for name in [CASE, DETAIL, "study_summary.json"]:
        assert recovery["hashes"][name] == hashes[name], f"Stale {name}"
    assert recovery["main_study_script_sha256"] == main_summary["script_sha256"]
    rows = pd.read_csv(OUT / CASE)
    detail = pd.read_csv(OUT / DETAIL)
    unique = ["cohort", "meter", "day", "model_a", "model_b", "mask_seed", "gap_hours"]
    assert not rows.duplicated(unique).any()
    assert set(rows.gap_hours) == {6, 12}
    assert set(rows.mask_seed) == {1103, 2207, 3301}
    assert rows.select_dtypes(include=["number"]).apply(np.isfinite).all().all()
    assert (rows.initial_width >= 0).all()
    tolerance = 1e-8 * np.maximum(1., rows.initial_width.to_numpy())
    assert np.all(rows.optimal_worst_width <= rows.greedy_worst_width + tolerance)
    for prefix in ["before", "optimal", "greedy"]:
        assert set(rows[prefix + "_decision"].unique()).issubset({-1, 0, 1})
        rows[prefix + "_resolved"] = rows[prefix + "_decision"] != 0
        assert np.all(rows[prefix + "_lower"] <= rows.reference_gap + tolerance)
        assert np.all(rows[prefix + "_upper"] >= rows.reference_gap - tolerance)
    for prefix in ["optimal", "greedy"]:
        assert rows[prefix + "_query_count"].between(0, 2).all()
        assert np.all(rows[prefix + "_actual_width"] <= rows[prefix + "_worst_width"] + tolerance)
    # Independent cross-file aggregation catches dropped cases and mismatched seeds.
    keys = ["cohort", "meter", "model_a", "model_b", "mask_seed", "gap_hours"]
    for prefix, policy in [("optimal", OPT), ("greedy", GREEDY)]:
        calc = rows.groupby(keys).agg(pair_trials=("initial_width", "size"),
                                      decisions=(prefix + "_resolved", "sum"),
                                      initial=("initial_width", "mean"),
                                      actual=(prefix + "_actual_width", "mean"),
                                      worst=(prefix + "_worst_width", "mean"),
                                      queries=(prefix + "_query_count", "mean")).sort_index()
        expected = detail[(detail.policy == policy) & (detail.budget == 2)].set_index(keys).sort_index()
        assert calc.index.equals(expected.index)
        np.testing.assert_array_equal(calc.pair_trials, expected.pair_trials)
        np.testing.assert_array_equal(calc.decisions, expected.decisions)
        for lhs, rhs in [("initial", "mean_initial_width"), ("actual", "mean_actual_remaining_width"),
                         ("worst", "mean_worst_case_remaining_width"), ("queries", "mean_queries")]:
            np.testing.assert_allclose(calc[lhs], expected[rhs], rtol=1e-9, atol=1e-8)
    outputs = []
    for (cohort, gap), subset in rows.groupby(["cohort", "gap_hours"], sort=True):
        scopes = {"all_pairs": subset,
                  "neural_pairs": subset[(subset.model_a == "mlp") | (subset.model_b == "mlp")]}
        scopes.update({"pair:" + a + ":" + b: group
                       for (a, b), group in subset.groupby(["model_a", "model_b"], sort=True)})
        for scope, group in scopes.items():
            outputs.append({"cohort": cohort, "gap_hours": int(gap), "scope": scope, **describe(group)})
    for name, original in hashes.items():
        assert digest(OUT / name) == original, "Input changed during analysis"
    report = {"completed_utc": datetime.now(timezone.utc).isoformat(),
              "status": "Exploratory reviewer-requested diagnostic, specified after the earlier nonneural study",
              "scenario": {"gap_hours": [6, 12], "budget": 2, "total_block_hours": 6,
                           "total_tolerance": 0, "mask": "contiguous"},
              "signs": "Positive resolution difference favors exact selection; positive width improvement is greedy width minus exact width, normalized by initial width. Query difference is exact minus greedy; negative means fewer exact queries.",
              "unit_warning": "Cases and meter-seed summaries are dependent descriptive observations, not independent replicates. Meter distributions equally weight meters; pooled fractions equally weight cases. Width ratios use summed widths within each aggregate unit; zero initial-width units are excluded only from ratios.",
              "scope_warning": "The optimized objective is worst-case remaining width. Actual width and strict ranking resolution need not improve over greedy on each historical target.",
              "groups": outputs, "source_hashes": hashes,
              "analysis_script_sha256": digest(__file__)}
    (OUT / "recovery_diagnostics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for group in outputs:
        if group["gap_hours"] == 6 and group["scope"] in ["all_pairs", "neural_pairs"]:
            print(json.dumps({k: group[k] for k in ["cohort", "scope", "dependent_cases", "optimal_only_resolved", "greedy_only_resolved", "meter_distribution"]}))


if __name__ == "__main__":
    main()
