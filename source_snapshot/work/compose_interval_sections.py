"""Verified independent-total-interval extension of batch recovery."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def interval_sections():
    r = json.loads((ROOT / 'outputs/study_interval_total_recovery.json').read_text())
    assert r['all_passed']
    for name, expected in r['source_hashes'].items():
        assert hashlib.sha256((ROOT / 'outputs' / name).read_bytes()).hexdigest() == expected
    c = r['counts']
    text = r'''\subsection{Recovery with independently bounded totals}\label{sec:interval-recovery}
The exact-total model can be extended without imposing a load-shape model.
After subtracting observed values, let each independent block satisfy
$0\leq L_g\leq\sum_{i\in\M_g}y_i\leq U_g<\infty$.
Query answers remain exact, targets are nonnegative and uncapped, and
each query has unit cost. For a nonempty retained set with coefficient
extremes $\alpha\leq\beta$, define
\begin{equation}
 F_{L,U}(\alpha,\beta)=
 U\max(\beta,0)+L\min(\beta,0)
 -L\max(\alpha,0)-U\min(\alpha,0).
 \label{eq:interval-recovery-cost}
\end{equation}
\begin{proposition}[Batch recovery under total intervals]
For a fixed batch leaving at least one unknown coordinate in a block,
its worst-case remaining comparison width is
$F_{L_g,U_g}(\alpha,\beta)$. For each local query count, an optimal
retained set is a consecutive window in sorted coefficient order.
The allocation recurrence therefore remains exact when its local costs
use \eqref{eq:interval-recovery-cost} and allow full-block recovery at
zero remaining width.
\end{proposition}
\begin{proof}
If the queried values sum to $S$, the residual total interval is
$[\ell,u]=[\max(0,L-S),U-S]$. The queried contribution shifts both
comparison endpoints equally. The remaining width is $u\beta-\ell\alpha$
when $\alpha\geq0$, $\ell\beta-u\alpha$ when $\beta\leq0$, and
$u(\beta-\alpha)$ when $\alpha\leq0\leq\beta$. Each expression is
nonincreasing in feasible $S$: below $L$ its slope is
$\alpha-\beta$; above $L$ the respective slopes are $-\beta$,
$\alpha$, and $\alpha-\beta$. Zero queried values are feasible whenever
a coordinate remains, by assigning the required total to that remainder.
Hence the worst width occurs at $S=0$, yielding
\eqref{eq:interval-recovery-cost}. This cost is nondecreasing in
$\beta$ and nonincreasing in $\alpha$. Any retained subset can be
replaced by a consecutive window of the same size with extremes inside
its extremes, without increasing cost. Independent blocks contribute
additively, so the budget-allocation recurrence applies. A fully queried
block has no unknown contribution and contributes zero width.
\end{proof}
Two implementation details distinguish this extension from exact totals.
A singleton with coefficient $c$ retains width $(U-L)|c|$; querying it
may therefore be necessary. Likewise, constant coefficients need not
imply zero width. Local budgets must include $k_g=m_g$, and a block
can be skipped only when its actual width is zero. The released
\texttt{interval\_total\_recovery.py} implements these rules separately
from the primary exact-total experimental code. The result does not
assume independent stochastic errors; it assumes a product of declared
total intervals. Additional known correlations require a different set.
Uncertain query answers, overlapping constraints, target capacity limits
and unequal costs remain outside this implementation.
'''
    verification = r'''
The separate interval-total batch solver was checked on ''' + str(c['exhaustive_instances']) + r'''
small synthetic instances by enumerating ''' + f"{c['exhaustive_query_subsets']:,}" + r'''
query subsets and computing extrema using ''' + f"{c['lp_calls']:,}" + r'''
HiGHS linear-program solves. It also passed ''' + str(c['conditional_answer_checks']) + r'''
conditional-answer checks, ''' + str(c['exact_total_comparisons']) + r'''
reductions to the exact-total implementation, and ''' + str(c['invalid_input_checks']) + r'''
invalid-input checks. The maximum recorded discrepancy was zero in these
constructed cases; this is finite numerical verification, not an
outward-rounded arithmetic guarantee. This extension was not used to
replace or pool the primary exact-total meter results, and its tests do
not measure field deployment benefits.
'''
    return text, verification
