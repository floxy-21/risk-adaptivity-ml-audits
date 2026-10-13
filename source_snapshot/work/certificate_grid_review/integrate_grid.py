"""Insert the matched, complete historical certificate-grid summary."""


def integrate_grid(text, rows, report):
    assert report['status'] == 'passed' and report['scope'] == 'full'
    assert report['paired_comparisons'] == 66096 and report['scenario_cells'] == 324
    assert report['cross_tab'] == {'both': 10404, 'paired_only': 23906, 'neither': 31786, 'separate_only': 0}
    example=report['portugal_example']
    assert (example['paired_certified'],example['separate_certified'],example['comparisons']) == (478,64,540)
    anchor=r'\subsection{Historical robust gain and adverse realized tradeoff}'
    assert text.count(anchor)==1
    block=r'''\paragraph{Complete scenario-grid check.}
The 478-versus-64 example is one cell of the existing historical design.
To assess its representativeness, a post-review descriptive analysis matches
the saved paired and separate-loss endpoints across all 324 scenario cells:
the original 34 series, both access regimes, all declared gap lengths,
mask mechanisms and aggregate block sizes, and total tolerances of
0\%, 1\% and 5\%. No forecast, mask, acquisition policy or endpoint was
refitted or retuned. The resulting 66,096 repeated model-pair comparisons
are not independent experiments. Table~\ref{tab:certificate-grid} includes
all cohort/access/tolerance combinations, including unresolved outcomes.

For Portugal's archive-aware exact-total grid, paired bounds certify
7,836 of 9,720 comparisons, versus 2,513 with separate-loss bounds: an
additional 5,323 certificates, or 54.76 percentage points. The single-cell
76.67-point example is therefore not the full-grid effect size.
Every cohort/access/tolerance combination has additional paired certificates.
Across the complete grid, 10,404 comparisons are certified by both,
23,906 by paired bounds only, and 31,786 by neither; none is certified by
separate bounds only. The checker reproduces the saved decision margins,
verifies interval nesting and reference enclosure, and finds no incorrect
issued certificate. These are binary64 checks with documented tolerances.
This benefit concerns uncertainty-aware certification over a matched bound
comparator; it is not new evidence of forecast accuracy, superiority over
the historical donor, or acquisition savings.

\begin{table}[htbp]
\centering\small\setlength{\tabcolsep}{4pt}
\caption{Complete historical scenario grid, aggregated within cohort, access
regime and relative total tolerance. Both: both bound methods certify;
paired only: only paired bounds certify; neither: neither certifies;
separate only: only separate-loss bounds certify. All results use identical
information and zero additional queries. Repeated consumers, pairs, masks
and tolerances share observations. The supplement retains all 324 cells.}
\label{tab:certificate-grid}
\begin{tabular}{lllrrrrr}
\toprule
Source & Access & Tol. & Cases & Both & Paired only & Neither & Separate only\\
\midrule
'''+rows+r'''\bottomrule
\end{tabular}
\end{table}
\FloatBarrier
The redistributable endpoint replay covers 60,264 Portugal/household
comparisons. The 5,832 counter comparisons were checked from the original
local endpoints; their bundled summaries are reproducible after the
documented BLEM raw-source regeneration, rather than from redistributed
counter endpoints. These two reproduction scopes are explicitly separated.

'''
    return text.replace(anchor,block+anchor,1)
