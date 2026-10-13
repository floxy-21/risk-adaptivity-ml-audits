"""Compose the frozen real-trace interval-total sensitivity from saved results."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def interval_trace_sections(table, pct):
    """Return (experimental_design, results); table/pct follow main composer API."""
    report = json.loads((OUT/'study_interval_trace_recovery.json').read_text(encoding='utf-8'))
    assert report['status'] == 'passed'
    assert report['meters'] == 34 and report['heldout_meter_days'] == 3729
    assert report['checks']['wrong_certificates'] == 0
    assert report['checks']['source_artifacts_unchanged']
    assert digest(ROOT/'work/interval_trace_protocol.txt') == report['protocol_sha256']
    for name, expected in report['source_hashes'].items():
        path = OUT/name
        # The complete local BLEM-bearing archive need not be redistributed.
        if path.exists():
            assert digest(path) == expected, name
    for name, expected in report['output_hashes'].items():
        assert digest(OUT/name) == expected, name
    audit = json.loads((OUT/'study_interval_trace_audit.json').read_text(encoding='utf-8'))
    assert audit['status'] == 'passed' and audit['existing_artifacts_unchanged']
    assert digest(ROOT/'work/verify_interval_trace.py') == audit['script_sha256']
    for name, expected in audit['source_hashes'].items():
        if (OUT/name).exists():
            assert digest(OUT/name) == expected, name
    lookup = {(r['cohort'], r['tolerance'], r['regime'], r['budget'], r['policy']):r
              for r in report['cohort_results']}
    differences = {(r['cohort'],r['tolerance'],r['regime']):r for r in report['exact_vs_greedy']}
    exact, greedy = report['policies']
    restricted, archive = report['regimes']
    source_names = {'portugal':'Portugal','household':'Household','blem_counters':'Counters'}
    rows = []
    for cohort in ('portugal','household','blem_counters'):
        for regime, access in ((restricted,'D'),(archive,'A')):
            for tolerance in report['tolerances']:
                zero = lookup[cohort,tolerance,regime,0,exact]
                opt = lookup[cohort,tolerance,regime,2,exact]
                heur = lookup[cohort,tolerance,regime,2,greedy]
                rows.append([source_names[cohort],f'{100*tolerance:.0f}',access,
                             pct(zero['certification']),pct(opt['certification']),
                             pct(heur['certification']),pct(opt['worst_width_fraction']),
                             pct(heur['worst_width_fraction'])])
    design = r'''\subsection{Interval-total recovery sensitivity on frozen traces}
A separate protocol, fixed before its outcomes, evaluates the interval-total
batch solver on the original 34 series and all 3,729 held-out meter-days.
No forecasting model is refitted. The six-hour contiguous gaps, six-hour
blocks, three original mask seeds and all six model pairs are retained.
For each complete reference block total $T$, the supplied interval is
$[(1-\tau)T,(1+\tau)T]$, with $\tau\in\{0,0.01,0.05\}$.
These are constructed sensitivity bands, not calibrated instrument errors
or independent backup measurements.

Both daily access regimes include all exact deductions from retained
totals: an exact singleton residual and every zero-upper-residual block
are revealed without a query. An interval-valued singleton remains unknown.
The saved-archive regime additionally uses every documented persistence
copy in the available test forecasts before making these deductions.
The restricted regime supplies only the isolated daily record and its totals.
The exact batch globally minimizes the worst-width objective. The greedy
batch successively chooses the largest one-step reduction in that same
objective; ties use the smallest target index. A batch receives at
most two exact target answers \emph{per day and model pair}; no answer is
visible during selection, and full-block recovery is permitted.
Freely known or determined values cannot consume the budget.
This eligibility check uses the information available before batch selection.
The experiment does not cancel or refund a later batch request when an
earlier returned answer would make it inferable; it is not an adaptive
early-stopping cost study.
All cases, including already certified comparisons, are retained.
Rates and width summaries average within meters and then equally across
meters in each cohort. Raw widths and widths normalized by squared training
mean energy are supplied alongside paid-query and deduction counts.
'''
    caption = (r'Recovery under constructed total intervals on real traces. '
               r'$\tau$: total half-width (\%). D: isolated daily record with exact deductions; '
               r'A: all saved persistence copies plus exact deductions. '
               r'$C_0$: certification without paid queries; $C_E,C_G$: certification '
               r'after at most two queries per day/pair for exact and greedy batches (\%). '
               r'$W_E,W_G$: remaining worst width as a percentage of initial width, '
               r'computed as a within-meter ratio of sums and then macro-averaged. '
               r'Zero initial width contributes zero to this ratio. '
               r'All observed certificates were correct; repeats are dependent.')
    recovery_table = table(r'Source & $\tau$ & Access & $C_0$ & $C_E$ & $C_G$ & $W_E$ & $W_G$',
                           rows,'lrlrrrrr',caption,'tab:interval-trace-recovery',True)
    p0 = lookup['portugal',0.,restricted,2,exact]
    p5 = lookup['portugal',.05,restricted,2,exact]
    p50 = lookup['portugal',.05,restricted,0,exact]
    a50 = lookup['portugal',.05,archive,0,exact]
    a5 = lookup['portugal',.05,archive,2,exact]
    dr, da = differences['portugal',.05,restricted], differences['portugal',.05,archive]
    checks = report['checks']
    max_endpoint_error = report['integration_checks']['max_lp_absolute_error']
    max_zero_width_difference = max(abs(r['mean_worst_width_difference'])
                                    for r in report['zero_tolerance_reconciliation'])
    results = r'''\FloatBarrier
\subsection{Recovery with interval totals on real traces}
\label{sec:interval-trace-recovery}
Table~\ref{tab:interval-trace-recovery} reports every cohort, access regime
and total-uncertainty setting. Under restricted daily access, widening the
Portugal totals from exact values to $\pm5\%$ lowers two-query certification
from ''' + pct(p0['certification']) + r'''\% to ''' + pct(p5['certification']) + r'''\%.
Recovery still increases certification from ''' + pct(p50['certification']) + r'''\%
at zero queries. With saved-archive access and $\pm5\%$ totals, the change
is smaller: ''' + pct(a50['certification']) + r'''\% to ''' + pct(a5['certification']) + r'''\%.
The exact-minus-greedy certification differences at this setting are
''' + f"{dr['exact_minus_greedy_certification_pp']:.3f}" + r''' and
''' + f"{da['exact_minus_greedy_certification_pp']:.3f}" + r''' percentage points,
respectively. The corresponding reductions in mean realized width,
normalized by squared training mean energy, are
''' + f"{-dr['exact_minus_greedy_normalized_actual_width']:.6f}" + r''' and
''' + f"{-da['exact_minus_greedy_normalized_actual_width']:.6f}" + r'''.
These are observed increments, not approximation guarantees for certification.

''' + recovery_table + r'''
No incorrect certificate, truth-enclosure failure, or realized-width
violation occurred in ''' + f"{checks['policy_budget_evaluations']:,}" + r'''
dependent policy/budget evaluations. Exact worst width never exceeded
greedy worst width in the ''' + f"{checks['exact_worst_width_no_greater_than_greedy']:,}" + r'''
matched cases. At zero total uncertainty,
''' + f"{checks['zero_tolerance_initial_bound_equivalence']:,}" + r''' initial-bound
and optimal-objective comparisons agree with the original exact-total
implementation within the declared numerical tolerance;
all ''' + f"{checks['zero_tolerance_query_comparisons']:,}" + r''' compared query
tuples and their decisions are unchanged. The largest discrepancy in the
reconciled cohort mean worst width is \texttt{''' + f'{max_zero_width_difference:.3g}' + r'''}.
Independent integration fixtures additionally verify
''' + str(report['integration_checks']['independent_lp_endpoint_calls']) + r'''
linear-program endpoints, with maximum absolute discrepancy
\texttt{''' + f'{max_endpoint_error:.3g}' + r'''}; these floating-point checks
do not provide outward-rounded enclosures. Source hashes confirm that the
original archives and implementations are unchanged.
A separate aggregation script reconstructs all meter, cohort and policy
comparison tables from the saved pair/seed summaries; it does not rerun
the raw-trace experiment.
The sensitivity demonstrates behavior under specified total intervals on
real load shapes. It does not estimate physical meter-error distributions,
retrieval cost, response latency, or operational savings.
'''
    return design, results
