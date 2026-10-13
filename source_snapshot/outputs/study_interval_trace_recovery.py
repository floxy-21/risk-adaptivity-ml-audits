"""Frozen-trace sensitivity of exact batch recovery to bounded aggregate totals.

Run with the original study environment. This script writes aggregate results
only, never modifies its inputs, and does not retrain or calibrate meter errors.
The public interval solver is used unchanged. Query choice receives visible
information only; hidden target answers are used after the batch is fixed.
"""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from interval_total_recovery import IntervalTotalBlock, optimal_queries, worst_width
from study_archive_access import persistence_lookup, reveal_from_archive
from study_recovery import (decision, prepare_blocks as exact_blocks,
                            optimal_queries as exact_queries,
                            baseline_queries as old_baseline,
                            pair_interval as exact_interval,
                            worst_width as exact_width)

ROOT = Path(__file__).resolve().parents[1]
OUT, WORK = ROOT / 'outputs', ROOT / 'work'
TOLERANCES = (0., .01, .05)
SEEDS = (1103, 2207, 3301)
REGIMES = ('restricted_record_closed', 'saved_forecast_archive_closed')
POLICIES = ('optimal_minimax_width', 'greedy_width_reduction')
METRICS = ('pair_trials', 'decisions', 'wrong_decisions', 'enclosed_truth',
           'initial_width_sum', 'actual_width_sum', 'worst_width_sum',
           'queries_sum', 'free_copy_sum', 'deduced_sum', 'original_missing_sum')
DAY_NS = 86_400_000_000_000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close_visible(observed, lower, upper):
    """Subtract observations; reveal only algebraically determined targets."""
    visible = np.array(observed, dtype=float, copy=True)
    residuals, deduced = [], []
    if len(visible) % 6 or len(lower) != len(visible) // 6 or len(upper) != len(lower):
        raise ValueError('invalid six-hour grid')
    for block_no, start in enumerate(range(0, len(visible), 6)):
        ids = tuple(i for i in range(start, start + 6) if np.isnan(visible[i]))
        fixed = math.fsum(float(visible[i]) for i in range(start, start + 6)
                          if not np.isnan(visible[i]))
        lo, hi = float(lower[block_no]), float(upper[block_no])
        tol = 1e-9 * max(1., abs(lo), abs(hi))
        if not 0 <= lo <= hi or fixed > hi + tol:
            raise ValueError('infeasible total or fixed observations')
        if not ids:
            if fixed < lo - tol:
                raise ValueError('fully observed block outside interval')
            continue
        residual_lo, residual_hi = max(0., lo - fixed), max(0., hi - fixed)
        if residual_hi == 0.:
            visible[list(ids)] = 0.
            deduced.extend(ids)
        elif lo == hi and len(ids) == 1:
            visible[ids[0]] = residual_hi
            deduced.extend(ids)
        else:
            residuals.append((ids, residual_lo, residual_hi))
    return visible, tuple(residuals), tuple(deduced)


def make_blocks(coefficients, residuals):
    return tuple(IntervalTotalBlock(ids, tuple(float(coefficients[i]) for i in ids), lo, hi)
                 for ids, lo, hi in residuals)


def greedy_queries(blocks, budget):
    """One-step batch greedy; no target answers are visible during selection."""
    query = []
    for _ in range(budget):
        candidates = []
        for block in blocks:
            previous = tuple(i for i in query if i in block.indices)
            if worst_width((block,), previous) > 0.:
                candidates.extend(i for i in block.indices if i not in query)
        if not candidates:
            break
        selected = min(candidates, key=lambda i: (worst_width(blocks, (*query, i)), i))
        query.append(selected)
    return tuple(sorted(query))


def choose_queries(coefficients, visible, lower, upper, budget, policy):
    """Information firewall: this interface accepts no hidden target vector."""
    closed, residuals, _ = close_visible(visible, lower, upper)
    blocks = make_blocks(coefficients, residuals)
    if policy == POLICIES[0]:
        result = optimal_queries(blocks, budget)
        query, cost = result.queries, result.worst_case_width
    elif policy == POLICIES[1]:
        query = greedy_queries(blocks, budget)
        cost = worst_width(blocks, query)
    else:
        raise ValueError('unknown policy')
    assert len(query) <= budget and len(set(query)) == len(query)
    assert all(np.isnan(closed[i]) for i in query)
    return query, cost


def pair_interval(a, b, observed, lower, upper):
    """Sharp endpoints evaluated at witnesses using stable paired losses."""
    visible, residuals, _ = close_visible(observed, lower, upper)
    c = 2. * (b - a) / len(a)
    ylo, yhi = np.nan_to_num(visible, nan=0.), np.nan_to_num(visible, nan=0.)
    for ids, lo, hi in residuals:
        smallest = min(ids, key=lambda i: (c[i], i))
        largest = max(ids, key=lambda i: (c[i], -i))
        ylo[smallest] = hi if c[smallest] < 0 else lo
        yhi[largest] = hi if c[largest] > 0 else lo
    def value(y):
        return math.fsum(float(v) for v in ((a-b) / len(a)) * ((a-y)+(b-y)))
    return value(ylo), value(yhi)


def integration_checks():
    # A positive-width interval never identifies its last unknown coordinate.
    observed = np.array([1., 1., 1., 1., 1., np.nan])
    closed, _, ids = close_visible(observed, [6.], [6.])
    assert ids == (5,) and closed[5] == 1.
    closed, residual, ids = close_visible(observed, [5.9], [6.1])
    assert not ids and np.isnan(closed[5]) and residual[0][1] < residual[0][2]
    zeros, _, ids = close_visible(np.full(6, np.nan), [0.], [0.])
    assert len(ids) == 6 and np.all(zeros == 0)
    # Independent LP extrema exercise total subtraction, signs and paid answers.
    rng = np.random.default_rng(9183)
    lp_calls = 0
    max_error = 0.
    for _ in range(24):
        truth = rng.integers(0, 12, size=6).astype(float) / 4
        a, b = rng.integers(0, 20, size=(2, 6)).astype(float) / 4
        mask = rng.choice(6, size=4, replace=False)
        observed = truth.copy()
        observed[mask] = np.nan
        epsilon = TOLERANCES[_ % 3]
        total = truth.sum()
        lower, upper = [total*(1-epsilon)], [total*(1+epsilon)]
        c = 2*(b-a)/6
        for policy in POLICIES:
            query, predicted = choose_queries(c, observed, lower, upper, 2, policy)
            # Same visible state must give the same batch, independent of caller truth.
            assert (query, predicted) == choose_queries(c, observed.copy(), lower, upper, 2, policy)
            recovered = observed.copy()
            recovered[list(query)] = truth[list(query)]
            for current in (observed, recovered):
                got = pair_interval(a, b, current, lower, upper)
                bounds = [(0, None) if np.isnan(x) else (x, x) for x in current]
                constant = math.fsum(float(x) for x in (a*a-b*b)/6)
                endpoints = []
                for sign in (1, -1):
                    lp = linprog(sign*c, A_ub=[np.ones(6), -np.ones(6)],
                                 b_ub=[upper[0], -lower[0]], bounds=bounds, method='highs')
                    assert lp.success, lp.message
                    endpoints.append(constant + sign*lp.fun)
                    lp_calls += 1
                error = max(abs(got[0]-endpoints[0]), abs(got[1]-endpoints[1]))
                max_error = max(max_error, error)
                np.testing.assert_allclose(got, endpoints, atol=1e-9, rtol=1e-10)
            lo, hi = pair_interval(a, b, recovered, lower, upper)
            assert hi-lo <= predicted + 1e-8
    return {'independent_lp_endpoint_calls': lp_calls, 'max_lp_absolute_error': max_error,
            'exact_singleton_closed': True, 'uncertain_singleton_retained': True,
            'zero_upper_closed': True, 'query_interface_excludes_hidden_truth': True}


def run_meter(task):
    started = time.perf_counter()
    cohort, meter, meter_data, models, training_mean = task
    norm = max(float(training_mean)**2, 1e-12)
    lookup = persistence_lookup(meter_data[['timestamp', 'daily']])
    stats = defaultdict(lambda: np.zeros(len(METRICS)))
    checks = defaultdict(int)
    max_initial_error = max_objective_error = max_copy_error = 0.
    for day, group in meter_data.groupby('day', sort=True):
        group = group.sort_values('timestamp')
        assert len(group) == 24
        truth = group.truth_kwh.to_numpy()
        forecasts = group[models].to_numpy().T
        timestamps = group.timestamp.tolist()
        totals = truth.reshape(-1, 6).sum(axis=1)
        epochday = int(pd.Timestamp(day).value // DAY_NS)
        for seed in SEEDS:
            rng = np.random.default_rng(np.random.SeedSequence([seed, epochday, 1]))
            start = int(rng.integers(0, 19))
            observed = truth.copy()
            observed[start:start+6] = np.nan
            archive, copied = reveal_from_archive(timestamps, observed, lookup)
            if copied:
                error = float(np.max(abs(archive[list(copied)]-truth[list(copied)])))
                max_copy_error = max(max_copy_error, error)
                assert error <= 1e-12
            for epsilon in TOLERANCES:
                lower, upper = (1-epsilon)*totals, (1+epsilon)*totals
                for regime, original_visible, free_count in (
                        (REGIMES[0], observed, 0), (REGIMES[1], archive, len(copied))):
                    visible, residuals, deduced = close_visible(original_visible, lower, upper)
                    if deduced:
                        np.testing.assert_allclose(visible[list(deduced)], truth[list(deduced)],
                                                   atol=1e-8, rtol=1e-10)
                    for ai, bi in itertools.combinations(range(4), 2):
                        a, b = forecasts[ai], forecasts[bi]
                        c = 2*(b-a)/24
                        blocks = make_blocks(c, residuals)
                        initial = worst_width(blocks, ())
                        initial_bounds = pair_interval(a, b, visible, lower, upper)
                        cache = {(): initial_bounds}
                        true_difference = math.fsum(float(v) for v in ((a-b)/24)*((a-truth)+(b-truth)))
                        true_sign = decision(true_difference, true_difference)
                        allowance = 1e-8 * max(1., abs(true_difference), initial)
                        selected = {}
                        if epsilon == 0:
                            old = exact_blocks(c, original_visible, totals)
                            old_bounds = exact_interval(a, b, original_visible, totals)
                            error = max(abs(x-y) for x,y in zip(initial_bounds, old_bounds))
                            max_initial_error = max(max_initial_error, error)
                            assert error <= allowance
                            checks['zero_tolerance_initial_bound_equivalence'] += 1
                        for budget in (0, 2):
                            for policy in POLICIES:
                                if budget == 0:
                                    query, worst = (), initial
                                elif not blocks:
                                    query, worst = (), 0.
                                elif policy == POLICIES[0]:
                                    result = optimal_queries(blocks, budget)
                                    query, worst = result.queries, result.worst_case_width
                                else:
                                    query = greedy_queries(blocks, budget)
                                    worst = worst_width(blocks, query)
                                assert len(query) <= budget
                                assert all(np.isnan(visible[i]) for i in query)
                                if query not in cache:
                                    recovered = visible.copy()
                                    recovered[list(query)] = truth[list(query)]
                                    cache[query] = pair_interval(a, b, recovered, lower, upper)
                                lo, hi = cache[query]
                                actual = max(0., hi-lo)
                                assert lo <= true_difference+allowance and hi >= true_difference-allowance
                                assert actual <= worst+allowance and worst <= initial+allowance
                                selected[budget, policy] = (query, worst, decision(lo, hi))
                                d = decision(lo, hi)
                                wrong = int(d != 0 and d != true_sign)
                                assert wrong == 0
                                key = (epsilon, regime, seed, models[ai], models[bi], budget, policy)
                                stats[key] += [1, int(d != 0), wrong, 1, initial, actual, worst,
                                               len(query), free_count, len(deduced), 6]
                                checks['policy_budget_evaluations'] += 1
                        assert selected[2, POLICIES[0]][1] <= selected[2, POLICIES[1]][1]+allowance
                        checks['exact_worst_width_no_greater_than_greedy'] += 1
                        if epsilon == 0:
                            for policy in POLICIES:
                                oq = exact_queries(old, 2) if policy == POLICIES[0] else old_baseline(old, 2, policy)
                                newq, neww, newd = selected[2, policy]
                                oldw = exact_width(old, oq)
                                if policy == POLICIES[0]:
                                    error = abs(neww-oldw)
                                    max_objective_error = max(max_objective_error, error)
                                    assert error <= allowance
                                    checks['zero_tolerance_optimal_objective_equivalence'] += 1
                                checks['zero_tolerance_query_comparisons'] += 1
                                checks['zero_tolerance_query_tuple_changes'] += int(newq != oq)
                                recovered = original_visible.copy()
                                recovered[list(oq)] = truth[list(oq)]
                                oldd = decision(*exact_interval(a, b, recovered, totals))
                                checks['zero_tolerance_decision_changes'] += int(newd != oldd)
    rows = []
    for (epsilon, regime, seed, model_a, model_b, budget, policy), values in sorted(stats.items()):
        row = {'cohort':cohort,'meter':meter,'tolerance':epsilon,'regime':regime,
               'mask_seed':seed,'model_a':model_a,'model_b':model_b,'budget':budget,'policy':policy,
               'training_mean_squared':norm, **dict(zip(METRICS, map(float, values)))}
        rows.append(row)
    report = {'cohort':cohort,'meter':meter,'days':meter_data.day.nunique(),
              'checks':dict(checks), 'max_initial_bound_error_at_zero':max_initial_error,
              'max_optimal_objective_error_at_zero':max_objective_error,
              'max_persistence_copy_error':max_copy_error, 'wall_seconds':time.perf_counter()-started}
    return rows, report


def summarize_meter(detail):
    keys = ['cohort','meter','tolerance','regime','budget','policy','training_mean_squared']
    table = detail.groupby(keys, as_index=False)[list(METRICS)].sum()
    for count in ('pair_trials','decisions','wrong_decisions','enclosed_truth','queries_sum',
                  'free_copy_sum','deduced_sum','original_missing_sum'):
        table[count] = table[count].astype(int)
    table['certification'] = table.decisions/table.pair_trials
    table['mean_queries'] = table.queries_sum/table.pair_trials
    table['free_copy_fraction'] = table.free_copy_sum/table.original_missing_sum
    table['deduced_fraction'] = table.deduced_sum/table.original_missing_sum
    for prefix in ('initial','actual','worst'):
        table[f'mean_{prefix}_width'] = table[f'{prefix}_width_sum']/table.pair_trials
        table[f'normalized_{prefix}_width'] = table[f'mean_{prefix}_width']/table.training_mean_squared
    for prefix in ('actual','worst'):
        table[f'{prefix}_width_fraction'] = np.divide(table[f'{prefix}_width_sum'], table.initial_width_sum,
                                                     out=np.zeros(len(table)), where=table.initial_width_sum>0)
    return table


def main():
    started = time.perf_counter()
    protocol = WORK/'interval_trace_protocol.txt'
    if not protocol.exists():
        raise RuntimeError('Freeze protocol before outcomes')
    input_names = ['study_predictions.csv','study_summary.json','study_recovery.py',
                   'study_archive_access.py','study_archive_access_cohorts.csv',
                   'interval_total_recovery.py','energy_rank_bounds.py','run_energy_rank_study.py']
    hashes = {name:sha(OUT/name) for name in input_names}
    summary = json.loads((OUT/'study_summary.json').read_text())
    assert hashes['study_predictions.csv'] == summary['artifacts']['study_predictions.csv']['sha256']
    models = summary['design']['models']
    assert models == ['daily','ridge','hist_gradient_boosting','mlp']
    integration = integration_checks()
    frame = pd.read_csv(OUT/'study_predictions.csv')
    frame['day'] = frame.timestamp.str[:10]
    norms = {(m['cohort'],m['meter']):m['training_mean_kwh'] for m in summary['meters']}
    tasks = [(cohort,meter,group,models,norms[cohort,meter])
             for (cohort,meter),group in frame.groupby(['cohort','meter'],sort=True)]
    rows, provenance = [], []
    with ProcessPoolExecutor(max_workers=2) as pool:
        for result_rows, report in pool.map(run_meter,tasks):
            rows.extend(result_rows)
            provenance.append(report)
            print(datetime.now(timezone.utc).isoformat(timespec='seconds'),report['cohort'],
                  report['meter'],'complete',round(report['wall_seconds'],2),'seconds',flush=True)
    detail = pd.DataFrame(rows)
    meters = summarize_meter(detail)
    group_keys = ['cohort','tolerance','regime','budget','policy']
    metrics = ['certification','mean_queries','free_copy_fraction','deduced_fraction',
               'mean_initial_width','mean_actual_width','mean_worst_width',
               'normalized_initial_width','normalized_actual_width','normalized_worst_width',
               'actual_width_fraction','worst_width_fraction']
    cohorts = meters.groupby(group_keys,as_index=False)[metrics].mean()
    pooled = meters.groupby(group_keys,as_index=False)[['pair_trials','decisions','wrong_decisions','enclosed_truth']].sum()
    cohorts = cohorts.merge(pooled,on=group_keys)
    cohorts['pooled_certification'] = cohorts.decisions/cohorts.pair_trials
    gaps = []
    for key,group in cohorts[cohorts.budget==2].groupby(['cohort','tolerance','regime']):
        exact = group[group.policy==POLICIES[0]].iloc[0]
        greedy = group[group.policy==POLICIES[1]].iloc[0]
        gaps.append({'cohort':key[0],'tolerance':key[1],'regime':key[2],
                     'exact_minus_greedy_certification_pp':100*(exact.certification-greedy.certification),
                     'exact_minus_greedy_normalized_actual_width':exact.normalized_actual_width-greedy.normalized_actual_width,
                     'exact_minus_greedy_normalized_worst_width':exact.normalized_worst_width-greedy.normalized_worst_width,
                     'exact_mean_queries':exact.mean_queries,'greedy_mean_queries':greedy.mean_queries})
    old = pd.read_csv(OUT/'study_archive_access_cohorts.csv')
    old = old[(old.gap_hours==6)&(old.scope=='all_pairs')]
    zero_checks = []
    for row in cohorts[cohorts.tolerance==0].itertuples(index=False):
        old_regime = 'restricted_record' if row.regime==REGIMES[0] else 'available_test_persistence_archive'
        ref = old[(old.cohort==row.cohort)&(old.regime==old_regime)&(old.budget==row.budget)&(old.policy==row.policy)].iloc[0]
        zero_checks.append({'cohort':row.cohort,'regime':row.regime,'budget':row.budget,'policy':row.policy,
                            'certification_difference':row.certification-ref.resolved_fraction,
                            'mean_query_difference':row.mean_queries-ref.mean_queries,
                            'mean_actual_width_difference':row.mean_actual_width-ref.mean_actual_remaining_width,
                            'mean_worst_width_difference':row.mean_worst_width-ref.mean_worst_case_remaining_width})
    output_frames = {'study_interval_trace_recovery.csv':meters,
                     'study_interval_trace_recovery_pair_seed.csv':detail,
                     'study_interval_trace_recovery_cohorts.csv':cohorts,
                     'study_interval_trace_recovery_gaps.csv':pd.DataFrame(gaps)}
    for name,data in output_frames.items():
        data.to_csv(OUT/name,index=False)
    for name,digest in hashes.items():
        assert sha(OUT/name)==digest,'Input changed: '+name
    totals = defaultdict(int)
    for report in provenance:
        for key,value in report['checks'].items():
            totals[key] += value
    result = {'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
              'wall_seconds':time.perf_counter()-started,'python':platform.python_version(),
              'numpy':np.__version__,'regimes':list(REGIMES),'tolerances':list(TOLERANCES),
              'seeds':list(SEEDS),'budgets':[0,2],'policies':list(POLICIES),'meters':len(tasks),
              'heldout_meter_days':sum(p['days'] for p in provenance),
              'checks':{**dict(totals),'all_truth_enclosed':True,'wrong_certificates':0,
                        'actual_width_le_predicted_worst':True,'no_paid_observed_or_determined_queries':True,
                        'source_artifacts_unchanged':True},
              'integration_checks':integration,'cohort_results':cohorts.to_dict('records'),
              'exact_vs_greedy':gaps,'zero_tolerance_reconciliation':zero_checks,
              'provenance_by_meter':provenance,'source_hashes':{**hashes,Path(__file__).name:sha(__file__)},
              'protocol_sha256':sha(protocol),'output_hashes':{name:sha(OUT/name) for name in output_frames},
              'interpretation':'Retrospective original-panel sensitivity with constructed total intervals, not measured instrument calibration. All exact deductions and documented saved-persistence copies are free. Two queries per DAY and MODEL PAIR; unchanged complete-target forecasting. Equal-cost conditional width objective; no field cost or latency claim. Macro means average meters within cohort. Zero-width fraction is defined as zero. Repeated cases are dependent.',
              'distribution':'Aggregate statistics only; no hourly BLEM readings or persistence copies.'}
    (OUT/'study_interval_trace_recovery.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'status':'passed','wall_seconds':result['wall_seconds'],'checks':result['checks'],
                      'exact_vs_greedy':gaps},indent=2),flush=True)


if __name__ == '__main__':
    main()
