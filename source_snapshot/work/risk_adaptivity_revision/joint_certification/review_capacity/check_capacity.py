"""Independent capped endpoint checks and paired cohort reconciliation.

The capped-width producer is not imported. Exact verification groups capped
simplex vertices by equal prefix answers. An independent 12-variable endpoint
LP checks first/middle/last blocks in each system, every batch and contrast.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
import hashlib
import importlib.util
from itertools import combinations
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ROOT = BASE.parents[1]
INPUT = BASE/'joint_certification/assurance_feasibility/verify_assurance.py'
spec = importlib.util.spec_from_file_location('capacity_checker_source_binding', INPUT)
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)
SETS = tuple(q for n in range(6) for q in combinations(range(1, 6), n))
HALF = F(1, 2)
TOL = 2e-9


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p, obj):
    Path(p).write_text(json.dumps(binding.clean(obj), indent=2)+'\n', encoding='utf-8')


def vertex_groups(cap):
    supports = list(combinations(range(6), int(1/cap)))
    grouped = {}
    for q in SETS:
        groups = defaultdict(list)
        for ix, support in enumerate(supports):
            groups[tuple(sum(h < k for h in support) for k in q)].append(ix)
        grouped[q] = list(groups.values())
    return supports, grouped


def vertex_widths(C, cap, cached):
    """Exact endpoint-pair maxima from integral vertices, without slopes.

    After scaling by cap, the pair polytope has integer RHS 1/cap and bounds
    [0,1]. Its rows are one total equation and segment u-v balances; changing
    the sign of the total row gives a network matrix, hence integral vertices.
    Thus both endpoints have exactly 1/cap nonzero entries equal to cap.
    Grouping their supports by prefix answers enumerates every endpoint pair.
    """
    supports, groups = cached
    vals = [[cap*sum(c[h] for h in support) for support in supports] for c in C]
    return {q: [max(max(v[i] for i in group)-min(v[i] for i in group)
                       for group in groups[q]) for v in vals] for q in SETS}


def endpoint_lp(c, cap, q):
    # u and v are feasible completions giving identical observed prefix sums.
    A = [[1.]*6+[0.]*6, [0.]*6+[1.]*6]
    rhs = [1., 1.]
    for k in q:
        A.append([float(h < k) for h in range(6)] + [-float(h < k) for h in range(6)])
        rhs.append(0.)
    objective = np.array([-float(x) for x in c]+[float(x) for x in c])
    A, rhs = np.array(A), np.array(rhs)
    opt = linprog(objective, A_eq=A, b_eq=rhs, bounds=[(0., float(cap))]*12,
                  method='highs', options={'primal_feasibility_tolerance': 1e-9,
                                           'dual_feasibility_tolerance': 1e-9})
    assert opt.success, opt.message
    equality = float(np.max(np.abs(A@opt.x-rhs)))
    bounds = max(0., float(-min(opt.x)), float(max(opt.x)-float(cap)))
    dual = float(rhs@opt.eqlin.marginals + float(cap)*sum(opt.upper.marginals))
    dual_gap = abs(float(opt.fun)-dual)
    assert max(equality, bounds, dual_gap) <= TOL
    return -float(opt.fun), {'u': opt.x[:6].tolist(), 'v': opt.x[6:].tolist(),
                            'equality_residual': equality, 'bound_residual': bounds,
                            'duality_gap': dual_gap}


def raw_answers(capacity_report):
    original, external = {}, {}
    for key, record in capacity_report['inputs'].items():
        path = ROOT/record['path']
        assert sha(path) == record['sha256']
        if key == 'original_endpoints':
            with path.open(newline='', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    t = datetime.fromisoformat(row['interval_start_utc'])
                    original[row['meter'], t] = F(int(row['end_counter_integer'])-int(row['start_counter_integer']), 10**10)
        elif key == 'external_counters':
            with path.open(newline='', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    if row['valid'] == '1':
                        t = datetime.fromisoformat(row['timestamp_utc'].replace('Z', '+00:00'))
                        external['hpm_'+row['system_id'], t] = F(row['counter_kwh'])
    return original, external


def actual_profile(ident, original, external):
    cohort, meter, day, hour = ident.split('/')
    start = datetime.fromisoformat(day).replace(hour=int(hour), tzinfo=timezone.utc)
    if cohort == 'original':
        y = [original[meter, start+timedelta(hours=h)] for h in range(6)]
    else:
        z = [external[meter, start+timedelta(hours=h)] for h in range(7)]
        y = [b-a for a, b in zip(z, z[1:])]
    assert min(y) >= 0 and sum(y) > 0
    return [v/sum(y) for v in y]


def classify(b, a):
    return 'fixed' if b <= 2 else ('adaptive_only' if a else 'neither')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--chain-dir', type=Path)
    mode.add_argument('--certificate-inputs', type=Path, help='Check bundled coefficient/certificate metadata without raw-record verification')
    p.add_argument('--capacity-dir', type=Path, default=BASE/'joint_certification/empirical_external_capacity_results')
    p.add_argument('--budget-dir', type=Path, default=BASE/'joint_certification/reading_budget/executed_external')
    p.add_argument('--results', type=Path, required=True)
    args = p.parse_args(); start = time.perf_counter()
    report = read(args.results/'report.json'); ledger = read(args.results/'ledger.json')
    assert report['status'] == ledger['status'] == 'PASS'
    assert sha(args.results/'ledger.json') == report['ledger_sha256']
    if args.certificate_inputs:
        snapshot = read(args.certificate_inputs)
        assert snapshot['ledger_sha256'] == sha(args.results/'ledger.json')
        assert snapshot['report_sha256'] == sha(args.results/'report.json')
        source = snapshot['source_rows']
        for row in source:
            row['coefficients'] = [[F(x) for x in c] for c in row['coefficients']]
        provenance = {'mode': 'bundled_capacity_certificates',
                      'input_snapshot_sha256': sha(args.certificate_inputs),
                      'original_source_provenance': snapshot['source_provenance']}
        budgets = {r['id']: r for r in snapshot['budgets']}
        capcases = {(r['id'], r['cap_fraction']): r for r in snapshot['capacity_cases']}
        original, external = None, None
    else:
        source, provenance = binding.source_inputs(args.chain_dir)
        for path, key in [(args.capacity_dir/'empirical_capacity_report.json', 'capacity_report_sha256'),
                          (args.capacity_dir/'empirical_capacity_cases.csv', 'capacity_cases_sha256'),
                          (args.capacity_dir/'empirical_capacity_plans.json', 'capacity_plans_sha256'),
                          (args.budget_dir/'ledger.json', 'budget_ledger_sha256')]:
            assert sha(path) == report[key]
        budgets = {r['id']: r for r in read(args.budget_dir/'ledger.json')['rows']}
        capreport = read(args.capacity_dir/'empirical_capacity_report.json')
        original, external = raw_answers(capreport)
        with (args.capacity_dir/'empirical_capacity_cases.csv').open(newline='', encoding='utf-8-sig') as f:
            capcases = {(r['id'], r['cap_fraction']): r for r in csv.DictReader(f)}
    rows = {(r['id'], r['cap']): r for r in ledger['rows']}
    assert len(rows) == len(ledger['rows']) == 2*len(source)
    systems = defaultdict(list)
    for r in source:
        systems['/'.join(r['id'].split('/')[:2])].append(r['id'])
    sampled = set()
    for values in systems.values():
        values.sort()
        sampled.update(values[i] for i in (0, len(values)//2, len(values)-1))
    cached = {cap: vertex_groups(cap) for cap in (F(1), F(1, 2), F(1, 3))}
    checks = Counter(); endpoints = []; reconciled = []
    maxdiff = maxeq = maxbounds = maxgap = 0.
    for ix, case in enumerate(source, 1):
        C = case['coefficients']; ident = case['id']; budget = budgets[ident]
        assert budget['coefficient_digest'] == case['coefficient_digest']
        uncap = vertex_widths(C, F(1), cached[F(1)])
        uncapped_q = min((q for q in SETS if max(uncap[q]) <= HALF), key=lambda q: (len(q), q))
        assert len(uncapped_q) == budget['fixed_minimum_readings']
        uncapped_state = classify(len(uncapped_q), budget['adaptive_minimum_readings'] is not None)
        x = actual_profile(ident, original, external) if not args.certificate_inputs else None
        for cap in (F(1, 2), F(1, 3)):
            r = rows[ident, str(cap)]; archived = capcases[ident, str(cap)]
            assert r['coefficient_digest'] == case['coefficient_digest']
            values = vertex_widths(C, cap, cached[cap])
            saved = {tuple(z['query']): F(z['width']) for z in r['all_fixed_batches']}
            assert set(saved) == set(SETS)
            for q in SETS:
                assert max(values[q]) == saved[q], (ident, cap, q, max(values[q]), saved[q])
                checks['exact_fixed_batch_width_equalities'] += 1
                if ident in sampled:
                    for contrast, c in enumerate(C):
                        value, detail = endpoint_lp(c, cap, q)
                        discrepancy = abs(value-float(values[q][contrast]))
                        assert discrepancy <= TOL, (ident, cap, q, contrast, discrepancy)
                        maxdiff = max(maxdiff, discrepancy)
                        maxeq = max(maxeq, detail['equality_residual'])
                        maxbounds = max(maxbounds, detail['bound_residual'])
                        maxgap = max(maxgap, detail['duality_gap'])
                        endpoints.append({'id': ident, 'cap': str(cap), 'batch': list(q), 'contrast': contrast,
                                          'exact_width': str(values[q][contrast]), 'lp_width': value, **detail})
                        checks['endpoint_LPs'] += 1
            best = min((q for q in SETS if saved[q] <= HALF), key=lambda q: (len(q), q))
            assert list(best) == r['capped_minimum_batch'] and len(best) == r['capped_fixed_budget']
            assert saved[best] == F(r['capped_batch_worst_width'])
            assert len(uncapped_q) == r['uncapped_fixed_budget']
            assert uncapped_state == r['uncapped_state']
            compatible = (max(x) <= cap) if x is not None else (archived['actual_record_satisfies_cap'] == 'True')
            assert compatible == r['compatible'] == (archived['actual_record_satisfies_cap'] == 'True')
            if x is not None:
                assert abs(float(max(x))-float(archived['largest_recorded_hour_fraction'])) <= 1e-14
            adaptive = float(archived['adaptive_guarantee']) <= .5+1e-8
            assert adaptive == (archived['adaptive_guarantees_half'] == 'True')
            capped_state = classify(len(best), adaptive)
            assert capped_state == r['capped_state']
            assert r['was_reading_saving_case'] == (uncapped_state == 'adaptive_only')
            assert (len(best) <= 2) == (archived['det_batch_guarantees_half'] == 'True')
            checks['minimum_fixed_budget_checks'] += 1
            checks['raw_record_compatibility_checks' if x is not None else 'carried_compatibility_flags'] += 1
            checks['paired_state_checks'] += 1
            reconciled.append(r)
        if ix % 150 == 0:
            print(json.dumps({'blocks': ix, 'checks': dict(checks), 'seconds': time.perf_counter()-start}), flush=True)
    for group, summary in report['summaries'].items():
        key, cap = group.rsplit('/cap=', 1)
        selected = [r for r in reconciled if r['cap'] == cap and key in (r['cohort'], r['cohort']+'/'+r['system'])]
        valid = [r for r in selected if r['compatible']]
        savings = [r for r in selected if r['uncapped_state'] == 'adaptive_only']
        retained = [r for r in savings if r['compatible']]
        transitions = Counter(r['uncapped_state']+'->'+r['capped_state'] for r in valid)
        expected = {'all_blocks': len(selected), 'compatible_blocks': len(valid),
                    'excluded_blocks': len(selected)-len(valid), 'paired_transitions': dict(sorted(transitions.items())),
                    'uncapped_fixed_budget_histogram_on_compatible': dict(sorted(Counter(str(r['uncapped_fixed_budget']) for r in valid).items())),
                    'capped_fixed_budget_histogram_on_compatible': dict(sorted(Counter(str(r['capped_fixed_budget']) for r in valid).items())),
                    'original_reading_saving_cases': len(savings), 'saving_cases_excluded': len(savings)-len(retained),
                    'saving_cases_compatible': len(retained),
                    'saving_cases_now_fixed_at_most_two': sum(r['capped_fixed_budget'] <= 2 for r in retained),
                    'saving_cases_still_adaptive_only': sum(r['capped_state'] == 'adaptive_only' for r in retained),
                    'new_adaptive_only_from_uncapped_neither': transitions['neither->adaptive_only'],
                    'uncapped_min_fixed_readings_on_compatible': sum(r['uncapped_fixed_budget'] for r in valid),
                    'capped_min_fixed_readings_on_compatible': sum(r['capped_fixed_budget'] for r in valid)}
        assert expected == summary, (group, expected, summary)
        checks['summary_groups'] += 1
    endpoint_path = args.results/'endpoint_lp_checks.json'
    dump(endpoint_path, {'status': 'PASS', 'cases': endpoints})
    if not args.certificate_inputs:
        snapshot = {'source_rows': source, 'source_provenance': provenance,
                    'budgets': [{'id': r['id'], 'coefficient_digest': r['coefficient_digest'],
                                 'fixed_minimum_readings': r['fixed_minimum_readings'],
                                 'adaptive_minimum_readings': r['adaptive_minimum_readings']} for r in budgets.values()],
                    'capacity_cases': [{k: r[k] for k in ('id', 'cap_fraction', 'actual_record_satisfies_cap',
                                                        'largest_recorded_hour_fraction', 'adaptive_guarantee',
                                                        'adaptive_guarantees_half', 'det_batch_guarantees_half')}
                                       for r in capcases.values()],
                    'ledger_sha256': sha(args.results/'ledger.json'), 'report_sha256': sha(args.results/'report.json')}
        dump(args.results/'checker_inputs.json', snapshot)
    result = {'status': 'PASS', 'checks': dict(checks), 'selected_block_ids': sorted(sampled),
              'selection_rule': 'First, middle (floor(n/2)), and last sorted block ID in every source/system, without outcomes.',
              'exact_check_method': 'Integral endpoint-pair vertices grouped by equal prefix observations; no marginal-slope formula or producer import.',
              'endpoint_LP_tolerance': TOL, 'maximum_endpoint_width_discrepancy': maxdiff,
              'maximum_endpoint_equality_residual': maxeq, 'maximum_endpoint_bound_residual': maxbounds,
              'maximum_endpoint_duality_gap': maxgap,
              'adaptive_scope': 'Existing capped adaptive classifications are joined; their endpoint verification is separate.',
              'raw_records_verified_in_this_run': not bool(args.certificate_inputs),
              'compatibility_scope': ('Saved compatibility metadata only; no raw-record verification in this replay.' if args.certificate_inputs else
                                      'Every compatibility flag recomputed from pinned original integer counters or external rational cumulative readings.'),
              'provenance': provenance, 'checker_sha256': sha(__file__),
              'ledger_sha256': sha(args.results/'ledger.json'), 'report_sha256': sha(args.results/'report.json'),
              'endpoint_output_sha256': sha(endpoint_path), 'elapsed_seconds': time.perf_counter()-start}
    dump(args.results/('certificate_check.json' if args.certificate_inputs else 'independent_check.json'), result)
    print(json.dumps(binding.clean(result), indent=2))


if __name__ == '__main__':
    main()
