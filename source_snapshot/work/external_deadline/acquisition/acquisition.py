"""Target-blind batch acquisition APIs for the external deadline benchmark.

Only predictions, already-visible targets, aggregates and frozen surrogate
parameters enter select_batch. The caller owns reveal, closure and stopping.
"""
from pathlib import Path
import importlib.util
from itertools import combinations
import sys
import time
import numpy as np
from scipy.special import erf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for path in (ROOT/'outputs', ROOT/'work/randomized_recovery_root', HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
from study_recovery import prepare_blocks, optimal_queries, baseline_queries, worst_width
from compact_secondary import solve_compact_secondary

# The existing compiler is reused in a private module instance. Its solver
# dependency is supplied explicitly; no frozen file or shared module changes.
_spec = importlib.util.spec_from_file_location('_external_deadline_compiler', ROOT/'work/randomized_recovery_root/compact_policy.py')
_compiler = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _compiler
_spec.loader.exec_module(_compiler)
_last_compact_report = None


def _secondary_solver(*args, **kwargs):
    global _last_compact_report
    result = solve_compact_secondary(*args, **kwargs)
    _last_compact_report = {k: v for k, v in result.items() if k != 'metadata'}
    return result


_compiler.solve_compact = _secondary_solver
POLICIES = ('exact', 'greedy', 'hara', 'uniform', 'randomized')


def expected_absolute_squared_loss_contrast(a, b, mean, sd):
    """Hara et al. Eq.(8), for Y~N(mean,sd**2), by a folded-normal moment.

    E |(a-Y)^2-(b-Y)^2| = |a-b| E |a+b-2Y|.
    """
    a, b, mean, sd = np.broadcast_arrays(*[np.asarray(x, dtype=float) for x in (a, b, mean, sd)])
    if any(not np.isfinite(x).all() for x in (a, b, mean, sd)) or np.any(sd < 0):
        raise ValueError('Finite predictions/surrogate parameters and nonnegative SD required')
    difference, scale = np.abs(a+b-2*mean), 2*sd
    positive = scale > 0
    absolute = difference.copy()
    ratio = np.divide(difference, scale, out=np.zeros_like(scale), where=positive)
    absolute = np.where(positive, scale*np.sqrt(2/np.pi)*np.exp(-0.5*ratio**2)+difference*erf(ratio/np.sqrt(2)), absolute)
    return np.abs(a-b)*absolute


def aggregate_conditioned_gaussian(mean, sd, observed, totals, blocksize=6):
    """Marginals of independent Gaussian predictions conditioned on each sum.

    This approximate proposal may assign negative energy; it is used only to
    acquire readings. The certificate always uses nonnegative exact totals.
    """
    visible = np.asarray(observed, dtype=float)
    mu = np.broadcast_to(np.asarray(mean, dtype=float), visible.shape).copy()
    sigma = np.broadcast_to(np.asarray(sd, dtype=float), visible.shape).copy()
    if not np.isfinite(mu).all() or not np.isfinite(sigma).all() or np.any(sigma <= 0):
        raise ValueError('Frozen Gaussian surrogate needs finite mean and strictly positive SD')
    # Validate totals and the observation vector independently of predictions.
    blocks = prepare_blocks(np.zeros(len(visible)), visible, totals, blocksize)
    for block in blocks:
        indices = list(block.indices)
        variance = sigma[indices]**2
        variance_sum = float(variance.sum())
        mu[indices] += variance/variance_sum*(block.energy-float(mu[indices].sum()))
        sigma[indices] = np.sqrt(np.maximum(0., variance-variance**2/variance_sum))
    known = np.isfinite(visible)
    mu[known], sigma[known] = visible[known], 0.
    return mu, sigma


def _eligible(blocks, selected):
    answer = []
    chosen = set(selected)
    for block in blocks:
        remaining = [(i, c) for i, c in zip(block.indices, block.coefficients) if i not in chosen]
        if block.energy > 0 and len(remaining) > 1 and max(c for i, c in remaining) > min(c for i, c in remaining):
            answer.extend(i for i, c in remaining)
    return sorted(answer)


def select_batch(policy, a, b, observed, totals, budget=2, *, rng=None,
                 surrogate_mean=None, surrogate_sd=None, blocksize=6):
    """Return a nonadaptive batch selected before any requested values are seen.

    At most two unique coordinates are selected. Reapply only after the caller
    reveals the complete batch, deducts its full cost and performs closure.
    Exactness concerns this batch's worst-width objective, not stopping cost.
    """
    started = time.perf_counter()
    if policy not in POLICIES:
        raise ValueError('Unknown acquisition policy')
    if isinstance(budget, bool) or not isinstance(budget, (int, np.integer)) or not 0 <= budget <= 2:
        raise ValueError('Batch budget must be integer zero, one or two')
    a, b, observed = (np.asarray(x, dtype=float) for x in (a, b, observed))
    if a.shape != b.shape or a.shape != observed.shape or a.ndim != 1 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Predictions and visible observations must have equal finite-vector dimensions')
    blocks = tuple(prepare_blocks(2*(b-a)/len(a), observed, totals, blocksize))
    initial = worst_width(blocks, ())
    diagnostics = {'initial_width': initial, 'target_blind_api': True}
    if not budget or initial == 0:
        query = ()
    elif policy == 'exact':
        query = optimal_queries(blocks, int(budget))
        if not query and initial > 0:
            # A width tie with the empty batch must not stall the executable
            # stopping procedure. This target-blind secondary choice reveals
            # a full feasible batch with the same optimal worst-case width.
            active = tuple(block for block in blocks if block.energy > 0 and len(block.indices) > 1 and np.ptp(block.coefficients) > 0)
            capacity = sum(len(block.indices)-1 for block in active)
            size = min(int(budget), capacity)
            available = sorted(i for block in active for i in block.indices)
            candidates = [q for q in combinations(available, size)
                          if all(len(set(q).intersection(block.indices)) < len(block.indices) for block in active)]
            value, query = min((worst_width(blocks, q), q) for q in candidates)
            if abs(value-initial) > 1e-12*max(1., initial):
                raise AssertionError('Empty-batch tie refinement changed the primary optimum')
            diagnostics['empty_optimum_progress_tie_break'] = True
    elif policy == 'greedy':
        query = baseline_queries(blocks, int(budget), 'greedy_width_reduction')
    else:
        if not isinstance(rng, np.random.Generator):
            raise TypeError('Stochastic policies require an explicit numpy.random.Generator')
        if policy == 'randomized':
            active = tuple(block for block in blocks if block.energy > 0 and len(block.indices) > 1 and np.ptp(block.coefficients) > 0)
            ranges = [float(np.ptp(block.coefficients)) for block in active]
            coefficients = [(np.asarray(block.coefficients)-min(block.coefficients))/r for block, r in zip(active, ranges)]
            energies = [block.energy*r/initial for block, r in zip(active, ranges)]
            compiled = _compiler.solve_policy(coefficients, energies, int(budget), tolerance=2e-7)
            local = compiled.sample(rng)
            query = tuple(sorted(active[g].indices[j] for g, indices in enumerate(local) for j in indices))
            diagnostics.update(compact=dict(_last_compact_report), compilation=compiled.diagnostics,
                               robust_expected_width=initial*compiled.worst_expected_width,
                               barycenter_expected_width=initial*sum(e*float(np.mean(c)) for e, c in zip(energies, compiled.expected_coefficients)),
                               expected_width_coefficients=[{'indices': list(block.indices), 'coefficients': (c*r).tolist()}
                                                            for block, c, r in zip(active, compiled.expected_coefficients, ranges)])
        else:
            if policy == 'hara':
                if surrogate_mean is None or surrogate_sd is None:
                    raise ValueError('Hara requires frozen mean and residual SD')
                mu, sd = aggregate_conditioned_gaussian(surrogate_mean, surrogate_sd, observed, totals, blocksize)
                weights = expected_absolute_squared_loss_contrast(a, b, mu, sd)
                diagnostics.update(surrogate_conditional_mean=mu.tolist(), surrogate_conditional_sd=sd.tolist(), acquisition_weights=weights.tolist(), zero_weight_fallbacks=0)
            selected = []
            draws = []
            for _ in range(int(budget)):
                eligible = _eligible(blocks, selected)
                if not eligible:
                    break
                scores = weights[eligible] if policy == 'hara' else np.ones(len(eligible))
                if not np.isfinite(scores).all():
                    raise ArithmeticError('Nonfinite acquisition weights')
                if scores.max() == 0:
                    scores = np.ones(len(eligible))
                    diagnostics['zero_weight_fallbacks'] += 1
                scaled = scores/scores.max()
                probabilities = scaled/scaled.sum()
                chosen = int(rng.choice(eligible, p=probabilities))
                draws.append({'eligible': eligible, 'probabilities': probabilities.tolist(), 'chosen': chosen})
                selected.append(chosen)
            query = tuple(sorted(selected))
            diagnostics['draws'] = draws
    if len(query) > budget or len(set(query)) != len(query) or any(not np.isnan(observed[i]) for i in query):
        raise AssertionError('Acquisition violated query eligibility or batch cap')
    diagnostics['selected_batch_worst_width'] = worst_width(blocks, query)
    return {'query_indices': list(query), 'planning_seconds': time.perf_counter()-started, 'diagnostics': diagnostics}
