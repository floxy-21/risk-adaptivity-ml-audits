"""Independent full-domain affine branch certificate and runtime check.

Exact standard-library arithmetic. The producer is never imported. Each
conditional width LP is reconstructed from the stored-error query semantics.
"""
import argparse
from fractions import Fraction as F
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'INDEPENDENT_BRANCH_CHECKS.json')
    args = parser.parse_args()
    started = time.perf_counter()
    geometry_path = ROOT / 'replay/geometry.json'
    geometry = {r['id']: r for r in json.loads(geometry_path.read_text())['cases']}
    prior_path = ROOT / 'stored_error_sensitivity/exact_certificates/certificates.json'
    prior = {r['id']: r for r in json.loads(prior_path.read_text())['certificates']
             if F(r['delta_exact']) == F(1, 100)}
    bundle_path = HERE / 'branch_certificates.json'
    bundle = json.loads(bundle_path.read_text())
    assert bundle['schema'] == 'affine-conditional-dual-box-v1'
    records = bundle['certificates']
    assert len(records) == 22 and {r['id'] for r in records} == set(prior)
    spec = importlib.util.spec_from_file_location('checked_executable_policy', HERE / 'policy.py')
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    margins = []
    line_count = runtime_tests = 0
    ledger = []
    for record in records:
        case_id = record['id']
        raw = [F.from_float(float(x)) for x in geometry[case_id]['c']]
        span = max(raw) - min(raw)
        assert span > 0
        c = [x / span for x in raw]
        assert list(map(F, record['normalized_coefficients_exact'])) == c
        delta = F(record['delta_exact'])
        assert delta == F(1, 100)
        first = record['first_query']
        assert first in range(1, 6) and first == prior[case_id]['first']
        domain = -delta, 1 + delta
        assert tuple(map(F, record['first_answer_domain_exact'])) == domain
        objective = [-x for x in c] + [F(0)] * 5 + c + [F(0)] * 5
        boxes = ([(F(0), F(1))] * 6 + [(-delta, delta)] * 5) * 2
        rows, rhs = [], []
        for base in [0, 11]:
            row = [F(int(base <= j < base + 6)) for j in range(22)]
            rows.extend([row, [-x for x in row]])
            rhs.extend([F(1), F(-1)])
        affine = []
        successors = set()
        for line in record['lines']:
            line_count += 1
            second = line['second_query']
            assert second in range(1, 6) and second != first and second not in successors
            assert second in prior[case_id]['seconds']
            successors.add(second)
            # First endpoints are both observed at t; the second readout is
            # equal between the endpoints, but its common value is free.
            equality = []
            for base in [0, 11]:
                row = [F(0)] * 22
                for j in range(first): row[base + j] = F(1)
                row[base + 5 + first] = F(1)
                equality.append(row)
            row = [F(0)] * 22
            for j in range(second): row[j], row[j + 11] = F(1), F(-1)
            row[5 + second], row[16 + second] = F(1), F(-1)
            equality.append(row)
            lam, nu = [list(map(F, line[k])) for k in ['inequality_multipliers', 'equality_multipliers']]
            assert len(lam) == 4 and all(x <= 0 for x in lam) and len(nu) == 3
            residual = [objective[j] - sum(a[j] * v for a, v in zip(rows, lam))
                        - sum(a[j] * v for a, v in zip(equality, nu)) for j in range(22)]
            correction = sum(min(r * lo, r * hi) for r, (lo, hi) in zip(residual, boxes))
            intercept = -(sum(v * b for v, b in zip(lam, rhs)) + correction)
            slope = -(nu[0] + nu[1])
            assert list(map(F, line['stationarity_residual'])) == residual
            assert F(line['box_correction_exact']) == correction
            assert F(line['intercept_exact']) == intercept and F(line['slope_exact']) == slope
            assert F(line['source_width_weight_exact']) > 0
            affine.append((intercept, slope, second))
        assert affine and len(affine) <= 2
        # A finite lower envelope of affine lines is linear between pairwise
        # intersections. Its maximum on the closed answer interval is thus
        # attained at an endpoint or one of these intersections.
        points = set(domain)
        for (a, b, _), (d, e, _) in itertools.combinations(affine, 2):
            if b != e:
                t = (d - a) / (b - e)
                if domain[0] <= t <= domain[1]: points.add(t)
        points = sorted(points)
        values = [(t, min(a + b * t for a, b, _ in affine)) for t in points]
        assert [(F(t), F(v)) for t, v in record['breakpoint_checks']] == values
        upper = max(v for _, v in values)
        margin = F(1, 2) - upper
        assert margin >= 0
        assert F(record['certified_worst_branch_bound_exact']) == upper
        assert F(record['certified_margin_exact']) == margin
        margins.append(margin)
        # Exercise the actual callback policy at every envelope breakpoint
        # and an interior point of each resulting interval. This is code
        # checking, while the affine argument above covers the continuum.
        test_points = sorted(set(points + [(a + b) / 2 for a, b in zip(points, points[1:])]))
        for t in test_points:
            mass = max(F(0), min(F(1), t))
            x = [mass] + [F(0)] * 4 + [1 - mass]
            errors = [F(0)] * 5
            errors[first - 1] = t - mass
            assert abs(errors[first - 1]) <= delta
            calls = []
            def reader(k):
                calls.append(k)
                return sum(x[:k]) + errors[k - 1]
            result = policy.execute(case_id, reader)
            expected_upper, expected_second = min((a + b * t, j) for a, b, j in affine)
            assert calls == [first, expected_second]
            assert result['hard_query_budget'] == 2
            assert F(result['guaranteed_width_over_original_W0_upper_exact']) == expected_upper <= F(1, 2)
            runtime_tests += 1
        ledger.append({'id': case_id, 'first': first, 'successors': sorted(successors),
                       'envelope_upper_exact': str(upper), 'margin_exact': str(margin),
                       'breakpoints': len(points), 'constructed_runtime_checks': len(test_points)})
    # Direct checks of the feasibility guard: monotone true prefixes need not
    # have monotone noisy readings, but must admit a monotone selection in
    # their exact error bands.
    assert policy.transcript_is_feasible({1: F(51, 100), 2: F(49, 100)})
    assert not policy.transcript_is_feasible({1: F(52, 100), 2: F(48, 100)})
    assert not policy.transcript_is_feasible({1: F(-11, 1000)})
    assert not policy.transcript_is_feasible({5: F(1011, 1000)})
    report = {
        'status': 'PASS', 'whole_answer_domains_certified': len(records),
        'conditional_affine_dual_lines_checked': line_count,
        'constructed_policy_runtime_checks': runtime_tests,
        'minimum_margin_exact': str(min(margins)), 'minimum_margin': float(min(margins)),
        'verification': 'Exact weak-duality row reconstruction and complete affine-envelope proof on [-.01,1.01]; no LP calls',
        'runtime_scope': 'Actual rational-line callback implementation checked at all envelope breakpoints and intervening midpoint cells; no noisy recorded-data replay',
        'original_primary_result': '22/29 at two queries remains unchanged; other seven use separately certified fixed three-query batches',
        'cases': ledger, 'input_sha256': {'geometry': sha(geometry_path), 'prior_certificates': sha(prior_path),
                                         'branch_certificates': sha(bundle_path), 'policy': sha(HERE / 'policy.py')},
        'source_sha256': sha(Path(__file__)), 'seconds': time.perf_counter() - started}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}, indent=2))


if __name__ == '__main__':
    main()
