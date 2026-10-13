"""Proposed editorial-only integration. No file is changed when run directly.

Root may import apply_editorial_trim after coordinating the source change.
Preserves all proofs, data tables, plots, results, protocol details and citations.
The fresh-refit discussion must be reviewed separately before integration.
"""
from pathlib import Path
import hashlib
import json
import re

INTRODUCTION = r'''\section{Introduction}
Evaluating a fixed machine-learning forecast requires verification targets
as well as saved predictions. When targets are missing, deletion changes
the evaluated record and imputation makes its score depend on a chosen
completion. Production monitoring systems explicitly join predictions to
subsequently collected actuals \cite{azuremonitor,awsmonitor}. The question
here is which model comparisons follow from the available measurements
alone, and which additional targets would most reduce the remaining ambiguity.
The audit operates on saved predictions; it requires neither model gradients
nor an additional fitted missing-shape model.

Aggregate observations provide useful constraints without specifying that
shape. Differences between cumulative meter readings constrain the energy
within their interval \cite{canada}. NorPEN documents missing high-frequency
transmissions alongside more reliably collected hourly billing registers
\cite{norpen}. Elexon's procedures reconcile interval sums with register
advances and recover a missing interval from the advance and the other
readings \cite{elexon}; AEMO provides for replacing substituted readings
when actual data are recovered \cite{aemo}. These sources motivate retained
totals and subsequent correction. They do not establish that exact totals
survive every outage, or that selectively retrieving individual readings
is cheaper than retrieving an entire gap.

We represent the unknown targets by a common feasible set of nonnegative
values consistent with the observed readings and disjoint aggregate totals.
A strict forecast ordering is established only if every feasible completion
gives that ordering. For squared error, the unknown squared target cancels
from the paired loss difference, leaving a linear objective. Sharp extrema
then depend on the residual energy and the range of forecast disagreement
within each block. Thus a large missing fraction can still permit a decision,
while a small gap can remain consequential.

The main contribution is an exact recovery method for this structured
evaluation problem. Its three results distinguish established optimization
tools from the specialized reductions developed here:
\begin{enumerate}
\item Deterministic worst-width recovery reduces to sorted retained windows
and budget allocation across blocks. A zero-answer argument shows that
deterministic adaptation cannot improve this minimax value.
\item Randomized recovery admits an exact weighted-endpoint pricing oracle
and a compact budget-flow linear program. The solution generates executable
batches satisfying a hard reading budget without enumerating all query
subsets. The hidden record is fixed before the random draw.
\item For one block with $m$ missing and $r\geq2$ retained coordinates and positive optima,
the deterministic-to-randomized worst-expected-width ratio is at most $m/r$.
Separated clusters attain this bound when $r$ divides $m$.
\end{enumerate}
The deterministic extension to independently bounded totals and a secondary
minimax-regret option are retained in the appendices. The randomized theory
uses exact totals; neither recovery objective maximizes empirical certification.

The experiments test both the applicability and the limits of these results.
In the energy audit, permitted direct copies from the saved forecast archive
reconstruct most masked targets before recovery, leaving a small incremental
certification benefit from exact rather than greedy allocation. Randomization
improves its robust objective but worsens observed expected width; this
tradeoff persists under target-independent secondary optimization and on
additional consumers. Naturally accumulated precipitation records provide
a separate zero-query application: some comparisons follow from surviving
totals even though individual forecast scores are not identified.

The practical output is therefore a defensible comparison interval and an
exactly optimized recovery policy for a stated uncertainty criterion.
The evidence does not establish general ranking-accuracy superiority over
imputation or measured retrieval savings. The following sections define the
observation model, derive deterministic recovery, and develop the randomized
method in Section~\ref{sec:randomized-recovery}. The results lead with the
archive-consistent audit; the appendices preserve the restricted-record
experiments and supporting designs.

'''

DISCUSSION = r'''\section{Discussion}
The methodological result is exact optimization of the uncertainty left in
a fixed-record model comparison. Shared-target cancellation makes the
comparison linear; sorted windows solve deterministic recovery; weighted
endpoints and a compact flow representation make randomized batch recovery
tractable without enumerating its query subsets. The deterministic adaptivity
identity and sharp one-block randomization gap characterize what these
policies can guarantee. The synthetic scaling study establishes operability
across the reported sizes and budgets, while retaining the limits of its
single-run timing and memory measurements.

For an applied evaluator, the comparison interval can accompany an existing
imputed score. If it excludes zero, the ordering is supported by every
completion in the declared set; if it straddles zero, witness completions
show exactly why the available information does not determine the winner.
This distinction matters even when an imputer performs well on the observed
record. The historical donor makes no full-period errors in the reported
archive-aware exact-total grid at full coverage. The experiment therefore
supports a conditional defensibility guarantee, not superiority in observed
whole-period ranking accuracy. The conservative selector likewise has worse
Portugal mean normalized realized regret than the donor (1.549 versus 0.195,
both multiplied by $10^3$); Appendix~\ref{app:regret} retains the complete
tradeoff.

The information available to the evaluator determines how much recovery
can add. Later persistence forecasts directly reveal most masked energy
targets in this historical archive. The large restricted-record recovery
gains describe a different information set; after free reconstruction,
the exact allocator's certification increment over greedy is small.
The additional-consumer analyses reproduce this distinction within the
same source and calendar. Their contribution is evidence about the fixed
procedure, rather than a measurement of field outage prevalence or
production retrieval costs.

Randomization improves worst expected width but does not improve the
observed energy-audit outcomes. The adverse width and certification results
persist under the two specified secondary refinements and the fixed-rule
additional-consumer audit. Section~\ref{sec:tie-selection} explains why a
minimax policy must specify its secondary selection; the contrast family
that follows shows how the same robust policy can help or harm at different
feasible records. Randomized recovery is consequently appropriate when
worst expected ambiguity is the stated objective, not an empirically
dominant replacement for deterministic recovery or imputation.

The rainfall application establishes a narrower positive use: two of nine
naturally accumulated daily records support a strict forecast comparison,
although separately bounded individual scores do not. One survives the
declared total sensitivity. The six ambiguous cases, one exact tie and
unresolved combined-period result remain part of that evidence. The 43
dry controls validate only a degenerate observation case. These records
support zero-query identification without establishing recoverable missing
hourly truth, a general forecast ranking, or a benefit from paid recovery.

\subsection{Operational interpretation}
An operational audit must declare its target window, information cutoff,
prediction archive, observed values and aggregate constraints. Verified
direct target copies and aggregate-determined values are incorporated
before comparing models or selecting queries. The evaluated energy regime
uses documented persistence copies; it does not invert the other fitted
predictors or use unsaved feature caches. Sharpness is relative to this
declared set, not to every possible record in the forecasting system.

If the comparison remains unresolved and a separate source can supply
individual readings, the evaluator can select a batch, validate the returned
values, update residual totals and recompute the interval. The budget is
per model pair and counts readings, not network transactions or staff time.
It provides no retrieval saving when an entire gap is obtained at the same
cost. Shared requests across many pairs, cancellation after an early decision,
and optimal randomized adaptive recovery require different objectives and
evaluations. Actual target-arrival and repair timestamps are absent here,
so decision latency and deployment savings remain unmeasured.

\subsection{Limitations and scope}
The guarantees depend on the measurement model. Energy outages are imposed
retrospectively; UCI totals are constructed from complete traces, and retained
BLEM counter endpoints do not demonstrate an independent backup channel's
survival. Complete-record eligibility, the convenience sample and historical
test calendars limit generalization. The fixed MLP and other forecasters
define reproducible comparisons, rather than state-of-the-art accuracy.
Post-review analyses reuse these records and are not independent prospective
cohorts. Constructed tolerance bands are sensitivity assumptions, not
calibrated measurement-error distributions.

Nonnegative uncapped targets and disjoint totals permit the exact recovery
reductions. Physical caps, overlapping or correlated totals, signed flows,
unequal query costs and uncertain returned readings require their own
constraints and algorithms; the randomized results here use exact totals.
Other losses need not retain squared-error cancellation. Mathematical
sharpness does not validate the measurements, and binary64 checks do not
supply outward-rounded machine-certified enclosures.

\FloatBarrier
'''

RESTRICTED_CAPTIONS = (
    'tab:sensitivity','tab:daily','tab:recovery','tab:width',
    'tab:dailymatched','tab:namedpairs','tab:marginstrata','tab:neural',
    'tab:actualrecovery','tab:recoveryci','tab:regret',
    'fig:operator','fig:dailycoverage','fig:recovery')

def section(text,start,end):
    assert text.count(start)==text.count(end)==1,(start,end)
    left=text.index(start);right=text.index(end,left)
    return text[left:right]

def prefix_caption(text,label,prefix):
    marker=r'\label{'+label+'}'
    assert text.count(marker)==1,label
    position=text.index(marker)
    opening=text.rfind(r'\caption{',0,position)
    assert opening>=0,label
    insertion=opening+len(r'\caption{')
    assert text.find(r'\label{',opening)==position,label
    return text[:insertion]+prefix+text[insertion:]

def apply_editorial_trim(text):
    if '% Editorial consolidation 2026-10-11' in text:
        return text
    old_intro=section(text,r'\section{Introduction}',r'\section{Related Work and Contribution Boundary}')
    old_discussion=section(text,r'\section{Discussion}',r'\section{Conclusion}')
    assert old_intro.startswith('\\section{Introduction}\nEvaluating deployed machine-learning'), 'Introduction changed; review before applying'
    assert old_discussion.startswith('\\section{Discussion}\nThe method provides two connected'), 'Discussion changed; review before applying'
    changed=text.replace(old_intro,INTRODUCTION,1).replace(old_discussion,DISCUSSION,1)
    for label in RESTRICTED_CAPTIONS:
        changed=prefix_caption(changed,label,'Frozen restricted-record daily evaluation; no saved-archive reconstruction. ')
    changed=prefix_caption(changed,'tab:random-results',
        r'Six-hour contiguous gaps, exact six-hour totals, seed 1103, and $B=2$ per day/model pair. ')
    changed=prefix_caption(changed,'tab:recovery-attribution','Three mask seeds. ')
    changed=prefix_caption(changed,'tab:newconsumers','Daily outcomes over three mask seeds. ')
    changed=changed.replace(r'\paragraph{Fixed-rule randomized audit on the held-out consumers.}'+'\n','',1)
    changed=changed.replace(r'\paragraph{Bounded synthetic scaling audit.}'+'\n','',1)
    # Repetition is removed without changing tables, witnesses, plots or proofs.
    for pattern in (r'\\begin\{tabular\}.*?\\end\{tabular\}',
                    r'\\begin\{(?:proposition|corollary|proof)\}.*?\\end\{(?:proposition|corollary|proof)\}',
                    r'\\addplot.*?;',r'\\label\{[^}]+\}',r'\\bibitem.*?(?=\\bibitem|\\end\{thebibliography\})'):
        assert re.findall(pattern,text,re.S)==re.findall(pattern,changed,re.S),pattern
    return '% Editorial consolidation 2026-10-11\n'+changed

if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    source=root/'outputs/revised_manuscript.tex'
    original=source.read_text(encoding='utf-8')
    revised=apply_editorial_trim(original)
    words=lambda x:len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*",x))
    print(json.dumps({'status':'proposed_editorial_transform_passed',
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_unchanged':True,'approximate_words_removed':words(original)-words(revised),
        'data_tables_plots_proofs_labels_bibliography_unchanged':True,
        'modified_captions':len(RESTRICTED_CAPTIONS)+3,
        'scope':'In-memory dry run only; no manuscript or builder is written.'},indent=2))
