"""Independent exact verification of fixed-counter fallback guarantees.

Standard library only. Reconstructs the information model without importing
the producer or reading its proposed constraint matrices as definitions.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'INDEPENDENT_CERTIFICATE_CHECKS.json')
    args = parser.parse_args()
    start = time.perf_counter()
    lock = json.loads((HERE / 'protocol_lock.json').read_text())
    for entry in lock['inputs'].values():
        assert sha(ROOT / entry['path'].replace('\\', '/')) == entry['sha256']
    geometry = {r['id']: r for r in json.loads((ROOT / 'replay/geometry.json').read_text())['cases']}
    expected = {r['id'] for r in json.loads((ROOT / 'replay/half_witnesses.json').read_text())}
    assert len(expected) == 29
    bundle_path = HERE / 'fixed_batch_certificates.json'
    bundle = json.loads(bundle_path.read_text())
    assert bundle['schema'] == 'fixed-batch-rational-dual-box-v1'
    certificates = bundle['certificates']
    assert len(certificates) == 29 and {r['id'] for r in certificates} == expected
    margins = []
    by_id = {}
    for cert in certificates:
        case_id = cert['id']
        assert case_id not in by_id
        delta = F(cert['delta_exact'])
        assert delta == F(1, 100) and F(cert['threshold_exact']) == F(1, 2)
        raw = [F.from_float(float(x)) for x in geometry[case_id]['c']]
        span = max(raw) - min(raw)
        assert span > 0
        c = [x / span for x in raw]
        assert list(map(F, cert['original_coefficients_exact'])) == raw
        assert list(map(F, cert['normalized_coefficients_exact'])) == c
        batch = cert['query_boundaries']
        assert len(batch) == len(set(batch)) == cert['queries']
        assert all(type(k) is int and 1 <= k <= 5 for k in batch)
        objective = [-v for v in c] + [F(0)] * 5 + c + [F(0)] * 5
        inequalities, rhs = [], []
        for base in [0, 11]:
            row = [F(int(base <= j < base + 6)) for j in range(22)]
            inequalities.extend([row, [-x for x in row]])
            rhs.extend([F(1), F(-1)])
        equalities = []
        for k in batch:
            row = [F(0)] * 22
            for j in range(k):
                row[j] = F(1)
                row[j + 11] = F(-1)
            row[k + 5] = F(1)
            row[k + 16] = F(-1)
            equalities.append(row)
        boxes = ([(F(0), F(1))] * 6 + [(-delta, delta)] * 5) * 2
        assert list(map(F, cert['objective'])) == objective
        assert [list(map(F, r)) for r in cert['A_ub']] == inequalities
        assert list(map(F, cert['b_ub'])) == rhs
        assert [list(map(F, r)) for r in cert['A_eq']] == equalities
        assert list(map(F, cert['b_eq'])) == [F(0)] * len(batch)
        assert [tuple(map(F, r)) for r in cert['bounds']] == boxes
        lam = list(map(F, cert['inequality_multipliers']))
        nu = list(map(F, cert['equality_multipliers']))
        assert len(lam) == 4 and all(v <= 0 for v in lam)
        assert len(nu) == len(batch)
        residual = [objective[j] - sum(a[j] * v for a, v in zip(inequalities, lam))
                    - sum(a[j] * v for a, v in zip(equalities, nu)) for j in range(22)]
        row_value = sum(v * b for v, b in zip(lam, rhs))
        correction = sum(min(r * lo, r * hi) for r, (lo, hi) in zip(residual, boxes))
        upper = -(row_value + correction)
        margin = F(1, 2) - upper
        assert list(map(F, cert['stationarity_residual'])) == residual
        assert F(cert['row_term_exact']) == row_value
        assert F(cert['residual_box_correction_exact']) == correction
        assert F(cert['certified_upper_exact']) == upper
        assert F(cert['certified_margin_exact']) == margin and margin >= 0
        assert cert['passes_exactly'] is True
        margins.append(margin)
        by_id[case_id] = cert
    old_path = ROOT / 'stored_error_sensitivity/exact_certificates/certificates.json'
    old = {r['id']: r for r in json.loads(old_path.read_text())['certificates']
           if F(r['delta_exact']) == F(1, 100)}
    assert len(old) == 22
    prescriptions = json.loads((HERE / 'prescriptions.json').read_text())
    assert len(prescriptions) == 29 and {r['id'] for r in prescriptions} == expected
    policy_counts = Counter()
    for policy in prescriptions:
        case_id = policy['id']
        assert policy['selection_uses_hidden_answers'] is False
        assert F(policy['delta_exact']) == F(1, 100)
        assert F(policy['threshold_over_W0_exact']) == F(1, 2)
        assert list(map(F, policy['original_coefficients_exact'])) == list(map(F, by_id[case_id]['original_coefficients_exact']))
        if case_id in old:
            assert policy['policy_type'] == 'existing_two_query_adaptive_support'
            assert policy['hard_query_budget'] == 2
            assert policy['first_query'] == old[case_id]['first']
            assert policy['second_query_candidates'] == old[case_id]['seconds']
            assert F(policy['support_certified_upper_exact']) == F(old[case_id]['certified_upper_exact']) <= F(1, 2)
        else:
            assert policy['policy_type'] == 'fixed_batch_fallback'
            assert policy['hard_query_budget'] == by_id[case_id]['queries']
            assert policy['query_boundaries'] == by_id[case_id]['query_boundaries']
            assert F(policy['batch_certified_upper_exact']) == F(by_id[case_id]['certified_upper_exact'])
        policy_counts[str(policy['hard_query_budget'])] += 1
    report = {
        'status': 'PASS', 'fixed_batch_certificates_exactly_checked': len(certificates),
        'existing_positive_certificates_linked_not_rerun': len(old),
        'prescriptions_checked': len(prescriptions), 'hybrid_budget_counts': dict(policy_counts),
        'minimum_fixed_margin_exact': str(min(margins)),
        'minimum_fixed_margin': float(min(margins)),
        'maximum_fixed_upper': float(F(1, 2) - min(margins)),
        'verification': 'Independent exact row reconstruction and weak-duality residual-box check; no LP solver',
        'scope': 'Certified fixed-batch upper bounds plus correspondence to previously verified two-query support policies; no exact-optimum or physical-device claim',
        'certificate_sha256': sha(bundle_path), 'existing_positive_certificate_sha256': sha(old_path),
        'source_sha256': sha(Path(__file__)), 'seconds': time.perf_counter() - start}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
