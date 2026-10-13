"""Exact batch recovery for independent interval-valued energy totals.

Targets are nonnegative and uncapped. Each disjoint block has a known bound
L <= sum(targets) <= U. Fixed coefficients define the linear comparison
objective. A query reveals one target exactly; queries are selected before
answers arrive. The objective is worst-case remaining comparison width.

Example:
    block = IntervalTotalBlock((0, 1, 2), (-1, 0, 2), 1, 3)
    result = optimal_queries((block,), budget=1)
    print(result.queries, result.worst_case_width)

This optional solver is separate from the exact-total empirical study. It
does not model uncertain query answers, overlapping totals, finite target
caps, packet costs, physical meter errors, or correlations between totals.
Floating-point arithmetic is used; no directed-rounding certificate is
claimed. The implementation uses tuple bookkeeping, not backpointers.
"""
from dataclasses import dataclass
import math
import numbers


def _finite(value, name):
    if isinstance(value, bool):
        raise ValueError(name + " must be a finite real number")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(name + " must be a finite real number") from exc
    if not math.isfinite(value):
        raise ValueError(name + " must be a finite real number")
    return value


@dataclass(frozen=True)
class IntervalTotalBlock:
    indices: tuple
    coefficients: tuple
    lower: float
    upper: float

    def __post_init__(self):
        try:
            ids, cs = tuple(self.indices), tuple(self.coefficients)
        except TypeError as exc:
            raise ValueError("indices and coefficients must be sequences") from exc
        if not ids or len(ids) != len(cs):
            raise ValueError("blocks require equally sized nonempty sequences")
        if any(isinstance(i, bool) or not isinstance(i, numbers.Integral) or i < 0 for i in ids):
            raise ValueError("indices must be nonnegative integers")
        if len(set(ids)) != len(ids):
            raise ValueError("block indices must be unique")
        cs = tuple(_finite(c, "coefficient") for c in cs)
        lower, upper = _finite(self.lower, "lower total"), _finite(self.upper, "upper total")
        if not 0 <= lower <= upper:
            raise ValueError("total bounds must satisfy 0 <= lower <= upper")
        object.__setattr__(self, "indices", tuple(int(i) for i in ids))
        object.__setattr__(self, "coefficients", cs)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)


@dataclass(frozen=True)
class RecoverySolution:
    queries: tuple
    worst_case_width: float

    @property
    def used_budget(self):
        return len(self.queries)


def _validated_blocks(blocks):
    try:
        blocks = tuple(blocks)
    except TypeError as exc:
        raise ValueError("blocks must be a sequence") from exc
    seen = set()
    for block in blocks:
        if not isinstance(block, IntervalTotalBlock):
            raise ValueError("expected IntervalTotalBlock instances")
        if seen.intersection(block.indices):
            raise ValueError("blocks must have disjoint coordinate indices")
        seen.update(block.indices)
    return blocks, seen


def _range_cost(lower, upper, smallest, largest):
    # Algebraically equivalent to max(U*M,L*M)-min(L*m,U*m).
    # Each branch is a sum of nonnegative terms to avoid cancellation.
    if smallest >= 0:
        cost = (upper - lower) * largest + lower * (largest - smallest)
    elif largest <= 0:
        cost = (upper - lower) * (-smallest) + lower * (largest - smallest)
    else:
        cost = upper * largest + upper * (-smallest)
    if not math.isfinite(cost):
        raise ValueError("width arithmetic overflows; rescale inputs")
    return cost


def worst_width(blocks, queries):
    """Worst conditional width over all feasible exact query answers.

    A fully queried block contributes zero. Otherwise zero answers attain
    the worst width, including for a singleton or constant coefficients.
    """
    blocks, ids = _validated_blocks(blocks)
    try:
        queries = tuple(queries)
    except TypeError as exc:
        raise ValueError("queries must be a sequence") from exc
    if any(isinstance(i, bool) or not isinstance(i, numbers.Integral) or i not in ids for i in queries):
        raise ValueError("queries must be known coordinate indices")
    if len(set(queries)) != len(queries):
        raise ValueError("queries must be unique")
    query_set = set(queries)
    widths = []
    for block in blocks:
        retained = [c for i, c in zip(block.indices, block.coefficients) if i not in query_set]
        if retained:
            widths.append(_range_cost(block.lower, block.upper, min(retained), max(retained)))
    try:
        total = math.fsum(widths)
    except OverflowError as exc:
        raise ValueError("width arithmetic overflows; rescale inputs") from exc
    if not math.isfinite(total):
        raise ValueError("width arithmetic overflows; rescale inputs")
    return total


def _block_options(block, budget):
    ordered = sorted(zip(block.coefficients, block.indices))
    m = len(ordered)
    initial = _range_cost(block.lower, block.upper, ordered[0][0], ordered[-1][0])
    if initial == 0:
        return [(0.0, ())]
    result = []
    for k in range(min(budget, m) + 1):
        if k == m:
            result.append((0.0, tuple(sorted(block.indices))))
            continue
        retain = m - k
        cost, start = min((_range_cost(block.lower, block.upper, ordered[start][0],
                                      ordered[start + retain - 1][0]), start)
                          for start in range(k + 1))
        query = tuple(sorted(i for _, i in ordered[:start] + ordered[start + retain:]))
        result.append((cost, query))
    return result


def optimal_queries(blocks, budget):
    """Return an exact at-most-budget batch and its worst remaining width.

    Equal widths prefer fewer queries. Other ties use the first sorted
    window, then tuple/index ordering in the allocation DP; no global
    lexicographically minimal-query guarantee is made. Unlike exact-total
    recovery, querying the last coordinate of a block may be necessary.
    """
    if isinstance(budget, bool) or not isinstance(budget, numbers.Integral) or budget < 0:
        raise ValueError("budget must be a nonnegative integer")
    blocks, ids = _validated_blocks(blocks)
    cap = min(int(budget), len(ids))
    states = {0: (0.0, ())}
    for block in blocks:
        options = _block_options(block, cap)
        next_states = {}
        for used, (cost, queries) in states.items():
            for k, (extra, new_queries) in enumerate(options[:cap - used + 1]):
                total = cost + extra
                if not math.isfinite(total):
                    raise ValueError("width arithmetic overflows; rescale inputs")
                candidate = (total, tuple(sorted(queries + new_queries)))
                if used + k not in next_states or candidate < next_states[used + k]:
                    next_states[used + k] = candidate
        states = next_states
    cost, _, queries = min((cost, used, queries) for used, (cost, queries) in states.items())
    return RecoverySolution(queries, cost)
