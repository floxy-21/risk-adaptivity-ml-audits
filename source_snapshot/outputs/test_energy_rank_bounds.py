"""Independent enumeration and analytical checks for energy_rank_bounds.py.

Run: python -m unittest discover -s outputs -p test_energy_rank_bounds.py -v
"""
import itertools
import math
import random
import unittest

from energy_rank_bounds import EnergyBlock, bound_pairwise_mse


def direct_difference(a, b, y, weights=None):
    weights = weights or [1] * len(a)
    return sum(w * ((p - t) ** 2 - (q - t) ** 2)
               for p, q, t, w in zip(a, b, y, weights)) / sum(weights)


class EnergyRankTests(unittest.TestCase):
    def test_analytical_example_and_extrema(self):
        # D = 2*y0 - 2*y1, y0+y1=2, both in [0,2].
        result = bound_pairwise_mse([0, 2], [2, 0], [None, None],
                                   [EnergyBlock([0, 1], 2)], upper=[2, 2])
        self.assertAlmostEqual(result.lower, -4)
        self.assertAlmostEqual(result.upper, 4)
        self.assertEqual(result.winner, "indeterminate")
        self.assertEqual(result.lower_completion, (0, 2))
        self.assertEqual(result.upper_completion, (2, 0))

    def test_constant_contrast_identified_with_every_target_missing(self):
        result = bound_pairwise_mse([1, 2, 3], [2, 3, 4], [None] * 3,
                                   [EnergyBlock(range(3), 3)])
        self.assertAlmostEqual(result.lower, -3)
        self.assertAlmostEqual(result.upper, -3)
        self.assertEqual(result.winner, "A")

    def test_tolerant_total_has_interior_optimum(self):
        # The minimum fills coordinate 0 to 1, leaves coordinate 1 at zero.
        # Optimal sum=1 is strictly inside [0,2], so endpoint-only is wrong.
        result = bound_pairwise_mse([2, 0], [0, 2], [None, None],
                                   [EnergyBlock([0, 1], 0, 2)], upper=[1, 1])
        self.assertEqual(result.lower_completion, (1, 0))
        self.assertEqual(result.upper_completion, (0, 1))
        self.assertAlmostEqual(result.lower, -2)
        self.assertAlmostEqual(result.upper, 2)

    def test_observed_contribution_and_full_denominator(self):
        result = bound_pairwise_mse([0, 0, 0], [1, 1, 1], [2, None, 0],
                                   [EnergyBlock([0, 1], 3)])
        self.assertEqual(result.lower_completion, (2, 1, 0))
        self.assertAlmostEqual(result.lower, 1)
        self.assertEqual(result.winner, "B")

    def test_multiple_blocks_and_zero_weight(self):
        a, b = [0, 2, 1, 3], [2, 0, 2, 2]
        weights = [0, 1, 2, 3]
        result = bound_pairwise_mse(a, b, [None] * 4,
                                   [EnergyBlock([0, 1], 2), EnergyBlock([2, 3], 3)],
                                   upper=[3] * 4, weights=weights)
        candidates = [y for y in itertools.product(range(4), repeat=4)
                      if y[0] + y[1] == 2 and y[2] + y[3] == 3]
        values = [direct_difference(a, b, y, weights) for y in candidates]
        self.assertAlmostEqual(result.lower, min(values))
        self.assertAlmostEqual(result.upper, max(values))

    def test_signed_targets_with_nonzero_lower_bounds(self):
        result = bound_pairwise_mse([0, 1], [1, 0], [None, None],
                                   [EnergyBlock([0, 1], -1)], lower=[-2, -1], upper=[1, 2])
        self.assertAlmostEqual(result.lower, -3)
        self.assertAlmostEqual(result.upper, 1)

    def test_random_integer_vertex_oracle(self):
        # Box bounds plus integer sum bounds define an integral polytope.
        # Exhaustive integer lattice enumeration includes its extrema, so this
        # checks the continuous solver without reimplementing its greedy rule.
        rng = random.Random(29173)
        for case in range(250):
            n = rng.randint(2, 5)
            lo = [rng.randint(-1, 1) for _ in range(n)]
            hi = [x + rng.randint(0, 3) for x in lo]
            total_lo = rng.randint(sum(lo), sum(hi))
            total_hi = rng.randint(total_lo, sum(hi))
            a = [rng.randint(-3, 5) for _ in range(n)]
            b = [rng.randint(-3, 5) for _ in range(n)]
            weights = [rng.randint(0, 3) for _ in range(n)]
            weights[0] += 1
            result = bound_pairwise_mse(a, b, [None] * n,
                                       [EnergyBlock(range(n), total_lo, total_hi)],
                                       lower=lo, upper=hi, weights=weights)
            candidates = [y for y in itertools.product(
                *(range(l, u + 1) for l, u in zip(lo, hi)))
                if total_lo <= sum(y) <= total_hi]
            values = [direct_difference(a, b, y, weights) for y in candidates]
            with self.subTest(case=case):
                self.assertAlmostEqual(result.lower, min(values), places=10)
                self.assertAlmostEqual(result.upper, max(values), places=10)
                for completion, expected in [(result.lower_completion, result.lower),
                                             (result.upper_completion, result.upper)]:
                    self.assertTrue(total_lo - 1e-10 <= sum(completion) <= total_hi + 1e-10)
                    self.assertTrue(all(l - 1e-10 <= y <= u + 1e-10
                                        for l, y, u in zip(lo, completion, hi)))
                    self.assertAlmostEqual(direct_difference(a, b, completion, weights), expected)

    def test_refined_constraints_cannot_widen_bounds(self):
        args = ([0, 3, 1], [2, 0, 2], [None] * 3)
        loose = bound_pairwise_mse(*args, [EnergyBlock(range(3), 1, 7)], upper=[3] * 3)
        tight = bound_pairwise_mse(*args, [EnergyBlock(range(3), 4)], upper=[3] * 3)
        self.assertGreaterEqual(tight.lower, loose.lower)
        self.assertLessEqual(tight.upper, loose.upper)

    def test_swapping_models_reverses_bounds(self):
        a, b = [2, -1, 3], [0, 2, 2]
        args = ([None] * 3, [EnergyBlock(range(3), 3, 5)])
        ab = bound_pairwise_mse(a, b, *args)
        ba = bound_pairwise_mse(b, a, *args)
        self.assertAlmostEqual(ab.lower, -ba.upper)
        self.assertAlmostEqual(ab.upper, -ba.lower)

    def test_all_observed_no_blocks_and_tie(self):
        result = bound_pairwise_mse([1, 2], [1, 2], [1, 0], [])
        self.assertEqual((result.lower, result.upper, result.winner), (0, 0, "indeterminate"))

    def test_large_common_offset_matches_decimal_reference(self):
        from decimal import Decimal, localcontext
        a = [10000000010., 10000000002., 10000000000., 10000000008.,
             10000000010., 10000000002., 10000000008.]
        b = [10000000013., 10000000003., 10000000001., 10000000011.,
             10000000013., 10000000003., 10000000011.]
        y = [10000000011.500002, 10000000002.499998, 10000000000.5,
             10000000009.500002, 10000000011.5, 10000000002.499998,
             10000000009.499998]
        with localcontext() as context:
            context.prec = 80
            exact = sum((Decimal(ai)-Decimal(yi))**2 - (Decimal(bi)-Decimal(yi))**2
                        for ai, bi, yi in zip(a, b, y)) / Decimal(len(a))
        result = bound_pairwise_mse(a, b, y, [])
        self.assertAlmostEqual(result.lower, float(exact), delta=1e-18)
        self.assertEqual(result.lower, result.upper)
        self.assertEqual(result.winner, "B")

    def test_zero_weight_and_equal_forecasts_avoid_irrelevant_overflow(self):
        result = bound_pairwise_mse([1e308, 0], [-1e308, 1], [0, 0], [], weights=[0, 1])
        self.assertEqual(result.lower, -1.)
        identical = bound_pairwise_mse([1e308], [1e308], [-1e308], [], lower=[-1e308])
        self.assertEqual(identical.lower, 0.)

    def test_unsafe_arithmetic_overflow_fails_explicitly(self):
        with self.assertRaises(ValueError):
            bound_pairwise_mse([1e308], [-1e308], [0], [])
        with self.assertRaises(ValueError):
            bound_pairwise_mse([1e200], [0], [0], [])
        with self.assertRaises(ValueError):
            bound_pairwise_mse([1, 1], [1, 1], [1e308, 1e308], [EnergyBlock([0, 1], 1e308)])

    def test_overflowing_witness_rejected_even_for_equal_forecasts(self):
        # A finite feasible signed-bound problem can have an unrepresentable
        # greedy endpoint. Equal forecasts must not hide an infinite witness.
        with self.assertRaisesRegex(ValueError, "witness arithmetic"):
            bound_pairwise_mse([0,0], [0,0], [None,None],
                              [EnergyBlock([0,1],1.7e308)], lower=[1e308,-1e308])

    def test_infeasible_rejected(self):
        for block in [EnergyBlock([0, 1], -1), EnergyBlock([0, 1], 5),
                      EnergyBlock([0, 1], 2, 1)]:
            with self.assertRaises(ValueError):
                bound_pairwise_mse([0, 0], [1, 1], [None, None], [block], upper=[2, 2])

    def test_invalid_structure_and_values_rejected(self):
        base = dict(a=[0, 0], b=[1, 1], observed=[None, None],
                    blocks=[EnergyBlock([0, 1], 2)])
        invalid = [dict(blocks=[EnergyBlock([0], 1)]),
                   dict(blocks=[EnergyBlock([0, 1], 2), EnergyBlock([1], 1)]),
                   dict(blocks=[EnergyBlock([0, 0], 2)]),
                   dict(blocks=[EnergyBlock([], 0)]),
                   dict(blocks=[EnergyBlock([0, 2], 2)]),
                   dict(a=[math.nan, 0]), dict(b=[0, math.inf]),
                   dict(observed=[math.nan, None]), dict(lower=[-math.inf, 0]),
                   dict(upper=[math.nan, 2]), dict(upper=[-math.inf, 2]),
                   dict(lower=[3, 0], upper=[2, 2]), dict(weights=[0, 0]),
                   dict(weights=[1, -1]), dict(weights=[1, math.inf]),
                   dict(numerical_tolerance=-1), dict(numerical_tolerance=math.nan),
                   dict(blocks=[EnergyBlock([0, 1], math.inf)])]
        for update in invalid:
            with self.subTest(update=update), self.assertRaises(ValueError):
                bound_pairwise_mse(**(base | update))


if __name__ == "__main__":
    unittest.main()
