"""Additional study-specific numerical and information-flow checks."""
import unittest
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from run_energy_rank_study import bounds, impute, daily_design, local_dst_affected


class StudyChecks(unittest.TestCase):
    def test_hidden_target_rearrangement_invariance(self):
        a = np.arange(1., 25.)
        b = a.copy(); b[1], b[4] = b[4], b[1]
        mask = np.zeros(24, bool); mask[[1, 4]] = True
        oa, ob = a.copy(), b.copy(); oa[mask] = ob[mask] = np.nan
        p = np.stack([a / 2, a / 3, a * .9, np.ones(24)])
        for bs in [6, 24]:
            ta, tb = a.reshape(-1, bs).sum(1), b.reshape(-1, bs).sum(1)
            for tau in [0., .01, .05]:
                np.testing.assert_allclose(bounds(p, oa, ta, bs, tau), bounds(p, ob, tb, bs, tau))
            for shape in [np.ones(24), np.arange(24.), a[::-1]]:
                np.testing.assert_allclose(impute(oa, ta, shape, bs), impute(ob, tb, shape, bs))

    def test_day_origin_features_are_available(self):
        idx = pd.date_range("2013-01-01", periods=24 * 12, freq="h")
        s = pd.Series(np.arange(len(idx), dtype=float), index=idx)
        days, x, y, eligible = daily_design(s)
        for d in np.flatnonzero(eligible):
            np.testing.assert_equal(x[d, :, 0], y[d - 1])
            np.testing.assert_equal(x[d, :, 1], y[d - 2])
            np.testing.assert_equal(x[d, :, 2], y[d - 7])
            np.testing.assert_equal(x[d, :, 3], np.repeat(y[d - 1].mean(), 24))

    def test_dst_target_and_lag_exclusion(self):
        days = pd.date_range("2014-03-29", "2014-04-07", freq="D")
        affected = set(days[local_dst_affected(days)].strftime("%Y-%m-%d"))
        self.assertEqual(affected, {"2014-03-30", "2014-03-31", "2014-04-01", "2014-04-06"})

    def test_random_cap_free_bounds_against_general_lp(self):
        rng = np.random.default_rng(737)
        for _ in range(100):
            truth = rng.uniform(0, 10, 24)
            pred = rng.uniform(0, 10, (4, 24))
            mask = np.zeros(24, bool); mask[rng.choice(24, 12, False)] = True
            obs = truth.copy(); obs[mask] = np.nan
            bs, tau = int(rng.choice([6, 24])), float(rng.choice([0., .01, .05]))
            totals = truth.reshape(-1, bs).sum(1)
            low, high, ilow, ihigh = bounds(pred, obs, totals, bs, tau)
            c = 2 * (pred[1] - pred[0]) / 24
            constant = np.mean(pred[0] ** 2 - pred[1] ** 2)
            A, rhs = [], []
            for j, start in enumerate(range(0, 24, bs)):
                row = np.zeros(24); row[start:start + bs] = 1
                A += [row, -row]; rhs += [totals[j] * (1 + tau), -totals[j] * (1 - tau)]
            lim = [(0, None) if mask[i] else (truth[i], truth[i]) for i in range(24)]
            l = linprog(c, A_ub=A, b_ub=rhs, bounds=lim, method="highs")
            u = linprog(-c, A_ub=A, b_ub=rhs, bounds=lim, method="highs")
            self.assertTrue(l.success and u.success)
            np.testing.assert_allclose([low[0], high[0]], [constant + l.fun, constant - u.fun], atol=1e-7)
            self.assertTrue(np.all(low >= ilow - 1e-7) and np.all(high <= ihigh + 1e-7))


if __name__ == "__main__":
    unittest.main(verbosity=2)
