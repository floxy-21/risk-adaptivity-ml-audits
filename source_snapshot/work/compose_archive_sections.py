"""Compose the post-review archive sensitivity from verified aggregate results."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'

ARCHIVE_METHODS = r'''\subsection{Evaluator-access sensitivity}
The primary restricted-record experiment conditions on the current day's
predictions, surviving targets and retained totals. A post-review protocol
adds a second regime: all available saved test persistence predictions
for that meter. The implemented persistence forecast at $t+24$ hours is
an exact copy of the actual measurement at $t$. A timestamp lookup built
from forecast columns alone therefore reveals a masked target whenever
that later forecast is present. Its provenance is checked against the
fixed feature-construction code; equality with hidden truth is checked
only afterward. No lookup falls back to raw measurements.

We first add these free values to the observed set, then recompute sharp
bounds and batches of at most two paid queries. The same six- and
twelve-hour gaps, six-hour totals, three seeds, six model pairs and all
34 meters are retained. Paid batches never request an already revealed
value. Restricted-regime counts and widths are reconciled with the original
recovery archive. Both exact and greedy policies retain the original
all-case budget convention, including already certified pairs; average
queries do not estimate an optimal early-stopping policy.

This is retrospective access to the available saved test persistence
archive, including future records. It is not a same-day access model,
full informational closure, or a new blind validation cohort. Missing
future archive rows remain unavailable; nonlinear inversion, feature
caches and records outside this archive are excluded. If persistence
used imputed inputs, its output would not establish a measured target.
Free-recovery fractions count masked coordinate occurrences; repeated
seeds and model pairs do not constitute independent observations.
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_archive():
    r = json.loads((OUT / 'study_archive_access.json').read_text())
    assert r['status'] == 'passed' and r['checks']['wrong_certificates'] == 0
    assert r['meters'] == 34 and r['heldout_meter_days'] == 3729
    assert digest(OUT / 'study_archive_access.py') == r['script_sha256']
    assert digest(ROOT / 'work/archive_access_protocol.txt') == r['protocol_sha256']
    for name, expected in {**r['source_hashes'], **r['output_hashes']}.items():
        path = OUT / name
        if path.exists():
            assert digest(path) == expected, name
        elif name == 'study_predictions.csv':
            omitted = json.loads((ROOT / 'work/prediction_archive_omission.json').read_text())
            assert omitted['sha256'] == expected
        else:
            raise FileNotFoundError(path)
    return r


def archive_sections():
    r = load_archive()
    lookup = {(x['cohort'], x['gap_hours'], x['regime'], x['budget'], x['policy']): x
              for x in r['cohort_results']}
    regime = 'available_test_persistence_archive'
    exact, greedy = 'optimal_minimax_width', 'greedy_width_reduction'
    text = r'''\FloatBarrier
\subsection{Sensitivity to the available forecast archive}\label{sec:archive-access}
Allowing the saved future persistence forecasts changes the information
problem substantially (Table~\ref{tab:archive-access}). The lookup reveals
most masked targets without paid recovery. These results are not additional
improvements attributable to the query optimizer: they arise from using
information already present in the broader archive.

\begin{table}[htbp]
\centering\small
\caption{Access to all available saved test persistence forecasts. Free:
percentage of originally masked target occurrences revealed before queries.
$C_0,C_2$: certified comparison percentages at zero and at most two paid
queries using the exact policy. $\Delta$: exact-minus-greedy $C_2$ in
percentage points. $\bar q$: actual mean paid queries per pair at budget two.
All figures include every case, not only previously unresolved comparisons.}
\label{tab:archive-access}
\begin{tabular}{lrrrrrr}
\toprule
Cohort & Gap (h) & Free (\%) & $C_0$ & $C_2$ & $\Delta$ & $\bar q$\\
\midrule
'''
    for cohort, label in [('portugal', 'Portugal'), ('household', 'Household'),
                          ('blem_counters', 'Counters')]:
        for gap in (6, 12):
            zero = lookup[cohort, gap, regime, 0, exact]
            two = lookup[cohort, gap, regime, 2, exact]
            other = lookup[cohort, gap, regime, 2, greedy]
            gain = 100 * (two['resolved_fraction'] - other['resolved_fraction'])
            text += (f"{label} & {gap} & {100*zero['free_revealed_fraction']:.2f} & "
                     f"{100*zero['resolved_fraction']:.2f} & {100*two['resolved_fraction']:.2f} & "
                     f"{gain:+.3f} & {two['mean_queries']:.3f}" + r'\\' + '\n')
    text += r'''\bottomrule
\end{tabular}
\end{table}
The saved persistence copies match the reference targets exactly in the
stored binary64 data. Every recomputed comparison interval contains its
reference difference, and no certificate is incorrect. The restricted
regime reproduces ''' + f"{r['restricted_reference_rows_reconciled']:,}" + r'''
archived meter and named-pair/seed rows, including decision counts,
widths and mean queries. The sensitivity evaluates ''' + f"{r['dependent_policy_budget_pair_evaluations']:,}" + r'''
dependent policy/budget/pair cases; this is a computation count, not an
independent statistical sample.

The large restricted-record gain from paid recovery therefore does not
carry over unchanged to an archive with these future exact copies.
The remaining uncertainty is concentrated at boundaries and gaps in the
available test archive. A practical audit should incorporate authorized
reconstructable targets first and allocate a recovery budget only to the
remaining unknowns. This analysis supports that workflow, but does not
measure field retrieval savings or establish how often a real evaluator
has only the restricted inputs.
'''
    p0 = lookup['portugal', 6, regime, 0, exact]
    p2 = lookup['portugal', 6, regime, 2, exact]
    return ARCHIVE_METHODS, text, p0, p2
