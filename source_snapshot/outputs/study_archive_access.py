"""Post-review sensitivity to access to the saved test persistence archive.

Only aggregate results are written. The local target archive is never modified.
Free reconstruction accepts forecast timestamps and values, not hidden targets.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from study_recovery import (prepare_blocks, optimal_queries, baseline_queries,
                            pair_interval, decision, worst_width)
from run_energy_rank_study import daily_design

ROOT = Path(__file__).resolve().parents[1]
OUT, WORK = ROOT / "outputs", ROOT / "work"
DAY_NS = 86400000000000
GAPS = (6, 12)
SEEDS = (1103, 2207, 3301)
BUDGETS = (0, 2)
POLICIES = ("optimal_minimax_width", "greedy_width_reduction")
REGIMES = ("restricted_record", "available_test_persistence_archive")
METRIC_NAMES = ("pair_trials", "decisions", "wrong_decisions", "enclosed_truth",
                "initial_width_sum", "actual_width_sum", "worst_width_sum",
                "queries_sum", "original_missing_sum", "free_revealed_sum")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def persistence_lookup(visible_forecasts):
    """Map past target timestamp to its future saved persistence prediction.

    Requiring this exact schema makes passing the truth column an error.
    The caller supplies data for one meter only. No raw-data fallback exists.
    """
    if list(visible_forecasts.columns) != ["timestamp", "daily"]:
        raise ValueError("The reconstruction interface accepts timestamp and daily only")
    if visible_forecasts.timestamp.duplicated().any():
        raise ValueError("Duplicate archive timestamps")
    result = {}
    for timestamp, value in visible_forecasts.itertuples(index=False, name=None):
        time_ns = pd.Timestamp(timestamp).value
        value = float(value)
        if not np.isfinite(value) or value < 0:
            raise ValueError("Invalid archived daily-persistence prediction")
        result[time_ns - DAY_NS] = (time_ns, value)
    return result


def reveal_from_archive(timestamps, observed, lookup):
    """Add verified-pipeline persistence copies; never receive hidden truths."""
    revealed = np.array(observed, dtype=float, copy=True)
    found = []
    for i, timestamp in enumerate(timestamps):
        if np.isfinite(revealed[i]):
            continue
        source = lookup.get(pd.Timestamp(timestamp).value)
        if source is not None:
            future, value = source
            assert future - pd.Timestamp(timestamp).value == DAY_NS
            revealed[i] = value
            found.append(i)
    return revealed, tuple(found)


def choose_queries(a, b, observed, totals, budget, policy):
    """Evaluator-only interface; complete targets are not an argument."""
    blocks = prepare_blocks(2.0 * (b - a) / len(a), observed, totals)
    query = (optimal_queries(blocks, budget) if policy == POLICIES[0] else
             baseline_queries(blocks, budget, policy))
    assert len(query) <= budget
    assert all(np.isnan(observed[i]) for i in query)
    return query, worst_width(blocks, query)


def self_checks():
    # A saved forecast at day D+1 reveals D even when no truth column exists.
    tiny = pd.DataFrame({"timestamp": ["2020-01-02T03:00:00"], "daily": [7.0]})
    lookup = persistence_lookup(tiny)
    visible, indices = reveal_from_archive(["2020-01-01T03:00:00"], [np.nan], lookup)
    assert indices == (0,) and visible[0] == 7.0
    absent, indices = reveal_from_archive(["2020-01-03T03:00:00"], [np.nan], lookup)
    assert not indices and np.isnan(absent[0])
    try:
        persistence_lookup(tiny.assign(truth_kwh=999.0))
    except ValueError:
        pass
    else:
        raise AssertionError("Hidden-truth schema was accepted")
    # Check the actual feature constructor's first feature is an exact day lag.
    series = pd.Series(np.arange(24 * 12, dtype=float) + 1,
                       index=pd.date_range("2020-01-01", periods=24 * 12, freq="h"))
    days, features, targets, eligible = daily_design(series)
    np.testing.assert_array_equal(features[1:, :, 0], targets[:-1])
    # Distinct hidden completions with the same visible data yield the same batch.
    a = np.array([0., 1., 3., 2., 5., 1.])
    b = np.array([2., 0., 2., 6., 1., 4.])
    hidden1 = np.array([1., 2., 3., 4., 5., 6.])
    hidden2 = hidden1[::-1].copy()
    assert hidden1.sum() == hidden2.sum()
    observed1, observed2 = np.full(6, np.nan), np.full(6, np.nan)
    for policy in POLICIES:
        one = choose_queries(a, b, observed1, [hidden1.sum()], 2, policy)
        two = choose_queries(a, b, observed2, [hidden2.sum()], 2, policy)
        assert one == two
    return {"timestamp_only_lookup": True, "missing_future_row_not_filled": True,
            "hidden_truth_column_rejected": True, "causal_lag24_feature_identity": True,
            "same_visible_information_query_invariance": True}


def format_row(keys, values):
    cohort, meter, gap, seed, model_a, model_b, regime, budget, policy = keys
    raw = dict(zip(METRIC_NAMES, map(float, values)))
    n = int(raw["pair_trials"])
    row = {"cohort": cohort, "meter": meter, "gap_hours": gap,
           "mask_seed": seed, "model_a": model_a, "model_b": model_b,
           "regime": regime, "budget": budget, "policy": policy, **raw}
    for key in ("pair_trials", "decisions", "wrong_decisions", "enclosed_truth",
                "queries_sum", "original_missing_sum", "free_revealed_sum"):
        row[key] = int(row[key])
    row.update(resolved_fraction=row["decisions"] / n,
               mean_queries=row["queries_sum"] / n,
               free_revealed_fraction=row["free_revealed_sum"] / row["original_missing_sum"],
               mean_initial_width=row["initial_width_sum"] / n,
               mean_actual_remaining_width=row["actual_width_sum"] / n,
               mean_worst_case_remaining_width=row["worst_width_sum"] / n)
    return row


def aggregate(frame, keys):
    totals = frame.groupby(keys, sort=True, as_index=False)[list(METRIC_NAMES)].sum()
    totals["resolved_fraction"] = totals.decisions / totals.pair_trials
    totals["mean_queries"] = totals.queries_sum / totals.pair_trials
    totals["free_revealed_fraction"] = totals.free_revealed_sum / totals.original_missing_sum
    for original, mean in [("initial_width_sum", "mean_initial_width"),
                           ("actual_width_sum", "mean_actual_remaining_width"),
                           ("worst_width_sum", "mean_worst_case_remaining_width")]:
        totals[mean] = totals[original] / totals.pair_trials
    return totals


def reconcile_restricted(detail, meters):
    checks = 0
    for actual, source, keys in [
        (detail, "study_recovery_pair_seed.csv",
         ["cohort", "meter", "gap_hours", "mask_seed", "model_a", "model_b", "budget", "policy"]),
        (meters, "study_recovery.csv", ["cohort", "meter", "gap_hours", "budget", "policy"]),
    ]:
        actual = actual[actual.regime == REGIMES[0]].set_index(keys).sort_index()
        expected = pd.read_csv(OUT / source)
        expected = expected[expected.budget.isin(BUDGETS) & expected.policy.isin(POLICIES)]
        expected = expected.set_index(keys).sort_index()
        assert actual.index.equals(expected.index), source
        for name in ["pair_trials", "decisions", "wrong_decisions", "enclosed_truth"]:
            np.testing.assert_array_equal(actual[name], expected[name])
        for name in ["resolved_fraction", "mean_queries", "mean_initial_width",
                     "mean_actual_remaining_width", "mean_worst_case_remaining_width"]:
            np.testing.assert_allclose(actual[name], expected[name], rtol=1e-9, atol=1e-11)
        checks += len(actual)
    return checks


def main():
    started = time.perf_counter()
    protocol = WORK / "archive_access_protocol.txt"
    if not protocol.exists():
        raise RuntimeError("Freeze the archive-access protocol before execution")
    input_names = ["study_predictions.csv", "study_summary.json", "study_recovery.csv",
                   "study_recovery_pair_seed.csv", "run_energy_rank_study.py", "study_recovery.py"]
    original_hashes = {name: sha(OUT / name) for name in input_names}
    summary = json.loads((OUT / "study_summary.json").read_text())
    assert original_hashes["study_predictions.csv"] == summary["artifacts"]["study_predictions.csv"]["sha256"]
    assert original_hashes["run_energy_rank_study.py"] == summary["script_sha256"]
    checks = self_checks()
    models = summary["design"]["models"]
    assert models == ["daily", "ridge", "hist_gradient_boosting", "mlp"]
    pairs = list(itertools.combinations(range(4), 2))
    frame = pd.read_csv(OUT / "study_predictions.csv")
    frame["day"] = frame.timestamp.str[:10]
    detailed = []
    provenance = []
    total_evaluations = 0
    archive_evaluations_reused = 0
    max_copy_error = 0.0
    for (cohort, meter), meter_data in frame.groupby(["cohort", "meter"], sort=True):
        # The mapping cannot inspect truth or other forecast columns.
        lookup = persistence_lookup(meter_data[["timestamp", "daily"]])
        validated_links = 0
        copy_errors = []
        for row in meter_data[["timestamp", "truth_kwh"]].itertuples(index=False):
            source = lookup.get(pd.Timestamp(row.timestamp).value)
            if source is not None:
                future, value = source
                assert future == pd.Timestamp(row.timestamp).value + DAY_NS
                copy_errors.append(abs(value - row.truth_kwh))
                np.testing.assert_allclose(value, row.truth_kwh, rtol=1e-12, atol=1e-12)
                validated_links += 1
        max_copy_error = max(max_copy_error, max(copy_errors, default=0.0))
        stats = defaultdict(lambda: np.zeros(len(METRIC_NAMES)))
        unique_masked = unique_free = 0
        days_with_free_copy = 0
        for day, group in meter_data.groupby("day", sort=True):
            group = group.sort_values("timestamp")
            assert len(group) == 24 and len(set(group.timestamp)) == 24
            timestamps = group.timestamp.tolist()
            truth = group.truth_kwh.to_numpy()
            forecasts = group[models].to_numpy().T
            totals = truth.reshape(-1, 6).sum(axis=1)
            epochday = int(pd.Timestamp(day).value // DAY_NS)
            has_any_free = False
            for gap in GAPS:
                gi = [2, 6, 12].index(gap)
                for seed in SEEDS:
                    rng = np.random.default_rng(np.random.SeedSequence([seed, epochday, gi]))
                    start = int(rng.integers(0, 25 - gap))
                    observed = truth.copy()
                    observed[start:start + gap] = np.nan
                    archive_observed, free_indices = reveal_from_archive(timestamps, observed, lookup)
                    assert set(free_indices).issubset(range(start, start + gap))
                    if free_indices:
                        np.testing.assert_allclose(archive_observed[list(free_indices)], truth[list(free_indices)],
                                                   rtol=1e-12, atol=1e-12)
                        has_any_free = True
                    unique_masked += gap
                    unique_free += len(free_indices)
                    for ai, bi in pairs:
                        a, b = forecasts[ai], forecasts[bi]
                        true_diff = float(np.mean((a - truth) ** 2) - np.mean((b - truth) ** 2))
                        true_sign = decision(true_diff, true_diff)
                        for regime, visible, free_count in [(REGIMES[0], observed, 0),
                                                             (REGIMES[1], archive_observed, len(free_indices))]:
                            blocks = prepare_blocks(2 * (b - a) / 24, visible, totals)
                            initial = worst_width(blocks, ())
                            query_cache = {}
                            for budget in BUDGETS:
                                for policy in POLICIES:
                                    query, worst = choose_queries(a, b, visible, totals, budget, policy)
                                    assert not set(query).intersection(free_indices) if regime == REGIMES[1] else True
                                    if query not in query_cache:
                                        # Paid retrieval occurs only after query selection completes.
                                        recovered = visible.copy()
                                        recovered[list(query)] = truth[list(query)]
                                        query_cache[query] = pair_interval(a, b, recovered, totals)
                                    else:
                                        archive_evaluations_reused += 1
                                    lo, hi = query_cache[query]
                                    actual = max(0., hi - lo)
                                    tolerance = 1e-8 * max(1., abs(true_diff), initial)
                                    assert lo <= true_diff + tolerance and hi >= true_diff - tolerance
                                    assert actual <= worst + tolerance
                                    d = decision(lo, hi)
                                    wrong = int(d != 0 and d != true_sign)
                                    assert wrong == 0
                                    key = (cohort, meter, gap, seed, models[ai], models[bi], regime, budget, policy)
                                    stats[key] += [1, int(d != 0), wrong, 1, initial, actual, worst,
                                                   len(query), gap, free_count]
                                    total_evaluations += 1
            days_with_free_copy += int(has_any_free)
        detailed.extend(format_row(key, value) for key, value in sorted(stats.items()))
        provenance.append({"cohort": cohort, "meter": meter, "target_rows": len(meter_data),
                           "target_rows_with_saved_next_day_copy": validated_links,
                           "test_days": meter_data.day.nunique(), "test_days_with_free_copy": days_with_free_copy,
                           "masked_coordinate_occurrences_all_gaps_seeds": unique_masked,
                           "free_coordinate_occurrences_all_gaps_seeds": unique_free,
                           "max_copy_absolute_error": max(copy_errors, default=0.0)})
        print(datetime.now(timezone.utc).isoformat(timespec="seconds"), cohort, meter, "archive-access complete", flush=True)
    detail = pd.DataFrame(detailed)
    meter_keys = ["cohort", "meter", "gap_hours", "regime", "budget", "policy"]
    meters = aggregate(detail, meter_keys)
    baseline_rows = reconcile_restricted(detail, meters)
    cohort_keys = ["cohort", "gap_hours", "regime", "budget", "policy"]
    cohorts = aggregate(meters, cohort_keys)
    cohort_pairs = aggregate(detail, ["cohort", "model_a", "model_b", "gap_hours", "regime", "budget", "policy"])
    # The fixed panels have equal day counts within cohort, so pooled and macro coverage agree.
    macro = meters.groupby(cohort_keys).resolved_fraction.mean().sort_index()
    np.testing.assert_allclose(cohorts.set_index(cohort_keys).resolved_fraction.sort_index(), macro, rtol=1e-13)
    cohort_pairs["scope"] = "named_pair"
    cohorts["scope"] = "all_pairs"
    cohorts["model_a"], cohorts["model_b"] = "all", "all"
    all_cohort = pd.concat([cohorts, cohort_pairs], ignore_index=True)
    gap_rows = []
    for (cohort, gap, regime), group in cohorts[cohorts.budget == 2].groupby(["cohort", "gap_hours", "regime"]):
        exact = group[group.policy == POLICIES[0]].iloc[0]
        greedy = group[group.policy == POLICIES[1]].iloc[0]
        gap_rows.append({"cohort": cohort, "gap_hours": int(gap), "regime": regime,
                         "exact_minus_greedy_coverage_percentage_points": 100 * (exact.resolved_fraction - greedy.resolved_fraction),
                         "exact_coverage": exact.resolved_fraction, "greedy_coverage": greedy.resolved_fraction,
                         "exact_mean_queries": exact.mean_queries, "greedy_mean_queries": greedy.mean_queries})
    output_frames = {"study_archive_access_pair_seed.csv": detail,
                     "study_archive_access_meters.csv": meters,
                     "study_archive_access_cohorts.csv": all_cohort}
    for name, data in output_frames.items():
        data.to_csv(OUT / name, index=False)
    for name, digest in original_hashes.items():
        assert sha(OUT / name) == digest, "Existing artifact was changed: " + name
    result = {"status": "passed", "completed_utc": datetime.now(timezone.utc).isoformat(),
              "wall_seconds": time.perf_counter() - started,
              "regimes": list(REGIMES), "gaps": list(GAPS), "seeds": list(SEEDS),
              "budgets": list(BUDGETS), "policies": list(POLICIES), "meters": len(provenance),
              "heldout_meter_days": int(frame.groupby(["cohort", "meter", "day"]).ngroups),
              "dependent_policy_budget_pair_evaluations": total_evaluations,
              "unique_pair_mask_gap_comparisons_per_regime": total_evaluations // (2 * len(BUDGETS) * len(POLICIES)),
              "exact_interval_cache_hits": archive_evaluations_reused,
              "restricted_reference_rows_reconciled": baseline_rows,
              "checks": {**checks, "free_values_match_truth_after_lookup": True,
                         "no_queries_to_observed_or_free_coordinates": True,
                         "all_reference_differences_enclosed": True, "wrong_certificates": 0,
                         "source_artifacts_unchanged": True, "macro_equals_pooled_cohort_coverage": True},
              "max_persistence_copy_absolute_error": max_copy_error,
              "copy_validation_tolerance": {"relative": 1e-12, "absolute": 1e-12},
              "provenance_by_meter": provenance,
              "cohort_results": cohorts.to_dict("records"), "named_pair_results": cohort_pairs.to_dict("records"),
              "exact_vs_greedy": gap_rows,
              "interpretation": "Post-review same-panel sensitivity. Full available saved test-persistence archive, not full informational closure. Later forecasts are retrospective inputs; no nonlinear inversion or cache/raw-source lookup. All budgets are pair-specific and applied even if already certified. Free fractions count originally masked coordinate occurrences; no independence or deployment-cost claim.",
              "distribution": "Aggregates only; no BLEM hourly values or persistence forecasts are written.",
              "source_hashes": original_hashes, "script_sha256": sha(__file__),
              "protocol_sha256": sha(protocol),
              "output_hashes": {name: sha(OUT / name) for name in output_frames}}
    (OUT / "study_archive_access.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": "passed", "wall_seconds": result["wall_seconds"],
                      "rows_reconciled": baseline_rows, "cohort_results": result["cohort_results"],
                      "exact_vs_greedy": gap_rows}, indent=2), flush=True)


if __name__ == "__main__":
    main()
