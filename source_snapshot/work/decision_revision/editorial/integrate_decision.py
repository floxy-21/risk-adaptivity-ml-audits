"""Pure integration of verified decision-acquisition evidence. No file writes."""
import re

POLICIES=['ml_decision','uniform_decision','width_one','hara_one','uniform_one','randomized_one']
LABELS={'ml_decision':'ML-guided decision','uniform_decision':'Uniform-simplex decision',
        'width_one':'Width (exact = greedy)','hara_one':'Hara proposal','uniform_one':'Uniform sampling',
        'randomized_one':'Randomized width'}

def lookup(rows,population):
    result={row['policy']:row for row in rows if row['population']==population}
    if set(result)!=set(POLICIES):raise AssertionError('Policy grid incomplete')
    return result

def one_replace(text,old,new):
    if text.count(old)!=1:raise AssertionError('Expected one editorial anchor: '+old[:90])
    return text.replace(old,new,1)

def number(value,digits=3):
    return '--' if value is None else f'{value:.{digits}f}'

def result_text(summary,oracle,run):
    s=lookup(summary['summaries'],'initially_uncertified')
    o=lookup(oracle['summaries'],'initially_uncertified')
    ml,w=s['ml_decision'],s['width_one'];mo,wo=o['ml_decision'],o['width_one']
    success=mo['ratio_at_most_1_10'] and mo['no_finite_strict_oracle_cases']==0 and mo['all_case_strict_coverage_at_cap']==1 and ml['unresolved']==0 and ml['numerical_ties']==0
    verdict='meets' if success else 'does not meet'
    reduction=summary['relative_mean_reduction']
    relative_word='lower' if reduction>=0 else 'higher'
    ci=summary['descriptive_consumer_bootstrap_interval']
    ratio_ci=mo['descriptive_household_bootstrap_ratio_95']
    interval_notice=(rf'The descriptive ratio interval [{ratio_ci[0]:.3f}, {ratio_ci[1]:.3f}] crosses 1.10; the point criterion is a statement about this finite panel, not a population guarantee.'
                     if ratio_ci is not None and ratio_ci[0]<1.10<ratio_ci[1]
                     else 'The descriptive ratio interval measures stability across these consumers; it does not turn the finite-panel criterion into a population guarantee.')
    attrition=(r'Consumer \texttt{MAC000028} remains in the selected and fitted set of 20 but has no eligible test day; the other 19 contribute the reported comparisons.'
               if summary['eligible_households']==19 else '')
    rows=[]
    for policy in POLICIES:
        a,b=s[policy],o[policy];interval=b['descriptive_household_bootstrap_ratio_95']
        display='--' if interval is None else f'[{interval[0]:.3f}, {interval[1]:.3f}]'
        rows.append(f"{LABELS[policy]} & {a['macro_mean_requests']:.3f} & {number(a['B80'],0)} & {number(b['ratio_of_macro_means'])} & {display} & {100*a['coverage'][-1]:.1f}\\\\")
    text=rf'''\subsection{{New-consumer decision-acquisition confirmation}}\label{{sec:decision-confirmation-results}}
The frozen confirmation contributes {summary['eligible_households']:,} households,
{summary['eligible_days']:,} household-days and {summary['case_count']:,} day--pair--mask
comparisons, including {summary['initially_uncertified_cases']:,} initially uncertified
comparisons. The six policies receive identical information and acquire one
reading at a time. {attrition}
Table~\ref{{tab:decision-confirmation}} reports the complete
policy comparison. An exhaustive search evaluates {oracle['subsets_checked']:,}
candidate query subsets after the acquisition run has finished; hidden values
are used only in this explicitly hindsight calculation.

\begin{{table}}[htbp]
\centering\small\setlength{{\tabcolsep}}{{4pt}}
\caption{{New-consumer confirmation: initially uncertified comparisons,
equal household weights. Cost is mean charged hourly records; ratio is the
ratio of policy and hindsight-minimum mean costs on identical strictly
certifiable cases. Intervals are descriptive 95\% paired-household bootstrap
intervals. Coverage is strict certification at the six-request cap.
Exact and greedy width policies coincide at a one-query budget.}}
\label{{tab:decision-confirmation}}
\begin{{tabular}}{{lrc rlr}}
\toprule
Policy & Cost & $B_{{80}}$ & Ratio & Ratio interval & \shortstack{{Coverage\\(\%)}}\\
\midrule
'''+ '\n'.join(rows)+rf'''
\bottomrule
\end{{tabular}}
\end{{table}}

The ML-guided policy's mean is {ml['macro_mean_requests']:.4f} requested records,
compared with the matched hindsight mean
{mo['oracle_macro_mean_requests_on_same_cases']:.4f}. Its ratio is
{number(mo['ratio_of_macro_means'],4)}; the ordinary width policy's ratio is
{number(wo['ratio_of_macro_means'],4)}. The ML-guided policy {verdict} the
new, predeclared criterion of ratio at most 1.10 with complete strict
coverage and no incorrect strict certificates. This criterion measures
proximity to a finite-panel lower bound; it is not a claim of unique
algorithmic superiority. Every policy's ratio is disclosed in the table.
{interval_notice}

Against the better width/Hara mean, the ML-guided policy uses
{100*abs(reduction):.2f}\% {relative_word} requests. The descriptive interval
for the signed relative reduction is [{100*ci[0]:.2f}, {100*ci[1]:.2f}]\%.
Its $B_{{80}}$ is {number(ml['B80'],0)}, compared with
{number(w['B80'],0)} for width acquisition. The complete coverage curves,
pair and household summaries are supplied; a mean-cost gain does not imply
that one policy has higher coverage at every budget.

There are {mo['no_finite_strict_oracle_cases']:,} cases without a finite strict
hindsight certificate, {ml['unresolved']:,} unresolved final ML-guided cases and
{ml['numerical_ties']:,} numerical-tie stops in this primary population.
Such cases remain in coverage denominators; ratios, if needed, explicitly
use the common strictly certifiable stratum rather than hiding these cases.
All issued strict decisions passed the independent reference-sign and
enclosure checks. At the later archive cutoff,
{run['late_strict_certified']:,} of {summary['case_count']:,} comparisons are
strictly certified using direct forecast copies with zero paid requests.
The timing rule is constructed; no production arrival times or transaction
prices were measured.

Planning-time logs are descriptive implementation measurements on a shared
host. The reference singleton-width kernel also computes unused probability
scores, so these logs do not establish optimized runtime dominance. The
separate compact-solver scaling experiment retains its original timing and
memory definitions.

\subsection{{Earlier batch experiment and development diagnosis}}
The earlier external experiment is retained in
Appendix~\ref{{app:external-batch-results}}. Every policy needed four
readings for 80\% conditional coverage, and its predeclared 15\% reduction
criterion failed. The decision-directed revision does not change that
outcome. In development, switching all policies to individual-read stopping
already lowers the width baseline's mean from 2.4208 to 1.8065; the
uniform-simplex decision rule reaches 1.7939, and the selected ML-guided
rule reaches 1.7806. Most of the gain over two-reading batches is therefore
available from ordinary sequential stopping, rather than the new score.
Appendix~\ref{{app:decision-development}} retains every concentration and
the development-only hindsight diagnosis. These were used to design the
new confirmation, not counted as independent evidence for it.
'''
    return text,success

def abstract_text(summary,oracle,success):
    s=lookup(summary['summaries'],'initially_uncertified');o=lookup(oracle['summaries'],'initially_uncertified')
    ml=s['ml_decision'];mo=o['ml_decision'];wo=o['width_one'];r=summary['relative_mean_reduction']
    direction='lower' if r>=0 else 'higher'
    acquisition_finding=('only a small incremental acquisition benefit' if 0<=r<=.02 else
                         'an incremental acquisition benefit' if r>0 else 'higher acquisition cost')
    return rf'''Auditing machine-learning forecasts with incomplete verification targets requires distinguishing observed accuracy from conclusions valid for every admissible completion. We derive sharp paired squared-loss bounds for nonnegative targets constrained by disjoint aggregate totals. Our main contribution is an exact endpoint-conditioned representation of budgeted recovery: a weighted pricing oracle and compact linear program generate randomized batches respecting the query budget on every draw, with the hidden record fixed beforehand. Deterministic recovery reduces to sorted windows and budget allocation; deterministic adaptation cannot improve its minimax width. For one block with $m$ missing and $r\geq2$ retained coordinates, the deterministic-to-randomized worst-expected-width ratio is at most $m/r$ when both optima are positive; separated clusters attain the bound when $r$ divides $m$. Across 28 synthetic instances, all compact runs complete, with numerical agreement in 12 eligible exhaustive comparisons. A 48-coordinate, 24-query setting contains more than 32 trillion possible batches. In the Portugal archive-aware six-hour-gap setting, paired bounds certify 478 of 540 whole-period comparisons, versus 64 using separately bounded individual losses, with identical information and no additional queries. A confirmation on {summary['eligible_households']} previously unfitted consumers finds {acquisition_finding} from machine-learning guidance over ordinary one-query width acquisition. Later forecast copies eliminate recovery in that confirmation, and robust randomization worsens realized width in the historical audit. The results establish exact structured recovery and its limits.'''

def development_text(development,uniform,dev_oracle):
    lines=[]
    for r in development['summaries']:
        if r['subgroup']=='all':
            lines.append(f"{r['kappa']:g} & {r['macro_mean_requests']:.4f} & {number(r['B80'],0)} & {100*r['coverage'][1]:.2f} & {100*r['coverage'][2]:.2f}\\\\")
    return r'''\section{Decision-Acquisition Development and Limits}\label{app:decision-development}
All 26,910 original validation comparisons from 20 consumers are development
data for this revision; 11,246 are initially uncertified. No test outcome
is used to select the concentration. The predefined grid below is evaluated
without outcome-based replacement or additional tuning; its minimum
household-macro mean selects $\kappa=4$.

\begin{table}[htbp]
\centering\small
\caption{Complete development concentration grid. Cost and coverage use
the initially uncertified population with equal household weights. These
are development outcomes, not untouched confirmation results.}
\label{tab:decision-development}
\begin{tabular}{rrrrr}
\toprule
$\kappa$ & Mean requests & $B_{80}$ & Coverage at 1 (\%) & Coverage at 2 (\%)\\
\midrule
'''+ '\n'.join(lines)+r'''
\bottomrule
\end{tabular}
\end{table}

The uniform-simplex decision rule averages 1.7939 requests versus 1.8065
for the ordinary one-query width baseline; both have $B_{80}=3$.
The hindsight minimum averages 1.6805. Thus even a clairvoyant rule cannot
reduce this baseline's mean by 15\% on the same weighted development panel.
This finding motivated a new finite-panel efficiency endpoint before the
new-consumer confirmation. The unrun proposal to use a 15\% mean-cost
criterion is archived; it is not presented as a completed prespecified test.
The completed earlier 15\% $B_{80}$ test remains a separate failed result.
The simple 300-case prefix pilot, full development curves and every
concentration's per-case outputs are retained in the supplement.

'''

def integrate(base,theory,oracle_theory,worstcase,summary,oracle,run,development,uniform,dev_oracle):
    text=base
    old_title=re.search(r'\\title\{[^\n]+\}',text).group()
    text=one_replace(text,old_title,r'\title{Exact Algorithms and Limits for Auditing Machine-Learning Forecasts with Aggregate Targets}')
    results,success=result_text(summary,oracle,run)
    abstract=abstract_text(summary,oracle,success)
    text=re.sub(r'(?s)\\begin\{abstract\}.*?\\end\{abstract\}',lambda m:'\\begin{abstract}\n'+abstract+'\n\\end{abstract}',text,count=1)
    text=re.sub(r'(?s)\\noindent\\textbf\{Keywords:\}.*?\n\n',lambda m:r'\noindent\textbf{Keywords:} artificial intelligence; machine learning; model evaluation;'+ '\n'+r'randomized algorithms; robust optimization; partial identification.'+'\n\n',text,count=1)
    text=one_replace(text,'Evaluating a fixed machine-learning forecast requires verification targets',
                     'Auditing artificial intelligence forecasts requires verification targets')
    text=one_replace(text,'Model-based acquisition comparators may use a fitted surrogate.',
                     'Model-based acquisition, including the decision-directed rule below, uses a fitted surrogate to select queries; its final certificate remains independent of that surrogate.')
    text=one_replace(text,'Its three results distinguish established optimization',
                     'Its results distinguish established optimization')
    text=one_replace(text,'The main contribution is an exact recovery method for this structured\nevaluation problem.',
                     'The main contribution is an exact representation of the structured\nrecovery game, including its endpoint-conditioned pricing rule, executable\nrandomized batches and tight comparison with deterministic adaptive queries.')
    text=one_replace(text,'On the frozen LCL test,',
                     'In the earlier Low Carbon London (LCL) two-reading-batch experiment,')
    anchor='Separated clusters attain this bound when $r$ divides $m$.\n\\end{enumerate}'
    text=one_replace(text,anchor,'Separated clusters attain this bound when $r$ divides $m$.\n'+r'\end{enumerate}'+'\n'+
                     r'The deterministic benchmark includes adaptive policies; the randomized'+'\n'+
                     r'result concerns nonadaptive batches. No optimality among randomized'+'\n'+
                     r'adaptive policies, overlapping aggregates or heterogeneous query costs'+'\n'+
                     r'is claimed.'+'\n\n'+
                     r'A supporting decision-directed extension has a closed-form one-query certification'+ '\n'+
                     r'probability under a declared Dirichlet surrogate. A new-consumer evaluation'+ '\n'+
                     r'compares executable stopping costs with every baseline and an exhaustive'+ '\n'+
                     r'hindsight lower bound; this separates algorithmic benefit from limited'+ '\n'+
                     r'remaining query headroom.'+'\n')
    text=one_replace(text,'uses exact totals; neither recovery objective maximizes empirical certification.',
                     'uses exact totals; neither robust-width objective maximizes empirical certification. The separate decision-directed score targets one-query certification probability and does not claim global stopping optimality.')
    oldroad='The experiments lead with the external\ndeadline evaluation; historical archive attribution, adverse randomized'
    text=one_replace(text,oldroad,'The experiments lead with a frozen new-consumer\ndecision-acquisition confirmation, followed by the earlier external\ndeadline evaluation; historical archive attribution, adverse randomized')
    cite=r'''Decision-oriented acquisition is itself established. Javdani et al.~\cite{javdani2014}
study Bayesian tests that place every remaining hypothesis in a common
decision region, with an expected-cost objective. Our specialized score
integrates the post-query sign region of an aggregate-constrained regression
contrast; no general invention of decision-aware active learning is claimed.

'''
    text=one_replace(text,r'\section{Observation Model and Evaluation Target}',cite+r'\section{Observation Model and Evaluation Target}')
    classic=r'''Compact formulations obtained from dynamic programs are established:
Martin et al.~\cite{martin1990} give polyhedral representations using
acyclic hyperflows. Our budget-flow construction uses this general
optimization principle. Its problem-specific content is the retained-endpoint
conditioning and interior inclusion constraints that preserve exactly the
mass-times-range recovery objective, together with the matching one-block
randomization bound. Compactness alone is not a claim of a new general
optimization paradigm or a measured speedup over another compact solver.

'''
    text=one_replace(text,r'\section{Observation Model and Evaluation Target}',classic+r'\section{Observation Model and Evaluation Target}')
    text=one_replace(text,r'\section{Budgeted Recovery of Missing Readings}',theory+'\n'+oracle_theory+'\n'+r'\section{Budgeted Recovery of Missing Readings}')
    design=r'''\subsection{Development-selected policy and new-consumer confirmation}\label{sec:decision-confirmation-design}
After the earlier two-reading experiment, we diagnose the mismatch between
batch-width optimization and decision cost on the original validation panel.
All policies then receive one query per step and the same certificate.
The ML-guided concentration is selected from $\{0.5,1,2,4,8,16\}$ by the
lowest development household-macro mean requests, with smaller concentration
breaking an exact tie; $\kappa=4$ is frozen before new model fitting.

The next 20 training-eligible consumers among the previously inventoried
lowest 100 IDs, excluding the original 20, are selected without outcome
substitution. Their source-quality counts were already known, but they had
no fitted models or evaluated acquisition outcomes. This is new-consumer
confirmation within the same London source and calendar, not an untouched
metering infrastructure or prospective outage study. The causal forecast
specifications, chronological splits, three mask seeds, totals and early/late
archive rules are unchanged; each new consumer receives separately fitted
models. Ridge regression, histogram gradient boosting and a multilayer
perceptron produce 60 new fits; a persistence baseline completes the
four-model comparison. ML-guided and uniform-simplex decision policies are compared with
singleton width, Hara, uniform and randomized-width acquisition. Exact and
greedy width choices coincide at one query, so one common baseline is shown.

The new primary endpoint is mean charged requests divided by the matched
hindsight minimum, with equal household weights among initially uncertified
cases. The pre-confirmation criterion is ratio at most 1.10, no incorrect
strict certificates and complete strict coverage at the cap. It was chosen
after development showed that even clairvoyant selection could not improve
the fair width baseline's mean by 15\%. The width baseline itself already
met the 1.10 development ratio. Consequently this criterion tests efficient
certified acquisition, not an advantage exclusive to the new policy.
It neither revises nor passes the earlier 15\% $B_{80}$ hypothesis.
The full protocol and archived unrun mean-improvement proposal are supplied.

Every policy's ratio, mean, coverage curve and $B_{80}$ is reported.
Cases lacking a finite strict hindsight certificate remain in all-case
coverage, and any ratio on a certifiable stratum is explicitly identified.
Two thousand paired household bootstrap resamples, seed 8241, describe
panel stability; they are not representative-population uncertainty.
The secondary relative saving compares with the better width/Hara mean,
reselected within each bootstrap draw. Randomized results retain three
seeded paths per day, not exact expectations of adaptive stopping cost.

'''
    text=one_replace(text,r'\subsection{Historical evidence and reproducibility}',design+r'\subsection{Historical evidence and reproducibility}')
    text=one_replace(text,r'\subsection{Executable stopping policies and equal information}',
                     r'\subsection{Earlier batch policies and equal information}')
    text=one_replace(text,'policy excludes already determined and contrast-irrelevant coordinates\nfrom its acquisition candidates under the same rule. Each',
                     r'''policy uses the following block-level eligibility rule, also used by the
single-reading confirmation. After free deductions, retain every unknown
coordinate in a block with positive residual total, at least two unknowns,
and nonconstant remaining contrast coefficients. In particular, an
individual zero coefficient does not make a coordinate ineligible.
Surrogate scores may still assign an eligible coordinate zero selection
probability; eligibility and policy preference are distinct. Each''')
    batch_rule=r'''The simultaneous batch obeys
$|Q\cap\mathcal M_g|\leq m_g-1$ in every exact-total block, where
$m_g=|\mathcal M_g|$ after free deductions. The last unknown value would
otherwise be purchased despite being determined by the total and other
answers. The stage limit is at most two, not mandatory two-query spending:
equal-width optima can use fewer queries, and a policy can stop constructing
a batch when the remaining coefficients become constant. All returned
coordinates are charged before the comparison is tested. An independent
audit of all 129,718 saved earlier-experiment batches found no violation;
the two batches smaller than their initial count-only capacity had already
made the residual contrast constant. The one-query confirmation reapplies
free closure after every answer. Supporting fixtures are supplied in
Online Resource~1.

'''
    text=one_replace(text,'The Hara-inspired proposal adapts the squared-loss comparison weight',
                     batch_rule+'The Hara-inspired proposal adapts the squared-loss comparison weight')
    text=one_replace(text,'width, we select the lexicographically first feasible full batch with the\nsame primary optimum.',
                     r'''width, we select the lexicographically first batch of the largest feasible
cardinality up to the current stage limit, with the same primary optimum.
This maximum-cardinality refinement applies to that empty-optimum fallback,
not to every returned batch.''')
    text=one_replace(text,r'\subsection{Predeclared decision-cost outcomes}',
                     r'\subsection{Earlier batch experiment: predeclared outcomes}')
    start=text.index(r'\subsection{External decision-cost evidence}')
    end=text.index(r'\subsection{Historical archive evidence and attribution}',start)
    previous_results=text[start:end]
    text=text[:start]+results+'\n'+text[end:]
    discussion=r'''\subsection{Decision efficiency and the remaining practical boundary}
The revised experiment asks whether a valid decision can be reached close
to the minimum number of readings that the completed record would permit.
Proximity to this hindsight bound gives a finite-panel cost guarantee
against every correctly certifying policy on the same weighted records.
It does not make the oracle executable or imply a population-wide ratio.
The ordinary singleton width policy is reported alongside the learned rule;
shared efficiency limits the scope for a large additional algorithmic gain.
The learned score remains a surrogate objective, and observed coverage
curves need not be ordered at every budget. An empirically correct imputed
ranking and an all-completions certificate answer different questions.
Neither the cost ratio nor the certificate establishes improved downstream
forecast accuracy, observed retrieval economics or a production deadline.

'''
    text=one_replace(text,r'\section{Discussion}',r'\section{Discussion}'+'\n'+discussion)
    text=one_replace(text,r'\subsection{What the external decision-cost result establishes}',
                     r'\subsection{What the earlier batch experiment establishes}')
    text=text.replace('The external benchmark evaluates\nrepeated batch acquisition with stopping, without claiming that its full',
                      'The earlier external benchmark evaluates repeated batch acquisition, and\nthe new-consumer benchmark evaluates single-reading acquisition with stopping. Neither full')
    # The sentence continuation is adjusted without changing existing mathematical material.
    text=text.replace('Neither full\nsequence minimizes the total requests needed for a decision.',
                      'Neither full\nsequence is claimed to minimize the total requests needed for a decision.')
    old_start=text.index(r'\section{Conclusion}')
    old_end=text.index(r'\FloatBarrier',old_start)
    conclusion=r'''\section{Conclusion}
The aggregate-constrained recovery problem admits exact deterministic and
randomized algorithms despite the combinatorial number of possible query
batches. Retained-endpoint conditioning yields a compact representation and
an executable distribution satisfying the budget on every draw. Together
with the deterministic adaptivity identity and sharp one-block randomization
ratio, these results characterize what recovery can guarantee for this
structured model-evaluation problem. They specialize established robust
optimization and extended-formulation principles to the stated geometry.

The empirical studies identify the limits of the application as well as
its feasibility. Saved forecasts often resolve targets without acquisition;
the machine-learning-guided score offers a small advantage over an already
efficient baseline, and robust randomization can worsen realized uncertainty.
The earlier failed budget target is retained. Thus the supported practical
use is a defensible model-comparison certificate under declared information
and record budgets, rather than demonstrated substantial retrieval savings.
Source reconstruction, scaling measurements, complete acquisition traces
and executable checks support these claims within their stated scope.
'''
    text=text[:old_start]+conclusion+'\n'+text[old_end:]
    appendix=(development_text(development,uniform,dev_oracle)+worstcase+'\n'+
              r'\section{Earlier External Batch Evaluation}\label{app:external-batch-results}'+'\n'+previous_results+'\n')
    text=one_replace(text,r'\appendix',r'\appendix'+'\n'+appendix)
    supplement=r'''The present decision-acquisition revision is reproduced with
\texttt{python} \path{work/reproduce_decision_revision.py}. Its default route
checks the new source records, independently verifies confirmation trajectories
and exhaustive hindsight subsets, and rebuilds the present manuscript.
The \texttt{--development} option also checks the complete original validation
selection grid; \texttt{--legacy} adds the earlier external replay.
The \texttt{--refit} option runs new model fitting and confirmation in an
isolated stage, and \texttt{--small} runs mathematical fixtures. Replaying
saved forecasts does not constitute a fresh fit or external investigator
replication. The release pins every composition input and preserves earlier
negative outcomes and protocol amendments.
The independent randomized check verifies finite-game objectives and mixture
moments and support; it does not replay the compact sampler's exact random
draw. The complete sampler is supplied, and the fresh-fit route reruns its
acquisition.

The later query-eligibility review supplies an exact-rational
zero-coefficient fixture, calls to every production policy and the actual
hindsight driver, a complete audit of the earlier saved batches, and
synthetic batch-feasibility checks. Run
\texttt{python} \path{work/eligibility_review_20261011/check_review.py}.
These checks clarify eligibility and accounting; they do not refit models
or replace an empirical result. The associated diagnostic scripts explain
the small learned-policy gain from the already evaluated confirmation
traces and are explicitly retrospective.

'''
    text=one_replace(text,r'\section*{Supplementary Materials}',r'\section*{Supplementary Materials}'+'\n'+supplement)
    text=text.replace('The entry point for the present external revision is','The entry point for the preceding external revision is')
    text=text.replace('trajectories and summaries, and reconstructs this manuscript in an isolated',
                      'trajectories and summaries, and reconstructs its earlier manuscript in an isolated')
    text=text.replace('The external-revision entry point above\nrebuilds the present manuscript.',
                      'The decision-revision entry point above rebuilds the present manuscript.')
    bib=r'''\bibitem{javdani2014} S. Javdani, Y. Chen, A. Karbasi, A. Krause,
D. Bagnell, and S. Srinivasa, ``Near Optimal Bayesian Active Learning for
Decision Making,'' in \emph{Proceedings of the Seventeenth International
Conference on Artificial Intelligence and Statistics}, \emph{Proceedings
of Machine Learning Research}, vol.~33, pp.~430--438, 2014.
\url{https://proceedings.mlr.press/v33/javdani14.html}.
'''
    bib+=r'''\bibitem{martin1990} R. K. Martin, R. L. Rardin, and B. A. Campbell,
``Polyhedral Characterization of Discrete Dynamic Programming,''
\emph{Operations Research}, vol.~38, no.~1, pp.~127--138, 1990.
\url{https://doi.org/10.1287/opre.38.1.127}.
'''
    text=one_replace(text,r'\end{thebibliography}',bib+r'\end{thebibliography}')
    return '% Decision acquisition editorial integration v1\n'+text,{'primary_criterion_met':success,'abstract_rough_words':len(re.findall(r"\b[\w]+(?:[-'][\w]+)*\b",abstract))}
