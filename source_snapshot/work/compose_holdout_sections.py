"""Compose the completed, frozen new-consumer replication without refitting."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def holdout_sections():
    report = json.loads((OUT / 'study_holdout_consumers.json').read_text(encoding='utf-8'))
    assert report['status'] == 'passed'
    selection = report['selection']
    assert sha(OUT / 'study_holdout_consumers.py') == selection['script_sha256']
    assert sha(ROOT / 'work/holdout_consumers_protocol.txt') == selection['protocol_sha256']
    for name, expected in {**selection['helper_hashes'], **report['output_hashes']}.items():
        assert sha(OUT / name) == expected, name
    assert report['checks']['consumer_ids_disjoint']
    assert report['checks']['unchanged_original_artifacts']
    assert not report['failures']
    audit = json.loads((OUT / 'study_holdout_independent_audit.json').read_text(encoding='utf-8'))
    assert audit['status'] == 'passed'
    assert sha(ROOT / 'work/verify_holdout_replication.py') == audit['script_sha256']
    for name, expected in audit['source_hashes'].items():
        assert sha(OUT / name) == expected, name
    lookup = {(r['regime'], r['budget'], r['policy']): r for r in report['cohort_results']}
    restricted = 'restricted_record'
    archive = 'available_test_persistence_archive'
    exact, greedy = 'optimal_minimax_width', 'greedy_width_reduction'
    p0, p2, pg = (lookup[restricted, b, policy] for b, policy in [(0, exact), (2, exact), (2, greedy)])
    a0, a2, ag = (lookup[archive, b, policy] for b, policy in [(0, exact), (2, exact), (2, greedy)])
    comparisons = {(r['regime'], r['comparison']): r for r in report['paired_consumer_comparisons']}
    epochs = [r['mlp_training']['epochs'] for r in report['fit_metadata']]
    numeric_min, numeric_max = float('inf'), -float('inf')
    with (OUT / 'study_holdout_consumers_predictions.csv').open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            values = [float(row[key]) for key in ['truth_kwh', *selection['config']['models']]]
            numeric_min, numeric_max = min(numeric_min, *values), max(numeric_max, *values)
    warnings = [w for r in report['fit_metadata'] for w in
                r.get('additional_warnings', []) + r['mlp_training'].get('warnings', [])]
    if warnings:
        training = (f'The archived fit metadata retains {len(warnings)} training warnings; '
                    'no consumer or fit was replaced in response. ')
    else:
        training = (f'All 30 neural fits stopped in {min(epochs)}--{max(epochs)} epochs '
                    'within the fixed allowance, with no captured training warnings. ')
    methods = r'''\subsection{Frozen replication on previously unused consumers}
After the original analyses, a dated local protocol fixed a replication
before evaluating additional consumers from the same UCI Portugal source.
The documented original loaders accessed only meter IDs MT\_001--MT\_080.
Candidates were MT\_081--MT\_370 in ascending order; the first 30 meeting
the original 2013-only coverage and positivity rule were selected.
All selected IDs are disjoint from the original panel. The supplement
records every candidate's training eligibility, the selected IDs, source
and code hashes, and the protocol. Selection does not depend on 2014
forecast errors, recovery results or convergence warnings.

The original timestamp conversion, causal features, daylight-saving
exclusions, 2013 training year, 2014 test windows, four model specifications
and training allowance were frozen. Each new consumer received a separate
fit using its own training history. This evaluates a fixed procedure on
previously unused consumers, not zero-shot transfer or a new data source.
No retuning, fit retry or outcome-driven consumer replacement was allowed.
The primary endpoint uses six-hour contiguous gaps, exact six-hour totals,
the three original mask seeds, all six model pairs and budgets zero and
at most two. Exact and greedy recovery are evaluated under both declared
access regimes. Primary rates weight consumers equally; pooled counts and
rates are supplied separately. Descriptive paired percentile intervals
use 2,000 whole-consumer bootstrap resamples with seed 1729. The consumers
share a historical source and test calendar, so these intervals do not
establish independent-population generalization. This local protocol is
not an independently registered study.
'''
    rows = []
    for label, zero, opt, heur in [('Restricted record', p0, p2, pg), ('Saved archive', a0, a2, ag)]:
        rows.append(f"{label} & {100*zero['resolved_fraction']:.2f} & "
                    f"{100*opt['resolved_fraction']:.2f} & {100*heur['resolved_fraction']:.2f} & "
                    f"{opt['mean_queries']:.3f}" + r'\\')
    result = r'''
\FloatBarrier
\subsection{Replication on 30 previously unused consumers}
\label{sec:newconsumers}
The fixed training-only rule selected 30 additional consumers from 255
eligible candidates. Each contributes 107 test days, giving ''' + f"{report['heldout_meter_days']:,}" + r'''
additional meter-days and ''' + f"{report['target_rows']:,}" + r''' hourly targets.
The supplied targets and fixed forecasts range from ''' + f'{numeric_min:.2f}' + r''' to
''' + f'{numeric_max:,.2f}' + r''' kWh per hourly target.
''' + training + r'''The analysis retains all ''' + f"{report['unique_pair_mask_comparisons_per_regime']:,}" + r'''
pair/mask comparisons per access regime. Policy and budget evaluations of
the same records are dependent; they are not additional independent samples.

\begin{table}[t]
\centering\small
\caption{Frozen new-consumer replication: mean consumer-level certification
rates (\%) under six-hour gaps and totals. $q\leq2$ denotes an available
two-reading budget per model pair. Final column: mean readings actually
queried by exact recovery.}
\label{tab:newconsumers}
\begin{tabular}{lrrrr}
\toprule
Access & $q=0$ & Exact $q\leq2$ & Greedy $q\leq2$ & Queries\\
\midrule
''' + '\n'.join(rows) + r'''
\bottomrule
\end{tabular}
\end{table}

'''
    for regime, label in [(restricted, 'Restricted-record'), (archive, 'Saved-archive')]:
        comp = comparisons[regime, 'exact_minus_greedy_q2']
        low, high = comp['descriptive_ci95_percentage_points']
        result += (f"{label} exact-minus-greedy coverage is "
                   f"{comp['mean_coverage_difference_percentage_points']:.3f} percentage points "
                   f"(descriptive 95\\% consumer-bootstrap interval [{low:.3f}, {high:.3f}]); "
                   f"{comp['positive_meters']} consumers favor exact recovery, "
                   f"{comp['negative_meters']} favor greedy and {comp['tied_meters']} tie.\n")
    result += (r'The saved archive reconstructs ' + f"{100*a0['free_revealed_fraction']:.3f}" +
               r'''\% of masked targets without a query. No incorrect certificate,
truth-enclosure failure or violation of the predicted worst remaining
width occurred in the ''' + f"{report['checks']['evaluations']:,}" + r''' dependent policy/budget
evaluations. Query eligibility and copied target values also passed the
recorded checks. Per-consumer, named-pair, seed and forecast-error tables,
along with these UCI-only predictions, are supplied for reconstruction.
This replication tests the fixed procedure beyond its development panel;
it does not supply production outage, target-arrival or retrieval-cost data.
''')
    result += (r'''
A separate checker, importing none of the analysis implementations,
recomputes all ''' + f"{audit['forecast_metric_rows_checked']:,}" + r''' forecast-error rows and
''' + f"{audit['independent_numerical_checks']['all_q0_pair_seed_regime_cases']:,}" + r''' zero-query comparisons,
and reconciles all pair/seed, consumer, cohort and named-pair aggregates.
Representative numerical checks additionally enumerate ''' +
               f"{audit['independent_numerical_checks']['vertices']:,}" + r''' direct-loss vertices
and ''' + f"{audit['independent_numerical_checks']['query_subsets']:,}" + r''' query subsets.
This is a separate implementation within the same study; it does not
independently refit the forecasts or reproduce every two-query case.
''')
    return methods, result, report, (p0, p2, pg, a0, a2, ag)
