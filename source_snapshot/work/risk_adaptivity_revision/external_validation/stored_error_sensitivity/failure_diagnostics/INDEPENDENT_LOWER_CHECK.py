"""Independent solver-free audit of deterministic two-query lower witnesses."""
from collections import Counter
import csv
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
SENS = HERE.parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    start = time.perf_counter()
    path = HERE/'witnesses.json'
    package = json.loads(path.read_text())
    assert package['schema'] == 'fixed-error-deterministic-impossibility-v1'
    geometry_path = SENS.parent/'replay/geometry.json'
    original_ledger = SENS/'case_ledger.csv'
    for field, p in [('case_ledger_sha256', original_ledger),
                     ('geometry_sha256', geometry_path),
                     ('diagnostic_protocol_sha256', HERE/'PROTOCOL.txt')]:
        assert package['inputs'][field] == sha(p)
    geometry = {r['id']: r for r in json.loads(geometry_path.read_text())['cases']}
    rows = list(csv.DictReader(original_ledger.open()))
    expected = {(r['id'], F(r['delta'])) for r in rows
                if F(r['delta']) > 0 and r['adaptive_guarantee'] == 'False'}
    seen = set(); margins = []; first_count = 0; pair_count = 0
    for case in package['witnesses']:
        key = (case['id'], F(case['delta_exact']))
        assert key in expected and key not in seen
        seen.add(key)
        delta = key[1]
        raw = list(map(F.from_float, geometry[key[0]]['c']))
        assert raw == list(map(F, case['original_coefficients_exact']))
        span = max(raw)-min(raw)
        assert span > 0 and span == F(case['range_exact'])
        c = [x/span for x in raw]
        assert c == list(map(F, case['normalized_coefficients_exact']))
        assert F(case['threshold_exact']) == F(1,2)
        firsts = case['first_query_witnesses']
        assert len(firsts) == 5 and {r['first'] for r in firsts} == set(range(1,6))
        first_bounds = []
        for row in firsts:
            first = row['first']; t = F(row['first_answer_exact'])
            assert -delta <= t <= 1+delta
            pairs = row['pairs']
            assert len(pairs) == 4 and {r['second'] for r in pairs} == set(range(1,6))-{first}
            bounds = []
            for pair in pairs:
                second = pair['second']
                u, v = [list(map(F, pair[k])) for k in ('u_increments','v_increments')]
                eu, ev = [list(map(F, pair[k])) for k in ('u_errors','v_errors')]
                assert len(u) == len(v) == 6 and len(eu) == len(ev) == 5
                assert min(u+v) >= 0 and sum(u) == sum(v) == 1
                assert all(abs(e) <= delta for e in eu+ev)
                assert sum(u[:first])+eu[first-1] == sum(v[:first])+ev[first-1] == t
                answer = sum(u[:second])+eu[second-1]
                assert answer == sum(v[:second])+ev[second-1]
                assert answer == F(pair['common_second_answer_exact'])
                width = sum(ci*(ui-vi) for ci,ui,vi in zip(c,u,v))
                assert width == F(pair['contrast_exact']) > F(1,2)
                assert width-F(1,2) == F(pair['margin_exact'])
                bounds.append(width)
                pair_count += 1
            lower = min(bounds)
            assert lower == F(row['certified_first_lower_exact'])
            first_bounds.append(lower)
            first_count += 1
        lower = min(first_bounds)
        assert lower == F(case['deterministic_optimum_lower_exact'])
        margin = lower-F(1,2)
        assert margin == F(case['strict_impossibility_margin_exact']) > 0
        margins.append(margin)
    assert seen == expected and len(seen) == 9
    report = {'status': 'PASS', 'case_levels': len(seen),
              'unique_cases': len({case_id for case_id,_ in seen}),
              'counts_by_delta': {str(k):v for k,v in Counter(d for _,d in seen).items()},
              'first_query_witnesses': first_count, 'endpoint_pairs': pair_count,
              'minimum_exact_impossibility_margin': str(min(margins)),
              'minimum_margin_float': float(min(margins)), 'witnesses_sha256': sha(path),
              'seconds': time.perf_counter()-start,
              'scope': 'Exact impossibility for deterministic policies with at most two declared queries; no randomized-adaptive or physical-error claim.'}
    (HERE/'INDEPENDENT_LOWER_CHECKS.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
