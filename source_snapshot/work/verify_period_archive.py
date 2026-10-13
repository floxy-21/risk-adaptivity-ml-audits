"""Independent archive-only verification of period information-access results.

Run from any directory: python work/verify_period_archive.py
Requires NumPy, pandas and SciPy. Imports no study implementation. Does not
require original target archives or training data, and does not refit models.
Full scalar-trace aggregation is separate from fixed UCI LP/witness checks.
"""
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
import csv
import gzip
import hashlib
from itertools import combinations, groupby, product, zip_longest
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
MODELS = ("daily", "ridge", "hist_gradient_boosting", "mlp")
PAIRS = tuple(combinations(range(4), 2))
REGIMES = ("restricted_daily_product_closed", "saved_forecast_archive_closed")
METHODS = ("paired_bounds", "individual_bounds", "complete_case", "uniform", "seasonal_profile", "historical_donor")
KINDS = ("lower", "upper", "individual_lower", "individual_upper", "cc_numerator", "uniform", "profile", "donor")
KEYS = ["cohort", "meter", "model_a", "model_b", "gap_hours", "pattern", "seed", "block_hours", "total_tolerance", "regime", "method"]
FULL = (1 << 24) - 1
COUNTS = Counter()
MAX_ERRORS = defaultdict(float)
FILEMAP = {}
PUBLIC_MODE = False
ORACLE_MASK_CORRECTIONS = {}


def input_path(name):
    return OUT / FILEMAP.get(name,name)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def array_sha(values):
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()


def rows(name):
    path = input_path(name)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def close(a, b, label, rtol=2e-8, atol=2e-9):
    if np.isscalar(a) and np.isscalar(b):
        a,b=float(a),float(b)
        if math.isnan(a) or math.isnan(b):
            assert math.isnan(a) and math.isnan(b),label
            return
        MAX_ERRORS[label]=max(MAX_ERRORS[label],abs(a-b))
        assert math.isclose(a,b,rel_tol=rtol,abs_tol=atol),(label,a,b)
        return
    aa, bb = np.asarray(a, float), np.asarray(b, float)
    assert aa.shape == bb.shape, (label, aa.shape, bb.shape)
    assert np.array_equal(np.isnan(aa), np.isnan(bb)), label
    good = np.isfinite(aa) & np.isfinite(bb)
    if good.any():
        MAX_ERRORS[label] = max(MAX_ERRORS[label], float(np.max(np.abs(aa[good] - bb[good]))))
    assert np.allclose(aa, bb, rtol=rtol, atol=atol, equal_nan=True), (label, aa, bb)


def sign(lo, hi=None):
    hi = lo if hi is None else hi
    eps = 1e-9 * max(1., abs(lo), abs(hi))
    return -1 if hi < -eps else 1 if lo > eps else 0


def indices(mask):
    return [h for h in range(24) if mask & (1 << h)]


def datekey(row):
    return row["cohort"], row["meter"], row["day"]


def load_sources():
    forecasts = list(rows("frozen_forecasts.csv"))
    lookup = {}
    dayrows = defaultdict(list)
    for i, r in enumerate(forecasts):
        timestamp = datetime.fromisoformat(r["target_interval_start"])
        r["_time"] = timestamp
        lookup[(r["cohort"], r["meter"], timestamp)] = i
        dayrows[(r["cohort"], r["meter"], timestamp.date().isoformat())].append(i)
    expected = {}
    for i, r in enumerate(forecasts):
        j = lookup.get((r["cohort"], r["meter"], r["_time"] + timedelta(days=1)))
        if j is not None and (not PUBLIC_MODE or r["cohort"]!="blem_counters"):
            expected[i] = j
    copy_masks = defaultdict(int)
    observed = set()
    for row in rows("study_period_archive_sources.csv"):
        i, j = int(row["target_row"]), int(row["source_row"])
        assert i not in observed and expected[i] == j
        observed.add(i)
        target, source = forecasts[i], forecasts[j]
        assert target["cohort"] == source["cohort"] == row["cohort"]
        assert target["meter"] == source["meter"] == row["meter"]
        assert datetime.fromisoformat(row["target_timestamp"]) == target["_time"]
        assert datetime.fromisoformat(row["source_timestamp"]) == source["_time"]
        assert source["_time"] - target["_time"] == timedelta(days=1)
        assert row["source_column"] == "daily"
        if row["cohort"] != "blem_counters":
            assert array_sha([float(source["daily"])]) == row["copied_value_sha256"]
            COUNTS["uci_source_copy_value_hashes"] += 1
        day = (row["cohort"], row["meter"], target["_time"].date().isoformat())
        copy_masks[day] |= 1 << target["_time"].hour
        COUNTS["source_copy_pointers"] += 1
    assert observed == set(expected)
    assert len(forecasts) == 89496 and len(expected) == (78648 if PUBLIC_MODE else 85128)
    portugal = sorted({r["meter"] for r in forecasts if r["cohort"] == "portugal"})
    meters = [("household", "household_1"), ("portugal", portugal[0]), ("portugal", portugal[-1])]
    samples = set()
    for cohort, meter in meters:
        days = sorted(k for k in dayrows if k[:2] == (cohort, meter) and copy_masks[k] == FULL)
        samples.update([days[0], days[-1]])
    return forecasts, dayrows, expected, copy_masks, samples


def numerical_sample(link, state, snapshot, forecasts, rowids, future):
    """Independent visible-state construction, LP endpoints and primal witnesses."""
    truth = np.array([float(forecasts[future[i]]["daily"]) for i in rowids])
    pred = np.array([[float(forecasts[i][m]) for i in rowids] for m in MODELS])
    missing = int(link["initial_missing_mask"])
    bs, tau = int(link["block_hours"]), float(link["total_tolerance"])
    gap, pattern, seed = int(link["gap_hours"]), link["pattern"], int(link["seed"])
    epochday = (datetime.fromisoformat(link["day"]) - datetime(1970, 1, 1)).days
    rng = np.random.default_rng(np.random.SeedSequence([seed, epochday, (2, 6, 12).index(gap)]))
    if pattern == "contiguous":
        start = int(rng.integers(0, 25-gap)); wanted = range(start, start+gap)
    elif pattern == "scattered":
        wanted = rng.choice(24, gap, replace=False)
    else:
        wanted = np.argsort(truth, kind="stable")[-gap:]
    assert sum(1 << int(i) for i in wanted) == missing
    central = truth.reshape(-1, bs).sum(axis=1)
    close(central, json.loads(snapshot["central_totals"]), "sample_retained_totals")
    visible = truth.copy(); visible[indices(missing)] = np.nan
    if link["regime"] == REGIMES[1]:
        visible[indices(int(link["archive_copy_mask"]))] = truth[indices(int(link["archive_copy_mask"]))]
    deduced = 0
    for g, total in enumerate(central):
        ids = np.arange(g*bs, (g+1)*bs)
        unknown = ids[~np.isfinite(visible[ids])]
        remaining = float(total - np.nansum(visible[ids]))
        # Numerical subtraction may leave tiny negative roundoff at exact zero.
        if remaining < 0 and abs(remaining) <= 1e-10 * max(1., abs(total)):
            remaining = 0.
        if len(unknown) and ((tau == 0 and len(unknown) == 1) or remaining + tau*total == 0):
            visible[unknown] = remaining if len(unknown) == 1 else 0.
            deduced |= sum(1 << int(i) for i in unknown)
    assert deduced == int(link["aggregate_deduced_mask"])
    known = np.isfinite(visible)
    assert sum(1 << int(i) for i in np.flatnonzero(known)) == int(link["visible_mask"])
    close(visible[known], truth[known], "sample_determined_truth", atol=1e-8)
    ids = np.flatnonzero(~known)
    residual_lo, residual_hi, A = [], [], []
    for g, total in enumerate(central):
        in_block = (ids // bs == g).astype(float)
        if not in_block.any():
            residual_lo.append(0.); residual_hi.append(0.); continue
        base = visible[g*bs:(g+1)*bs]
        remain = float(total - np.nansum(base))
        residual_lo.append(max(0., remain-tau*total)); residual_hi.append(remain+tau*total)
        A.extend([in_block, -in_block])
    if len(ids):
        close(residual_lo, json.loads(state["residual_lower"]), "sample_residual_lower")
        close(residual_hi, json.loads(state["residual_upper"]), "sample_residual_upper")
    b = []
    for g in range(len(central)):
        if np.any(ids // bs == g): b.extend([residual_hi[g], -residual_lo[g]])
    for k, (a, z) in enumerate(PAIRS):
        coefficients = 2*(pred[z]-pred[a])/24
        constant = float(np.sum(pred[a]**2-pred[z]**2)/24 + np.sum(coefficients[known]*visible[known]))
        cc = float(np.sum((pred[a,known]-visible[known])**2-(pred[z,known]-visible[known])**2))
        if tau == 0 or known.all():
            close(cc, float(state[f"cc_numerator_{k}"]), "sample_complete_case_numerator")
        direct = float(np.mean((pred[a]-truth)**2-(pred[z]-truth)**2))
        if len(ids):
            for direction, field in ((1., "lower"), (-1., "upper")):
                result = linprog(direction*coefficients[ids], A_ub=np.array(A), b_ub=np.array(b), bounds=(0, None), method="highs")
                assert result.success, result.message
                witness = visible.copy(); witness[ids] = result.x
                assert np.all(witness >= -1e-8)
                totals = witness.reshape(-1,bs).sum(axis=1)
                assert np.all(totals >= (1-tau)*central-1e-7*np.maximum(1,central))
                assert np.all(totals <= (1+tau)*central+1e-7*np.maximum(1,central))
                endpoint = constant + float(np.dot(coefficients[ids], result.x))
                actual_mse = float(np.mean((pred[a]-witness)**2-(pred[z]-witness)**2))
                close(endpoint, actual_mse, "sample_witness_direct_mse", atol=1e-7)
                close(endpoint, float(state[f"{field}_{k}"]), "sample_LP_endpoint", atol=1e-7)
                COUNTS["independent_LP_endpoint_witnesses"] += 1
        else:
            close([direct,direct], [float(state[f"lower_{k}"]),float(state[f"upper_{k}"])], "sample_fully_reconstructed_MSE", atol=1e-7)
            COUNTS["fully_reconstructed_pair_intervals"] += 1
        lo,hi = float(state[f"lower_{k}"]),float(state[f"upper_{k}"])
        assert lo-1e-7*max(1,abs(direct)) <= direct <= hi+1e-7*max(1,abs(direct))
        COUNTS["sample_truth_enclosures"] += 1
    COUNTS["numerical_sample_links"] += 1


def verify_traces(metadata, forecasts, dayrows, future, copy_masks, samples):
    accumulated = {}
    expected_days=sum(r["test_days"] for r in metadata.values())
    expected_conditions=set(product((2,6,12),("contiguous","scattered","high_demand"),(1103,2207,3301),(6,24),(0.,.01,.05),REGIMES))
    state_groups = groupby(rows("study_period_archive_states.csv.gz"), datekey)
    link_groups = groupby(rows("study_period_archive_links.csv.gz"), datekey)
    aggregate_groups = groupby(rows("study_period_archive_aggregates.csv.gz"), datekey)
    for ss, ll, aa in zip_longest(state_groups, link_groups, aggregate_groups):
        assert ss is not None and ll is not None and aa is not None
        day, siter = ss; assert ll[0] == aa[0] == day
        states = {r["state_id"]:r for r in siter}
        links = list(ll[1]); snapshots = {r["aggregate_snapshot_id"]:r for r in aa[1]}
        assert len(links) == 324 and len(snapshots) == 6 and len(dayrows[day]) == 24
        COUNTS["daily_states"] += len(states); COUNTS["aggregate_snapshots"] += 6
        COUNTS["meter_days"] += 1
        arrays = {}
        for sid,s in states.items():
            visible, eligible = int(s["visible_mask"]), int(s["query_eligible_mask"])
            assert (visible ^ eligible) == FULL and not (visible & eligible)
            assert visible.bit_count() == int(s["observed_count"])
            arrays[sid] = np.array([[float(s[f"{kind}_{i}"]) for kind in KINDS] for i in range(6)])
            arr = arrays[sid]
            assert np.isfinite(arr[:,:4]).all()
            epsilon = 1e-8*np.maximum(1,np.max(np.abs(arr[:,:4]),axis=1))
            assert np.all(arr[:,0] <= arr[:,1]+epsilon)
            assert np.all(arr[:,2] <= arr[:,0]+epsilon) and np.all(arr[:,3] >= arr[:,1]-epsilon)
            if visible == FULL:
                assert int(s["block_hours"]) == 0 and float(s["total_tolerance"]) == -1
                close(arr[:,0],arr[:,1],"fully_observed_width")
                close(arr[:,2],arr[:,0],"fully_observed_individual_lower")
                close(arr[:,3],arr[:,0],"fully_observed_individual_upper")
                close(arr[:,4]/24,arr[:,0],"fully_observed_complete_case")
                for j in (5,6,7):
                    close(arr[:,j],arr[:,0],"fully_observed_imputation")
                assert s["residual_bounds_sha256"] == array_sha([])
            if day[0] != "blem_counters":
                lows,ups=json.loads(s["residual_lower"]),json.loads(s["residual_upper"])
                assert array_sha(lows+ups) == s["residual_bounds_sha256"]
                if visible!=FULL:
                    bs=int(s["block_hours"])
                    for g,upper in enumerate(ups):
                        if upper==0:
                            assert not (eligible & (((1<<bs)-1) << (g*bs)))
        for snap in snapshots.values():
            assert int(snap["source_row_start"]) == min(dayrows[day])
            assert int(snap["source_row_end"]) == max(dayrows[day])
            if day[0] != "blem_counters":
                central,lo,hi = [json.loads(snap[k]) for k in ("central_totals","total_lower","total_upper")]
                assert array_sha(central) == snap["central_totals_sha256"]
                assert array_sha(lo+hi) == snap["total_bounds_sha256"]
                tau=float(snap["total_tolerance"])
                close(lo,np.array(central)*(1-tau),"declared_total_lower")
                close(hi,np.array(central)*(1+tau),"declared_total_upper")
        cases_today = {}
        initial_masks={}
        day_number=(datetime.fromisoformat(day[2])-datetime(1970,1,1)).days
        copied_truth=None
        if day[0]!="blem_counters" and copy_masks[day]==FULL:
            copied_truth=np.array([float(forecasts[future[i]]["daily"]) for i in dayrows[day]])
        used_states=set()
        for r in links:
            sid = r["state_id"]; s = states[sid]; used_states.add(sid)
            arr = arrays[sid]
            gap,seed,bs,tau = int(r["gap_hours"]),int(r["seed"]),int(r["block_hours"]),float(r["total_tolerance"])
            key=(*day[:2],gap,r["pattern"],seed,bs,tau,r["regime"])
            local=key[2:]; assert local not in cases_today; cases_today[local]=arr
            assert r["regime"] in REGIMES
            initial,copied,deduced,visible,eligible=[int(r[n]) for n in ("initial_missing_mask","archive_copy_mask","aggregate_deduced_mask","visible_mask","query_eligible_mask")]
            maskkey=(gap,r["pattern"],seed)
            if maskkey in initial_masks:
                assert initial_masks[maskkey]==initial
            else:
                initial_masks[maskkey]=initial
                COUNTS["distinct_daily_masks"]+=1
                if r["pattern"] in ("contiguous","scattered"):
                    rng=np.random.default_rng(np.random.SeedSequence([seed,day_number,(2,6,12).index(gap)]))
                    if r["pattern"]=="contiguous":
                        start=int(rng.integers(0,25-gap));wanted=range(start,start+gap)
                    else:wanted=rng.choice(24,gap,replace=False)
                    assert initial==sum(1<<int(i) for i in wanted)
                    COUNTS["independent_RNG_masks"]+=1
                elif copied_truth is not None:
                    wanted=ORACLE_MASK_CORRECTIONS.get((*day,gap),np.argsort(copied_truth,kind="stable")[-gap:])
                    assert initial==sum(1<<int(i) for i in wanted)
                    COUNTS["copy_reconstructed_oracle_masks_with_frozen_corrections"]+=1
            assert initial.bit_count()==gap and not (copied&deduced)
            assert (copied|deduced) & ~initial == 0
            assert visible == (FULL ^ initial) | copied | deduced
            assert eligible == (FULL ^ visible) and eligible & (copied|deduced) == 0
            assert visible==int(s["visible_mask"]) and eligible==int(s["query_eligible_mask"])
            assert copied == (initial & copy_masks[day] if r["regime"]==REGIMES[1] else 0)
            if visible!=FULL:
                assert int(s["block_hours"])==bs and float(s["total_tolerance"])==tau
            snap=snapshots[r["aggregate_snapshot_id"]]
            assert int(snap["block_hours"])==bs and float(snap["total_tolerance"])==tau
            if tau==0:
                for start in range(0,24,bs):
                    assert (eligible & (((1<<bs)-1)<<start)).bit_count()!=1
            if key not in accumulated:
                accumulated[key]=[np.zeros((6,8)),0,0,np.zeros(6),0,np.zeros(3,dtype=np.int64)]
            total=accumulated[key]
            total[0]+=np.nan_to_num(arr,nan=0.)
            nobs=visible.bit_count(); total[1]+=nobs; total[2]+=1
            if tau==0: total[3]+=arr[:,4]/nobs
            total[4]+=int(nobs==24); total[5]+=[gap,copied.bit_count(),deduced.bit_count()]
            COUNTS["daily_state_links"]+=1
            if day in samples and seed==1103:
                numerical_sample(r,s,snap,forecasts,dayrows[day],future)
        assert used_states==set(states)
        assert set(cases_today)==expected_conditions
        for local,arr in cases_today.items():
            if local[-1]!=REGIMES[0]: continue
            other=cases_today[(*local[:-1],REGIMES[1])]
            eps=1e-8*np.maximum(1,np.max(np.abs(arr[:,:4]),axis=1))
            assert np.all(other[:,0]>=arr[:,0]-eps) and np.all(other[:,1]<=arr[:,1]+eps)
            assert np.all(other[:,2]>=arr[:,2]-eps) and np.all(other[:,3]<=arr[:,3]+eps)
            COUNTS["daily_pair_interval_nonwidening"]+=12
        if COUNTS["meter_days"]%500==0:
            print(f"Independent trace check: {COUNTS['meter_days']} / {expected_days} meter-days",flush=True)
    assert COUNTS["meter_days"]==expected_days and COUNTS["daily_state_links"]==expected_days*324
    return accumulated


def compare_tables(actual, expected, keys, label):
    a=actual.set_index(keys).sort_index(); b=expected.set_index(keys).sort_index()
    assert a.index.is_unique and b.index.is_unique and a.index.equals(b.index), label
    assert set(a.columns)==set(b.columns), (label,set(a.columns)^set(b.columns))
    for col in a.columns:
        if a[col].dtype==bool or b[col].dtype==bool:
            assert np.array_equal(a[col],b[col]),(label,col)
        else:
            close(a[col].to_numpy(),b[col].to_numpy(),label+":"+col)


def verify_period(accumulated, metadata):
    frame=pd.read_csv(input_path("study_period_archive_cases.csv"),float_precision="round_trip")
    assert len(frame)==len(metadata)*6480
    assert not frame.duplicated(KEYS).any()
    seen=set()
    for r in frame.itertuples(index=False):
        key=(r.cohort,r.meter,r.gap_hours,r.pattern,r.seed,r.block_hours,r.total_tolerance,r.regime)
        sums,den,days,legacy,known,counts=accumulated[key]
        pair=PAIRS.index((MODELS.index(r.model_a),MODELS.index(r.model_b)))
        mi=METHODS.index(r.method)
        ident=(*key,pair,mi); assert ident not in seen; seen.add(ident)
        assert days==r.days==metadata[key[:2]]["test_days"] and r.full_target_denominator==24*days
        assert den==r.observed_target_denominator
        assert known==r.fully_known_days
        assert tuple(counts)==(r.originally_missing_coordinates,r.free_archive_coordinates,r.aggregate_determined_coordinates)
        scale=max(metadata[key[:2]]["training_mean_kwh"]**2,1e-12)
        close(scale,r.normalization_scale,"period_scale")
        if mi==0: lo,hi=sums[pair,:2]/days
        elif mi==1: lo,hi=sums[pair,2:4]/days
        elif mi==2: lo=hi=sums[pair,4]/den
        else: lo=hi=sums[pair,mi+2]/days
        close([lo,hi],[r.mean_lower_or_point,r.mean_upper_or_point],"period_endpoints_and_points")
        close((hi-lo)/scale,r.normalized_width,"period_normalized_width")
        assert r.decision==sign(lo,hi) and r.unresolved==int(r.decision==0)
        assert r.wrong_decision==int(r.decision!=0 and r.decision!=sign(r.true_mean_gap))
        if mi<2:
            epsilon=1e-8*max(1,abs(r.true_mean_gap))
            assert lo-epsilon<=r.true_mean_gap<=hi+epsilon
            assert not r.wrong_decision
            COUNTS["whole_period_truth_enclosures"]+=1
        if r.total_tolerance==0:
            close(legacy[pair]/days,r.closed_daily_mean_complete_case,"legacy_daily_CC_mean")
        else:
            assert mi<2 and math.isnan(r.closed_daily_mean_complete_case)
        COUNTS["whole_period_rows_reconstructed"]+=1
    assert len(accumulated)==len(metadata)*324
    return frame


def verify_summaries(frame):
    for suffix,keys in (
        ("scenarios",["cohort","regime","gap_hours","pattern","block_hours","total_tolerance","method"]),
        ("cohorts",["cohort","regime","total_tolerance","method"]),
        ("pairs",["cohort","model_a","model_b","regime","total_tolerance","method"])):
        records=[]
        for key,group in frame.groupby(keys):
            decisions=int(np.count_nonzero(group.decision))
            wrong=int(group.wrong_decision.sum())
            records.append(dict(zip(keys,key),comparisons=len(group),decisions=decisions,
                unresolved=len(group)-decisions,wrong_decisions=wrong,
                mean_normalized_width=math.fsum(group.normalized_width)/len(group),
                coverage=decisions/len(group),error_among_decisions=wrong/decisions if decisions else np.nan))
        expected=pd.DataFrame(records)
        actual=pd.read_csv(OUT/f"study_period_archive_{suffix}.csv")
        actual=actual[actual.cohort.isin(set(frame.cohort))]
        compare_tables(actual,expected,keys,f"summary_{suffix}")
        COUNTS[f"{suffix}_summary_rows"]=len(records)
    records=[]; keys=["cohort","gap_hours","pattern","block_hours","regime"]
    identity=lambda r:(r.meter,r.model_a,r.model_b,r.seed)
    for key,g in frame[frame.total_tolerance==0].groupby(keys):
        certified={identity(r):r for r in g[g.method=="paired_bounds"].itertuples(index=False)}
        target=sum(r.decision!=0 for r in certified.values())
        for method in METHODS[2:]:
            candidates=list(g[g.method==method].itertuples(index=False))
            assert {identity(r) for r in candidates}==set(certified)
            candidates=[r for r in candidates if r.decision!=0]
            candidates.sort(key=lambda r:(-abs(r.mean_lower_or_point)/r.normalization_scale,*identity(r)))
            chosen=candidates[:target]
            matching=sum(certified[identity(r)].decision==r.decision for r in chosen)
            unresolved=sum(certified[identity(r)].decision==0 for r in chosen)
            records.append(dict(zip(keys,key),method=method,comparisons=len(certified),paired_decisions=target,
                paired_wrong_decisions=sum(r.wrong_decision for r in certified.values()),selected_decisions=len(chosen),
                available_point_decisions=len(candidates),wrong_decisions=sum(r.wrong_decision for r in chosen),
                coverage_exactly_matched=len(chosen)==target,selected_with_matching_certificate=matching,
                selected_paired_unresolved=unresolved,selected_with_opposite_certificate=len(chosen)-matching-unresolved,
                minimum_selected_normalized_margin=abs(chosen[-1].mean_lower_or_point)/chosen[-1].normalization_scale if chosen else np.nan))
    actual=pd.read_csv(OUT/"study_period_archive_matched.csv")
    actual=actual[actual.cohort.isin(set(frame.cohort))]
    compare_tables(actual,pd.DataFrame(records),keys+["method"],"matched_coverage")
    COUNTS["matched_coverage_rows"]=len(records)


def verify_cross_summary_consistency():
    """All-cohort aggregate consistency, not BLEM case-level reconstruction."""
    keys=["cohort","regime","total_tolerance","method"]
    cohorts=pd.read_csv(OUT/"study_period_archive_cohorts.csv")
    for suffix in ("scenarios","pairs"):
        source=pd.read_csv(OUT/f"study_period_archive_{suffix}.csv")
        records=[]
        for key,g in source.groupby(keys):
            n=int(g.comparisons.sum());d=int(g.decisions.sum());w=int(g.wrong_decisions.sum())
            records.append(dict(zip(keys,key),comparisons=n,decisions=d,unresolved=int(g.unresolved.sum()),
                wrong_decisions=w,mean_normalized_width=math.fsum(g.mean_normalized_width*g.comparisons)/n,
                coverage=d/n,error_among_decisions=w/d if d else np.nan))
        compare_tables(cohorts,pd.DataFrame(records),keys,"all_cohort_cross_summary_"+suffix)
        COUNTS["all_cohort_cross_summary_rows"]+=len(records)
    scenarios=pd.read_csv(OUT/"study_period_archive_scenarios.csv")
    paired=scenarios[(scenarios.total_tolerance==0)&(scenarios.method=="paired_bounds")]
    pkeys=["cohort","gap_hours","pattern","block_hours","regime"]
    index=paired.set_index(pkeys)
    for r in pd.read_csv(OUT/"study_period_archive_matched.csv").itertuples(index=False):
        p=index.loc[tuple(getattr(r,k) for k in pkeys)]
        assert r.comparisons==p.comparisons and r.paired_decisions==p.decisions
        assert r.paired_wrong_decisions==p.wrong_decisions
        assert 0<=r.wrong_decisions<=r.selected_decisions<=min(r.available_point_decisions,r.paired_decisions)
        assert r.selected_decisions==min(r.available_point_decisions,r.paired_decisions)
        assert r.coverage_exactly_matched==(r.selected_decisions==r.paired_decisions)
        assert r.selected_with_matching_certificate+r.selected_paired_unresolved+r.selected_with_opposite_certificate==r.selected_decisions
        COUNTS["all_cohort_matched_count_consistency_rows"]+=1


def reconcile_legacy(frame):
    keys=[k for k in KEYS if k!="regime"]
    old=pd.read_csv(OUT/"study_period_comparisons.csv",float_precision="round_trip").set_index(keys)
    new=frame[frame.regime==REGIMES[0]].set_index(keys)
    old=old.loc[new.index]
    close(new.true_mean_gap,old.true_mean_gap,"legacy_reference_gap",atol=1e-10)
    assert np.array_equal(new.days,old.days)
    summaries=[]
    for method in METHODS:
        a=new.xs(method,level="method");b=old.xs(method,level="method")
        if method in METHODS[:2]+("uniform","seasonal_profile"):
            close(a.mean_lower_or_point,b.mean_lower_or_point,"legacy_"+method+"_lower")
            close(a.mean_upper_or_point,b.mean_upper_or_point,"legacy_"+method+"_upper")
        if method in METHODS[:2]:
            assert np.array_equal(a.decision,b.decision)
            COUNTS["legacy_interval_rows_reconciled"]+=len(a)
        summaries.append({"method":method,"rows":len(a),"changed_decisions":int(np.count_nonzero(a.decision.to_numpy()!=b.decision.to_numpy()))})
    return summaries


def main():
    global PUBLIC_MODE,FILEMAP,ORACLE_MASK_CORRECTIONS
    start=time.perf_counter()
    manifest=json.loads((OUT/"study_period_archive_manifest.json").read_text())
    report=json.loads((OUT/"study_period_archive.json").read_text())
    assert report["status"]=="passed" and manifest["within_period_raw_access_equals_saved_archive_here"]
    assert set(manifest["regimes"])==set(REGIMES)
    assert sha(OUT/"study_period_archive_manifest.json")==report["manifest_sha256"]
    assert sha(OUT/"study_period_archive.py")==report["script_sha256"]==manifest["script_sha256"]
    detailed=["study_period_archive_"+suffix for suffix in ("cases.csv","sources.csv","states.csv.gz","links.csv.gz","aggregates.csv.gz")]
    public_manifest=None
    if not all((OUT/name).exists() for name in detailed):
        PUBLIC_MODE=True
        public_manifest=json.loads((OUT/"study_period_archive_public_manifest.json").read_text())
        assert public_manifest["status"]=="passed"
        assert public_manifest["full_analysis_sha256"]==sha(OUT/"study_period_archive.json")
        FILEMAP={full:public for public,full in public_manifest["public_to_full"].items()}
        assert set(FILEMAP)==set(detailed)
        for name,record in public_manifest["public_files"].items():
            assert sha(OUT/name)==record["sha256"] and (OUT/name).stat().st_size==record["bytes"]
        for name,record in public_manifest["omitted_files"].items():
            assert report["output_hashes"][name]==record["sha256"]
    names={FILEMAP.get(name,name) for name in report["output_hashes"]}|{"study_period_archive.json","study_period_archive.py","study_period_archive_manifest.json",
        "study_summary.json","study_period_comparisons.csv","frozen_forecasts.csv","frozen_forecasts.json","study_period_archive_mask_audit.json"}
    if PUBLIC_MODE:names.add("study_period_archive_public_manifest.json")
    source_hashes={name:sha(OUT/name) for name in sorted(names)}
    for name,digest in report["output_hashes"].items():
        if name not in FILEMAP:assert source_hashes[name]==digest,name
    summary=json.loads((OUT/"study_summary.json").read_text())
    for name in ("study_summary.json","study_period_comparisons.csv"):
        assert source_hashes[name]==report["source_hashes"][name]
    export=json.loads((OUT/"frozen_forecasts.json").read_text())
    assert source_hashes["frozen_forecasts.csv"]==export["output_sha256"]
    assert export["source_hashes"]["study_predictions.csv"]==report["source_hashes"]["study_predictions.csv"]
    mask_audit=json.loads((OUT/"study_period_archive_mask_audit.json").read_text())
    assert mask_audit["status"]=="passed" and mask_audit["source_hashes"]["study_predictions.csv"]==report["source_hashes"]["study_predictions.csv"]
    ORACLE_MASK_CORRECTIONS={(r["cohort"],r["meter"],r["day"],r["gap_hours"]):r["original_mask_hours"] for r in mask_audit["changed_oracle_masks"]}
    assert len(ORACLE_MASK_CORRECTIONS)==4
    metadata={(r["cohort"],r["meter"]):r for r in summary["meters"]}
    if PUBLIC_MODE:metadata={key:value for key,value in metadata.items() if key[0]!="blem_counters"}
    forecasts,dayrows,future,copy_masks,samples=load_sources()
    accumulated=verify_traces(metadata,forecasts,dayrows,future,copy_masks,samples)
    frame=verify_period(accumulated,metadata)
    verify_summaries(frame)
    verify_cross_summary_consistency()
    reconciliation=reconcile_legacy(frame)
    expected_states=public_manifest["row_counts"]["study_period_archive_states.csv.gz"]["public_rows"] if PUBLIC_MODE else report["checks"]["states"]
    assert COUNTS["daily_states"]==expected_states
    for name,digest in source_hashes.items(): assert sha(OUT/name)==digest,name
    result={"status":"passed","completed_utc":datetime.now(timezone.utc).isoformat(),
        "wall_seconds":time.perf_counter()-start,"script_sha256":sha(__file__),"source_hashes":source_hashes,
        "verification_mode":"public_UCI_detailed_and_all_cohort_summary_consistency" if PUBLIC_MODE else "full34_local_scalar_trace_reconstruction",
        "counts":dict(COUNTS),"maximum_absolute_discrepancies":dict(MAX_ERRORS),"legacy_reconciliation":reconciliation,
        "numerical_sample_design":{"meters":"Household and lexically first/last original Portugal meters",
            "days":[list(s) for s in sorted(samples)],"conditions":"First seed1103, every gap/mask/block/tolerance and both regimes, all six pairs",
            "target_source":"Bundled UCI daily-persistence forecasts at t+24; complete target reconstruction is possible on each selected day"},
        "scope":{"detailed_period_results":"Reconstructed from archived daily scalar contributions, independently recomputed denominators/signs/normalizations/counts and corresponding aggregation/matched-selection tables: "+("31UCI meters only" if PUBLIC_MODE else "all34 meters"),
            "all_cohort_aggregates":"Scenario and named-pair summaries independently reconcile to cohort summaries; matched count constraints checked for all cohorts",
            "direct_reconstruction":"Timestamp/source-row eligibility checked for "+("UCI only" if PUBLIC_MODE else "all34 meters")+"; UCI copy values hash-checked; BLEM values remain omitted",
            "numerical_endpoints":"Independent SciPy linear programs, feasible primal witnesses and direct paired MSE on fixed UCI samples",
            "mask_checks":"Every contiguous/scattered mask independently regenerated; all other masks checked for cardinality and consistency across information/bound settings. High-demand ranks additionally reconstructed on fully copy-covered UCI days, using four explicit original-source rounding corrections from the separate mask audit.",
            "not_rerun":["Model fitting and training-data eligibility","Every daily numerical bound from raw observations","Boundary-day raw-target numerical validation","Profile/donor reconstruction from raw training observations","BLEM target values and persistence-copy value hashes","Paid-query choices: this analysis is zero-query; separate daily recovery has its own verifier"]+( ["BLEM daily scalar traces and method-specific period cases are deliberately omitted; --raw regeneration is needed for full34 scalar reconstruction"] if PUBLIC_MODE else [])}}
    (OUT/"study_period_archive_audit.json").write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({"status":"passed","wall_seconds":result["wall_seconds"],"counts":result["counts"]}),flush=True)


if __name__=="__main__":
    main()
