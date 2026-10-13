"""Residual-corrected rational certificates for the 49 positive-error survivors.

Does not change frozen sensitivity results, protocols, or their solver.
Approximate LP multipliers only propose rigorous, exactly checked upper bounds.
"""
from collections import Counter
import csv
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
DEST = HERE / 'exact_certificates'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def formulation(c, first, seconds, delta):
    """Row order: each endpoint's +/- total, then each support width.

    Equalities per successor: u first=t, v first=t, u second=v second.
    Variables: successor-ordered (u[11],v[11]), then eta,t.
    """
    copies = 2 * len(seconds)
    size = 11 * copies + 2
    eta, answer = size - 2, size - 1
    f = [F(0)] * size
    f[eta] = F(-1)
    A, b, E, h = [], [], [], []
    for copy in range(copies):
        row = [F(0)] * size
        row[copy*11:copy*11+6] = [F(1)] * 6
        A.extend([row, [-x for x in row]])
        b.extend([F(1), F(-1)])
    def measurement(cut):
        return [F(int(i < cut)) for i in range(6)] + [F(int(i == cut-1)) for i in range(5)]
    for index, second in enumerate(seconds):
        u, v = 22*index, 22*index+11
        row = [F(0)] * size
        row[u:u+6] = [-x for x in c]
        row[v:v+6] = c
        row[eta] = F(1)
        A.append(row); b.append(F(0))
        for start in [u, v]:
            row = [F(0)] * size
            row[start:start+11] = measurement(first)
            row[answer] = F(-1)
            E.append(row); h.append(F(0))
        row = [F(0)] * size
        row[u:u+11] = measurement(second)
        row[v:v+11] = [-x for x in measurement(second)]
        E.append(row); h.append(F(0))
    bounds = ([(F(0), F(1))]*6 + [(-delta, delta)]*5)*copies
    bounds += [(F(0), F(1)), (-delta, F(1)+delta)]
    return f, A, b, E, h, bounds


def main():
    started = time.perf_counter()
    ledger_path = HERE/'case_ledger.csv'
    geometry_path = HERE.parent/'replay/geometry.json'
    with ledger_path.open(newline='', encoding='utf-8') as file:
        ledger = list(csv.DictReader(file))
    selected = [row for row in ledger if F(row['delta']) > 0 and row['adaptive_guarantee'] == 'True']
    assert Counter(F(row['delta']) for row in selected) == {F(1,1000):27, F(1,100):22}
    original = {row['id']: row for row in json.loads(geometry_path.read_text())['cases']}
    certificates = []
    for row in selected:
        raw = [F.from_float(float(x)) for x in original[row['id']]['c']]
        scale = max(raw)-min(raw)
        assert scale > 0
        c = [x/scale for x in raw]
        delta = F(row['delta'])
        first = int(row['best_first_query'])
        seconds = [int(x) for x in row['sparse_second_queries'].split(';')]
        assert len(seconds) in [1,2] and first not in seconds
        f,A,b,E,h,bounds = formulation(c,first,seconds,delta)
        solution = linprog(np.array(f,dtype=float), A_ub=np.array(A,dtype=float),
            b_ub=np.array(b,dtype=float), A_eq=np.array(E,dtype=float),
            b_eq=np.array(h,dtype=float), bounds=[tuple(map(float,z)) for z in bounds],
            method='highs', options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
        assert solution.success, solution.message
        assert all(math.isfinite(float(x)) for x in [*solution.ineqlin.marginals,*solution.eqlin.marginals])
        # Inequality sign is sufficient; stationarity need not be exact because
        # the bounded-box residual term below corrects it rigorously.
        lam = [min(F(0),F.from_float(float(x))) for x in solution.ineqlin.marginals]
        nu = [F.from_float(float(x)) for x in solution.eqlin.marginals]
        residual = [f[j]-sum(A[i][j]*lam[i] for i in range(len(A)))-
                    sum(E[i][j]*nu[i] for i in range(len(E))) for j in range(len(f))]
        row_term = sum(x*y for x,y in zip(lam,b)) + sum(x*y for x,y in zip(nu,h))
        correction = sum(min(r*lo,r*hi) for r,(lo,hi) in zip(residual,bounds))
        upper = -(row_term+correction)
        assert 0 <= upper <= F(1,2), (row['id'],delta,str(upper))
        certificates.append({'id':row['id'],'system_id':int(row['system_id']),
            'delta_exact':str(delta),'first':first,'seconds':seconds,
            'original_coefficients_exact':list(map(str,raw)), 'range_exact':str(scale),
            'normalized_coefficients_exact':list(map(str,c)),
            'variable_order':'successor-ordered u[6 increments,5 errors],v[6 increments,5 errors], then eta,t',
            'objective':list(map(str,f)), 'A_ub':[[str(x) for x in z] for z in A],
            'b_ub':list(map(str,b)), 'A_eq':[[str(x) for x in z] for z in E],
            'b_eq':list(map(str,h)), 'bounds':[[str(x) for x in z] for z in bounds],
            'inequality_multipliers':list(map(str,lam)), 'equality_multipliers':list(map(str,nu)),
            'stationarity_residual':list(map(str,residual)), 'row_term_exact':str(row_term),
            'residual_box_correction_exact':str(correction), 'certified_upper_exact':str(upper),
            'threshold_exact':'1/2','certified_margin_exact':str(F(1,2)-upper),
            'proposal_LP_value':float(-solution.fun),
            'original_float_support_value':float(row['support_value']),
            'scope':'Rigorous upper bound for specified first query and sparse successor support; not an exact optimum claim'})
    DEST.mkdir(exist_ok=True)
    bundle={'schema':'bounded-error-rational-dual-box-v1', 'inputs':{
        'case_ledger_sha256':sha(ledger_path),'geometry_sha256':sha(geometry_path),
        'protocol_sha256':sha(HERE/'PROTOCOL.txt')}, 'certificates':certificates}
    (DEST/'certificates.json').write_text(json.dumps(bundle,indent=2)+'\n')
    report={'status':'PASS','cases':49,'by_delta':{'1/1000':27,'1/100':22},
        'arithmetic':'Exact rational source coefficients, proposed binary64 multipliers, exact bounded-box residual correction',
        'guarantee':'Every saved exact upper bound is <= 1/2 for the same selected first query and sparse successor support',
        'minimum_certified_margin':min(float(F(r['certified_margin_exact'])) for r in certificates),
        'max_upper_minus_proposal_LP':max(float(F(r['certified_upper_exact']))-r['proposal_LP_value'] for r in certificates),
        'source_sha256':sha(Path(__file__)),'certificates_sha256':sha(DEST/'certificates.json'),
        'seconds':time.perf_counter()-started,
        'scope':'Exact feasibility-side guarantee certificates; unchanged selection/results; no physical calibration or assertion of exact optimal objective value'}
    (DEST/'generation_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__ == '__main__': main()
