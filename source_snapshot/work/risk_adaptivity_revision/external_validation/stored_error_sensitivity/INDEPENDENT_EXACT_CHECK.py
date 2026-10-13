"""Read-only standard-library audit of support certificates and old upper bounds.

This checker is separately written from the certificate generator. It rebuilds
all LP rows from query semantics, then evaluates a rational weak-duality bound.
"""
import csv
from fractions import Fraction as F
import hashlib
import itertools
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent


def main():
    start = time.perf_counter()
    path = HERE/'exact_certificates/certificates.json'
    package = json.loads(path.read_text())
    geometry = {r['id']: r for r in json.loads((HERE.parent/'replay/geometry.json').read_text())['cases']}
    old = {r['id']: r for r in json.loads((HERE.parent/'replay/half_witnesses.json').read_text())}
    rows = list(csv.DictReader((HERE/'case_ledger.csv').open()))
    expected = {(r['id'], F(r['delta'])) for r in rows
                if F(r['delta']) > 0 and r['adaptive_guarantee'] == 'True'}
    seen = set()
    margins = []
    for cert in package['certificates']:
        case_id = cert['id']; delta = F(cert['delta_exact'])
        assert (case_id, delta) not in seen
        seen.add((case_id, delta))
        original = list(map(F.from_float, geometry[case_id]['c']))
        assert original == list(map(F, cert['original_coefficients_exact']))
        ran = max(original)-min(original)
        assert ran == F(cert['range_exact']) > 0
        c = [x/ran for x in original]
        assert c == list(map(F, cert['normalized_coefficients_exact']))
        assert max(c)-min(c) == 1
        first = cert['first']-1
        seconds = [x-1 for x in cert['seconds']]
        assert len(seconds) in (1, 2) and len(set(seconds)) == len(seconds)
        assert all(0 <= x < 5 and x != first for x in seconds)
        assert delta in (F(1, 1000), F(1, 100))
        n = 22*len(seconds)+2
        eta, answer = n-2, n-1
        objective = [F(0)]*n; objective[eta] = -1
        A, b, E, h = [], [], [], []
        bounds = []
        # Total equalities are stored as opposing inequality rows.
        for copy in range(2*len(seconds)):
            offset = 11*copy
            row = [F(0)]*n; row[offset:offset+6] = [F(1)]*6
            A.extend([row, [-x for x in row]]); b.extend([F(1), F(-1)])
            bounds += [(F(0), F(1))]*6+[(-delta, delta)]*5
        for index, second in enumerate(seconds):
            u, v = 22*index, 22*index+11
            row = [F(0)]*n
            row[u:u+6] = [-x for x in c]
            row[v:v+6] = c[:]
            row[eta] = 1
            A.append(row); b.append(F(0))
            for offset in (u, v):
                row = [F(0)]*n
                row[offset:offset+first+1] = [F(1)]*(first+1)
                row[offset+6+first] = 1
                row[answer] = -1
                E.append(row); h.append(F(0))
            row = [F(0)]*n
            row[u:u+second+1] = [F(1)]*(second+1)
            row[v:v+second+1] = [F(-1)]*(second+1)
            row[u+6+second] = 1; row[v+6+second] = -1
            E.append(row); h.append(F(0))
        bounds += [(F(0), F(1)), (-delta, 1+delta)]
        assert objective == list(map(F, cert['objective']))
        assert A == [list(map(F, r)) for r in cert['A_ub']]
        assert b == list(map(F, cert['b_ub']))
        assert E == [list(map(F, r)) for r in cert['A_eq']]
        assert h == list(map(F, cert['b_eq']))
        assert bounds == [tuple(map(F, r)) for r in cert['bounds']]
        lam = list(map(F, cert['inequality_multipliers']))
        nu = list(map(F, cert['equality_multipliers']))
        assert len(lam) == len(A) and len(nu) == len(E)
        assert all(x <= 0 for x in lam)
        residual = [objective[j]-sum(lam[i]*A[i][j] for i in range(len(A)))
                    -sum(nu[i]*E[i][j] for i in range(len(E))) for j in range(n)]
        assert residual == list(map(F, cert['stationarity_residual']))
        row_term = sum(x*y for x,y in zip(lam, b))+sum(x*y for x,y in zip(nu, h))
        correction = sum(min(r*lo, r*hi) for r,(lo,hi) in zip(residual,bounds))
        upper = -row_term-correction
        assert row_term == F(cert['row_term_exact'])
        assert correction == F(cert['residual_box_correction_exact'])
        assert upper == F(cert['certified_upper_exact'])
        margin = F(1,2)-upper
        assert margin == F(cert['certified_margin_exact']) > 0
        margins.append(margin)
        # Recheck the original rational finite-profile upper bound. The new
        # observation fibers contain these zero-error fibers, so this exact
        # success upper bound transfers under the declared expanded model.
        weights = list(map(F, old[case_id]['adverse_weights']))
        assert len(weights) == 6 and min(weights) >= 0 and sum(weights) == 1
        scores = []
        for q in itertools.combinations(range(1,6), 2):
            boundaries = (0,)+q+(6,)
            total_success = F(0)
            for hour in range(6):
                for left,right in zip(boundaries[:-1],boundaries[1:]):
                    if left <= hour < right:
                        width = max(c[left:right])-min(c[left:right])
                        total_success += weights[hour]*(width <= F(1,2))
                        break
            scores.append(total_success)
        assert max(scores) <= F(1,2)
    assert seen == expected and len(seen) == 49
    report = {'status': 'PASS', 'certificate_count': len(seen),
              'rational_matrix_checks': len(seen), 'inherited_rational_upper_checks': len(seen),
              'smallest_rigorous_margin_exact': str(min(margins)),
              'smallest_rigorous_margin_float': float(min(margins)),
              'certificates_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'seconds': time.perf_counter()-start,
              'claim': 'Rigorous support-defined adaptive precision guarantee; no exact optimum or physical calibration claim.'}
    (HERE/'INDEPENDENT_EXACT_CHECKS.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
