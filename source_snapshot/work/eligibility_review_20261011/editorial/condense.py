"""Pure main-text consolidation; no scientific evidence or formal block edits.

Apply condense(text) AFTER the decision integrator and current review repairs.
The function returns TeX and does not read or write any manuscript.
"""
import re

MARKER='% Main-text consolidation: eligibility review 20261011'

DECISION_OVERVIEW=r'''\subsection{Supporting decision-directed acquisition}
The bounds also permit acquisition aimed at a model decision rather than
interval width. A separate machine-learning-guided rule integrates the
post-query strict-certificate event under a Ridge-centred Dirichlet
surrogate. Its parameters are fixed before acquisition; the final
all-completions certificate continues to use the original measurement
constraints. Maximizing this score optimizes its one-query surrogate
utility, not general sequential stopping cost. The formal probability
formula, its restricted small-instance cost result, and a counterexample
separating probability from width optimization are retained in
Appendix~\ref{app:supporting-decision-theory}.

The same appendix defines a hindsight certificate-cost lower bound by
exhaustive subsets of the completed reference record. It is a diagnostic
benchmark, not an executable query policy. Comparing every method with
this common bound distinguishes an algorithmic improvement from limited
remaining acquisition headroom. The confirmation evaluates the learned
rule alongside ordinary width acquisition and other matched comparators.

'''

RELATED_OVERVIEW=r'''\section{Related Work and Contribution Boundary}
Partial identification already studies conclusions that survive incomplete
observations \cite{manski,polo}; probabilistic observation models address
imperfect verification \cite{bessac}. Squared-loss cancellation is an
instance of the established paired-loss structure discussed by Patton
\cite{patton}. Energy-constrained imputation and disaggregation also predate
this work \cite{cpi,hu,heat}. Our target is the extreme difference between
two fixed forecasts over all measurement-compatible completions, rather
than one plausible reconstructed trajectory. The sharp formulas are a
starting point for the recovery problem, not a claim to invent partial
identification or conservation-based reconstruction.

Active evaluation acquires labels to assess fixed predictors.
Sawade et al.\ \cite{sawade} optimize asymptotic comparison power;
Hara et al.\ \cite{hara} reduce variance of estimated loss differences.
Decision-region acquisition with expected-cost objectives is established
\cite{javdani2014}, as are active testing and pretrained classifier
selection \cite{active,okanovic2025}. These objectives differ from our
worst remaining range of a fixed-record contrast under disjoint exact
totals. The empirical Hara comparator is a declared regression adaptation,
not a replication of its original classification experiment. The learned
one-query extension supplies a specialized score and a matched comparison;
it does not establish general superiority over active evaluation.

Robust information discovery and optimization after queries are also
established \cite{ddid,chen2026}. Randomized combinatorial optimization
admits general oracle and separation frameworks \cite{kawase2024}.
The deterministic retained-window subproblem uses classical
minimum-diameter geometry \cite{aggarwal}; budget allocation uses dynamic
programming. Martin et al.\ \cite{martin1990} establish polyhedral
representations of discrete dynamic programs through acyclic hyperflows.
Consequently a compact flow formulation alone is not a new optimization
paradigm. The specialized content here is the endpoint-conditioned
representation preserving the mass-times-range objective, its weighted
pricing oracle and executable hard-budget distribution, together with
the deterministic adaptivity identity and tight one-block randomization
gap.

Secondary optimization of robust optima follows established concerns
about dominated solutions \cite{iancu2014}. We specify such a rule and
evaluate its effect rather than claiming the principle as new. The
deterministic guarantee covers adaptive policies, whereas the randomized
result concerns nonadaptive batches with the hidden record fixed before
the draw. It does not cover arbitrary measurement constraints or an
optimal randomized adaptive strategy. Table~\ref{tab:closest-work}
compares the nearest settings under their respective assumptions;
Appendix~\ref{app:extended-related-work} retains the complete literature
discussion. Mathematical exactness does not make these distinct problems
one empirical benchmark or imply that one method dominates the others.

'''

WORKFLOW_OVERVIEW=r'''\section{Evaluation Design}
\label{sec:evaluation-overview}
Low Carbon London (LCL) supplies public half-hour readings \cite{lcl}.
The benchmark evaluates persistence and fits Ridge regression, histogram
gradient boosting and multilayer-perceptron forecasters using the declared
January--September 2013 training period, October--December validation
period and January--February 2014 test period. Household selection uses
training availability among the lowest 100 source IDs. The earlier batch
experiment and subsequent confirmation select separate sets of 20;
19 in the latter have eligible test days, without outcome-based
replacement. The confirmation's 60 learned-model fits use unchanged
specifications. Source-quality counts were already known: this is
new-consumer evaluation within the same source and calendar, not an
untouched infrastructure or prospective outage study.

Each eligible day has four constructed exact six-hour totals and one
masked six-hour gap under three fixed streams. The same surviving
readings, totals and permitted forecasts reach every policy. The early
benchmark audit occurs at the start of day $D+1$, before any issued
forecast uses target day $D$ as a lag. At noon on $D+1$, persistence
forecasts for $D+2$ supply every target in $D$. Their saved values and
source traces provide free reconstruction. These issue times are declared
benchmark coordinates; source timezone conventions and production arrival
or repair times are not established. The experiment models an incomplete
audit export, not a physical failure shared by the forecast service.

Before acquisition, permitted copies, singleton residuals and zero-total
deductions are incorporated. An active block has positive residual total,
at least two unknown coordinates, and remaining contrast coefficients
that are not all equal. Every unknown coordinate in that block is
eligible, including an individual zero-coefficient coordinate; a policy's
score may still assign it zero selection probability. For a simultaneous
batch, each block with $m_g$ remaining unknowns satisfies
$|Q_g|\leq m_g-1$, avoiding a paid final reading already implied by its
total. Earlier policies request at most two readings per stage; all six
confirmation policies request one and apply free deductions between
requests. All stop at a certificate, numerical tie or six charged
readings. Costs are individual hourly records for one fixed model pair,
not shared requests across six pairs, network transactions or money.

The earlier experiment's predeclared 15\% improvement in the budget
needed for 80\% coverage failed and remains reported. The supporting
learned policy selects its Dirichlet concentration on development data
and freezes it before new fitting. The later primary criterion---mean
requests at most 1.10 times the matched hindsight minimum, complete
strict coverage and no incorrect decisions---was chosen after the
development headroom diagnosis. Ordinary width acquisition already met
that development ratio. Every comparator is therefore reported; this
criterion is not exclusive evidence for the learned rule. Equal-household
summaries and descriptive paired-household bootstrap intervals retain
initially uncertified cases and disclose any noncertifiable cases.

Appendix~\ref{app:detailed-decision-protocol} preserves source screening,
chronology, proposals, stopping conventions and the full endpoint history.
Historical energy and natural-accumulation analyses provide complementary
evidence under their own stated archives. Checks use binary64 arithmetic
with declared tolerances, not outward-rounded arithmetic certification.
The supplement distinguishes saved-forecast replay, source reconstruction
and model refitting; independently implemented checks remain within-study
verification rather than external investigator replication.

'''

DISCUSSION_OVERVIEW=r'''\section{Discussion}
The contribution is an exact solution and characterization of a
structured recovery problem. Endpoint conditioning and the weighted
pricing oracle give an executable compact randomized policy; the
deterministic adaptivity identity and tight one-block gap describe what
these methods can guarantee. These results specialize established
optimization principles to disjoint aggregate constraints. Their value
is a defensible fixed-record comparison and a precise account of
remaining uncertainty. They do not establish a general new forecasting
architecture, a universal label-acquisition strategy or substantial
retrieval savings. The scaling evidence establishes computational
operability over the measured cases, subject to its single-run timing
and memory limitations.

The application evidence must be read alongside those limits. The
learned rule uses 0.97\% fewer readings than ordinary singleton width
acquisition; both are close to the matched hindsight lower bound. Their
shared efficiency leaves little observed headroom for a large additional
gain, and the learned rule's ratio interval crosses 1.10. The earlier
15\% budget-improvement criterion failed. Later persistence copies
eliminate recovery in the confirmation and remove most masked targets
in the historical archive. Robust randomization improves worst expected
width but worsens realized width and certification; neither of the two
tested target-independent secondary rules removed the observed tradeoff.
The historical donor
already makes no whole-period ranking errors at full coverage. An
all-completions certificate therefore adds a conditional defensibility
guarantee, not demonstrated superiority in observed ranking accuracy.
Natural rainfall accumulations illustrate zero-query identification,
but do not validate target retrieval or its economics. The full
interpretation, including unfavorable conservative-regret results,
remains in Appendix~\ref{app:extended-interpretation}.

A practical audit first declares its target window, available archive,
surviving readings and aggregate constraints, then incorporates verified
free reconstruction. If individual targets can subsequently be retrieved,
the method can select a batch and recompute its certificate after the
answers arrive. Record counts are pair-specific; shared recovery across
models, whole-gap retrieval and actual transaction costs require separate
accounting. No production arrival or repair timestamps were measured.
Constructed outages, totals and access cutoffs test a computational
workflow, while complete-record eligibility and convenience cohorts
limit generalization. The trained models supply reproducible artificial
intelligence comparisons rather than a claim of state-of-the-art
forecast accuracy. The surrogate guides acquisition without narrowing
the final feasible set, but does not make the full stopping sequence
optimal. The exact recovery reductions rely on nonnegative targets,
disjoint totals and unit query costs; randomized results use exact totals.
Recovery guarantees for overlapping constraints, uncertain answers,
physical caps, unequal costs and randomized adaptation are not established
here. Mathematical sharpness does not validate measurements,
and numerical residual checks are not formal floating-point enclosures.

\FloatBarrier
'''

def _unique_index(text,needle):
    if text.count(needle)!=1:
        raise ValueError('Expected one stable consolidation anchor: '+needle)
    return text.index(needle)

def _take(text,start,end):
    lo=_unique_index(text,start);hi=_unique_index(text,end)
    if hi<=lo:raise ValueError('Reversed consolidation anchors')
    return text[lo:hi]

def condense(text):
    """Return consolidated TeX; preserve all relocated body text verbatim."""
    if MARKER in text:raise ValueError('Do not consolidate a consolidated manuscript')
    stop=r'\subsection{Stopping when a model choice is justified}'
    recovery=r'\section{Budgeted Recovery of Missing Readings}'
    theory=_take(text,stop,recovery)
    related_start=r'\section{Related Work and Contribution Boundary}'
    related=_take(text,related_start,r'\section{Observation Model and Evaluation Target}')
    tables=list(re.finditer(r'\\begin\{table\}.*?\\end\{table\}',related,re.S))
    if len(tables)!=1 or r'\label{tab:closest-work}' not in tables[0].group():
        raise ValueError('Expected the unique closest-work table')
    table=tables[0].group()
    survey=related.replace(table,'',1)
    survey=survey.replace(related_start,r'\section{Extended Related Work}\label{app:extended-related-work}',1)
    workflow_start=r'\section{Decision Workflow and External Evaluation}'
    workflow=_take(text,workflow_start,r'\section{Results}')
    workflow_appendix=workflow.replace(workflow_start,r'\section{Detailed Decision-Acquisition Protocol}\label{app:detailed-decision-protocol}',1)
    discussion=_take(text,r'\section{Discussion}',r'\section{Conclusion}')
    discussion_appendix=discussion.replace(r'\section{Discussion}',r'\section{Extended Interpretation and Limits}\label{app:extended-interpretation}',1)
    text=text.replace(theory,DECISION_OVERVIEW,1)
    text=text.replace(related,RELATED_OVERVIEW+table+'\n\n',1)
    text=text.replace(workflow,WORKFLOW_OVERVIEW,1)
    text=text.replace(discussion,DISCUSSION_OVERVIEW,1)
    # Match the evidence hierarchy to the specialized optimization contribution.
    headings=[r'\subsection{'+s+'}' for s in [
        'New-consumer decision-acquisition confirmation',
        'Earlier batch experiment and development diagnosis',
        'Historical archive evidence and attribution',
        'Historical robust gain and adverse realized tradeoff',
        'Runtime and memory of compact randomized recovery',
        'Naturally accumulated records without fine-resolution truth']]
    results=_take(text,headings[0],r'\section{Discussion}')
    parts=[_take(text,h,headings[i+1] if i+1<len(headings) else r'\section{Discussion}')
           for i,h in enumerate(headings)]
    text=text.replace(results,''.join(parts[i] for i in [4,2,3,5,0,1]),1)
    scaling_anchor='All 560 sampled-policy checks pass.'
    _unique_index(text,scaling_anchor)
    text=text.replace(scaling_anchor,scaling_anchor+r'''
For the two $m=48$, $B=24$ profiles, $\binom{48}{24}=32{,}247{,}603{,}683{,}100$
fixed-size batches are represented by 10,076 linear-program variables.
Their measured method times are 0.606--1.631 seconds with approximately
97.3\,MiB peak worker memory. The batch count is not a measured speedup,
evidence of computational hardness, or a comparison with another compact
formulation.''',1)
    appendix=(r'\section{Supporting Decision-Acquisition Theory}\label{app:supporting-decision-theory}'+'\n'+theory+
              '\n\\FloatBarrier\n'+workflow_appendix+'\n\\FloatBarrier\n'+survey+
              '\n\\FloatBarrier\n'+discussion_appendix+'\n\\FloatBarrier\n')
    _unique_index(text,r'\appendix')
    text=text.replace(r'\appendix',r'\appendix'+'\n'+appendix,1)
    return MARKER+'\n'+text
