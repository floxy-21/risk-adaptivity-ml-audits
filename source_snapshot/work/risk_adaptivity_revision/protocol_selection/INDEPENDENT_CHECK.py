"""Independent bounded integration check of the frozen protocol selector.

The exact mathematical certificates have separate checks. Here their source
correspondence, interface eligibility, costs, callback dispatch and cached
HTTP attribution are checked without new observations or optimization.
"""
import argparse
from collections import Counter
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
FALLBACK = BASE / 'external_validation/stored_error_fallback'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=HERE / 'independent_results')
    parser.add_argument('--results-dir', type=Path, default=HERE / 'results',
                        help='Producer output directory to verify, including clean-replay outputs')
    args = parser.parse_args()
    started = time.perf_counter()
    lock = json.loads((HERE / 'protocol_lock.json').read_text())
    assert sha(HERE / 'PROTOCOL.txt') == lock['protocol_sha256']
    for name, digest in lock['inputs'].items():
        assert sha(BASE / name) == digest
    fixed = {r['id']: r for r in json.loads((FALLBACK / 'fixed_batch_certificates.json').read_text())['certificates']}
    branches = {r['id']: r for r in json.loads((FALLBACK / 'branch_certificates.json').read_text())['certificates']}
    lower_path = BASE / 'external_validation/stored_error_sensitivity/failure_diagnostics/witnesses.json'
    excluded = {r['id'] for r in json.loads(lower_path.read_text())['witnesses']
                if F(r['delta_exact']) == F(1, 100)}
    assert len(fixed) == 29 and len(branches) == 22
    assert set(fixed) - set(branches) == excluded and len(excluded) == 7
    assert all(r['queries'] == 3 for r in fixed.values())
    scenarios = {r['id']: r for r in lock['scenarios']}
    ledger = json.loads((args.results_dir / 'case_ledger.json').read_text())
    producer_report = json.loads((args.results_dir / 'report.json').read_text())
    assert len(ledger) == 116
    assert {(r['id'], r['scenario']) for r in ledger} == {(i, s) for i in fixed for s in scenarios}
    spec = importlib.util.spec_from_file_location('reviewed_selector', HERE / 'selector.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    selector = module.Selector()
    counts = {s: Counter() for s in scenarios}
    resource_totals = {s: {'readings': 0, 'rounds': 0,
                           'http_requests': 0 if s == 'public_bulk' else None} for s in scenarios}
    executions = blocked = candidate_checks = 0
    for row in ledger:
        case_id, scenario_id = row['id'], row['scenario']
        interface = scenarios[scenario_id]
        assert row['interface_manifest'] == interface
        assert row['measurement_model'] == lock['measurement_model']
        assert row['uses_withheld_answers_for_selection'] is False
        candidates = {r['protocol']: r for r in row['candidates']}
        assert set(candidates) == {'bulk_range', 'fixed_batch', 'adaptive'}
        expected_upper = F(fixed[case_id]['certified_upper_exact'])
        assert expected_upper <= F(1, 2)
        for name, candidate in candidates.items():
            candidate_checks += 1
            expected_exclusions = set()
            if name == 'bulk_range':
                assert candidate['query_boundaries'] == [1, 2, 3, 4, 5]
                assert set(fixed[case_id]['query_boundaries']) <= set(candidate['query_boundaries'])
                assert candidate['included_certificate_boundaries'] == fixed[case_id]['query_boundaries']
                readings, rounds, requests = 5, 1, 1
                if scenario_id != 'public_bulk': expected_exclusions.add('BULK_NOT_ADMISSIBLE')
                if interface['maximum_optional_readings'] is not None and 5 > interface['maximum_optional_readings']:
                    expected_exclusions.add('EXCEEDS_OPTIONAL_READINGS')
            elif name == 'fixed_batch':
                assert candidate['query_boundaries'] == fixed[case_id]['query_boundaries']
                readings, rounds = 3, 1
                requests = 3 if scenario_id == 'public_bulk' else None
                if scenario_id == 'restricted_two_readings': expected_exclusions.add('EXCEEDS_OPTIONAL_READINGS')
            else:
                readings, rounds = 2, 2
                requests = 2 if scenario_id == 'public_bulk' else None
                if case_id not in branches:
                    expected_exclusions.add('NO_TWO_QUERY_GUARANTEE')
                    assert candidate['certificate'] is None and candidate['certified_upper_exact'] is None
                else:
                    source = branches[case_id]
                    assert candidate['first_query'] == source['first_query']
                    assert candidate['successor_boundaries'] == [v['second_query'] for v in source['lines']]
                    assert F(candidate['certified_upper_exact']) == F(source['certified_worst_branch_bound_exact']) <= F(1, 2)
                if scenario_id == 'restricted_one_round': expected_exclusions.add('EXCEEDS_INFORMATION_ROUNDS')
            assert candidate['optional_readings'] == readings and candidate['information_rounds'] == rounds
            assert candidate['http_requests'] == requests
            assert {r['code'] for r in candidate['exclusion_reasons']} == expected_exclusions
            assert len(candidate['exclusion_reasons']) == len(expected_exclusions)
            assert candidate['admissible'] == (not expected_exclusions)
            cert = candidate['certificate']
            if cert is not None:
                filename = 'branch_certificates.json' if name == 'adaptive' else 'fixed_batch_certificates.json'
                path = 'external_validation/stored_error_fallback/' + filename
                assert cert['path'] == path and cert['sha256'] == sha(BASE / path)
                assert cert['case_id'] == case_id
                if name != 'adaptive': assert F(candidate['certified_upper_exact']) == expected_upper
        if scenario_id == 'public_bulk':
            selected_name = 'bulk_range'
        elif scenario_id == 'restricted_one_round':
            selected_name = 'fixed_batch'
        elif case_id in branches:
            selected_name = 'adaptive'
        elif scenario_id == 'restricted_three_readings':
            selected_name = 'fixed_batch'
        else:
            selected_name = None
        assert row['status'] == ('CERTIFIED' if selected_name else 'ESCALATION_REQUIRED')
        assert row['selected'] == (candidates[selected_name] if selected_name else None)
        assert selector.select(case_id, deepcopy(interface)) == row
        calls = []
        def point(k):
            calls.append(('point', k))
            return F(k, 6)
        def batch(indices, *, mode):
            calls.append((mode, tuple(indices)))
            return {k: F(k, 6) for k in indices}
        if selected_name is None:
            try: selector.execute(row, read_point=point, read_batch=batch)
            except ValueError: blocked += 1
            else: raise AssertionError('Uncertified plan executed')
            assert not calls
            counts[scenario_id]['escalate'] += 1
        else:
            result = selector.execute(row, read_point=point, read_batch=batch)
            choice = row['selected']
            assert len(calls) == choice['information_rounds']
            assert len(set(result['query_boundaries'])) == choice['optional_readings']
            assert F(result['guaranteed_width_over_original_W0_upper_exact']) <= F(1, 2)
            if selected_name != 'adaptive':
                assert calls == [(selected_name, tuple(choice['query_boundaries']))]
                assert result['query_boundaries'] == choice['query_boundaries']
            else:
                assert calls[0] == ('point', branches[case_id]['first_query'])
                assert calls[1][1] in choice['successor_boundaries']
            executions += 1
            counts[scenario_id][selected_name] += 1
            resource_totals[scenario_id]['readings'] += choice['optional_readings']
            resource_totals[scenario_id]['rounds'] += choice['information_rounds']
            if choice['http_requests'] is not None: resource_totals[scenario_id]['http_requests'] += choice['http_requests']
    assert (executions, blocked, candidate_checks) == (109, 7, 348)
    assert counts == {
        'public_bulk': Counter(bulk_range=29),
        'restricted_three_readings': Counter(adaptive=22, fixed_batch=7),
        'restricted_two_readings': Counter(adaptive=22, escalate=7),
        'restricted_one_round': Counter(fixed_batch=29)}
    assert resource_totals['restricted_three_readings']['readings'] == 65
    assert resource_totals['restricted_three_readings']['rounds'] == 51
    assert resource_totals['restricted_one_round']['readings'] == 87
    assert resource_totals['restricted_one_round']['rounds'] == 29
    # Mutation and malformed response tests must reject before certification.
    certified = next(r for r in ledger if r['scenario'] == 'public_bulk')
    tampered = deepcopy(certified)
    tampered['selected']['certified_upper_exact'] = '0'
    called = []
    try: selector.execute(tampered, read_point=lambda k: called.append(k), read_batch=lambda *a, **k: called.append(a))
    except ValueError: pass
    else: raise AssertionError('Changed guarantee accepted')
    assert not called
    nested_plan_rejections = 0
    for target,field,value in [('selected','information_rounds',True),
                               ('selected','information_rounds',1.0),
                               ('selected','first_boundary',True),
                               ('selected','first_boundary',1.0),
                               ('candidate','information_rounds',True),
                               ('candidate','information_rounds',1.0)]:
        changed = deepcopy(certified)
        destination = changed['selected'] if target == 'selected' else changed['candidates'][0]
        if field == 'first_boundary': destination['query_boundaries'][0] = value
        else: destination[field] = value
        called = []
        try:
            selector.execute(changed, read_point=lambda k: called.append(k),
                             read_batch=lambda *a, **k: called.append(a))
        except ValueError: nested_plan_rejections += 1
        else: raise AssertionError('Type-aliased nested plan accepted')
        assert not called
    # Regression: JSON-like strings and bool/int equality must never turn an
    # inadmissible retrieval interface into permission to acquire observations.
    invalid_interfaces = []
    for flag in ['bulk_allowed', 'fixed_batch_allowed', 'adaptive_allowed']:
        for value in ['false', 'true', 0, None]:
            changed = deepcopy(scenarios['public_bulk'])
            changed[flag] = value
            invalid_interfaces.append(changed)
    for key in ['permitted_boundaries', 'bulk_returns_boundaries']:
        for value in [True, 1.0]:
            changed = deepcopy(scenarios['public_bulk'])
            changed[key][0] = value
            invalid_interfaces.append(changed)
    changed = deepcopy(scenarios['public_bulk'])
    del changed['adaptive_allowed']
    invalid_interfaces.extend([changed, None])
    schema_rejections = 0
    for interface in invalid_interfaces:
        changed = deepcopy(certified)
        changed['interface_manifest'] = interface
        called = []
        try:
            selector.execute(changed, read_point=lambda k: called.append(k),
                             read_batch=lambda *a, **k: called.append(a))
        except ValueError:
            schema_rejections += 1
        else:
            raise AssertionError('Malformed acquisition permission or query identifier accepted')
        assert not called
    malformed_rejections = 0
    for callback in [lambda indices, **kwargs: {}, lambda indices, **kwargs: {k: F(2) for k in indices},
                     lambda indices, **kwargs: [list(indices)],
                     lambda indices, **kwargs: {True: F(1,6),2:F(2,6),3:F(3,6),4:F(4,6),5:F(5,6)}]:
        try: selector.execute(certified, read_point=lambda k: F(0), read_batch=callback)
        except ValueError: malformed_rejections += 1
        else: raise AssertionError('Malformed or infeasible batch accepted')
    guard_rejections = 0
    for mode in ['threshold', 'error', 'budget', 'units']:
        interface = deepcopy(scenarios['public_bulk'])
        if mode == 'threshold': interface['measurement_model']['precision_over_initial_width_exact'] = '3/5'
        elif mode == 'error': interface['measurement_model']['error_bound_exact'] = '1/50'
        elif mode == 'budget': interface['maximum_optional_readings'] = -1
        else: interface['scalar_reading_unit'] = 'one_http_request'
        try: selector.select(certified['id'], interface)
        except ValueError: guard_rejections += 1
        else: raise AssertionError('Unsupported model or unit accepted')
    # Missing request costs cannot be silently optimized.
    interface = deepcopy(scenarios['restricted_three_readings'])
    interface['preference'] = ['http_requests']
    missing_cost = selector.select(certified['id'], interface)
    assert missing_cost['status'] == 'ESCALATION_REQUIRED'
    for c in missing_cost['candidates']:
        if c['protocol'] != 'bulk_range': assert 'MISSING_COST_METADATA' in {x['code'] for x in c['exclusion_reasons']}
    # Counterfactual grouping is declared, not inferred from the real API.
    case_id = sorted(branches)[0]
    interface = deepcopy(scenarios['restricted_three_readings'])
    interface['point_transport'] = 'native_multipoint_request'
    interface['preference'] = ['http_requests', 'information_rounds', 'optional_readings']
    assert selector.select(case_id, interface)['selected']['protocol'] == 'fixed_batch'
    interface['preference'] = ['optional_readings', 'information_rounds']
    assert selector.select(case_id, interface)['selected']['protocol'] == 'adaptive'
    # Independently recompute the cached descriptive HTTP statistics.
    http = BASE / 'external_validation/operational/http_benchmark_20261012'
    trials = json.loads((http / 'trials.json').read_text())
    requests = json.loads((http / 'request_log.json').read_text())['records']
    saved = json.loads((args.results_dir / 'recorded_http_summary.json').read_text())
    assert len(trials) == saved['trials'] == 30
    assert len(requests) == saved['total_requests'] == 60
    assert sum(t['requests'] for t in trials) == saved['trial_requests'] == 54
    assert sum(r['role'] == 'initial endpoint' for r in requests) == saved['initial_endpoint_setup_requests'] == 6
    for name, summary in saved['by_policy'].items():
        rows = [r for r in trials if r['policy'] == name]
        assert len(rows) == summary['trials'] == 6
        for key in ['requests', 'information_rounds', 'api_io_seconds', 'end_to_end_elapsed_seconds',
                    'body_bytes_received', 'relative_width', 'precision_success']:
            assert summary[key] == statistics.mean(float(r[key]) for r in rows)
    assert producer_report['status'] == 'PASS'
    assert producer_report['scenario_cases'] == len(ledger)
    assert producer_report['constructed_callback_executions'] == executions
    assert producer_report['blocked_dispatches'] == blocked
    assert producer_report['modified_plan_rejected_before_acquisition'] is True
    assert producer_report['protocol_lock_sha256'] == sha(HERE / 'protocol_lock.json')
    assert producer_report['selector_sha256'] == sha(HERE / 'selector.py')
    for name, actual_counts in counts.items():
        reported = producer_report['scenarios'][name]
        protocol_counts = {k: v for k, v in actual_counts.items() if k != 'escalate'}
        assert reported['cases'] == 29
        assert reported['protocol_counts'] == protocol_counts
        assert reported['certified'] == sum(protocol_counts.values())
        assert reported['escalation_required'] == actual_counts.get('escalate', 0)
        assert reported['reserved_scalar_readings'] == resource_totals[name]['readings']
        assert reported['information_rounds_total'] == resource_totals[name]['rounds']
        assert reported['planned_http_requests_total'] == resource_totals[name]['http_requests']
    report = {
        'status': 'PASS', 'case_scenario_rows': 116, 'candidate_exclusion_checks': candidate_checks,
        'constructed_callback_executions': executions, 'blocked_without_callbacks': blocked,
        'scenario_counts': {k: dict(v) for k, v in counts.items()}, 'resource_totals': resource_totals,
        'changed_plan_rejected_before_callback': True, 'malformed_batch_rejections': malformed_rejections,
        'nested_type_aliased_plan_rejections_before_callbacks': nested_plan_rejections,
        'malformed_interface_rejections_before_callbacks': schema_rejections,
        'unsupported_model_budget_unit_rejections': guard_rejections,
        'missing_cost_escalation_checked': True, 'counterfactual_native_grouping_checked': True,
        'http_trials': 30, 'http_requests': 60, 'trial_requests': 54, 'setup_requests': 6,
        'scope': 'Independent integration/source-correspondence check; exact mathematical certificates checked by existing separate programs. No new empirical, physical-calibration or optimization claim.',
        'selector_sha256': sha(HERE / 'selector.py'), 'protocol_lock_sha256': sha(HERE / 'protocol_lock.json'),
        'checked_results_directory': str(args.results_dir),
        'ledger_sha256': sha(args.results_dir / 'case_ledger.json'),
        'producer_report_sha256': sha(args.results_dir / 'report.json'),
        'recorded_http_summary_sha256': sha(args.results_dir / 'recorded_http_summary.json'),
        'source_sha256': sha(Path(__file__)),
        'seconds': time.perf_counter() - started}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
