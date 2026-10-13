"""Integrate the verified randomized method and natural-record application.

Called by the original manuscript builder before bibliography ordering. It
changes the existing document, not its primary empirical study or forecasts.
"""
from pathlib import Path
import json, re

TITLE='Auditing Machine-Learning Forecasts with Aggregate Targets: Exact Deterministic and Randomized Recovery'

ABSTRACT=r'''Missing verification targets can make machine-learning model comparisons
depend on imputation assumptions. We study fixed-record squared-error audits
when nonnegative targets and disjoint aggregate measurements constrain the
missing values. Paired-loss cancellation gives sharp comparison intervals.
Sorted windows and dynamic programming solve deterministic budgeted recovery,
and deterministic adaptation cannot improve its minimax width. We then
derive an exact randomized batch method: a weighted-endpoint pricing oracle
and a compact flow formulation replace enumeration of query subsets. For one
block with $m$ unknown coordinates, $r\geq2$ retained coordinates, and positive optima, the
deterministic-to-randomized worst-expected-width ratio is at most $m/r$;
separated clusters attain the bound when $r$ divides $m$. Every realized
comparison interval remains valid. The energy evaluation contains 34 meter
series and 3,729 test days, with a frozen replication on 30 additional
consumers and 3,210 days. All permitted direct forecast-archive copies are
incorporated before the historical audit. On the original public Portugal
panel, randomization reduces normalized worst expected width by 9.88\%
relative to exact deterministic recovery, but increases observed expected
width by 17.45\%. A separate public rainfall application establishes two
strict daily comparisons from nine naturally accumulated records; one
survives a declared aggregate-tolerance sensitivity. Secondary optimization
and the additional-consumer analysis preserve the observed tradeoff;
independent checks reproduce the calculations. The contribution is an exact tractable recovery method and a
sharp limit on the value of randomization, with explicit separation between
robust guarantees, realized performance, and unmeasured retrieval costs.'''

DESIGN=r'''
\subsection{Randomized recovery with a fixed hidden record}\label{sec:random-design}
The new batch experiment uses all 31 public UCI meter series from the
original study, comprising 3,456 days and 20,736 day--pair comparisons.
It is an additional analysis of that panel, not a new independent cohort.
Before examining outcomes, its protocol fixes the six-hour contiguous mask,
seed 1103, exact six-hour totals, all six model pairs, the permitted saved
persistence archive, and budget $B=2$ per day and pair. Direct archive
copies and exact-total deductions are incorporated before any policy is
optimized. The comparator is the globally optimal deterministic policy,
with greedy also retained in the distributed results. Budgets count
readings, not optimization iterations or retrieval transactions.

For each positive-width case, an independently enumerated finite-game
linear program computes a distribution over all eligible batches. Its
primal and dual constraints, positive support, and source observations
are saved. The compact formulation of Section~\ref{sec:randomized}
is independently solved on every such case. Expected realized width and
certification are exact probability-weighted sums over the saved support,
not Monte Carlo estimates. They use the held-out reference targets only
after the query distribution is fixed. Worst expected width instead takes
the maximum over every feasible record fixed before the random draw.
These are distinct outcomes, both reported without an effect-size filter.

For the compact implementation, a fixed synthetic suite compares 42
one-, two-, and three-block instances with exhaustive batch linear programs,
including tied coefficients. Four separated-cluster instances check the
sharp gap. Two larger one-block instances have 60 and 120 coordinates.
A separate policy-compilation check verifies original-index mapping,
preprocessing, and the actual distribution induced by flow-path and
conditional-subset sampling; it includes 48 cases, 5,800 seeded draws,
and eight invalid-input checks. These numerical checks use ordinary
floating-point arithmetic and the declared tolerances; they do not replace
the proofs or supply outward-rounded machine certificates.
'''

TIE_THEORY=r'''
\subsection{Choosing among equally robust policies}\label{sec:tie-selection}
The primary minimax objective need not select a unique policy. Robust
optima can be dominated away from their worst case, a general issue studied
by Iancu and Trichakis~\cite{iancu2014}. For example, take one block with
$E=1$, $c=(0,2,4,12)$ and $B=2$. A policy retaining pairs
$\{1,2\},\{1,3\},\{2,3\}$ with probabilities $0.4,0.2,0.4$ has expected
coefficient vector $(1.6,1.6,1.6,0)$. Retaining $\{1,2\}$ and $\{3,4\}$
with probabilities $0.8,0.2$ instead gives $(1.6,1.6,1.6,1.6)$.
Both have optimal worst expected width $1.6$: dual weights
$(0.2,0.6,0.2,0)$ certify this value. The first policy is never worse,
and is strictly better when $y_4>0$.

Write $e_{gi}(\pi)=\mathbb E_\pi v_{gi}(Q)$. After finding $R_B$, a
target-independent secondary rule minimizes
\begin{equation}
 H(\pi)=\sum_g\frac{E_g}{m_g}\sum_{i\in\M_g} e_{gi}(\pi)
 \quad\text{subject to}\quad
 \sum_g E_g\max_i e_{gi}(\pi)\leq R_B.
 \label{eq:secondary-policy}
\end{equation}
This is expected width at the uniform-within-block feasible completion,
not an estimated load distribution. It is a linear objective on the
optimal face of the finite LP. A policy that is no worse at every feasible
record and strictly better somewhere would also improve $H$, contradicting
secondary optimality. Thus this standard refinement removes dominated
expected-width functions; it need not identify a unique distribution or
maximize certification.

We also check the stronger requirement of never worsening the archived
policy $\pi_0$. Expected-width dominance is equivalent to
$\sum_g E_g\max_i[e_{gi}(\pi)-e_{gi}(\pi_0)]\leq0$.
Block epigraph variables, free in sign, encode this condition linearly.
Minimizing $H$ over that set preserves a primary-optimal $\pi_0$'s robust
value in exact arithmetic. The two refinements answer different questions:
the first chooses a reference criterion on the optimal face; the second
only allows improvements over the particular saved policy. Neither uses
hidden targets or guarantees that certification improves.

\subsection{Interpreting the robust objective}
A four-coordinate family displays the full tradeoff without selecting a
favorable observed record. Let $c=(0,\delta,L,L+\delta)$, $L\geq2\delta>0$,
and $B=2$. An optimal deterministic policy retains the first pair; its width
is $E\delta\lambda$, where $\lambda$ is that pair's share of total energy.
Equally mixing the two within-cluster retained pairs gives width
$E\delta/2$ in expectation at every feasible record and attains the lower
bound in Proposition~\ref{prop:random-gap}. It improves on that deterministic
policy when $\lambda>1/2$, ties at $1/2$, and worsens when $\lambda<1/2$.
The robust guarantee protects against an unspecified feasible allocation
chosen before the random draw; it is not an average-load or decision-cost
optimum. More generally Proposition~\ref{prop:random-gap} implies
$(D_B-R_B)/D_B\leq B/m$ for positive one-block optima. The low-budget
$(m,B)=(60,4)$ and $(120,6)$ fixtures therefore permit at most $6.67\%$
and $5\%$ relative robust gains, motivating the larger budget fractions in
the computational study below.
'''

TIE_DESIGN=r'''
\subsection{Post-review selection among minimax optima}\label{sec:tie-design}
The original energy experiment uses the feasible distribution returned by
HiGHS dual simplex with fixed input ordering and no secondary objective.
It is one specified solver selection, not a claim that all optimal policies
have the same realized performance. A subsequent frozen sensitivity protocol
applies both refinements in Section~\ref{sec:tie-selection} to all 1,074
positive-width cases, retaining the other 19,662 cases unchanged. Policies
are saved before reference targets are parsed or used for evaluation;
the file is hashed earlier solely for provenance. The
primary-optimal-face constraint uses the unrounded value of the saved
feasible mixture, with no deliberate slack; primal and dual feasibility
tolerances are $10^{-9}$. Archived policies and unfavorable original results
are retained. This is a post-review analysis of the same panel, not a new
independent replication or a claim of exact interval-arithmetic certification.
'''

TIE_RESULTS=r'''
\subsection{Secondary optimization does not remove the observed penalty}
\label{sec:tie-results}
All 2,148 secondary LPs complete. Neither the dominance refinement nor the
uniform-completion refinement changes the realized expected width in any
of the 1,074 positive-width cases beyond the declared $10^{-9}$ scaled
comparison tolerance. Neither strictly improves the secondary objective at
that tolerance. The largest normalized primary lower-bound gap is
$1.96\times10^{-12}$ and the largest dominance residual is
$5.75\times10^{-12}$. Portugal's normalized expected width remains
23.670\% for both refinements, versus 20.154\% for deterministic recovery;
certification remains 98.688\% versus 98.795\%. The household summaries
are likewise unchanged at the displayed precision. Independent replay checks
every refined distribution, secondary optimum, and case aggregation.
Thus the reported 17.45\% Portugal penalty persists under these specified
target-independent tie refinements. It is not evidence that every minimax
policy has that penalty, or that the percentage transfers to other records.
The exact counterexample in Section~\ref{sec:tie-selection} remains a useful
regression test even though this empirical panel shows no such improvement.
'''

LITERATURE_ADD=r'''
Chen et al.~\cite{chen2026} study robust selection after querying uncertain
parameters under budgeted uncertainty. Their subsequent item-selection
problem differs from reducing a fixed contrast's range over continuous
aggregate-constrained targets. Iancu and Trichakis~\cite{iancu2014} address
dominated robust optima; our secondary policy audit applies this established
principle rather than claiming it as a new concept.
Table~\ref{tab:closest-work} distinguishes the nearest settings. Exactness
refers to each work's own stated problem, not a common benchmark or a claim
that one method dominates the others.
\begin{table}[htbp]\centering\footnotesize
\caption{Closest methodological settings and the contribution boundary.}
\label{tab:closest-work}
\begin{tabular}{>{\raggedright\arraybackslash}p{0.16\linewidth}>{\raggedright\arraybackslash}p{0.25\linewidth}>{\raggedright\arraybackslash}p{0.25\linewidth}>{\raggedright\arraybackslash}p{0.23\linewidth}}\toprule
Work & Information and uncertainty & Acquisition and objective & Solution or guarantee\\\midrule
Maia Polo et al.~\cite{polo} & Weak labels and partially identified performance & No coordinate-recovery design; classification metric bounds & Convex optimization under its observation assumptions\\
Hara et al.~\cite{hara} & Unlabeled test pool and surrogate label model & Adaptive labeling; variance of estimated test-loss differences & Unbiased estimation with a surrogate-based acquisition approximation\\
Chen et al.~\cite{chen2026} & Queried parameters and budgeted uncertainty & Queries followed by item selection; robust objective or feasibility & General hardness, special-case algorithms and mixed-integer formulations\\
Kawase and Sumita~\cite{kawase2024} & Set family and objective scenarios & Randomized feasible-set choice; worst expected objective & General oracle/separation framework and approximation results\\
This work & Nonnegative targets with disjoint exact sums & Fixed-pair recovery; deterministic width or randomized expected width & Exact window/DP and compact LP; deterministic adaptivity identity and sharp one-block gap\\
\bottomrule\end{tabular}\end{table}
'''

def empirical(root):
    here=root/'work/new_direction_randomized'
    result=json.loads((here/'result.json').read_text())
    audit=json.loads((here/'independent_verification.json').read_text())
    compact=json.loads((root/'work/randomized_recovery_root/compact_verification.json').read_text())
    policy=json.loads((root/'work/randomized_recovery_root/policy_verification.json').read_text())
    assert result['status']==audit['status']==compact['status']==policy['status']=='passed'
    rows=[]
    for cohort,label in [('portugal','Portugal'),('household','Household')]:
        x=next(v for v in result['cohort_summary'] if v['cohort']==cohort and v['scope']=='all_cases')
        keys=['fraction_deterministic_worst_width','fraction_randomized_worst_expected_width',
              'fraction_deterministic_actual_width','fraction_randomized_expected_actual_width',
              'mean_deterministic_certification','mean_randomized_expected_certification']
        rows.append(label+' & '+' & '.join(f'{100*x[k]:.3f}' for k in keys)+r' \\')
    scale=[]
    for x in compact['scalability']:
        scale.append(f"{x['m']} & {x['budget']} & {x['number_of_fixed_size_batches']:,} & {x['compact']['variables']:,}"+r' \\')
    return r'''
\subsection{Exact randomized recovery: robust gain and realized tradeoff}
\label{sec:random-results}
Of the 20,736 fixed comparisons, 1,074 retain positive width after free
archive information and total deductions. The finite-game solutions have
2,341 positive-probability batches. Independent reconstruction checks all
20,736 cases, all positive batches, 19,662 permitted direct target copies,
and all 1,074 compact-versus-finite-game optima. The largest objective
discrepancy, divided by $\max(1,\text{initial width})$, is
$1.34\times10^{-13}$. No issued support-batch certificate contradicts
the reference comparison. These dependent checks validate the calculation;
their count is not an independent statistical sample size.

Table~\ref{tab:random-results} separates the robust objective from realized
outcomes. Portugal's mean normalized worst expected width decreases from
29.595\% to 26.673\% of its initial width, a relative reduction of 9.88\%
against the exact deterministic optimum. Its normalized expected width at
the actual record increases from 20.154\% to 23.670\%, or 17.45\% relatively.
The household reductions and increases are 6.66\% and 11.05\%, respectively.
Certification decreases slightly in both cohorts. The robust objective
improves strictly in 663 positive-width cases; realized expected width
improves in 14, worsens in 649, and is unchanged in the remaining 411.
No query-count advantage is claimed: both exact policies use two readings
in these positive-width cases.

\begin{table}[htbp]\centering\small
\caption{Randomized and deterministic exact recovery under identical saved-archive
access and budget. Width columns are percentages of initial width: first sum
within each meter, then average meter ratios. Certification averages all
day--pair cases within each meter, then meters. ``Rand.'' reports expectations
over the optimized batch distribution. Lower width is better; higher
certification is better.}\label{tab:random-results}
\begin{tabular}{lrrrrrr}\toprule
&\multicolumn{2}{c}{Worst width}&\multicolumn{2}{c}{Realized width}&\multicolumn{2}{c}{Certification (\%)}\\
Cohort&Det.&Rand.&Det.&Rand.&Det.&Rand.\\\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule\end{tabular}\end{table}

This adverse realized tradeoff is consistent with the objective: minimizing
the largest expected ambiguity over all compatible records does not
minimize width or maximize certification at the particular realized load
profile. Randomization is therefore a robust-design option, not an
empirically dominant default replacement for deterministic recovery.

The compact implementation agrees with exhaustive finite-game programs on
all 42 synthetic cases to within $1.78\times10^{-13}$ absolute objective
error. Constructed $(m,r)=(4,2),(6,2),(9,3),(12,2)$ instances attain factors
2, 3, 3, and 6, respectively. These are sharpness examples, not estimates
of typical field gains. Table~\ref{tab:compact-scale} demonstrates that the
implementation need not enumerate all batches. The larger instance has
more than 3.65 billion size-six subsets but only 3,221 LP variables.
The independent sampler audit also checks its induced mixture, rather than
only whether sampled batches have the correct size: the largest recovered
coefficient discrepancy is $1.78\times10^{-15}$. All floating-point
projection and normalization corrections are recorded in Online Resource~1.

\begin{table}[htbp]\centering\small
\caption{Fixed one-block scalability checks. The batch counts are combinatorial
counts, not enumerated runs. LP variable counts include the epigraph. These
two synthetic configurations establish feasibility at these sizes, not an
asymptotic runtime benchmark.}\label{tab:compact-scale}
\begin{tabular}{rrrr}\toprule
Coordinates $m$&Budget $B$&Size-$B$ batches&Compact LP variables\\\midrule
'''+ '\n'.join(scale)+r'''
\bottomrule\end{tabular}\end{table}
'''

def integrate(text,root):
    root=Path(root)
    # Reader-facing notation guide; no change to assumptions or calculations.
    notation=r'''
Table~\ref{tab:notation} collects the main symbols. The development first
defines the common feasible record and sharp comparison bounds, then treats
deterministic batch recovery. The randomized method in
Section~\ref{sec:randomized-recovery} also assumes exact totals; it minimizes
worst expected width when the hidden record is fixed before the batch draw.
The deterministic extension to interval totals is given separately in
Appendix~\ref{app:interval-theory}.

\begin{table}[htbp]\centering\small
\caption{Main notation. Quantities refer to one fixed model pair and its
declared evaluation record; exact and interval totals are distinguished.}
\label{tab:notation}
\begin{tabular}{p{0.23\linewidth}p{0.70\linewidth}}\toprule
Symbol & Meaning\\\midrule
$N$, $y_i$, $a_i$, $b_i$ & Target count, target value, and two fixed predictions.\\
$\Oset$, $\M$ & Observed coordinates (including permitted reconstructions) and remaining missing coordinates.\\
$I_g$, $\M_g$, $m_g$ & Disjoint aggregate block, its missing coordinates, and their count.\\
$\F$ & All target records compatible with the declared observations and aggregate constraints.\\
$E_g$; $[\ell_g,u_g]$ & Exact residual total; residual-total interval after subtracting observed values.\\
$D(y)$, $c_i$ & Paired MSE difference $L_a(y)-L_b(y)$ and coefficient $2(b_i-a_i)/N$ of a missing target.\\
$B$, $Q$, $S_g(Q)$ & Hard reading budget, queried batch, and unqueried coordinates in block $g$.\\
$W(Q,y)$ & Remaining comparison-interval width after querying $Q$ on record $y$.\\
$\pi$, $R_B$ & Distribution over admissible batches and its optimal worst expected width.\\
$m$, $r$, $D_B$ & In the one-block gap theorem: missing count, retained count $r=m-B$, and optimal deterministic worst-case width.\\
\bottomrule\end{tabular}
\end{table}

'''
    text=text.replace(r'\section{Observation Model and Evaluation Target}',
        r'\section{Observation Model and Evaluation Target}'+'\n'+notation,1)
    text=re.sub(r'\\title\{.*?\}\n\\author',lambda _:r'\title{'+TITLE+r'}'+'\n'+r'\author',text,count=1,flags=re.S)
    text=re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}',lambda _:r'\begin{abstract}'+'\n'+ABSTRACT+'\n'+r'\end{abstract}',text,count=1,flags=re.S)
    text=re.sub(r'\\noindent\\textbf\{Keywords:\}.*?\n\n',lambda _:r'\noindent\textbf{Keywords:} machine learning; model evaluation; robust optimization;'+'\n'+r'randomized recovery; partial identification; aggregate observations.'+'\n\n',text,count=1,flags=re.S)
    marker=r'\section{Related Work and Contribution Boundary}'
    intro=r'''
The deterministic result leaves a distinct question: can a distribution
over recovery batches reduce the worst expected ambiguity when the hidden
record is fixed before the draw? Section~\ref{sec:randomized} answers this
question with an exact weighted-endpoint oracle, a compact budget-flow
linear program, and a sharp one-block randomization-gap bound. The compact
program produces usable query batches and removes the need to enumerate
all query subsets. Its benefit is defined against the optimal deterministic
policy, including deterministic adaptive strategies under the earlier theorem.
We separately measure realized performance, which need not improve with
this robust objective. Finally, naturally accumulated precipitation records
provide a documented example where a total survives while the temporal
distribution does not; their role is to test the audit's information model,
not to validate hypothetical recovery costs or a new AI forecasting model.

'''
    text=text.replace(marker,intro+marker,1)
    text=text.replace(r'\section{Observation Model and Evaluation Target}',
        LITERATURE_ADD+'\n'+r'\section{Observation Model and Evaluation Target}',1)
    text=re.sub(r'This does not rule out gains in average width, empirical resolution, or\nrandomized expected-minimax criteria\..*?optimization are essential\.',
        lambda _: 'This deterministic result does not rule out gains in average width or\nempirical resolution. Section~\\ref{sec:randomized-recovery} characterizes\nthe separate randomized worst-expected-width objective.',text,count=1,flags=re.S)
    text=text.replace(r'\section{Experimental Design}',(root/'work/randomized_recovery_root/theory_section.tex').read_text()+ '\n'+TIE_THEORY+'\n'+r'\section{Experimental Design}',1)
    text=text.replace('All information and\ndeterministic deductions available before recovery are incorporated first.',
        'The benchmark first incorporates permitted direct persistence copies\nand aggregate-determined values. Sharpness is relative to the declared\nfeasible set; inverse constraints from other fitted predictors are not\nincluded in the evaluated archive regime.')
    text=text.replace(r'\subsection{Generative-AI assistance}',DESIGN+'\n'+TIE_DESIGN+'\n'+r'\subsection{Generative-AI assistance}',1)
    natural=(root/'work/new_direction_practical/noaa/manuscript_fragment.tex').read_text()
    tie_check=json.loads((root/'work/randomized_tie_review/independent_verification.json').read_text())
    assert tie_check['status']=='passed'
    holdout_check=json.loads((root/'work/randomized_holdout_review/independent_verification.json').read_text())
    assert holdout_check['status']=='PASS'
    holdout=r'\subsection{Randomized recovery on additional consumers}'+'\n'+(root/'work/randomized_holdout_review/holdout_fragment.tex').read_text()
    scaling=r'\subsection{Computational scaling of randomized recovery}'+'\n'+(root/'work/randomized_scaling_review/scaling_fragment.tex').read_text()
    text=text.replace(r'\section{Discussion}',empirical(root)+'\n'+TIE_RESULTS+'\n'+holdout+'\n'+scaling+'\n'+natural+'\n'+r'\section{Discussion}',1)
    text=text.replace('scheduled interval-energy targets. Predictions are issued before these\ntargets occur and are frozen before evaluation masks are imposed.',
        'scheduled nonnegative targets. For the energy experiments, predictions are\nissued before these targets occur and are frozen before evaluation masks\nare imposed. The separate precipitation application uses documented\nretrospective reforecasts and naturally accumulated observations.')
    text=text.replace('The experiments impose missingness retrospectively. Actual cumulative',
        'The energy experiments impose missingness retrospectively. Actual cumulative')
    text=text.replace('The primary \\emph{restricted-record} regime supplies',
        'The original daily \\emph{restricted-record} regime supplies')
    text=text.replace('This study reanalyzes public meter records and does not recruit participants',
        'This study reanalyzes public meter and precipitation records and does not recruit participants')
    text=text.replace('time. A shared repair request covering many candidate comparisons would',
        'time. The randomized extension likewise optimizes one fixed pair and a\nhard batch budget, with the hidden record fixed before the draw. It does\nnot solve optimal randomized adaptive recovery or guarantee an improvement\non each realized record. A shared repair request covering many candidate comparisons would')
    discussion=r'''
The randomized extension strengthens the methodological contribution in a
precise way: it provides exact optimization over batch distributions,
constructive sampling, and a sharp separation from deterministic strategies.
It does not strengthen the claim of average energy-audit performance: its
observed width and certification tradeoff is unfavorable on the evaluated
public panel. Its use is justified when worst expected residual ambiguity
is the declared decision criterion. The natural precipitation cases add
evidence that the aggregate-only observation pattern occurs in a public
archive. They establish two strict comparisons without inventing missing
hourly values, but do not establish the availability or cost of later
recovery, population-level prevalence, or a modern forecasting advantage.

'''
    text=text.replace(r'\subsection{Operational interpretation}',discussion+r'\subsection{Operational interpretation}',1)
    conclusion=r'''\section{Conclusion}
Aggregate observations support sharp comparisons of fixed forecasts despite
missing verification targets. For deterministic recovery, sorted windows
and dynamic programming solve the worst remaining width objective, and
deterministic adaptation cannot improve it. For randomized nonadaptive
recovery, weighted endpoints and a compact budget-flow formulation solve
the worst expected width objective without enumerating query subsets.
For positive optima and $r\geq2$, the one-block deterministic-to-randomized ratio is bounded by $m/r$, with
attaining clustered examples when $r$ divides $m$.

The experiments distinguish these guarantees from realized performance.
The archive-consistent energy audit uses permitted direct target copies
before evaluating every comparator. Randomization improves its optimized
robust objective but has an unfavorable realized tradeoff on the tested
energy panel. Naturally accumulated rainfall records support two strict
daily comparisons from surviving totals, with one robust to the specified
total sensitivity. The practical output is an auditable interval, a decision
when justified, and an exactly optimized recovery policy for the selected
criterion. Operational retrieval costs and arrival times remain unmeasured.

\FloatBarrier
'''
    text=re.sub(r'\\section\{Conclusion\}.*?(?=\\appendix)',lambda _:conclusion,text,count=1,flags=re.S)
    data_add=r'''
The additional randomized-recovery materials include the compact optimizer,
an executable hard-budget sampler, complete finite-game primal/dual traces,
all positive query batches, an independent reconstruction of every public
energy case, and sharpness/scalability fixtures. The NOAA materials include
the selected observation records, decoded gridpoint predictions and message
provenance, the fixed source-selection protocol, all nine natural cases,
all 43 dry controls, failed-run diagnostics and the declared preprocessing
and tolerance sensitivities. Source URLs and content hashes identify the
downloaded records; the supplement does not include the large GRIB cache.
The naturally missing subdaily targets are not available as reference truth.
'''
    text=text.replace(r'\subsection*{Research Transparency}',data_add+'\n'+r'\subsection*{Research Transparency}',1)
    # Keep the central proofs, information-consistent comparison, new optimizer
    # and natural-record application together. Retain supporting analyses in
    # an explicit appendix, including all unfavorable comparator outcomes.
    extended=[]
    moves=[
        ('Daily decisions and the value of pairing','restricted-daily',
         r'''\subsection{Restricted-record sensitivity}
The isolated daily-record experiment is a separate limited-input benchmark.
Appendices~\ref{app:restricted-daily} and~\ref{app:restricted-recovery}
retain its complete comparisons and budget grid. Its large recovery gains
must not be interpreted as gains after the saved archive has already been
used. The archive-consistent evidence above is the primary retrospective
application result.
'''),
        ('Budgeted recovery of measured values','restricted-recovery',''),
        ('Recovery with independently bounded totals','interval-theory',
         r'''\subsection{Extension to independently bounded totals}
The deterministic batch objective also admits an exact extension when each
disjoint aggregate lies in a specified interval. Appendix~\ref{app:interval-theory}
gives the optimizer and proof; the randomized theory below concerns exact
totals only.
'''),
        ('Daily fairness and close-competitor diagnostics','fairness-design',''),
        ('Evaluator-access sensitivity','access-design',''),
        ('Frozen replication on previously unused consumers','replication-design',''),
        ('Interval-total recovery sensitivity on frozen traces','interval-design',
         r'''\subsection{Additional designs and reproducibility}
Appendices~\ref{app:fairness-design}--\ref{app:interval-design} give the
matched-coverage diagnostics, earlier access sensitivity, frozen selection
and fitting of 30 previously unused consumers, and real-trace interval-total
experiment. The replication adds 3,210 days from the same source and calendar;
the constructed tolerance study adds assumptions, not new measured cases.
Their full results are retained below in the additional analyses appendix.
'''),
        ('Daily decisions at equal coverage','matched-daily',''),
        ('Named competitors and comparison difficulty','named-pairs',''),
        ('Comparisons involving the neural forecaster','neural-pairs',''),
        ('Incremental benefit over greedy retrieval','greedy-detail',
         r'''\subsection{Attribution and the exact-versus-greedy distinction}
In the original restricted-record six-hour experiment, exact recovery exceeds
greedy certification by 1.15 percentage points on average across Portugal
meters. Exact alone certifies 785 dependent cases and greedy alone 119;
actual width is larger under exact recovery in 700 cases. Thus the worst-case
width optimum is not a pointwise certification optimum.
The following archive-consistent analysis isolates the much smaller
archive-aware allocator increment from free reconstruction and paid readings.
Appendix~\ref{app:greedy-detail} retains query counts, signed distributions
and descriptive bootstrap intervals.
'''),
        ('A traceable neural-model audit','worked-audit',''),
        ('Sensitivity to the available forecast archive','earlier-access',''),
        ('Replication on 30 previously unused consumers','replication-results',
         r'''\subsection{Replication and total-uncertainty sensitivity}
The frozen additional 30-consumer panel increases restricted-record
certification from 25.02\% to 64.11\% with exact two-query recovery;
archive-aware certification instead starts at 96.87\% and reaches 98.57\%.
The archive-aware exact-over-greedy increment is 0.061 percentage points
(Appendix~\ref{app:replication-results}). This supports repeatability within
the same dataset and calendar, not independent infrastructure validation.
With constructed $\pm5\%$ total bands on the original Portugal traces,
certification increases from 15.8\% to 46.3\% under restricted access and
from 96.5\% to 98.1\% with the saved archive. Appendix~\ref{app:interval-results}
retains every cohort, tolerance and policy result.
'''),
        ('Recovery with interval totals on real traces','interval-results','')]
    for title,label,replacement in moves:
        pattern=r'\\subsection\{'+re.escape(title)+r'\}.*?(?=\\(?:sub)?section\*?\{|\Z)'
        m=re.search(pattern,text,re.S)
        if not m:raise ValueError('Missing appendix move: '+title)
        block=m.group(0)
        block=block.replace(r'\subsection{'+title+'}',r'\subsection{'+title+'}'+r'\label{app:'+label+'}',1)
        extended.append(block)
        text=text[:m.start()]+replacement+'\n'+text[m.end():]
    text=text.replace(r'\appendix',r'''\appendix
\section{Additional Designs, Extensions, and Energy Results}\label{app:additional}
This appendix retains the supporting designs and complete analyses. The
original uniform-random retrieval baseline in its tables is distinct from
the optimized batch distribution of Section~\ref{sec:randomized-recovery}.
'''+ '\n'.join(extended)+'\n'+r'\FloatBarrier',1)
    text=text.replace(' & Random &',' & Uniform random &')
    text=text.replace(r'Figure~\ref{fig:recovery} displays coverage and worst-case width across budgets.',
        r'Appendix~\ref{app:neural-pairs} also displays coverage and worst-case width across budgets.')
    recovery_figure=re.search(r'\\begin\{figure\}.*?\\label\{fig:recovery\}\\end\{figure\}',text,re.S)
    # Match the nearest figure opening, not earlier figures in the appendix.
    if recovery_figure:
        end=text.index(r'\label{fig:recovery}')
        start=text.rfind(r'\begin{figure}',0,end)
        text=text[:start]+r'Figure~\ref{fig:recovery} displays coverage and worst-case width across budgets.'+'\n'+text[start:]
    text=text.replace('The fixed training-only rule selected 30 additional consumers from 255',
        r'Table~\ref{tab:newconsumers} reports the replication. The fixed training-only rule selected 30 additional consumers from 255')
    # Lead with the archive-aware information boundary; keep all restricted
    # outcomes, including favorable and unfavorable comparisons, in the appendix.
    archive_pattern=r'\\subsection\{Archive-consistent whole-period results\}.*?(?=\\(?:sub)?section\*?\{|\Z)'
    archive_match=re.search(archive_pattern,text,re.S)
    assert archive_match
    archive_block=archive_match.group(0)
    text=text[:archive_match.start()]+text[archive_match.end():]
    text=text.replace(r'\section{Results}',r'''\section{Results}
The main retrospective application uses the declared saved forecast archive.
Its permitted direct copies remove most target uncertainty before any paid
recovery. We first report this regime and the exact attribution of free
information, additional readings, and allocation. Restricted-record results
are retained as a separate sensitivity analysis. The methodological
contribution is exact audit and recovery under specified uncertainty;
these experiments do not demonstrate superior full-period ranking accuracy
or production retrieval savings over the strongest imputation comparator.
'''+archive_block,1)
    text=text.replace('The following archive-consistent analysis isolates the much smaller',
                      'The preceding archive-consistent analysis isolates the much smaller')
    # Bring the traceable explanation into the main text without upgrading
    # its restricted information regime into evidence of a field deployment.
    example_pattern=r'\\subsection\{A traceable neural-model audit\}.*?(?=\\(?:sub)?section\*?\{|\Z)'
    example_match=re.search(example_pattern,text,re.S)
    assert example_match
    example_block=example_match.group(0).replace(r'\subsection{A traceable neural-model audit}',
        r'\subsection{Worked example under restricted record access}')
    text=text[:example_match.start()]+text[example_match.end():]
    text=text.replace(r'\subsection{Restricted-record sensitivity}',example_block+'\n'+r'\subsection{Restricted-record sensitivity}',1)
    text=text.replace(r'Appendix~\ref{app:worked-audit}',r'Section~\ref{app:worked-audit}')
    text=text.replace('The contribution is a constrained model-evaluation and target-recovery method\nfor energy forecasts\nand its completed computational evaluation.',
        'The contribution is a constrained model-evaluation and target-recovery\nmethod, with energy and precipitation records used to test its assumptions\nand consequences. It is principally a methodological contribution, not a\ndemonstration of forecast-accuracy or retrieval-cost superiority.')
    extra_bib=r'''
\bibitem{chen2026} X. Chen, M. Goerigk, and M. Poss, ``The robust selection
problem with information discovery,'' \emph{Discrete Applied Mathematics},
vol.~382, pp.~277--292, 2026. \url{https://doi.org/10.1016/j.dam.2025.12.012}.
\bibitem{iancu2014} D. A. Iancu and N. Trichakis, ``Pareto efficiency in robust
optimization,'' \emph{Management Science}, vol.~60, no.~1, pp.~130--147, 2014.
\url{https://doi.org/10.1287/mnsc.2013.1753}.
'''
    text=text.replace(r'\end{thebibliography}',extra_bib+'\n'+r'\end{thebibliography}',1)
    text=text.replace('sec:randomized}', 'sec:randomized-recovery}')
    for p in [root/'work/randomized_recovery_root/bibitem_suggestions.tex',root/'work/new_direction_practical/noaa/bibitems.txt']:
        text=text.replace(r'\end{thebibliography}',p.read_text()+'\n'+r'\end{thebibliography}',1)
    assert len(re.findall(r'\\section\{Conclusion\}',text))==1
    assert r'\label{sec:randomized-recovery}' in text
    from final_peer_review.editorial_trim import apply_editorial_trim
    text=apply_editorial_trim(text)
    fresh_check=json.loads((root/'work/fresh_refit_review/independent_verification.json').read_text())
    assert fresh_check['status']=='passed'
    fresh_fragment=(root/'work/fresh_refit_review/refit_fragment.tex').read_text()
    text=text.replace(r'\subsection{Missingness and retained totals}',
        r'\paragraph{Fresh model-fitting verification.}'+'\n'+fresh_fragment+'\n'+r'\subsection{Missingness and retained totals}',1)
    return text
