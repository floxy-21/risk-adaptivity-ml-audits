"""Solver-free exact check of deterministic two-query impossibility witnesses.

Uses only the Python standard library and writes only the requested report.
It does not import the witness generator or any optimization implementation.
"""
import argparse
from collections import Counter
import csv
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
SENS = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'verification.json')
    args = parser.parse_args()
    start = time.perf_counter()
    source_ledger = SENS / 'case_ledger.csv'
    source_geometry = SENS.parent / 'replay/geometry.json'
    certificate_path = HERE / 'witnesses.json'
    bundle = json.loads(certificate_path.read_text(encoding='utf-8'))
    assert bundle['schema'] == 'fixed-error-deterministic-impossibility-v1'
    for name, path in [('case_ledger_sha256', source_ledger),
                       ('geometry_sha256', source_geometry),
                       ('diagnostic_protocol_sha256', HERE / 'PROTOCOL.txt')]:
        assert bundle['inputs'][name] == sha(path), ('changed input', name)
    with source_ledger.open(newline='', encoding='utf-8') as handle:
        old_rows = list(csv.DictReader(handle))
    expected = {(r['id'], F(r['delta'])) for r in old_rows
                if F(r['delta']) > 0 and r['adaptive_guarantee'] == 'False'}
    assert len(expected) == 9
    assert Counter(delta for _, delta in expected) == {F(1, 1000): 2, F(1, 100): 7}
    geometry = {r['id']: r for r in json.loads(source_geometry.read_text())['cases']}
    with (HERE / 'case_ledger.csv').open(newline='', encoding='utf-8') as handle:
        summary = list(csv.DictReader(handle))
    assert len(summary) == 9
    summary_by_key = {(r['id'], F(r['delta_exact'])): r for r in summary}
    assert set(summary_by_key) == expected
    observed = set()
    all_margins = []
    first_count = pair_count = 0
    by_delta = {}
    for witness in bundle['witnesses']:
        key = witness['id'], F(witness['delta_exact'])
        assert key in expected and key not in observed
        observed.add(key)
        case_id, delta = key
        raw = [F.from_float(float(v)) for v in geometry[case_id]['c']]
        span = max(raw) - min(raw)
        assert span > 0 and list(map(F, witness['original_coefficients_exact'])) == raw
        assert F(witness['range_exact']) == span
        c = [v / span for v in raw]
        assert list(map(F, witness['normalized_coefficients_exact'])) == c
        assert F(witness['threshold_exact']) == F(1, 2)
        firsts = witness['first_query_witnesses']
        assert len(firsts) == 5 and {v['first'] for v in firsts} == set(range(1, 6))
        first_lowers = []
        for first_witness in firsts:
            first_count += 1
            first = first_witness['first']
            answer = F(first_witness['first_answer_exact'])
            assert -delta <= answer <= 1 + delta
            pairs = first_witness['pairs']
            assert len(pairs) == 4
            assert {p['second'] for p in pairs} == set(range(1, 6)) - {first}
            widths = []
            for pair in pairs:
                pair_count += 1
                second = pair['second']
                u, v = [list(map(F, pair[name])) for name in ['u_increments', 'v_increments']]
                eu, ev = [list(map(F, pair[name])) for name in ['u_errors', 'v_errors']]
                for x, e in [(u, eu), (v, ev)]:
                    assert len(x) == 6 and len(e) == 5
                    assert all(0 <= z <= 1 for z in x) and sum(x) == 1
                    assert all(-delta <= z <= delta for z in e)
                    assert sum(x[:first]) + e[first - 1] == answer
                second_answer = F(pair['common_second_answer_exact'])
                assert sum(u[:second]) + eu[second - 1] == second_answer
                assert sum(v[:second]) + ev[second - 1] == second_answer
                width = sum(a * (x - y) for a, x, y in zip(c, u, v))
                assert width == F(pair['contrast_exact']) and width > F(1, 2)
                assert F(pair['margin_exact']) == width - F(1, 2)
                widths.append(width)
            lower = min(widths)
            assert lower == F(first_witness['certified_first_lower_exact'])
            first_lowers.append(lower)
        lower = min(first_lowers)
        margin = lower - F(1, 2)
        assert lower == F(witness['deterministic_optimum_lower_exact'])
        assert margin == F(witness['strict_impossibility_margin_exact']) and margin > 0
        row = summary_by_key[key]
        assert F(row['certified_lower_exact']) == lower and F(row['margin_exact']) == margin
        assert float(row['certified_lower']) == float(lower)
        assert float(row['margin']) == float(margin)
        all_margins.append(margin)
        by_delta.setdefault(str(delta), []).append(float(lower))
    assert observed == expected and first_count == 45 and pair_count == 180
    report = {
        'status': 'PASS', 'case_levels': len(observed),
        'unique_cases': len({key[0] for key in observed}),
        'legal_first_queries_checked': first_count, 'endpoint_pairs_checked': pair_count,
        'by_delta': {d: {'case_levels': len(values), 'minimum_certified_lower': min(values),
                         'maximum_certified_lower': max(values)} for d, values in by_delta.items()},
        'minimum_strict_margin_exact': str(min(all_margins)),
        'minimum_strict_margin': float(min(all_margins)),
        'verification': 'Exact Fraction feasibility and transcript checks; no LP or numerical tolerance',
        'scope': 'Deterministic adaptive policies with at most two distinct permitted counter queries; fixed hidden-error model only',
        'not_established': ['randomized adaptive impossibility', 'physical calibration of error bounds'],
        'certificate_sha256': sha(certificate_path), 'source_sha256': sha(Path(__file__)),
        'input_sha256': bundle['inputs'], 'seconds': time.perf_counter() - start}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
