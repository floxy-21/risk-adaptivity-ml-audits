"""Independent enumeration and interval-oracle tests for recovery policies."""
import itertools
import json
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from energy_rank_bounds import EnergyBlock, bound_pairwise_mse
from study_recovery import (Block, baseline_queries, optimal_queries, pair_interval,
                            prepare_blocks, worst_width)

OUT = Path(__file__).resolve().parent


def integration_ready():
    try:
        record = json.loads((OUT / "study_recovery.json").read_text())
        return (OUT / "study_recovery.csv").exists() and "mlp" in record.get("models", [])
    except (OSError, ValueError):
        return False


class RecoveryTests(unittest.TestCase):
    def test_optimal_against_exhaustive_subsets(self):
        rng = np.random.default_rng(562009)
        for _ in range(120):
            sizes = rng.integers(1, 5, size=int(rng.integers(1, 4)))
            blocks, index = [], 0
            for size in sizes:
                ids = tuple(range(index, index + int(size)))
                cs = tuple(rng.integers(-3, 4, size=size).astype(float))
                blocks.append(Block(ids, cs, float(rng.integers(0, 5))))
                index += int(size)
            for budget in range(4):
                oracle = float("inf")
                fewest = None
                for k in range(min(index, budget) + 1):
                    for query in itertools.combinations(range(index), k):
                        if any(set(block.indices).issubset(query) for block in blocks):
                            continue
                        value = worst_width(blocks, query)
                        if value < oracle:
                            oracle, fewest = value, k
                        elif value == oracle:
                            fewest = min(fewest, k)
                query = optimal_queries(blocks, budget)
                self.assertAlmostEqual(worst_width(blocks, query), oracle, places=12)
                self.assertEqual(len(query), fewest)

    def test_zero_energy_constant_and_singleton_need_no_queries(self):
        blocks = [Block((0, 1), (-3., 4.), 0.), Block((2, 3), (1., 1.), 5.), Block((4,), (9.,), 7.)]
        self.assertEqual(optimal_queries(blocks, 20), ())
        for method in ["random", "largest_absolute_contrast", "greedy_width_reduction"]:
            self.assertEqual(baseline_queries(blocks, 20, method, np.arange(5)), ())

    def test_query_caps_and_worst_case_attainment(self):
        blocks = [Block((0, 1, 2), (-2., 0., 3.), 8.), Block((3, 4), (1., 2.), 4.)]
        for budget in [0, 1, 2, 3, 20]:
            query = optimal_queries(blocks, budget)
            self.assertLessEqual(len(query), min(budget, 3))
            for block in blocks:
                remaining = [i for i in block.indices if i not in query]
                self.assertTrue(remaining)
                # Queried readings all zero is feasible; all energy remains.
                remaining_energy = block.energy
                cs = [c for i, c in zip(block.indices, block.coefficients) if i not in query]
                expected = remaining_energy * (max(cs) - min(cs))
                self.assertAlmostEqual(worst_width([block], [i for i in query if i in block.indices]), expected)
        self.assertEqual(worst_width(blocks, optimal_queries(blocks, 20)), 0.)

    def test_bounds_against_generic_solver_and_policy_information(self):
        rng = np.random.default_rng(901711)
        for _ in range(100):
            a, b, truth = rng.uniform(0, 4, (3, 24))
            mask = np.zeros(24, bool)
            mask[rng.choice(24, 12, replace=False)] = True
            observed = truth.copy(); observed[mask] = np.nan
            totals = truth.reshape(-1, 6).sum(axis=1)
            blocks = prepare_blocks(2 * (b-a) / 24, observed, totals)
            query = optimal_queries(blocks, 3)
            revealed = observed.copy(); revealed[list(query)] = truth[list(query)]
            lo, hi = pair_interval(a, b, revealed, totals)
            eb = []
            for start in range(0, 24, 6):
                missing = [i for i in range(start, start+6) if np.isnan(revealed[i])]
                if missing:
                    residual = max(0., float(totals[start//6] - np.nansum(revealed[start:start+6])))
                    eb.append(EnergyBlock(missing, residual))
            ref = bound_pairwise_mse(a.tolist(), b.tolist(), [None if np.isnan(x) else float(x) for x in revealed], eb)
            np.testing.assert_allclose([lo, hi], [ref.lower, ref.upper], atol=1e-10, rtol=1e-10)
            self.assertLessEqual(hi-lo, worst_width(blocks, query)+1e-10)
            # Rearranged hidden targets preserving each total give the same
            # visible interface and hence the same pre-reveal batch.
            alternate = truth.copy()
            for start in range(0, 24, 6):
                ids = [i for i in range(start, start+6) if mask[i]]
                alternate[ids] = alternate[ids][::-1]
            alternate_observed = alternate.copy(); alternate_observed[mask] = np.nan
            same_blocks = prepare_blocks(2*(b-a)/24, alternate_observed, totals)
            self.assertEqual(optimal_queries(same_blocks, 3), query)

    def test_greedy_is_not_assumed_optimal(self):
        # Zero one-step gains at repeated extremes can mislead a greedy tie.
        blocks = [Block((0, 1, 2, 3, 4), (0., 0., 4., 10., 10.), 1.)]
        query = optimal_queries(blocks, 2)
        self.assertEqual(worst_width(blocks, query), 4.)
        greedy = baseline_queries(blocks, 2, "greedy_width_reduction")
        self.assertEqual(worst_width(blocks, greedy), 6.)

    def test_cross_block_allocation_defeats_immediate_gain_greedy(self):
        blocks = [Block((0, 1, 2, 3), (0., 1., 100., 101.), 1.),
                  Block((4, 5, 6), (0., 10., 20.), 1.)]
        self.assertEqual(worst_width(blocks, ()), 121.)
        self.assertEqual(worst_width(blocks, optimal_queries(blocks, 2)), 21.)
        greedy = baseline_queries(blocks, 2, "greedy_width_reduction")
        self.assertEqual(worst_width(blocks, greedy), 101.)

    @unittest.skipUnless(integration_ready(), "Run the revised AI recovery experiment first")
    def test_archived_zero_budget_matches_completed_main_study(self):
        recovery = pd.read_csv(OUT / "study_recovery.csv")
        main = pd.read_csv(OUT / "study_comparisons.csv")
        main = main[(main.method == "paired_bounds") & (main.pattern == "contiguous") &
                    (main.block_hours == 6) & (main.total_tolerance == 0) & main.gap_hours.isin([6, 12])]
        group = main.groupby(["cohort", "meter", "gap_hours"])
        sums = group[["trials", "decisions", "wrong_decisions", "enclosed_truth"]].sum()
        widths = group.mean_bound_width.mean()
        for _, row in recovery[recovery.budget == 0].iterrows():
            key = (row.cohort, row.meter, row.gap_hours)
            expected = sums.loc[key]
            self.assertEqual(row.pair_trials, expected.trials)
            self.assertEqual(row.decisions, expected.decisions)
            self.assertEqual(row.wrong_decisions, expected.wrong_decisions)
            self.assertEqual(row.enclosed_truth, expected.enclosed_truth)
            np.testing.assert_allclose(row.mean_initial_width, widths.loc[key], atol=1e-9, rtol=1e-10)

    @unittest.skipUnless(integration_ready(), "Run the revised AI recovery experiment first")
    def test_neural_zero_budget_matches_main_neural_pairs(self):
        recovery = pd.read_csv(OUT / "study_recovery_neural.csv")
        main = pd.read_csv(OUT / "study_comparisons.csv")
        main = main[(main.method == "paired_bounds") & (main.pattern == "contiguous") &
                    (main.block_hours == 6) & (main.total_tolerance == 0) & main.gap_hours.isin([6, 12]) &
                    ((main.model_a == "mlp") | (main.model_b == "mlp"))]
        expected = main.groupby(["cohort", "meter", "gap_hours"])[["trials", "decisions", "wrong_decisions"]].sum()
        for _, row in recovery[recovery.budget == 0].iterrows():
            record = expected.loc[(row.cohort,row.meter,row.gap_hours)]
            self.assertEqual(row.pair_trials, record.trials)
            self.assertEqual(row.decisions, record.decisions)
            self.assertEqual(row.wrong_decisions, record.wrong_decisions)

    @unittest.skipUnless(integration_ready() and (OUT / "study_predictions.csv").exists(), "Regenerate the AI prediction archive and recovery outputs first")
    def test_recovery_result_integrity_and_counts(self):
        from study_recovery import sha
        result = json.loads((OUT / "study_recovery.json").read_text())
        paths = {"script": OUT / "study_recovery.py", "protocol": OUT.parent / "work" / result["protocol_filename"],
                 **{name: OUT / name for name in ["study_predictions.csv", "study_summary.json", "study_recovery.csv",
                                                "study_recovery_neural.csv", "study_recovery_regression_fixtures.json",
                                                "study_recovery_pair_seed.csv","study_recovery_cases.csv"]},
                 "exploratory_protocol":OUT.parent/'work'/result['exploratory_diagnostics']['protocol_filename'],
                 "implementation_protocol":OUT.parent/'work'/result['implementation_amendment_filename']}
        for key, path in paths.items():
            self.assertEqual(sha(path), result["hashes"][key])
        self.assertEqual(result["meters"], 34)
        self.assertEqual(result["dependent_policy_budget_pair_evaluations"], result["heldout_meter_days"] * 2 * 3 * 6 * 4 * 6)
        all_rows = pd.read_csv(OUT / "study_recovery.csv")
        neural_rows = pd.read_csv(OUT / "study_recovery_neural.csv")
        keys = ["cohort","meter","gap_hours","budget","policy"]
        combined = all_rows.merge(neural_rows,on=keys,suffixes=("_all","_neural"),validate="one_to_one")
        self.assertTrue((combined.pair_trials_all == 2*combined.pair_trials_neural).all())

    @unittest.skipUnless(integration_ready(), "Run the revised AI recovery experiment first")
    def test_exploratory_diagnostics_reconcile_without_changing_primary(self):
        detailed = pd.read_csv(OUT/'study_recovery_pair_seed.csv')
        primary = pd.read_csv(OUT/'study_recovery.csv')
        keys = ['cohort','meter','gap_hours','budget','policy']
        fields = ['pair_trials','decisions','wrong_decisions','enclosed_truth']
        expected = detailed.groupby(keys)[fields].sum().sort_index()
        actual = primary.set_index(keys)[fields].sort_index()
        pd.testing.assert_frame_equal(actual,expected,check_dtype=False)
        cases = pd.read_csv(OUT/'study_recovery_cases.csv')
        result = json.loads((OUT/'study_recovery.json').read_text())
        self.assertEqual(len(cases),result['heldout_meter_days']*2*3*6)
        self.assertFalse(cases.duplicated(['cohort','meter','day','model_a','model_b','mask_seed','gap_hours']).any())
        self.assertTrue((cases.optimal_worst_width <= cases.greedy_worst_width +
                         1e-8*np.maximum(1.,cases.initial_width)).all())
        self.assertTrue((cases.normalized_absolute_reference_margin >= 0).all())

    def test_invalid_grid_inputs_rejected(self):
        a, b, observed, totals = np.zeros(6), np.ones(6), np.full(6, np.nan), np.array([6.])
        for bad in [np.array([np.nan]), np.array([np.inf]), np.array([-1.]), np.array([6., 7.]), np.array([])]:
            with self.subTest(totals=bad), self.assertRaises(ValueError):
                pair_interval(a, b, observed, bad)
        with self.assertRaises(ValueError):
            pair_interval(a, b, np.ones(6), [100.])
        for bad in [np.array([-1., np.nan, np.nan, np.nan, np.nan, np.nan]), np.array([np.inf]*6)]:
            with self.assertRaises(ValueError):
                pair_interval(a, b, bad, totals)
        for aa, bb, yy, size in [(a[:1], b, observed, 6), (a, b[:1], observed, 6),
                                 (a, b, observed[:1], 6), (a, b, observed, 4),
                                 (a, b, observed, 0), (a, b, observed, 6.0)]:
            with self.assertRaises(ValueError):
                pair_interval(aa, bb, yy, totals, size)
        with self.assertRaises(ValueError):
            pair_interval(np.full(6, np.nan), b, observed, totals)

    def test_invalid_block_and_query_inputs_rejected(self):
        for args in [((), (), 1), ((0,0),(1,2),1), ((0,1),(1,),1),
                     ((0,1),(1,np.nan),1), ((0,1),(1,2),-1), ((0,1),(1,2),np.inf),
                     ((True,1),(1,2),1), ((-1,1),(1,2),1), (None,(1,),1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                Block(*args)
        overlapping = [Block((0,1),(0,1),1), Block((1,2),(0,1),1)]
        with self.assertRaises(ValueError):
            optimal_queries(overlapping, 1)
        block = [Block((0,1),(0,1),1)]
        for budget in [-1, True, 1.5]:
            with self.assertRaises(ValueError):
                optimal_queries(block, budget)
        for query in [(0,0), (3,), (True,)]:
            with self.assertRaises(ValueError):
                worst_width(block, query)
        with self.assertRaises(ValueError):
            baseline_queries(block, 1, "random", [0,0])
        overflowing = [Block((0,1),(0,1e308),1), Block((2,3),(0,1e308),1)]
        with self.assertRaises(ValueError):
            optimal_queries(overflowing, 0)
        with self.assertRaises(ValueError):
            worst_width(overflowing, ())

    def test_weighted_sampling_is_batch_deterministic_and_nonredundant(self):
        blocks = [Block((0,1,2),(0.,1.,3.),4.), Block((3,4),(0.,2.),2.)]
        for policy in ["contrast_weighted_sampling", "squared_contrast_weighted_sampling"]:
            one = baseline_queries(blocks, 1, policy, random_seed=6189)
            two = baseline_queries(blocks, 2, policy, random_seed=6189)
            self.assertTrue(set(one).issubset(two))
            self.assertEqual(two, baseline_queries(blocks, 2, policy, random_seed=6189))
            self.assertEqual(len(two), len(set(two)))
            self.assertTrue(all(not set(b.indices).issubset(two) for b in blocks))
            self.assertEqual(baseline_queries([Block((0,1),(0.,0.),2.)], 2, policy), ())

    def test_interval_memoization_matches_direct_evaluation(self):
        from study_recovery import POLICIES
        rng = np.random.default_rng(302511)
        calls,hits = 0,0
        for _ in range(30):
            a,b,truth = rng.uniform(.01,5.,(3,24))
            observed = truth.copy(); observed[3:15] = np.nan
            totals = truth.reshape(-1,6).sum(axis=1)
            blocks = prepare_blocks(2*(b-a)/24,observed,totals)
            cache = {}
            for q in range(4):
                for policy in POLICIES:
                    query = optimal_queries(blocks,q) if policy==POLICIES[0] else baseline_queries(blocks,q,policy,np.arange(3,15),1729)
                    recovered = observed.copy(); recovered[list(query)] = truth[list(query)]
                    direct = pair_interval(a,b,recovered,totals)
                    if query in cache:
                        hits += 1
                    else:
                        cache[query] = direct
                    self.assertEqual(cache[query],direct)
                    calls += 1
        self.assertEqual(calls,720)
        self.assertGreater(hits,calls//4)

    def test_valid_archived_fixtures_preserved(self):
        fixtures = json.loads((OUT / "study_recovery_regression_fixtures.json").read_text())
        for fixture in fixtures:
            a, b, truth = (np.array(fixture[k]) for k in ["a", "b", "truth"])
            observed = np.array(fixture["observed"], dtype=float)
            totals = np.array(fixture["totals"])
            blocks = prepare_blocks(2*(b-a)/24, observed, totals)
            for case in fixture["cases"]:
                q, policy = case["q"], case["policy"]
                query = optimal_queries(blocks,q) if policy=="optimal_minimax_width" else baseline_queries(blocks,q,policy,fixture["order"])
                self.assertEqual(query, tuple(case["queries"]))
                revealed = observed.copy(); revealed[list(query)] = truth[list(query)]
                np.testing.assert_allclose(pair_interval(a,b,revealed,totals), case["interval"], rtol=1e-10, atol=1e-8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
