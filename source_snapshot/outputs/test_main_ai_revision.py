"""Numerical regressions for the vectorized implementation after the AI revision."""
from decimal import Decimal, localcontext
import unittest
import numpy as np
from run_energy_rank_study import bounds, individual_extrema, MODELS


class RevisionChecks(unittest.TestCase):
    def test_large_common_offset_fully_observed_matches_decimal(self):
        a = np.tile([10000000010., 10000000002., 10000000000.], 8)
        b = a + np.tile([3., 1., 1.], 8)
        y = (a+b)/2 + np.tile([.000002, -.000002, 0.], 8)
        p = np.stack([a, b, a+1, b+1])
        with localcontext() as context:
            context.prec = 80
            expected = sum((Decimal(float(ai))-Decimal(float(yi)))**2 -
                           (Decimal(float(bi))-Decimal(float(yi)))**2
                           for ai, bi, yi in zip(a,b,y))/Decimal(24)
        lo, hi, _, _ = bounds(p,y,y.reshape(-1,6).sum(1),6,0.)
        self.assertAlmostEqual(lo[0],float(expected),delta=1e-18)
        self.assertEqual(lo[0],hi[0])
        self.assertGreater(lo[0],0.)

    def test_single_unknown_large_offset_has_exact_individual_loss(self):
        p = np.array([[1e10+1], [1e10+3]])
        low,high = individual_extrema(p,1e10,1e10)
        np.testing.assert_array_equal(low,[1.,9.])
        np.testing.assert_array_equal(high,[1.,9.])

    def test_original_contrast_is_preserved_for_large_target(self):
        p=np.tile(np.array([1.,2.,3.,4.])[:,None],(1,24))
        y=np.full(24,1e16)
        lo,hi,_,_=bounds(p,y,y.reshape(-1,6).sum(1),6,0.)
        self.assertAlmostEqual(lo[0],2e16,delta=8.)
        self.assertEqual(lo[0],hi[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
