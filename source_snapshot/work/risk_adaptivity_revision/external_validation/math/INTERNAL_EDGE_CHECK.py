"""Independent edge checks for the delegated internal review (no external data)."""
import importlib.util
import argparse
import itertools
import json
from pathlib import Path
import sys
from fractions import Fraction
import numpy as np
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'INTERNAL_EDGE_CHECKS.json')
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('reviewed_prototype', ROOT/'robust_two_query.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
out = {'scope': 'Internal AI reviewer edge checks; no heldout data; not human validation'}

for name, c in [('zero_contrast', np.zeros(3)), ('one_query_exact', np.array([1.,0.,0.]))]:
    model = m.Model(np.empty((0,3)), np.empty(0), c, np.eye(3), [(0.,1.)]*3)
    try:
        result = m.mean_hardest(model, list(itertools.combinations(range(3),2)))
        out[name] = {'status':'returned', 'result':result}
    except Exception as exc:
        out[name] = {'status':'exception', 'type':type(exc).__name__, 'message':str(exc)}

out['constant_contrast_uncertain_total'] = []
for delta,alpha in [(0.,0.),(.01,0.),(0.,.01),(.01,.01)]:
    model = m.meter_model(np.ones(6), storage_error=delta, relative_increment_error=alpha)
    width = m.worst_batch(model,[])[0]
    analytic = (1+2*delta)/(1-alpha) - (1-2*delta)/(1+alpha)
    out['constant_contrast_uncertain_total'].append({'delta':delta,'alpha':alpha,'LP_width':width,
        'analytic_width':analytic,'absolute_error':abs(width-analytic)})

out['K_family_exact_precision_witnesses'] = []
for K in range(2,9):
    threshold = Fraction(1,K)
    only_one = True
    for j in range(K):
        a = [Fraction(1,2*K) if i==j else Fraction(2*K-1,2*K*(K-1)) for i in range(K)]
        widths = a + [a[i]+a[-1] for i in range(K-1)]
        successes = [i for i,w in enumerate(widths) if w <= threshold]
        only_one &= successes == [j]
        assert sum(a) == 1
    out['K_family_exact_precision_witnesses'].append({'K':K,'exact_rational_check':only_one})

def independent_batch_risk(model, batches, probabilities):
    # Independent construction: one common record and endpoint pair per batch.
    # No eta, width inequalities, or prototype copies/solve helper is reused.
    n = len(model.c); size = n*(1+2*len(batches))
    objective = np.zeros(size)
    Aub = []; bub = []; Aeq = []; beq = []
    for copy in range(1+2*len(batches)):
        for row, rhs in zip(model.A, model.b):
            expanded = np.zeros(size); expanded[copy*n:(copy+1)*n] = row
            Aub.append(expanded); bub.append(rhs)
    for k, (Q, probability) in enumerate(zip(batches, probabilities)):
        u = (1+2*k)*n; v=u+n
        objective[u:u+n] = -probability*model.c
        objective[v:v+n] = probability*model.c
        for q in Q:
            for start in (u,v):
                row = np.zeros(size); row[:n] = -model.queries[q]
                row[start:start+n] = model.queries[q]
                Aeq.append(row); beq.append(0.)
    bounds = model.bounds*(1+2*len(batches))
    result = linprog(objective, A_ub=np.asarray(Aub) if Aub else None,
        b_ub=np.asarray(bub) if bub else None, A_eq=np.asarray(Aeq), b_eq=np.asarray(beq),
        bounds=bounds, method='highs', options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    assert result.success, result.message
    return -result.fun

models = [('three_coordinate',m.three_coordinate())]
for delta,alpha in [(0.,0.),(.001,0.),(.01,0.),(0.,.01),(.001,.01)]:
    models.append((f'meter_delta{delta}_alpha{alpha}',m.meter_model([0,0,1,1,0,1],storage_error=delta,relative_increment_error=alpha)))
rng = np.random.default_rng(20261012)
for index in range(12):
    n=3+index%4
    A=rng.normal(size=(n+2,n)); b=.25+rng.random(n+2); c=rng.normal(size=n); queries=rng.normal(size=(5,n))
    models.append((f'coupled{index}',m.Model(A,b,c,queries,[(-1.,1.)]*n)))
out['independent_extracted_policy_upper_checks'] = []
for name,model in models:
    batches=list(itertools.combinations(range(len(model.queries)),2))
    report=m.mean_hardest(model,batches)
    record=np.asarray(report['record'])
    upper=independent_batch_risk(model,batches,report['batch_probabilities'])
    constraint_violation=max(0.,float(np.max(model.A@record-model.b))) if len(model.b) else 0.
    bounds_violation=max([0.]+[lo-value for (lo,hi),value in zip(model.bounds,record) if lo is not None]+[value-hi for (lo,hi),value in zip(model.bounds,record) if hi is not None])
    out['independent_extracted_policy_upper_checks'].append({'name':name,'primal':report['value'],
        'independent_policy_worst_mean':float(upper),'absolute_gap':float(abs(upper-report['value'])),
        'record_inequality_violation':constraint_violation,'record_bounds_violation':bounds_violation})

for name in ['zero_contrast', 'one_query_exact']:
    assert out[name]['status'] == 'returned', (name, out[name])
    result = out[name]['result']
    assert abs(result['value']) < 2e-8
    assert abs(sum(result['batch_probabilities']) - 1) < 2e-8
    assert min(result['batch_probabilities']) >= -2e-8
assert all(r['absolute_error'] <= 2e-8 for r in out['constant_contrast_uncertain_total'])
assert all(r['exact_rational_check'] for r in out['K_family_exact_precision_witnesses'])
for row in out['independent_extracted_policy_upper_checks']:
    assert max(row['absolute_gap'], row['record_inequality_violation'], row['record_bounds_violation']) <= 2e-8
out['status'] = 'PASS'
out['comparison_tolerance'] = 2e-8
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2))
