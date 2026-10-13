"""Recompute cap sensitivity from bundled forecast coefficients, without raw meters.

Exact rational oracle/ledger and finite-game certificates are checked separately
from floating-point general-polytope LP checks in run_cap_sensitivity.py.
"""
from fractions import Fraction as F
from pathlib import Path
from collections import Counter
import csv
import argparse
import hashlib
import itertools
import json
import time

from counter_two_side import (two_side, full_uncapped, capped_batch_worst,
                             capped_at_profile, capped_first, capped_adaptive)

HERE = Path(__file__).resolve().parent
BATCHES = list(itertools.combinations(range(1, 6), 2))
CAPS = {'uncapped': F(1), 'E/2': F(1, 2), 'E/3': F(1, 3)}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row):
    return row['id'], row['scenario'], row['threshold']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'cap_bundled_check.json')
    args = parser.parse_args()
    started = time.perf_counter()
    names = ['CAP_SENSITIVITY_PROTOCOL.txt', 'cap_sensitivity_manifest.json',
             'cap_sensitivity_coefficients.json', 'cap_sensitivity_bundled_cases.csv',
             'cap_sensitivity_witnesses.json', 'cap_sensitivity_report.json']
    manifest = json.loads((HERE / names[1]).read_text())
    coefficients = json.loads((HERE / names[2]).read_text())
    assert digest(HERE / names[0]) == manifest['protocol_sha256']
    assert coefficients['source_protocol_sha256'] == manifest['protocol_sha256']
    cases = coefficients['cases']
    assert len(cases) == 290
    assert len({case['id'] for case in cases}) == 290
    assert {case['id'] for case in cases} == set(manifest['case_ids'])
    with (HERE / names[3]).open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    witnesses = json.loads((HERE / names[4]).read_text())
    report = json.loads((HERE / names[5]).read_text())
    ledger = {key(row): row for row in rows}
    proofs = {key(row): row for row in witnesses}
    assert len(rows) == len(ledger) == len(witnesses) == len(proofs) == 1740
    assert set(ledger) == set(proofs)
    groups = {}
    profile_checks = 0
    zero_flags = Counter()
    for case in cases:
        original = list(map(F, case['c_exact']))
        scale = max(original) - min(original)
        assert scale == F(case['range_exact']) > 0
        c = [v / scale for v in original]
        best, firsts = two_side(c)
        assert all(row['value'] == full_uncapped(c, row['first']) for row in firsts)
        for scenario, cap in CAPS.items():
            initial = capped_batch_worst(c, (), cap)
            (A, first), _ = capped_adaptive(c, cap)
            worsts = [capped_batch_worst(c, q, cap) for q in BATCHES]
            D = min(worsts)
            if cap == 1:
                assert A == best['value']
            for threshold, tau in [('fixed_old_absolute', F(1, 2)),
                                   ('half_new_initial', initial / 2)]:
                case_key = case['id'], scenario, threshold
                row = ledger[case_key]
                proof = proofs[case_key]
                expected = {'new_W0_over_old_exact': initial,
                            'tau_over_old_exact': tau,
                            'A_over_old_exact': A, 'D_over_old_exact': D}
                for column, value in expected.items():
                    assert F(row[column]) == value, (case_key, column)
                assert row['meter'] == case['meter'] and row['pair'] == case['pair']
                assert int(row['adaptive_first']) == first
                assert F(proof['tau_over_old_exact']) == tau
                category = ('batch_suffices' if D <= tau else
                            'feedback_required' if A <= tau else 'adaptive_not_guaranteed')
                assert row['class'] == category
                assert (row['zero_query_suffices'] == 'True') == (initial <= tau)
                groups.setdefault((scenario, threshold), Counter())[category] += 1
                zero_flags[scenario, threshold] += int(initial <= tau)
                profiles = [list(map(F, p)) for p in proof['profiles']]
                assert len(profiles) == int(row['finite_profiles'])
                for p in profiles:
                    assert len(p) == 6 and sum(p) == 1 and all(0 <= x <= cap for x in p)
                matrix = [[int(capped_at_profile(c, q, p, cap) <= tau)
                           for q in BATCHES] for p in profiles]
                profile_checks += len(profiles)
                adverse = list(map(F, proof['adverse_weights']))
                mixture = list(map(F, proof['finite_game_batch_weights']))
                assert len(adverse) == len(profiles) and len(mixture) == 10
                assert sum(adverse) == sum(mixture) == 1
                assert all(x >= 0 for x in adverse + mixture)
                upper = max(sum(adverse[i] * matrix[i][j] for i in range(len(profiles)))
                            for j in range(10))
                finite_lower = min(sum(mixture[j] * matrix[i][j] for j in range(10))
                                   for i in range(len(profiles)))
                assert finite_lower == upper == F(proof['finite_upper_exact'])
                assert upper == F(row['finite_upper_exact'])
                # Continuum lower bounds require an independent all-answer cover.
                support = [tuple(q) for q in proof['continuum_cover_support']]
                weights = list(map(F, proof['continuum_cover_weights']))
                lower = F(proof['continuum_lower_exact'])
                assert lower == F(row['continuum_lower_exact'])
                if lower:
                    assert len(support) in [1, 2] and len(weights) == len(support)
                    assert all(q in BATCHES for q in support)
                    assert all(w == F(1, len(support)) for w in weights)
                    assert lower == F(1, len(support))
                    if len(support) == 1:
                        assert capped_batch_worst(c, support[0], cap) <= tau
                    else:
                        common = set(support[0]) & set(support[1])
                        assert len(common) == 1
                        first_cover = next(iter(common))
                        seconds = [next(k for k in q if k != first_cover) for q in support]
                        cover_value, _ = capped_first(c, first_cover, cap, seconds)
                        assert cover_value <= tau
                else:
                    assert not support and not weights
                assert lower <= upper
                exact = str(upper) if lower == upper else 'not established'
                assert proof['continuum_success_exact'] == row['continuum_success_exact'] == exact
    for group in report['summaries']:
        group_key = group['scenario'], group['threshold']
        assert dict(groups[group_key]) == group['counts']
        assert zero_flags[group_key] == group['zero_query_suffices']
        subset = [r for r in rows if (r['scenario'], r['threshold']) == group_key]
        assert len(subset) == group['cases'] == 290
        assert sum(r['continuum_success_exact'] == '1/2' for r in subset) == group['exact_half']
        for meter, counts in group['by_meter'].items():
            assert dict(Counter(r['class'] for r in subset if r['meter'] == meter)) == counts
    constructed = list(map(F, [0, 0, 1, 1, 0, 1]))
    assert capped_batch_worst(constructed, (2, 4), F(1, 2)) == F(1, 2)
    assert capped_adaptive(constructed, F(1, 2))[0][0] == F(1, 2)
    output = {'status': 'PASS', 'scope': 'Bundled-coefficient rational reproduction; no raw-meter reconstruction or model refit',
              'cases': 290, 'case_scenario_threshold_rows': 1740,
              'feasible_profile_checks': profile_checks,
              'finite_game_primal_dual_checks': 1740,
              'continuum_lower_guarantees': 'Exact all-answer single/pair covers, independently checked',
              'arithmetic': 'Exact fractions of bundled frozen binary64 forecast coefficients',
              'physical_width_scope': 'Absolute meter totals are not reconstructed; positive E cancels in relative-cap analysis',
              'input_sha256': {name: digest(HERE / name) for name in names},
              'source_sha256': digest(__file__), 'seconds': time.perf_counter() - started}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2), flush=True)


if __name__ == '__main__':
    main()
