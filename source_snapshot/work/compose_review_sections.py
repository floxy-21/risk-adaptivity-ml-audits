"""Embed reviewer-requested evidence as self-contained LaTeX, without images.

PGFPlots coordinates are copied from archived result files. No hidden outcome
is used to choose abstention thresholds or the worked operator example.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'


def num(value):
    return format(float(value), '.10g')


def math_value(value):
    if value and (abs(value) < 0.0001 or abs(value) >= 10000):
        mantissa, exponent = f'{value:.3e}'.split('e')
        return '$' + mantissa + r'\times10^{' + str(int(exponent)) + '}$'
    return f'{value:.5g}'


def curve(points, style, label=None):
    text = '\\addplot+[' + style + '] coordinates {'
    text += ' '.join('(' + num(x) + ',' + num(y) + ')' for x, y in points)
    text += '};\n'
    if label:
        text += '\\addlegendentry{' + label + '}\n'
    return text


def axis(body, extra='', width=r'0.76\linewidth', height='5.5cm'):
    return (r'\begin{tikzpicture}' + '\n' + r'\begin{axis}['
            + 'width=' + width + ',height=' + height
            + r',tick label style={font=\normalsize},label style={font=\normalsize},'
            + r'legend style={font=\normalsize,draw=none},grid=major,'
            + r'grid style={gray!20},scaled ticks=false,' + extra + ']\n'
            + body + '\\end{axis}\n\\end{tikzpicture}\n')


def recovery_figure(recovery):
    lookup = {(x['gap_hours'], x['budget'], x['policy']): x
              for x in recovery['cohorts']['portugal']}
    body = ''
    policies = [('optimal_minimax_width', 'blue,mark=*', 'Exact'),
                ('greedy_width_reduction', 'orange!85!black,mark=square*,dashed', 'Greedy'),
                ('random', 'gray,mark=triangle*,dotted', 'Random')]
    for key, ylabel in [('resolved_fraction', r'Certified comparisons (\%)'),
                         ('worst_case_width_fraction', r'Worst-case width remaining (\%)')]:
        plots = ''.join(curve([(b, 100 * lookup[6, b, p][key]) for b in range(4)], style, label)
                        for p, style, label in policies)
        body += axis(plots, 'xmin=0,xmax=3,xtick={0,1,2,3},ymin=0,ymax=105,'
                     + 'xlabel={Reading budget per pair},ylabel={' + ylabel + '},'
                     + r'legend pos=outer north east', height='5.2cm') + '\n'
    return (r'\begin{figure}[htbp]\centering' + '\n' + body
            + r'\caption{Recovery in the Portugal panel: six missing hourly targets, exact '
            + r'six-hour totals, all six model pairs and three mask seeds. Curves are '
            + r'means of per-meter results. Top: realized certification coverage. Bottom: '
            + r'worst-case width relative to its no-recovery value, the criterion optimized. '
            + r'A width advantage need not give a coverage advantage at the observed truth.}'
            + '\n' + r'\label{fig:recovery}\end{figure}' + '\n')


def operator_figure(op):
    path = OUT / 'study_operator_example.csv'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == op['hashes']['table']
    with path.open(newline='', encoding='utf-8') as f:
        records = list(csv.DictReader(f))
    assert len(records) == 24
    def points(key):
        return [(i, float(row[key])) for i, row in enumerate(records) if row[key] != '']
    common = r'xmin=0,xmax=23,xtick={0,6,12,18,23},xlabel={Hour index},ylabel={Interval energy (kWh)},legend pos=outer north east'
    panels = [curve(points('mlp_kwh'), 'blue,mark=none', 'MLP')
              + curve(points('hgb_kwh'), 'orange!85!black,mark=none,dashed', 'Boosting')
              + curve(points('visible_before_kwh'), 'black,only marks,mark=*', 'Visible')
              + curve(points('recovered_value_kwh'), 'red,only marks,mark=star,mark size=3pt', 'Retrieved')]
    for phase in ['before', 'after']:
        panels.append(curve(points(phase + '_lower_witness_kwh'), 'blue,mark=none', 'Lower witness')
                      + curve(points(phase + '_upper_witness_kwh'), 'orange!85!black,mark=none,dashed', 'Upper witness'))
    titles = ['Fixed forecasts and surviving readings', 'Attaining completions before recovery',
              'Attaining completions after recovery']
    body = '\n'.join(axis(panel, common + ',title={' + title + '}', height='4.8cm')
                     for panel, title in zip(panels, titles))
    return (r'\begin{figure}[htbp]\centering' + '\n' + body
            + r'\caption{Worked historical audit, meter \texttt{'
            + op['meter'].replace('_', r'\_') + '} on ' + op['day']
            + r'. Lower and upper witnesses attain the bounds on MLP-minus-boosting MSE; '
            + r'they are measurement-compatible extremal completions, not predicted load profiles. '
            + r'The first chronologically unresolved eligible case was selected before inspecting '
            + r'the recovery outcome. Retrieved values come from the held-out reference trace. '
            + r'Full values and retained totals are in \texttt{study\_operator\_example.csv}.}'
            + '\n' + r'\label{fig:operator}\end{figure}' + '\n')


def verify_hashes(report):
    for filename, expected in report.get('source_hashes', {}).items():
        path = OUT / filename
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, filename
        elif filename == 'study_predictions.csv':
            marker = json.loads((ROOT / 'work/prediction_archive_omission.json').read_text())
            assert marker['sha256'] == expected and marker['filename'] == filename
        elif filename == 'study_recovery_cases.csv':
            marker = json.loads((OUT / 'study_recovery_cases_public_manifest.json').read_text())
            assert marker['status'] == 'passed'
            assert marker['omitted_files'][filename]['sha256'] == expected
            assert marker['omitted_files'][filename]['bytes'] > 0
            assert marker['public_files']
            for public_name, record in marker['public_files'].items():
                public_path = OUT / public_name
                assert public_path.is_file() and public_path.stat().st_size == record['bytes']
                assert hashlib.sha256(public_path.read_bytes()).hexdigest() == record['sha256'], public_name
        else:
            raise FileNotFoundError(path)


DAILY_METHODS = r'''\subsection{Daily fairness and close-competitor diagnostics}
In response to methodological review, we add exploratory daily analyses for
the six-hour contiguous gap, exact six-hour totals, and all three fixed
mask seeds. These analyses reuse every eligible saved forecast without
refitting. At budgets zero and two, each point evaluator receives exactly
the same recovered observations as the sharp comparison for that model pair.
At budget two, these are the optimal width-minimizing batch and its actual
withheld values; donor matching and residual-energy allocation are then
updated using the expanded visible record.

Within each cohort, budget, and named pair (and separately across all pairs),
selective point evaluators rank the absolute estimated comparison margin
divided by the squared training mean. Stable meter/day/seed/pair ordering
breaks ties. The selected count is matched to the sharp method's number
of certificates; additional curves retain 5\% through 100\% of comparisons.
Selection uses visible scores, not complete-reference errors. The error
rate is the pooled number of wrong decisions divided by selected decisions.
Each meter in a cohort contributes the same number of days, so pooled
certificate coverage also equals its meter macro-average. These descriptive
rates are not independent-trial estimates.

Named-pair results address comparisons among the learned models directly.
For interpretation only, we also divide comparisons into five equal-count
strata ordered by the absolute complete-reference daily MSE difference,
normalized by the squared training mean. Strata are fixed at budget zero
and reused at budget two; deterministic ordering can place tied margins
in adjacent rank quintiles. Their hidden-reference margin is never used for
query selection or abstention; this post-hoc diagnostic measures difficulty,
not a deployable selection rule.
'''


def daily_figure(report):
    styles = [('complete_case', 'gray,mark=none', 'Deletion'),
              ('uniform', 'orange!85!black,mark=none,dashed', 'Uniform'),
              ('seasonal_profile', 'blue,mark=none', 'Profile'),
              ('historical_donor', 'green!50!black,mark=none,dashdotted', 'Donor')]
    body = ''
    for budget in [0, 2]:
        rows = [r for r in report['curves'] if r['cohort'] == 'portugal'
                and r['pair'] == 'all_pairs' and r['budget'] == budget]
        plots = ''.join(curve([(100*r['coverage'], 100*r['error'])
                              for r in sorted(rows, key=lambda x: x['coverage'])
                              if r['method'] == method and r['error'] is not None], style, label)
                        for method, style, label in styles)
        cert = next(r for r in report['pairs'] if r['cohort'] == 'portugal'
                    and r['pair'] == 'all_pairs' and r['budget'] == budget)
        assert cert['certificate_wrong'] == 0
        plots += curve([(100*cert['certificate_coverage'], 0)],
                       'red,only marks,mark=star,mark size=3pt', 'Certificate')
        body += axis(plots, r'xmin=0,xmax=100,ymin=-0.5,xlabel={Coverage (\%)},'
                     + r'ylabel={Wrong decisions (\%)},legend pos=outer north east,title={Budget '
                     + str(budget) + ' per pair}', height='5.5cm') + '\n'
    return (r'\begin{figure}[htbp]\centering' + '\n' + body
            + r'\caption{Daily error versus coverage in the Portugal panel, six-hour gaps '
            + r'and exact six-hour totals. Every evaluator receives the same optimal-batch '
            + r'recovered values at budget two. Curves select by visible estimated margins; '
            + r'the star shows the sharp method\textquotesingle s attained coverage and observed error. '
            + r'Complete-reference losses are used only after selection to count errors. '
            + r'All values are descriptive on this fixed panel.}'
            + '\n' + r'\label{fig:dailycoverage}\end{figure}' + '\n')


def daily_sections(table, pct):
    report = json.loads((OUT/'study_daily_evaluation.json').read_text())
    verify_hashes(report)
    names = {'portugal': 'Portugal', 'household': 'Household', 'blem_counters': 'Counters'}
    methods = ['complete_case', 'uniform', 'seasonal_profile', 'historical_donor']
    rows = []
    for cohort in names:
        for budget in [0, 2]:
            subset = {r['method']: r for r in report['matched']
                      if r['cohort'] == cohort and r['budget'] == budget and r['pair'] == 'all_pairs'}
            assert all(subset[m]['coverage_exactly_matched'] for m in methods)
            rows.append([names[cohort], budget, pct(subset[methods[0]]['certificate_coverage']),
                         *[f"{100*subset[m]['error']:.3f}" for m in methods]])
    result = r'''\subsection{Daily decisions at equal coverage}
Table~\ref{tab:dailymatched} supplies the daily matched-coverage comparison,
including equal-information evaluation after recovery. Figure~\ref{fig:dailycoverage}
shows how selective point-method errors change with coverage. Neither
analysis tunes a threshold against hidden outcomes. Zero certificate errors
are expected when the reference is feasible and the implementation is
correct; the coverage and query requirements determine the empirical usefulness.
'''
    result += table('Source & Budget & Coverage & Deletion & Uniform & Profile & Donor', rows, 'lrrrrrr',
                    r'Daily errors (\%) among selected comparisons at identical coverage (\%). '
                    r'All six named pairs and three seeds; six-hour gaps and totals. The sharp '
                    r'method has zero observed error in every row. Budget two supplies the same '
                    r'pair-specific recovered readings to all evaluators. Selective errors are '
                    r'pooled wrong/selected counts; coverage equals the cohort\textquotesingle s '
                    r'meter macro-average.', 'tab:dailymatched', True)
    profile=next(r for r in report['matched'] if r['cohort']=='portugal' and r['budget']==2 and r['pair']=='all_pairs' and r['method']=='seasonal_profile')
    donor=next(r for r in report['matched'] if r['cohort']=='portugal' and r['budget']==2 and r['pair']=='all_pairs' and r['method']=='historical_donor')
    result+=r'''For Portugal at budget two, profile and donor imputation make
''' + str(profile['wrong']) + ' and ' + str(donor['wrong']) + r''' wrong decisions,
respectively, among ''' + f"{profile['selected']:,}" + r''' selected comparisons each.
The sharp method certifies the same number without an incorrect decision.
The point-method errors are small; these observed differences concern this
specified selective rule and panel, rather than all possible imputation
methods or future records.
'''
    result += daily_figure(report)
    pairnames = {'daily': 'Daily', 'ridge': 'Ridge', 'hist_gradient_boosting': 'Boosting', 'mlp': 'MLP'}
    lookup = {(r['pair'], r['budget']): r for r in report['pairs'] if r['cohort'] == 'portugal'}
    prows = []
    pairs = sorted({key[0] for key in lookup if key[0] != 'all_pairs'})
    for pair in pairs:
        label = '--'.join(pairnames[p] for p in pair.split('__'))
        prows.append([label, pct(lookup[pair, 0]['certificate_coverage']),
                      pct(lookup[pair, 2]['certificate_coverage'])])
    result += r'''\subsection{Named competitors and comparison difficulty}
Table~\ref{tab:namedpairs} separates every model pair in the primary panel,
including ridge versus boosting and ridge versus MLP. These comparisons
prevent aggregate coverage from being attributed solely to the difference
between persistence and learned forecasts. The complete-reference margin
strata in Table~\ref{tab:marginstrata} further isolate close daily comparisons;
they are explanatory strata formed after evaluation, not information
available to the audit.
'''
    result += table('Portugal model pair & Before & Budget two', prows, 'lrr',
                    r'Certified daily comparisons (\%) by named model pair, six-hour gaps '
                    r'and exact six-hour totals. The full cohort and pair breakdown is in '
                    r'\texttt{study\_daily\_pairs.csv}.', 'tab:namedpairs')
    strata = {(r['margin_quintile'], r['budget']): r for r in report['margin_strata']
              if r['cohort'] == 'portugal' and r['pair'] == 'all_pairs'}
    srows = []
    for q in range(1, 6):
        row = strata[q, 0]
        srows.append([q, math_value(row['complete_reference_margin_min']),
                      math_value(row['complete_reference_margin_max']),
                      pct(row['certificate_coverage']), pct(strata[q, 2]['certificate_coverage'])])
    result += table('Quintile & Min. margin & Max. margin & Before & Budget two', srows, 'lrrrr',
                    r'Portugal certification (\%) by increasing absolute normalized '
                    r'complete-reference daily loss margin, pooled over all six pairs. '
                    r'Quintile 1 contains the closest comparisons. The same cases define '
                    r'each stratum at both budgets; repeated mask seeds remain dependent. '
                    r'Pair-specific strata are archived in \texttt{study\_daily\_margin\_strata.csv}.',
                    'tab:marginstrata')
    result += r'''In the closest-margin quintile, budget-two certification is
''' + f"{100*strata[1,2]['certificate_coverage']:.2f}" + r'''\%, versus
''' + f"{100*strata[5,2]['certificate_coverage']:.2f}" + r'''\% in the widest-margin quintile.
Recovery therefore helps close comparisons but does not remove their
identification difficulty. The named learned-model comparisons and the
small-margin strata should be considered together when assessing a use case.
'''
    return result


def recovery_diagnostic_sections(recovery, table, pct):
    report = json.loads((OUT/'recovery_diagnostics.json').read_text())
    verify_hashes(report)
    groups = {(g['cohort'], g['gap_hours'], g['scope']): g for g in report['groups']}
    p = groups['portugal', 6, 'all_pairs']
    mg = p['meter_distribution']['resolution_gain_optimal_minus_greedy']
    sg = p['meter_seed_distribution']['resolution_gain_optimal_minus_greedy']
    width = p['case_distribution']['normalized_worst_width_improvement_greedy_minus_optimal']
    actual = p['case_distribution']['normalized_actual_width_improvement_greedy_minus_optimal']
    result = r'''\subsection{Incremental benefit over greedy retrieval}
The gain over no recovery combines acquiring new data with selecting them.
To isolate allocation, we compare exact and greedy selection at the same
budget on every case. In Portugal at six missing hours and budget two,
the mean meter-level resolution difference is ''' + f"{100*mg['mean']:.2f}" + r''' percentage
points, with meter-level range ''' + f"{100*mg['quantiles']['min']:.2f}" + ' to ' + f"{100*mg['quantiles']['max']:.2f}" + r'''.
The median is ''' + f"{100*mg['quantiles']['median']:.2f}" + r'''; across meter--seed summaries
the 10th and 90th percentiles are ''' + f"{100*sg['quantiles']['p10']:.2f}" + ' and ' + f"{100*sg['quantiles']['p90']:.2f}" + r''' points.
Exact selection alone resolves ''' + f"{p['optimal_only_resolved']:,}" + r''' dependent cases,
whereas greedy alone resolves ''' + f"{p['greedy_only_resolved']:,}" + r'''. Thus the worst-case-width
optimum is not a pointwise optimum for realized certification.

Across these cases, the additional worst-case-width reduction of exact
over greedy, divided by initial width, has median ''' + f"{100*width['quantiles']['median']:.2f}" + r'''\%, 90th percentile
''' + f"{100*width['quantiles']['p90']:.2f}" + r'''\%, and maximum ''' + f"{100*width['quantiles']['max']:.2f}" + r'''\%.
Realized width is larger under the exact policy in ''' + f"{actual['negative']:,}" + r''' cases;
that outcome is compatible with optimizing a worst-case objective.
The complete signed distributions and pair/seed breakdowns are retained in
\texttt{recovery\_diagnostics.json}, \texttt{study\_recovery\_pair\_seed.csv},
and the full local \texttt{study\_recovery\_cases.csv}. The public package
supplies \texttt{study\_recovery\_cases\_public.csv} for UCI cases and
hashes plus regeneration instructions for the omitted BLEM case rows.
These post-review diagnostics include
all cases and are descriptive; repeated days, pairs, and seeds are dependent.
Table~\ref{tab:actualrecovery} complements the budget caps with actual query
counts and both realized and worst-case remaining widths.
'''
    names = {'portugal': 'Portugal', 'household': 'Household', 'blem_counters': 'Counters'}
    policies = [('optimal_minimax_width', 'Exact'), ('greedy_width_reduction', 'Greedy'), ('random', 'Random')]
    rows = []
    for cohort, label in names.items():
        lookup = {(r['gap_hours'], r['budget'], r['policy']): r for r in recovery['cohorts'][cohort]}
        for policy, name in policies:
            row = lookup[6, 2, policy]
            rows.append([label, name, f"{row['mean_queries']:.3f}",
                         pct(row['actual_width_fraction']), pct(row['worst_case_width_fraction']),
                         pct(row['resolved_fraction'])])
    result += table('Source & Policy & Queries & Actual width & Worst width & Resolved', rows, 'llrrrr',
                    r'Actual mean reading counts and remaining-width fractions (\%) at budget two, '
                    r'six-hour gaps and totals. Within-meter width fractions divide summed remaining '
                    r'width by summed initial width; cohort values macro-average meters. Queries '
                    r'are per specified pair, not the cost of ranking all four models. '
                    r'All policies and budgets appear in \texttt{study\_recovery.csv}.',
                    'tab:actualrecovery', True)
    return result
