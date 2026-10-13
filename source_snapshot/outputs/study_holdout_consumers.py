"""Frozen replication on previously unused consumers from the same UCI source.

No original artifact is overwritten. This is not a new external dataset or a
deployment study. Run from the original workspace after obtaining its source.
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import platform
import time
import traceback
import warnings
import zipfile

import numpy as np
import pandas as pd
import scipy
import sklearn

from run_energy_rank_study import (MODELS, MLP_PARAMETERS, daily_design,
                                  local_dst_affected, fit_forecasts, digest)
from study_archive_access import (DAY_NS, SEEDS, BUDGETS, POLICIES, REGIMES,
                                  METRIC_NAMES, persistence_lookup,
                                  reveal_from_archive, choose_queries,
                                  format_row, aggregate, self_checks)
from study_recovery import prepare_blocks, pair_interval, decision, worst_width

ROOT = Path(__file__).resolve().parents[1]
WORK, OUT = ROOT / "work", ROOT / "outputs"
COHORT = "portugal_new_consumers"
ORIGINAL_NAMES = ("study_predictions.csv", "study_summary.json", "study_recovery.csv",
                  "study_recovery_pair_seed.csv", "run_energy_rank_study.py", "study_recovery.py")
CONFIG = {
    "candidate_first": "MT_081", "candidate_last": "MT_370", "selected_count": 30,
    "selection_year": 2013, "minimum_nonmissing_fraction": .99,
    "strict_minimum_positive_fraction": .95, "train_year": 2013,
    "test_year": 2014, "test_months": [1, 4, 7, 10], "test_max_day": 28,
    "models": MODELS, "gap_hours": 6, "total_block_hours": 6,
    "seeds": list(SEEDS), "budgets": list(BUDGETS), "policies": list(POLICIES),
    "regimes": list(REGIMES), "workers": 2, "training_threads_per_worker": 2,
    "bootstrap_seed": 1729, "bootstrap_resamples": 2000,
    "ridge_alpha": 1.,
    "hgb": {"max_iter": 100, "learning_rate": .08, "max_leaf_nodes": 15,
            "min_samples_leaf": 20, "l2_regularization": 1., "max_bins": 127,
            "random_state": 1729, "early_stopping": False},
    "mlp": MLP_PARAMETERS,
    "mlp_target_scaling": "training mean; invert then nonnegative clipping",
    "selection_uses_test_values": False, "tuning_or_consumer_replacement": False,
}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def log(message):
    print(datetime.now(timezone.utc).isoformat(timespec="seconds"), message, flush=True)


def select_consumers():
    """Selection depends on 2013 only; 2014 values never affect the ID list."""
    path = WORK / "data_electricity.txt"
    names = pd.read_csv(path, sep=";", nrows=0).columns.tolist()
    candidates = [f"MT_{i:03d}" for i in range(81, 371)]
    assert all(name in names for name in candidates)
    columns = [names[0], *candidates]
    raw = pd.read_csv(path, sep=";", decimal=",", usecols=columns,
                      dtype={name: "float64" for name in candidates})
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.iloc[:, 0], format="%Y-%m-%d %H:%M:%S")
                                - pd.Timedelta(minutes=15))
    values = raw[candidates]
    hourly = values.resample("h").sum(min_count=4) / 4
    train = hourly.loc["2013"]
    screening = [{"meter": name, "training_hour_count": len(train),
                  "training_nonmissing_fraction": float(train[name].notna().mean()),
                  "training_positive_fraction": float((train[name] > 0).mean())}
                 for name in candidates]
    eligible = [row["meter"] for row in screening
                if row["training_nonmissing_fraction"] >= .99 and row["training_positive_fraction"] > .95]
    if len(eligible) < 30:
        raise RuntimeError(f"Frozen rule produced only {len(eligible)} eligible candidate consumers")
    selected = eligible[:30]
    return hourly[selected].copy(), selected, screening


def evaluate_consumer(job):
    """Separate worker: immutable ID, fixed fitter, no retries or retuning."""
    meter, series = job
    try:
        return evaluate_consumer_impl(meter, series)
    except Exception as error:
        return {"meter": meter, "status": "failed", "error": repr(error),
                "traceback": traceback.format_exc()}


def evaluate_consumer_impl(meter, series):
    started = time.perf_counter()
    days_all, features, targets, eligible = daily_design(series)
    # Verify the actual design's complete-day causal features, not a substitute.
    for column, lag in enumerate((1, 2, 7)):
        np.testing.assert_allclose(features[lag:, :, column], targets[:-lag],
                                   rtol=0, atol=0, equal_nan=True)
    np.testing.assert_allclose(features[1:, :, 3],
                               np.repeat(targets[:-1].mean(axis=1)[:, None], 24, axis=1),
                               rtol=0, atol=0, equal_nan=True)
    eligible &= ~local_dst_affected(days_all)
    test_mask = ((days_all.year == 2014) & np.isin(days_all.month, [1, 4, 7, 10])
                 & (days_all.day <= 28) & eligible)
    with warnings.catch_warnings(record=True) as outer_warnings:
        warnings.simplefilter("always")
        days, truth_all, pred_all, profiles, donors, meta = fit_forecasts("portugal", meter, series)
    assert days.equals(days_all[test_mask])
    np.testing.assert_array_equal(truth_all, targets[test_mask])
    assert np.isfinite(truth_all).all() and (truth_all >= 0).all()
    assert np.isfinite(pred_all).all() and (pred_all >= 0).all()
    np.testing.assert_array_equal(pred_all[:, 0, :], features[test_mask, :, 0])
    meta["cohort"] = COHORT
    meta["additional_warnings"] = [str(w.message) for w in outer_warnings]
    meta["status"] = "passed"
    forecast_rows = []
    for di, day in enumerate(days):
        for hour in range(24):
            forecast_rows.append((COHORT, meter, (day + pd.Timedelta(hours=hour)).isoformat(),
                                  truth_all[di, hour], *pred_all[di, :, hour]))
    predictions = pd.DataFrame(forecast_rows, columns=["cohort", "meter", "timestamp", "truth_kwh", *MODELS])
    lookup = persistence_lookup(predictions[["timestamp", "daily"]])
    copy_links = 0
    max_copy_error = 0.
    for timestamp, value in predictions[["timestamp", "truth_kwh"]].itertuples(index=False, name=None):
        source = lookup.get(pd.Timestamp(timestamp).value)
        if source is not None:
            future, copied = source
            assert future - pd.Timestamp(timestamp).value == DAY_NS
            error = abs(copied - value)
            max_copy_error = max(max_copy_error, error)
            np.testing.assert_allclose(copied, value, rtol=0, atol=0)
            copy_links += 1
    stats = defaultdict(lambda: np.zeros(len(METRIC_NAMES)))
    checks = {"evaluations": 0, "wrong_certificates": 0, "enclosure_failures": 0,
              "worst_width_failures": 0, "free_copy_checks": 0, "query_feasibility_checks": 0}
    failures = []
    unique_masked = unique_free = days_with_copy = 0
    for di, day in enumerate(days):
        truth, forecasts = truth_all[di], pred_all[di]
        timestamps = [(day + pd.Timedelta(hours=hour)).isoformat() for hour in range(24)]
        totals = truth.reshape(-1, 6).sum(axis=1)
        epochday = int(day.value // DAY_NS)
        has_copy = False
        for seed in SEEDS:
            rng = np.random.default_rng(np.random.SeedSequence([seed, epochday, 1]))
            start = int(rng.integers(0, 19))
            observed = truth.copy()
            observed[start:start + 6] = np.nan
            augmented, free_indices = reveal_from_archive(timestamps, observed, lookup)
            assert set(free_indices).issubset(range(start, start + 6))
            if free_indices:
                np.testing.assert_array_equal(augmented[list(free_indices)], truth[list(free_indices)])
                has_copy = True
            checks["free_copy_checks"] += 1
            unique_masked += 6
            unique_free += len(free_indices)
            for ai, bi in itertools.combinations(range(4), 2):
                a, b = forecasts[ai], forecasts[bi]
                true_diff = float(np.mean((a - truth) ** 2) - np.mean((b - truth) ** 2))
                true_sign = decision(true_diff, true_diff)
                for regime, visible, free in ((REGIMES[0], observed, 0),
                                               (REGIMES[1], augmented, len(free_indices))):
                    blocks = prepare_blocks(2 * (b - a) / 24, visible, totals)
                    initial = worst_width(blocks, ())
                    cache = {}
                    for budget in BUDGETS:
                        for policy in POLICIES:
                            query, worst = choose_queries(a, b, visible, totals, budget, policy)
                            assert len(query) <= budget and all(np.isnan(visible[i]) for i in query)
                            if regime == REGIMES[1]:
                                assert not set(query).intersection(free_indices)
                            checks["query_feasibility_checks"] += 1
                            if query not in cache:
                                recovered = visible.copy()
                                # Paid values are disclosed only after the fixed batch is chosen.
                                recovered[list(query)] = truth[list(query)]
                                cache[query] = pair_interval(a, b, recovered, totals)
                            lo, hi = cache[query]
                            width = max(0., hi - lo)
                            tolerance = 1e-8 * max(1., abs(true_diff), initial)
                            enclosed = lo <= true_diff + tolerance and hi >= true_diff - tolerance
                            within_worst = width <= worst + tolerance
                            d = decision(lo, hi)
                            wrong = int(d != 0 and d != true_sign)
                            checks["evaluations"] += 1
                            checks["wrong_certificates"] += wrong
                            checks["enclosure_failures"] += int(not enclosed)
                            checks["worst_width_failures"] += int(not within_worst)
                            if wrong or not enclosed or not within_worst:
                                failures.append({"meter": meter, "day": str(day.date()), "seed": seed,
                                                 "model_a": MODELS[ai], "model_b": MODELS[bi],
                                                 "regime": regime, "budget": budget, "policy": policy,
                                                 "wrong": wrong, "enclosed": bool(enclosed),
                                                 "within_worst": bool(within_worst)})
                            key = (COHORT, meter, 6, seed, MODELS[ai], MODELS[bi], regime, budget, policy)
                            stats[key] += [1, int(d != 0), wrong, int(enclosed), initial, width, worst,
                                           len(query), 6, free]
        days_with_copy += int(has_copy)
    metrics = []
    for mi, model in enumerate(MODELS):
        residual = pred_all[:, mi] - truth_all
        mse = float(np.mean(residual ** 2))
        metrics.append({"cohort": COHORT, "meter": meter, "model": model,
                        "test_days": len(days), "test_targets": truth_all.size,
                        "mse_kwh2": mse, "rmse_kwh": np.sqrt(mse),
                        "mae_kwh": float(np.mean(np.abs(residual)))})
        np.testing.assert_allclose(mse, meta["mse"][model], rtol=1e-12, atol=1e-12)
    return {"status": "passed" if not failures else "failed_checks", "meter": meter,
            "metadata": meta, "predictions": predictions,
            "detail": [format_row(k, v) for k, v in sorted(stats.items())],
            "forecast_metrics": metrics, "checks": checks, "failures": failures,
            "provenance": {"meter": meter, "test_days": len(days), "target_rows": truth_all.size,
                           "target_rows_with_saved_next_day_copy": copy_links,
                           "test_days_with_free_copy": days_with_copy,
                           "masked_coordinate_occurrences_all_seeds": unique_masked,
                           "free_coordinate_occurrences_all_seeds": unique_free,
                           "max_copy_absolute_error": max_copy_error},
            "wall_seconds": time.perf_counter() - started}


def cohort_aggregate(meters, keys):
    """Retain pooled counts, but the declared primary rate weights meters equally."""
    result = aggregate(meters, keys)
    means = ["resolved_fraction", "mean_queries", "free_revealed_fraction", "mean_initial_width",
             "mean_actual_remaining_width", "mean_worst_case_remaining_width"]
    result = result.rename(columns={key: "pooled_" + key for key in means})
    macro = meters.groupby(keys, as_index=False)[means].mean()
    return result.merge(macro, on=keys, validate="one_to_one")


def paired_bootstraps(meters):
    output = []
    rng = np.random.default_rng(1729)
    for regime in REGIMES:
        frame = meters[meters.regime == regime]
        exact = frame[(frame.budget == 2) & (frame.policy == POLICIES[0])].set_index("meter").sort_index()
        for name, budget, policy in (("exact_minus_greedy_q2", 2, POLICIES[1]),
                                     ("exact_q2_minus_q0", 0, POLICIES[0])):
            other = frame[(frame.budget == budget) & (frame.policy == policy)].set_index("meter").sort_index()
            assert exact.index.equals(other.index)
            diff = 100 * (exact.resolved_fraction.to_numpy() - other.resolved_fraction.to_numpy())
            resamples = diff[rng.integers(0, len(diff), size=(2000, len(diff)))].mean(axis=1)
            low, high = np.percentile(resamples, [2.5, 97.5])
            output.append({"regime": regime, "comparison": name, "meters": len(diff),
                           "mean_coverage_difference_percentage_points": float(diff.mean()),
                           "descriptive_ci95_percentage_points": [float(low), float(high)],
                           "positive_meters": int((diff > 0).sum()), "negative_meters": int((diff < 0).sum()),
                           "tied_meters": int((diff == 0).sum()),
                           "per_meter_differences": dict(zip(exact.index, diff.tolist()))})
    return output


def main():
    started = time.perf_counter()
    protocol = WORK / "holdout_consumers_protocol.txt"
    if not protocol.exists():
        raise RuntimeError("Freeze the holdout-consumer protocol before candidate inspection")
    original_hashes = {name: digest(OUT / name) for name in ORIGINAL_NAMES}
    original = json.loads((OUT / "study_summary.json").read_text())
    assert original_hashes["run_energy_rank_study.py"] == original["script_sha256"]
    assert original_hashes["study_predictions.csv"] == original["artifacts"]["study_predictions.csv"]["sha256"]
    assert MODELS == original["design"]["models"]
    assert json.loads(json.dumps(MLP_PARAMETERS)) == original["design"]["fixed_hyperparameters"]["mlp"]
    original_ids = {m["meter"] for m in original["meters"] if m["cohort"] == "portugal"}
    helpers = {name: digest(OUT / name) for name in ("study_archive_access.py", "study_recovery.py",
                                                    "run_energy_rank_study.py", "energy_rank_bounds.py")}
    checks = self_checks()
    source_meta = json.loads((WORK / "data_electricity_provenance.json").read_text())
    assert digest(WORK / "data_electricity.zip") == source_meta["zip_sha256"]
    raw_hash = digest(WORK / "data_electricity.txt")
    with zipfile.ZipFile(WORK / "data_electricity.zip") as archive:
        raw_member = next(name for name in archive.namelist() if name.endswith("LD2011_2014.txt"))
        member_hash = hashlib.sha256()
        with archive.open(raw_member) as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                member_hash.update(chunk)
        assert member_hash.hexdigest() == raw_hash
    log("Source and frozen helpers verified; selecting consumers from 2013 only")
    hourly, selected, screening = select_consumers()
    assert len(selected) == 30 and len(set(selected)) == 30
    assert not original_ids.intersection(selected)
    frozen_selection = {"frozen_utc": datetime.now(timezone.utc).isoformat(), "selected_ids": selected,
                        "selection_statistics": screening, "config": CONFIG,
                        "config_sha256": canonical_hash(CONFIG), "protocol_sha256": digest(protocol),
                        "source_text_sha256": raw_hash, "source_zip_sha256": source_meta["zip_sha256"],
                        "script_sha256": digest(__file__), "helper_hashes": helpers,
                        "original_artifact_hashes": original_hashes,
                        "outcomes_inspected_before_selection": False}
    (OUT / "study_holdout_consumers_selection.json").write_text(json.dumps(frozen_selection, indent=2), encoding="utf-8")
    log("Frozen selected IDs: " + ",".join(selected))
    jobs = [(meter, hourly[meter]) for meter in selected]
    results = []
    with ProcessPoolExecutor(max_workers=2) as pool:
        for result in pool.map(evaluate_consumer, jobs):
            results.append(result)
            log(f"New-consumer replication {len(results)}/30: {result['meter']} {result['status']}")
    execution_failures = [r for r in results if r["status"] == "failed"]
    if execution_failures:
        report = {"status": "failed", "reason": "Frozen consumer fit/evaluation failed; no replacement permitted",
                  "selection": frozen_selection, "failures": execution_failures,
                  "completed_consumers": [r["meter"] for r in results if r["status"] != "failed"]}
        (OUT / "study_holdout_consumers.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise RuntimeError("Frozen replication failed; see the retained failure report")
    detail = pd.DataFrame([row for result in results for row in result["detail"]])
    meter_keys = ["cohort", "meter", "gap_hours", "regime", "budget", "policy"]
    meters = aggregate(detail, meter_keys)
    pair_meters = aggregate(detail, meter_keys + ["model_a", "model_b"])
    cohort_keys = ["cohort", "gap_hours", "regime", "budget", "policy"]
    cohorts = cohort_aggregate(meters, cohort_keys)
    pairs = cohort_aggregate(pair_meters, cohort_keys + ["model_a", "model_b"])
    metrics = pd.DataFrame([row for result in results for row in result["forecast_metrics"]])
    forecasts = pd.concat([result["predictions"] for result in results], ignore_index=True)
    assert set(forecasts.meter) == set(selected)
    assert not forecasts.duplicated(["meter", "timestamp"]).any()
    total_checks = {key: sum(r["checks"][key] for r in results) for key in results[0]["checks"]}
    heldout_days = sum(r["metadata"]["test_days"] for r in results)
    assert len(forecasts) == heldout_days * 24
    assert total_checks["evaluations"] == heldout_days * 3 * 6 * 2 * 2 * 2
    for name, value in original_hashes.items():
        assert digest(OUT / name) == value, "Original artifact changed: " + name
    for name, value in helpers.items():
        assert digest(OUT / name) == value, "Frozen helper changed: " + name
    assert digest(__file__) == frozen_selection["script_sha256"]
    assert digest(protocol) == frozen_selection["protocol_sha256"]
    outputs = {"study_holdout_consumers_predictions.csv": forecasts,
               "study_holdout_consumers_pair_seed.csv": detail,
               "study_holdout_consumers_meters.csv": meters,
               "study_holdout_consumers_cohorts.csv": cohorts,
               "study_holdout_consumers_named_pairs.csv": pairs,
               "study_holdout_consumers_forecast_metrics.csv": metrics}
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)
    failure_count = sum(total_checks[k] for k in ("wrong_certificates", "enclosure_failures", "worst_width_failures"))
    report = {"status": "passed" if failure_count == 0 else "failed_checks",
              "completed_utc": datetime.now(timezone.utc).isoformat(),
              "wall_seconds": time.perf_counter() - started, "selection": frozen_selection,
              "versions": {"python": platform.python_version(), "numpy": np.__version__,
                           "pandas": pd.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__},
              "meters": 30, "heldout_meter_days": heldout_days, "target_rows": len(forecasts),
              "unique_pair_mask_comparisons_per_regime": heldout_days * 3 * 6,
              "checks": {**checks, **total_checks, "unchanged_original_artifacts": True,
                         "source_text_matches_verified_zip": True, "consumer_ids_disjoint": True,
                         "causal_features_verified": True, "frozen_config_unchanged": True},
              "failures": [f for r in results for f in r["failures"]],
              "fit_metadata": [r["metadata"] for r in results],
              "provenance_by_meter": [r["provenance"] for r in results],
              "cohort_results": cohorts.to_dict("records"), "named_pair_results": pairs.to_dict("records"),
              "paired_consumer_comparisons": paired_bootstraps(meters),
              "forecast_metrics_macro": metrics.groupby("model")[["mse_kwh2", "rmse_kwh", "mae_kwh"]].mean().to_dict("index"),
              "output_hashes": {name: digest(OUT / name) for name in outputs},
              "interpretation": "Frozen post-review replication on previously unused consumers within the same historical UCI source and calendar. All scenarios retained. Primary rates macro-average consumers; pooled rates are separate. Bootstrap intervals are descriptive whole-consumer panel stability, not population confidence. Two access regimes are modeled; future persistence access is retrospective and incomplete. No deployment, retrieval economics, external-dataset validation, or acceptance probability is established."}
    (OUT / "study_holdout_consumers.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    log(json.dumps({"status": report["status"], "wall_seconds": report["wall_seconds"],
                    "checks": report["checks"], "cohort_results": report["cohort_results"],
                    "paired_consumer_comparisons": report["paired_consumer_comparisons"]}))
    assert failure_count == 0, "Incorrect results retained in failure report"


if __name__ == "__main__":
    main()
