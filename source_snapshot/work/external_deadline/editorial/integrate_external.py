"""Pure, bounded editorial integration of verified external deadline evidence.

Does not read/write a manuscript, regenerate any baseline result, or infer a
favorable result. Root supplies verified external design/results and wording.
"""
from collections import Counter
import hashlib
import re

MARKER = '% External deadline editorial integration v1'

DECISION_COROLLARY = r'''\subsection{Stopping when a model choice is justified}\label{sec:decision-stopping}
The intervals also support a decision among a fixed finite set of candidate
forecasts. For a common nonempty compact feasible set $\F_t$ on the same
evaluation coordinates, write
\[
 U_{jk}(\F_t)=\max_{y\in\F_t}\{L_j(y)-L_k(y)\},\qquad
 \rho(\F_t)=\min_j\max_k U_{jk}(\F_t),\qquad U_{jj}=0.
\]
Here $L_j$ is the candidate's fixed-record MSE; the comparator is the best
candidate on that completed record. Appendix~\ref{app:regret} proves the
identity $\max_{y\in\F_t}\{L_j(y)-\min_kL_k(y)\}=\max_kU_{jk}(\F_t)$.
\begin{corollary}[Certified decision stopping]\label{cor:decision-stopping}
For $\varepsilon\geq0$, if $\rho(\F_t)\leq\varepsilon$, any minimizing
candidate $j_t$ satisfies
\[
 L_{j_t}(y)\leq\min_k L_k(y)+\varepsilon\qquad\text{for every }y\in\F_t.
\]
If a true additional reading gives a nonempty feasible subset
$\F_{t+1}\subseteq\F_t$, then $\rho(\F_{t+1})\leq\rho(\F_t)$.
\end{corollary}
\begin{proof}
The first statement follows from the displayed regret identity. Restricting
the feasible set cannot increase any $U_{jk}$, hence cannot increase either
its maximum over $k$ or the subsequent minimum over $j$.
\end{proof}
Thus an auditor may stop when the information justifies its predeclared
MSE-regret tolerance. At zero tolerance this certifies a best-or-tied-best
candidate; a strict winner requires strictly negative upper bounds against
every distinct competitor. A positive tolerance and any training-based
normalization must be fixed before test outcomes are examined. The result
does not make a repeated width-optimal batch policy optimal for the total
requests needed to stop. Pairwise experiments below retain separate query
budgets; shared multi-model requests would require their own cost accounting.
'''

OKANOVIC_PARAGRAPH = r'''Okanovic et al.~\cite{okanovic2025} study label-efficient selection of
pretrained classifiers for a target pool. Their MODEL SELECTOR concerns
classification and informative label acquisition. Our regression audit
instead requires a fixed-record squared-loss ordering to hold for every
nonnegative completion compatible with observed targets and aggregate sums.
We do not reproduce their classifier-selection benchmark or claim superiority
over that framework. The external acquisition comparison evaluates the
pairwise Hara rule with the same aggregate certificate as the other policies;
this remains a specifically identified adaptation.

'''

OKANOVIC_BIB = r'''\bibitem{okanovic2025} P. Okanovic, A. Kirsch, J. Kasper, T. Hoefler,
A. Krause, and N. M. G\"urel, ``All models are wrong, some are useful:
Model Selection with Limited Labels,'' in \emph{Proceedings of the 28th
International Conference on Artificial Intelligence and Statistics},
\emph{Proceedings of Machine Learning Research}, vol.~258, pp.~2035--2043,
2025. \url{https://proceedings.mlr.press/v258/okanovic25a.html}.
'''

HISTORICAL_DESIGN_SUMMARY = r'''\subsection{Historical evidence and reproducibility}
The earlier energy study contains 34 series and 3,729 meter-days from Portugal,
the French household trace and three cumulative-counter meters; a separately
frozen same-source replication contains 30 further consumers and 3,210 days.
These historical studies use their original issue schedule, unlike the
external deadline experiment. Their full designs and development chronology
are retained in Appendix~\ref{app:historical-design}, with complete supporting
results in Appendices~\ref{app:additional} and~\ref{app:historical-results}.

The historical saved-archive audit includes every permitted direct
persistence copy and aggregate deduction before all comparison methods.
The same enlarged observed set, totals and evaluation horizon are supplied
to bounds and imputers; inverse constraints from other fitted predictors
are outside that declared set. Section~\ref{sec:period-information} states
the exact historical feasible set and explains why its updated daily extrema
aggregate to sharp period bounds. Historical two-query batches are budgets
per day and pair, not unrestricted period-wide or joint multi-model budgets.

An identification interval describes all compatible completions of a fixed
record, rather than sampling uncertainty. All reported numerical checks use
binary64 arithmetic and declared tolerances, not outward-rounded enclosures.
The reproducibility package separates saved-forecast replay, raw-source
reconstruction and fresh model fitting; independent checks mean separate
implementations within this study, not external investigator replication.
Unfavorable outcomes, protocol amendments and incomplete-source limitations
remain in the supporting evidence.
'''

HISTORICAL_ARCHIVE_SUMMARY = r'''\subsection{Historical archive evidence and attribution}
The retrospective energy audit demonstrates why available information must
be used before acquiring readings. On the original Portugal six-hour-gap
archive, 95.33\% of masked target occurrences are recovered from saved
persistence copies. Daily certification starts at 96.67\% and reaches
98.71\% with at most two readings per pair; the exact allocator adds only
0.042 percentage points over greedy. The complete period grids and
same-information matched-coverage comparisons are retained in
Appendix~\ref{app:historical-results}.

Table~\ref{tab:recovery-attribution} separates free reconstruction, paid
recovery and allocation of the same budget. The large restricted-record
gain is not attributed to exact allocation after archive reconstruction.
In the primary six-hour-gap period comparison, paired cancellation certifies
478 of 540 Portugal comparisons (88.5\%), versus 64 (11.9\%) for separate-loss
bounds. However, the historical donor makes zero errors at full coverage in
9,720 Portugal, 324 household and 972 counter exact-total period decisions.
This favors that comparator on the realized panel; it does not guarantee
its ordering on every compatible completion. The audit's distinguishing
output is the all-completions certificate, not demonstrated full-period
ranking-accuracy superiority.
'''

RANDOMIZED_SUMMARY = r'''\subsection{Historical robust gain and adverse realized tradeoff}
The saved-archive randomized experiment contains 20,736 public day--pair
comparisons, of which 1,074 retain positive width. Table~\ref{tab:random-results}
reports the exact optimized mixture expectations. For Portugal, normalized
worst width falls from 29.595\% to 26.673\%, a 9.88\% relative reduction,
while expected width at the actual record rises from 20.154\% to 23.670\%,
a 17.45\% penalty. Certification falls from 98.795\% to 98.688\%; both
policies use two readings in the positive-width cases. Expected realized
width improves in 14 cases, worsens in 649 and ties in 411.

Both target-independent secondary refinements complete on all 1,074
positive-width cases (2,148 LPs) without removing that penalty beyond the
specified tolerance. This does not imply that every minimax mixture has
the same realized penalty. The additional 30-consumer archive likewise
retains the adverse pattern: deterministic versus secondary randomized
realized-width fractions are 0.18497 versus 0.21935, with all-case
certification 98.894\% versus 98.776\%. Detailed policies, source separation,
residual checks and all outcomes remain in
Appendix~\ref{app:historical-results}. The robust optimizer is therefore
evaluated as a different objective, not an empirically dominant acquisition
default.
'''

SCALING_SUMMARY = r'''\subsection{Runtime and memory of compact randomized recovery}
The frozen synthetic grid varies blocks $G\in\{1,2,4\}$, coordinates per
block $m\in\{6,12\}$ and budget fraction $f\in\{1/4,1/2\}$, with two
joint coefficient/total profiles; four additional one-block cases use
$m\in\{24,48\}$ and $f=1/2$. All 28 compact runs succeed. Twelve prescribed
exhaustive comparisons agree within $1.27\times10^{-15}$ after division by
$\max(1,W_0)$; 16 instances exceed the predetermined enumeration limit.
All 560 sampled-policy checks pass.

Table~\ref{tab:compact-scaling-audit} reports method time and worker peak
memory on an Intel Core i7-8565U, Windows 11 and a single numerical thread.
Method time includes construction, solution and policy compilation after
imports; worker memory includes interpreter and imports. Each instance ran
once on a shared host. The two profiles vary coefficient ties and total
heterogeneity jointly, so their effects are not isolated. These are bounded
operability measurements, not runtime dominance or asymptotic-complexity
evidence. Full case manifests, solver residuals, timing boundaries and the
memory-watchdog limitation are retained in
Appendix~\ref{app:historical-results}.
'''

NATURAL_SUMMARY = r'''\subsection{Naturally accumulated records without fine-resolution truth}
Nine NOAA one-day precipitation accumulations give a separate zero-query
application, without imposing artificial missingness. A fixed GEFSv12 control
and ensemble-mean reforecast comparison has two strict daily certificates;
separate individual-loss bounds certify neither. One certificate survives
the declared $\pm2.54$\,mm total sensitivity. Six cases remain ambiguous and
one is an exact forecast tie. Including 43 dry complete controls leaves the
52-day interval $[-0.250924,1.195845]\,\mathrm{mm}^2$ unresolved.
Section~\ref{sec:noaa-natural} retains all nine cases, source provenance,
quantization treatment and tolerance checks. This is a natural observation
structure for partial identification, not an ML architecture benchmark or
evidence that missing hourly targets can be retrieved. Fine-resolution truth
and operational recovery costs are unavailable.
'''


def _split_section(text, title, next_title):
    start = text.index('\\section{'+title+'}')
    end = text.index('\\section{'+next_title+'}', start)
    return text[:start], text[start:end], text[end:]


def _extract_float(text, label):
    pattern = r'\\begin\{(table\*?|figure\*?)\}.*?\\end\{\1\}'
    found = [m for m in re.finditer(pattern, text, flags=re.S) if '\\label{'+label+'}' in m.group()]
    if len(found) != 1:
        raise ValueError('Expected one float for '+label)
    match = found[0]
    return match.group(), text[:match.start()]+text[match.end():]


def _environment_blocks(text):
    # Non-nesting named environments used in this manuscript. Their content
    # is checked exactly; equation movement only changes rendered numbering.
    kinds = 'proposition|corollary|proof|table\\*?|figure\\*?|equation|align'
    return Counter((m.group(1), m.group(0)) for m in re.finditer(r'\\begin\{('+kinds+r')\}.*?\\end\{\1\}', text, flags=re.S))


def _bibitems(text):
    start = text.index(r'\begin{thebibliography}')
    end = text.index(r'\end{thebibliography}', start)
    segment = text[start:end]
    return {m.group(1): m.group(0).strip() for m in re.finditer(r'\\bibitem\{([^}]+)\}.*?(?=\\bibitem\{|\Z)', segment, flags=re.S)}


def _reorder_bibliography(text):
    begin = text.index(r'\begin{thebibliography}')
    head_end = text.index('\n', begin)+1
    end = text.index(r'\end{thebibliography}', head_end)
    content = text[head_end:end]
    matches = list(re.finditer(r'\\bibitem\{([^}]+)\}', content))
    prefix = content[:matches[0].start()]
    entries = {}
    for i, match in enumerate(matches):
        stop = matches[i+1].start() if i+1 < len(matches) else len(content)
        if match.group(1) in entries:
            raise ValueError('Duplicate bibliography key')
        entries[match.group(1)] = content[match.start():stop].strip()
    order = []
    for match in re.finditer(r'\\cite\{([^}]+)\}', text[:begin]):
        for key in match.group(1).split(','):
            if key not in order:
                order.append(key)
    missing = set(order)-set(entries)
    if missing:
        raise ValueError('Missing bibliography entries: '+', '.join(sorted(missing)))
    order += [key for key in entries if key not in order]
    return text[:head_end]+prefix+'\n\n'.join(entries[key] for key in order)+'\n'+text[end:]


def audit_preservation(before, after):
    old, new = _environment_blocks(before), _environment_blocks(after)
    omitted = old-new
    if omitted:
        raise AssertionError('Existing theorem/proof/equation/table/figure content changed: '+str([key[0] for key in omitted]))
    for key, item in _bibitems(before).items():
        if _bibitems(after).get(key) != item:
            raise AssertionError('Existing bibliography item changed: '+key)
    old_labels = Counter(re.findall(r'\\label\{([^}]+)\}', before))
    new_labels = Counter(re.findall(r'\\label\{([^}]+)\}', after))
    if any(count != 1 for count in new_labels.values()) or old_labels-new_labels:
        raise AssertionError('A label is duplicated or lost')
    refs = set(re.findall(r'\\(?:eqref|ref)\{([^}]+)\}', after))
    if refs-set(new_labels):
        raise AssertionError('Unresolved labels: '+', '.join(sorted(refs-set(new_labels))))
    main = after.split(r'\appendix', 1)[0]
    return {'status': 'passed', 'baseline_text_sha256': hashlib.sha256(before.encode()).hexdigest(),
            'integrated_text_sha256': hashlib.sha256(after.encode()).hexdigest(),
            'hash_scope': 'UTF-8 encoding of supplied text strings, after caller newline normalization; not necessarily original file bytes.',
            'original_named_environments_preserved': sum(old.values()),
            'original_tables_preserved': sum(n for (kind, body), n in old.items() if kind.startswith('table')),
            'original_figures_preserved': sum(n for (kind, body), n in old.items() if kind.startswith('figure')),
            'original_labels_preserved': len(old_labels), 'final_labels': len(new_labels),
            'original_bibliography_entries_preserved': len(_bibitems(before)),
            'main_text_rough_words': len(re.findall(r'\b[\w-]+\b', main)),
            'baseline_main_text_rough_words': len(re.findall(r'\b[\w-]+\b', before.split(r'\appendix', 1)[0])),
            'page_count_not_assessed': True,
            'numbering_notice': 'Moved floats/equations and added corollary are renumbered automatically; label identities remain unchanged. Never retain old numeric section/table references in external reports.'}


def integrate_external(text, design_fragment, results_fragment, result_summary):
    """Return revised TeX; use only after independent external verification.

    result_summary['verified'] must be True. Optional full-text fields:
    abstract_latex, external_interpretation_latex, conclusion_latex,
    bibliography_latex, supplementary_latex, introduction_result_latex.
    All empirical external claims must be supplied from verified outputs.
    """
    if result_summary.get('verified') is not True:
        raise ValueError('External independent verification must pass before integration')
    if MARKER in text:
        raise ValueError('Use the saved pre-external baseline, not an integrated manuscript')
    for fragment in (design_fragment, results_fragment):
        if not fragment.strip() or any(command in fragment for command in (r'\documentclass', r'\begin{document}', r'\appendix', r'\end{document}')):
            raise ValueError('Expected a nonempty design/results fragment')
    baseline = text
    # Remove the complete original protocol/results sections, preserving their
    # exact bodies for appendices. Main uses concise interpretation plus the
    # most informative unchanged tables; no adverse numerical result is lost.
    prefix, historical_design, tail = _split_section(text, 'Experimental Design', 'Results')
    _, historical_results, suffix = _split_section(tail, 'Results', 'Discussion')
    historical_design = historical_design.replace(r'\section{Experimental Design}', r'\section{Historical Energy Study: Design and Reproducibility}\label{app:historical-design}', 1)
    historical_results = historical_results.replace(r'\section{Results}', r'\section{Supporting Historical Results}\label{app:historical-results}', 1)
    attribution, historical_results = _extract_float(historical_results, 'tab:recovery-attribution')
    randomized, historical_results = _extract_float(historical_results, 'tab:random-results')
    scaling, historical_results = _extract_float(historical_results, 'tab:compact-scaling-audit')
    main_design = '\\section{Decision Workflow and External Evaluation}\n\\label{sec:external-evaluation}\n'+design_fragment.strip()+'\n\n'+HISTORICAL_DESIGN_SUMMARY
    main_results = ('\\section{Results}\n'+results_fragment.strip()+'\n\n'+HISTORICAL_ARCHIVE_SUMMARY+'\n'+attribution+
                    '\n\\FloatBarrier\n'+RANDOMIZED_SUMMARY+'\n'+randomized+'\n\\FloatBarrier\n'+SCALING_SUMMARY+'\n'+scaling+
                    '\n\\FloatBarrier\n'+NATURAL_SUMMARY+'\n')
    text = prefix+main_design+'\n'+main_results+'\n'+suffix
    text = text.replace(r'\section{Budgeted Recovery of Missing Readings}', DECISION_COROLLARY+'\n'+r'\section{Budgeted Recovery of Missing Readings}', 1)
    appendices = '\n'+historical_design+'\n\\FloatBarrier\n'+historical_results+'\n\\FloatBarrier\n'
    text = text.replace(r'\section*{Supplementary Materials}', appendices+r'\section*{Supplementary Materials}', 1)
    anchor = 'Related active testing and worst-case sensor selection address model'
    if anchor not in text:
        raise ValueError('Related-work insertion anchor changed')
    text = text.replace(anchor, OKANOVIC_PARAGRAPH+anchor, 1)
    text = text.replace(r'\end{thebibliography}', '\n'+OKANOVIC_BIB+'\n'+result_summary.get('bibliography_latex', '')+'\n'+r'\end{thebibliography}', 1)
    start = text.index('The practical output is therefore')
    stop = text.index(r'\section{Related Work and Contribution Boundary}', start)
    text = text[:start]+r'''The practical question is whether a justified model comparison can be reached
with fewer requested readings before later forecast information arrives.
The external evaluation tests an executable stopping workflow under fixed
early and later audit cutoffs, using all forecast records allowed by each
cutoff. It separates observed record-count benefits from the exact batch
width guarantee and from unmeasured transaction cost or field latency.
'''+result_summary.get('introduction_result_latex', '')+r'''
The development below defines the observation model, sharp decision
guarantees and deterministic recovery, followed by the randomized method in
Section~\ref{sec:randomized-recovery}. The experiments lead with the external
deadline evaluation; historical archive attribution, adverse randomized
outcomes, scaling and natural accumulated records supply complementary
evidence. Supporting protocols, restricted-record grids and development
chronology remain in the appendices.

'''+text[stop:]
    # Distinguish previously untested stopping economics from the newly
    # executed benchmark, without converting it to a deployment claim.
    text = text.replace('Shared requests across many pairs, cancellation after an early decision,\nand optimal randomized adaptive recovery require different objectives and\nevaluations.',
                        'Shared requests across many pairs and optimal randomized adaptive recovery\nrequire different objectives and evaluations. The external benchmark evaluates\nrepeated batch acquisition with stopping, without claiming that its full\nsequence minimizes the total requests needed for a decision.')
    text = text.replace('Post-review analyses reuse these records and are not independent prospective\ncohorts.',
                        'The earlier post-review energy analyses reuse their source records and are\nnot independent prospective cohorts. The external source separates those\ndevelopment records from the new benchmark; its simulated access schedule\nstill does not supply a prospective deployment study.')
    interpretation = result_summary.get('external_interpretation_latex', '')
    if interpretation:
        text = text.replace(r'\section{Discussion}', r'\section{Discussion}'+'\n'+interpretation.strip()+'\n', 1)
    if result_summary.get('abstract_latex'):
        text = re.sub(r'(?s)\\begin\{abstract\}.*?\\end\{abstract\}', lambda m: '\\begin{abstract}\n'+result_summary['abstract_latex'].strip()+'\n\\end{abstract}', text, count=1)
    if result_summary.get('conclusion_latex'):
        start = text.index(r'\section{Conclusion}')+len(r'\section{Conclusion}')
        end = text.index(r'\appendix', start)
        text = text[:start]+'\n'+result_summary['conclusion_latex'].strip()+'\n\\FloatBarrier\n'+text[end:]
    if result_summary.get('supplementary_latex'):
        text = text.replace(r'\section*{Supplementary Materials}', r'\section*{Supplementary Materials}'+'\n'+result_summary['supplementary_latex'].strip()+'\n', 1)
    text = _reorder_bibliography(text)
    text = MARKER+'\n'+text
    audit_preservation(baseline, text)
    return text
