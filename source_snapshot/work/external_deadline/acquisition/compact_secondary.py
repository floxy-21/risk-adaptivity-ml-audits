"""Compact exact-total LP with the predeclared uniform-barycenter secondary rule.

This follows the frozen compact_randomized.py formulation, adding one LP on
its primary-optimal face. No target values or realized outcomes enter either
objective. Caller normalizes the initial worst width to one.
"""
import time
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, vstack


def _sparse(rows, n):
    entries = [(r, c, v) for r, row in enumerate(rows) for c, v in row.items() if v]
    rr, cc, vv = zip(*entries) if entries else ([], [], [])
    return coo_matrix((vv, (rr, cc)), shape=(len(rows), n)).tocsr()


def solve_compact_secondary(coefficients, energies, budget, *, return_metadata=False):
    started = time.perf_counter()
    original = [np.asarray(c, dtype=float) for c in coefficients]
    maps = [np.argsort(c, kind='stable') for c in original]
    cs = [c[order] for c, order in zip(original, maps)]
    es = np.asarray(energies, dtype=float)
    if (not cs or len(cs) != len(es) or not all(len(c) >= 2 and np.isfinite(c).all() for c in cs)
            or not np.isfinite(es).all() or np.any(es <= 0)
            or isinstance(budget, bool) or not isinstance(budget, int) or budget < 0):
        raise ValueError('Invalid active compact-LP problem')
    caps = [len(c)-1 for c in cs]
    q = min(budget, sum(caps))
    nvars = len(cs)
    objective = list(es)
    eq, eqrhs, ub, ubrhs, flow, options, interiors = [], [], [], [], {}, [], {}
    scenario = [[{g: -1.} for _ in c] for g, c in enumerate(cs)]

    def variable():
        nonlocal nvars
        result = nvars
        nvars += 1
        objective.append(0.)
        return result

    def add(row, column, value):
        row[column] = row.get(column, 0.) + value

    for g, c in enumerate(cs):
        m = len(c)
        prefix_cap, suffix_cap = sum(caps[:g]), sum(caps[g+1:])
        for spent in range(min(q, prefix_cap)+1):
            for k in range(min(caps[g], q-spent)+1):
                if spent+k+suffix_cap < q:
                    continue
                retained = m-k
                endpoints = [(0, 0)] if retained == 1 else [(l, u) for l in range(m) for u in range(l+retained-1, m)]
                for lower, upper in endpoints:
                    x = variable()
                    add(flow.setdefault((g, spent), {}), x, 1.)
                    add(flow.setdefault((g+1, spent+k), {}), x, -1.)
                    options.append((g, spent, k, lower, upper, x))
                    interiors[x] = []
                    width = float(c[upper]-c[lower])
                    if retained == 1:
                        continue
                    add(scenario[g][lower], x, width)
                    add(scenario[g][upper], x, width)
                    row = {x: -(retained-2.)}
                    if retained > 2:
                        for i in range(lower+1, upper):
                            z = variable()
                            interiors[x].append((i, z))
                            row[z] = 1.
                            ub.append({z: 1., x: -1.})
                            ubrhs.append(0.)
                            add(scenario[g][i], z, width)
                        eq.append(row)
                        eqrhs.append(0.)
    for node, row in sorted(flow.items()):
        eq.append(row)
        eqrhs.append(1. if node == (0, 0) else -1. if node == (len(cs), q) else 0.)
    for block in scenario:
        ub.extend(block)
        ubrhs.extend([0.]*len(block))
    ae, au = _sparse(eq, nvars), _sparse(ub, nvars)
    be, bu, primary = np.array(eqrhs), np.array(ubrhs), np.array(objective)
    solver_options = {'primal_feasibility_tolerance': 1e-9, 'dual_feasibility_tolerance': 1e-9}
    first = linprog(primary, A_ub=au, b_ub=bu, A_eq=ae, b_eq=be, bounds=(0, None),
                    method='highs-ds', options=solver_options)
    if not first.success:
        raise RuntimeError('Primary compact LP: '+first.message)
    secondary = np.zeros(nvars)
    for g, block in enumerate(scenario):
        for row in block:
            for j, value in row.items():
                if j != g:  # Remove epigraph variable, retain expected-width coefficients.
                    secondary[j] += es[g]*value/len(block)
    au2 = vstack([au, coo_matrix(primary[None, :])]).tocsr()
    bu2 = np.r_[bu, first.fun]
    result = linprog(secondary, A_ub=au2, b_ub=bu2, A_eq=ae, b_eq=be, bounds=(0, None),
                     method='highs-ds', options=solver_options)
    if not result.success:
        raise RuntimeError('Secondary compact LP: '+result.message)
    primal_error = max(float(np.max(np.abs(ae@result.x-be))), float(np.max(au2@result.x-bu2)), float(-np.min(result.x)), 0.)
    dual_value = float(bu2@result.ineqlin.marginals + be@result.eqlin.marginals)
    stationarity = secondary-au2.T@result.ineqlin.marginals-ae.T@result.eqlin.marginals-result.lower.marginals
    dual_error = max(float(np.max(np.abs(stationarity))), float(np.max(result.ineqlin.marginals)), float(-np.min(result.lower.marginals)), 0.)
    gap = abs(float(result.fun)-dual_value)
    if max(primal_error, dual_error, gap) > 2e-7:
        raise ArithmeticError('Secondary compact LP numerical residual exceeds tolerance')
    report = {'value': float(first.fun), 'variables': nvars, 'equalities': len(eq), 'inequalities': len(ub)+1,
              'feasibility_max': primal_error, 'secondary_value': float(result.fun),
              'secondary_duality_gap': gap, 'secondary_dual_residual': dual_error,
              'primary_face_error': abs(float(primary@result.x-first.fun)),
              'seconds': time.perf_counter()-started,
              'positive_edge_options': int(sum(result.x[x] > 1e-9 for *_, x in options))}
    if return_metadata:
        report['metadata'] = {
            'query_count': q, 'sorted_coefficients': [c.tolist() for c in cs],
            'original_index_maps': [order.tolist() for order in maps],
            'block_epigraphs': result.x[:len(cs)].tolist(),
            'edges': [{'group': g, 'spent': spent, 'queries': k, 'lower': lower, 'upper': upper,
                       'flow': float(result.x[x]), 'interior_masses': [(i, float(result.x[z])) for i, z in interiors[x]]}
                      for g, spent, k, lower, upper, x in options]}
    return report
