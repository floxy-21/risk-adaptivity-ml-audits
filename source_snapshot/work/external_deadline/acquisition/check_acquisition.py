"""Small independent analytic/enumerated fixtures; no external test outcomes."""
from pathlib import Path
import hashlib
import itertools
import json
import time
import numpy as np
from scipy.integrate import quad
from scipy.optimize import linprog
from acquisition import (select_batch, expected_absolute_squared_loss_contrast,
                         aggregate_conditioned_gaussian, POLICIES)
from compact_secondary import solve_compact_secondary

HERE = Path(__file__).resolve().parent


def finite_game(cs, es, budget):
    offsets = np.cumsum([0]+[len(c) for c in cs])
    groups = [np.arange(offsets[g], offsets[g+1]) for g in range(len(cs))]
    nq = min(budget, sum(len(c)-1 for c in cs))
    batches = [q for q in itertools.combinations(range(offsets[-1]), nq)
               if all(len(set(q).intersection(group)) < len(group) for group in groups)]
    matrix = np.zeros((offsets[-1], len(batches)))
    for j, q in enumerate(batches):
        for g, group in enumerate(groups):
            retained = [i for i in group if i not in q]
            contrast = np.asarray(cs[g])[np.array(retained)-offsets[g]]
            width = float(np.ptp(contrast))
            matrix[retained, j] = es[g]*width
    a = np.zeros((offsets[-1], len(batches)+len(cs)))
    a[:, :len(batches)] = matrix
    for g, group in enumerate(groups):
        a[group, len(batches)+g] = -1.
    equality = np.r_[np.ones(len(batches)), np.zeros(len(cs))][None, :]
    primary = np.r_[np.zeros(len(batches)), np.ones(len(cs))]
    options = {'primal_feasibility_tolerance': 1e-9, 'dual_feasibility_tolerance': 1e-9}
    first = linprog(primary, A_ub=a, b_ub=np.zeros(len(a)), A_eq=equality, b_eq=[1.], bounds=(0, None), method='highs-ipm', options=options)
    assert first.success
    secondary = np.r_[sum(matrix[group].mean(axis=0) for group in groups), np.zeros(len(cs))]
    second = linprog(secondary, A_ub=np.vstack([a, primary]), b_ub=np.r_[np.zeros(len(a)), first.fun], A_eq=equality, b_eq=[1.], bounds=(0, None), method='highs-ipm', options=options)
    assert second.success
    return float(first.fun), float(second.fun)


def main():
    started = time.perf_counter()
    gaussian = [(1., 3., 2., .4), (0., 2., 1.2, .7), (1., 1., 0., .1), (2., 5., -1., .3)]
    errors = []
    for a, b, mu, sd in gaussian:
        exact = float(expected_absolute_squared_loss_contrast(a, b, mu, sd))
        numeric = quad(lambda z: abs((a-z)**2-(b-z)**2)*np.exp(-.5*((z-mu)/sd)**2)/(sd*np.sqrt(2*np.pi)), mu-12*sd, mu+12*sd, points=[(a+b)/2] if mu-12*sd < (a+b)/2 < mu+12*sd else None, epsabs=1e-11)[0]
        errors.append(abs(exact-numeric))
    assert max(errors) < 1e-9
    np.testing.assert_allclose(expected_absolute_squared_loss_contrast([0, 1], [3, 4], [2, -1], 0), [3, 21])
    observed = np.array([1., np.nan, np.nan, np.nan, 2., np.nan])
    mu, sd = aggregate_conditioned_gaussian(np.arange(6.), 2., observed, [12.], 6)
    assert abs(mu.sum()-12.) < 1e-12
    np.testing.assert_allclose(sd[[1, 2, 3, 5]], np.sqrt(3.))
    np.testing.assert_array_equal(mu[[0, 4]], [1., 2.])
    fixtures = [([[0., 0., 2., 3.]], [1.]), ([[0., 2., 4., 12.]], [1.]),
                ([[0., 0., 0., 1., 1., 1.]], [3.]), ([[0., 1., 2.], [0., 2., 4.]], [1., .2]),
                ([[0., .1, .4, 1., 1.1, 3.]], [.02])]
    numerical = []
    for cs, es in fixtures:
        for budget in (1, 2):
            actual = solve_compact_secondary(cs, es, budget)
            primary, secondary = finite_game(cs, es, budget)
            delta = max(abs(actual['value']-primary), abs(actual['secondary_value']-secondary))
            assert delta < 1e-8, (cs, budget, actual, primary, secondary)
            numerical.append(delta)
    # Empty primary-optimal batches cannot stall the stopping workflow.
    result = select_batch('exact', np.zeros(6), np.array([0, 0, 0, 3, 3, 3.]), np.full(6, np.nan), [1.], 2)
    assert len(result['query_indices']) == 2 and result['diagnostics']['empty_optimum_progress_tie_break']
    # All policies share observed/aggregate input, do not mutate it, never
    # request an observed value and never exhaust a block's last deduction.
    a = np.array([0., .5, 1., 2., 2.5, 3.])
    b = a[::-1]
    original = observed.copy()
    for policy in POLICIES:
        for seed in range(12):
            result = select_batch(policy, a, b, observed, [12.], 2, rng=np.random.default_rng(seed), surrogate_mean=np.ones(6), surrogate_sd=.2)
            q = result['query_indices']
            assert 0 < len(q) <= 2 and len(set(q)) == len(q) and all(np.isnan(observed[i]) for i in q)
            np.testing.assert_array_equal(original, observed)
            repeated = select_batch(policy, a, b, observed, [12.], 2, rng=np.random.default_rng(seed), surrogate_mean=np.ones(6), surrogate_sd=.2)
            assert repeated['query_indices'] == q
    for policy in POLICIES:
        result = select_batch(policy, a, b, np.ones(6), [6.], 2, rng=np.random.default_rng(2), surrogate_mean=np.ones(6), surrogate_sd=.2)
        assert result['query_indices'] == []
    report = {'status': 'passed', 'scope': 'Analytic quadrature, independent finite-game secondary LP, eligibility and reproducible draws; no external outcome data.',
              'gaussian_quadrature_cases': len(gaussian), 'gaussian_max_absolute_error': max(errors),
              'finite_game_comparisons': len(numerical), 'finite_game_max_absolute_error': max(numerical),
              'policy_seed_cases': len(POLICIES)*12, 'all_observed_cases': len(POLICIES), 'empty_primary_optimum_progress_fixture': 'passed',
              'seconds': time.perf_counter()-started,
              'sha256': {name: hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('acquisition.py', 'compact_secondary.py', 'check_acquisition.py')}}
    (HERE/'fixture_check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
