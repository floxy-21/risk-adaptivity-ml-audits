"""Independent numerical verification of the new-consumer replication.

Uses saved CSV reconstruction and NumPy only for the frozen mask RNG.
No original analysis function is imported. Raw data are not needed and no
model is refitted. Selection eligibility was checked separately against raw data.
"""
import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT, WORK = ROOT / "outputs", ROOT / "work"

MODELS = ("daily", "ridge", "hist_gradient_boosting", "mlp")
SEEDS = (1103, 2207, 3301)
REGIMES = ("restricted_record", "available_test_persistence_archive")
POLICIES = ("optimal_minimax_width", "greedy_width_reduction")
RAW_FIELDS = ("pair_trials", "decisions", "wrong_decisions", "enclosed_truth",
              "initial_width_sum", "actual_width_sum", "worst_width_sum",
              "queries_sum", "original_missing_sum", "free_revealed_sum")
INTEGER_FIELDS = {"pair_trials", "decisions", "wrong_decisions", "enclosed_truth",
                  "queries_sum", "original_missing_sum", "free_revealed_sum"}
MEANS = {"resolved_fraction": ("decisions", "pair_trials"),
         "mean_queries": ("queries_sum", "pair_trials"),
         "free_revealed_fraction": ("free_revealed_sum", "original_missing_sum"),
         "mean_initial_width": ("initial_width_sum", "pair_trials"),
         "mean_actual_remaining_width": ("actual_width_sum", "pair_trials"),
         "mean_worst_case_remaining_width": ("worst_width_sum", "pair_trials")}
MAX_ERRORS = defaultdict(float)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(8 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def rows(name):
    with (OUT / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def close(a, b, kind, rel=1e-10, absolute=1e-8):
    a, b = float(a), float(b)
    MAX_ERRORS[kind] = max(MAX_ERRORS[kind], abs(a - b))
    assert math.isclose(a, b, rel_tol=rel, abs_tol=absolute), (kind, a, b)


def summed(group):
    return {k: math.fsum(float(r[k]) for r in group) for k in RAW_FIELDS}


def compare_raw(actual, expected):
    for k in RAW_FIELDS:
        if k in INTEGER_FIELDS:
            assert int(actual[k]) == int(expected[k]), (k, actual[k], expected[k])
        else:
            close(actual[k], expected[k], "aggregate_width_sums")


def aggregation_check(detail, meters, cohorts, named_pairs, days_by_meter):
    assert len(detail) == 30 * 3 * 6 * 2 * 2 * 2
    seen = set()
    by_meter = defaultdict(list)
    by_pair_meter = defaultdict(list)
    for r in detail:
        key = tuple(r[k] for k in ("meter", "mask_seed", "model_a", "model_b", "regime", "budget", "policy"))
        assert key not in seen
        seen.add(key)
        assert int(r["pair_trials"]) == days_by_meter[r["meter"]]
        assert int(r["original_missing_sum"]) == 6 * int(r["pair_trials"])
        for mean, (top, bottom) in MEANS.items():
            close(r[mean], float(r[top]) / float(r[bottom]), "detail_derived_means")
        k = tuple(r[x] for x in ("meter", "regime", "budget", "policy"))
        by_meter[k].append(r)
        by_pair_meter[k + (r["model_a"], r["model_b"])].append(r)
    direct_meters = {k: summed(v) for k, v in by_meter.items()}
    assert len(meters) == len(direct_meters) == 240
    for r in meters:
        k = tuple(r[x] for x in ("meter", "regime", "budget", "policy"))
        expect = direct_meters[k]
        compare_raw(r, expect)
        for mean, (top, bottom) in MEANS.items():
            close(r[mean], expect[top] / expect[bottom], "meter_derived_means")

    def check_cohorts(actual_rows, source, pair=False):
        for r in actual_rows:
            tail = tuple(r[k] for k in ("regime", "budget", "policy"))
            if pair:
                tail += (r["model_a"], r["model_b"])
            matches = [v for k, v in source.items() if k[1:] == tail]
            assert len(matches) == 30
            totals = {k: math.fsum(v[k] for v in matches) for k in RAW_FIELDS}
            compare_raw(r, totals)
            for mean, (top, bottom) in MEANS.items():
                macro = math.fsum(v[top] / v[bottom] for v in matches) / 30
                close(r[mean], macro, "cohort_macro_means")
                close(r["pooled_" + mean], totals[top] / totals[bottom], "cohort_pooled_means")

    check_cohorts(cohorts, direct_meters)
    direct_pair_meters = {k: summed(v) for k, v in by_pair_meter.items()}
    check_cohorts(named_pairs, direct_pair_meters, pair=True)
    assert len(cohorts) == 8 and len(named_pairs) == 48
    return {"pair_seed_rows": len(detail), "consumer_rows": len(meters),
            "cohort_rows": len(cohorts), "named_pair_rows": len(named_pairs)}


def direct_difference(a, b, y):
    return math.fsum((float(x) - float(t)) ** 2 for x, t in zip(a, y)) / 24 - math.fsum((float(x) - float(t)) ** 2 for x, t in zip(b, y)) / 24


def vertex_extrema(a, b, visible, totals):
    missing_groups, energies = [], []
    for start in range(0, 24, 6):
        missing = [i for i in range(start, start + 6) if math.isnan(visible[i])]
        if missing:
            observed_sum = math.fsum(visible[i] for i in range(start, start + 6) if not math.isnan(visible[i]))
            energy = max(0., totals[start // 6] - observed_sum)
            missing_groups.append(missing)
            energies.append(energy)
    values = []
    for peaks in itertools.product(*missing_groups):
        y = [0. if math.isnan(v) else v for v in visible]
        for peak, energy in zip(peaks, energies):
            y[peak] = energy
        values.append(direct_difference(a, b, y))
    return min(values), max(values), len(values)


def independent_worst(coefficients, visible, totals, queries):
    terms = []
    for start in range(0, 24, 6):
        missing = [i for i in range(start, start + 6) if math.isnan(visible[i])]
        retained = [coefficients[i] for i in missing if i not in queries]
        energy = max(0., totals[start // 6] - math.fsum(visible[i] for i in range(start, start + 6) if not math.isnan(visible[i])))
        if len(retained) > 1:
            terms.append(energy * (max(retained) - min(retained)))
    return math.fsum(terms)


def formula_interval(a, b, visible, totals):
    coefficients = [2 * (float(v) - float(u)) / 24 for u, v in zip(a, b)]
    known = math.fsum((float(u) ** 2 - float(v) ** 2) / 24 for u, v in zip(a, b))
    known += math.fsum(c * float(y) for c, y in zip(coefficients, visible) if not math.isnan(y))
    lower, upper = [known], [known]
    for start in range(0, 24, 6):
        missing = [i for i in range(start, start + 6) if math.isnan(visible[i])]
        if missing:
            energy = max(0., totals[start // 6] - math.fsum(float(visible[i]) for i in range(start, start + 6) if not math.isnan(visible[i])))
            lower.append(energy * min(coefficients[i] for i in missing))
            upper.append(energy * max(coefficients[i] for i in missing))
    return math.fsum(lower), math.fsum(upper)


def strict_decision(lo, hi):
    tolerance = 1e-9 * max(1., abs(lo), abs(hi))
    return -1 if hi < -tolerance else (1 if lo > tolerance else 0)


def numerical_checks(day_rows, future, detail):
    consumers = sorted({k[0] for k in day_rows})
    representatives = [consumers[0], consumers[len(consumers) // 2], consumers[-1]]
    representative_days = set()
    for meter in representatives:
        dates = sorted(k[1] for k in day_rows if k[0] == meter)
        representative_days.update((meter, day) for day in (dates[0], dates[len(dates) // 2], dates[-1]))
    counters = {"representative_consumer_days": len(representative_days), "interval_vertex_cases": 0,
                "vertices": 0, "exhaustive_batch_checks": 0, "query_subsets": 0,
                "all_q0_pair_seed_regime_cases": 0}
    counts = defaultdict(lambda: [0, 0, 0, 0.])
    for (meter, day), data in day_rows.items():
        data = sorted(data, key=lambda r: r["timestamp"])
        truth = [float(r["truth_kwh"]) for r in data]
        totals = [math.fsum(truth[s:s + 6]) for s in range(0, 24, 6)]
        epochday = (datetime.fromisoformat(day) - datetime(1970, 1, 1)).days
        for seed in SEEDS:
            start = int(np.random.default_rng(np.random.SeedSequence([seed, epochday, 1])).integers(0, 19))
            observed = truth.copy()
            observed[start:start + 6] = [math.nan] * 6
            augmented = observed.copy()
            for i in range(start, start + 6):
                t = datetime.fromisoformat(data[i]["timestamp"])
                if (meter, t + timedelta(days=1)) in future:
                    augmented[i] = future[meter, t + timedelta(days=1)]
            for ma, mb in itertools.combinations(MODELS, 2):
                a = [float(r[ma]) for r in data]
                b = [float(r[mb]) for r in data]
                coefficients = [2 * (v - u) / 24 for u, v in zip(a, b)]
                reference = direct_difference(a, b, truth)
                true_sign = strict_decision(reference, reference)
                for regime, visible in zip(REGIMES, (observed, augmented)):
                    lo, hi = formula_interval(a, b, visible, totals)
                    certified = strict_decision(lo, hi)
                    tol = 1e-8 * max(1., abs(reference), abs(lo), abs(hi))
                    assert lo - tol <= reference <= hi + tol
                    assert certified == 0 or certified == true_sign
                    key = (meter, str(seed), ma, mb, regime)
                    counts[key][0] += 1
                    counts[key][1] += int(certified != 0)
                    counts[key][2] += int(certified != 0 and certified != true_sign)
                    counts[key][3] += max(0., hi - lo)
                    counters["all_q0_pair_seed_regime_cases"] += 1
                    if (meter, day) not in representative_days:
                        continue
                    missing = [i for i, value in enumerate(visible) if math.isnan(value)]
                    candidates = [q for size in range(min(2, len(missing)) + 1)
                                  for q in itertools.combinations(missing, size)]
                    objectives = [(independent_worst(coefficients, visible, totals, q), len(q), q) for q in candidates]
                    minimum, _, optimum = min(objectives)
                    counters["query_subsets"] += len(candidates)
                    counters["exhaustive_batch_checks"] += 1
                    # Independent exhaustive optimum, not the published solver's tie rule.
                    for query in ((), optimum):
                        recovered = visible.copy()
                        for i in query:
                            recovered[i] = truth[i]
                        lower, upper = formula_interval(a, b, recovered, totals)
                        direct_lo, direct_hi, vertices = vertex_extrema(a, b, recovered, totals)
                        close(lower, direct_lo, "representative_direct_mse_vertex_endpoints", rel=1e-8)
                        close(upper, direct_hi, "representative_direct_mse_vertex_endpoints", rel=1e-8)
                        assert upper - lower <= independent_worst(coefficients, visible, totals, query) + tol
                        counters["interval_vertex_cases"] += 1
                        counters["vertices"] += vertices
    checked = 0
    for r in detail:
        if r["budget"] != "0":
            continue
        key = tuple(r[k] for k in ("meter", "mask_seed", "model_a", "model_b", "regime"))
        expected = counts[key]
        assert int(r["pair_trials"]) == expected[0]
        assert int(r["decisions"]) == expected[1]
        assert int(r["wrong_decisions"]) == expected[2] == 0
        close(r["actual_width_sum"], expected[3], "all_q0_width_sums", rel=1e-9)
        checked += 1
    assert checked == 2160
    return {"representative_consumers": representatives, "q0_detail_rows_recomputed": checked, **counters}


def main():
    report_path = OUT / "study_holdout_consumers.json"
    assert report_path.exists(), "Wait for the complete frozen run"
    report = json.loads(report_path.read_text())
    selection = json.loads((OUT / "study_holdout_consumers_selection.json").read_text())
    assert report["status"] == "passed" and report["selection"] == selection
    for name, expected in report["output_hashes"].items():
        assert sha(OUT / name) == expected
    predictions = rows("study_holdout_consumers_predictions.csv")
    detail = rows("study_holdout_consumers_pair_seed.csv")
    meters = rows("study_holdout_consumers_meters.csv")
    cohorts = rows("study_holdout_consumers_cohorts.csv")
    named_pairs = rows("study_holdout_consumers_named_pairs.csv")
    metrics = rows("study_holdout_consumers_forecast_metrics.csv")
    day_rows = defaultdict(list)
    future, errors = {}, defaultdict(list)
    for r in predictions:
        meter, stamp = r["meter"], datetime.fromisoformat(r["timestamp"])
        assert (meter, stamp) not in future
        future[meter, stamp] = float(r["daily"])
        day_rows[meter, r["timestamp"][:10]].append(r)
        target = float(r["truth_kwh"])
        assert math.isfinite(target) and target >= 0
        for model in MODELS:
            predicted = float(r[model])
            assert math.isfinite(predicted) and predicted >= 0
            errors[meter, model].append(predicted - target)
    assert set(r["meter"] for r in predictions) == set(selection["selected_ids"])
    days_by_meter = defaultdict(int)
    free_days, copies_by_meter = defaultdict(int), defaultdict(int)
    for (meter, day), data in day_rows.items():
        assert len(data) == 24 and len({r["timestamp"] for r in data}) == 24
        days_by_meter[meter] += 1
        count = 0
        for r in data:
            later = future.get((meter, datetime.fromisoformat(r["timestamp"]) + timedelta(days=1)))
            if later is not None:
                assert later == float(r["truth_kwh"])
                count += 1
        assert count in (0, 24)
        free_days[meter] += int(count == 24)
        copies_by_meter[meter] += count
    assert len(day_rows) == report["heldout_meter_days"]
    assert len(predictions) == report["target_rows"] == len(day_rows) * 24
    for r in metrics:
        e = errors[r["meter"], r["model"]]
        mse = math.fsum(v * v for v in e) / len(e)
        close(r["mse_kwh2"], mse, "forecast_mse")
        close(r["rmse_kwh"], math.sqrt(mse), "forecast_rmse")
        close(r["mae_kwh"], math.fsum(abs(v) for v in e) / len(e), "forecast_mae")
        assert int(r["test_targets"]) == len(e)
    for r in detail:
        expected_free = 6 * free_days[r["meter"]] if r["regime"] == REGIMES[1] else 0
        assert int(r["free_revealed_sum"]) == expected_free
    counts = aggregation_check(detail, meters, cohorts, named_pairs, days_by_meter)
    numerical = numerical_checks(day_rows, future, detail)
    dependencies = [*report["output_hashes"], "study_holdout_consumers.json", "study_holdout_consumers_selection.json"]
    result = {"status": "passed", "completed_utc": datetime.now(timezone.utc).isoformat(),
              "aggregation_checks": counts, "prediction_rows": len(predictions), "meter_days": len(day_rows),
              "forecast_metric_rows_checked": len(metrics), "days_by_consumer": dict(days_by_meter),
              "free_copy_targets_by_consumer": dict(copies_by_meter),
              "independent_numerical_checks": numerical,
              "maximum_absolute_discrepancies": dict(MAX_ERRORS),
              "source_hashes": {name: sha(OUT / name) for name in dependencies},
              "script_sha256": sha(Path(__file__)),
              "scope": "Prediction/aggregate-file validation with no original analysis imports. All aggregation, forecast metrics and q0 certificates recomputed; selected direct-MSE vertices and exhaustive query subsets checked independently.",
              "limitations": "Raw training selection and source preprocessing were checked separately and are not rerun here. No model refitting or independent predictor reimplementation. q2 reported aggregates and query counts reconciled from detail rows; not every published q2 per-case choice or certificate is independently reproduced. Representative exhaustive optima may use a different tie rule. Same source/calendar; no external-population or deployment validation."}
    target = OUT / "study_holdout_independent_audit.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "aggregation_checks", "prediction_rows", "meter_days",
                                              "forecast_metric_rows_checked", "independent_numerical_checks",
                                              "maximum_absolute_discrepancies")}, indent=2))
    print("AUDIT_FILE", target)


if __name__ == "__main__":
    main()
