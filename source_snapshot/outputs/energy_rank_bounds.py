"""Numerical sharp bounds for paired MSE with missing energy observations.

This reference uses only the Python standard library. Predictions are fixed;
unknown targets are constrained by coordinate bounds and disjoint energy sums.
All targets and predictions must use the same interval-energy units. Convert
power to interval energy before using this API when interval durations differ.

The optimization is exact in real arithmetic, but this floating-point
implementation is NOT an interval-arithmetic or formally verified certificate.
The bounds concern this finite evaluation set, not future generalization.
"""

from dataclasses import dataclass
import math
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class EnergyBlock:
    """Disjoint coordinate indices and a total interval (or exact total).

    ``EnergyBlock([0, 1], 3)`` means y[0] + y[1] == 3.
    ``EnergyBlock([0, 1], 2.9, 3.1)`` permits totals in [2.9, 3.1].
    Observed coordinates may occur in a block and count toward its total.
    """

    indices: Sequence[int]
    total_lower: float
    total_upper: Optional[float] = None


@dataclass(frozen=True)
class PairwiseBounds:
    """Bounds on MSE(A) - MSE(B), with attaining target completions."""

    lower: float
    upper: float
    winner: str
    lower_completion: Tuple[float, ...]
    upper_completion: Tuple[float, ...]
    numerical_margin: float


def _finite(value, name):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(name + " must be numeric and finite") from exc
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return value


def _vector(values, n, default, name, allow_positive_infinity=False):
    if values is None:
        return [default] * n
    if len(values) != n:
        raise ValueError(name + " must have one entry per prediction")
    result = []
    for value in values:
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(name + " contains a nonnumeric value") from exc
        if not math.isfinite(value) and not (
            allow_positive_infinity and value == math.inf
        ):
            raise ValueError(name + " contains an invalid nonfinite value")
        result.append(value)
    return result


def _minimum_completion(indices, coefficients, lo, hi, required, allowed):
    """Continuous bounded knapsack; ``required/allowed`` are increments."""
    result = {i: lo[i] for i in indices}
    order = sorted(indices, key=lambda i: coefficients[i])
    allocations = {i: 0.0 for i in indices}
    # Every feasible completion must add at least this much energy.
    remaining = required
    for i in order:
        amount = min(remaining, hi[i] - lo[i])
        allocations[i] = amount
        result[i] += amount
        remaining -= amount
        if remaining <= 0:
            break
    # Extra energy is beneficial only at strictly negative objective slopes.
    remaining = max(0.0, allowed - math.fsum(allocations.values()))
    for i in order:
        if coefficients[i] >= 0 or remaining <= 0:
            break
        amount = min(remaining, hi[i] - result[i])
        result[i] += amount
        remaining -= amount
    return result


def bound_pairwise_mse(
    a: Sequence[float],
    b: Sequence[float],
    observed: Sequence[Optional[float]],
    blocks: Sequence[EnergyBlock],
    *,
    lower: Optional[Sequence[float]] = None,
    upper: Optional[Sequence[float]] = None,
    weights: Optional[Sequence[float]] = None,
    numerical_tolerance: float = 1e-10,
) -> PairwiseBounds:
    """Bound the weighted MSE difference without imputing a preferred truth.

    Missing entries of ``observed`` are None. Each must belong to exactly one
    block; observed entries need not belong to a block. Blocks must not overlap.
    Lower/upper bounds are coordinate-wise; defaults are 0 and +infinity.
    Finite, nonnegative weights default to 1 and must have positive sum. A zero
    weight excludes a coordinate from loss, but not from its energy constraint.

    The common loss denominator is sum(weights) over ALL scheduled coordinates.
    The winner is A if the upper bound is below a numerical margin, B if the
    lower bound is above it, and indeterminate otherwise. The margin is
    numerical_tolerance * max(1, abs(lower), abs(upper)); it is not statistical.
    Feasibility is checked without relaxing the supplied physical constraints.
    Values extremely close to a constraint boundary can require caller-side
    rounding consistent with measurement precision.

    Complexity is O(n + sum_b m_b log m_b), where m_b is the number of missing
    coordinates in block b. Coupled/overlapping blocks require a general LP.
    """
    n = len(a)
    if n == 0 or len(b) != n or len(observed) != n:
        raise ValueError("a, b, observed must have the same nonzero length")
    a = [_finite(x, "prediction A") for x in a]
    b = [_finite(x, "prediction B") for x in b]
    tolerance = _finite(numerical_tolerance, "numerical_tolerance")
    if tolerance < 0:
        raise ValueError("numerical_tolerance must be nonnegative")
    lo = _vector(lower, n, 0.0, "lower")
    hi = _vector(upper, n, math.inf, "upper", True)
    w = _vector(weights, n, 1.0, "weights")
    if any(x < 0 for x in w):
        raise ValueError("weights must be nonnegative")
    try:
        denominator = math.fsum(w)
    except OverflowError as exc:
        raise ValueError("weight sum overflows") from exc
    if not math.isfinite(denominator) or denominator <= 0:
        raise ValueError("weights must have a finite positive sum")
    w = [x / denominator for x in w]
    fixed = []
    for i, value in enumerate(observed):
        if lo[i] > hi[i]:
            raise ValueError("lower exceeds upper")
        value = None if value is None else _finite(value, "observed target")
        if value is not None and not lo[i] <= value <= hi[i]:
            raise ValueError("observed target violates its coordinate bounds")
        fixed.append(value)
    coefficients = [2 * w[i] * (b[i] - a[i]) if w[i] else 0.0 for i in range(n)]
    if any(not math.isfinite(x) for x in coefficients):
        raise ValueError("loss arithmetic overflows; rescale all energy values")
    neg_coefficients = [-x for x in coefficients]
    low_completion = [lo[i] if fixed[i] is None else fixed[i] for i in range(n)]
    high_completion = list(low_completion)
    covered = set()
    for block in blocks:
        if not isinstance(block, EnergyBlock):
            raise ValueError("blocks must contain EnergyBlock instances")
        indices = tuple(block.indices)
        if not indices:
            raise ValueError("empty energy block")
        if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < n
               for i in indices):
            raise ValueError("block indices must be integers in range")
        if len(set(indices)) != len(indices) or covered.intersection(indices):
            raise ValueError("duplicate or overlapping block indices")
        covered.update(indices)
        total_lo = _finite(block.total_lower, "block total lower")
        total_hi = total_lo if block.total_upper is None else _finite(
            block.total_upper, "block total upper")
        if total_lo > total_hi:
            raise ValueError("block total lower exceeds upper")
        missing = tuple(i for i in indices if fixed[i] is None)
        try:
            known_total = math.fsum(fixed[i] for i in indices if fixed[i] is not None)
            base = math.fsum(lo[i] for i in missing)
            maximum = math.fsum(hi[i] for i in missing)
        except OverflowError as exc:
            raise ValueError("energy arithmetic overflows; rescale targets") from exc
        feasible_lo = max(total_lo - known_total, base)
        feasible_hi = min(total_hi - known_total, maximum)
        if not math.isfinite(base) or not math.isfinite(known_total):
            raise ValueError("energy arithmetic overflows; rescale targets")
        if feasible_lo > feasible_hi:
            raise ValueError("energy block is infeasible")
        required = max(0.0, feasible_lo - base)
        allowed = max(0.0, feasible_hi - base)
        if not math.isfinite(required) or not math.isfinite(allowed):
            raise ValueError("energy arithmetic overflows; rescale targets")
        low = _minimum_completion(missing, coefficients, lo, hi, required, allowed)
        high = _minimum_completion(
            missing, neg_coefficients, lo, hi, required, allowed)
        for i in missing:
            low_completion[i] = low[i]
            high_completion[i] = high[i]
    if any(fixed[i] is None and i not in covered for i in range(n)):
        raise ValueError("every missing target must be covered by an energy block")

    def value(completion):
        if any(not math.isfinite(y) for y in completion):
            raise ValueError("witness arithmetic overflows; rescale coordinate bounds")
        # Evaluate the attaining witness without subtracting large a^2-b^2
        # and linear terms. Keep a-b directly: subtracting two residuals could
        # erase a small representable forecast contrast when y is enormous.
        terms = [wi * (ai - bi) * ((ai - yi) + (bi - yi))
                 for wi, ai, bi, yi in zip(w, a, b, completion)
                 if wi and ai != bi]
        if any(not math.isfinite(x) for x in terms):
            raise ValueError("loss arithmetic overflows; rescale targets")
        try:
            result = math.fsum(terms)
        except OverflowError as exc:
            raise ValueError("loss arithmetic overflows; rescale targets") from exc
        if not math.isfinite(result):
            raise ValueError("nonfinite objective; rescale targets")
        return result

    low_value, high_value = value(low_completion), value(high_completion)
    margin = tolerance * max(1.0, abs(low_value), abs(high_value))
    if not math.isfinite(margin):
        raise ValueError("numerical margin overflows")
    if low_value > high_value + margin:
        raise ArithmeticError("numerically inconsistent bounds; rescale targets")
    winner = "A" if high_value < -margin else "B" if low_value > margin else "indeterminate"
    return PairwiseBounds(low_value, high_value, winner,
                          tuple(low_completion), tuple(high_completion), margin)
