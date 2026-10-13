"""Whole-period audit with explicit access, closure, traces and no model refits.

Run: python outputs/study_period_archive.py
Requires regenerated original inputs. All outputs have a new filename prefix.
"""
from __future__ import annotations
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
import csv
import gzip
import hashlib
import itertools
import json
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import time
import traceback
import numpy as np
import pandas as pd
from run_energy_rank_study import (MODELS, PAIRS, P0, P1, GAPS, PATTERNS, SEEDS, BLOCKS,
                                  TAUS, bounds, impute, sign, daily_design,
                                  local_dst_affected, load_household, load_portugal,
                                  residual_energy, digest)
from study_archive_access import persistence_lookup, reveal_from_archive, DAY_NS

ROOT = Path(__file__).resolve().parents[1]
OUT, WORK = ROOT / "outputs", ROOT / "work"
REGIMES = ("restricted_daily_product_closed", "saved_forecast_archive_closed")
POINTS = ("complete_case", "uniform", "seasonal_profile", "historical_donor")
METHODS = ("paired_bounds", "individual_bounds", *POINTS)
KEYS = ["cohort", "meter", "model_a", "model_b", "gap_hours", "pattern", "seed",
        "block_hours", "total_tolerance", "regime", "method"]
SCALAR_NAMES = [f"{kind}_{i}" for kind in ("lower", "upper", "individual_lower", "individual_upper",
                                         "cc_numerator", "uniform", "profile", "donor") for i in range(6)]


def array_hash(values):
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()


def bitmask(indices):
    return sum(1 << int(i) for i in indices)


def close_observations(observed, totals, blocksize, tau):
    """Only supplied measurements; no truth argument or truth canonicalization."""
    result = np.asarray(observed, dtype=float).copy()
    deduced = []
    lower, upper = [], []
    for start in range(0, 24, blocksize):
        indices = np.arange(start, start + blocksize)
        missing = indices[np.isnan(result[indices])]
        total = float(totals[start // blocksize])
        residual = residual_energy(result[indices], total)
        lo, hi = max(0., residual - tau * total), residual + tau * total
        if len(missing) and (hi == 0 or (tau == 0 and len(missing) == 1)):
            result[missing] = 0. if hi == 0 else residual
            deduced.extend(missing.tolist())
        remaining = indices[np.isnan(result[indices])]
        if not len(remaining):
            # The empty sum is fixed at zero; intersect with its declaration.
            lower.append(0.)
            upper.append(0.)
        else:
            residual = residual_energy(result[indices], total)
            lower.append(max(0., residual - tau * total))
            upper.append(residual + tau * total)
    return result, tuple(deduced), np.array(lower), np.array(upper)


def point_values(pred, observed, totals, blocksize, weekday, profiles, donors):
    obs = np.isfinite(observed)
    scores = np.sum((pred[:, obs] - observed[obs]) ** 2, axis=1)
    cc_numerator = scores[P0] - scores[P1]
    if obs.all():
        diff = cc_numerator / 24
        return np.stack([cc_numerator, diff, diff, diff])
    donor_obs = donors[:, obs]
    scales = observed[obs].sum() / np.maximum(donor_obs.sum(axis=1), 1e-12)
    distance = np.mean((donor_obs * scales[:, None] - observed[obs]) ** 2, axis=1)
    donor = donors[int(np.argmin(distance))]
    completed = [impute(observed, totals, shape, blocksize)
                 for shape in (np.ones(24), profiles[weekday], donor)]
    diffs = []
    for value in completed:
        scores = np.mean((pred - value) ** 2, axis=1)
        diffs.append(scores[P0] - scores[P1])
    return np.stack([cc_numerator, *diffs])


def training_data(cohort, meter, series, metadata):
    days, features, targets, eligible = daily_design(series)
    if cohort in ("household", "portugal"):
        eligible &= ~local_dst_affected(days)
    if cohort == "portugal":
        train = eligible & (days.year == 2013)
    elif cohort == "household":
        train = eligible & np.isin(days.year, [2008, 2009])
    else:
        train = eligible & (days < pd.Timestamp("2017-10-01", tz=days.tz))
    donors = targets[train]
    assert len(donors) == metadata["train_days"]
    np.testing.assert_allclose(donors.mean(), metadata["training_mean_kwh"], rtol=1e-13, atol=1e-13)
    profiles = np.stack([donors[days[train].dayofweek == k].mean(axis=0) for k in range(7)])
    return profiles, donors


def self_checks():
    observed = np.arange(1., 25.)
    totals = observed.reshape(-1, 6).sum(axis=1)
    hidden = observed.copy(); hidden[2] = np.nan
    closed, deduced, lower, upper = close_observations(hidden, totals, 6, 0)
    assert deduced == (2,) and closed[2] == 3. and not np.isnan(closed).any()
    uncertain, deduced, lower, upper = close_observations(hidden, totals, 6, .01)
    assert not deduced and np.isnan(uncertain[2]) and upper[0] > lower[0]
    empty = observed.copy(); empty[:6] = np.nan
    zeros, deduced, _, _ = close_observations(empty, [0., *totals[1:]], 6, .05)
    assert len(deduced) == 6 and (zeros[:6] == 0).all()
    # Alter unseen completions while holding supplied observations/totals fixed.
    pred = np.arange(96., dtype=float).reshape(4, 24) / 20
    alternative = observed.copy(); alternative[0] += .5; alternative[1] -= .5
    assert not np.array_equal(alternative, observed)
    np.testing.assert_array_equal(alternative.reshape(-1, 6).sum(axis=1), totals)
    one = observed.copy(); one[:6] = np.nan
    two = alternative.copy(); two[:6] = np.nan
    a = bounds(pred, one, totals, 6, 0)
    b = bounds(pred, two, totals, 6, 0)
    for x, y in zip(a, b): np.testing.assert_array_equal(x, y)
    return {"singleton_exact_deduction": True, "uncertain_singleton_retained": True,
            "zero_upper_residual_deduction": True, "hidden_completion_interface_invariance": True}


def analyze_meter(job):
    cohort, meter, frame, series, metadata = job
    part = WORK / "period_archive_parts" / (cohort + "_" + meter)
    part.mkdir(parents=True, exist_ok=True)
    try:
        return analyze_meter_impl(cohort, meter, frame, series, metadata, part)
    except Exception as error:
        return {"status": "failed", "cohort": cohort, "meter": meter,
                "error": repr(error), "traceback": traceback.format_exc()}


def analyze_meter_impl(cohort, meter, frame, series, metadata, part):
    profiles, donors = training_data(cohort, meter, series, metadata)
    lookup = persistence_lookup(frame[["timestamp", "daily"]])
    row_ids = dict(zip(frame.timestamp.map(lambda s: pd.Timestamp(s).value), frame.source_row))
    copy_rows = []
    for row in frame.itertuples(index=False):
        target_ns = pd.Timestamp(row.timestamp).value
        source = lookup.get(target_ns)
        if source is not None:
            future, value = source
            assert future - target_ns == DAY_NS
            np.testing.assert_allclose(value, row.truth_kwh, rtol=0, atol=0)
            copy_rows.append({"cohort": cohort, "meter": meter, "target_row": row.source_row,
                              "target_timestamp": row.timestamp, "source_row": row_ids[future],
                              "source_timestamp": str(pd.Timestamp(future)) if pd.Timestamp(row.timestamp).tz is None
                                                    else pd.Timestamp(future, tz="UTC").isoformat(),
                              "source_column": "daily", "copied_value_sha256": array_hash([value])})
    sums = defaultdict(lambda: np.zeros((6, 8)))
    observed_denominators = defaultdict(int)
    legacy_cc_sums = defaultdict(lambda: np.zeros(6))
    known_days = defaultdict(int)
    closed_counts = defaultdict(lambda: np.zeros(3, dtype=np.int64))
    check_counts = {"states": 0, "snapshot_links": 0, "enclosure_checks": 0,
                    "non_widening_checks": 0, "wrong_certificates": 0,
                    "original_helper_daily_checks": 0, "fully_known_state_reuses": 0}
    state_header = ["state_id", "cohort", "meter", "day", "observed_count", "visible_mask",
                    "query_eligible_mask", "observed_values_sha256", "block_hours", "total_tolerance",
                    "residual_lower", "residual_upper", "residual_bounds_sha256", *SCALAR_NAMES]
    map_header = ["cohort", "meter", "day", "gap_hours", "pattern", "seed", "block_hours",
                  "total_tolerance", "regime", "state_id", "initial_missing_mask", "archive_copy_mask",
                  "aggregate_deduced_mask", "visible_mask", "query_eligible_mask", "aggregate_snapshot_id"]
    aggregate_header = ["aggregate_snapshot_id", "cohort", "meter", "day", "block_hours", "total_tolerance",
                        "source_row_start", "source_row_end", "central_totals", "central_totals_sha256",
                        "total_lower", "total_upper", "total_bounds_sha256"]
    total_reference = np.zeros(6)
    n_days = 0
    with gzip.open(part / "states.csv.gz", "wt", newline="", encoding="utf-8") as sf, \
         gzip.open(part / "links.csv.gz", "wt", newline="", encoding="utf-8") as lf, \
         gzip.open(part / "aggregates.csv.gz", "wt", newline="", encoding="utf-8") as af:
        sw, lw, aw = csv.DictWriter(sf, state_header), csv.DictWriter(lf, map_header), csv.DictWriter(af, aggregate_header)
        sw.writeheader(); lw.writeheader(); aw.writeheader()
        for day_index, (day, group) in enumerate(frame.groupby("day", sort=True)):
            group = group.sort_values("timestamp")
            assert len(group) == 24
            n_days += 1
            truth = group.truth_kwh.to_numpy()
            # The original oracle mask used the in-memory source targets.
            # Default CSV parsing can merge/reorder floating near-ties.
            # Keep its pinned mask definition; do not rank reparsed targets.
            original_mask_targets = series.reindex(pd.to_datetime(group.timestamp)).to_numpy()
            assert np.isfinite(original_mask_targets).all()
            np.testing.assert_allclose(original_mask_targets, truth, rtol=1e-13, atol=1e-13)
            pred = group[MODELS].to_numpy().T
            timestamps = group.timestamp.tolist()
            weekday = pd.Timestamp(day).dayofweek
            totals_by_block = {bs: truth.reshape(-1, bs).sum(axis=1) for bs in BLOCKS}
            scores = np.mean((pred - truth) ** 2, axis=1)
            reference = scores[P0] - scores[P1]
            total_reference += reference
            for bs in BLOCKS:
                for tau in TAUS:
                    totals = totals_by_block[bs]
                    snapid = f"{cohort}|{meter}|{day}|{bs}|{tau}"
                    aw.writerow({"aggregate_snapshot_id": snapid, "cohort": cohort, "meter": meter,
                                 "day": day, "block_hours": bs, "total_tolerance": tau,
                                 "source_row_start": int(group.source_row.min()), "source_row_end": int(group.source_row.max()),
                                 "central_totals": json.dumps(totals.tolist()) if cohort != "blem_counters" else "",
                                 "central_totals_sha256": array_hash(totals),
                                 "total_lower": json.dumps(((1-tau)*totals).tolist()) if cohort != "blem_counters" else "",
                                 "total_upper": json.dumps(((1+tau)*totals).tolist()) if cohort != "blem_counters" else "",
                                 "total_bounds_sha256": array_hash(np.r_[(1-tau)*totals, (1+tau)*totals])})
            cache = {}
            for gi, gap in enumerate(GAPS):
                for pattern in PATTERNS:
                    for seed in SEEDS:
                        rng = np.random.default_rng(np.random.SeedSequence([seed, int(pd.Timestamp(day).value // DAY_NS), gi]))
                        missing = np.zeros(24, dtype=bool)
                        if pattern == "contiguous":
                            start = int(rng.integers(0, 25-gap)); missing[start:start+gap] = True
                        elif pattern == "scattered": missing[rng.choice(24, gap, replace=False)] = True
                        else: missing[np.argsort(original_mask_targets, kind="stable")[-gap:]] = True
                        initial = truth.copy(); initial[missing] = np.nan
                        augmented, copied = reveal_from_archive(timestamps, initial, lookup)
                        if copied: np.testing.assert_array_equal(augmented[list(copied)], truth[list(copied)])
                        for bs in BLOCKS:
                            totals = totals_by_block[bs]
                            for tau in TAUS:
                                previous_bounds = None
                                for ri, (regime, supplied) in enumerate(zip(REGIMES, (initial, augmented))):
                                    visible, deduced, residual_lo, residual_hi = close_observations(supplied, totals, bs, tau)
                                    observed = np.isfinite(visible)
                                    if deduced:
                                        np.testing.assert_allclose(visible[list(deduced)], truth[list(deduced)], rtol=1e-10, atol=1e-10)
                                    observation_hash = array_hash(visible)
                                    # Exact values enter the identity; do not replace them with hidden truth.
                                    state_key = (observation_hash, 0 if observed.all() else bs, -1 if observed.all() else tau)
                                    if state_key not in cache:
                                        if observed.all():
                                            point = point_values(pred, visible, totals, bs, weekday, profiles, donors)
                                            lo = hi = ilo = ihi = point[0] / 24
                                        else:
                                            lo, hi, ilo, ihi = bounds(pred, visible, totals, bs, tau)
                                            point = point_values(pred, visible, totals, bs, weekday, profiles, donors) if tau == 0 else np.full((4, 6), np.nan)
                                        scalars = np.stack([lo, hi, ilo, ihi, *point], axis=1)
                                        sid = f"{cohort}|{meter}|{day_index}|{len(cache)}"
                                        state = {"state_id": sid, "cohort": cohort, "meter": meter, "day": day,
                                                 "observed_count": int(observed.sum()), "visible_mask": bitmask(np.flatnonzero(observed)),
                                                 "query_eligible_mask": bitmask(np.flatnonzero(~observed)),
                                                 "observed_values_sha256": observation_hash,
                                                 "block_hours": 0 if observed.all() else bs, "total_tolerance": -1 if observed.all() else tau,
                                                 "residual_lower": json.dumps([] if observed.all() else residual_lo.tolist()) if cohort != "blem_counters" else "",
                                                 "residual_upper": json.dumps([] if observed.all() else residual_hi.tolist()) if cohort != "blem_counters" else "",
                                                 "residual_bounds_sha256": array_hash([] if observed.all() else np.r_[residual_lo, residual_hi])}
                                        state.update(dict(zip(SCALAR_NAMES, scalars.T.ravel())))
                                        sw.writerow(state)
                                        cache[state_key] = (sid, scalars, int(observed.sum()))
                                        check_counts["states"] += 1
                                    else:
                                        if observed.all(): check_counts["fully_known_state_reuses"] += 1
                                    sid, scalars, nobs = cache[state_key]
                                    lo, hi, ilo, ihi = scalars[:, :4].T
                                    epsilon = 1e-8 * np.maximum(1., np.abs(reference))
                                    assert np.all(lo <= reference + epsilon) and np.all(hi >= reference - epsilon)
                                    assert np.all(ilo <= reference + epsilon) and np.all(ihi >= reference - epsilon)
                                    check_counts["enclosure_checks"] += 12
                                    if previous_bounds is not None:
                                        pl, pu, pil, piu = previous_bounds
                                        tolerance = 1e-8 * np.maximum(1., np.maximum(np.abs(pl), np.abs(pu)))
                                        assert np.all(lo >= pl-tolerance) and np.all(hi <= pu+tolerance)
                                        assert np.all(ilo >= pil-tolerance) and np.all(ihi <= piu+tolerance)
                                        check_counts["non_widening_checks"] += 12
                                    previous_bounds = (lo, hi, ilo, ihi)
                                    # Original helper is rerun on a fixed, outcome-independent subset of days.
                                    if ri == 0 and day_index in (0, len(frame)//24 - 1):
                                        raw = bounds(pred, initial, totals, bs, tau)
                                        for a, b in zip(raw, (lo, hi, ilo, ihi)):
                                            np.testing.assert_allclose(a, b, rtol=1e-9, atol=1e-9)
                                        check_counts["original_helper_daily_checks"] += 1
                                    case = (gap, pattern, seed, bs, tau, regime)
                                    sums[case] += np.nan_to_num(scalars, nan=0.)
                                    observed_denominators[case] += nobs
                                    if tau == 0: legacy_cc_sums[case] += scalars[:, 4] / nobs
                                    known_days[case] += int(nobs == 24)
                                    closed_counts[case] += [gap, len(copied) if ri else 0, len(deduced)]
                                    lw.writerow(dict(zip(map_header, [cohort, meter, day, gap, pattern, seed, bs, tau,
                                        regime, sid, bitmask(np.flatnonzero(missing)), bitmask(copied) if ri else 0,
                                        bitmask(deduced), bitmask(np.flatnonzero(observed)), bitmask(np.flatnonzero(~observed)),
                                        f"{cohort}|{meter}|{day}|{bs}|{tau}"])))
                                    check_counts["snapshot_links"] += 1
    assert n_days == metadata["test_days"]
    reference = total_reference / n_days
    scale = max(metadata["training_mean_kwh"] ** 2, 1e-12)
    rows = []
    for case, scalar_sum in sorted(sums.items()):
        gap, pattern, seed, bs, tau, regime = case
        for mi, method in enumerate(METHODS):
            if tau != 0 and method in POINTS: continue
            if method == "paired_bounds": lo, hi = scalar_sum[:, 0]/n_days, scalar_sum[:, 1]/n_days
            elif method == "individual_bounds": lo, hi = scalar_sum[:, 2]/n_days, scalar_sum[:, 3]/n_days
            elif method == "complete_case": lo = hi = scalar_sum[:, 4]/observed_denominators[case]
            else: lo = hi = scalar_sum[:, mi+2]/n_days
            margin = 1e-9 * np.maximum(1., np.maximum(abs(lo), abs(hi)))
            decisions = np.where(lo > margin, 1, np.where(hi < -margin, -1, 0))
            wrong = (decisions != 0) & (decisions != sign(reference))
            if method in METHODS[:2]:
                assert not wrong.any()
                assert np.all(lo <= reference + 1e-8*np.maximum(1., abs(reference)))
                assert np.all(hi >= reference - 1e-8*np.maximum(1., abs(reference)))
            for pair, (ai, bi) in enumerate(PAIRS):
                rows.append(dict(zip(KEYS, [cohort, meter, MODELS[ai], MODELS[bi], gap, pattern, seed, bs, tau, regime, method]),
                    days=n_days, full_target_denominator=24*n_days, observed_target_denominator=observed_denominators[case],
                    mean_lower_or_point=float(lo[pair]), mean_upper_or_point=float(hi[pair]), true_mean_gap=float(reference[pair]),
                    decision=int(decisions[pair]), wrong_decision=int(wrong[pair]), unresolved=int(decisions[pair] == 0),
                    normalized_width=float((hi[pair]-lo[pair])/scale), normalization_scale=scale,
                    closed_daily_mean_complete_case=float(legacy_cc_sums[case][pair]/n_days) if tau == 0 else np.nan,
                    originally_missing_coordinates=int(closed_counts[case][0]), free_archive_coordinates=int(closed_counts[case][1]),
                    aggregate_determined_coordinates=int(closed_counts[case][2]), fully_known_days=known_days[case]))
    return {"status": "passed", "cohort": cohort, "meter": meter, "part": str(part), "rows": rows,
            "copies": copy_rows, "checks": check_counts, "training_days": len(donors),
            "training_mean": float(donors.mean()), "prediction_rows": len(frame)}


def merge_gzip(parts, name, destination):
    with gzip.open(destination, "wt", newline="", encoding="utf-8") as target:
        first = True
        for part in parts:
            with gzip.open(Path(part)/name, "rt", encoding="utf-8") as source:
                header = next(source)
                if first: target.write(header); first = False
                for line in source: target.write(line)


def summarize(frame, keys):
    result = frame.groupby(keys, as_index=False).agg(comparisons=("decision", "size"),
        decisions=("decision", lambda x: int((x != 0).sum())), unresolved=("unresolved", "sum"),
        wrong_decisions=("wrong_decision", "sum"), mean_normalized_width=("normalized_width", "mean"))
    result["coverage"] = result.decisions/result.comparisons
    result["error_among_decisions"] = result.wrong_decisions/result.decisions.replace(0, np.nan)
    return result


def matched_coverage(frame):
    records = []
    exact = frame[frame.total_tolerance == 0]
    groups = ["cohort", "gap_hours", "pattern", "block_hours", "regime"]
    identity = ["meter", "model_a", "model_b", "seed"]
    for key, group in exact.groupby(groups):
        paired = group[group.method == "paired_bounds"].set_index(identity)
        target = int((paired.decision != 0).sum())
        for method in POINTS:
            candidates = group[group.method == method].copy()
            assert set(map(tuple, candidates[identity].to_numpy())) == set(paired.index)
            candidates["ranking_score"] = candidates.mean_lower_or_point.abs()/candidates.normalization_scale
            candidates = candidates[candidates.decision != 0].sort_values(["ranking_score", *identity],
                                                                         ascending=[False, True, True, True, True], kind="stable")
            chosen = candidates.head(target)
            pdec = paired.loc[pd.MultiIndex.from_frame(chosen[identity]), "decision"].to_numpy()
            matching = int((pdec == chosen.decision.to_numpy()).sum())
            unresolved = int((pdec == 0).sum())
            records.append(dict(zip(groups, key), method=method, comparisons=len(paired), paired_decisions=target,
                paired_wrong_decisions=int(paired.wrong_decision.sum()), selected_decisions=len(chosen),
                available_point_decisions=len(candidates), wrong_decisions=int(chosen.wrong_decision.sum()),
                coverage_exactly_matched=len(chosen) == target, selected_with_matching_certificate=matching,
                selected_paired_unresolved=unresolved, selected_with_opposite_certificate=len(chosen)-matching-unresolved,
                minimum_selected_normalized_margin=float(chosen.ranking_score.iloc[-1]) if len(chosen) else np.nan))
    return pd.DataFrame(records)


def reconcile(frame, original):
    keys = [k for k in KEYS if k != "regime"]
    restricted = frame[frame.regime == REGIMES[0]].set_index(keys).sort_index()
    original = original.set_index(keys).sort_index()
    expected = original.loc[restricted.index]
    assert np.array_equal(restricted.days, expected.days)
    np.testing.assert_allclose(restricted.true_mean_gap, expected.true_mean_gap, rtol=1e-10, atol=1e-10)
    interval = restricted.index.get_level_values("method").isin(METHODS[:2])
    for column in ("mean_lower_or_point", "mean_upper_or_point"):
        np.testing.assert_allclose(restricted.loc[interval, column], expected.loc[interval, column], rtol=1e-8, atol=1e-9)
    assert np.array_equal(restricted.loc[interval, "decision"], expected.loc[interval, "decision"])
    changes = []
    for method in METHODS:
        mask = restricted.index.get_level_values("method") == method
        new, old = restricted.loc[mask], expected.loc[mask]
        delta = new.mean_lower_or_point.to_numpy()-old.mean_lower_or_point.to_numpy()
        if method in ("uniform", "seasonal_profile"):
            np.testing.assert_allclose(new.mean_lower_or_point, old.mean_lower_or_point, rtol=1e-8, atol=1e-9)
        changes.append({"method": method, "rows": len(new),
                        "changed_decisions": int((new.decision.to_numpy()!=old.decision.to_numpy()).sum()),
                        "maximum_point_or_lower_difference": float(np.max(np.abs(delta))),
                        "closure_only_changed_complete_case_decisions": int((sign(new.closed_daily_mean_complete_case.to_numpy())!=old.decision.to_numpy()).sum()) if method == "complete_case" else None,
                        "normalization_additional_changed_complete_case_decisions": int((sign(new.closed_daily_mean_complete_case.to_numpy())!=new.decision.to_numpy()).sum()) if method == "complete_case" else None})
    return {"reference_rows": len(restricted), "interval_rows_reconciled": int(interval.sum()), "by_method": changes}


def main():
    started = time.perf_counter()
    protocol = WORK/"period_archive_protocol.txt"
    if not protocol.exists(): raise RuntimeError("Freeze protocol before execution")
    original_names = ["study_predictions.csv", "study_summary.json", "study_period_comparisons.csv",
                      "study_matched_coverage.csv", "study_archive_access.json", "study_recovery.csv",
                      "study_recovery_pair_seed.csv", "run_energy_rank_study.py", "study_recovery.py",
                      "study_archive_access.py", "energy_rank_bounds.py"]
    source_hashes = {name: digest(OUT/name) for name in original_names}
    summary = json.loads((OUT/"study_summary.json").read_text())
    assert source_hashes["study_predictions.csv"] == summary["artifacts"]["study_predictions.csv"]["sha256"]
    assert source_hashes["study_period_comparisons.csv"] == summary["artifacts"]["study_period_comparisons.csv"]["sha256"]
    assert source_hashes["run_energy_rank_study.py"] == summary["script_sha256"]
    tests = self_checks()
    predictions = pd.read_csv(OUT/"study_predictions.csv")
    predictions["source_row"] = np.arange(len(predictions))
    predictions["day"] = predictions.timestamp.str[:10]
    household, portugal = load_household(), load_portugal()
    blem = pd.read_csv(WORK/"data_blem_hourly.csv", index_col=0, parse_dates=True)
    metadata = {(r["cohort"], r["meter"]): r for r in summary["meters"]}
    jobs = []
    for (cohort, meter), group in predictions.groupby(["cohort", "meter"], sort=True):
        series = household if cohort == "household" else portugal[meter] if cohort == "portugal" else blem[meter]
        jobs.append((cohort, meter, group, series, metadata[(cohort, meter)]))
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": digest(__file__),
        "protocol_sha256": digest(protocol), "source_hashes": source_hashes,
        "regimes": {REGIMES[0]: "Isolated daily evaluators; period aggregator receives only scalar bounds, point loss sums and counts. No cross-day raw forecasts. Historical restricted reference only.",
                    REGIMES[1]: "Every saved TEST forecast row for the same meter, all four candidate columns. Every documented t+24 daily-persistence copy is incorporated, including within the evaluated period. Exact aggregate deductions follow. No outside-period forecasts, arrival assumption, nonlinear inversion, feature cache or raw-target fallback."},
        "within_period_raw_access_equals_saved_archive_here": True,
        "forecast_archive": {"file": "study_predictions.csv", "sha256": source_hashes["study_predictions.csv"],
                             "row_index": "zero-based data row excluding CSV header", "columns": MODELS,
                             "targets_not_accessible_except_observed_or_documented_copies": True},
        "retained_measurements": "Original full target snapshot supplies nominal disjoint6/24hour totals BEFORE original artificial masks; each case supplies only its declared block size and symmetric0/1/5percent band. This is not measured backup-channel survival.",
        "mask_design": {"gaps": GAPS, "patterns": PATTERNS, "seeds": SEEDS, "blocks": BLOCKS, "taus": TAUS},
        "implementation_correction": {"amendment_file": "work/period_archive_bugfix_amendment.txt",
            "amendment_sha256": digest(WORK/"period_archive_bugfix_amendment.txt"),
            "high_demand_rank_source": "Pinned original hourly source series; original stable argsort. Default CSV parse altered4near-tie masks in the failed first implementation. All34meters rerun; no tolerance relaxation."},
        "denominators": {"bounds_and_completed_imputations": "24*eligible days", "complete_case": "pooled observed-coordinate paired-loss numerator divided by total closed observed count", "legacy_complete_case": "equal-day mean of observed-only contrasts, retained only to diagnose compatibility changes"},
        "trace_encoding": {"masks": "24-bit nonnegative integers; bit h is target hour h", "value_hashes": "SHA256 of little-endian float64 array bytes; observed vectors retain NaN at missing coordinates", "states": "Deduplicated by exact visible-value hash and block/tolerance; fully observed state has block0,tau-1, empty residual arrays, and is universal for that same visible vector. No hidden-truth substitution.", "blem_values": "Observation and residual/aggregate values omitted where they could reveal raw targets; row references/hashes support raw-dependent regeneration. Daily aggregate loss contributions are included.", "scalar_fields": SCALAR_NAMES},
        "recovery_attribution": "Existing daily archive results only: budget2 PER DAY PER PAIR; no new period-wide paid-query optimization. Free reconstruction and exact-minus-greedy gain must be reported separately."}
    (OUT/"study_period_archive_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for r in pool.map(analyze_meter, jobs):
            results.append(r)
            print(datetime.now(timezone.utc).isoformat(), f"Period archive {len(results)}/34 {r['cohort']}/{r['meter']} {r['status']}", flush=True)
    failures = [r for r in results if r["status"] != "passed"]
    if failures:
        (OUT/"study_period_archive.json").write_text(json.dumps({"status": "failed", "failures": failures}, indent=2), encoding="utf-8")
        raise RuntimeError("Reanalysis failed; failures retained")
    frame = pd.DataFrame([row for result in results for row in result["rows"]])
    original = pd.read_csv(OUT/"study_period_comparisons.csv")
    reconciliation = reconcile(frame, original)
    base_keys = [k for k in KEYS if k != "regime"]
    restricted = frame[frame.regime==REGIMES[0]].set_index(base_keys).sort_index()
    archive = frame[frame.regime==REGIMES[1]].set_index(base_keys).sort_index()
    assert restricted.index.equals(archive.index)
    bounded = archive.index.get_level_values("method").isin(METHODS[:2])
    assert np.all(archive.loc[bounded,"normalized_width"] <= restricted.loc[bounded,"normalized_width"] + 1e-8)
    scenario = summarize(frame, ["cohort","regime","gap_hours","pattern","block_hours","total_tolerance","method"])
    cohorts = summarize(frame, ["cohort","regime","total_tolerance","method"])
    pairs = summarize(frame, ["cohort","model_a","model_b","regime","total_tolerance","method"])
    matched = matched_coverage(frame)
    outputs = {"study_period_archive_cases.csv": frame, "study_period_archive_scenarios.csv": scenario,
               "study_period_archive_cohorts.csv": cohorts, "study_period_archive_pairs.csv": pairs,
               "study_period_archive_matched.csv": matched,
               "study_period_archive_sources.csv": pd.DataFrame([row for r in results for row in r["copies"]])}
    for name, data in outputs.items(): data.to_csv(OUT/name, index=False)
    trace_names = []
    for source, name in (("states.csv.gz","study_period_archive_states.csv.gz"),
                         ("links.csv.gz","study_period_archive_links.csv.gz"),
                         ("aggregates.csv.gz","study_period_archive_aggregates.csv.gz")):
        merge_gzip([r["part"] for r in results], source, OUT/name); trace_names.append(name)
    for name, expected in source_hashes.items(): assert digest(OUT/name) == expected, name
    assert digest(__file__) == manifest["script_sha256"] and digest(protocol) == manifest["protocol_sha256"]
    checks = {k: sum(r["checks"][k] for r in results) for k in results[0]["checks"]}
    result = {"status": "passed", "completed_utc": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": time.perf_counter()-started, "meters": len(results), "period_case_rows": len(frame),
        "manifest_sha256": digest(OUT/"study_period_archive_manifest.json"), "source_hashes": source_hashes,
        "script_sha256": digest(__file__), "protocol_sha256": digest(protocol), "checks": {**tests, **checks, "original_sources_unchanged": True},
        "reconciliation": reconciliation, "cohort_results": cohorts.replace({np.nan:None}).to_dict("records"),
        "recovery_attribution": json.loads((OUT/"study_archive_access.json").read_text())["exact_vs_greedy"],
        "output_hashes": {name: digest(OUT/name) for name in [*outputs, *trace_names]},
        "limitation": "Post-review reanalysis on the original panel. Sharpness is relative to the stated augmented product set; no full nonlinear information closure, deployment timing, retrieval savings or independent population inference is established."}
    (OUT/"study_period_archive.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status":result["status"],"wall_seconds":result["wall_seconds"],"checks":result["checks"],"reconciliation":reconciliation}), flush=True)


if __name__ == "__main__":
    main()
