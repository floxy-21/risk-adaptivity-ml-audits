"""One-shot confirmation on the next training-selected, previously unfitted LCL consumers.

freeze: records the development-selected concentration before new model fitting.
run: evaluates all eligible TEST cases once, with no test-driven policy selection.
The earlier failed two-query experiment is never replaced by this experiment.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, itertools, json, math, sys, time
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'work/external_deadline'
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(HERE / 'prototype'))
from evaluate import interval, closure, decision, stream, RevealOracle, safe
from acquisition import select_batch
from policy import select_one as select_uniform
from ridge_policy import select_one as select_guided, make_alpha

MODELS = ['daily', 'ridge', 'hist_gradient_boosting', 'mlp']
PAIRS = list(itertools.combinations(range(4), 2))
SEEDS = [1103, 2207, 3301]
POLICIES = ['ml_decision', 'uniform_decision', 'width_one', 'hara_one', 'uniform_one', 'randomized_one']


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def write(p, v):
    Path(p).write_text(json.dumps(safe(v), indent=2, allow_nan=False)+'\n', encoding='utf-8')


def freeze():
    target = HERE / 'confirmation_protocol.json'
    assert not target.exists(), 'A frozen confirmation must not be silently replaced'
    assert not (HERE / 'confirmation_fitted').exists(), 'Freeze before new fitting'
    grid = read(HERE / 'prototype/ridge_grid/summary.json')
    assert grid['status'] == 'passed'
    rows = [r for r in grid['summaries'] if r['subgroup'] == 'all']
    chosen = min(rows, key=lambda r: (r['macro_mean_requests'], r['kappa']))
    assert chosen['kappa'] == grid['selected_kappa']
    source = read(HERE / 'confirmation_source/manifest.json')
    assert source['status'] == 'passed'
    source_check = read(HERE / 'math/confirmation_source_check.json')
    assert source_check['status'] == 'passed'
    assert read(HERE / 'math/ridge_independent_check.json')['status'] == 'passed'
    paths = [Path(__file__), HERE / 'prototype/policy.py', HERE / 'prototype/ridge_policy.py',
             HERE / 'prototype/ridge_grid/summary.json', HERE / 'prototype/ridge_grid/pre_run_manifest.json',
             HERE / 'confirmation_source/manifest.json', HERE / 'confirmation_source/hourly.csv',
             HERE / 'confirmation_source/forecast_config.json', OLD / 'forecast/forecast.py',
             HERE / 'math/confirmation_source_check.json', HERE / 'math/ridge_independent_check.json',
             OLD / 'evaluate.py', OLD / 'acquisition/acquisition.py',
             OLD / 'acquisition/compact_secondary.py', ROOT / 'outputs/study_recovery.py',
             ROOT / 'work/randomized_recovery_root/compact_policy.py',
             ROOT / 'work/randomized_recovery_root/compact_randomized.py']
    protocol = {
        'status': 'frozen_before_new_fitting', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'selected_kappa': grid['selected_kappa'], 'selected_ids': source['selected_ids'],
        'selection': 'Next20 training-eligible IDs excluding original20 among frozen lowest100; no substitutions based on test outcomes.',
        'new_cohort_scope': 'Previously unfitted and no evaluated forecast/acquisition outcomes. Source quality counts for all100 were already known; same source and calendar as development.',
        'alpha': 'kappa*6*max(nonnegative Ridge_i,1e-8*max(block mean nonnegative Ridge,1e-12))/sum floored whole-block weights; fixed once, no re-normalization after observing coordinates.',
        'policies': POLICIES, 'batch_size_for_every_policy': 1, 'cap': 6,
        'width_baseline': 'Exact and greedy singleton width minimizers coincide; common lowest-coordinate tie-break. Report one identical baseline.',
        'primary_population': 'All initially non-strictly-certified test comparisons; equal weights for each contributing household.',
        'primary_endpoint': 'Ratio of household-macro mean charged requests to the exhaustively computed hindsight minimum strict-certificate cost, on the same initially uncertified cases with identical household weights.',
        'success_criterion': 'Mean cost ratio<=1.10, no incorrect strict certificates, and full strict coverage at cap. Report ratio for EVERY policy, including equally efficient baselines. Ratio alone is not novel-policy superiority.',
        'endpoint_origin': 'Chosen after development oracle analysis established that even clairvoyant queries cannot improve mean cost by15% over the fair singleton width baseline there. Width already meets the10% development ratio. The unrun15%-mean confirmation proposal is preserved, not represented as a preregistered completed experiment.',
        'oracle': 'Exhaustive subsets of initially unknown targets, hidden values used ONLY for this explicitly clairvoyant benchmark. Same strict numerical certificate and aggregate closure. Ratio of macro means, not mean per-case ratios.',
        'ties': 'Retain all initially non-strictly-certified cases. If any cannot obtain a strict certificate even with all targets, report their exact/numerical tie counts, fail the full-strict-coverage criterion, and do not silently omit them to claim success. Report efficiency on the strict-certifiable stratum separately if needed.',
        'uncertainty': {'replicates': 2000, 'seed': 8241, 'unit': 'household',
                        'percentiles': [2.5, 97.5], 'baseline': 'Minimum of width and Hara means recomputed within every bootstrap replicate.',
                        'interpretation': 'Descriptive across this deterministic consumer panel, not a population confidence guarantee.'},
        'primary_uncertainty': 'Paired-household bootstrap2000 draws seed8241, descriptive percentile interval of ratio of means; not a representative-population guarantee. Report all-case and initially-uncertified ratios separately.',
        'secondary': 'Relative mean saving against better width/Hara with paired bootstrap; B80 integer0..6; all-case and learned-only coverage; per-pair/per-household means and planning time; uniform/randomized singleton comparators and uniform-Dirichlet ablation.',
        'historical_distinction': 'New endpoint motivated by development diagnosis and policy selected after the old failed experiment, explicitly declared before new-consumer evaluation. Does not revise or pass the old15% B80 hypothesis.',
        'forecast_specifications': 'Original frozen causal LCL Ridge, HGB, MLP and persistence unchanged; trainJan-Sep2013; validationOct-Dec2013 only for original Hara calibration; testJan-Feb2014.',
        'information': 'Same constructed early cutoff at startD+1; all issued records accessible; later noonD+1 archive consumes all24 direct persistence copies before evaluation.',
        'query_cost': 'One hourly record request; last coordinate/surviving total free; pair-specific, not shared system or measured monetary cost.',
        'replication_paths': 'Three prescribed mask and stochastic streams per day, not exact expectations over randomized trajectories.',
        'input_hashes': {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}}
    write(target, protocol)
    print(json.dumps({'status': 'frozen', 'kappa': grid['selected_kappa'], 'households': source['selected_ids']}, indent=2))


def trajectory(policy, a, b, initial, totals, oracle, mean, sd, alpha, key):
    observed = initial.copy()
    lo, hi = interval(a, b, observed, totals)
    status, _ = decision(lo, hi)
    initial_status = status
    paid, trace = [], []
    planning = 0.
    oracle.validate_interval(a, b, lo, hi)
    while status == 'unresolved' and len(paid) < 6:
        started = time.perf_counter()
        if policy == 'ml_decision':
            selected = select_guided(a, b, observed, totals, alpha)
        elif policy in ['uniform_decision', 'width_one']:
            objective = 'decision_probability' if policy == 'uniform_decision' else 'exact_width_one'
            selected = select_uniform(a, b, observed, totals, objective=objective)
        else:
            selected = select_batch(policy.removesuffix('_one'), a, b, observed, totals, 1,
                                    rng=stream('decision-confirmation', key, policy, len(paid)),
                                    surrogate_mean=mean, surrogate_sd=sd)
        planning += time.perf_counter()-started
        query = selected['query_indices']
        assert len(query) == 1 and query[0] not in paid and np.isnan(observed[query[0]])
        before = [lo, hi]
        values = oracle.reveal(query)
        observed[query] = values
        paid.extend(query)
        observed, deductions = closure(observed, totals)
        lo, hi = interval(a, b, observed, totals)
        status, _ = decision(lo, hi)
        oracle.validate_interval(a, b, lo, hi)
        tol = 1e-9*max(1., abs(lo), abs(hi), *map(abs, before))
        assert lo >= before[0]-tol and hi <= before[1]+tol
        trace.append({'query': query[0], 'value': float(values[0]), 'bounds': [lo, hi],
                      'status': status, 'cost': len(paid), 'deductions': deductions,
                      'chosen_probability': selected.get('chosen', {}).get('certificate_probability'),
                      'chosen': selected.get('chosen'), 'diagnostics': selected.get('diagnostics')})
    return {'initial_status': initial_status, 'final_status': status, 'paid_requests': len(paid),
            'certification_cost': len(paid) if status in ['a', 'b'] else None,
            'planning_seconds': planning, 'trace': trace}


def summarize(out):
    df = pd.read_csv(out / 'cases.csv')
    summaries, curves = [], []
    for population, group in [('all', df), ('initially_uncertified', df[~df.initial_status.isin(['a', 'b'])]),
                              ('learned_initially_uncertified', df[df.learned_pair & ~df.initial_status.isin(['a', 'b'])])]:
        for policy, rows in group.groupby('policy'):
            coverage = []
            for budget in range(7):
                value = float(rows.assign(cert=rows.certification_cost.notna() & (rows.certification_cost <= budget))
                              .groupby('household_id').cert.mean().mean())
                coverage.append(value)
                curves.append(dict(population=population, policy=policy, budget=budget, coverage=value))
            summaries.append(dict(population=population, policy=policy, cases=len(rows),
                                  households=int(rows.household_id.nunique()),
                                  macro_mean_requests=float(rows.groupby('household_id').paid_requests.mean().mean()),
                                  pooled_mean_requests=float(rows.paid_requests.mean()),
                                  B80=next((b for b, v in enumerate(coverage) if v >= .8), None),
                                  coverage=coverage, unresolved=int((rows.final_status == 'unresolved').sum()),
                                  numerical_ties=int((rows.final_status == 'numerical_tie').sum()),
                                  planning_mean_ms=float(rows.planning_seconds.mean()*1000)))
    pd.DataFrame(curves).to_csv(out / 'coverage_curves.csv', index=False, float_format='%.17g')
    conditional = df[~df.initial_status.isin(['a', 'b'])]
    by_house = conditional.groupby(['household_id', 'policy']).paid_requests.mean().unstack()
    by_house.to_csv(out / 'household_costs.csv', float_format='%.17g')
    conditional.groupby(['pair', 'policy']).paid_requests.mean().unstack().to_csv(out / 'pair_costs.csv', float_format='%.17g')
    means = by_house.mean()
    baseline = min(['width_one', 'hara_one'], key=lambda p: (means[p], p))
    reduction = 1-means['ml_decision']/means[baseline]
    rng = np.random.default_rng(8241)
    bootstrap = []
    for _ in range(2000):
        draw = by_house.iloc[rng.integers(0, len(by_house), len(by_house))].mean()
        bootstrap.append(1-draw['ml_decision']/min(draw['width_one'], draw['hara_one']))
    ci = np.percentile(bootstrap, [2.5, 97.5])
    pd.DataFrame({'relative_reduction': bootstrap}).to_csv(out / 'bootstrap.csv', index=False, float_format='%.17g')
    lookup = {r['policy']: r for r in summaries if r['population'] == 'initially_uncertified'}
    report = dict(status='passed', selected_kappa=read(HERE / 'confirmation_protocol.json')['selected_kappa'],
                  case_count=int(df.case_id.nunique()), policy_rows=len(df),
                  eligible_households=int(df.household_id.nunique()),
                  eligible_days=int(df[['household_id', 'day_utc']].drop_duplicates().shape[0]),
                  initially_uncertified_cases=int(conditional.case_id.nunique()),
                  best_primary_baseline=baseline, relative_mean_reduction=float(reduction),
                  descriptive_consumer_bootstrap_interval=ci.tolist(),
                  criterion_met=None, criterion_status='Pending independent exhaustive hindsight-oracle analysis; relative mean reduction is secondary.',
                  summaries=summaries,
                  scope='Frozen new-consumer confirmation of a development-selected policy; same source/calendar, simulated archive/outage/totals, no measured monetary costs.')
    write(out / 'summary.json', report)
    return report


def run():
    protocol = read(HERE / 'confirmation_protocol.json')
    for relative, expected in protocol['input_hashes'].items():
        assert sha(ROOT / relative) == expected, 'Frozen input changed: '+relative
    fd = HERE / 'confirmation_fitted'
    assert read(fd / 'fit_metadata.json')['status'] == 'passed'
    out = HERE / 'confirmation'
    out.mkdir(exist_ok=False)
    started = time.perf_counter()
    files = [fd / x for x in ['forecast_archive.csv', 'reference_targets.csv', 'candidate_days.csv', 'surrogate_parameters.json', 'fit_metadata.json']]
    write(out / 'pre_run_manifest.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
          'protocol_sha256': sha(HERE / 'confirmation_protocol.json'),
          'selected_kappa': protocol['selected_kappa'], 'policies': POLICIES,
          'require_all_source_cases': True, 'rng_salt': 'decision-confirmation',
          'fit_inputs': {p.relative_to(ROOT).as_posix(): sha(p) for p in files},
          'policy_inputs': protocol['input_hashes']})
    arc = pd.read_csv(fd / 'forecast_archive.csv')
    for col in ['target_timestamp_utc', 'issue_time_utc', 'persistence_source_time_utc', 'latest_feature_source_end_utc']:
        arc[col] = pd.to_datetime(arc[col], utc=True)
    ref = pd.read_csv(fd / 'reference_targets.csv')
    ref['stamp'] = pd.to_datetime(ref.timestamp_utc, utc=True)
    candidates = pd.read_csv(fd / 'candidate_days.csv')
    candidates['day_utc'] = pd.to_datetime(candidates.day_utc, utc=True)
    if candidates.eligible.dtype != bool:
        candidates['eligible'] = candidates.eligible.astype(str).str.lower().eq('true')
    candidates = candidates[(candidates.period == 'test') & candidates.eligible].sort_values(['household_id', 'day_utc'])
    assert set(candidates.household_id) <= set(protocol['selected_ids'])
    surrogate = read(fd / 'surrogate_parameters.json')
    surrogate = surrogate.get('households', surrogate)
    rows, n, days, late_certified = [], 0, 0, 0
    with (out / 'source_cases.jsonl').open('w') as sources, (out / 'trajectories.jsonl').open('w') as traces:
        for house, house_days in candidates.groupby('household_id', sort=True):
            ha = arc[arc.household_id == house].sort_values('target_timestamp_utc')
            assert not ha.target_timestamp_utc.duplicated().any()
            lookup = ha.set_index('target_timestamp_utc')
            hr = ref[ref.household_id == house].set_index('stamp')
            learned = ha[MODELS[1:]].notna().any(axis=1)
            assert (ha.loc[learned, 'latest_feature_source_end_utc'] <= ha.loc[learned, 'issue_time_utc']).all()
            sd = float(surrogate[house]['sd_kwh'])
            assert sd == max(float(surrogate[house]['validation_residual_rmse_kwh']),
                             1e-8*float(surrogate[house]['training_mean_kwh']))
            for day in house_days.day_utc:
                stamps = pd.date_range(day, periods=24, freq='h')
                hidden = hr.loc[stamps, 'energy_kwh'].to_numpy(float)
                predictions = lookup.loc[stamps, MODELS].to_numpy(float).T
                assert np.isfinite(hidden).all() and np.isfinite(predictions).all()
                early = day+pd.Timedelta(days=1)
                future = ha[ha.persistence_source_time_utc.isin(stamps) & ha.daily.notna()]
                assert not len(future[future.issue_time_utc <= early])
                copies = future[future.issue_time_utc <= early+pd.Timedelta(hours=12)].sort_values('persistence_source_time_utc')
                assert len(copies) == 24
                late_observed = copies.daily.to_numpy(float)
                assert np.array_equal(late_observed, hidden)
                totals = np.array([math.fsum(hidden[6*g:6*(g+1)]) for g in range(4)])
                alpha = make_alpha(predictions[1], protocol['selected_kappa'])
                for seed in SEEDS:
                    start = int(stream('mask', house, str(day), seed).integers(0, 19))
                    mask = list(range(start, start+6))
                    initial = hidden.copy()
                    initial[mask] = np.nan
                    initial, deductions = closure(initial, totals)
                    for ia, ib in PAIRS:
                        case_id = f'{house}|{day.date()}|{seed}|{ia}-{ib}'
                        a, b = predictions[ia], predictions[ib]
                        source = dict(case_id=case_id, household_id=house, day_utc=str(day), seed=seed,
                                      pair=f'{MODELS[ia]} vs {MODELS[ib]}', learned_pair=ia != 0,
                                      mask=mask, a=a, b=b, totals=totals, initial_observed=initial,
                                      initial_deductions=deductions, surrogate_mean=predictions[1], surrogate_sd=sd,
                                      initial_alpha=alpha)
                        oracle = RevealOracle(hidden)
                        results = {}
                        for policy in POLICIES:
                            result = trajectory(policy, a, b, initial, totals, oracle, predictions[1], sd, alpha, case_id)
                            results[policy] = result
                            rows.append({k: source[k] for k in ['case_id', 'household_id', 'day_utc', 'pair', 'learned_pair']} |
                                        {'policy': policy} | {k: v for k, v in result.items() if k != 'trace'})
                        lo, hi = interval(a, b, late_observed, totals)
                        ls, _ = decision(lo, hi)
                        oracle.validate_interval(a, b, lo, hi)
                        late_certified += int(ls in ['a', 'b'])
                        sources.write(json.dumps(safe(source), separators=(',', ':'), allow_nan=False)+'\n')
                        traces.write(json.dumps(safe({'case_id': case_id, 'policies': results,
                                                     'late_bounds': [lo, hi], 'late_status': ls}), separators=(',', ':'), allow_nan=False)+'\n')
                        n += 1
                days += 1
                if days % 20 == 0:
                    print(json.dumps({'days': days, 'cases': n, 'seconds': time.perf_counter()-started}), flush=True)
    pd.DataFrame(rows).to_csv(out / 'cases.csv', index=False, float_format='%.17g')
    summary = summarize(out)
    for relative, expected in protocol['input_hashes'].items():
        assert sha(ROOT / relative) == expected, 'Frozen input changed during evaluation'
    report = dict(status='passed', wall_seconds=time.perf_counter()-started, cases=n, eligible_days=days,
                  late_strict_certified=late_certified, late_paid_requests=0,
                  completed_utc=datetime.now(timezone.utc).isoformat(),
                  protocol_sha256=sha(HERE / 'confirmation_protocol.json'),
                  source_target_blind_policy_api=True,
                  outputs={p.name: sha(p) for p in out.iterdir() if p.is_file()})
    write(out / 'run_result.json', report)
    print(json.dumps({k: v for k, v in summary.items() if k != 'summaries'}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['freeze', 'run'])
    args = parser.parse_args()
    freeze() if args.mode == 'freeze' else run()
