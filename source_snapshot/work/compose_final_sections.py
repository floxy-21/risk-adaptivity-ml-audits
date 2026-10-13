"""Assemble the measured-result sections of the one manuscript."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'

DATA_METHODS=r'''\subsection{Data sources and chronological splits}
The primary evaluation uses 34 consumption series from three public sources
(Table~\ref{tab:data}). The Portugal panel uses the first 30 eligible meter
IDs in the ordered UCI ElectricityLoadDiagrams20112014 file \cite{portugal}.
Eligibility requires at least 99\% finite and more than 95\% positive
training-hour values. The training year is 2013; test windows are the first
28 days of January, April, July, and October 2014. The original end-stamped
15-minute average-kW readings are shifted to interval starts and converted
to hourly energy by summing four values and dividing by four.

The UCI French household trace \cite{uci} supplies a separate scale and
load pattern. Training uses 2008--2009 and testing uses eligible days in
2010. Hourly kWh is the sum of 60 minute-average kW values divided by 60;
all 60 readings must be valid. For both UCI sources, the spring and autumn
clock-transition dates and target days whose 1-, 2-, or 7-day lags touch
them are excluded in training and testing. This prevents documented local
time-grid artifacts from contaminating the features. Every eligible day
must contain all 24 targets and all required causal features. The retained
totals in these two sources are constructed from the complete trace before
masking; they are not separate backup-register measurements.

The third source contains actual cumulative Discovergy consumption counters
released with the BLEM study \cite{blem}. We use the first three consumer
IDs in the pinned source version identified in the supplement. Each raw
series contains 175,201 readings on an uninterrupted three-minute grid,
without counter decreases. Hourly energy is calculated from integer
counter differences at exact UTC hour endpoints, using the source's
$10^{-10}$ conversion to kWh. Training uses January--September 2017 and
testing uses October--December 2017, subject to complete-day and feature
availability. First and last partial days are excluded. Here the retained
six-hour or daily totals can be obtained directly from the recorded
counter endpoints. Removing interval targets is still an artificial outage:
the experiment assumes these endpoints remain available and does not
measure an independent communication channel's survival rate.

\begin{table}[t]
\centering\normalsize
\caption{Data retained after feature and quality filters. Training and
test counts are days per series; totals are test meter-days.}
\label{tab:data}
\begin{tabular}{lrrrr}
\toprule
Source & Meters & Train & Test & Total\\
\midrule
Portugal & 30 & 357 & 107 & 3,210\\
French household & 1 & 587 & 246 & 246\\
Counter meters & 3 & 266 & 91 & 273\\
\bottomrule
\end{tabular}
\end{table}

The study contains 3,729 test meter-days. A dated local protocol records
the design and amendments for counter data, daylight-saving handling,
information-flow checks, and whole-period comparisons. This is not a
registered study. The household trace was used during implementation
development and is reported separately. After inspecting an earlier
four-model analysis, we replaced weekly persistence with an MLP in a
dated expansion of the candidate model set. An initial neural run exposed training-iteration-limit
warnings; a documented amendment increased the training allowance based
on those training diagnostics, retaining the architecture and all other
hyperparameters. The final configuration was checked for training convergence
before the final evaluation run. The retained split therefore is not a new blind
validation panel. No hyperparameters were selected using the revised
evaluation outcomes. All reported empirical values come from the revised
run; the earlier results are not mixed with it. The underlying records
remain historical (2010--2017), rather than newly collected 2026 loads.
'''

BLEM_REFERENCE=r'''\bibitem{blem} M. Kostmann and W. K. H\"ardle,
``Forecasting in blockchain-based local energy markets,''
\emph{Energies}, vol.~12, art.~2718, 2019.
\url{https://doi.org/10.3390/en12142718}.
Source data: \url{https://github.com/QuantLet/BLEM}.'''

RECOVERY_METHOD=r'''A comparison that remains unresolved can guide data repair.
Suppose an operator can retrieve at most $B$ missing interval-energy values
from a meter buffer or a secondary archive. Each recovered target has unit
cost. The policy chooses one batch before seeing any of the requested
values. The budget represents a limit on records retrieved and validated;
equal record cost is an explicit abstraction, not a measured staffing or
communication cost. The budget counts recovered targets, not network packets or
cumulative-register endpoint requests. This extension applies when such
retrieval is operationally possible; it does not recover permanently lost
information without an additional measurement source. The budget and
optimality statement apply to one specified model pair. Different pairs
can request different values; a joint recovery plan for all candidates
would require a different multi-objective optimization.

\subsection{An exact objective before reading recovery}
For an exact-total block let $Q_g\subset\M_g$ be the queried indices and
$S_g=\M_g\setminus Q_g$ the remaining missing indices. If $S_g$ is nonempty,
the comparison-width contribution after observing the query answers is
\begin{equation}
 W_g(Q_g,y)=\left(E_g-\sum_{i\in Q_g}y_i\right)
 \left(\max_{i\in S_g}c_i-\min_{i\in S_g}c_i\right).
 \label{eq:querywidth}
\end{equation}
The constant term of the comparison changes too, but does not affect its
width. The worst possible width over the currently feasible targets is
\begin{equation}
 H_g(Q_g)=E_g\left(\max_{i\in S_g}c_i-\min_{i\in S_g}c_i\right),
 \label{eq:worstquery}
\end{equation}
because the queried values can all be zero while the remaining coordinates
carry the full residual energy. A singleton $S_g$ has zero range. Thus the
last missing target need not be queried: its exact total already determines
it after the other missing values are recovered. Zero-energy blocks also
need no recovery.

\begin{proposition}[Optimal batch recovery within a block]
Sort the $m_g$ missing-target coefficients as
$c_{g,(1)}\leq\cdots\leq c_{g,(m_g)}$. For $0\leq k\leq m_g-1$, the
smallest worst-case width obtainable by recovering $k$ values is
\begin{equation}
 h_g(k)=E_g\min_{1\leq s\leq k+1}
 \{c_{g,(s+m_g-k-1)}-c_{g,(s)}\}.
 \label{eq:window}
\end{equation}
An attaining batch queries the coordinates outside a minimizing consecutive
window of $m_g-k$ sorted coefficients.
\end{proposition}
\begin{proof}
Equation~\eqref{eq:worstquery} reduces the problem to retaining $m_g-k$
coefficients with minimum range. Any such subset spans at least $m_g-k$
ordered entries. A consecutive window of that size within its span has no
larger range. Conversely each consecutive window is a feasible retained
subset. Minimizing over the $k+1$ possible windows proves the formula;
the zero-query-energy completion attains its worst-case width.
\end{proof}

\subsection{Allocation across retained-total blocks}
Disjoint blocks permit simultaneous attainment of their worst cases.
For allocation, index only blocks with $m_g\geq2$ and $E_g>0$ by
$g=1,\ldots,G$; all other blocks have zero width and require no query.
Consequently the global problem is
\begin{equation}
 \min_{\substack{k_g\in\{0,\ldots,m_g-1\}\\\sum_g k_g\leq B}}
 \sum_g h_g(k_g),
 \label{eq:allocation}
\end{equation}
with empty and already determined blocks assigned zero cost and no queries.
Dynamic programming gives an exact solution. If $V(g,b)$ is the minimum
cost for the first $g$ blocks using exactly $b$ recoveries, then
\begin{equation}
 V(g,b)=\min_{0\leq k\leq\min(b,m_g-1)}
 \{V(g-1,b-k)+h_g(k)\}.
\end{equation}
Initialize $V(0,0)=0$, other states to infinity, and select the smallest
$V(G,b)$ over $b\leq B$. Store the minimizing window and allocation to
return actual interval indices. Coefficient ties and equal-cost allocations
use deterministic index-based rules. The algorithm uses only archived
forecasts, surviving values, and retained totals before requesting the batch.

An implementation has four steps: remove determined blocks; sort each
remaining block's coefficients while retaining their interval indices;
enumerate the minimum-range window at every feasible local budget and
apply the allocation recurrence; then recover the selected indices and
map them to record timestamps. Put $q=\min(B,\sum_g(m_g-1))$ and
$K_g=\min(q,m_g-1)$. Sorting costs
$O(\sum_g m_g\log m_g)$; enumerating the scalar window costs requires
$O(\sum_g(K_g+1)^2)$ operations. The allocation recurrence has at most
$O(G(q+1)^2)$ transitions. A backpointer implementation needs $O(q+1)$
rolling scalar states and $O(G(q+1))$ backpointer storage, in addition to
the sorted inputs and local window choices. The released readable Python
prototype instead copies and sorts query-index tuples at each transition,
adding up to $O(q\log(q+1))$ work per transition and $O((q+1)^2)$
auxiliary tuple storage. The reported timings include this bookkeeping;
they do not describe a backpointer-only implementation.

\begin{proposition}[A limitation of one-step greedy recovery]
For the greedy batch rule that repeatedly chooses the coordinate giving
the largest immediate decrease in worst-case width, no positive universal
approximation factor for width reduction holds, even with one block and
two queries. The ratio of its remaining width to the optimal remaining
width is unbounded, including instances with a strictly positive optimum.
\end{proposition}
\begin{proof}
Take one block of residual energy $E=3$, budget two, and coefficients
$(0,\varepsilon/2,\varepsilon,1,1)$, where $0<\varepsilon<1/2$.
Greedy uniquely removes the first coefficient and then the second,
leaving worst-case width $3(1-\varepsilon)$. The minimum-range
three-element window is $(0,\varepsilon/2,\varepsilon)$, so the exact
rule removes the two unit coefficients and leaves width $3\varepsilon$.
The ratio of width reductions is
$\varepsilon/(1-\varepsilon)\to0$, whereas the ratio of remaining
widths is $(1-\varepsilon)/\varepsilon\to\infty$.
\end{proof}
These coefficients are realized by nonnegative five-target forecasts
$a_i=0$ and $b_i=5c_i/2$. Their initial comparison interval contains
zero: its endpoints are $K=-5/2-25\varepsilon^2/16$ and $K+3$.
Independent enumeration of every subset of at most two queries verifies
the executable examples. This is an analytical limitation of the width
heuristic; it does not assert frequent greedy failure or an approximation
claim for empirical certification rates.

For an analytical example, a block with $E=6$ and coefficients
$(0,1,2,10)$ initially has width 60. One query at the coefficient 10
guarantees remaining width at most 12, regardless of the answer returned.
This illustrates the objective; it is not a measured
experiment or an assertion that typical loads have this shape.

The optimality statement concerns \emph{worst-case interval width} for
nonadaptive batches, exact totals, nonnegative uncapped targets, and equal
query costs. It does not optimize realized width, the probability of
certification, or the number of correct empirical decisions. An alternative
batch can perform better at the realized load profile. Optimizing average behavior under a stochastic load model would require
an explicitly specified target distribution.
Section~\ref{sec:interval-recovery} gives a separate batch extension for
independently bounded totals. Unequal query costs and capacity constraints
remain outside the implemented recovery rules.
Optimal batches for different budgets need not be nested. Their optimal
worst-case widths cannot increase with budget, but their realized widths
or resolution rates need not be monotone across independently chosen batches.

\subsection{Deterministic adaptivity cannot improve this minimax width}
Adaptive and fixed information have a substantial optimal-recovery
literature \cite{osipenko}. Classical sufficient conditions involving
central symmetry do not directly apply to a positive-energy simplex with
more than two coordinates. The proof below instead uses a feasible
zero-answer transcript for the restricted coordinate-query geometry.
The following statement uses the specific
nonnegative exact-sum geometry and a hard query budget.
\begin{corollary}[Deterministic adaptive recovery]
Under the assumptions above, let $W^*(B)$ be the optimal value in
\eqref{eq:allocation}. Among all deterministic policies that select each
next query using the answers already observed and request at most $B$
values for every feasible record, the smallest worst-case terminal
comparison width is exactly $W^*(B)$.
\end{corollary}
\begin{proof}
A query whose answer is already determined---a zero-residual block or its
last missing coordinate---can be omitted and its answer simulated in the
policy's history. This preserves its terminal information while using no
more queries. For the resulting nonredundant policy, answer zero to each
query. The transcript is feasible: each positive-energy block retains at
least one unqueried coordinate, to which its remaining energy can be
assigned at termination. Let $Q_0$ be the queried set on this transcript.
Its terminal width is $\sum_g E_g\operatorname{range}(c_{\M_g\setminus Q_0})$,
which is at least $W^*(B)$ because $|Q_0|\leq B$. A completion assigning
the residual energies to unqueried coordinates realizes this transcript.
Every deterministic adaptive policy consequently has worst-case width
at least $W^*(B)$. The optimal fixed batch is itself a deterministic policy,
giving the reverse inequality.
\end{proof}
This does not rule out gains in average width, empirical resolution, or
randomized expected-minimax criteria. For example, with $E=1$,
$c=(0,1,2,3)$ and $B=2$, deterministic minimax width is 1. Querying either
the first two or last two coordinates with equal probability gives expected
width $\tfrac12[(y_3+y_4)+(y_1+y_2)]=\tfrac12$ for every feasible record.
Thus the deterministic qualifier and the order of expectation and worst-case
optimization are essential.
'''

RECOVERY_RELATED=r'''Active evaluation already studies which labels to acquire for assessing
fixed predictors. Sawade et al.\ \cite{sawade} directly address paired model
comparison, including squared-loss regression, by choosing an importance
sampling distribution to improve asymptotic test power. Hara et al.\
\cite{hara} develop adaptive acquisition aimed at reducing the variance of
estimated test-loss differences. These works establish budgeted acquisition
for model comparison; our contribution concerns a different objective:
the worst remaining range of a fixed-record loss difference under retained
energy constraints.

Related active testing and worst-case sensor selection address model
evaluation and measurement choice more broadly \cite{active,sensorsel}.
Costly observation within robust optimization is also established.
Vayanos et al.\ \cite{ddid} formulate decision-dependent information
discovery and develop tractable approximations for multistage problems.
Our recovery rule specializes this general setting to a scalar contrast
over nonnegative interval values with disjoint exact sums. This structure
permits an exact sorted-window calculation and budget-allocation dynamic
program.'''

RECOVERY_REFERENCES=r'''\bibitem{active} J. Kossen, S. Farquhar, Y. Gal, and
T. Rainforth, ``Active testing: Sample-efficient model evaluation,''
\emph{Proceedings of Machine Learning Research}, vol.~139,
pp.~5753--5763, 2021.
\url{https://proceedings.mlr.press/v139/kossen21a.html}.
\bibitem{sensorsel} Y. Wang, M. Sznaier, and F. Dabbene,
``A convex optimization approach to worst-case optimal sensor selection,''
in \emph{Proceedings of the 52nd IEEE Conference on Decision and Control},
pp.~6353--6358, 2013.
\url{https://robustsystems.coe.neu.edu/sites/robustsystems.coe.neu.edu/files/systems/papers/Yin_CDC13.pdf}.
\bibitem{sawade} C. Sawade, N. Landwehr, and T. Scheffer,
``Active comparison of prediction models,''
\emph{Advances in Neural Information Processing Systems}, vol.~25, 2012.
\url{https://proceedings.neurips.cc/paper_files/paper/2012/file/92fb0c6d1758261f10d052e6e2c1123c-Paper.pdf}.

\bibitem{hara} S. Hara, M. Matsuura, J. Honda, and S. Ito,
``Active model selection: A variance minimization approach,''
\emph{Machine Learning}, vol.~113, pp.~8327--8345, 2024.
\url{https://doi.org/10.1007/s10994-024-06603-1}.

\bibitem{ddid} P. Vayanos, A. Georghiou, and H. Yu,
``Robust optimization with decision-dependent information discovery,''
\emph{Management Science}, vol.~72, no.~2, pp.~1509--1528, 2026
(published online June 2025).
\url{https://doi.org/10.1287/mnsc.2021.00160}.

\bibitem{osipenko} K. Yu. Osipenko,
``Generalized adaptive versus nonadaptive recovery from noisy information,''
\emph{Journal of Complexity}, vol.~53, pp.~162--172, 2019.
\url{https://doi.org/10.1016/j.jco.2018.12.001}.

\bibitem{aemo} Australian Energy Market Operator,
``Metrology procedure: Part B---Metering data validation, substitution
and estimation,'' version~8.13, effective June~9, 2026,
secs.~2.4--2.5 and 3.2.
\url{https://www.aemo.com.au/-/media/files/electricity/nem/retail_and_metering/market_settlement_and_transfer_solutions/2026/metrology-procedure-part-b-v813-clean.pdf}.'''


def pct(x):
    return '--' if x is None else f'{100*x:.1f}'


def table(header,rows,columns,caption,label,wide=False):
    kind='table*' if wide else 'table'
    lines=[f'\\begin{{{kind}}}[htbp]',r'\centering\normalsize\setlength{\tabcolsep}{4pt}',
           '\\caption{'+caption+'}', '\\label{'+label+'}',
           '\\begin{tabular}{'+columns+'}',r'\toprule',header+r'\\',r'\midrule']
    lines += [' & '.join(map(str,row))+r'\\' for row in rows]
    lines += [r'\bottomrule',r'\end{tabular}','\\end{'+kind+'}']
    return '\n'.join(lines)+'\n'


def main_sections(t,s,mc,rt):
    cohorts=['portugal','household','blem_counters']
    names={'portugal':'Portugal','household':'Household','blem_counters':'Counters'}
    # Values are generated from archived comparisons; no manually entered table data.
    daily=table('Source & Gap & Total & Paired & Separate & Deletion & Uniform & Profile & Donor',
        [[names[r['cohort']],r['gap'],r['block'],pct(r['paired_bounds_resolved']),pct(r['individual_bounds_resolved']),
          *[pct(r[m+'_error']) for m in ('complete_case','uniform','seasonal_profile','historical_donor')]] for r in t['daily']],
        'lrrrrrrrr',
        r'Daily comparison results for contiguous gaps and exact totals. Gap and total are hours. '
        r'Paired and Separate columns give resolved comparisons (\%); the four point-method columns give errors '
        r'among decisions (\%). Both bounding methods made zero incorrect decisions. Point methods make '
        r'nearly all decisions; their higher coverage must be considered when comparing errors. '
        r'Rates are macro-averaged over meters. Unresolved fraction is 100 minus resolved percentage.', 'tab:daily',True)
    sensitivity=[]
    for co in cohorts:
        for pattern in ('contiguous','scattered','high_demand'):
            z={r['total_tolerance']:r for r in t['sensitivity'] if r['cohort']==co and r['pattern']==pattern}
            sensitivity.append([names[co],{'contiguous':'Contiguous','scattered':'Scattered','high_demand':'High demand'}[pattern],
                                *[pct(z[tau]['resolved']) for tau in (0,.01,.05)]])
    sensitivity=table(r'Source & Mask & Exact & $1\%$ & $5\%$',sensitivity,'llrrr',
        r'Daily paired resolution (\%) with six missing targets and six-hour totals. High demand is an oracle '
        r'stress mask. Every issued decision remained correct.', 'tab:sensitivity')
    regret=[]
    for co in cohorts:
        for method,name in [('complete_case','Deletion'),('uniform','Uniform'),('seasonal_profile','Profile'),('historical_donor','Donor'),('minimax_regret','Minimax regret')]:
            r=next(r for r in t['selection'] if r['cohort']==co and r['selector']==method)
            regret.append([names[co],name,f"{1000*r['mean_regret']:.3f}",f"{1000*r['p95_regret']:.3f}",f"{1000*r['worst_bound']:.3f}"])
    regret=table('Source & Selector & Mean actual & Tail actual & Mean bound',regret,'llrrr',
        r'Selection tradeoff for contiguous six-target gaps and exact six-hour totals. '
        r'Entries are $10^3$ times normalized realized regret and worst-case regret bound. '
        r'Tail actual is the mean of individual meters\textquotesingle\ 95th-percentile regrets, '
        r'not a pooled percentile. Every realized regret was within its corresponding '
        r'bound. Minimax reduces the worst-case criterion but does not minimize observed regret.', 'tab:regret',True)
    gain=t['portugal_direct_resolution_gain']['6']
    epochs=[m['mlp_training']['epochs'] for m in s['meters']]
    warned=sum(bool(m['mlp_training']['warnings']) for m in s['meters'])
    fit_text=(r'The neural fits used '+str(min(epochs))+'--'+str(max(epochs))+r''' epochs.
''')
    if warned:
        fit_text+=str(warned)+r''' of the 34 fits reported a convergence
warning at the fixed iteration limit; these results are retained.
'''
    else:
        fit_text+=r'''All 34 fits met the training-loss convergence criterion
before the fixed iteration cap, with no convergence warnings. Per-meter
iterations, training objectives, and fit times are archived.
'''
    mse=table('Source & Daily & Ridge & Boosting & Neural MLP',
        [[names[r['cohort']],*[f"{r[m]:.4f}" for m in s['design']['models']]] for r in t['normalized_forecast_mse']],
        'lrrrr',r'Complete-reference MSE divided by squared training mean hourly energy, then averaged over meters. '
        r'These fixed forecasts define the audited comparisons.', 'tab:forecasts')
    assert s['design']['models']==['daily','ridge','hist_gradient_boosting','mlp']
    def row(co,gap,block=6):
        return next(x for x in t['daily'] if x['cohort']==co and x['gap']==gap and x['block']==block)
    def series(gap,key,block=6):
        return ', '.join(pct(row(co,gap,block)[key])+r'\%' for co in cohorts)
    pair_count=sum(v['paired_bounds']['n'] for c in s['cohorts'].values() for v in c['comparison'].values())
    daily_count=sum(v['paired_bounds']['decisions'] for c in s['cohorts'].values() for v in c['comparison'].values())
    period_count=sum(v['paired_bounds']['decisions'] for c in s['cohorts'].values() for v in c['period_comparison'].values())
    for c in s['cohorts'].values():
        for section in ['comparison','period_comparison']:
            assert all(v['paired_bounds']['wrong']==0 for v in c[section].values())
    gain=t['portugal_direct_resolution_gain']['6']
    result=r'''\subsection{AI forecasters and completed evaluation}
All 34 series completed the revised forecast and verification pipeline.
The evaluated candidate set replaces the earlier weekly-persistence model with a
trained MLP; every reported table uses the resulting four-model set.
Table~\ref{tab:forecasts} reports complete-reference prediction quality.
These scores describe the fixed models being audited, not an improvement
caused by the audit itself. The design contains '''+f'{pair_count//6:,}'+r'''
day--mask--aggregate--tolerance scenarios and '''+f'{pair_count:,}'+r'''
pair comparisons, including dependent pairs and repeated masks.
The paired method issued '''+f'{daily_count:,}'+r''' daily and
'''+f'{period_count:,}'+r''' historical isolated-daily-product period certificates with no incorrect
certified decisions. Every calculated paired interval enclosed the
complete-reference difference. This verifies consistency under feasible
measurement constraints; the useful empirical outcome is the fraction of
comparisons for which a strict ordering can be established.
'''+mse+fit_text+r'''
\subsection{Daily decisions and the value of pairing}
For two missing hours and exact six-hour totals, paired resolution was
'''+series(2,'paired_bounds_resolved')+r''' for Portugal, the household,
and the counter cohort, respectively; separate individual-error bounds
resolved '''+series(2,'individual_bounds_resolved')+r'''. At six missing
hours the corresponding paired rates were '''+series(6,'paired_bounds_resolved')+r''',
versus '''+series(6,'individual_bounds_resolved')+r''' for separate bounds.
The Portugal six-hour-gap gain was '''+f"{100*gain['improvement']:.1f}"+r'''
percentage points (descriptive whole-meter bootstrap 95\% interval:
'''+f"{100*gain['ci95'][0]:.1f}--{100*gain['ci95'][1]:.1f}"+r''').
Both methods receive identical measurements. Their difference therefore
isolates the benefit of comparing against the shared unknown target.

The profile imputer made daily ordering errors of
'''+series(6,'seasonal_profile_error')+r''' in that setting, while deciding
'''+series(6,'seasonal_profile_resolved')+r''' of comparisons.
Certified decisions trade coverage for a conditional all-completions
guarantee; these figures alone do not establish error-rate superiority
at equal coverage. With twelve missing hours and only a daily total,
paired resolution fell to '''+series(12,'paired_bounds_resolved',24)+r'''.
The complete contiguous-gap grid is retained in Table~\ref{tab:daily}.
'''+daily+r'''
'''
    from compose_period_archive_sections import period_archive_sections
    _, period_results, _ = period_archive_sections(table, pct)
    result += period_results
    result+=r'''
\subsection{Total uncertainty and selective missingness}
Table~\ref{tab:sensitivity} retains every mask mechanism and total-error
setting for six missing targets and six-hour totals. Widening total
uncertainty enlarges the feasible set and cannot improve the mathematical
certificate. The contiguous, scattered, and highest-demand masks test
different locations of missing energy and forecast disagreement. The
highest-demand mask is an oracle stress condition, not a learned or
prospective outage predictor.
'''+sensitivity+r'''
\subsection{Numerical verification and execution cost}
The revised reference, integration, recovery, and malformed-input tests
passed. The study additionally passed '''+f"{s['reference_crosschecks_passed']:,}"+r'''
random study/reference cross-checks. Independent LP/QP audits and an
exhaustive adaptive-query oracle provide checks beyond the implementation's
own formulas. Their reports and source hashes accompany the manuscript.
'''
    audit=json.loads((OUT/'study_independent_audit.json').read_text())
    adapt=json.loads((OUT/'test_recovery_adaptivity.json').read_text())
    def sci(x):
        mant,exp=f'{x:.2e}'.split('e')
        return mant+r'\times10^{'+str(int(exp))+'}'
    result+=r'The largest absolute LP discrepancy was $'+sci(audit['max_lp_absolute_error'])+r'''$
across '''+str(audit['paired_lp_solves'])+r''' extrema; the corresponding
individual-error minimum discrepancy was $'''+sci(audit['max_projection_absolute_error'])+r'''$
across '''+str(audit['individual_qp_solves'])+r''' constrained optimizations.
The adaptive oracle checked 5,952 finite small cases, including determined
last-coordinate queries and excess budgets, with exact agreement between
adaptive, exhaustive fixed-batch, and sorted-window optima.

On an Intel Core i7-8565U CPU with 15.75 GiB RAM, the revised main
pipeline took '''+f"{s['wall_seconds']:.1f}"+r''' s using two computation
threads and no GPU. Prepared-input timing used 30 feasible cases at each
length, five warmups, and three repetitions. The validated reference API
returned both extrema and witnesses in median '''+f"{rt['lengths']['24']['methods']['reference']['median_ms']:.3f}"+r''' ms for
24 targets and '''+f"{rt['lengths']['168']['methods']['reference']['median_ms']:.3f}"+r''' ms for 168 targets.
Two SciPy HiGHS calls on prepared matrices took
'''+f"{rt['lengths']['24']['methods']['highs_two_solves']['median_ms']:.3f}"+r''' and
'''+f"{rt['lengths']['168']['methods']['highs_two_solves']['median_ms']:.3f}"+r''' ms, respectively.
These measurements include solver-call overhead and exclude fitting and
file processing. They describe one host under uncontrolled concurrent
activity; no end-to-end forecasting speedup is inferred.
'''
    regret_result=r'''\subsection{Observed selection tradeoff}
Table~\ref{tab:regret} retains realized regret and the exact worst-case
criterion for every evaluated selector in the six-hour-gap/six-hour-total
setting. A small worst-case bound is a different objective from a small
regret at the actual reference completion. This extension should be used
only when that conservative criterion is relevant; it does not establish
that minimax selection improves average prediction accuracy.
'''+regret
    return result,regret_result


RECOVERY_DESIGN=r'''\subsection{Recovery experiment}
A recovery experiment was added after inspecting the original verification
analysis. For the evaluation including the MLP, a new dated protocol fixed six
acquisition policies and a separate summary of the three MLP-involving
model pairs before revised outcomes were calculated. The experiment reuses
the newly fitted forecasts of all 34 series; it does not fit models on
recovered targets or tune their parameters.
This extension uses contiguous gaps of six and twelve hours, exact six-hour
totals, all three main-study mask seeds, and budgets of zero through three
recovered targets per model pair. It is a same-panel extension rather than
external validation.

The optimal batch rule is compared with seeded random recovery, recovery
of the largest absolute contrast coefficients, and greedy selection of the
next target yielding the largest immediate worst-case width reduction.
Two further policies sample with weights proportional to $|a_i-b_i|$ or
$(a_i-b_i)^2$, inspired by the prediction-only limiting distributions of
Sawade et al.\ \cite{sawade}. We adapt these weights to sampling without
replacement among eligible missing records, then apply the same retained-total
certificate. These are acquisition-policy adaptations, not reproductions
of the original importance-weighted risk estimator or Wald test.
All avoid querying the final missing value in a block, which its total
already determines. Selection uses only evaluator-visible information;
the complete batch is fixed before withheld values are revealed.
The budgets are applied to the same full set of comparisons, including
comparisons already resolved without recovery. This experiment measures
width refinement and final resolution, not the minimum retrieval cost to
establish a winner or an early-stopping repair policy.

We report final resolution, actual queries used, realized remaining width,
and the worst possible post-recovery width. A width fraction is the sum of
remaining widths divided by the sum of initial widths within a meter,
then averaged over meters. The optimization guarantee concerns the
worst-case width; realized width and resolution are evaluated separately.
Pre-execution tests include exhaustive query-subset comparison on 120
small multiblock problems at four budgets, 100 generic-bound checks,
information invariance, zero-energy/tie cases, and two greedy counterexamples.
Post-run checks verify source hashes and exact agreement of zero-budget
counts with the corresponding main-study settings.
'''


def recovery_sections(r):
    cohorts=['portugal','household','blem_counters']
    names={'portugal':'Portugal','household':'Household','blem_counters':'Counters'}
    ps=['optimal_minimax_width','greedy_width_reduction','random','largest_absolute_contrast',
        'contrast_weighted_sampling','squared_contrast_weighted_sampling']
    allr={(co,x['gap_hours'],x['budget'],x['policy']):x for co in cohorts for x in r['cohorts'][co]}
    def get(co,gap,budget,policy=ps[0]):
        return allr[co,gap,budget,policy]
    rows=[]
    for co in cohorts:
        for gap in (6,12):
            for b in (0,1,2,3):
                z=[get(co,gap,b,p) for p in ps]
                rows.append([names[co],gap,b,*[pct(x['resolved_fraction']) for x in z]])
    tab=table(r'Source & Gap & Budget & Optimal & Greedy & Random & Max. $|c|$ & Wt. $|c|$ & Wt. $c^2$',
        rows,'lrrrrrrrr',
        r'Completed recovery experiment: exact six-hour totals, three mask seeds, pair-specific batch queries. '
        r'All six policy columns are final resolution (\%), macro-averaged over meters. Wt.: weighted '
        r'sampling without replacement, using prediction-only contrast weights inspired by active comparison. '
        r'Every certificate was correct. Optimal refers to worst-case width, not a guarantee of maximum '
        r'empirical resolution. All policies use at most the listed number of recovered targets.', 'tab:recovery',True)
    starts=[pct(get(co,6,0)['resolved_fraction']) for co in cohorts]
    ends=[pct(get(co,6,2)['resolved_fraction']) for co in cohorts]
    wc=[pct(get(co,6,2)['worst_case_width_fraction']) for co in cohorts]
    gc=[pct(get(co,6,2,ps[1])['worst_case_width_fraction']) for co in cohorts]
    greedy=[pct(get(co,6,2,ps[1])['resolved_fraction']) for co in cohorts]
    random=[pct(get(co,6,2,ps[2])['resolved_fraction']) for co in cohorts]
    widthrows=[[names[co],gap,*[pct(get(co,gap,2,p)['worst_case_width_fraction']) for p in ps]] for co in cohorts for gap in (6,12)]
    widthtab=table(r'Source & Gap & Optimal & Greedy & Random & Max. $|c|$ & Wt. $|c|$ & Wt. $c^2$',
        widthrows,'lrrrrrrr',r'Remaining worst-case width (\% of initial width) with budget two. '
        r'Within each meter, total remaining width is divided by total initial width; ratios are then '
        r'macro-averaged. This is the objective optimized by the proposed recovery rule.', 'tab:width',True)
    losses=[]
    for co in cohorts:
        for gap in (6,12):
            for b in (1,2,3):
                best=max((get(co,gap,b,p)['resolved_fraction'],p) for p in ps[1:])
                opt=get(co,gap,b)['resolved_fraction']
                if best[0]>opt+1e-12:
                    losses.append((best[0]-opt,co,gap,b,best[1],opt,best[0]))
    result=r'''\subsection{Budgeted recovery of measured values}
Table~\ref{tab:recovery} reports the complete recovery grid. For six-hour
gaps, allowing two selected readings per pair raised paired resolution
from '''+r'\%, '.join(starts[:-1])+r'\%, and '+starts[-1]+r'''\% to
'''+r'\%, '.join(ends[:-1])+r'\%, and '+ends[-1]+r'''\% for Portugal,
the household, and the counter cohort, respectively. The recovered values
are actual withheld readings; no synthetic completion is substituted for
them. All newly certified decisions remained correct.

The optimal rule left '''+r'\%, '.join(wc[:-1])+r'\%, and '+wc[-1]+r'''\% of
the initial worst-case width at that budget, compared with
'''+r'\%, '.join(gc[:-1])+r'\%, and '+gc[-1]+r'''\% for greedy width
reduction. The implementation checked on every comparison that the
optimal batch's worst-case width was no larger than each baseline's and
that the realized post-recovery width was within its predicted bound.
These are the optimized criterion and its direct numerical verification.
Table~\ref{tab:width} reports the width comparison across gap sizes;
Figure~\ref{fig:recovery} displays coverage and worst-case width across budgets.
'''+tab+widthtab+r'''
At the same two-query budget, random recovery resolved
'''+r'\%, '.join(random[:-1])+r'\%, and '+random[-1]+r'''\%, while greedy
width reduction resolved '''+r'\%, '.join(greedy[:-1])+r'\%, and '+greedy[-1]+r'''\%.
The gains over no recovery and the differences between recovery policies
answer distinct questions. The former measures the value of additional
readings; the latter measures how efficiently the budget is allocated.
The optimized quantity is worst-case width, while empirical resolution
also depends on the location of the interval relative to zero.
'''
    if losses:
        diff,co,gap,b,pol,opt,best=max(losses)
        label={'greedy_width_reduction':'greedy width reduction','random':'random recovery',
               'largest_absolute_contrast':'largest-absolute-contrast recovery',
               'contrast_weighted_sampling':'absolute-contrast weighted sampling',
               'squared_contrast_weighted_sampling':'squared-contrast weighted sampling'}[pol]
        result+=r'''
Worst-case width and empirical resolution are distinct. A baseline had
higher aggregate resolution than the optimal-width rule in '''+str(len(losses))+r''' of
the 18 nonzero-budget cohort/gap/budget settings. The largest difference
was '''+f'{100*diff:.3f}'+r''' percentage points for '''+names[co]+r''',
'''+str(gap)+r''' missing hours and budget '''+str(b)+r''': '''+label+r'''
resolved '''+f'{100*best:.3f}'+r'''\% versus '''+f'{100*opt:.3f}'+r'''\% for the optimal-width
rule. This does not contradict its minimax-width guarantee and is retained
in the table rather than relabelled as an accuracy-optimal result.
'''
    else:
        result+=r'''
The optimal-width policy had at least as high aggregate resolution as
each comparator in these cohort/gap/budget settings. This empirical
observation is limited to the evaluated records; the theorem guarantees
worst-case width optimality, not resolution optimality at an arbitrary
realized completion.
'''
    neural={(co,x['gap_hours'],x['budget'],x['policy']):x for co in cohorts for x in r['neural_pairs_cohorts'][co]}
    nrows=[]
    for co in cohorts:
        nrows.append([names[co],pct(neural[co,6,0,ps[0]]['resolved_fraction']),
                      *[pct(neural[co,6,2,p]['resolved_fraction']) for p in ps]])
    ntab=table(r'Source & Before & Optimal & Greedy & Random & Max. $|c|$ & Wt. $|c|$ & Wt. $c^2$',nrows,'lrrrrrrr',
        r'AI-specific audit: resolution (\%) for the three comparisons involving the neural MLP, '
        r'six-hour gaps and exact six-hour totals. Before: no recovery. All other columns use budget two. '
        r'This subset was specified before the revised results were calculated.', 'tab:neural',True)
    result+=r'''\subsection{Comparisons involving the neural forecaster}
Table~\ref{tab:neural} isolates MLP-versus-persistence, MLP-versus-ridge,
and MLP-versus-boosting comparisons, keeping every meter, test day, and
mask seed. This prevents the AI conclusion from resting only on an
aggregate that includes comparisons between simpler models. The audit
requires saved predictions and measurement constraints, so its procedure
is identical for the neural and other candidates. These results establish
its applicability to the trained MLP; they do not establish a new neural
architecture or state-of-the-art forecasting accuracy.
'''+ntab
    return result,starts,ends,wc


def main():
    import hashlib
    from compose_review_sections import (DAILY_METHODS, daily_sections, recovery_figure,
                                         operator_figure, recovery_diagnostic_sections, verify_hashes)
    def read(name):
        return json.loads((OUT/name).read_text(encoding='utf-8'))
    t,s,mc,rt,r=map(read,['manuscript_result_tables.json','study_summary.json','study_matched_coverage.json',
                        'study_runtime_benchmark.json','study_recovery.json'])
    assert r['meters']==34 and r['heldout_meter_days']==3729
    assert r['dependent_policy_budget_pair_evaluations']==3729*2*6*3*4*6
    for filename in ['study_predictions.csv','study_summary.json','study_recovery.csv']:
        if (OUT/filename).exists():
            assert hashlib.sha256((OUT/filename).read_bytes()).hexdigest()==r['hashes'][filename]
        else:
            assert filename=='study_predictions.csv'
            omission=json.loads((ROOT/'work/prediction_archive_omission.json').read_text())
            assert omission['filename']==filename and omission['sha256']==r['hashes'][filename]
            assert omission['bytes']==s['artifacts'][filename]['bytes']
    for co in r['cohorts']:
        assert all(x['wrong_decisions']==0 for x in r['cohorts'][co])
    assert {m['train_days'] for m in s['meters'] if m['cohort']=='blem_counters'}=={266}
    recovery,starts,ends,wc=recovery_sections(r)
    recovery+=recovery_figure(r)
    recovery+=recovery_diagnostic_sections(r,table,pct)
    ai=read('ai_recovery_analysis.json')
    op=read('study_operator_example.json')
    exported=read('frozen_forecasts.json')
    verify_hashes(exported)
    assert hashlib.sha256((OUT/'frozen_forecasts.csv').read_bytes()).hexdigest()==exported['output_sha256']
    numeric_max=max(x['max'] for x in exported['numeric_ranges'].values())
    numeric_min=min(x['min'] for x in exported['numeric_ranges'].values())
    numerical_scale=r'''The measured held-out targets and fixed forecasts in the original
34-series evaluation range from '''+f'{numeric_min:.2f}'+r''' to '''+f'{numeric_max:.2f}'+r''' kWh per hourly target;
their aggregate ranges and source hash are in \texttt{frozen\_forecasts.json}.
Computation uses binary64 arithmetic. Stress regressions separately check
common offsets near $10^{10}$ against 80-digit decimal calculations, and
contrast preservation with targets of $10^{16}$. These are specific
regression checks, not an accuracy guarantee throughout that magnitude
range. Nonfinite inputs and detected arithmetic overflow are rejected.
Applications requiring a machine-certified enclosure should use
outward-rounded interval arithmetic or an appropriate exact solver.
'''
    for filename,expected in ai['source_hashes'].items():
        assert hashlib.sha256((OUT/filename).read_bytes()).hexdigest()==expected
    assert op['hashes']['main_summary']==r['hashes']['study_summary.json']
    assert op['hashes']['predictions']==r['hashes']['study_predictions.csv']
    cirows=[]
    for scope,label in [('all_pairs','All pairs'),('neural_pairs','MLP pairs')]:
        for key,name in [('no_recovery','No recovery'),('greedy','Greedy'),
                         ('absolute_weighted',r'Weighted $|c|$'),('squared_weighted',r'Weighted $c^2$')]:
            v=ai['portugal'][scope]['resolution_differences']['optimal_minus_'+key]
            cirows.append([label,name,f"{100*v['mean']:.2f}",
                           f"{100*v['percentile95'][0]:.2f}",f"{100*v['percentile95'][1]:.2f}"])
    recovery+=r'''Table~\ref{tab:recoveryci} summarizes the paired meter-bootstrap
stability of the resolution gains, separately for all pairs and neural-model
pairs. Whole meters remain the resampling unit.
'''
    recovery+=table('Comparisons & Reference & Gain & Lower & Upper',cirows,'llrrr',
        r'Portugal resolution gain in percentage points: optimal recovery with budget two minus '
        r'the reference policy, six-hour gaps and exact six-hour totals. Lower/Upper: descriptive '
        r'95\% paired bootstrap limits from 2,000 resamples of the same 30 whole meters. '
        r'All days, pairs, and seeds remain aggregated within each meter. These are panel-stability '
        r'intervals, not population-wide confidence claims.', 'tab:recoveryci')
    def mathnum(x):
        v=f'{x:.5g}'
        if 'e' in v:
            a,b=v.split('e');return a+r'\times10^{'+str(int(b))+'}'
        return v
    def interval(v):
        return '$['+mathnum(v[0])+','+mathnum(v[1])+']$'
    query_text=', '.join(q['timestamp'][11:16]+' ('+f"{q['value_kwh']:.5g}"+r' kWh)' for q in op['queries'])
    total_text=', '.join(f'{x:.5g}' for x in op['block_totals_kwh'])
    outcome=('a strict preference for the neural MLP' if op['after_decision']=='MLP' else
             'a strict preference for gradient boosting' if op['after_decision']=='HGB' else
             'an unresolved comparison')
    recovery+=r'''\subsection{A traceable neural-model audit}
The worked record is meter \texttt{'''+op['meter'].replace('_',r'\_')+r'''} on
'''+op['day']+r''', selected as the first chronologically unresolved Portugal
MLP-versus-boosting comparison under mask seed 1103, before inspecting
the recovery outcome. Its four retained six-hour totals, in day order,
are $('''+total_text+r''')$ kWh. Its six-hour verification gap initially gives the
MLP-minus-boosting MSE interval '''+interval(op['before_interval_mse_a_minus_b'])+r'''
in squared kWh. With budget two, the optimizer requests '''+str(op['query_count'])+r'''
records at provider-local times: '''+query_text+r'''. After their actual withheld values are
revealed, the interval becomes '''+interval(op['after_interval_mse_a_minus_b'])+r''',
giving '''+outcome+r'''. The guaranteed remaining-width fraction for the
chosen batch is '''+pct(op['worst_case_width_after']/op['worst_case_width_before'])+r'''\%.
The supplement supplies timestamps, issued predictions, visible readings,
totals, query choices, and a separately labelled complete reference. This
is a reproducible operator illustration on archived data, not a live meter
deployment or a case selected because recovery succeeded. Figure~\ref{fig:operator}
displays the forecasts, observations, and attaining completions before and
after recovery.
'''
    recovery+=operator_figure(op)
    results,regret_results=main_sections(t,s,mc,rt)
    marker=r'\subsection{Archive-consistent whole-period results}'
    results=results.replace(marker,daily_sections(table,pct)+recovery+'\n'+marker)
    for heading in ['Daily decisions at equal coverage', 'Named competitors and comparison difficulty',
                    'Budgeted recovery of measured values', 'Incremental benefit over greedy retrieval',
                    'A traceable neural-model audit', 'Archive-consistent whole-period results',
                    'Total uncertainty and selective missingness', 'Numerical verification and execution cost']:
        old=r'\subsection{'+heading+'}'
        results=results.replace(old,r'\FloatBarrier'+'\n'+old)
    rr=read('study_recovery_runtime.json')
    results+=r'''
The additional two-query batch optimizer was timed on 30 prepared
24-target problems at each gap size, with five warmups and three repeats.
Its median latency was '''+f"{rr['results']['6']['median_ms']:.3f}"+r''' ms for
six missing targets and '''+f"{rr['results']['12']['median_ms']:.3f}"+r''' ms for
twelve. This measures query selection alone; input preparation, retrieval
from a real meter or archive, and recomputation of the bounds are excluded.
The experiment does not measure communication latency.
'''
    rlookup={(x['gap_hours'],x['budget'],x['policy']):x for x in r['cohorts']['portugal']}
    greedy_gain=100*(rlookup[6,2,'optimal_minimax_width']['resolved_fraction']-rlookup[6,2,'greedy_width_reduction']['resolved_fraction'])
    from compose_interval_sections import interval_sections
    interval_recovery, interval_validation = interval_sections()
    results += interval_validation
    from compose_archive_sections import archive_sections
    archive_design, archive_results, archive_p0, archive_p2 = archive_sections()
    results += archive_results
    from compose_holdout_sections import holdout_sections
    holdout_design, holdout_results, holdout, holdout_rows = holdout_sections()
    results += holdout_results
    hp0, hp2, hpg, ha0, ha2, hag = holdout_rows
    from compose_period_archive_sections import period_archive_sections
    period_design, _, period_report = period_archive_sections(table, pct)
    from compose_interval_trace_sections import interval_trace_sections
    interval_trace_design, interval_trace_results = interval_trace_sections(table, pct)
    results += interval_trace_results
    abstract=r'''\textbf{Purpose:} Missing verification targets can make
machine-learning model comparisons depend on gap-filling assumptions.
We study auditable comparisons and selective target recovery when energy
aggregate measurements remain available.
\textbf{Methods:} Paired squared-error cancellation gives sharp bounds
and attaining completions. Sorted coefficient windows and dynamic programming
minimize worst-case remaining width under a batch reading budget.
For exact totals, deterministic adaptive querying cannot improve this
objective, while greedy selection can be arbitrarily worse. An extension
handles independently interval-bounded totals. The historical audit incorporates
every documented direct target copy in the permitted forecast archive
before comparing methods with identical information.
\textbf{Results:} Four fixed forecasters are evaluated on 34 meter series
and 3,729 test meter-days. Under restricted daily access, at most two readings
per day and model pair increase Portugal certification from '''+starts[0]+r'''\% to
'''+ends[0]+r'''\%. A frozen replication with unchanged model specifications
on 30 previously unused consumers adds 3,210 meter-days, increasing
certification from '''+f"{100*hp0['resolved_fraction']:.1f}"+r'''\% to
'''+f"{100*hp2['resolved_fraction']:.1f}"+r'''\%.
With saved-archive access, original-panel Portugal daily certification is already
'''+f"{100*archive_p0['resolved_fraction']:.1f}"+r'''\% before recovery and
'''+f"{100*archive_p2['resolved_fraction']:.1f}"+r'''\% afterward.
Real-trace recovery also remains informative under constructed 1\% and
5\% total-uncertainty bands. No evaluated certificate is incorrect;
independent solver and reproduction checks support the implementations.
\textbf{Conclusion:} The contribution is exact constrained evaluation and
worst-case recovery optimization. Available archive information largely
determines the practical need for additional readings; measured retrieval
economics and production outage validation remain open.'''
    discussion=r'''The method provides two connected decisions: whether the
retained measurements establish a strict ordering, and which recoverable
values most reduce the worst ambiguity when more information is needed.
The first calculation is sharp under its declared constraints; the second
is an exact nonadaptive allocation for a defined uncertainty objective.
Together they turn the energy-conservation structure into a usable audit
and recovery procedure, without fitting an additional missing-shape model.

The recovery experiment addresses a limitation exposed by the main study:
long gaps can leave too little information for useful coverage. Selected
true readings shrink the feasible set and materially increase the number
of supported comparisons. The result does not require a claim that an
imputer is generally inaccurate. Imputers can be excellent on realized
records, as the matched-coverage and regret results show. A guarantee over
all retained-measurement-compatible records answers a different operational
requirement and can be attached to an existing imputation-based workflow.
However, the archive-access analysis shows that much of this apparent
missingness disappears when later saved persistence forecasts are available.
The large primary recovery gains therefore apply to the restricted-record
regime; they must not be generalized to an archive with these exact copies.
The frozen new-consumer replication addresses repeated use of the original
development panel while preserving this access distinction. It adds
evidence about the fixed procedure within the same source and calendar,
without replacing the need to establish actual retrieval costs and
availability at a production evaluation cutoff.

The incremental coverage benefit of exact allocation over greedy recovery
is much smaller than its benefit over acquiring no readings. Its rationale
is the globally minimal worst-case interval and low prepared-input
computation cost, not a claim of large average accuracy gains over every
acquisition heuristic. The signed case and meter-level distributions make
that distinction explicit.

Recovery recommendations are most relevant when an analyst can request
specific archived interval values from a meter buffer or a secondary store.
In a decision-only deployment, already certified pairs could be skipped;
our fixed-budget experiment does not estimate the savings of that
early-stopping workflow. The present optimum also concerns one pair at a
time. A shared repair request covering many candidate comparisons would
need a joint objective and its own evaluation.
'''
    select={(x['cohort'],x['selector']):x for x in t['selection']}
    discussion+=r'''

The secondary conservative selector also has an unfavorable realized tradeoff:
Portugal mean normalized regret, multiplied by $10^3$, is
'''+f"{1000*select['portugal','minimax_regret']['mean_regret']:.3f}"+r''' for minimax regret versus
'''+f"{1000*select['portugal','historical_donor']['mean_regret']:.3f}"+r''' for donor imputation.
Appendix~\ref{app:regret} reports every selector's mean, tail, and worst-case
criterion. This prevents the valid worst-case guarantee from being read as
an average-accuracy advantage.
'''
    conclusion=r'''Retained energy totals support sharp squared-error
comparisons even when interval readings are missing. The paired calculation
uses the common unknown truth directly and establishes every strict ordering
that follows from the stated feasible set in exact arithmetic. An exact
sorted-window and dynamic-programming recovery rule further minimizes
worst-case remaining width under a batch reading budget. Completed
experiments on 34 series and a frozen 30-consumer replication evaluate
certification gains from limited recovery under restricted-record access,
with much smaller incremental value
when later saved forecasts already reveal the targets. A greedy boundary
example establishes why an exact optimizer matters for the worst-case
objective without asserting large average empirical improvements.
The corrected whole-period audit first incorporates all documented direct
copies in the declared forecast archive and gives every comparator the
same observations and totals. Real-trace sensitivity experiments also
evaluate independently interval-bounded totals. The practical procedure
is to specify evaluator access, incorporate
verified recoverable information, and optimize queries only over remaining
unknowns. Its guarantees concern the stated feasible set and objective;
field retrieval economics remain to be established.'''
    sections={'ABSTRACT':abstract,'DATA_METHODS':DATA_METHODS,'RESULTS':results,'DISCUSSION':discussion,
              'CONCLUSION':conclusion,'BLEM_REFERENCE':BLEM_REFERENCE,'RECOVERY_METHOD':RECOVERY_METHOD,
              'RECOVERY_RELATED':RECOVERY_RELATED,'RECOVERY_REFERENCES':RECOVERY_REFERENCES,
              'RECOVERY_DESIGN':RECOVERY_DESIGN,'REGRET_RESULTS':regret_results,'REVIEW_DESIGN':DAILY_METHODS,
              'NUMERICAL_SCALE':numerical_scale,'ARCHIVE_DESIGN':archive_design,
              'HOLDOUT_DESIGN':holdout_design,'PERIOD_ARCHIVE_DESIGN':period_design,
              'INTERVAL_TRACE_DESIGN':interval_trace_design,
              'INTERVAL_RECOVERY':interval_recovery,
              'MLP_EPOCH_CAP':str(s['design']['fixed_hyperparameters']['mlp']['max_iter'])}
    (ROOT/'work/final_sections.json').write_text(json.dumps(sections,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'sections_ready':list(sections),'recovery_start_percent':starts,'recovery_two_query_percent':ends,
                      'recovery_worst_width_percent':wc},indent=2))


if __name__=='__main__':
    main()
