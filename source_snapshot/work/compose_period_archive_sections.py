"""Generate the corrected whole-period information model and measured results."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'

DESIGN = r'''\subsection{Archive-consistent whole-period audits}\label{sec:period-information}
The historical audit covers all eligible test days of one meter and one
fixed model pair. Its target is the paired MSE over those same hourly
coordinates, with denominator $N=24d$ for $d$ retained days. The benchmark
snapshot specifies surviving hourly readings, six-hour or daily aggregate
bands, and the permitted saved forecast records. Actual production arrival
times are unavailable; this is a retrospective access rule, not a measured
deadline or latency experiment.

The operative \emph{saved-forecast archive} regime supplies every saved
test forecast row for that meter and all four candidates. For each masked
target at time $t$, an available daily-persistence prediction at $t+24$
provides $y_t$ directly. This includes later forecast rows inside the
evaluation period. The available saved test archive and the within-period
raw forecast vectors coincide in this benchmark; the result uses no
additional outside-period forecasts. Reconstruction reads timestamps and that forecast
column only; hidden reference targets subsequently check the copied value.
Every copy has a source-row trace. Training records used by the profile
and donor baselines remain confined to the original chronological training
period. Unsaved forecasts and feature caches are excluded. The feasible set
does not impose inverse constraints from other fitted predictor mappings,
including the ridge model; all four prediction columns are used for scoring,
but only the documented direct persistence identity is used for reconstruction.

An \emph{isolated-daily summary} reference supplies each daily evaluator
only that day's forecasts, surviving readings and aggregates. The period
aggregator receives scalar comparison endpoints, point-score sums and
counts, not cross-day raw forecast vectors. This deliberately limited
reference is not the information set of an analyst holding the complete
period's raw predictions. Both regimes also deduce a remaining singleton
from an exact residual total and all remaining zeros from a zero upper
residual total. A singleton with a positive-width total interval remains
unknown. The original daily experiments retain their frozen supplied-input
protocol; they are not relabelled as reanalyses with these enlarged observations.

Writing $O_0$ for surviving readings, $R(\mathcal A)$ for verified direct
copies from the permitted archive and $C$ for aggregate-determined values,
the new observed set is $O_{\mathcal A}=O_0\cup R(\mathcal A)\cup C$.
For exact totals the comparison set is
\begin{equation}
 \F_{\mathcal A}=\{y:y_i=o_i\ (i\in O_{\mathcal A}),\quad
 y_i\geq0\ (i\notin O_{\mathcal A}),\quad
 \textstyle\sum_{i\in I_g}y_i=T_g\ \text{for every }g\}.
 \label{eq:archive-set}
\end{equation}
For interval totals, replace the last equality by its declared lower and
upper bounds. Once copies fix coordinates, the remaining blocks are still
disjoint. The whole-period endpoints are therefore sharp \emph{for this
stated augmented product set}. Averaging updated daily endpoints is valid
here because every day has 24 targets; unequal day lengths would require
target-count weighting. This is not a claim of maximal information closure
under inversion of the fitted predictor mappings.

All period comparators receive the same enlarged observed set and retained
totals. Complete-case scoring pools observed paired-loss sums and divides
by the total observed-coordinate count across days. Its magnitude is not
a full-period MSE; only its sign is compared with the full-period reference.
The imputation methods and bounds use the full $24d$ denominator. Exact-total
point methods may abstain at the paired method's scenario-level coverage:
within cohort, gap, mask and aggregate settings, they retain the largest
absolute period contrasts divided by the squared training-period mean
hourly energy, with a fixed identity-based tie rule.
Reference outcomes are consulted only afterwards to count errors. Selection
shortfalls and unfavorable results are retained. This is a descriptive
score-based comparison, not a calibrated confidence procedure.

The reanalysis retains the original 34 meters, all three gap lengths,
three masks, three seeds, both aggregate lengths and three tolerances.
It refits no models. The oracle high-demand mask ranks the original hourly
source values before CSV serialization, preserving the original stable
tie order. This oracle stress does not add inequalities implied by the
mask-generation rule to the evaluator's declared product set.
Compatibility checks preserve the historical
restricted endpoints separately; donor and deletion scores can change after
exact deductions, and deletion additionally changes from a mean of daily
observed scores to pooled observed-coordinate scoring.
These whole-period tables are zero-query audits. Recovery experiments use
at most two readings \emph{per day and per model pair}; they do not solve
an unrestricted two-reading budget over the entire period.
Query eligibility is determined after free closure and before selecting the
nonadaptive batch; no sequential cancellation or refund rule is evaluated.
Period decisions require the stated $10^{-9}\max(1,|D^-|,|D^+|)$
sign margin. Enclosure checks allow $10^{-8}\max(1,|D_{\rm ref}|)$;
non-widening checks allow $10^{-8}$ times the maximum of one and the
absolute restricted endpoints. Exact-deduction values retain their
binary64 subtraction results and are never replaced by hidden truth.
These tolerances diagnose floating-point consistency, not formal
outward-rounded enclosure.
'''


def period_archive_sections(table, pct):
    """Render only completed, hash-checked new comparisons."""
    report = json.loads((OUT/'study_period_archive.json').read_text())
    assert report['status'] == 'passed'
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(OUT/'study_period_archive.py') == report['script_sha256']
    assert sha(ROOT/'work/period_archive_protocol.txt') == report['protocol_sha256']
    assert sha(OUT/'study_period_archive_manifest.json') == report['manifest_sha256']
    for name, expected in {**report['source_hashes'], **report['output_hashes']}.items():
        if (OUT/name).exists():
            assert sha(OUT/name) == expected, name
        elif name == 'study_predictions.csv':
            assert json.loads((ROOT/'work/prediction_archive_omission.json').read_text())['sha256'] == expected
        else:
            public=json.loads((OUT/'study_period_archive_public_manifest.json').read_text())
            assert public['omitted_files'][name]['sha256']==expected, name
            for public_name,record in public['public_files'].items():
                assert sha(OUT/public_name)==record['sha256'], public_name
    def read_csv(name):
        with (OUT/name).open(newline='',encoding='utf-8') as stream:
            return list(csv.DictReader(stream))
    scenarios=read_csv('study_period_archive_scenarios.csv')
    cohort_rows=read_csv('study_period_archive_cohorts.csv')
    matched=read_csv('study_period_archive_matched.csv')
    labels={'portugal':'Portugal','household':'Household','blem_counters':'Counters'}
    regimes=[('restricted_daily_product_closed','D'),('saved_forecast_archive_closed','A')]
    rows=[]
    for cohort in labels:
        for regime, access in regimes:
            for gap in (2,6,12):
                r=next(x for x in scenarios if x['cohort']==cohort and x['regime']==regime
                       and int(x['gap_hours'])==gap and x['pattern']=='contiguous'
                       and int(x['block_hours'])==6 and float(x['total_tolerance'])==0
                       and x['method']=='paired_bounds')
                rows.append([labels[cohort],access,gap,int(r['comparisons']),pct(float(r['coverage'])),
                             int(r['unresolved']),int(r['wrong_decisions']),f"{float(r['mean_normalized_width']):.4f}"])
    main_table=table('Source & Access & Gap & $n$ & Cert. (\\%) & Unres. & Wrong & Width',rows,'llrrrrrr',
        r'Corrected zero-query whole-period paired comparisons with contiguous gaps and exact six-hour totals. '
        r'D: isolated-daily summaries after exact deductions; A: the complete saved test forecast archive '
        r'after direct-copy reconstruction and exact deductions. Each meter contributes six pairs and three seeds. '
        r'$n$: comparisons; Unres.: unresolved comparisons; Wrong: erroneous issued decisions; '
        r'Width: mean interval width divided by squared training mean hourly energy. '
        r'The full mask, aggregate and tolerance grid is supplied in the supplement.', 'tab:period',True)
    methods=['complete_case','uniform','seasonal_profile','historical_donor']
    mrows=[]
    shortfalls=[]
    for cohort in labels:
        for regime,access in regimes:
            groups={m:[x for x in matched if x['cohort']==cohort and x['regime']==regime and x['method']==m]
                    for m in methods}
            base=groups[methods[0]]
            n=sum(int(x['comparisons']) for x in base)
            chosen=sum(int(x['paired_decisions']) for x in base)
            errors=[]
            for method in methods:
                assert sum(int(x['comparisons']) for x in groups[method])==n
                selected=sum(int(x['selected_decisions']) for x in groups[method])
                wrong=sum(int(x['wrong_decisions']) for x in groups[method])
                if selected!=chosen:
                    shortfalls.append(f"{labels[cohort]}, {access}, {method.replace('_',' ')}: "
                                      f"{selected} selected versus {chosen} paired decisions")
                errors.append(f'{100*wrong/selected:.2f}' if selected else '--')
            mrows.append([labels[cohort],access,n,pct(chosen/n),*errors])
    matched_table=table('Source & Access & $n$ & Coverage & Deletion & Uniform & Profile & Donor',mrows,'llrrrrrr',
        r'Whole-period errors among decisions (\%) at scenario-matched paired coverage, over all exact-total '
        r'gap/mask/aggregate settings. Both regimes supply identical information to every method within that regime. '
        r'Coverage is a percentage; the paired method has zero observed errors at the displayed coverage. '
        r'Deletion pools observed-coordinate loss sums and counts after free deductions. '
        r'Public UCI point scores permit inspection of the selected identities; BLEM identities are recovered by the raw-data reproduction path. '
        + (r'No method has a coverage shortfall.' if not shortfalls else
           r'The coverage column is the paired target; actual shortfalls are reported in the text.'), 'tab:matched',True)
    trace=json.loads((OUT/'study_interval_trace_recovery.json').read_text())
    lookup={(x['cohort'],x['tolerance'],x['regime'],x['budget'],x['policy']):x for x in trace['cohort_results']}
    exact,greedy='optimal_minimax_width','greedy_width_reduction'
    arows=[]
    for cohort in labels:
        d0=lookup[cohort,0.,'restricted_record_closed',0,exact]
        a0=lookup[cohort,0.,'saved_forecast_archive_closed',0,exact]
        a2=lookup[cohort,0.,'saved_forecast_archive_closed',2,exact]
        ag=lookup[cohort,0.,'saved_forecast_archive_closed',2,greedy]
        arows.append([labels[cohort],f"{100*(a0['certification']-d0['certification']):.3f}",
                      f"{100*(a2['certification']-a0['certification']):.3f}",
                      f"{100*(a2['certification']-ag['certification']):.3f}",
                      f"{a2['mean_queries']:.3f}",pct(a2['worst_width_fraction']),pct(ag['worst_width_fraction'])])
    attribution=table('Source & Free gain & Paid gain & Exact gain & Queries & $W_E$ & $W_G$',arows,'lrrrrrr',
        r'Attribution for the daily six-hour-gap, exact-six-hour-total experiment, with the same closure rules '
        r'as the period audit. Free gain: archive-aware minus isolated-daily zero-query certification; '
        r'Paid gain: archive-aware exact two-query minus zero-query certification; Exact gain: exact minus greedy '
        r'at the same archive-aware budget. Gains are percentage points. Queries: mean actual readings per '
        r'day/pair; $W_E,W_G$: remaining worst width as percentages of initial archive-aware width '
        r'(within-meter ratios of sums, macro-averaged; zero initial width contributes zero). '
        r'This table reports daily outcomes, not a global period-wide query allocation.', 'tab:recovery-attribution',True)
    checks=report['checks']
    primary={x['method']:x for x in scenarios if x['cohort']=='portugal'
             and x['regime']=='saved_forecast_archive_closed' and int(x['gap_hours'])==6
             and x['pattern']=='contiguous' and int(x['block_hours'])==6
             and float(x['total_tolerance'])==0}
    paired,separate=primary['paired_bounds'],primary['individual_bounds']
    bound_comparison=(r'For Portugal in the primary six-hour-gap archive setting, the paired bound certifies '
        +f"{int(paired['decisions']):,} of {int(paired['comparisons']):,} period comparisons ("
        +pct(float(paired['coverage']))+r'\%), versus '
        +f"{int(separate['decisions']):,} ("+pct(float(separate['coverage']))
        +r'\%) for separate-loss bounds using exactly the same information. '
        +r'This measures the value of preserving shared-target cancellation in the bound, '
        +r'not an improvement caused by paid recovery or by the exact query allocator.'+'\n')
    donor_records={x['cohort']:x for x in cohort_rows if x['regime']=='saved_forecast_archive_closed'
                   and x['method']=='historical_donor' and float(x['total_tolerance'])==0}
    donor_comparison='For historical-donor scoring at its full reported coverage, the archive-aware exact-total grid gives '
    donor_comparison+='; '.join(f"{labels[c]}: {int(donor_records[c]['wrong_decisions'])} errors in "
        f"{int(donor_records[c]['decisions']):,} decisions ({100*float(donor_records[c]['coverage']):.1f}\\% coverage)"
        for c in labels)
    donor_comparison+=r'. These favorable realized results do not provide a guarantee over all feasible completions.'+'\n'
    text=r'''\subsection{Archive-consistent whole-period results}
\label{sec:period-results}
Tables~\ref{tab:period} and~\ref{tab:matched} use the explicit information
sets of Section~\ref{sec:period-information}. In the archive regime,
every permitted direct persistence copy is incorporated before any bound,
imputation or observed-only score is calculated. The daily-summary regime
is a limited-input reference. It is not presented as an archive-wide
analysis with reconstructable targets left unknown.
'''+main_table+bound_comparison+matched_table+(r'Coverage shortfalls: '+('; '.join(shortfalls))+'.\n' if shortfalls else '')+r'''
The comparison archive contains '''+f"{report['period_case_rows']:,}"+r'''
method-specific period rows. All issued paired certificates were correct,
all reference differences were enclosed, and adding verified archive
information never widened the paired interval. The compatibility audit
reconciles '''+f"{report['reconciliation']['interval_rows_reconciled']:,}"+r'''
restricted paired/separate interval rows with the original analysis.
The new deletion and donor results use their enlarged observed sets;
their differences from historical outputs are separately documented rather
than attributed to new forecasts or new consumers.
'''+donor_comparison+r'''
Zero observed errors from an imputation method at matched coverage remain
evidence in its favor on this panel. The paired guarantee instead concerns
every completion in the declared feasible set; the experiment does not
establish general empirical error-rate dominance over selective imputation.
The source traces, scenario-to-state links, residual constraints, query
eligibility and per-state scalar contributions support reconstruction of
the revised period results. The distributed detailed cases and traces
cover the UCI cohorts. Full BLEM daily traces and archive-aware case
endpoints can reveal original readings and are therefore retained locally,
with their hashes and no-refit raw-data regeneration supplied instead.
BLEM cohort/scenario summaries remain reported. The clean-package checker
states its reduced detailed-trace scope; the full local checker covers
all 34 series.

Table~\ref{tab:recovery-attribution} separates three mechanisms. Archive
reconstruction uses information already supplied. Paid recovery obtains
additional readings. Exact-versus-greedy differences concern allocation of
the same budget after identical free information. The largest certification
change is not attributed to the optimizer. Remaining worst width is
reported because that is the objective the algorithm actually minimizes.
'''+attribution
    return DESIGN, text, report
