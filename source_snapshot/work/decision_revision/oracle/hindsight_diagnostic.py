"""Development-only, non-executable hindsight lower bound on certificate cost.

Enumerates every subset in increasing cardinality. Hidden reference values
are intentionally used here; this is an oracle diagnostic, not an acquisition
method and never contributes an empirical operational-improvement claim.
Imports no study acquisition, evaluation, or certificate implementation.
"""
from pathlib import Path
from itertools import combinations, product
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TRACE = ROOT / 'work/external_deadline/validation/trajectories.jsonl'
REFERENCE = ROOT / 'work/external_deadline/fitted/reference_targets.csv'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def bounds(a, b, visible, totals):
    """Independent direct linear extrema, without a closure dependency."""
    c = 2 * (b - a)
    known = np.isfinite(visible)
    fixed = math.fsum(float(x*x-z*z) for x, z in zip(a, b))
    fixed += math.fsum(float(c[i]*visible[i]) for i in np.flatnonzero(known))
    lo, hi = fixed, fixed
    for g, total in enumerate(totals):
        indices = list(range(6*g, 6*(g+1)))
        missing = [i for i in indices if not known[i]]
        if not missing:
            continue
        residual = float(total) - math.fsum(float(visible[i]) for i in indices if known[i])
        assert residual >= -1e-10 * max(1., abs(total))
        residual = max(0., residual)
        lo += residual * min(c[missing])
        hi += residual * max(c[missing])
    return lo / len(a), hi / len(a)


def sign(lo, hi):
    tol = 1e-10 * max(1., abs(lo), abs(hi))
    if hi < -tol:
        return 'a'
    if lo > tol:
        return 'b'
    return None


def corner_check(a, b, visible, totals, endpoints):
    """Independently realize every remaining product-simplex vertex."""
    choices, residuals = [], []
    for g, total in enumerate(totals):
        indices = list(range(6*g, 6*(g+1)))
        missing = [i for i in indices if not math.isfinite(visible[i])]
        if missing:
            choices.append(missing)
            residuals.append(max(0., float(total) - math.fsum(float(visible[i]) for i in indices if math.isfinite(visible[i]))))
    losses = []
    for vertex in product(*choices):
        y = np.nan_to_num(visible, nan=0.)
        for i, energy in zip(vertex, residuals):
            y[i] = energy
        # Recompute squared losses, not the linear endpoint formula.
        losses.append(math.fsum(float((x-v)**2-(z-v)**2) for x,z,v in zip(a,b,y)) / len(a))
    discrepancy = max(abs(min(losses)-endpoints[0]), abs(max(losses)-endpoints[1]))
    assert discrepancy <= 2e-9 * max(1., *map(abs, endpoints), *map(abs, losses))
    return len(losses), discrepancy


def main():
    started = time.perf_counter()
    assert 'validation' in str(TRACE)
    pin = {'status': 'frozen_before_diagnostic', 'created_utc': datetime.now(timezone.utc).isoformat(),
           'scope': 'Previously used DEVELOPMENT validation only; hindsight diagnostic, not a held-out efficacy test.',
           'inputs': {str(p.relative_to(ROOT)): sha(p) for p in [TRACE, REFERENCE, Path(__file__)]}}
    (HERE/'input_manifest.json').write_text(json.dumps(pin, indent=2)+'\n')
    ref = pd.read_csv(REFERENCE, dtype={'household_id': str})
    ref = ref[ref.period == 'validation'].copy()
    ref['day'] = ref.timestamp_utc.str[:10]
    references = {(h, d): group.sort_values('timestamp_utc').energy_kwh.to_numpy(float)
                  for (h, d), group in ref.groupby(['household_id', 'day']) if len(group)==24}
    rows = []
    subsets_checked = corners_checked = 0
    max_corner_error = max_initial_error = 0.
    with TRACE.open(encoding='utf-8') as trace:
        for line_no, line in enumerate(trace, 1):
            case = json.loads(line)
            a, b = np.asarray(case['a']), np.asarray(case['b'])
            observed = np.array([np.nan if x is None else x for x in case['initial_observed']])
            totals = np.asarray(case['totals'])
            truth = references[(case['household_id'], case['day_utc'][:10])]
            assert len(truth) == 24 and np.isfinite(truth).all()
            visible = np.isfinite(observed)
            assert np.max(np.abs(observed[visible]-truth[visible])) < 1e-9
            endpoints = bounds(a, b, observed, totals)
            initial_error = max(abs(x-y) for x,y in zip(endpoints, case['policies']['exact']['initial_bounds']))
            max_initial_error = max(max_initial_error, initial_error)
            assert initial_error < 1e-9 * max(1., *map(abs, endpoints))
            n, discrepancy = corner_check(a, b, observed, totals, endpoints)
            corners_checked += n; max_corner_error = max(max_corner_error, discrepancy)
            true_delta = float(np.mean((a-truth)**2-(b-truth)**2))
            assert endpoints[0]-1e-9 <= true_delta <= endpoints[1]+1e-9
            missing = list(np.flatnonzero(~visible))
            optimum = witness = final_sign = None
            tested = 0
            for size in range(len(missing)+1):
                for query in combinations(missing, size):
                    candidate = observed.copy()
                    if query:
                        candidate[list(query)] = truth[list(query)]
                    lo, hi = bounds(a, b, candidate, totals)
                    tested += 1
                    verdict = sign(lo, hi)
                    if verdict:
                        assert (verdict == 'a' and true_delta < 0) or (verdict == 'b' and true_delta > 0)
                        optimum, witness, final_sign = size, list(map(int, query)), verdict
                        n, discrepancy = corner_check(a, b, candidate, totals, (lo, hi))
                        corners_checked += n; max_corner_error = max(max_corner_error, discrepancy)
                        break
                if optimum is not None:
                    break
            subsets_checked += tested
            # A strict certificate at a full record must be available on this
            # case; actual near-zero ties would instead be retained as missing.
            row = {k: case[k] for k in ['case_id','household_id','day_utc','pair','learned_pair','seed']}
            row.update(initially_uncertified=sign(*endpoints) is None, initial_unknown=len(missing),
                       oracle_minimum_requests=optimum, oracle_witness=json.dumps(witness),
                       oracle_sign=final_sign, subsets_tested=tested)
            for policy, result in case['policies'].items():
                row[policy+'_historical_requests'] = result['paid_requests']
                if result['certification_cost'] is not None:
                    assert optimum is not None and optimum <= result['certification_cost']
            rows.append(row)
            if line_no % 5000 == 0:
                print(json.dumps({'cases':line_no,'seconds':time.perf_counter()-started}), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(HERE/'cases.csv', index=False, float_format='%.17g')
    summaries = {}
    curves = []
    for population, f in [('all', frame), ('initially_uncertified', frame[frame.initially_uncertified])]:
        columns = ['oracle_minimum_requests'] + [x for x in frame if x.endswith('_historical_requests')]
        summaries[population] = {'cases':len(f), 'households':f.household_id.nunique(),
            'household_macro_mean_requests':{c:float(f.groupby('household_id')[c].mean().mean()) for c in columns},
            'oracle_counts':{str(k):int(v) for k,v in f.oracle_minimum_requests.value_counts(dropna=False).sort_index().items()}}
        for budget in range(7):
            rates = f.assign(certified=f.oracle_minimum_requests.notna() & (f.oracle_minimum_requests <= budget)).groupby('household_id').certified.mean()
            curves.append({'population':population,'budget':budget,'coverage':float(rates.mean())})
    pd.DataFrame(curves).to_csv(HERE/'oracle_coverage_curves.csv', index=False, float_format='%.17g')
    for relative, value in pin['inputs'].items():
        assert sha(ROOT/relative) == value
    report = {'status':'passed','created_utc':datetime.now(timezone.utc).isoformat(),
        'scope':pin['scope'], 'interpretation':'Unattainable-information lower bound: the query subset is chosen using the hidden reference. No operational benefit or test-set confirmation is established.',
        'cases':len(frame), 'subsets_checked':subsets_checked, 'squared_loss_vertices_checked':corners_checked,
        'maximum_initial_endpoint_discrepancy':max_initial_error, 'maximum_vertex_discrepancy':max_corner_error,
        'summaries':summaries, 'oracle_curves':curves, 'seconds':time.perf_counter()-started,
        'input_manifest_sha256':sha(HERE/'input_manifest.json'), 'cases_sha256':sha(HERE/'cases.csv')}
    (HERE/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
