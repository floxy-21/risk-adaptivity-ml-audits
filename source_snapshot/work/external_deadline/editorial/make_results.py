"""Render verified external evidence without mutating any file or choosing outcomes.

The entry point returns (results_fragment, result_summary).  It refuses an
unfinished fit/evaluation/independent verification, mismatched pinned output,
or inconsistent headline.  It does not fit, optimize, resample, or aggregate
a new endpoint.  All numbers come from the frozen, independently checked
summaries.  The generated PGFPlots figure needs no external image artifact.
"""
from pathlib import Path
import hashlib
import json
import math
import re

import pandas as pd


POLICIES = ('exact', 'greedy', 'hara', 'uniform', 'randomized')
LABEL = {'exact': 'Exact', 'greedy': 'Greedy', 'hara': 'Hara + certificate',
         'uniform': 'Uniform', 'randomized': 'Randomized'}
SHORT_MODEL = {'daily': 'Pers.', 'ridge': 'Ridge',
               'hist_gradient_boosting': 'HGB', 'mlp': 'MLP'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _passed(path):
    obj = _json(path)
    _require(obj.get('status') == 'passed', 'Unverified artifact: '+str(path))
    return obj


def _hash_by_name(report, field, path):
    entries = [v for k, v in report[field].items()
               if Path(k.replace('\\', '/')).name == Path(path).name]
    _require(len(entries) == 1 and entries[0] == _sha(path),
             'Missing or changed verified artifact: '+str(path))


def _num(value, digits=2):
    value = float(value)
    _require(math.isfinite(value), 'Nonfinite reported value')
    return f'{value:,.{digits}f}'


def _pct(value, digits=2):
    return _num(100*float(value), digits)


def _budget(value):
    return 'NR' if value is None else str(int(value))


def _budget_prose(value):
    return 'not reached' if value is None else str(int(value))


def _row(frame, **filters):
    found = frame
    for key, value in filters.items():
        found = found[found[key] == value]
    _require(len(found) == 1, 'Expected exactly one summary row: '+str(filters))
    return found.iloc[0]


def _curve(frame, policy, budget, subgroup='all', regime='early', population='initially_unresolved'):
    return _row(frame, subgroup=subgroup, regime=regime, policy=policy,
                population=population, budget=budget)


def _stat(frame, policy, subgroup='all', regime='early', population='initially_unresolved'):
    return _row(frame, subgroup=subgroup, regime=regime, policy=policy, population=population)


def _run(ext, period, fit):
    directory = ext/period
    # All three status gates precede opening any numerical summary table.
    run = _passed(directory/'run_result.json')
    review = _passed(directory/'independent_verification.json')
    headline = _passed(directory/'headline_summary.json')
    _require(run['period'] == review['period'] == headline['period'] == period,
             'Wrong analysis period')
    for name, expected in run['outputs'].items():
        _require(_sha(directory/name) == expected, 'Changed evaluator output '+name)
    for name in ('cases.csv', 'trajectories.jsonl', 'archive_snapshots.json'):
        _hash_by_name(review, 'hashes', directory/name)
    for name in ('headline_summary.json', 'coverage_curves.csv', 'cost_summary.csv',
                 'household_curves.csv', 'pair_curves.csv', 'month_curves.csv'):
        _hash_by_name(review, 'hashes', directory/name)
    for name in ('forecast_archive.csv', 'reference_targets.csv', 'candidate_days.csv'):
        _hash_by_name(review, 'hashes', ext/'fitted'/name)
        _require(fit['output_hashes'][name] == _sha(ext/'fitted'/name), 'Changed fit output '+name)
    _require(headline['source_sha256'] == _sha(directory/'cases.csv'), 'Headline uses changed cases')
    _require(headline['summary_code_sha256'] == _sha(ext/'summarize.py'), 'Summary code changed')
    _hash_by_name(run, 'input_hashes', ext/'summarize.py')
    _require(review['B80_household_macro'] == headline['B80'], 'Independent B80 differs')
    _require(review['headline_practical_criterion_met'] == headline['fifteen_percent_budget_criterion_met'],
             'Independent criterion verdict differs')
    for name in ('bound_enclosure_failures', 'incorrect_certificates', 'timestamp_violations',
                 'duplicate_paid_queries', 'cap_violations', 'early_missing_direct_copies'):
        _require(review[name] == 0, 'Independent check failed: '+name)
    _require(review['strict_grid_checks'] == 'passed', 'Incomplete comparison grid')
    _require(review['imported_evaluator_or_acquisition'] is False, 'Checker independence differs')
    if (directory/'trace_logging_repair.json').exists():
        repair = review.get('logging_repair_verification') or {}
        _require(repair.get('status') == 'passed' and
                 repair.get('repair_report_sha256') == _sha(directory/'trace_logging_repair.json'),
                 'Trace-only repair has not been independently verified')
    _require(review['base_cases'] == run['base_cases'] == headline['counts']['base_cases'], 'Case counts differ')
    _require(review['eligible_days'] == run['eligible_days'] == headline['counts']['household_days'], 'Day counts differ')
    _require(review['household_count'] == run['households'] == headline['counts']['households'], 'Household counts differ')
    curves = pd.read_csv(directory/'coverage_curves.csv')
    costs = pd.read_csv(directory/'cost_summary.csv')
    # Independent checker checks these exact summaries; bind its reported
    # reconstruction to the underlying curves again for the editorial layer.
    _hash_by_name(review, 'hashes', directory/'independent_curves.csv')
    independent = pd.read_csv(directory/'independent_curves.csv')
    if set(('subgroup', 'regime', 'policy', 'population', 'budget', 'coverage')).issubset(independent.columns):
        keys = ['subgroup', 'regime', 'policy', 'population', 'budget']
        first = curves.set_index(keys).sort_index()
        second = independent.set_index(keys).sort_index()
        _require(first.index.equals(second.index), 'Editorial curve identities differ from checker')
        for a, b in zip(first.coverage, second.coverage):
            _require((pd.isna(a) and pd.isna(b)) or abs(float(a)-float(b)) < 1e-12,
                     'Editorial curve value differs from checker')
    else:
        raise ValueError('Independent curve schema not recognized')
    return {'run': run, 'review': review, 'headline': headline, 'curves': curves, 'costs': costs}


def _step_figure(curves):
    styles = ['blue,solid,mark=*', 'red,dashed,mark=square*', 'teal,dashdotted,mark=triangle*',
              'orange,dotted,mark=diamond*', 'violet,dash pattern=on 7pt off 3pt,mark=x']
    lines = [r'\begin{figure}[htbp]', r'\centering']
    for population, title in [('all', '(a) All eligible comparisons'),
                               ('initially_unresolved', '(b) Initially uncertified comparisons')]:
        lines += [r'\begin{tikzpicture}',
                  r'\begin{axis}[width=0.90\linewidth,height=4.7cm,xmin=0,xmax=6,ymin=0,ymax=100,',
                  'title={'+title+'},',
                  r'xtick={0,1,2,3,4,5,6},ytick={0,20,40,60,80,100},',
                  r'ylabel={Certified (\%)},grid=major,']
        if population == 'initially_unresolved':
            lines += [r'xlabel={Cumulative requested hourly target records per pair},',
                      r'legend style={at={(0.5,-0.35)},anchor=north,legend columns=3,font=\scriptsize}]']
        else:
            lines += [r'xlabel={},]']
        for policy, style in zip(POLICIES, styles):
            coordinates = ' '.join('('+str(b)+','+_pct(_curve(curves, policy, b, population=population).coverage, 6)+')' for b in range(7))
            lines.append(r'\addplot+[const plot,thick,'+style+'] coordinates {'+coordinates+'};')
            if population == 'initially_unresolved':
                lines.append(r'\addlegendentry{'+LABEL[policy]+'}')
        lines += [r'\end{axis}', r'\end{tikzpicture}']
        if population == 'all':
            lines.append(r'\par\medskip')
    lines += [r'\caption{External test decision curves under the early benchmark archive. '
              r'Panel (a) retains every eligible comparison; panel (b) uses the common '
              r'initially uncertified population. Each integer point uses executed batches '
              r'and equal household weights within its panel. The staircase does not '
              r'interpolate fractional requests. Randomized policies show the three fixed '
              r'paths; they are not exact expectations over all possible acquisition trajectories.}',
              r'\label{fig:external-stopping}', r'\end{figure}']
    return '\n'.join(lines)


def generate(root):
    """Return verified LaTeX fragments/summary; read-only, no outcome selection."""
    root = Path(root).resolve()
    ext = root/'work'/'external_deadline'
    if not ext.is_dir() and (root/'fitted').is_dir():
        ext = root
    fit = _passed(ext/'fitted'/'fit_metadata.json')
    test = _run(ext, 'test', fit)
    validation = _run(ext, 'validation', fit)
    th, vh = test['headline'], validation['headline']
    tc, vc, costs = test['curves'], validation['curves'], test['costs']
    config = _json(ext/'fitted'/'frozen_config.json')
    candidates = pd.read_csv(ext/'fitted'/'candidate_days.csv', dtype={'household_id': str})
    candidates['eligible'] = candidates.eligible.astype(str).str.lower().eq('true')
    selected = config['household_ids']
    _require(set(selected) == {h['household_id'] for h in fit['households']}, 'Fitted household set differs')
    _require(fit['model_fit_count'] == 3*len(selected), 'Learned model fit count differs')
    for period, payload in [('test', test), ('validation', validation)]:
        subset = candidates[(candidates.period == period) & candidates.eligible]
        _require(len(subset) == payload['run']['eligible_days'] and subset.household_id.nunique() == payload['run']['households'],
                 'Eligible calendar differs from reported run')
    selected_n = len(selected)
    evaluable_n = th['counts']['households']
    days_n, base_n = th['counts']['household_days'], th['counts']['base_cases']
    unresolved_n = th['counts']['initial_unresolved_base_cases']
    train_days = [int(h['training_days']) for h in fit['households']]
    warning_count = sum(len(m['warnings']) for h in fit['households'] for m in h['models'])
    excluded = sorted(set(selected)-set(candidates[(candidates.period == 'test') & candidates.eligible].household_id))
    common_coverage = float(_curve(tc, 'exact', 0, population='all').coverage)
    late = _curve(tc, 'free_archive', 0, regime='late', population='all')
    late_cost = _stat(costs, 'free_archive', regime='late', population='all')
    for policy in POLICIES:
        _require(abs(float(_curve(tc, policy, 0, population='all').coverage)-common_coverage)<1e-12,
                 'Policy initial information differs')
        _require(int(_curve(tc, policy, 0).cases) == unresolved_n, 'Conditional denominator differs')
    conditional_houses = int(_curve(tc, 'exact', 0).households)
    excluded_denominator_houses = int(_curve(tc, 'exact', 0).excluded_zero_denominator_households)
    exact_b = th['B80']['all']['exact']
    best_b = th['strongest_greedy_hara_B80']
    exact_cap = float(_curve(tc, 'exact', 6).coverage)
    criterion = bool(th['fifteen_percent_budget_criterion_met'])
    saving = th['exact_relative_B80_reduction']
    if saving is None:
        comparison = (r'The exact policy has $B_{80}='+_budget(exact_b)+r'$, while the '
                      r'better attained greedy/Hara budget is '+_budget_prose(best_b)+
                      r'; a finite relative reduction is therefore not defined.')
    else:
        comparison = (r'The exact policy has $B_{80}='+_budget(exact_b)+r'$, versus '+_budget(best_b)+
                      r' for the better greedy/Hara result, a '+_pct(saving)+r'\% relative budget reduction.')
    verdict = (r'\textbf{The predeclared 15\% practical budget criterion is '+
               ('met' if criterion else 'not met')+r'.}')
    cap = (r'Its six-request coverage is '+_pct(exact_cap)+r'\%; '+
           ('it is no lower than either' if th['exact_no_lower_cap_coverage'] else 'it is lower than at least one')+
           r' of the two prespecified baselines.')
    uniform_b = th['B80']['all']['uniform']
    if uniform_b is not None and exact_b is None:
        uniform_relation = 'it attains 80\\% whereas the exact policy does not.'
    elif th['uniform_has_lower_B80_than_exact']:
        uniform_relation = "its budget is lower than the exact policy's."
    else:
        uniform_relation = 'it does not attain a lower budget than the exact policy.'
    uniform = r'Uniform sampling has $B_{80}='+_budget(uniform_b)+r'$; '+uniform_relation
    # A prespecified secondary cost summary may explain the primary tie, but
    # never replaces the frozen B80 criterion. Compare with the lower-cost of
    # the same two declared baselines, not a selectively weaker comparator.
    cost_comparator = min(('greedy', 'hara'),
                          key=lambda p: float(_stat(costs,p).household_macro_mean_requests))
    exact_mean = float(_stat(costs,'exact').household_macro_mean_requests)
    baseline_mean = float(_stat(costs,cost_comparator).household_macro_mean_requests)
    mean_difference = baseline_mean-exact_mean
    if baseline_mean > 0:
        relative_mean = abs(mean_difference)/baseline_mean
        mean_direction = ('fewer' if mean_difference > 0 else 'more')
        mean_change = (r'This is '+_num(abs(mean_difference),3)+' '+mean_direction+r' records ('+
                       _pct(relative_mean)+r'\%).') if mean_difference else r'These mean costs are equal.'
    else:
        mean_change = r'No finite relative change is defined against a zero baseline cost.'
    pairwise_curve_differences = [float(_curve(tc,'exact',b).coverage)-
                                 float(_curve(tc,cost_comparator,b).coverage) for b in range(7)]
    if any(x > 1e-12 for x in pairwise_curve_differences) and any(x < -1e-12 for x in pairwise_curve_differences):
        curve_relation = r'Neither of these two curves dominates the other at every recorded budget.'
    elif all(abs(x) <= 1e-12 for x in pairwise_curve_differences):
        curve_relation = r'These two recorded coverage curves coincide.'
    elif all(x >= -1e-12 for x in pairwise_curve_differences):
        curve_relation = r'The exact curve is no lower at the recorded budgets in this test.'
    else:
        curve_relation = r'The comparator curve is no lower at the recorded budgets in this test.'
    secondary = (r'The secondary mean-request comparison is '+_num(exact_mean,3)+r' for exact versus '+
                 _num(baseline_mean,3)+r' for '+LABEL[cost_comparator]+
                 r', the lower-cost greedy/Hara comparator. '+mean_change+r' At two requests their '
                 r'conditional certification rates are '+_pct(_curve(tc,'exact',2).coverage)+r'\% and '+
                 _pct(_curve(tc,cost_comparator,2).coverage)+r'\%; at four they are '+
                 _pct(_curve(tc,'exact',4).coverage)+r'\% and '+
                 _pct(_curve(tc,cost_comparator,4).coverage)+r'\%, respectively. '+curve_relation+
                 r' These descriptive secondary summaries do not change the prespecified '
                 r'$B_{80}$ criterion or establish a population-level effect.')
    budget_tie = ''
    if len(set(th['B80']['all'].values())) == 1:
        budget_tie = (r'All five policies have $B_{80}='+_budget(exact_b)+r'$ on the primary population. ')
    table = [r'\begin{table}[htbp]', r'\centering\small',
             r'\caption{External test, early archive: household-macro certification among initially '
             r'uncertified comparisons. NR means 80\% coverage was not reached at the six-request cap.}',
             r'\label{tab:external-stopping}', r'\begin{tabular}{lrrrr}', r'\toprule',
             r'Policy & $C(2)$ (\%) & $C(4)$ (\%) & $C(6)$ (\%) & $B_{80}$\\', r'\midrule']
    for p in POLICIES:
        table.append(LABEL[p]+' & '+' & '.join(_pct(_curve(tc,p,b).coverage) for b in (2,4,6))+
                     ' & '+_budget(th['B80']['all'][p])+r'\\')
    table += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
    cost_table = [r'\begin{table}[htbp]', r'\centering\small\setlength{\tabcolsep}{4pt}',
                  r'\caption{External early-archive acquisition costs and planning overhead. '
                  r'$U$ denotes initially uncertified cases and $A$ all eligible cases. '
                  r'Request means average households equally; the request median and planning '
                  r'mean/95th percentile pool cases in $U$. The stop/cap columns count all '
                  r'uncertified stops (including numerical ties) and unresolved cases at the '
                  r'six-request cap, respectively. All costs include failures. Planning covers '
                  r'acquisition selection, not forecast fitting or physical retrieval.}',
                  r'\label{tab:external-costs}', r'\begin{tabular}{lrrrrr}', r'\toprule',
                  r'Policy & Mean$_U$ & Median$_U$ & Mean$_A$ & Stop/cap & \shortstack{Planning\\mean/p95 (ms)}\\', r'\midrule']
    for p in POLICIES:
        stats = _stat(costs,p)
        all_stats = _stat(costs,p,population='all')
        stops = int(stats.unresolved_at_stop)+int(stats.numerical_tie_stops)
        cost_table.append(LABEL[p]+' & '+_num(stats.household_macro_mean_requests,3)+' & '+
                          _num(stats.pooled_median_requests,1)+' & '+
                          _num(all_stats.household_macro_mean_requests,3)+' & '+
                          str(stops)+'/'+str(int(stats.unresolved_at_cap))+' & '+
                          _num(1000*stats.planning_seconds_mean_case,2)+'/'+
                          _num(1000*stats.planning_seconds_p95_case,2)+r'\\')
    cost_table += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
    breadth = [r'\begin{table}[htbp]', r'\centering\small',
               r'\caption{External early-archive $B_{80}$ by model pair and among learned-model-only '
               r'pairs. All rows use initially uncertified cases and equal household weights '
               r'within that row. Pers. is two-day persistence; HGB is histogram gradient boosting.}',
               r'\label{tab:external-pairs}', r'\begin{tabular}{lrrrrr}', r'\toprule',
               r'Comparison & Exact & Greedy & Hara & Uniform & Randomized\\', r'\midrule']
    breadth.append('All pairs & '+' & '.join(_budget(th['B80']['all'][p]) for p in POLICIES)+r'\\')
    breadth.append('Learned pairs only & '+' & '.join(_budget(th['B80']['learned'][p]) for p in POLICIES)+r'\\\midrule')
    for pair in th['pair_B80']:
        label = ' vs '.join(SHORT_MODEL[m] for m in pair['pair'].split(' vs '))
        breadth.append(label+' & '+' & '.join(_budget(pair[p]) for p in POLICIES)+r'\\')
    breadth += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
    phase = (r'The validation replay is a calibration diagnostic because the Hara surrogate '
             r'uses the full validation-period residual scale. Its $B_{80}$ values, in the same '
             r'policy order, are '+', '.join(_budget(vh['B80']['all'][p]) for p in POLICIES)+
             r'. The test comparison freezes that scale and the acquisition code before '
             r'test evaluation; validation is not presented as a second prospective cohort.')
    repair_text = ''
    if any(payload['review'].get('logging_repair_verification') for payload in (test, validation)):
        repair_text = (r' A logged observation-snapshot alias was repaired without changing '
                       r'query choices or outcomes; original and corrected traces are '
                       r'independently compared in the supplement.')
    tie_text = (r'At its final stopping state, exact recovery has '+f"{int(_stat(costs,'exact').unresolved_at_stop):,}"+
                r' unresolved cases and '+f"{int(_stat(costs,'exact').numerical_tie_stops):,}"+
                r' numerical-tie stops in the initially uncertified population. Numerical ties '
                r'are not counted as strict decisions. The corresponding exact and near-zero '
                r'reference-contrast counts are '+f"{int(_stat(costs,'exact').exact_reference_ties):,}"+
                r' and '+f"{int(_stat(costs,'exact').near_reference_ties):,}"+r', respectively; '
                r'the near-zero count includes exact ties.')
    attrition = (r'The '+str(selected_n-evaluable_n)+r' selected household'+('s' if selected_n-evaluable_n != 1 else '')+
                 r' without eligible test days '+('are' if selected_n-evaluable_n != 1 else 'is')+
                 r' retained in the source and candidate-day inventory, with no replacement.')
    warning_text = (f'All {warning_count} recorded fitting warnings are retained in the fit metadata; '
                    if warning_count else 'No fitting warnings were recorded; ')
    introduction = (r'On the frozen LCL test, the executable exact policy reaches '+
                    r'$B_{80}='+_budget(exact_b)+r'$ versus '+_budget(best_b)+
                    r' for the better greedy/Hara baseline; the predeclared 15\% budget criterion is '+
                    ('met' if criterion else 'not met')+r'. These are record-count results under '
                    r'the stated benchmark archive, not measured operational cost savings.'+'\n')
    implications = (r'\subsection{What the external decision-cost result establishes}'+'\n'+
                    verdict+' '+budget_tie+comparison+' '+cap+' '+uniform+'\n\n'+
                    (r'This supports a record-count advantage for this frozen workflow, with the '
                     r'pair and household variation in Table~\ref{tab:external-pairs}. It does not '
                     r'establish minimum sequential cost or benefit on arbitrary deployments.' if criterion else
                     r'The experiment therefore does not establish the planned practical advantage '
                     r'for exact acquisition over the stronger prespecified alternative. The '
                     r'exact per-batch width guarantee remains valid, but cannot be substituted '
                     r'for a demonstrated stopping-cost advantage.')+'\n\n'+
                    r'The comparison attaches an all-completions certificate to model evaluation. '
                    r'An empirically correct imputed ranking and a certified ranking answer '
                    r'different questions; this experiment does not show that the certificate '
                    r'improves downstream forecasting accuracy. The early and later benchmark '
                    r'archives isolate a decision before direct copies become available. Physical '
                    r'arrival times, monetary transaction costs and the availability of individual '
                    r'retrievals were not observed. The LCL result is a source-separated '
                    r'computational test with simulated missingness and totals, not a field '
                    r'deployment.'+'\n')
    results = (r'\subsection{External decision-cost evidence}\label{sec:external-results}'+'\n'+
               f'The frozen LCL test includes {evaluable_n} of {selected_n} training-selected households, '
               f'{days_n:,} eligible household-days and {base_n:,} day--mask--pair comparisons. '+attrition+' '+
               f'The completed fitting run contains {fit["model_fit_count"]} learned model fits, '
               f'using {sum(train_days):,} training household-days ({min(train_days)}--{max(train_days)} per household). '+
               warning_text+
               r'no model was replaced on the basis of test results. Validation contains '+
               f'{vh["counts"]["household_days"]:,} eligible household-days in '+
               f'{vh["counts"]["households"]} households.'+'\n\n'+
               r'The all-case early zero-request certification is '+_pct(common_coverage)+r'\%. '+
               f'The common primary population contains {unresolved_n:,} initially uncertified '
               f'comparisons from {conditional_houses} households; {excluded_denominator_houses} '
               r'households have zero conditional denominator. Table~\ref{tab:external-stopping} '
               r'and the lower panel of Figure~\ref{fig:external-stopping} use that population; '
               r'the upper panel retains all eligible comparisons. The later '
               r'archive certifies '+_pct(late.coverage)+r'\% of \emph{all} comparisons with '+
               _num(late_cost.household_macro_mean_requests,3)+r' requested records on average, after '+
               r'all permitted persistence copies are incorporated. This late all-case percentage '
               r'is not a conditional early-case curve.'+'\n\n'+
               verdict+' '+budget_tie+comparison+' '+cap+' '+uniform+'\n\n'+secondary+'\n\n'+'\n'.join(table)+'\n'+
               _step_figure(tc)+'\n'+'\n'.join(cost_table)+'\n'+r'\FloatBarrier'+'\n'+
               r'\subsection{Breadth, ties and reproducible checks}'+'\n'+
               f'Exact recovery has a strictly smaller attained $B_{{80}}$ than the better '
               f'greedy/Hara baseline in {th["households_exact_strictly_better"]} of '
               f'{len(th["household_B80"])} conditional household comparisons and '
               f'{th["pairs_exact_strictly_better"]} of {len(th["pair_B80"])} model pairs, '
               f'including {th["learned_pairs_exact_strictly_better"]} learned-model pairs. '+
               r'A baseline that never attains 80\% is shown as NR, and is not assigned an '
               r'invented numerical budget in these strict-improvement counts. '+
               r'Table~\ref{tab:external-pairs} preserves all pair-level outcomes; the '
               r'supplement supplies every household and month.'+'\n\n'+'\n'.join(breadth)+'\n\n'+
               tie_text+'\n\n'+phase+'\n\n'+
               r'A separately written checker reconstructs the source features, archive copies, '
               r'aggregate deductions, paid-query accounting, every saved acquisition stage and '
               r'household-macro tables. It checks '+f'{test["review"]["fully_replayed_batches"]:,} '+
               r'test batches and '+f'{validation["review"]["fully_replayed_batches"]:,} '+
               r'validation batches. Both runs have zero detected incorrect certificates, '
               r'enclosure failures, timestamp violations, duplicate paid requests and cap '
               r'violations. This is an independent implementation within the study, not '
               r'external-investigator replication; it does not independently refit the '
               r'models or prove each acquisition routine optimal.'+repair_text+'\n')
    abstract = (r'Missing verification targets can make historical comparisons of machine-learning '
                r'forecasts ambiguous even when aggregate measurements survive. We derive sharp '
                r'paired squared-loss bounds over nonnegative completions consistent with observed '
                r'targets and disjoint aggregate totals. Exact deterministic recovery minimizes '
                r'worst remaining comparison width; a compact randomized formulation minimizes '
                r'worst expected width, with a fixed secondary criterion for selecting among robust optima. '
                r'For one block with $m$ missing and $r\geq2$ retained coordinates and positive '
                r'optima, the deterministic/randomized value ratio is at most $m/r$; separated '
                r'clusters attain it when $r$ divides $m$. '
                r'The bounds also justify stopping when a model decision satisfies a declared '
                r'worst-case regret tolerance. An external Low Carbon London benchmark evaluates '
                r'executable repeated-batch acquisition on '+str(evaluable_n)+r' households and '+
                f'{days_n:,}'+r' test household-days using chronologically fitted forecasts. '
                r'Among initially uncertified comparisons, exact recovery reaches 80\% '
                r'household-macro certification at budget '+_budget_prose(exact_b)+r', compared with '+
                _budget_prose(best_b)+r' for the better greedy/Hara baseline. The predeclared 15\% '
                r'budget-reduction criterion is '+('met' if criterion else 'not met')+r'. '
                r'Later saved persistence predictions certify '+_pct(late.coverage)+r'\% of all '
                r'comparisons without paid recovery. Historical archive-consistent evidence '
                r'retains the adverse randomized tradeoff: a 9.88\% reduction in worst expected '
                r'width accompanies a 17.45\% increase at the observed records. Reproducible '
                r'source reconstruction, complete policy traces and runtime/memory experiments '
                r'delimit the guarantees. The contribution is certified fixed-record comparison '
                r'and exact recovery optimization; record-count outcomes under constructed '
                r'archives do not establish monetary savings or production latency gains.')
    abstract_words = len(re.sub(r'\\[A-Za-z]+|[{}$]', ' ', abstract).split())
    _require(150 <= abstract_words <= 250, 'Abstract outside 150--250 words: '+str(abstract_words))
    conclusion = (r'Paired loss cancellation yields sharp aggregate-constrained comparisons and '
                  r'exact deterministic and randomized batch-recovery procedures. The compact '
                  r'formulation, fixed secondary optimum and decision-stopping consequence '
                  r'make the guarantees explicit and reproducible. '+comparison+' '+verdict+' '+
                  uniform+'\n\n'+
                  r'The external sequential experiment uses common information, charges all '
                  r'requested records, skips certified cases and retains unsuccessful and tied '
                  r'outcomes. It is an executable pairwise workflow, not a proof of globally '
                  r'optimal stopping. The later archive eliminates the need for most or all '
                  r'recovery under its declared access schedule. Historical donor accuracy '
                  r'and the randomized realized-width penalty remain evidence against broad '
                  r'operational-superiority claims. Source-separated computation strengthens '
                  r'the evaluation without replacing the need to measure real retrieval '
                  r'availability, transaction costs and arrival times in a deployment. The '
                  r'released code separates source reconstruction, fresh fitting, saved-forecast '
                  r'replay and independent trace verification.')
    result_summary = {'verified': True, 'abstract_latex': abstract,
                      'introduction_result_latex': introduction,
                      'external_interpretation_latex': implications,
                      'conclusion_latex': conclusion,
                      'abstract_word_count': abstract_words,
                      'evidence': {'test': th, 'validation': vh,
                                   'training_selected_households': selected_n,
                                   'excluded_test_households': excluded,
                                   'model_fit_count': fit['model_fit_count'],
                                   'training_household_days': sum(train_days),
                                   'fit_warning_count': warning_count,
                                   'early_initial_all_case_coverage': common_coverage,
                                   'late_all_case_coverage': float(late.coverage)},
                      'generation_scope': 'Read-only rendering of verified frozen summaries; no outcome selection or new analysis.'}
    return results, result_summary
