"""Paired meter-level description of the revised recovery experiment.

Run after study_recovery.py completes. The same 30 Portugal meter IDs are
resampled across policies and model-pair scopes; all within-meter days,
pairs and mask seeds remain aggregated. Intervals describe heterogeneity in
this convenience panel, not confidence about all electricity customers.
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
SEED = 280109
REPLICATES = 2000
GAP, BUDGET = 6, 2
SCOPE_FILES = {"all_pairs": "study_recovery.csv",
               "neural_pairs": "study_recovery_neural.csv"}
POLICIES = ("optimal_minimax_width", "random", "largest_absolute_contrast",
            "greedy_width_reduction", "contrast_weighted_sampling",
            "squared_contrast_weighted_sampling")
COMPARATORS = {"no_recovery": ("optimal_minimax_width", 0),
               "greedy": ("greedy_width_reduction", BUDGET),
               "absolute_weighted": ("contrast_weighted_sampling", BUDGET),
               "squared_weighted": ("squared_contrast_weighted_sampling", BUDGET)}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def interval(values, samples):
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("A bootstrap vector contains a nonfinite value")
    estimate = float(values.mean())
    limits = np.quantile(values[samples].mean(axis=1), [0.025, 0.975])
    return {"mean": estimate, "percentile95": limits.tolist(),
            "mean_percent_or_percentage_points": estimate * 100,
            "percentile95_percent_or_percentage_points": (100 * limits).tolist()}


def select(frame, cohort, policy, budget):
    selected = frame[(frame.cohort == cohort) & (frame.gap_hours == GAP)
                     & (frame.policy == policy) & (frame.budget == budget)]
    if selected.meter.duplicated().any():
        raise ValueError("Duplicate meter/scenario row")
    return selected.set_index("meter").sort_index()


def validate_frame(frame, scope, main):
    key = ["cohort", "meter", "gap_hours", "budget", "policy"]
    assert not frame.duplicated(key).any()
    assert set(frame.policy) == set(POLICIES)
    assert set(frame.budget) == {0, 1, 2, 3}
    assert set(frame.gap_hours) == {6, 12}
    assert (frame.wrong_decisions == 0).all()
    assert (frame.pair_trials > 0).all()
    assert (frame.enclosed_truth == frame.pair_trials).all()
    np.testing.assert_allclose(frame.resolved_fraction,
                               frame.decisions / frame.pair_trials, rtol=1e-12)
    positive = frame.mean_initial_width > 0
    np.testing.assert_allclose(
        frame.loc[positive, "actual_width_fraction"],
        frame.loc[positive, "mean_actual_remaining_width"] /
        frame.loc[positive, "mean_initial_width"], rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(
        frame.loc[positive, "worst_case_width_fraction"],
        frame.loc[positive, "mean_worst_case_remaining_width"] /
        frame.loc[positive, "mean_initial_width"], rtol=1e-9, atol=1e-12)
    expected_pairs = 6 if scope == "all_pairs" else 3
    per_meter_days = {(m["cohort"], m["meter"]): m["test_days"]
                      for m in main["meters"]}
    for row in frame.itertuples(index=False):
        assert row.pair_trials == per_meter_days[(row.cohort, row.meter)] * 3 * expected_pairs


def main():
    filenames = list(SCOPE_FILES.values()) + ["study_recovery.json", "study_summary.json"]
    hashes = {name: digest(OUT / name) for name in filenames}
    summary = json.loads((OUT / "study_summary.json").read_text(encoding="utf-8"))
    recovery = json.loads((OUT / "study_recovery.json").read_text(encoding="utf-8"))
    assert "mlp" in summary["design"]["models"], "Expected fresh neural revision"
    assert recovery["main_study_script_sha256"] == summary["script_sha256"]
    assert recovery["hashes"]["study_summary.json"] == hashes["study_summary.json"]
    for filename in SCOPE_FILES.values():
        assert recovery["hashes"][filename] == hashes[filename]
    frames = {scope: pd.read_csv(OUT / filename)
              for scope, filename in SCOPE_FILES.items()}
    for scope, frame in frames.items():
        validate_frame(frame, scope, summary)
    meter_ids = select(frames["all_pairs"], "portugal", "optimal_minimax_width", BUDGET).index
    assert len(meter_ids) == 30
    resamples = np.random.default_rng(SEED).integers(0, len(meter_ids),
                                                   (REPLICATES, len(meter_ids)))
    outputs = {}
    for scope, frame in frames.items():
        optimal = select(frame, "portugal", "optimal_minimax_width", BUDGET)
        assert optimal.index.equals(meter_ids)
        assert (optimal.mean_initial_width > 0).all(), "Undefined width ratio"
        estimates = {}
        for name, (policy, budget) in COMPARATORS.items():
            comparison = select(frame, "portugal", policy, budget)
            assert comparison.index.equals(meter_ids)
            np.testing.assert_array_equal(optimal.pair_trials, comparison.pair_trials)
            np.testing.assert_allclose(optimal.mean_initial_width,
                                       comparison.mean_initial_width, rtol=1e-12)
            estimates["optimal_minus_" + name] = interval(
                (optimal.resolved_fraction - comparison.resolved_fraction).to_numpy(),
                resamples)
        zero = select(frame, "portugal", "optimal_minimax_width", 0)
        output = {
            "meters": len(meter_ids),
            "dependent_pair_trials": int(optimal.pair_trials.sum()),
            "resolution_at_zero_budget": interval(zero.resolved_fraction, resamples),
            "optimal_resolution_at_budget2": interval(optimal.resolved_fraction, resamples),
            "resolution_differences": estimates,
            "actual_remaining_width_fraction": interval(optimal.actual_width_fraction, resamples),
            "worst_case_remaining_width_fraction": interval(optimal.worst_case_width_fraction, resamples),
            "actual_width_reduction_fraction": interval(1 - optimal.actual_width_fraction, resamples),
            "worst_case_width_reduction_fraction": interval(1 - optimal.worst_case_width_fraction, resamples),
            "per_meter_paired_differences": [
                {"meter": meter, **{name: float(
                    optimal.loc[meter, "resolved_fraction"] -
                    select(frame, "portugal", policy, budget).loc[meter, "resolved_fraction"])
                    for name, (policy, budget) in COMPARATORS.items()}}
                for meter in meter_ids],
        }
        outputs[scope] = output
    descriptive = []
    for scope, frame in frames.items():
        for cohort in sorted(frame.cohort.unique()):
            for policy, budget in [("optimal_minimax_width", 0)] + [(p, BUDGET) for p in POLICIES]:
                rows = select(frame, cohort, policy, budget)
                positive = rows[rows.mean_initial_width > 0]
                descriptive.append({
                    "scope": scope, "cohort": cohort, "policy": policy, "budget": budget,
                    "meters": len(rows), "dependent_pair_trials": int(rows.pair_trials.sum()),
                    "macro_resolution_fraction": float(rows.resolved_fraction.mean()),
                    "macro_actual_remaining_width_fraction": float(positive.actual_width_fraction.mean()),
                    "macro_worst_case_remaining_width_fraction": float(positive.worst_case_width_fraction.mean()),
                    "meters_with_zero_initial_width": int(len(rows) - len(positive)),
                    "mean_queries": float(rows.mean_queries.mean()),
                    "wrong_decisions": int(rows.wrong_decisions.sum()),
                })
    # Cross-scope counts: the three MLP pairs are half of the full six pairs.
    for cohort in sorted(frames["all_pairs"].cohort.unique()):
        all_rows = select(frames["all_pairs"], cohort, "optimal_minimax_width", BUDGET)
        ai_rows = select(frames["neural_pairs"], cohort, "optimal_minimax_width", BUDGET)
        assert all_rows.index.equals(ai_rows.index)
        np.testing.assert_array_equal(all_rows.pair_trials, 2 * ai_rows.pair_trials)
    for name, before in hashes.items():
        assert digest(OUT / name) == before, "Input changed during postanalysis"
    report = {
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": {"gap_hours": GAP, "total_block_hours": 6, "total_tolerance": 0,
                     "mask": "contiguous", "budget": BUDGET},
        "bootstrap": {"seed": SEED, "replicates": REPLICATES, "unit": "meter",
                      "method": "paired percentile bootstrap of macro-mean meter summaries",
                      "scope_alignment": "same resampled meter positions for both pair scopes and all policies",
                      "scope_warning": "Descriptive for this convenience panel; within-meter dependence retained; cross-meter dependence not modeled; no population-wide confidence claim"},
        "width_aggregation": "For each meter, total remaining width / total initial width across its dependent trials, then equal-weight mean over meters with positive initial width",
        "resolution_aggregation": "Equal-weight mean over meter-level resolved fractions",
        "pair_scopes": {"all_pairs": "all six pairs among four models",
                        "neural_pairs": "the three pairs containing the fixed MLP"},
        "portugal": outputs, "cohort_descriptions": descriptive,
        "source_hashes": hashes,
        "analysis_script_sha256": digest(__file__),
    }
    destination = OUT / "ai_recovery_analysis.json"
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({scope: report["portugal"][scope]["resolution_differences"]
                      for scope in SCOPE_FILES}, indent=2))


if __name__ == "__main__":
    main()
