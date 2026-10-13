"""Independently check saved-task descriptors and task-bound dispatch.

No LPs, fitting, network or observed internal responses are used. Retained
endpoints are checked from the exact decimal tokens of cached public data.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(HERE))
from bound_workflow import BoundWorkflow


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=HERE / 'independent_binding_results')
    args = parser.parse_args()
    started = time.perf_counter()
    manifest_path = HERE / 'task_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['schema'] == 'saved-audit-task-binding-v1'
    for relative, digest in manifest['inputs'].items():
        assert sha(BASE / relative) == digest
    geometry = json.loads((BASE / 'external_validation/replay/geometry.json').read_text())
    cases = {r['id']: r for r in geometry['cases']}
    cert_path = BASE / 'external_validation/stored_error_fallback/fixed_batch_certificates.json'
    certs = {r['id']: r for r in json.loads(cert_path.read_text())['certificates']}
    forecasts = BASE / 'external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv'
    counters = BASE / 'external_heatpump/hourly/train_test_hourly_counters.csv'
    assert sha(forecasts) == geometry['manifest']['forecast_sha256']
    assert sha(counters) == geometry['manifest']['counter_sha256']
    cache = json.loads((BASE / 'external_heatpump/july_cache_manifest.json').read_text())
    raw_by_system = {}
    for source in cache['sources']:
        path = BASE / 'external_heatpump' / source['raw_path'].replace('\\', '/')
        assert sha(path) == source['sha256']
        data = json.loads(path.read_text(), parse_float=Decimal)
        raw_by_system[source['system_id']] = dict(data['heatpump_elec_kwh'])
    assert len(manifest['tasks']) == 29
    assert {r['task']['case_id'] for r in manifest['tasks']} == set(certs)
    endpoints = 0
    task_ids = set()
    for record in manifest['tasks']:
        task = record['task']
        case_id = task['case_id']
        assert case_id not in task_ids
        task_ids.add(case_id)
        case, certificate = cases[case_id], certs[case_id]
        assert canonical_digest(task) == record['task_sha256']
        assert task['system_id'] == case['system_id'] == certificate['system_id']
        assert task['feed_key'] == 'heatpump_elec_kwh'
        assert task['models'] == [case['model_a'], case['model_b']]
        assert task['forecast_issue_utc'] == case['forecast_issue_utc']
        start = datetime.fromisoformat(case['day']).replace(tzinfo=timezone.utc) + timedelta(hours=case['start_hour'])
        end = start + timedelta(hours=6)
        stamp = lambda dt: dt.isoformat().replace('+00:00', 'Z')
        assert task['start_utc'] == stamp(start) and task['end_utc'] == stamp(end)
        assert task['query_timestamps_utc'] == {str(k): stamp(start + timedelta(hours=k)) for k in range(1, 6)}
        raw = raw_by_system[case['system_id']]
        c0, c6 = F(raw[int(start.timestamp())]), F(raw[int(end.timestamp())])
        assert F(task['start_counter_kwh_exact']) == c0
        assert F(task['end_counter_kwh_exact']) == c6
        assert F(task['total_kwh_exact']) == c6 - c0 == F(case['E_exact']) > 0
        endpoints += 2
        coefficients = [F.from_float(float(x)) for x in case['c']]
        assert list(map(F, task['contrast_coefficients_exact'])) == coefficients
        assert list(map(F, certificate['original_coefficients_exact'])) == coefficients
        assert F(task['contrast_constant_exact']) == F.from_float(float(case['d']))
        assert task['reading_unit'] == 'kWh cumulative stored readout'
        assert F(task['error_bound_over_total_exact']) == F(1, 100)
        assert F(task['precision_over_initial_width_exact']) == F(1, 2)
        assert task['forecast_artifact_sha256'] == sha(forecasts)
        assert task['counter_artifact_sha256'] == sha(counters)
        assert task['certificate_artifact_sha256'] == sha(cert_path)
    workflow = BoundWorkflow()
    assert set(workflow.tasks) == task_ids
    executed = blocked = 0
    # Fixed constructed nonuniform profile: only dispatch/normalization tests.
    x = [F(1, 21), F(2, 21), F(3, 21), F(4, 21), F(5, 21), F(6, 21)]
    def envelopes(request):
        task = request['task']
        start, total = F(task['start_counter_kwh_exact']), F(task['total_kwh_exact'])
        return [{'task_sha256': request['task_sha256'], 'system_id': task['system_id'],
                 'feed_key': task['feed_key'], 'boundary': k,
                 'timestamp_utc': task['query_timestamps_utc'][str(k)],
                 'reading_unit': task['reading_unit'],
                 'counter_kwh_exact': str(start + total * sum(x[:k]))}
                for k in request['boundaries']]
    for case_id in sorted(task_ids):
        for interface in workflow.selector.lock['scenarios']:
            task = workflow.task(case_id)
            plan = workflow.plan(task, interface)
            called = []
            def point(request):
                called.append(request)
                return envelopes(request)[0]
            def batch(request):
                called.append(request)
                return envelopes(request)
            if plan['selection']['status'] == 'ESCALATION_REQUIRED':
                try: workflow.execute(plan, read_point=point, read_batch=batch)
                except ValueError: blocked += 1
                else: raise AssertionError('Uncertified task was dispatched')
                assert not called
                continue
            result = workflow.execute(plan, read_point=point, read_batch=batch)
            choice = plan['selection']['selected']
            assert len(called) == choice['information_rounds']
            assert len(set(result['query_boundaries'])) == choice['optional_readings']
            assert result['task_sha256'] == canonical_digest(task)
            assert result['task_manifest_sha256'] == sha(manifest_path)
            for request in called:
                assert request['task'] == task and request['task_sha256'] == result['task_sha256']
            assert {k: F(v) for k, v in result['normalized_stored_answers_exact'].items()} == {
                str(k): sum(x[:k]) for k in result['query_boundaries']}
            assert F(result['guaranteed_width_over_original_W0_upper_exact']) <= F(1, 2)
            executed += 1
    assert (executed, blocked) == (109, 7)
    case_id = sorted(task_ids)[0]
    task = workflow.task(case_id)
    interface = workflow.selector.scenario('public_bulk')
    plan = workflow.plan(task, interface)
    task_rejections = response_rejections = 0
    for field, value in [('system_id', True), ('system_id', 1.0),
                         ('models', list(reversed(task['models']))), ('contrast_constant_exact', '0'),
                         ('feed_key', 'other_feed'), ('forecast_artifact_sha256', '0' * 64),
                         ('end_counter_kwh_exact', '0')]:
        changed = deepcopy(task)
        changed[field] = value
        assert canonical_digest(changed) != canonical_digest(task)
        try: workflow.plan(changed, interface)
        except ValueError: task_rejections += 1
        else: raise AssertionError('Changed task binding accepted')
    for field, value in [('system_id', True), ('boundary', True), ('task_sha256', '0' * 64),
                         ('timestamp_utc', task['start_utc']), ('counter_kwh_exact', 1.25),
                         ('counter_kwh_exact', '1/0'), ('reading_unit', 'Wh'), ('feed_key', 'other_feed'),
                         ('boundary', [1]), ('boundary', {'index': 1})]:
        def bad_batch(request):
            response = envelopes(request)
            response[0][field] = value
            return response
        try: workflow.execute(plan, read_point=lambda request: None, read_batch=bad_batch)
        except ValueError: response_rejections += 1
        else: raise AssertionError('Mismatched response accepted')
    tampered = deepcopy(plan)
    tampered['task_sha256'] = '0' * 64
    calls = []
    try: workflow.execute(tampered, read_point=lambda r: calls.append(r), read_batch=lambda r: calls.append(r))
    except ValueError: pass
    else: raise AssertionError('Changed bound plan accepted')
    assert not calls
    nested_plan_rejections = 0
    for value in [True, 1.0]:
        for field in ['information_rounds', 'first_boundary']:
            changed = deepcopy(plan)
            if field == 'first_boundary': changed['selection']['selected']['query_boundaries'][0] = value
            else: changed['selection']['selected'][field] = value
            calls = []
            try: workflow.execute(changed, read_point=lambda r: calls.append(r), read_batch=lambda r: calls.append(r))
            except ValueError: nested_plan_rejections += 1
            else: raise AssertionError('Type-aliased bound plan accepted')
            assert not calls
    report = {
        'status': 'PASS', 'task_descriptors_checked': 29, 'exact_retained_endpoints_checked': endpoints,
        'coefficient_vectors_and_constants_checked': 29, 'source_forecast_and_counter_hashes_checked': True,
        'constructed_nonuniform_dispatches': executed, 'blocked_without_callbacks': blocked,
        'changed_task_rejections': task_rejections, 'bad_response_rejections': response_rejections,
        'changed_bound_plan_rejected_before_callback': True,
        'nested_type_aliased_bound_plan_rejections_before_callbacks': nested_plan_rejections,
        'scope': 'Independent saved-task/source binding and constructed integration verification; not provider authentication, physical calibration, fresh empirical replay or new certificate proof',
        'task_manifest_sha256': sha(manifest_path), 'bound_workflow_sha256': sha(HERE / 'bound_workflow.py'),
        'selector_sha256': sha(HERE / 'selector.py'), 'source_sha256': sha(Path(__file__)),
        'seconds': time.perf_counter() - started}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
