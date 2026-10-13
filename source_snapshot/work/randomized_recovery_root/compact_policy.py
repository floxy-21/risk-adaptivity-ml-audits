"""Actionable randomized batch policies for exact nonnegative block totals.

Example:
    policy = solve_policy([[3., 0., 4., 1.]], [1.], budget=2)
    batch = policy.sample(np.random.default_rng(123))
    # batch[g] is a tuple of ORIGINAL coordinate indices to recover in block g.

The record must be fixed before the private random draw. Each batch respects
the hard budget. This optimizes worst expected conditional interval width,
not certification probability or width on every draw. Floating-point repairs
and their effect on the LP marginals are reported in ``diagnostics``.
"""
from dataclasses import dataclass
from fractions import Fraction
from bisect import bisect_right
import math
import numpy as np
from compact_randomized import solve_compact


def _project_hypersimplex(values, count):
    """Euclidean projection to [0,1]^d with an integer sum, for LP roundoff."""
    v = np.asarray(values, dtype=float)
    if not np.isfinite(v).all() or not 0 <= count <= len(v):
        raise ValueError('Invalid conditional inclusion masses')
    if count == 0:
        return np.zeros(len(v))
    if count == len(v):
        return np.ones(len(v))
    lo, hi = -float(v.max()), 1. - float(v.min())
    for _ in range(100):
        shift = (lo + hi) / 2.
        if np.clip(v + shift, 0., 1.).sum() < count:
            lo = shift
        else:
            hi = shift
    projected = np.clip(v + (lo + hi) / 2., 0., 1.)
    # Remove the final summation ulps without violating the box.
    delta = float(count - projected.sum())
    for i in range(len(projected)):
        if delta > 0:
            change = min(delta, 1. - projected[i])
        else:
            change = max(delta, -projected[i])
        projected[i] += change
        delta -= change
        if abs(delta) <= 2e-15:
            break
    if abs(float(projected.sum()) - count) > 1e-10:
        raise ArithmeticError('Hypersimplex projection did not achieve cardinality')
    return projected


def _systematic_cdf(marginals, count):
    """Exact binary-rational CDF; repair the floating sum by recorded ulps."""
    p = np.asarray(marginals, dtype=float)
    values = [Fraction.from_float(float(v)) for v in p]
    delta = Fraction(count)-sum(values, Fraction(0))
    original = values.copy()
    for i in range(len(values)):
        change = min(delta,1-values[i]) if delta > 0 else max(delta,-values[i])
        values[i] += change
        delta -= change
        if not delta:
            break
    if delta or any(v < 0 or v > 1 for v in values):
        raise ArithmeticError('Cannot construct exact fixed-cardinality CDF')
    cumulative=[];total=Fraction(0)
    for value in values:
        total += value; cumulative.append(total)
    correction=max((float(abs(a-b)) for a,b in zip(values,original)),default=0.)
    return tuple(cumulative),np.array([float(v) for v in values]),correction


def systematic_subset(marginals, count, rng, *, cumulative=None):
    """Sample exactly count indices with the given fractional inclusion masses.

    A uniform offset through cumulative intervals implements a mixture of
    fixed-cardinality subsets. It preserves marginals in exact arithmetic.
    """
    p = np.asarray(marginals, dtype=float)
    if count == 0:
        return ()
    if (not np.isfinite(p).all() or np.any(p < 0) or np.any(p > 1)
            or abs(float(p.sum()) - count) > 1e-10):
        raise ValueError('Expected hypersimplex marginals')
    if cumulative is None:
        cumulative,_,_ = _systematic_cdf(p,count)
    offset = Fraction.from_float(float(rng.random()))
    result = tuple(bisect_right(cumulative,offset+j) for j in range(count))
    if len(set(result)) != count or any(i >= len(p) for i in result):
        raise ArithmeticError('Systematic sampling failed fixed-cardinality invariant')
    return result


@dataclass
class CompactPolicy:
    coefficients: tuple
    energies: tuple
    budget: int
    query_count: int
    active_groups: tuple
    index_maps: tuple
    edges_by_node: dict
    expected_coefficients: tuple
    worst_expected_width: float
    lp_value: float
    diagnostics: dict

    def sample(self, rng):
        """Return original-index query tuples, one tuple per input block."""
        if not isinstance(rng, np.random.Generator):
            raise TypeError('Pass an explicit numpy.random.Generator')
        result = [() for _ in self.coefficients]
        spent = 0
        for g, original_group in enumerate(self.active_groups):
            edges = self.edges_by_node[(g, spent)]
            probabilities = np.array([e['conditional_probability'] for e in edges])
            edge = edges[int(rng.choice(len(edges), p=probabilities))]
            m = len(self.index_maps[g])
            retained_count = m - edge['queries']
            if retained_count == 1:
                retained = {0}
            else:
                retained = {edge['lower'], edge['upper']}
                local = systematic_subset(edge['conditional_marginals'], retained_count-2, rng,
                                          cumulative=edge['systematic_cumulative'])
                retained.update(edge['interior_indices'][i] for i in local)
            queried = tuple(sorted(int(self.index_maps[g][i]) for i in range(m) if i not in retained))
            if len(queried) != edge['queries']:
                raise ArithmeticError('Local hard-budget invariant failed')
            result[original_group] = queried
            spent += len(queried)
        if spent != self.query_count or spent > self.budget:
            raise ArithmeticError('Global hard-budget invariant failed')
        return tuple(result)

    def expected_width_at(self, values):
        """Compute the policy's exact-mixture expected width at a fixed record.

        This is an algebraic expectation, not a Monte Carlo approximation.
        Values must be nonnegative and agree with the exact block totals.
        """
        if len(values) != len(self.coefficients):
            raise ValueError('Wrong number of blocks')
        total = 0.
        for y, c, energy, a in zip(values, self.coefficients, self.energies, self.expected_coefficients):
            y = np.asarray(y, dtype=float)
            if (y.ndim != 1 or len(y) != len(c) or not np.isfinite(y).all()
                    or np.any(y < 0) or not math.isclose(float(y.sum()), energy, rel_tol=1e-9, abs_tol=1e-9)):
                raise ValueError('Record does not satisfy the declared exact total')
            total += float(np.dot(y, a))
        return total


def solve_policy(coefficients, energies, budget, *, tolerance=1e-7):
    """Solve and compile a hard-budget, exact-total randomized batch policy.

    Zero-energy, singleton and constant-coefficient blocks need no queries.
    A positive-energy empty block is rejected. Query cost is one per original
    coordinate. All scientific preprocessing (e.g. free archive copies) must
    be completed by the caller before this API is used.
    """
    if isinstance(budget, bool) or not isinstance(budget, (int, np.integer)) or budget < 0:
        raise ValueError('budget must be a nonnegative integer')
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('tolerance must be finite and positive')
    cs = tuple(np.asarray(c, dtype=float).copy() for c in coefficients)
    es = tuple(float(e) for e in energies)
    if len(cs) != len(es) or any(c.ndim != 1 or not np.isfinite(c).all() for c in cs):
        raise ValueError('Expected equally many finite one-dimensional coefficient blocks and totals')
    if any(not math.isfinite(e) or e < 0 for e in es):
        raise ValueError('Totals must be finite and nonnegative')
    if any(len(c) == 0 and e != 0 for c, e in zip(cs, es)):
        raise ValueError('A positive total needs at least one coordinate')
    active = tuple(g for g, (c,e) in enumerate(zip(cs,es)) if e > 0 and len(c) > 1 and np.ptp(c) > 0)
    expected = [np.zeros(len(c)) for c in cs]
    diagnostics = {'preprocessed_blocks':len(cs)-len(active), 'active_blocks':len(active),
                   'maximum_conditional_projection':0., 'maximum_unconditional_marginal_change':0.,
                   'maximum_flow_change':0., 'maximum_coefficient_change':0.,
                   'maximum_systematic_cdf_correction':0.,
                   'hypersimplex_sum_error':0., 'positive_flow_edges':0,
                   'scope':'Floating-point projection and flow normalization; not interval arithmetic.'}
    if not active:
        return CompactPolicy(cs,es,int(budget),0,active,(),{},tuple(expected),0.,0.,diagnostics)
    raw = solve_compact([cs[g] for g in active], [es[g] for g in active], int(budget), return_metadata=True)
    meta = raw['metadata']
    index_maps = tuple(np.asarray(order,dtype=int) for order in meta['original_index_maps'])
    raw_coefficients = [np.zeros(len(cs[g])) for g in active]
    by_node = {}
    for edge in meta['edges']:
        g, b = edge['group'], edge['spent']
        c = np.asarray(meta['sorted_coefficients'][g])
        width = float(c[edge['upper']]-c[edge['lower']])
        r = len(c)-edge['queries']
        if r > 1:
            raw_coefficients[g][edge['lower']] += width*edge['flow']
            raw_coefficients[g][edge['upper']] += width*edge['flow']
            for i,mass in edge['interior_masses']:
                raw_coefficients[g][i] += width*mass
        if edge['flow'] > 0:
            by_node.setdefault((g,b), []).append(dict(edge, width=width))
        elif edge['flow'] < -tolerance:
            raise ArithmeticError('LP supplied a negative edge flow')
    node_mass = {(0,0):1.}
    actual = [np.zeros(len(cs[g])) for g in active]
    for g in range(len(active)):
        for node in sorted(n for n in node_mass if n[0] == g):
            mass = node_mass[node]
            if mass <= 0:
                continue
            edges = by_node.get(node, [])
            flow_sum = sum(edge['flow'] for edge in edges)
            if flow_sum <= 0:
                raise ArithmeticError('Positive incoming mass has no outgoing LP flow')
            probabilities = np.asarray([e['flow']/flow_sum for e in edges])
            probabilities /= probabilities.sum()
            for edge, conditional in zip(edges, probabilities):
                edge['conditional_probability'] = float(conditional)
                edge['actual_flow'] = mass*float(conditional)
                diagnostics['maximum_flow_change'] = max(diagnostics['maximum_flow_change'], abs(edge['actual_flow']-edge['flow']))
                next_node = (g+1, node[1]+edge['queries'])
                node_mass[next_node] = node_mass.get(next_node, 0.) + edge['actual_flow']
                r = len(actual[g])-edge['queries']
                indices = tuple(i for i,_ in edge['interior_masses'])
                raw_masses = np.asarray([v for _,v in edge['interior_masses']])
                raw_p = raw_masses/edge['flow']
                projected = _project_hypersimplex(raw_p, max(0,r-2))
                cumulative,projected,cdf_correction = _systematic_cdf(projected,max(0,r-2))
                diagnostics['maximum_systematic_cdf_correction'] = max(diagnostics['maximum_systematic_cdf_correction'],cdf_correction)
                edge['interior_indices'] = indices
                edge['conditional_marginals'] = projected
                edge['systematic_cumulative'] = cumulative
                if len(projected):
                    diagnostics['maximum_conditional_projection'] = max(diagnostics['maximum_conditional_projection'], float(np.max(np.abs(projected-raw_p))))
                    diagnostics['maximum_unconditional_marginal_change'] = max(diagnostics['maximum_unconditional_marginal_change'], float(np.max(np.abs(edge['actual_flow']*projected-raw_masses))))
                    diagnostics['hypersimplex_sum_error'] = max(diagnostics['hypersimplex_sum_error'], abs(float(projected.sum())-(r-2)))
                if r > 1:
                    actual[g][edge['lower']] += edge['width']*edge['actual_flow']
                    actual[g][edge['upper']] += edge['width']*edge['actual_flow']
                    for i,p in zip(indices,projected):
                        actual[g][i] += edge['width']*edge['actual_flow']*p
                diagnostics['positive_flow_edges'] += 1
    if abs(node_mass.get((len(active),meta['query_count']),0.)-1.) > tolerance:
        raise ArithmeticError('Compiled path distribution has incorrect sink mass')
    for g, original_group in enumerate(active):
        expected[original_group][index_maps[g]] = actual[g]
        diagnostics['maximum_coefficient_change'] = max(diagnostics['maximum_coefficient_change'], float(np.max(np.abs(actual[g]-raw_coefficients[g]))))
    value = sum(e*float(a.max(initial=0.)) for e,a in zip(es,expected))
    diagnostics['lp_primal_feasibility'] = raw['feasibility_max']
    diagnostics['objective_change'] = value-raw['value']
    diagnostics['lp_dimensions'] = {k:raw[k] for k in ('variables','equalities','inequalities')}
    if (abs(value-raw['value']) > tolerance*(1.+abs(raw['value']))
            or diagnostics['maximum_flow_change'] > tolerance
            or diagnostics['maximum_unconditional_marginal_change'] > tolerance):
        raise ArithmeticError('Numerical compilation correction exceeds declared tolerance')
    return CompactPolicy(cs,es,int(budget),meta['query_count'],active,index_maps,by_node,
                         tuple(expected),float(value),raw['value'],diagnostics)
