"""Independent error-eliminated LP audit; no source model imports or network.

An error-bounded answer shared by endpoint records u,v exists iff their
prefix sums differ by at most 2 delta.  A first answer t imposes separate
prefix bands t +/- delta on both records.  This eliminates all five latent
errors rather than copying the production lifted-space formulation.
"""
import itertools
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
COUNT = 0
MAX_RESIDUAL = 0.0


def solve(c, A, b, E, f, bounds):
    global COUNT, MAX_RESIDUAL
    result = linprog(c, A_ub=np.array(A), b_ub=np.array(b),
                     A_eq=np.array(E), b_eq=np.array(f), bounds=bounds,
                     method="highs", options={"primal_feasibility_tolerance": 1e-9,
                                              "dual_feasibility_tolerance": 1e-9})
    assert result.success, result.message
    residual = max(0., float(np.max(np.array(A) @ result.x-np.array(b))),
                   float(np.max(np.abs(np.array(E) @ result.x-np.array(f)))))
    for value, (lo, hi) in zip(result.x, bounds):
        if lo is not None:
            residual = max(residual, lo-value)
        if hi is not None:
            residual = max(residual, value-hi)
    assert residual < 2e-8
    MAX_RESIDUAL = max(MAX_RESIDUAL, residual)
    COUNT += 1
    return -float(result.fun)


def batch_value(c, delta, queries):
    A, b = [], []
    for query in queries:
        row = np.zeros(12)
        row[:query+1] = 1
        row[6:6+query+1] = -1
        A += [row, -row]
        b += [2*delta, 2*delta]
    E = [np.r_[np.ones(6), np.zeros(6)], np.r_[np.zeros(6), np.ones(6)]]
    return solve(np.r_[-c, c], A, b, E, [1., 1.], [(0., None)]*12)


def adaptive_value(c, delta, first, seconds):
    n = 12*len(seconds)+2
    eta, answer = n-2, n-1
    objective = np.zeros(n)
    objective[eta] = -1
    A, b, E, f = [], [], [], []
    for index, second in enumerate(seconds):
        u, v = 12*index, 12*index+6
        width = np.zeros(n)
        width[u:u+6] = -c
        width[v:v+6] = c
        width[eta] = 1
        A.append(width); b.append(0.)
        for offset in (u, v):
            total = np.zeros(n); total[offset:offset+6] = 1
            E.append(total); f.append(1.)
            band = np.zeros(n); band[offset:offset+first+1] = 1
            band[answer] = -1
            A += [band, -band]; b += [delta, delta]
        shared = np.zeros(n)
        shared[u:u+second+1] = 1
        shared[v:v+second+1] = -1
        A += [shared, -shared]; b += [2*delta, 2*delta]
    return solve(objective, A, b, E, f,
                 [(0., None)]*(n-2)+[(None, None), (-delta, 1+delta)])


def main():
    start = time.perf_counter()
    inputs = {r['id']: r for r in json.loads((HERE/'inputs.json').read_text())}
    witnesses = json.loads((HERE/'witnesses.json').read_text())
    comparisons = []
    batches = list(itertools.combinations(range(5), 2))
    for row in witnesses:
        c = np.array(inputs[row['id']]['c_scaled'])
        delta = row['delta']
        d = [batch_value(c, delta, q) for q in batches]
        a = [adaptive_value(c, delta, k, [j for j in range(5) if j != k]) for k in range(5)]
        supports = [adaptive_value(c, delta, r['first'], r['seconds']) for r in row['support_LPs']]
        discrepancies = [abs(x-y) for x, y in zip(d, row['deterministic_batch_widths'])]
        discrepancies += [abs(x-r['value']) for x, r in zip(a, row['first_query_LPs'])]
        discrepancies += [abs(x-r['value']) for x, r in zip(supports, row['support_LPs'])]
        assert max(discrepancies) < 2e-8
        comparisons.append({'id': row['id'], 'delta': delta,
                            'adaptive': min(a), 'deterministic': min(d),
                            'support': min(supports), 'max_discrepancy': max(discrepancies)})
    groups = []
    for delta in (0, .001, .01):
        rows = [r for r in comparisons if r['delta'] == delta]
        passing = [r for r in rows if r['adaptive'] <= .5+2e-8]
        failing = [r for r in rows if r['adaptive'] > .5+2e-8]
        groups.append({'delta': delta, 'cases': len(rows), 'passing': len(passing),
                       'smallest_passing_margin': min(.5-r['adaptive'] for r in passing),
                       'smallest_failing_excess': min((r['adaptive']-.5 for r in failing), default=None),
                       'deterministic_passing': sum(r['deterministic'] <= .5+2e-8 for r in rows)})
    report = {'status': 'PASS', 'scope': 'Independent error-eliminated LP reproduction at the same three locked levels',
              'cases': len(inputs), 'case_level_evaluations': len(comparisons), 'LP_count': COUNT,
              'max_primal_residual': MAX_RESIDUAL,
              'max_production_discrepancy': max(r['max_discrepancy'] for r in comparisons),
              'groups': groups, 'seconds': time.perf_counter()-start,
              'interpretation': 'Floating-point validation, not exact rational or interval-arithmetic certification.'}
    (HERE/'INDEPENDENT_REVIEW_CHECKS.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
