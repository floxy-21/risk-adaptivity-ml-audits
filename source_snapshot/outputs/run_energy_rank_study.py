"""Reproducible controlled verification-outage study; see frozen protocol.

Usage: work/review-env/Scripts/python.exe outputs/run_energy_rank_study.py
Expected raw files are described in work/study_protocol.txt. Outputs are CSV/JSON.
This is not a field-outage experiment. All masks are applied after forecasting.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
import csv
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import platform
import time
import warnings
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from energy_rank_bounds import EnergyBlock, bound_pairwise_mse

ROOT = Path(__file__).resolve().parents[1]
WORK, OUT = ROOT / "work", ROOT / "outputs"
MODELS = ["daily", "ridge", "hist_gradient_boosting", "mlp"]
MLP_PARAMETERS = dict(hidden_layer_sizes=(32, 16), activation="relu", solver="adam",
    alpha=.001, learning_rate_init=.001, batch_size=256, max_iter=1000,
    early_stopping=False, random_state=1729, tol=.0001, n_iter_no_change=10,
    shuffle=True)
METHODS = ["paired_bounds", "individual_bounds", "complete_case", "uniform", "seasonal_profile", "historical_donor"]
SELECTORS = ["minimax_regret", "complete_case", "uniform", "seasonal_profile", "historical_donor"]
PAIRS = list(itertools.combinations(range(4), 2))
P0, P1 = np.array(PAIRS).T
GAPS, PATTERNS, SEEDS, BLOCKS, TAUS = [2, 6, 12], ["contiguous", "scattered", "high_demand"], [1103, 2207, 3301], [6, 24], [0., .01, .05]


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def log(message):
    print(datetime.now(timezone.utc).isoformat(timespec="seconds"), message, flush=True)


def load_household():
    cache = WORK / "study_household_hourly.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    log("Parsing household minute readings")
    frame = pd.read_csv(WORK / "data_uci_household_power.txt", sep=";",
                        usecols=["Date", "Time", "Global_active_power"], na_values=["?"],
                        dtype={"Global_active_power": "float64"})
    index = pd.to_datetime(frame["Date"] + " " + frame["Time"], format="%d/%m/%Y %H:%M:%S")
    power = pd.Series(frame["Global_active_power"].to_numpy(), index=index)
    result = power.resample("h").sum(min_count=60) / 60
    result[power.resample("h").count() != 60] = np.nan
    result.to_pickle(cache)
    return result


def load_portugal():
    cache = WORK / "study_portugal_hourly.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    log("Parsing first 80 ordered Portugal meters for training-only eligibility")
    names = pd.read_csv(WORK / "data_electricity.txt", sep=";", nrows=0).columns.tolist()
    use = names[:81]
    frame = pd.read_csv(WORK / "data_electricity.txt", sep=";", decimal=",", usecols=use,
                        dtype={x: "float64" for x in use[1:]})
    index = pd.to_datetime(frame.iloc[:, 0], format="%Y-%m-%d %H:%M:%S") - pd.Timedelta(minutes=15)
    frame = frame.iloc[:, 1:]
    frame.index = pd.DatetimeIndex(index)
    hourly = frame.resample("h").sum(min_count=4) / 4
    train = hourly.loc["2013"]
    eligible = [c for c in hourly.columns if train[c].notna().mean() >= .99 and (train[c] > 0).mean() > .95]
    if len(eligible) < 30:
        raise RuntimeError("Fewer than30eligible in first80; extend ordered read without changingcriteria")
    hourly = hourly[eligible[:30]]
    hourly.to_pickle(cache)
    return hourly


def daily_design(series):
    # Provider local regular grid (Portugal/household); BLEM uses UTC.
    series = series.sort_index()
    start = series.index.min().ceil("D")
    end = series.index.max().floor("D")
    index = pd.date_range(start, end + pd.Timedelta(hours=23), freq="h")
    values = series.reindex(index).to_numpy(dtype=float)
    days = index[::24]
    y = values.reshape(-1, 24)
    x = np.full((len(days), 24, 10), np.nan)
    for k, lagdays in enumerate([1, 2, 7]):
        x[lagdays:, :, k] = y[:-lagdays]
    means = np.mean(y, axis=1)
    x[1:, :, 3] = means[:-1, None]
    hour = np.arange(24)
    x[:, :, 4] = np.sin(2 * np.pi * hour / 24)
    x[:, :, 5] = np.cos(2 * np.pi * hour / 24)
    x[:, :, 6] = np.sin(2 * np.pi * days.dayofweek.to_numpy()[:, None] / 7)
    x[:, :, 7] = np.cos(2 * np.pi * days.dayofweek.to_numpy()[:, None] / 7)
    x[:, :, 8] = np.sin(2 * np.pi * (days.month.to_numpy()[:, None] - 1) / 12)
    x[:, :, 9] = np.cos(2 * np.pi * (days.month.to_numpy()[:, None] - 1) / 12)
    eligible = np.isfinite(y).all(axis=1) & (y >= 0).all(axis=1) & np.isfinite(x).all(axis=(1, 2))
    return days, x, y, eligible


def local_dst_affected(days):
    """Exclude EU transition days and targets using their lag1/2/7 histories."""
    excluded = set()
    for year in set(days.year):
        for month in [3, 10]:
            end = pd.Timestamp(year=int(year), month=month, day=31)
            transition = end - pd.Timedelta(days=(end.dayofweek + 1) % 7)
            for lag in [0, 1, 2, 7]:
                excluded.add((transition + pd.Timedelta(days=lag)).date())
    return np.array([d.date() in excluded for d in days])


def fit_forecasts(cohort, meter, series):
    days, x, y, eligible = daily_design(series)
    if cohort in ["portugal", "household"]:
        eligible &= ~local_dst_affected(days)
    if cohort == "portugal":
        tr = (days.year == 2013) & eligible
        te = (days.year == 2014) & np.isin(days.month, [1, 4, 7, 10]) & (days.day <= 28) & eligible
    elif cohort == "household":
        tr = np.isin(days.year, [2008, 2009]) & eligible
        te = (days.year == 2010) & eligible
    else:
        # Fixed BLEM protocol supplement: Jan-Sep train, Oct-Dec test.
        split = pd.Timestamp("2017-10-01", tz=days.tz)
        tr, te = (days < split) & eligible, (days >= split) & eligible
    if tr.sum() < 30 or te.sum() < 10:
        raise RuntimeError(f"Insufficient data {cohort}/{meter}:train{tr.sum()}test{te.sum()}")
    train_x, train_y = x[tr].reshape(-1, 10), y[tr].reshape(-1)
    test_x, truth, testdays = x[te], y[te], days[te]
    fitted = [make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
              HistGradientBoostingRegressor(max_iter=100, learning_rate=.08,
                max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1,
                max_bins=127, random_state=1729, early_stopping=False)]
    training_mean = float(train_y.mean())
    if not np.isfinite(training_mean) or training_mean <= 0:
        raise ValueError("MLP target scaling requires a positive finite training mean")
    model_fit_seconds = {}
    before = time.perf_counter()
    with threadpool_limits(limits=2):
        pred = [test_x[:, :, 0]]
        for name, estimator in zip(MODELS[1:3], fitted):
            model_before = time.perf_counter()
            estimator.fit(train_x, train_y)
            pred.append(estimator.predict(test_x.reshape(-1, 10)).reshape(-1, 24))
            model_fit_seconds[name] = time.perf_counter() - model_before
        neural = make_pipeline(StandardScaler(), MLPRegressor(**MLP_PARAMETERS))
        model_before = time.perf_counter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            neural.fit(train_x, train_y / training_mean)
        pred.append(neural.predict(test_x.reshape(-1, 10)).reshape(-1, 24) * training_mean)
        model_fit_seconds["mlp"] = time.perf_counter() - model_before
        neural_estimator = neural.named_steps["mlpregressor"]
        neural_meta = {"epochs": int(neural_estimator.n_iter_),
                       "training_objective_loss": float(neural_estimator.loss_),
                       "target_scale_training_mean_kwh": training_mean,
                       "warnings": [str(w.message) for w in caught]}
    pred = np.maximum(np.stack(pred, axis=1), 0.)
    profiles = np.stack([np.mean(y[tr][days[tr].dayofweek == k], axis=0) for k in range(7)])
    meta = {"cohort": cohort, "meter": meter, "train_days": int(tr.sum()), "test_days": int(te.sum()),
            "train_start": str(days[tr][0].date()), "train_end": str(days[tr][-1].date()),
            "test_start": str(testdays[0].date()), "test_end": str(testdays[-1].date()),
            "training_mean_kwh": training_mean, "fit_seconds": time.perf_counter() - before,
            "model_fit_seconds": model_fit_seconds, "mlp_training": neural_meta,
            "mse": dict(zip(MODELS, np.mean((pred - truth[:, None]) ** 2, axis=(0, 2)).tolist()))}
    log(f"Fitted {cohort}/{meter}: train{tr.sum()} test{te.sum()}, {meta['fit_seconds']:.2f}s")
    return testdays, truth, pred, profiles, y[tr], meta


def individual_extrema(p, L, U):
    # p shape models x missing entries; nonnegative observations, no uppercaps.
    sortedp = np.sort(p, axis=1)[:, ::-1]
    positive_sum = np.maximum(p, 0).sum(axis=1)
    energy = np.clip(positive_sum, L, U)
    cs = np.cumsum(sortedp, axis=1)
    ranks = np.arange(1, p.shape[1] + 1)
    thetaall = (cs - energy[:, None]) / ranks
    active = sortedp > thetaall
    rho = np.maximum(active.sum(axis=1) - 1, 0)
    theta = thetaall[np.arange(len(p)), rho]
    projected = np.maximum(p - theta[:, None], 0)
    projected[energy == 0] = 0
    minimum = np.sum((p - projected) ** 2, axis=1)
    vertex_l = np.zeros_like(p)
    vertex_u = np.zeros_like(p)
    smallest = np.argmin(p, axis=1)
    vertex_l[np.arange(len(p)), smallest] = L
    vertex_u[np.arange(len(p)), smallest] = U
    maximum = np.maximum(np.sum((p - vertex_l) ** 2, axis=1),
                         np.sum((p - vertex_u) ** 2, axis=1))
    return minimum, maximum


def residual_energy(observed, total):
    residual = float(total - np.nansum(observed))
    if residual < -1e-9 * max(1., abs(total)):
        raise ValueError("central total smaller than observed energy")
    return max(0., residual)


def bounds(pred, observed_targets, supplied_totals, blocksize, tau):
    """Uses ONLY observed verification values and retained aggregate readings."""
    observed = np.isfinite(observed_targets)
    mask = ~observed
    coefficients = 2 * (pred[P1] - pred[P0])
    # Construct attaining witnesses, avoiding subtraction of expanded squares.
    low_y = np.tile(np.where(observed, observed_targets, 0.), (len(PAIRS), 1))
    high_y = low_y.copy()
    obs_sse = np.sum((pred[:, observed] - observed_targets[observed]) ** 2, axis=1)
    indiv_lo, indiv_hi = obs_sse.copy(), obs_sse.copy()
    for start in range(0, 24, blocksize):
        idx = np.arange(start, start + blocksize)
        missing = idx[mask[idx]]
        if len(missing) == 0:
            continue
        total = supplied_totals[start // blocksize]
        residual = residual_energy(observed_targets[idx], total)
        L, U = max(0., residual - tau * total), residual + tau * total
        cmin = coefficients[:, missing].min(axis=1)
        cmax = coefficients[:, missing].max(axis=1)
        low_index = missing[np.argmin(coefficients[:, missing], axis=1)]
        high_index = missing[np.argmax(coefficients[:, missing], axis=1)]
        low_y[np.arange(len(PAIRS)), low_index] = np.where(cmin < 0, U, L)
        high_y[np.arange(len(PAIRS)), high_index] = np.where(cmax > 0, U, L)
        il, iu = individual_extrema(pred[:, missing], L, U)
        indiv_lo += il
        indiv_hi += iu
    contrast = pred[P0] - pred[P1]
    lower = np.sum(contrast * ((pred[P0] - low_y) + (pred[P1] - low_y)), axis=1)
    upper = np.sum(contrast * ((pred[P0] - high_y) + (pred[P1] - high_y)), axis=1)
    return lower / 24, upper / 24, (indiv_lo[P0] - indiv_hi[P1]) / 24, (indiv_hi[P0] - indiv_lo[P1]) / 24


def impute(observed_targets, supplied_totals, shape, blocksize):
    """Central-total completion; has no access to hidden verification values."""
    result = observed_targets.copy()
    mask = ~np.isfinite(observed_targets)
    for start in range(0, 24, blocksize):
        idx = np.arange(start, start + blocksize)
        E = residual_energy(observed_targets[idx], supplied_totals[start // blocksize])
        idx = idx[mask[idx]]
        if len(idx):
            values = np.maximum(shape[idx], 0)
            result[idx] = E * (values / values.sum() if values.sum() > 0 else np.ones(len(idx)) / len(idx))
    return result


def sign(x, scale=None):
    margin = 1e-9 * np.maximum(1., np.abs(x) if scale is None else scale)
    return np.where(x > margin, 1, np.where(x < -margin, -1, 0))


def analyze_meter(cohort, meter, days, truth_all, pred_all, profiles, donors, meta, prediction_writer, trial_writer, selector_writer, period_writer, check_state):
    # stats axes gap,pattern,block,tau,method,pair,stat(n,decisions,wrong,enclosure,width)
    stats = np.zeros((3, 3, 2, 3, 6, 6, 5), dtype=float)
    period_sums = np.zeros((3, 3, 3, 2, 3, 6, 8), dtype=float)
    regret = np.zeros((len(days), 3, 3, 3, 2, 3, 5))
    correct = np.zeros_like(regret)
    regretbound = np.zeros_like(regret)
    norm = max(meta["training_mean_kwh"] ** 2, 1e-12)
    for d, day in enumerate(days):
        truth, pred = truth_all[d], pred_all[d]
        # Retained measurements are frozen BEFORE any verification masking.
        supplied_totals = {bs: truth.reshape(-1, bs).sum(axis=1) for bs in BLOCKS}
        true_scores = np.mean((pred - truth) ** 2, axis=1)
        true_diff = true_scores[P0] - true_scores[P1]
        truth_sign = sign(true_diff)
        for h in range(24):
            prediction_writer.writerow([cohort, meter, str((day + pd.Timedelta(hours=h)).isoformat()), truth[h], *pred[:, h]])
        for gi, gap in enumerate(GAPS):
            for pi, pattern in enumerate(PATTERNS):
                for si, seed in enumerate(SEEDS):
                    rng = np.random.default_rng(np.random.SeedSequence([seed, int(day.value // 86400000000000), gi]))
                    mask = np.zeros(24, dtype=bool)
                    if pattern == "contiguous":
                        start = int(rng.integers(0, 25 - gap))
                        mask[start:start + gap] = True
                    elif pattern == "scattered":
                        mask[rng.choice(24, gap, replace=False)] = True
                    else:
                        mask[np.argsort(truth, kind="stable")[-gap:]] = True
                    observed_targets = truth.copy()
                    observed_targets[mask] = np.nan
                    # Donor selected from past training days only, matching the
                    # observed verification shape with one multiplicative scale.
                    obs = ~mask
                    donor_obs = donors[:, obs]
                    scale = observed_targets[obs].sum() / np.maximum(donor_obs.sum(axis=1), 1e-12)
                    distance = np.mean((donor_obs * scale[:, None] - observed_targets[obs]) ** 2, axis=1)
                    donor = donors[int(np.argmin(distance))]
                    cc_scores = np.mean((pred[:, obs] - observed_targets[obs]) ** 2, axis=1)
                    for bi, bs in enumerate(BLOCKS):
                        completed = [impute(observed_targets, supplied_totals[bs], shape, bs) for shape in
                                     [np.ones(24), profiles[day.dayofweek], donor]]
                        baseline_scores = [cc_scores] + [np.mean((pred - v) ** 2, axis=1) for v in completed]
                        baseline_diffs = np.stack([score[P0] - score[P1] for score in baseline_scores])
                        for ti, tau in enumerate(TAUS):
                            lo, hi, ilo, ihi = bounds(pred, observed_targets, supplied_totals[bs], bs, tau)
                            period_sums[gi, pi, si, bi, ti] += np.stack([lo, hi, ilo, ihi, *baseline_diffs], axis=-1)
                            margin = 1e-9 * np.maximum(1., np.maximum(abs(lo), abs(hi)))
                            decision = np.where(lo > margin, 1, np.where(hi < -margin, -1, 0))
                            imargin = 1e-9 * np.maximum(1., np.maximum(abs(ilo), abs(ihi)))
                            idecision = np.where(ilo > imargin, 1, np.where(ihi < -imargin, -1, 0))
                            ds = np.vstack([decision, idecision, sign(baseline_diffs)])
                            row = stats[gi, pi, bi, ti]
                            row[:, :, 0] += 1
                            row[:, :, 1] += ds != 0
                            row[:, :, 2] += (ds != 0) & (ds != truth_sign)
                            eps = 1e-8 * np.maximum(1., abs(true_diff))
                            row[0, :, 3] += (lo <= true_diff + eps) & (hi >= true_diff - eps)
                            row[1, :, 3] += (ilo <= true_diff + eps) & (ihi >= true_diff - eps)
                            row[0, :, 4] += hi - lo
                            row[1, :, 4] += ihi - ilo
                            if np.any(lo < ilo - 1e-7) or np.any(hi > ihi + 1e-7):
                                raise AssertionError("paired bound should tighten individual envelope")
                            U = np.zeros((4, 4))
                            U[P0, P1] = hi
                            U[P1, P0] = -lo
                            worst_regret = U.max(axis=1)
                            selected = [int(np.argmin(worst_regret))] + [int(np.argmin(s)) for s in baseline_scores]
                            actual = np.maximum(0., true_scores[selected] - true_scores.min())
                            worst = worst_regret[selected]
                            if np.any(actual > worst + 1e-8 * np.maximum(1., abs(worst))):
                                raise AssertionError("regret bound missed reference truth")
                            regret[d, gi, pi, si, bi, ti] = actual / norm
                            regretbound[d, gi, pi, si, bi, ti] = worst / norm
                            correct[d, gi, pi, si, bi, ti] = actual <= 1e-9 * max(1., true_scores.max())
                            # Random audit of the evaluation stream, all tau/
                            # block/gap conditions; first1000 selected comparisons.
                            if check_state["count"] < 1000 and check_state["rng"].random() < .004:
                                pair = int(check_state["rng"].integers(0, 6))
                                eb = []
                                for start in range(0, 24, bs):
                                    idx = np.arange(start, start + bs)
                                    if mask[idx].any():
                                        # Missing-only total avoids cancellation
                                        # against observed totals in referenceAPI.
                                        total = supplied_totals[bs][start // bs]
                                        miss = idx[mask[idx]]
                                        E = residual_energy(observed_targets[idx], total)
                                        eb.append(EnergyBlock(miss.tolist(), max(0., E - tau * total), E + tau * total))
                                obslist = [None if mask[i] else float(observed_targets[i]) for i in range(24)]
                                ref = bound_pairwise_mse(pred[P0[pair]], pred[P1[pair]], obslist, eb)
                                np.testing.assert_allclose([lo[pair], hi[pair]], [ref.lower, ref.upper], rtol=1e-8, atol=1e-8)
                                check_state["count"] += 1
        if d and d % 50 == 0:
            log(f"Evaluated {cohort}/{meter} day{d}/{len(days)}")
    meter_rates = {}
    for gi, gap in enumerate(GAPS):
        for pi, pattern in enumerate(PATTERNS):
            for bi, bs in enumerate(BLOCKS):
                for ti, tau in enumerate(TAUS):
                    for mi, method in enumerate(METHODS):
                        for pair, (a, b) in enumerate(PAIRS):
                            n, decisions, wrong, enclosure, width = stats[gi, pi, bi, ti, mi, pair]
                            trial_writer.writerow([cohort, meter, MODELS[a], MODELS[b], gap, pattern, bs, tau, method,
                                int(n), int(decisions), int(wrong), int(enclosure) if mi < 2 else "", width / n if mi < 2 else ""])
                    for mi, method in enumerate(SELECTORS):
                        rr = regret[:, gi, pi, :, bi, ti, mi].reshape(-1)
                        cc = correct[:, gi, pi, :, bi, ti, mi].reshape(-1)
                        bb = regretbound[:, gi, pi, :, bi, ti, mi].reshape(-1)
                        selector_writer.writerow([cohort, meter, gap, pattern, bs, tau, method, len(rr), rr.mean(),
                            np.quantile(rr, .95), cc.mean(), bb.mean(), np.mean(rr <= bb + 1e-8)])
    # Cohort summary stores per-meter aggregates rather than independenttrial CIs.
    summary = {"meta": meta, "comparison": {}, "selection": {}, "conditions": {}, "period_comparison": {}}
    for ti, tau in enumerate(TAUS):
        summary["comparison"][str(tau)] = {}
        for mi, method in enumerate(METHODS):
            s = stats[:, :, :, ti, mi].sum(axis=(0, 1, 2, 3))
            n, decisions, wrong, enclosed, width = s
            summary["comparison"][str(tau)][method] = {
                "n": int(n), "decisions": int(decisions), "wrong": int(wrong), "resolved_fraction": decisions / n,
                "error_among_decisions": wrong / decisions if decisions else None,
                "enclosure_fraction": enclosed / n if mi < 2 else None,
                "mean_width": width / n if mi < 2 else None}
        summary["selection"][str(tau)] = {}
        for mi, method in enumerate(SELECTORS):
            rr, cc, bb = regret[:, :, :, :, :, ti, mi], correct[:, :, :, :, :, ti, mi], regretbound[:, :, :, :, :, ti, mi]
            summary["selection"][str(tau)][method] = {"mean_normalized_regret": float(rr.mean()),
                "p95_normalized_regret": float(np.quantile(rr, .95)), "best_fraction": float(cc.mean()),
                "mean_worst_case_bound": float(bb.mean()), "bound_coverage": float(np.mean(rr <= bb + 1e-8))}
        for gi, gap in enumerate(GAPS):
            for pi, pattern in enumerate(PATTERNS):
                for bi, bs in enumerate(BLOCKS):
                    key = f"gap{gap}_{pattern}_block{bs}_tau{tau}"
                    summary["conditions"][key] = {}
                    for mi, method in enumerate(METHODS):
                        s = stats[gi, pi, bi, ti, mi].sum(axis=0)
                        summary["conditions"][key][method] = {"resolved_fraction": float(s[1] / s[0]),
                            "error_among_decisions": float(s[2] / s[1]) if s[1] else None,
                            "n": int(s[0]), "decisions": int(s[1]), "wrong": int(s[2])}
    period_means = period_sums / len(days)
    oracle_mse = np.mean((pred_all - truth_all[:, None]) ** 2, axis=(0, 2))
    oracle_delta = oracle_mse[P0] - oracle_mse[P1]
    oracle_sign = sign(oracle_delta)
    for ti, tau in enumerate(TAUS):
        summary["period_comparison"][str(tau)] = {}
        for mi, method in enumerate(METHODS):
            loidx, hiidx = [(0, 1), (2, 3), (4, 4), (5, 5), (6, 6), (7, 7)][mi]
            l = period_means[:, :, :, :, ti, :, loidx]
            u = period_means[:, :, :, :, ti, :, hiidx]
            eps = 1e-9 * np.maximum(1., np.maximum(abs(l), abs(u)))
            decision = np.where(l > eps, 1, np.where(u < -eps, -1, 0))
            n, resolved = decision.size, np.sum(decision != 0)
            wrong = np.sum((decision != 0) & (decision != oracle_sign))
            summary["period_comparison"][str(tau)][method] = {"n": int(n), "decisions": int(resolved), "wrong": int(wrong),
                "resolved_fraction": float(resolved / n), "error_among_decisions": float(wrong / resolved) if resolved else None}
            for gi, gap in enumerate(GAPS):
                for pi, pattern in enumerate(PATTERNS):
                    for si, seed in enumerate(SEEDS):
                        for bi, bs in enumerate(BLOCKS):
                            for pair, (a, b) in enumerate(PAIRS):
                                ix = (gi, pi, si, bi, pair)
                                de = int(decision[ix])
                                period_writer.writerow([cohort, meter, MODELS[a], MODELS[b], gap, pattern, seed, bs, tau, method,
                                    len(days), float(l[ix]), float(u[ix]), float(oracle_delta[pair]), de,
                                    int(de != 0 and de != oracle_sign[pair])])
    return summary


def summarize(meters):
    result = {}
    rng = np.random.default_rng(17071)
    for cohort in sorted({m["meta"]["cohort"] for m in meters}):
        items = [m for m in meters if m["meta"]["cohort"] == cohort]
        c = {"meters": len(items), "test_days": sum(m["meta"]["test_days"] for m in items), "comparison": {}, "selection": {}, "period_comparison": {}}
        boot = rng.integers(0, len(items), (2000, len(items)))
        for tau in map(str, TAUS):
            c["period_comparison"][tau] = {}
            for method in METHODS:
                rows = [m["period_comparison"][tau][method] for m in items]
                rec = {k: int(sum(r[k] for r in rows)) for k in ["n", "decisions", "wrong"]}
                for metric in ["resolved_fraction", "error_among_decisions"]:
                    vals = np.array([r[metric] for r in rows if r[metric] is not None])
                    rec[metric] = float(vals.mean()) if len(vals) else None
                    if len(vals) == len(items) and len(items) > 1:
                        rec[metric + "_ci95"] = np.quantile(vals[boot].mean(axis=1), [.025, .975]).tolist()
                c["period_comparison"][tau][method] = rec
            c["comparison"][tau] = {}
            for method in METHODS:
                rows = [m["comparison"][tau][method] for m in items]
                record = {k: int(sum(r[k] for r in rows)) for k in ["n", "decisions", "wrong"]}
                for metric in ["resolved_fraction", "error_among_decisions", "enclosure_fraction", "mean_width"]:
                    vals = np.array([r[metric] for r in rows if r[metric] is not None])
                    record[metric] = float(vals.mean()) if len(vals) else None
                    if len(vals) == len(items) and len(items) > 1:
                        record[metric + "_ci95"] = np.quantile(vals[boot].mean(axis=1), [.025, .975]).tolist()
                c["comparison"][tau][method] = record
            c["selection"][tau] = {}
            for method in SELECTORS:
                rec = {}
                for metric in items[0]["selection"][tau][method]:
                    vals = np.array([m["selection"][tau][method][metric] for m in items])
                    rec[metric] = float(vals.mean())
                    if len(items) > 1:
                        rec[metric + "_ci95"] = np.quantile(vals[boot].mean(axis=1), [.025, .975]).tolist()
                c["selection"][tau][method] = rec
        result[cohort] = c
    return result


def main():
    started = time.perf_counter()
    protocol = WORK / "study_protocol.txt"
    if not protocol.exists():
        raise RuntimeError("Freeze protocol before fitting")
    if not (WORK / "study_protocol_ai_revision.txt").exists():
        raise RuntimeError("Freeze post-results AI revision protocol before fitting")
    log("Starting controlled verification-outage study")
    jobs = [("household", "household_1", load_household())]
    pt = load_portugal()
    jobs += [("portugal", col, pt[col]) for col in pt.columns]
    # Optional externally prepared real cumulative-counter cohort, only if a
    # protocol supplement was frozen before the start of this execution.
    blem = WORK / "data_blem_hourly.csv"
    if blem.exists() and (WORK / "study_protocol_blem.txt").exists():
        frame = pd.read_csv(blem, index_col=0, parse_dates=True)
        jobs += [("blem_counters", col, frame[col]) for col in frame.columns]
    checks = {"count": 0, "rng": np.random.default_rng(78331)}
    meters = []
    with open(OUT / "study_predictions.csv", "w", newline="", encoding="utf-8") as pf, \
         open(OUT / "study_comparisons.csv", "w", newline="", encoding="utf-8") as tf, \
         open(OUT / "study_selections.csv", "w", newline="", encoding="utf-8") as sf, \
         open(OUT / "study_period_comparisons.csv", "w", newline="", encoding="utf-8") as ff:
        pw, tw, sw, fw = csv.writer(pf), csv.writer(tf), csv.writer(sf), csv.writer(ff)
        pw.writerow(["cohort", "meter", "timestamp", "truth_kwh", *MODELS])
        tw.writerow(["cohort", "meter", "model_a", "model_b", "gap_hours", "pattern", "block_hours", "total_tolerance", "method", "trials", "decisions", "wrong_decisions", "enclosed_truth", "mean_bound_width"])
        sw.writerow(["cohort", "meter", "gap_hours", "pattern", "block_hours", "total_tolerance", "selector", "trials", "mean_normalized_regret", "p95_normalized_regret", "fraction_best", "mean_worst_case_bound", "regret_bound_coverage"])
        fw.writerow(["cohort", "meter", "model_a", "model_b", "gap_hours", "pattern", "seed", "block_hours", "total_tolerance", "method", "days", "mean_lower_or_point", "mean_upper_or_point", "true_mean_gap", "decision", "wrong_decision"])
        for cohort, meter, series in jobs:
            days, truth, pred, profiles, donors, meta = fit_forecasts(cohort, meter, series)
            summary = analyze_meter(cohort, meter, days, truth, pred, profiles, donors, meta, pw, tw, sw, fw, checks)
            meters.append(summary)
            pf.flush(); tf.flush(); sf.flush(); ff.flush()
            with open(OUT / "study_meter_results.json", "w", encoding="utf-8") as f:
                json.dump(meters, f, indent=2)
            log(f"Finished {cohort}/{meter}; referencechecks{checks['count']}")
    # Exactly1000 audit checks requested; remaining random feasible comparisons
    # generated independently if empirical sampling did not fill the quota.
    while checks["count"] < 1000:
        rng = checks["rng"]
        truth = rng.uniform(0, 10, 24)
        pred = rng.uniform(0, 10, (4, 24))
        mask = np.zeros(24, bool); mask[rng.choice(24, 6, replace=False)] = True
        bs, tau = int(rng.choice(BLOCKS)), float(rng.choice(TAUS))
        totals = truth.reshape(-1, bs).sum(axis=1)
        observed_targets = truth.copy(); observed_targets[mask] = np.nan
        lo, hi, _, _ = bounds(pred, observed_targets, totals, bs, tau)
        eb = []
        for start in range(0, 24, bs):
            idx = np.arange(start, start + bs); miss = idx[mask[idx]]
            if len(miss):
                total = totals[start // bs]
                E = residual_energy(observed_targets[idx], total)
                eb.append(EnergyBlock(miss.tolist(), max(0., E - tau * total), E + tau * total))
        ref = bound_pairwise_mse(pred[0], pred[1], [None if mask[i] else float(observed_targets[i]) for i in range(24)], eb)
        np.testing.assert_allclose([lo[0], hi[0]], [ref.lower, ref.upper], rtol=1e-8, atol=1e-8)
        checks["count"] += 1
    result = {"completed_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": time.perf_counter() - started,
        "protocol_sha256": digest(protocol), "script_sha256": digest(__file__), "reference_crosschecks_passed": checks["count"],
        "protocol_supplements": {p.name: digest(p) for p in WORK.glob("study_protocol_*.txt")},
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__},
        "design": {"models": MODELS, "methods": METHODS, "selectors": SELECTORS, "gaps": GAPS, "patterns": PATTERNS,
                   "seeds": SEEDS, "block_hours": BLOCKS, "total_tolerances": TAUS, "target_unit": "hourly kWh",
                   "missingness": "controlled synthetic verification outage", "high_demand": "oracle stress, repeated identically for3seeds",
                   "summary_unit": "macro-average per meter;95% bootstrap across whole meters;not independenttrials",
                   "p95_summary": "macro-average of within-meter95th percentiles",
                   "fixed_hyperparameters": {"tuning": "none", "ridge_alpha": 1.,
                       "hist_gradient_boosting_max_iter": 100, "mlp": MLP_PARAMETERS,
                       "mlp_target_scaling": "divide by training mean; invert before nonnegative clipping"},
                   "revision_status": "User-requested post-results AI revision; reused chronological test periods are not new independent confirmation"},
        "cohorts": summarize(meters), "meters": [m["meta"] for m in meters]}
    for source in [WORK / "data_uci_provenance.json", WORK / "data_electricity_provenance.json", WORK / "data_blem_provenance.json"]:
        if source.exists():
            result.setdefault("sources", []).append(json.loads(source.read_text(encoding="utf-8-sig")))
    result["artifacts"] = {p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
                           for p in OUT.glob("study_*.csv")}
    with open(OUT / "study_summary.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    log(f"COMPLETE wall_seconds={result['wall_seconds']:.1f}; checks={checks['count']}")


if __name__ == "__main__":
    main()
