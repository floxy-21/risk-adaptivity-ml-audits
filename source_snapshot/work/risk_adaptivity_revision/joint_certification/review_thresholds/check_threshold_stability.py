"""Independent exact checker for the frozen threshold certificates.

Uses only Python's standard library. Does not import the producer, use an
optimization solver, or inspect withheld fine-resolution target answers.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ROOT = BASE.parents[1]
TARGETS = [F(s) for s in ('.45', '.475', '.49', '.5', '.51', '.525', '.55')]


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def widths(C, q, x):
    """Directly sum segment energy times coefficient range, for every contrast."""
    cuts = [0] + list(q) + [len(x)]
    return [sum(sum(x[l:u]) * (max(c[l:u])-min(c[l:u]))
                for l, u in zip(cuts, cuts[1:])) for c in C]


def primal_two_forms(a, b):
    """Exact maximum of min(a.x,b.x) over a simplex, by primal edge vertices.

    The hypograph has two affine roof faces. Its maximizing vertex projects
    either to a simplex vertex or to an edge where the roof faces intersect.
    This avoids the producer's dual multiplier line-intersection calculation.
    """
    best = max(min(x, y) for x, y in zip(a, b))
    for i, j in combinations(range(len(a)), 2):
        di, dj = a[i]-b[i], a[j]-b[j]
        if di == dj:
            continue
        lam = -dj/(di-dj)
        if 0 <= lam <= 1:
            best = max(best, min(lam*a[i]+(1-lam)*a[j],
                                 lam*b[i]+(1-lam)*b[j]))
    return best


def quantiles(v):
    v = sorted(v)
    n = len(v)
    return {'n': n, 'min_exact': str(v[0]),
            'q25_exact': str(v[max(0, (n+3)//4-1)]),
            'median_exact': str(v[max(0, (n+1)//2-1)]),
            'q75_exact': str(v[max(0, (3*n+3)//4-1)]),
            'max_exact': str(v[-1])}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results', type=Path, default=HERE/'replayed')
    ap.add_argument('--chain-dir', type=Path, help='Additionally bind the checked certificates to a full source-chain run')
    args = ap.parse_args()
    start = time.perf_counter()
    d = args.results.resolve()
    cdir = args.chain_dir.resolve() if args.chain_dir else None
    inp, out, report = (read(d/f) for f in ('inputs.json', 'intervals.json', 'report.json'))
    assert report['status'] == 'PASS'
    assert sha(d/'inputs.json') == out['inputs_sha256'] == report['inputs_sha256']
    assert sha(d/'intervals.json') == report['intervals_sha256']
    chain_paths = [('precision/plans.json', 'precision_plans_sha256'),
                   ('precision/adaptive_half_check.json', 'adaptive_check_sha256'),
                   ('shared/empirical_plans.json', 'shared_plans_sha256'),
                   ('source_chain.json', 'source_chain_sha256'),
                   ('chain_execution.json', 'chain_execution_sha256')]
    raw = {}
    if cdir:
        for rel, field in chain_paths:
            assert sha(cdir/rel) == inp[field], (rel, field)
        pp, aa = read(cdir/'precision/plans.json'), read(cdir/'precision/adaptive_half_check.json')
        assert pp['status'] == aa['status'] == 'PASS'
        pp_by = {r['id']: r for r in pp['plans']}
        aa_by = {r['id']: r for r in aa['cases']}
        for relative, digest in inp['source_hashes'].items():
            p = (BASE/relative).resolve()
            assert sha(p) == digest
            for row in read(p)['cases']:
                raw[row['id']] = row['c']
    batches = list(combinations(range(1, 6), 2))
    assert inp['query_batches'] == [list(q) for q in batches]
    if cdir:
        assert inp['profiles'] == pp['profiles']
    profiles = [list(map(F, x)) for x in inp['profiles']]
    assert all(len(x) == 6 and min(x) >= 0 and sum(x) == 1 for x in profiles)
    assert len(inp['cases']) == len(out['cases']) == report['case_count'] == 222
    if cdir:
        assert {r['id'] for r in inp['cases']} == set(aa_by)
    ob = {r['id']: r for r in out['cases']}
    checks = Counter()
    for row in inp['cases']:
        ident = row['id']; result = ob[ident]
        if cdir:
            pp_row = pp_by[ident]
            assert row['raw_coefficients_binary64'] == [raw[k] for k in row['pair_case_ids']]
            assert row['raw_coefficients_binary64'] == pp_row['original_c_binary64']
            assert row['adaptive'] == aa_by[ident]
            for a, b in [('selected_indices', 'selected_indices'), ('batch_weights', 'batch_weights'),
                         ('saved_cover', 'pair_cover_multipliers'),
                         ('adverse_profile_weights', 'adverse_profile_weights')]:
                assert row[a] == pp_row[b]
        C = []
        for c in row['raw_coefficients_binary64']:
            c = [F(x) for x in c]; lo, hi = min(c), max(c)
            assert hi > lo
            C.append([(x-lo)/(hi-lo) for x in c])
        assert [[str(x) for x in c] for c in C] == row['normalized_coefficients_exact']
        # Evaluate all pure energy profiles directly, independently reconstructing
        # the coefficient vectors used in each fixed-batch uncertainty width.
        units = [[F(i == j) for i in range(6)] for j in range(6)]
        V = [[list(v) for v in zip(*(widths(C, q, x) for x in units))] for q in batches]
        checks['fixed_batch_pure_profiles'] += len(batches)*6
        adaptive = row['adaptive']; first = adaptive['first_query']; cursor = F(0); A = F(0)
        for branch in adaptive['branches']:
            lo, hi = F(branch['lo']), F(branch['hi'])
            assert lo == cursor < hi <= 1
            q = tuple(sorted((first, branch['second'])))
            assert q in batches
            bound = F(0)
            for t, prefix, suffix in product((lo, hi), range(first), range(first, 6)):
                x = [F(0)]*6; x[prefix] = t; x[suffix] = 1-t
                bound = max(bound, *widths(C, q, x))
                checks['adaptive_conditional_extreme_profiles'] += 1
            assert bound == F(branch['upper_exact'])
            A = max(A, bound); cursor = hi
            checks['adaptive_branches'] += 1
        assert cursor == 1 and A == F(result['adaptive_upper']) == F(adaptive['upper_exact'])
        i, j = row['selected_indices']
        assert i != j
        assert list(map(F, row['batch_weights'])) == [F(1, 2) if k in (i, j) else F(0) for k in range(10)]
        old_covers = {(z['first_contrast'], z['second_contrast']): z for z in row['saved_cover']}
        new_covers = {(z['r'], z['s']): z for z in result['cover_witnesses']}
        assert set(new_covers) == set(old_covers) == set(product(range(6), repeat=2))
        P, Pold = F(0), F(0)
        for (r, s), cv in new_covers.items():
            a, b = V[i][r], V[j][s]
            upper, lam = F(cv['upper']), F(cv['lambda'])
            assert 0 <= lam <= 1
            assert max(lam*x+(1-lam)*y for x, y in zip(a, b)) == upper
            assert primal_two_forms(a, b) == upper
            old_lam = F(old_covers[(r, s)]['lambda'])
            old = max(old_lam*x+(1-old_lam)*y for x, y in zip(a, b))
            assert old == F(cv['saved_upper']) and upper <= old <= F(1, 2)
            P, Pold = max(P, upper), max(Pold, old)
            checks['primal_dual_cover_equalities'] += 1
        assert P == F(result['pair_cover_lower']) and Pold == F(result['saved_pair_cover_lower'])
        mu = list(map(F, row['adverse_profile_weights']))
        assert len(mu) == len(profiles) and min(mu) >= 0 and sum(mu) == 1
        values = [[max(widths(C, q, x)) for q in batches] for x in profiles]
        assert [[str(v) for v in x] for x in values] == result['adverse_profile_widths']
        U = F(100)
        for n in range(10):
            events = Counter()
            for x, w in zip(values, mu):
                events[x[n]] += w
            cumulative = F(0)
            for threshold, mass in sorted(events.items()):
                previous = cumulative; cumulative += mass
                if cumulative > F(1, 2):
                    cv = result['adverse_crossovers'][n]
                    assert cv['batch_index'] == n
                    assert threshold == F(cv['threshold'])
                    assert cumulative == F(cv['success_at']) and previous == F(cv['success_strictly_below'])
                    U = min(U, threshold)
                    break
            checks['adversary_batch_inequalities'] += 1
        L, Lold = max(A, P), max(A, Pold)
        assert L == F(result['lower_closed']) and Lold == F(result['saved_lower_closed'])
        assert U == F(result['upper_open']) and L <= Lold <= F(1, 2) < U
        assert result['certified_targets'] == [str(t) for t in TARGETS if L <= t < U]
        checks['matched_half_cases'] += 1
    assert Counter(r['cohort'] for r in out['cases']) == {'original': 165, 'external': 57}
    for group, summ in report['summary'].items():
        rows = [r for r in out['cases'] if group == 'all' or group == r['cohort']
                or group == r['cohort']+'/'+r['meter']]
        assert summ['cases'] == len(rows)
        for tau in TARGETS:
            n = sum(F(r['lower_closed']) <= tau < F(r['upper_open']) for r in rows)
            assert summ['certified_at_threshold'][str(tau)] == n
            assert summ['inconclusive_at_threshold'][str(tau)] == len(rows)-n
        for field, col in [('tightened_multiplier_lower', 'lower_closed'),
                           ('saved_multiplier_lower', 'saved_lower_closed'),
                           ('adverse_upper_open', 'upper_open'), ('adaptive_bound', 'adaptive_upper')]:
            for k, value in quantiles([F(r[col]) for r in rows]).items():
                assert summ[field][k] == value
        margins = [[F(1, 2)-F(r['lower_closed']), F(r['upper_open'])-F(1, 2)] for r in rows]
        for field, vals in [('lower_margin_from_half', [z[0] for z in margins]),
                            ('upper_margin_from_half', [z[1] for z in margins]),
                            ('symmetric_margin_about_half', [min(z) for z in margins])]:
            for k, value in quantiles(vals).items():
                assert summ[field][k] == value
        for epsilon in (F(1, 100), F(1, 40), F(1, 20)):
            assert summ['entire_closed_symmetric_band'][str(epsilon)] == sum(
                low >= epsilon and high > epsilon for low, high in margins)
    result = {'status': 'PASS', 'checks': dict(checks),
              'scope': 'Exact threshold certificates for all 222 saved matched-half cases; independently reconstructed widths and primal/dual cover equality; no solver or producer import.',
              'execution_mode': 'full_source_chain' if cdir else 'bundled_certificate_replay',
              'source_records_verified_in_this_run': bool(cdir),
              'intervals_sha256': sha(d/'intervals.json'), 'report_sha256': sha(d/'report.json'),
              'inputs_sha256': sha(d/'inputs.json'), 'checker_sha256': sha(__file__),
              'elapsed_seconds': time.perf_counter()-start,
              'numerical_tolerance': 'None: exact Fraction arithmetic on saved binary64 rational inputs.'}
    (d/'independent_check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
