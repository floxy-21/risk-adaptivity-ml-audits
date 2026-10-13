"""Independent arithmetic, chronology and executable-cost replay.

Does not import the evaluator, forecast generator or acquisition algorithms.
No model refitting or policy-optimality claim is made by this checker.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import copy
import gzip
import hashlib
import itertools
import json
import math
import time
import numpy as np
import pandas as pd

MODELS = ('daily', 'ridge', 'hist_gradient_boosting', 'mlp')
POLICIES = ('exact', 'greedy', 'hara', 'uniform', 'randomized')
PAIRS = tuple(itertools.combinations(range(4), 2))
SEEDS = (1103, 2207, 3301)
CAP = 6
BLOCK = 6
WORKSPACE = Path(__file__).resolve().parents[3]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def resolve_frozen_path(value):
    """Map stored paths into this extracted workspace, never the old checkout."""
    text = str(value).replace('\\', '/')
    if text.startswith(('work/','outputs/')):
        suffix = text
    else:
        # Nested disposable workspaces themselves live below work/. The
        # last work/ or outputs/ boundary identifies the current tree.
        positions = [(text.rfind('/'+marker), marker) for marker in ('work/','outputs/')]
        position, marker = max(positions)
        require(position >= 0, 'No workspace-relative mapping for frozen path: '+text)
        suffix = text[position+1:]
    candidate = (WORKSPACE/suffix).resolve()
    require(candidate.is_relative_to(WORKSPACE.resolve()), 'Frozen path escapes package workspace')
    require(candidate.is_file(), 'Frozen package input missing: '+suffix)
    return candidate


def require(value, reason):
    if not bool(value):
        raise AssertionError(reason)


def close(a, b, reason, rtol=2e-10, atol=2e-11):
    aa, bb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    require(aa.shape == bb.shape and np.allclose(aa, bb, rtol=rtol, atol=atol, equal_nan=True), reason)


def bool_column(values):
    text = values.astype(str).str.lower().str.strip()
    require(text.isin(['true', 'false', '1', '0']).all(), 'Invalid Boolean field')
    return text.isin(['true', '1'])


def array(value):
    return np.asarray(value, dtype=float)


def deduce(known, totals):
    visible = array(known).copy()
    records = []
    for g, amount in enumerate(totals):
        ids = np.arange(6*g, 6*g+6)
        missing = ids[~np.isfinite(visible[ids])]
        remainder = float(amount) - math.fsum(visible[i] for i in ids if np.isfinite(visible[i]))
        require(remainder >= -1e-10*max(1., abs(amount)), 'Infeasible residual total')
        remainder = max(remainder, 0.)
        if len(missing) == 1:
            i = int(missing[0])
            visible[i] = remainder
            records.append(dict(index=i, value=remainder, kind='singleton', block=g))
        elif len(missing) and remainder == 0:
            for i in missing:
                visible[i] = 0.
                records.append(dict(index=int(i), value=0., kind='zero-total', block=g))
    return visible, records


def compare_deductions(actual, expected, context):
    require(len(actual) == len(expected), context+': deduction count')
    for a, e in zip(actual, expected):
        require({k: a[k] for k in ('index', 'kind', 'block')} == {k: e[k] for k in ('index', 'kind', 'block')}, context+': deduction identity')
        close(a['value'], e['value'], context+': deduction value')


def sharp_interval(a, b, visible, totals):
    a, b, visible = array(a), array(b), array(visible)
    coefficients = 2*(b-a)
    constant = math.fsum((float(a[i])**2-float(b[i])**2) for i in range(24))
    constant += math.fsum(float(coefficients[i]*visible[i]) for i in range(24) if np.isfinite(visible[i]))
    endpoint = [constant, constant]
    for g, amount in enumerate(totals):
        ids = range(g*6, g*6+6)
        free = [i for i in ids if not np.isfinite(visible[i])]
        if free:
            residual = max(0., float(amount)-math.fsum(float(visible[i]) for i in ids if np.isfinite(visible[i])))
            endpoint[0] += residual*min(float(coefficients[i]) for i in free)
            endpoint[1] += residual*max(float(coefficients[i]) for i in free)
    return np.array(endpoint)/24


def classification(bounds):
    low, high = map(float, bounds)
    tol = 1e-10*max(1., abs(low), abs(high))
    if high < -tol:
        return 'a'
    if low > tol:
        return 'b'
    if high-low <= tol:
        return 'numerical_tie'
    return 'unresolved'


def check_enclosure(bounds, delta):
    low, high = map(float, bounds)
    tolerance = 1e-9*max(1., abs(low), abs(high), abs(delta))
    require(low <= high+tolerance, 'Reversed interval')
    require(low-tolerance <= delta <= high+tolerance, 'Truth enclosure failure')
    sign = classification(bounds)
    require(not ((sign == 'a' and delta >= 0) or (sign == 'b' and delta <= 0)), 'Incorrect strict certificate')


def check_time(target, issue, persistence_source, feature_end=None, training_end=None):
    day = target.floor('D')
    require(issue == day-pd.Timedelta(hours=12), 'Issue time differs from frozen noon schedule')
    if persistence_source is not None and not pd.isna(persistence_source):
        require(persistence_source == target-pd.Timedelta(days=2), 'Wrong persistence source')
        require(persistence_source+pd.Timedelta(hours=1) <= issue, 'Persistence source after issue')
    if feature_end is not None and not pd.isna(feature_end):
        require(feature_end == day-pd.Timedelta(days=1), 'Feature end differs from causal complete-day boundary')
        require(feature_end <= issue, 'Future feature leakage')
        if training_end is not None:
            require(training_end <= issue, 'Fitted state not available at issue')


def check_batch(batch, observed, paid, cost):
    require(all(isinstance(i, (int, np.integer)) and 0 <= i < 24 for i in batch), 'Invalid query index')
    require(0 < len(batch) <= min(2, CAP-cost), 'Batch size or cap violation')
    require(len(set(batch)) == len(batch) and not set(batch).intersection(paid), 'Duplicate paid query')
    require(all(not np.isfinite(observed[i]) for i in batch), 'Query to already observed or deduced target')


def verify_logging_repair(rd):
    path = rd/'trace_logging_repair.json'
    if not path.exists():
        return None
    report = json.loads(path.read_text())
    require(report['status'] == 'repaired_logging_only', 'Unrecognized repair scope')
    original_path = resolve_frozen_path(report['original_trajectories_gzip'])
    old_run_path = resolve_frozen_path(report['original_run_result'])
    executed_path = resolve_frozen_path(report['executed_evaluator_path'])
    require(sha(old_run_path) == report['original_run_result_sha256'], 'Original execution report changed')
    require(sha(executed_path) == report['executed_evaluator_sha256'], 'Executed evaluator source changed')
    require(sha(WORKSPACE/'work/external_deadline/evaluate.py') == report['corrected_evaluator_sha256'], 'Corrected evaluator hash mismatch')
    require(sha(WORKSPACE/'work/external_deadline/repair_trace.py') == report['repair_script_sha256'], 'Repair script provenance mismatch')
    require(sha(rd/'trajectories.jsonl') == report['repaired_trace_sha256'], 'Repaired trajectory hash mismatch')
    old_run = json.loads(old_run_path.read_text())
    new_run = json.loads((rd/'run_result.json').read_text())
    require(old_run['input_hashes'] == new_run['input_hashes'], 'Logging repair changed experimental inputs')
    require(old_run['input_hashes']['work/external_deadline/evaluate.py'] == report['executed_evaluator_sha256'], 'Executed-source provenance mismatch')
    for name, expected_hash in old_run['outputs'].items():
        if name != 'trajectories.jsonl':
            require(sha(rd/name) == expected_hash, 'Original non-trace output changed '+name)
    required_unchanged = {'cases.csv','archive_snapshots.json','pre_outcome_manifest.json',
        'headline_summary.json','coverage_curves.csv','cost_summary.csv','household_curves.csv',
        'pair_curves.csv','month_curves.csv'}
    require(required_unchanged.issubset(report['unchanged_outcome_files']), 'Repair report omits outcome provenance')
    for name, expected_hash in report['unchanged_outcome_files'].items():
        require(sha(rd/name) == expected_hash, 'Logging repair changed an outcome file '+name)
    rows, stages, changed = 0, 0, 0
    uncompressed_hash = hashlib.sha256()
    with gzip.open(original_path,'rb') as original, (rd/'trajectories.jsonl').open('rb') as revised:
        for old_line, new_line in itertools.zip_longest(original,revised):
            require(old_line is not None and new_line is not None, 'Logging repair inserted/removed cases')
            uncompressed_hash.update(old_line)
            old, new = json.loads(old_line), json.loads(new_line)
            old_policies, new_policies = old.pop('policies'), new.pop('policies')
            require(old == new, 'Logging repair changed case inputs/outcomes')
            require(set(old_policies) == set(new_policies), 'Logging repair changed policies')
            for policy in old_policies:
                old_result, new_result = old_policies[policy], new_policies[policy]
                old_stages, new_stages = old_result.pop('stages'), new_result.pop('stages')
                require(old_result == new_result and len(old_stages) == len(new_stages), 'Logging repair changed trajectory outcome/cost')
                for k, (before_fix, after_fix) in enumerate(zip(old_stages,new_stages)):
                    old_after = before_fix.pop('after')
                    new_after = after_fix.pop('after')
                    require(before_fix == after_fix, 'Logging repair altered a field beyond stage.after')
                    observed = array(after_fix['before']).copy()
                    observed[after_fix['batch']] = array(after_fix['revealed'])
                    expected_after, deductions = deduce(observed, new['totals'])
                    close(new_after, expected_after, 'Repaired after is not before + charged reveal + closure')
                    compare_deductions(after_fix['deductions'],deductions,'Logging repair independent closure')
                    expected_old = array(new_after).copy()
                    if k+1 < len(new_stages):
                        following = new_stages[k+1]
                        close(following['before'],new_after,'Repaired after differs from next before')
                        expected_old[following['batch']] = array(following['revealed'])
                    close(old_after,expected_old,'Original after not explained exactly by next-batch alias')
                    changed += int(not np.array_equal(array(old_after),array(new_after),equal_nan=True))
                    stages += 1
            rows += 1
    require(uncompressed_hash.hexdigest() == report['original_trajectories_sha256'], 'Original trace gzip does not recover pinned original bytes')
    require(old_run['outputs']['trajectories.jsonl'] == uncompressed_hash.hexdigest(), 'Original trace not the executed output')
    require((rows,stages,changed) == (report['rows'],report['stages'],report['changed_after_snapshots']), 'Logging repair accounting mismatch')
    return dict(status='passed',rows=rows,stages=stages,changed_after_snapshots=changed,
                repair_report_sha256=sha(path),executed_evaluator_path=report['executed_evaluator_path'],
                executed_evaluator_sha256=report['executed_evaluator_sha256'],
                scope='Every original/revised record compared; only after snapshots changed and the exact next-batch alias mechanism explains each change. Policy batches, forecasts, costs, bounds, decisions and headline outcomes are unchanged.')


def check_policy(result, base, reference):
    observed = array(base['initial_observed'])
    totals, a, b = array(base['totals']), array(base['a']), array(base['b'])
    delta = float(np.mean((a-reference)**2-(b-reference)**2))
    interval = sharp_interval(a, b, observed, totals)
    close(result['initial_bounds'], interval, 'Initial interval mismatch')
    status = classification(interval)
    require(result['initial_status'] == status, 'Initial status mismatch')
    initial_status = status
    check_enclosure(interval, delta)
    cost, paid, timing, cert_cost, stages = 0, [], 0., 0 if status in ('a', 'b') else None, 0
    for stage in result['stages']:
        require(status == 'unresolved' and cost < CAP, 'Stage executed after stopping')
        close(stage['before'], observed, 'Stage starts with wrong observations')
        close(stage['before_bounds'], interval, 'Stage starts with wrong bounds')
        batch = stage['batch']
        require(stage['query_indices'] == batch, 'Selected batch differs from charged batch')
        check_batch(batch, observed, paid, cost)
        close(stage['revealed'], reference[batch], 'Revealed values differ from reference')
        cost += len(batch)
        paid.extend(batch)
        require(stage['cost'] == cost, 'Full requested batch not charged')
        observed[batch] = reference[batch]
        observed, deductions = deduce(observed, totals)
        compare_deductions(stage['deductions'], deductions, 'Stage closure')
        close(stage['after'], observed, 'Wrong posterior observed set/value')
        updated = sharp_interval(a, b, observed, totals)
        close(stage['bounds'], updated, 'Wrong posterior bounds')
        tolerance = 1e-9*max(1., *np.abs(interval), *np.abs(updated))
        require(updated[0] >= interval[0]-tolerance and updated[1] <= interval[1]+tolerance, 'Information widens interval')
        interval = updated
        status = classification(interval)
        require(stage['status'] == status, 'Posterior status mismatch')
        check_enclosure(interval, delta)
        if status in ('a', 'b') and cert_cost is None:
            cert_cost = cost
        require(np.isfinite(stage['planning_seconds']) and stage['planning_seconds'] >= 0, 'Invalid planning time')
        timing += stage['planning_seconds']
        stages += 1
    require(status != 'unresolved' or cost == CAP, 'Trajectory ended before resolution/cap')
    require(result['final_status'] == status, 'Final status mismatch')
    require(result['paid_requests'] == cost and result['paid_indices'] == paid, 'Final paid requests mismatch')
    require(result['certification_cost'] == cert_cost, 'Wrong cumulative certification cost')
    close(result['planning_seconds'], timing, 'Planning time sum mismatch')
    close(result['final_bounds'], interval, 'Final bounds mismatch')
    return dict(initial_status=initial_status, final_status=status, paid_requests=cost,
                certification_cost=cert_cost, planning_seconds=timing,
                initial_width=float(result['initial_bounds'][1]-result['initial_bounds'][0]),
                final_width=float(interval[1]-interval[0])), stages


def fixtures():
    # Independent scalar arithmetic and failures: no experiment implementation.
    package_path = 'C:/old/work/disposable/work/external_deadline/review/verify_external.py'
    require(resolve_frozen_path(package_path) == Path(__file__).resolve(), 'Nested portable path mapping')
    observed = np.ones(24)
    observed[:2] = np.nan
    totals = np.full(4, 6.)
    a, b, reference = np.zeros(24), np.ones(24), np.ones(24)
    close(sharp_interval(a, b, observed, totals), [1., 1.], 'Synthetic sharp bounds')
    observed[0] = 1.
    filled, deductions = deduce(observed, totals)
    close(filled, reference, 'Synthetic singleton closure')
    require(len(deductions) == 1 and deductions[0]['index'] == 1, 'Synthetic deduction trace')
    a, b = np.zeros(24), np.zeros(24)
    a[:2], b[:2] = [1., 3.], [2., 2.]
    initial = reference.copy()
    initial[:2] = np.nan
    base = dict(initial_observed=initial, totals=totals, a=a, b=b)
    first = sharp_interval(a,b,initial,totals)
    last = sharp_interval(a,b,reference,totals)
    stage = dict(batch=[0], query_indices=[0], revealed=[1.], cost=1, before=initial,
        before_bounds=first, after=reference, deductions=[dict(index=1,value=1.,kind='singleton',block=0)],
        bounds=last, status='b', planning_seconds=0.)
    policy = dict(initial_bounds=first, initial_status='unresolved', stages=[stage], final_status='b',
        paid_requests=1, paid_indices=[0], certification_cost=1, planning_seconds=0., final_bounds=last)
    check_policy(policy,base,reference)
    wrong_cost = copy.deepcopy(policy)
    wrong_cost['stages'][0]['cost'] = 0
    target = pd.Timestamp('2015-02-03 05:00Z')
    issue = pd.Timestamp('2015-02-02 12:00Z')
    check_time(target, issue, target-pd.Timedelta(days=2), pd.Timestamp('2015-02-02 00:00Z'), pd.Timestamp('2015-01-01 00:00Z'))
    caught = []
    bad = [
        ('future feature', lambda: check_time(target, issue, target-pd.Timedelta(days=2), pd.Timestamp('2015-02-03 00:00Z'))),
        ('future fitted state', lambda: check_time(target, issue, target-pd.Timedelta(days=2), pd.Timestamp('2015-02-02 00:00Z'), pd.Timestamp('2015-02-03 00:00Z'))),
        ('query cap', lambda: check_batch([0, 1], np.full(24, np.nan), list(range(2, 7)), 5)),
        ('duplicate query', lambda: check_batch([0, 0], np.full(24, np.nan), [], 0)),
        ('known query', lambda: check_batch([0], np.ones(24), [], 0)),
        ('hidden initial target', lambda: close(np.ones(24), np.r_[np.nan, np.ones(23)], 'Initial information leakage/missing closure')),
        ('uncharged requested batch', lambda: check_policy(wrong_cost,base,reference)),
        ('wrong certificate', lambda: check_enclosure([-2., -1.], 1.)),
    ]
    for name, callback in bad:
        try:
            callback()
        except AssertionError:
            caught.append(name)
        else:
            raise AssertionError('Corrupted fixture was accepted: '+name)
    return dict(status='passed', arithmetic_fixtures=4, rejected_corruptions=caught,
                imports_experiment_or_acquisition=False, external_outcomes_opened=False)


def check_features(fd, archive, candidates):
    prepared = json.loads((fd/'prepared.json').read_text())
    config = json.loads((fd/'frozen_config.json').read_text())
    fit = json.loads((fd/'fit_metadata.json').read_text())
    surrogate = json.loads((fd/'surrogate_parameters.json').read_text())
    source_path = resolve_frozen_path(prepared['hourly_path'])
    require(sha(source_path) == prepared['hourly_sha256'], 'Frozen source hourly hash mismatch')
    for key in ('config', 'protocol'):
        if prepared.get(key+'_path'):
            require(sha(resolve_frozen_path(prepared[key+'_path'])) == prepared[key+'_sha256'], 'Frozen '+key+' hash mismatch')
    source = pd.read_csv(source_path, dtype={'household_id':str})
    source['timestamp_utc'] = pd.to_datetime(source.timestamp_utc, utc=True)
    source['eligible'] = bool_column(source.eligible)
    require(not source.duplicated(['household_id','timestamp_utc']).any(), 'Duplicate source target row')
    for name, expected_hash in prepared['prepared_hashes'].items():
        require(sha(fd/name) == expected_hash, 'Prepared array/input hash mismatch '+name)
    require(sha(fd/'prepared.json') == fit['prepared_sha256'], 'Preparation changed after fitting')
    for name, expected_hash in fit['output_hashes'].items():
        require(sha(fd/name) == expected_hash, 'Forecast output hash mismatch '+name)
    require(set(str(x['household_id']) for x in prepared['households']) == set(archive.household_id), 'Household coverage mismatch')
    require(fit['model_fit_count'] == 3*len(prepared['households']), 'Wrong model fit count')
    checks = 0
    for household in prepared['households']:
        key = str(household['household_id'])
        with np.load(fd/household['array_file'], allow_pickle=False) as z:
            dates = pd.to_datetime(z['days_ns'], unit='ns', utc=True)
            x, y = z['x'], z['y']
            source_house = source[source.household_id == key].set_index('timestamp_utc')
            index = pd.date_range(dates[0], dates[-1]+pd.Timedelta(hours=23), freq='h')
            original = source_house.energy_kwh.where(source_house.eligible).reindex(index).to_numpy(float).reshape(-1,24)
            close(y, original, 'Prepared targets differ from eligible source hourly records')
            expected = np.full_like(x, np.nan)
            for column, lag in enumerate((2, 3, 8)):
                expected[lag:, :, column] = y[:-lag]
            expected[2:, :, 3] = np.mean(y[:-2], axis=1)[:, None]
            hour = np.arange(24)
            expected[:, :, 4] = np.sin(2*np.pi*hour/24)
            expected[:, :, 5] = np.cos(2*np.pi*hour/24)
            expected[:, :, 6] = np.sin(2*np.pi*dates.dayofweek.to_numpy()[:, None]/7)
            expected[:, :, 7] = np.cos(2*np.pi*dates.dayofweek.to_numpy()[:, None]/7)
            expected[:, :, 8] = np.sin(2*np.pi*(dates.month.to_numpy()[:, None]-1)/12)
            expected[:, :, 9] = np.cos(2*np.pi*(dates.month.to_numpy()[:, None]-1)/12)
            close(x, expected, 'Causal feature reconstruction '+key)
            checks += x.size
            complete = np.isfinite(expected).all(axis=(1, 2))
            reference_complete = np.isfinite(y).all(axis=1) & (y >= 0).all(axis=1)
            train = np.asarray((dates >= pd.Timestamp(config['train_start'], tz='UTC')) & (dates <= pd.Timestamp(config['train_end'], tz='UTC'))) & complete & reference_complete
            require(np.array_equal(z['train'], train), 'Training day selection mismatch')
            close(y[train].mean(), household['training_mean_kwh'], 'Training mean mismatch')
            training_end = dates[train][-1]+pd.Timedelta(days=1)
            require(pd.Timestamp(household['training_data_end_utc']) == training_end, 'Training end provenance mismatch')
            require(training_end == pd.Timestamp(config['train_end'],tz='UTC')+pd.Timedelta(days=1),
                    'Frozen study fitted-state availability precedes nominal training-window close')
            issue_ok = np.asarray(dates-pd.Timedelta(hours=12) >= training_end)
            archive_days = np.asarray((dates >= pd.Timestamp(config['validation_start'], tz='UTC')) & (dates <= pd.Timestamp(config['test_end'], tz='UTC')+pd.Timedelta(days=2)))
            learned = complete & issue_ok & archive_days
            require(np.array_equal(learned, z['learned']), 'Learned availability mismatch')
            hc = candidates[candidates.household_id == key].set_index('day_utc')
            require(set(hc.index) == set(dates[archive_days]), 'Candidate inventory omits dates')
            ha = archive[archive.household_id == key].set_index('target_timestamp_utc')
            hc = hc.loc[dates[archive_days]]
            require(np.array_equal(hc.eligible.to_numpy(), (reference_complete & learned)[archive_days]), 'Eligibility mismatch')
            for field, answer in [('reference_complete', reference_complete), ('feature_complete', complete), ('model_training_available_at_issue', issue_ok), ('all_forecasts_complete', learned)]:
                require(np.array_equal(hc[field].to_numpy(), answer[archive_days]), 'Candidate flag mismatch '+field)
            require(np.array_equal(hc.persistence_available_hours.to_numpy(), np.isfinite(expected[archive_days,:,0]).sum(axis=1)), 'Persistence hours mismatch')
            # Same all-row comparisons as the former scalar loop, performed
            # as arrays to avoid repeated pandas mixed-type row construction.
            persistence = expected[:,:,0].reshape(-1)
            active = np.repeat(archive_days,24) & (np.repeat(learned,24) | np.isfinite(persistence))
            expected_stamps = index[active]
            require(len(ha) == len(expected_stamps) and set(ha.index) == set(expected_stamps), 'Issued archive row missing or extra')
            ordered = ha.loc[expected_stamps]
            values = ordered[list(MODELS)].to_numpy(float)
            close(values[:,0], persistence[active], 'Persistence value mismatch')
            learned_rows = np.repeat(learned,24)[active]
            require(np.isfinite(values[learned_rows,1:]).all() and np.isnan(values[~learned_rows,1:]).all(), 'Learned forecast eligibility mismatch')
            expected_issue = expected_stamps.floor('D')-pd.Timedelta(hours=12)
            require(np.array_equal(ordered.issue_time_utc.to_numpy(), expected_issue.to_numpy()), 'Issue time differs from frozen noon schedule')
            expected_source = expected_stamps-pd.Timedelta(days=2)
            require(np.array_equal(ordered.persistence_source_time_utc.to_numpy(), expected_source.to_numpy()), 'Wrong persistence source')
            require((expected_source+pd.Timedelta(hours=1) <= expected_issue).all(), 'Persistence source after issue')
            recorded_end = ordered.latest_feature_source_end_utc
            require(recorded_end.iloc[np.flatnonzero(~learned_rows)].isna().all(), 'Unexpected learned feature provenance')
            expected_end = expected_stamps[learned_rows].floor('D')-pd.Timedelta(days=1)
            require(np.array_equal(recorded_end.iloc[np.flatnonzero(learned_rows)].to_numpy(), expected_end.to_numpy()), 'Feature end differs from causal complete-day boundary')
            require((expected_end <= expected_issue[learned_rows]).all() and (training_end <= expected_issue[learned_rows]).all(), 'Feature or fitted state after issue')
            valid = np.asarray((dates >= pd.Timestamp(config['validation_start'], tz='UTC')) & (dates <= pd.Timestamp(config['validation_end'], tz='UTC'))) & learned & reference_complete
            ridge = ha.loc[index[np.repeat(valid,24)], 'ridge'].to_numpy(float)
            residuals = y[valid].reshape(-1)-ridge
            expected_sd = float(np.sqrt(np.mean(residuals**2)))
            item = surrogate[key]
            close(item['validation_residual_rmse_kwh'], expected_sd, 'Frozen surrogate scale mismatch')
            close(item['sd_kwh'], max(expected_sd, 1e-8*household['training_mean_kwh']), 'Surrogate floor mismatch')
    return checks


def first_budget(frame):
    crossing = frame.loc[frame.coverage >= .8, 'budget']
    return int(crossing.min()) if len(crossing) else None


def frame_equal(path, expected, keys):
    actual = pd.read_csv(path, dtype={'household_id':str})
    require(set(actual.columns) == set(expected.columns), 'Summary columns mismatch '+path.name)
    require(not actual.duplicated(keys).any(), 'Duplicate summary row '+path.name)
    aa = actual.set_index(keys).sort_index()
    ee = expected.set_index(keys).sort_index()
    require(aa.index.equals(ee.index), 'Summary row identities mismatch '+path.name)
    for field in aa.columns:
        close(aa[field], ee[field], 'Summary arithmetic mismatch '+path.name+'/'+field)


def check_headlines(frame, rd):
    # Grouping and statistics are reconstructed from independently replayed
    # trajectories, not cases.csv or the summarizer's result tables.
    curves, house_curves, costs, pair_curves, month_curves = [], [], [], [], []
    for subgroup in ('all', 'learned'):
        selected = frame if subgroup == 'all' else frame[frame.learned_pair]
        for (regime, policy), group in selected.groupby(['regime', 'policy']):
            for population in ('all', 'initially_unresolved'):
                # Frozen rule retains numerical/reference ties in denominator.
                sample = group if population == 'all' else group[~group.initial_status.isin(('a', 'b'))]
                all_households = group.household_id.nunique()
                household_samples = dict(tuple(sample.groupby('household_id')))
                for budget in range(7):
                    certified = sample.certification_cost.notna() & (sample.certification_cost <= budget)
                    rates = []
                    for household, part in household_samples.items():
                        count = int((part.certification_cost.notna() & (part.certification_cost <= budget)).sum())
                        rate = count/len(part)
                        rates.append(rate)
                        if subgroup == 'all':
                            house_curves.append(dict(household_id=household, regime=regime, policy=policy, population=population,
                                budget=budget, coverage=rate, cases=len(part)))
                    curves.append(dict(subgroup=subgroup, regime=regime, policy=policy, population=population, budget=budget,
                        cases=len(sample), households=len(household_samples), excluded_zero_denominator_households=all_households-len(household_samples),
                        coverage=float(np.mean(rates)) if rates else None,
                        pooled_coverage=float(certified.sum()/len(sample)) if len(sample) else None))
                count = len(sample)
                times = sample.planning_seconds.to_numpy(float)
                requests = sample.paid_requests.to_numpy(float)
                costs.append(dict(subgroup=subgroup, regime=regime, policy=policy, population=population, cases=count,
                    household_macro_mean_requests=float(np.mean([part.paid_requests.mean() for part in household_samples.values()])) if count else None,
                    pooled_mean_requests=float(np.mean(requests)) if count else None,
                    pooled_median_requests=float(np.median(requests)) if count else None,
                    unresolved_at_stop=int((sample.final_status == 'unresolved').sum()),
                    unresolved_at_cap=int(((sample.final_status == 'unresolved') & (sample.paid_requests >= CAP)).sum()),
                    numerical_tie_stops=int((sample.final_status == 'numerical_tie').sum()),
                    exact_reference_ties=int(sample.exact_reference_tie.sum()), near_reference_ties=int(sample.near_reference_tie.sum()),
                    planning_seconds_total=float(np.sum(times)), planning_seconds_mean_case=float(np.mean(times)) if count else None,
                    planning_seconds_p95_case=float(np.quantile(times, .95)) if count else None))
    early = frame[frame.regime == 'early']
    for attribute, output in [('pair', pair_curves), ('month', month_curves)]:
        for (level, policy), part in early.groupby([attribute, 'policy']):
            sample = part[~part.initial_status.isin(('a', 'b'))]
            for budget in range(7):
                rates = [float((h.certification_cost.notna() & (h.certification_cost <= budget)).mean())
                         for _, h in sample.groupby('household_id')]
                output.append({attribute:level, 'policy':policy, 'budget':budget, 'cases':len(sample),
                               'coverage':float(np.mean(rates)) if rates else None})
    tables = {name:pd.DataFrame(records) for name, records in [('coverage_curves', curves), ('household_curves', house_curves),
        ('cost_summary', costs), ('pair_curves', pair_curves), ('month_curves', month_curves)]}
    keys = {'coverage_curves':['subgroup','regime','policy','population','budget'],
        'household_curves':['household_id','regime','policy','population','budget'],
        'cost_summary':['subgroup','regime','policy','population'], 'pair_curves':['pair','policy','budget'], 'month_curves':['month','policy','budget']}
    for name, table in tables.items():
        frame_equal(rd/(name+'.csv'), table, keys[name])
    c = tables['coverage_curves']
    budgets = {}
    for subgroup in ('all', 'learned'):
        part = c[(c.subgroup == subgroup) & (c.regime == 'early') & (c.population == 'initially_unresolved')]
        budgets[subgroup] = {p:first_budget(part[part.policy == p]) for p in POLICIES}
    available = [budgets['all'][p] for p in ('greedy', 'hara') if budgets['all'][p] is not None]
    best = min(available) if available else None
    exact = budgets['all']['exact']
    reduction = (best-exact)/best if best not in (None, 0) and exact is not None else None
    final = c[(c.subgroup == 'all') & (c.regime == 'early') & (c.population == 'initially_unresolved') & (c.budget == 6)].set_index('policy').coverage
    cap_ok = float(final['exact'])+1e-12 >= max(float(final[p]) for p in ('greedy', 'hara'))
    house_budgets, pair_budgets = [], []
    hc = tables['household_curves']
    for attribute, input_table, destination in [
        ('household_id', hc[(hc.regime == 'early') & (hc.population == 'initially_unresolved')], house_budgets),
        ('pair', tables['pair_curves'], pair_budgets)]:
        for identity, group in input_table.groupby(attribute):
            b = {p:first_budget(group[group.policy == p]) for p in POLICIES}
            values = [b[p] for p in ('greedy', 'hara') if b[p] is not None]
            baseline = min(values) if values else None
            destination.append({attribute:identity, **b, 'strongest_baseline':baseline,
                'exact_strictly_better':bool(b['exact'] is not None and baseline is not None and b['exact'] < baseline)})
    counts = dict(case_rows=len(frame), base_cases=int(frame.case_id.nunique()), households=int(frame.household_id.nunique()),
        household_days=len(frame[['household_id','day_utc']].drop_duplicates()),
        initial_unresolved_base_cases=int(((early.policy == 'exact') & ~early.initial_status.isin(('a','b'))).sum()))
    expected = dict(B80=budgets, strongest_greedy_hara_B80=best, exact_relative_B80_reduction=reduction,
        exact_no_lower_cap_coverage=bool(cap_ok), fifteen_percent_budget_criterion_met=bool(reduction is not None and reduction >= .15 and cap_ok),
        uniform_has_lower_B80_than_exact=bool(budgets['all']['uniform'] is not None and exact is not None and budgets['all']['uniform'] < exact),
        household_B80=house_budgets, pair_B80=pair_budgets,
        households_exact_strictly_better=sum(x['exact_strictly_better'] for x in house_budgets),
        pairs_exact_strictly_better=sum(x['exact_strictly_better'] for x in pair_budgets),
        learned_pairs_exact_strictly_better=sum(x['exact_strictly_better'] and 'daily' not in x['pair'] for x in pair_budgets), counts=counts)
    report = json.loads((rd/'headline_summary.json').read_text())
    require(report['status'] == 'passed' and report['source_sha256'] == sha(rd/'cases.csv'), 'Headline provenance mismatch')
    for name, value in expected.items():
        require(report[name] == value, 'Headline mismatch '+name)
    tables['coverage_curves'].to_csv(rd/'independent_curves.csv', index=False, float_format='%.17g')
    return expected, {name:len(table) for name, table in tables.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--forecast-dir', type=Path)
    parser.add_argument('--run-dir', type=Path)
    args = parser.parse_args()
    fixture_result = fixtures()
    if args.self_test:
        location = Path(__file__).with_name('checker_fixture_result.json')
        location.write_text(json.dumps(fixture_result, indent=2)+'\n')
        print(json.dumps(fixture_result, indent=2))
        return
    require(args.forecast_dir and args.run_dir, 'Both --forecast-dir and --run-dir are required')
    start = time.perf_counter()
    fd, rd = args.forecast_dir.resolve(), args.run_dir.resolve()
    run = json.loads((rd/'run_result.json').read_text())
    require(run['status'] == 'passed', 'Evaluator did not finish successfully')
    repair_check = verify_logging_repair(rd)
    manifest = json.loads((rd/'pre_outcome_manifest.json').read_text())
    require(manifest['period'] == run['period'] and manifest['inputs'] == run['input_hashes'], 'Pre-outcome manifest differs from completed-run inputs')
    for name, expected_hash in run['input_hashes'].items():
        resolved = resolve_frozen_path(name)
        if name == 'work/external_deadline/evaluate.py' and repair_check:
            resolved = resolve_frozen_path(repair_check['executed_evaluator_path'])
        require(sha(resolved) == expected_hash, 'Frozen evaluation file changed '+name)
    for name, expected_hash in run['outputs'].items():
        require(sha(rd/name) == expected_hash, 'Run output changed '+name)
    for name in ('forecast_archive.csv', 'reference_targets.csv', 'candidate_days.csv', 'surrogate_parameters.json'):
        entries = [v for p, v in run['input_hashes'].items() if Path(p).name == name]
        require(len(entries) == 1 and entries[0] == sha(fd/name), 'Frozen evaluation input mismatch '+name)
    archive = pd.read_csv(fd/'forecast_archive.csv', dtype={'household_id': str})
    for column in ('target_timestamp_utc', 'issue_time_utc', 'persistence_source_time_utc', 'latest_feature_source_end_utc'):
        archive[column] = pd.to_datetime(archive[column], utc=True)
    require(not archive.duplicated(['household_id', 'target_timestamp_utc']).any(), 'Duplicate archive row')
    reference = pd.read_csv(fd/'reference_targets.csv', dtype={'household_id': str})
    reference['timestamp_utc'] = pd.to_datetime(reference.timestamp_utc, utc=True)
    require(not reference.duplicated(['household_id', 'timestamp_utc']).any(), 'Duplicate reference row')
    candidates = pd.read_csv(fd/'candidate_days.csv', dtype={'household_id': str})
    candidates['day_utc'] = pd.to_datetime(candidates.day_utc, utc=True)
    for col in ('eligible', 'reference_complete', 'feature_complete', 'model_training_available_at_issue', 'all_forecasts_complete'):
        candidates[col] = bool_column(candidates[col])
    feature_checks = check_features(fd, archive, candidates)
    included = candidates[(candidates.period == run['period']) & candidates.eligible]
    expected_keys = {f'{r.household_id}|{r.day_utc.date()}|{seed}|{i}-{j}' for r in included.itertuples() for seed in SEEDS for i, j in PAIRS}
    lookup = archive.set_index(['household_id', 'target_timestamp_utc'])
    refl = reference.set_index(['household_id', 'timestamp_utc'])
    snapshots = json.loads((rd/'archive_snapshots.json').read_text())
    require(len(snapshots) == len(included), 'Wrong snapshot count')
    snapmap = {(str(s['household_id']), pd.Timestamp(s['day_utc'])): s for s in snapshots}
    require(len(snapmap) == len(snapshots), 'Duplicate snapshot')
    day_values = {}
    for r in included.itertuples():
        key = (r.household_id, r.day_utc)
        snap = snapmap[key]
        stamps = pd.date_range(r.day_utc, periods=24, freq='h')
        truth = refl.loc[[(r.household_id, stamp) for stamp in stamps], 'energy_kwh'].to_numpy(float)
        forecasts = lookup.loc[[(r.household_id, stamp) for stamp in stamps], list(MODELS)].to_numpy(float).T
        require(np.isfinite(truth).all() and (truth >= 0).all() and np.isfinite(forecasts).all(), 'Invalid eligible target day')
        early = r.day_utc+pd.Timedelta(days=1)
        late = early+pd.Timedelta(hours=12)
        require(pd.Timestamp(snap['early_cutoff']) == early and pd.Timestamp(snap['late_cutoff']) == late, 'Wrong audit cutoff')
        ha = archive[archive.household_id == r.household_id]
        source_rows = ha[ha.persistence_source_time_utc.isin(stamps) & ha.daily.notna()]
        require(not (source_rows.issue_time_utc <= early).any(), 'Early target copy excluded')
        late_rows = source_rows[source_rows.issue_time_utc <= late]
        require(len(late_rows) == 24, 'Incomplete late reconstruction')
        for hour in range(24):
            item = snap['late_copy_sources'][str(hour)]
            source = stamps[hour]
            target = source+pd.Timedelta(days=2)
            row = lookup.loc[(r.household_id, target)]
            require(pd.Timestamp(item['source_timestamp_utc']) == source and pd.Timestamp(item['target_timestamp_utc']) == target, 'Wrong copy trace timestamps')
            require(pd.Timestamp(item['issue_time_utc']) == row.issue_time_utc == late, 'Wrong late copy issue time')
            close(item['value'], row.daily, 'Copy trace differs from archive')
            close(row.daily, truth[hour], 'Copy differs from reference')
        for name, cutoff in [('early', early), ('late', late)]:
            permitted = ha[ha.issue_time_utc <= cutoff]
            require(snap['available_forecast_rows'][name] == len(permitted), 'Snapshot omits available issued row')
            require(snap['available_prediction_values'][name] == {m: int(permitted[m].notna().sum()) for m in MODELS}, 'Snapshot value counts mismatch')
        require(snap['early_future_target_rows'] == int(((ha.issue_time_utc <= early) & (ha.target_timestamp_utc >= early)).sum()), 'Future-target rows omitted')
        require(snap['early_direct_target_copies'] == 0 and snap['late_direct_target_copies'] == 24, 'Wrong reconstruction attribution')
        day_values[key] = (truth, forecasts)
    seen, reconstructed, stages_count = set(), [], 0
    with (rd/'trajectories.jsonl').open(encoding='utf-8') as lines:
        for line in lines:
            base = json.loads(line)
            identity = base['case_id']
            require(identity in expected_keys and identity not in seen, 'Unexpected or duplicate case')
            seen.add(identity)
            household, date, seed_text, pair_text = identity.split('|')
            day = pd.Timestamp(date, tz='UTC')
            seed = int(seed_text)
            ia, ib = map(int, pair_text.split('-'))
            require(household == str(base['household_id']) and day == pd.Timestamp(base['day_utc']) and seed == base['seed'], 'Case ID metadata mismatch')
            require(base['pair'] == f'{MODELS[ia]} vs {MODELS[ib]}' and base['learned_pair'] == (ia != 0), 'Pair metadata mismatch')
            reference_values, predictions = day_values[(household, day)]
            close(base['a'], predictions[ia], 'First forecasts not from archive')
            close(base['b'], predictions[ib], 'Second forecasts not from archive')
            totals = [math.fsum(reference_values[g*6:(g+1)*6]) for g in range(4)]
            close(base['totals'], totals, 'Constructed totals mismatch')
            entropy = hashlib.sha256(f'mask|{household}|{str(day)}|{seed}'.encode()).digest()
            mask_start = int(np.random.default_rng(int.from_bytes(entropy[:8], 'little')).integers(19))
            mask = list(range(mask_start, mask_start+6))
            require(base['mask'] == mask, 'Mask does not match frozen SHA stream')
            initial = reference_values.copy()
            initial[mask] = np.nan
            initial, deductions = deduce(initial, totals)
            close(base['initial_observed'], initial, 'Initial information leakage/missing closure')
            compare_deductions(base['initial_deductions'], deductions, 'Initial closure')
            delta = float(np.mean((predictions[ia]-reference_values)**2-(predictions[ib]-reference_values)**2))
            close(base['reference_difference'], delta, 'Reference contrast mismatch')
            require(base['exact_reference_tie'] == (delta == 0), 'Exact reference tie mislabeled')
            require(base['near_reference_tie'] == (abs(delta) <= 1e-10*max(1., abs(delta))), 'Near reference tie mislabeled')
            require(set(base['policies']) == set(POLICIES), 'Policy missing from common case')
            common = {k: base[k] for k in ('case_id', 'household_id', 'day_utc', 'month', 'seed', 'pair', 'learned_pair', 'exact_reference_tie', 'near_reference_tie')}
            for policy, result in base['policies'].items():
                row, stage_count = check_policy(result, base, reference_values)
                reconstructed.append(dict(**common, regime='early', policy=policy, **row))
                stages_count += stage_count
            late_bounds = sharp_interval(predictions[ia], predictions[ib], reference_values, totals)
            close(base['late_bounds'], late_bounds, 'Late comparison bounds mismatch')
            late_status = classification(late_bounds)
            require(base['late_status'] == late_status, 'Late status mismatch')
            check_enclosure(late_bounds, delta)
            reconstructed.append(dict(**common, regime='late', policy='free_archive', initial_status=late_status,
                final_status=late_status, paid_requests=0, certification_cost=0 if late_status in ('a', 'b') else None,
                planning_seconds=0., initial_width=late_bounds[1]-late_bounds[0], final_width=late_bounds[1]-late_bounds[0]))
    require(seen == expected_keys, 'Required cases omitted')
    actual = pd.read_csv(rd/'cases.csv', dtype={'household_id': str})
    expected = pd.DataFrame(reconstructed)
    require(len(actual) == len(expected) == len(included)*18*6, 'Wrong policy-row count')
    index = ['case_id', 'regime', 'policy']
    require(not actual.duplicated(index).any(), 'Duplicate case summary')
    aa, ee = actual.set_index(index).sort_index(), expected.set_index(index).sort_index()
    require(aa.index.equals(ee.index), 'Summary identities do not match traces')
    numeric = ['seed', 'paid_requests', 'certification_cost', 'planning_seconds', 'initial_width', 'final_width']
    close(aa[numeric], ee[numeric], 'Cases.csv arithmetic differs from independent replay')
    for field in sorted(set(ee.columns)-set(numeric)):
        require((aa[field].astype(str).to_numpy() == ee[field].astype(str).to_numpy()).all(), 'Summary field mismatch '+field)
    headline, table_counts = check_headlines(expected, rd)
    curves_path = rd/'independent_curves.csv'
    report = dict(status='passed', completed_utc=datetime.now(timezone.utc).isoformat(), period=run['period'],
        household_count=int(included.household_id.nunique()), eligible_days=len(included), base_cases=len(seen),
        policy_rows=len(expected), fully_replayed_batches=stages_count, feature_scalars_reconstructed=feature_checks,
        bound_enclosure_failures=0, incorrect_certificates=0, timestamp_violations=0, duplicate_paid_queries=0,
        cap_violations=0, early_missing_direct_copies=0, strict_grid_checks='passed', B80_household_macro=headline['B80'],
        headline_tables_checked=table_counts, headline_practical_criterion_met=headline['fifteen_percent_budget_criterion_met'],
        logging_repair_verification=repair_check,
        fixture_result=fixture_result, imported_evaluator_or_acquisition=False,
        scope='Independent arithmetic/chronology/trace/coverage replay; not a second training algorithm or acquisition optimality proof. Validation uses retrospectively calibrated full-validation surrogate, while test freezes it before test outcomes.',
        wall_seconds=time.perf_counter()-start,
        hashes={p.resolve().relative_to(WORKSPACE).as_posix():sha(p) for p in [Path(__file__),fd/'forecast_archive.csv',fd/'reference_targets.csv',fd/'candidate_days.csv',rd/'trajectories.jsonl',rd/'cases.csv',rd/'archive_snapshots.json',curves_path,
            rd/'headline_summary.json',rd/'coverage_curves.csv',rd/'cost_summary.csv',rd/'household_curves.csv',rd/'pair_curves.csv',rd/'month_curves.csv']})
    (rd/'independent_verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'hashes'}, indent=2))


if __name__ == '__main__':
    main()
