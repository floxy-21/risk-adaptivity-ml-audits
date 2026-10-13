"""Exact nonadaptive pair-specific recovery minimizing worst-case bound width.

Theory scope: exact disjoint block totals; nonnegative uncapped targets.
The policy selects a batch before seeing recovered values. One query reveals
one interval-energy record assumed to exist in a buffer/secondary archive.
This extension uses archived forecasts and never modifies the main study.
"""
from dataclasses import dataclass
import csv
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import numbers
from pathlib import Path
import time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT, WORK = ROOT / "outputs", ROOT / "work"
POLICIES = ["optimal_minimax_width", "random", "largest_absolute_contrast", "greedy_width_reduction",
            "contrast_weighted_sampling", "squared_contrast_weighted_sampling"]
BUDGETS, GAPS, BLOCKSIZE = [0, 1, 2, 3], [6, 12], 6
SEEDS = [1103, 2207, 3301]


@dataclass(frozen=True)
class Block:
    indices: tuple
    coefficients: tuple
    energy: float

    def __post_init__(self):
        try:
            indices = tuple(self.indices)
            coefficients = tuple(self.coefficients)
        except TypeError as exc:
            raise ValueError("block indices and coefficients must be sequences") from exc
        if not indices or len(indices) != len(coefficients):
            raise ValueError("blocks need equally sized nonempty index and coefficient sequences")
        if any(isinstance(i, bool) or not isinstance(i, numbers.Integral) or i < 0 for i in indices):
            raise ValueError("block indices must be nonnegative integers")
        if len(set(indices)) != len(indices):
            raise ValueError("block indices must be unique")
        try:
            coefficients = tuple(float(c) for c in coefficients)
            energy = float(self.energy)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("block values must be numeric") from exc
        if not all(math.isfinite(c) for c in coefficients) or not math.isfinite(energy) or energy < 0:
            raise ValueError("block coefficients must be finite and energy finite and nonnegative")
        object.__setattr__(self, "indices", tuple(int(i) for i in indices))
        object.__setattr__(self, "coefficients", coefficients)
        object.__setattr__(self, "energy", energy)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _vector(values, name, allow_missing=False):
    try:
        vector = np.asarray(values, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(name + " must be a numeric vector") from exc
    if vector.ndim != 1 or not len(vector):
        raise ValueError(name + " must be a nonempty one-dimensional vector")
    invalid = np.isinf(vector) if allow_missing else ~np.isfinite(vector)
    if invalid.any():
        raise ValueError(name + " contains invalid nonfinite values")
    return vector


def _validate_blocks(blocks):
    blocks = tuple(blocks)
    seen = set()
    for block in blocks:
        if not isinstance(block, Block):
            raise ValueError("expected validated Block instances")
        if seen.intersection(block.indices):
            raise ValueError("energy blocks must be disjoint")
        seen.update(block.indices)
    return blocks, seen


def _budget(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Integral) or value < 0:
        raise ValueError("budget must be a nonnegative integer")
    return int(value)


def prepare_blocks(coefficients, observed, totals, blocksize=6):
    """Validate and partition a complete regular interval grid.

    Observed entries use NaN/None for missing. Every coordinate belongs to one
    block, and every block, including fully observed ones, has a retained total.
    Tiny total-minus-observed discrepancies within 1e-9*max(1,total) are treated
    as roundoff; this is a numerical convention, not a measurement tolerance.
    """
    coefficients = _vector(coefficients, "coefficients")
    observed = _vector(observed, "observed targets", allow_missing=True)
    totals = _vector(totals, "totals")
    if isinstance(blocksize, bool) or not isinstance(blocksize, numbers.Integral) or blocksize <= 0:
        raise ValueError("blocksize must be a positive integer")
    blocksize = int(blocksize)
    if len(coefficients) != len(observed) or len(observed) % blocksize or len(totals) != len(observed) // blocksize:
        raise ValueError("grid, coefficients and total dimensions are inconsistent")
    if np.any(observed[np.isfinite(observed)] < 0) or np.any(totals < 0):
        raise ValueError("energy observations and totals must be nonnegative")
    blocks = []
    for start in range(0, len(observed), blocksize):
        indices = tuple(i for i in range(start, start + blocksize) if np.isnan(observed[i]))
        total = float(totals[start // blocksize])
        energy = total - float(np.nansum(observed[start:start + blocksize]))
        tolerance = 1e-9 * max(1., abs(total))
        if not math.isfinite(energy) or energy < -tolerance or (not indices and abs(energy) > tolerance):
            raise ValueError("Infeasible retained total")
        if not indices:
            continue
        blocks.append(Block(indices, tuple(float(coefficients[i]) for i in indices), max(0., energy)))
    return blocks


def worst_width(blocks, queries):
    blocks, indices = _validate_blocks(blocks)
    queries = tuple(queries)
    if any(isinstance(i, bool) or not isinstance(i, numbers.Integral) or i not in indices for i in queries) or len(set(queries)) != len(queries):
        raise ValueError("queries must be unique missing-coordinate indices")
    return _worst_width(blocks, queries)


def _worst_width(blocks, queries):
    queried = set(queries)
    total = 0.0
    for block in blocks:
        if block.energy == 0:
            continue
        remaining = [c for i, c in zip(block.indices, block.coefficients) if i not in queried]
        if len(remaining) > 1:
            total += block.energy * (max(remaining) - min(remaining))
    if not math.isfinite(total):
        raise ValueError("width arithmetic overflows; rescale coefficients or energy")
    return total


def block_options(block, budget):
    """Minimum-range sorted windows, returning (cost, queried indices)."""
    ordered = sorted(zip(block.coefficients, block.indices))
    m = len(ordered)
    if block.energy == 0 or ordered[0][0] == ordered[-1][0]:
        return [(0.0, ())]
    options = []
    for k in range(min(budget, m - 1) + 1):
        retain = m - k
        cost, start = min((block.energy * (ordered[start + retain - 1][0] - ordered[start][0]), start)
                          for start in range(k + 1))
        if not math.isfinite(cost):
            raise ValueError("width arithmetic overflows; rescale coefficients or energy")
        query = tuple(sorted(i for _, i in ordered[:start] + ordered[start + retain:]))
        options.append((cost, query))
    return options


def optimal_queries(blocks, budget):
    """Exact at-most-budget DP; ties favor fewer queries.

    Remaining ties use deterministic sorted-window and tuple/index rules;
    the result is not promised globally lexicographically smallest.

    The scalar allocation recurrence has O(G*q*q) transitions after sorting
    and computing block-window costs. This readable prototype also copies and
    sorts up to q indices per transition (O(q*log(q)) bookkeeping); it does not
    claim the runtime bound of a backpointer-only implementation.
    Floating point comparisons are used; this is not interval arithmetic.
    """
    budget = _budget(budget)
    blocks, _ = _validate_blocks(blocks)
    cap = min(budget, sum(max(0, len(b.indices) - 1) for b in blocks))
    states = {0: (0.0, ())}
    for block in blocks:
        options = block_options(block, cap)
        next_states = {}
        for used, (cost, queries) in states.items():
            for k, (extra_cost, extra_queries) in enumerate(options[:cap - used + 1]):
                combined_cost = cost + extra_cost
                if not math.isfinite(combined_cost):
                    raise ValueError("width arithmetic overflows; rescale coefficients or energy")
                candidate = (combined_cost, tuple(sorted(queries + extra_queries)))
                if used + k not in next_states or candidate < next_states[used + k]:
                    next_states[used + k] = candidate
        states = next_states
    _, _, query = min((cost, used, query) for used, (cost, query) in states.items())
    return query


def baseline_queries(blocks, budget, policy, random_order=None, random_seed=0):
    """Nonadaptive baselines, excluding redundant final-in-block queries."""
    if policy not in POLICIES[1:]:
        raise ValueError("Unknown baseline")
    budget = _budget(budget)
    blocks, indices = _validate_blocks(blocks)
    query = []
    if policy == "random":
        if random_order is None or len(random_order) != len(indices) or set(random_order) != indices:
            raise ValueError("random_order must permute all missing-coordinate indices")
        priorities = {int(i): j for j, i in enumerate(random_order)}
    else:
        priorities = {}
    rng = np.random.default_rng(random_seed) if policy.endswith("weighted_sampling") else None
    coefficient = {i: c for b in blocks for i, c in zip(b.indices, b.coefficients)}
    for _ in range(budget):
        available = []
        for block in blocks:
            remaining = [i for i in block.indices if i not in query]
            if len(remaining) > 1 and block.energy > 0:
                cs = [coefficient[i] for i in remaining]
                if max(cs) > min(cs):
                    available.extend(remaining)
        if not available:
            break
        if policy == "random":
            selected = min(available, key=lambda i: priorities[i])
        elif policy == "largest_absolute_contrast":
            selected = min(available, key=lambda i: (-abs(coefficient[i]), i))
        elif policy == "greedy_width_reduction":
            selected = min(available, key=lambda i: (_worst_width(blocks, query + [i]), i))
        else:
            # Sawade-inspired adaptation: fixed-contrast weighted sampling
            # without replacement, not their with-replacement risk estimator.
            available = sorted(available)
            magnitude = np.array([abs(coefficient[i]) for i in available])
            scale = magnitude.max()
            weights = magnitude / scale if scale > 0 else np.ones(len(available))
            if policy == "squared_contrast_weighted_sampling":
                weights = weights ** 2
            selected = int(rng.choice(available, p=weights / weights.sum()))
        query.append(selected)
    return tuple(sorted(query))


def pair_interval(a, b, observed, totals, blocksize=6):
    """Numerical sharp interval using validated inputs and stable witnesses."""
    a, b = _vector(a, "prediction A"), _vector(b, "prediction B")
    observed = _vector(observed, "observed targets", allow_missing=True)
    if len(a) != len(b) or len(a) != len(observed):
        raise ValueError("predictions and observed targets must have equal lengths")
    try:
        with np.errstate(over="raise", invalid="raise"):
            coefficients = 2.0 * (b - a) / len(a)
            blocks = prepare_blocks(coefficients, observed, totals, blocksize)
            lower_y, upper_y = np.nan_to_num(observed, nan=0.), np.nan_to_num(observed, nan=0.)
            for block in blocks:
                lower_y[block.indices[int(np.argmin(block.coefficients))]] = block.energy
                upper_y[block.indices[int(np.argmax(block.coefficients))]] = block.energy
            active = a != b
            def value(y):
                terms = ((a[active] - b[active]) / len(a)) * ((a[active] - y[active]) + (b[active] - y[active]))
                result = math.fsum(terms)
                if not math.isfinite(result):
                    raise ValueError("loss arithmetic is nonfinite; rescale values")
                return result
            return value(lower_y), value(upper_y)
    except (FloatingPointError, OverflowError) as exc:
        raise ValueError("arithmetic overflow; rescale values") from exc


def decision(lo, hi):
    if not math.isfinite(lo) or not math.isfinite(hi) or lo > hi + 1e-9 * max(1.,abs(lo),abs(hi)):
        raise ValueError("decision requires finite ordered bounds")
    margin = 1e-9 * max(1., abs(lo), abs(hi))
    return 1 if lo > margin else (-1 if hi < -margin else 0)


def summarize_rows(result_frame, seed):
    cohorts = {}
    rng = np.random.default_rng(seed)
    for cohort, frame in result_frame.groupby("cohort", sort=True):
        rows = []
        for (gap, q, policy), group in frame.groupby(["gap_hours", "budget", "policy"], sort=True):
            record = {"gap_hours": int(gap), "budget": int(q), "policy": policy, "meters": len(group),
                "pair_trials": int(group.pair_trials.sum()), "decisions": int(group.decisions.sum()),
                "wrong_decisions": int(group.wrong_decisions.sum())}
            bootstrap = rng.integers(0, len(group), (2000, len(group)))
            for field in ["resolved_fraction", "actual_width_fraction", "worst_case_width_fraction", "mean_queries"]:
                values = group[field].to_numpy()
                record[field] = float(values.mean())
                if len(values) > 1:
                    record[field + "_ci95"] = np.quantile(values[bootstrap].mean(axis=1), [.025, .975]).tolist()
            rows.append(record)
        cohorts[cohort] = rows
    return cohorts


def run():
    started = time.perf_counter()
    protocol = WORK / "recovery_ai_protocol.txt"
    if not protocol.exists():
        raise RuntimeError("Freeze recovery protocol before running")
    main = json.loads((OUT / "study_summary.json").read_text())
    models = main["design"]["models"]
    if len(models) != 4 or len(set(models)) != 4 or "mlp" not in models:
        raise RuntimeError("Wait for the completed four-model AI main study")
    if sha(OUT / "study_predictions.csv") != main["artifacts"]["study_predictions.csv"]["sha256"]:
        raise RuntimeError("Prediction archive does not match the completed main summary")
    pairs = list(itertools.combinations(range(len(models)), 2))
    neural_index = models.index("mlp")
    data = pd.read_csv(OUT / "study_predictions.csv")
    # Preserve each cohort's original day labels: BLEM is UTC, others provider
    # local-grid time. Mixed aware/naive strings must not trigger conversion.
    data["day"] = pd.to_datetime(data.timestamp.str.slice(0, 10), format="%Y-%m-%d")
    all_rows, neural_rows = [], []
    detail_rows = []
    training_means = {(m['cohort'],m['meter']):m['training_mean_kwh'] for m in main['meters']}
    diagnostic_protocol = WORK / 'recovery_exploratory_amendment.txt'
    cache_protocol = WORK / 'recovery_cache_amendment.txt'
    if not diagnostic_protocol.exists():
        raise RuntimeError('Freeze the exploratory diagnostic amendment before running')
    if not cache_protocol.exists():
        raise RuntimeError('Record the implementation-only cache amendment before running')
    case_fields = ['cohort','meter','day','model_a','model_b','mask_seed','gap_hours',
        'reference_gap','normalized_absolute_reference_margin','initial_width','before_decision',
        'before_lower','before_upper','optimal_query_indices','optimal_query_count','optimal_decision',
        'optimal_actual_width','optimal_worst_width','optimal_lower','optimal_upper',
        'greedy_query_indices','greedy_query_count','greedy_decision','greedy_actual_width',
        'greedy_worst_width','greedy_lower','greedy_upper']
    case_file = open(OUT/'study_recovery_cases.csv','w',newline='',encoding='utf-8')
    case_writer = csv.DictWriter(case_file,fieldnames=case_fields)
    case_writer.writeheader()
    total_checks = 0
    for (cohort, meter), frame in data.groupby(["cohort", "meter"], sort=True):
        # n,decisions,wrong,enclosed,initialwidth,actualwidth,worstwidth,queries
        stats = {(gap, q, policy): np.zeros(8) for gap in GAPS for q in BUDGETS for policy in POLICIES}
        neural_stats = {key: np.zeros(8) for key in stats}
        detailed_stats = {(gap,seed,ai,bi,q,policy):np.zeros(8)
            for gap in GAPS for seed in SEEDS for ai,bi in pairs
            for q in BUDGETS for policy in POLICIES}
        for day, group in frame.groupby("day", sort=True):
            group = group.sort_values("timestamp")
            assert len(group) == 24
            truth = group.truth_kwh.to_numpy()
            forecasts = group[models].to_numpy().T
            supplied_totals = truth.reshape(-1, BLOCKSIZE).sum(axis=1)
            epochday = int(day.value // 86400000000000)
            for gap in GAPS:
                for mask_seed in SEEDS:
                    gapindex = [2, 6, 12].index(gap)
                    rng = np.random.default_rng(np.random.SeedSequence([mask_seed, epochday, gapindex]))
                    start = int(rng.integers(0, 25 - gap))
                    observed = truth.copy()
                    observed[start:start + gap] = np.nan
                    missing = np.arange(start, start + gap)
                    for pairindex, (ai, bi) in enumerate(pairs):
                        a, b = forecasts[ai], forecasts[bi]
                        true_gap = float(np.mean((a - truth) ** 2) - np.mean((b - truth) ** 2))
                        true_decision = decision(true_gap, true_gap)
                        coefficients = 2.0 * (b - a) / 24
                        blocks = prepare_blocks(coefficients, observed, supplied_totals)
                        initial_width = worst_width(blocks, ())
                        case_row = {'cohort':cohort,'meter':meter,'day':str(day.date()),
                            'model_a':models[ai],'model_b':models[bi],'mask_seed':mask_seed,'gap_hours':gap,
                            'reference_gap':true_gap,'normalized_absolute_reference_margin':abs(true_gap)/training_means[cohort,meter]**2,
                            'initial_width':initial_width}
                        # Exact memoization for identical observed/recovered
                        # coordinates in this fixed day/pair/mask. Policies
                        # finish before values are exposed, unchanged.
                        interval_cache = {}
                        random_order = np.random.default_rng(np.random.SeedSequence([70119, mask_seed, epochday, gapindex, pairindex])).permutation(missing)
                        for q in BUDGETS:
                            optimal = optimal_queries(blocks, q)
                            optimal_cost = worst_width(blocks, optimal)
                            for policy in POLICIES:
                                weighted_power = 2 if policy == "squared_contrast_weighted_sampling" else 1
                                sampling_seed = np.random.SeedSequence([270011,mask_seed,epochday,gapindex,pairindex,weighted_power])
                                query = optimal if policy == POLICIES[0] else baseline_queries(blocks, q, policy, random_order, sampling_seed)
                                predicted_width = worst_width(blocks, query)
                                assert len(query) <= q
                                assert optimal_cost <= predicted_width + 1e-8 * max(1., initial_width)
                                # The policy has finished. Only now reveal targets.
                                if query not in interval_cache:
                                    recovered = observed.copy()
                                    recovered[list(query)] = truth[list(query)]
                                    interval_cache[query] = pair_interval(a, b, recovered, supplied_totals)
                                lo, hi = interval_cache[query]
                                actual_width = max(0., hi - lo)
                                margin = 1e-8 * max(1., abs(true_gap), initial_width)
                                assert lo <= true_gap + margin and hi >= true_gap - margin
                                assert actual_width <= predicted_width + margin
                                d = decision(lo, hi)
                                wrong = int(d != 0 and d != true_decision)
                                assert wrong == 0
                                update = [1, d != 0, wrong, 1, initial_width, actual_width, predicted_width, len(query)]
                                stats[gap, q, policy] += update
                                detailed_stats[gap,mask_seed,ai,bi,q,policy] += update
                                if neural_index in (ai, bi):
                                    neural_stats[gap, q, policy] += update
                                if q == 0 and policy == POLICIES[0]:
                                    case_row.update(before_decision=d,before_lower=lo,before_upper=hi)
                                if q == 2 and policy in (POLICIES[0],'greedy_width_reduction'):
                                    prefix = 'optimal' if policy == POLICIES[0] else 'greedy'
                                    case_row.update({prefix+'_query_indices':';'.join(map(str,query)),
                                        prefix+'_query_count':len(query),prefix+'_decision':d,
                                        prefix+'_actual_width':actual_width,prefix+'_worst_width':predicted_width,
                                        prefix+'_lower':lo,prefix+'_upper':hi})
                                total_checks += 1
                        case_writer.writerow(case_row)
        for source, destination in [(stats,all_rows),(neural_stats,neural_rows)]:
            for (gap, q, policy), values in source.items():
                n, resolved, wrong, enclosed, initial, actual, worst, queried = values
                destination.append({"cohort": cohort, "meter": meter, "gap_hours": gap, "budget": q, "policy": policy,
                    "pair_trials": int(n), "decisions": int(resolved), "wrong_decisions": int(wrong), "enclosed_truth": int(enclosed),
                    "resolved_fraction": resolved / n, "mean_initial_width": initial / n, "mean_actual_remaining_width": actual / n,
                    "mean_worst_case_remaining_width": worst / n, "actual_width_fraction": actual / initial if initial > 0 else 0.,
                    "worst_case_width_fraction": worst / initial if initial > 0 else 0., "mean_queries": queried / n})
        for (gap,seed,ai,bi,q,policy),values in detailed_stats.items():
            n,resolved,wrong,enclosed,initial,actual,worst,queried = values
            detail_rows.append({'cohort':cohort,'meter':meter,'model_a':models[ai],'model_b':models[bi],
                'mask_seed':seed,'gap_hours':gap,'budget':q,'policy':policy,'pair_trials':int(n),
                'decisions':int(resolved),'wrong_decisions':int(wrong),'enclosed_truth':int(enclosed),
                'resolved_fraction':resolved/n,'mean_initial_width':initial/n,
                'mean_actual_remaining_width':actual/n,'mean_worst_case_remaining_width':worst/n,
                'actual_width_fraction':actual/initial if initial>0 else 0.,
                'worst_case_width_fraction':worst/initial if initial>0 else 0.,'mean_queries':queried/n})
        case_file.flush()
        print(datetime.now(timezone.utc).isoformat(timespec="seconds"), cohort, meter, "complete", flush=True)
    case_file.close()
    pd.DataFrame(detail_rows).to_csv(OUT/'study_recovery_pair_seed.csv',index=False)
    result_frame = pd.DataFrame(all_rows)
    result_frame.to_csv(OUT / "study_recovery.csv", index=False)
    neural_frame = pd.DataFrame(neural_rows)
    neural_frame.to_csv(OUT / "study_recovery_neural.csv", index=False)
    cohorts = summarize_rows(result_frame,277091)
    neural_cohorts = summarize_rows(neural_frame,277092)
    result = {"completed_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": time.perf_counter() - started,
        "study_design": "Post-main same-panel recovery extension, fixed forecasts, contiguous6/12-hour gaps, six-hour exact totals, seeds1103/2207/3301; budgets at most0/1/2/3, pair-specific nonadaptive interval-record queries",
        "not_guaranteed": "Minimax worst-case interval width does not guarantee minimum realized width or maximum empirical resolution",
        "query_semantics": "One interval-energy record assumed recoverable from a buffer or secondary archive; not a cumulative-counter snapshot or packet",
        "meters": int(data.groupby(["cohort", "meter"]).ngroups), "heldout_meter_days": int(data.groupby(["cohort", "meter", "day"]).ngroups),
        "dependent_policy_budget_pair_evaluations": total_checks, "cohorts": cohorts,
        "neural_pairs_cohorts": neural_cohorts, "models": models, "policies": POLICIES,
        "protocol_filename": protocol.name,
        "exploratory_diagnostics": {"protocol_filename":diagnostic_protocol.name,
            "scope":"Reviewer-requested post-main diagnostics; unchanged policies, masks, budgets and primary summaries",
            "case_unit":"One meter-day, pair, mask seed and gap; q2 optimal and greedy outcomes, including every success and failure",
            "reference_margin":"Absolute full-data MSE difference divided by squared training mean; descriptive analysis only, never query-policy input"},
        "implementation_amendment_filename":cache_protocol.name,
        "hashes": {"script": sha(__file__), "protocol": sha(protocol), "study_predictions.csv": sha(OUT / "study_predictions.csv"),
                   "study_summary.json": sha(OUT / "study_summary.json"), "study_recovery.csv": sha(OUT / "study_recovery.csv"),
                   "study_recovery_neural.csv": sha(OUT / "study_recovery_neural.csv"),
                   "exploratory_protocol":sha(diagnostic_protocol),
                   "implementation_protocol":sha(cache_protocol),
                   "study_recovery_pair_seed.csv":sha(OUT/'study_recovery_pair_seed.csv'),
                   "study_recovery_cases.csv":sha(OUT/'study_recovery_cases.csv'),
                   "study_recovery_regression_fixtures.json": sha(OUT / "study_recovery_regression_fixtures.json")},
        "main_study_script_sha256": main["script_sha256"],
        "summary_unit": "Macro-average per meter; whole-meter bootstrap is descriptive for this convenience panel"}
    (OUT / "study_recovery.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("COMPLETE", result["wall_seconds"], "seconds", total_checks, "checks", flush=True)


if __name__ == "__main__":
    run()
