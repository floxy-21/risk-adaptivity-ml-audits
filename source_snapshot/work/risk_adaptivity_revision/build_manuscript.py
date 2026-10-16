"""Compose the risk/adaptivity manuscript in the existing editor file.

--freeze records the reviewed input hashes; ordinary reconstruction verifies
them and the exact output hash. Historical scientific inputs remain immutable.
"""
from pathlib import Path
import argparse, hashlib, json, re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'work/risk_adaptivity_revision'
BASE_SHA = '5d39e16db1b60d5ac3f25bc0b10b6cb0338fcf0b9f0db281446840ebf4b774c8'
READ = set()

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def source(rel):
    p = ROOT / rel
    READ.add(p)
    return p.read_text(encoding='utf-8-sig')

def local(rel):
    return source('work/risk_adaptivity_revision/' + rel)

def between(s, a, b):
    return s[s.index(a):s.index(b, s.index(a))]

def json_source(rel):
    return json.loads(source(rel))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    baseline = BASE / 'prior_release/revised_manuscript.tex'
    assert sha(baseline) == BASE_SHA
    old = local('prior_release/revised_manuscript.tex')
    dual = json_source('work/risk_adaptivity_revision/dual/results/verification.json')
    gen = json_source('work/risk_adaptivity_revision/general/verification.json')
    math = json_source('work/risk_adaptivity_revision/math/classification_verification.json')
    assert dual['status'] == 'PASS' and dual['cases'] == 80
    assert gen['status'] == 'passed' and len(gen['cases']) == 6
    assert math['status'] == 'passed' and math['endpoint_LPs_solved'] == 3202
    practical = json_source('work/risk_adaptivity_revision/practical/replication/verification.json')
    selection = json_source('work/risk_adaptivity_revision/practical_multi/results_public/report.json')
    api = json_source('work/risk_adaptivity_revision/practical_api/verification.json')
    assert practical['status'] == 'passed' and practical['comparisons'] == 19440
    assert [(r['paired_certified'], r['separate_certified']) for r in practical['summaries']] == [(7753,2527),(7424,2010)]
    primary = next(r for r in selection['summary'] if r['cohort'] == 'portugal' and r['total_tolerance'] == 0)
    assert selection['status'] == 'passed' and (primary['paired_certified'],primary['separate_certified']) == (933,167)
    assert api['status'] == 'PASS' and sum(r['checks']['independent_endpoint_LPs'] for r in api['examples']) == 24
    boundary = json_source('work/risk_adaptivity_revision/two_target_boundary/numeric_report.json')
    boundary_exact = json_source('work/risk_adaptivity_revision/two_target_boundary/solver_free_report.json')
    boundary_source = BASE / 'two_target_boundary/verify_boundary.py'
    READ.add(boundary_source)
    assert boundary['status'] == boundary_exact['status'] == 'PASS'
    assert boundary['source_sha256'] == boundary_exact['source_sha256'] == sha(boundary_source)
    assert boundary['proof_input_sha256'] == boundary_exact['proof_input_sha256']
    assert boundary['numerical_verification']['actual_total_LPs'] == 7131
    assert boundary['numerical_verification']['maximum_width_discrepancy'] < 1e-7
    support = json_source('work/risk_adaptivity_revision/two_target_boundary/support_report.json')
    support_checker = BASE / 'two_target_boundary/verify_support.py'
    READ.add(support_checker)
    assert support['status'] == 'PASS' and support['checker_sha256'] == sha(support_checker)
    assert support['actual_width_evaluations'] == 126195
    budget_dir = 'work/risk_adaptivity_revision/joint_certification/reading_budget/'
    budgets = json_source(budget_dir + 'executed_all/report.json')
    budget_check = json_source(budget_dir + 'executed_all/independent_check.json')
    budget_source = ROOT / (budget_dir + 'reading_budget.py')
    budget_checker = ROOT / (budget_dir + 'check_reading_budget.py')
    READ.update([budget_source, budget_checker])
    assert budgets['status'] == budget_check['status'] == 'PASS'
    assert budgets['source_sha256'] == sha(budget_source)
    assert budget_check['checker_sha256'] == sha(budget_checker)
    assert budget_check['producer_report_sha256'] == sha(ROOT / (budget_dir + 'executed_all/report.json'))
    for cohort, values in [('original', (819,168,2625,2457)), ('external', (279,57,743,686))]:
        row = budgets['summaries'][cohort]
        assert (row['blocks'], row['strict_readout_saving_cases'],
                row['fixed_total_readings_all_blocks'],
                row['adaptive_where_certified_otherwise_minimum_fixed_total']) == values
        assert row['adaptive_two_vs_minimum_fixed_histogram'] == {'3': values[1]}

    preamble = r'''% Self-contained source composed from pinned proofs and measured outputs.
\documentclass[12pt]{article}
\usepackage[letterpaper,margin=1in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{newtxtext,ragged2e}
\usepackage[justification=raggedright,singlelinecheck=false]{caption}
\usepackage{amsmath,amssymb,amsthm,booktabs,array}
\usepackage{tikz}
\usepackage[authoryear,round]{natbib}
\usepackage[hidelinks]{hyperref}
\usepackage{xurl,microtype,placeins}
\usepackage[mathlines]{lineno}
\AtBeginDocument{\raggedright\linenumbers}
\setlength{\emergencystretch}{2em}
\renewcommand{\topfraction}{0.95}
\renewcommand{\bottomfraction}{0.9}
\renewcommand{\textfraction}{0.05}
\renewcommand{\floatpagefraction}{0.75}
\newtheorem{theorem}{Theorem}
\newtheorem{proposition}{Proposition}
\newtheorem{corollary}{Corollary}
\newcommand{\F}{\mathcal{F}}
\newcommand{\R}{\mathbb R}
\newcommand{\M}{\mathcal M}
\newcommand{\Oset}{\mathcal O}
\newcommand{\clip}{\operatorname{clip}}
'''
    text = preamble + local('editorial/front.tex').replace('adjust2024', 'wei2024')
    workflow_marker = 'The central result is a boundary'
    assert text.count(workflow_marker) == 1
    text = text.replace(workflow_marker,
                        local('editorial/audit_workflow.tex') + '\n' + workflow_marker, 1)
    # The focused introduction owns its concise, pinpoint-attributed comparison.
    theory = local('math/theorem_proof.tex')
    for title in ('Universal classification of width penalties', 'Sharp growing separations'):
        start = theory.index(r'\begin{proposition}[' + title + ']')
        end = theory.index(r'\end{proposition}', start) + len(r'\end{proposition}')
        theory = theory[:start] + theory[start:end].replace('{proposition}', '{theorem}') + theory[end:]
    theory = theory.replace("Sion's minimax theorem\ntherefore", "Sion's minimax theorem \\citep{sion1958}\ntherefore")
    growing_start = theory.index(r'\section{Growing moment and precision separations}')
    classification_start = theory.index(r'\section{Which width penalties can benefit from adaptation?}')
    example_start = theory.index(r'\subsection{A three-coordinate example}')
    scalar_setup = theory[:classification_start]
    classification = theory[classification_start:example_start]
    scalar_example = theory[example_start:growing_start]
    growing_support = theory[growing_start:]
    general_algorithms = local('general/algorithms.tex')
    text += local('editorial/focused_information.tex')
    helly_full = local('editorial/helly_focused.tex')
    text += local('editorial/helly_precision_short.tex').replace(
        r'\subsection{A precision consequence of sparse-policy bounds}',
        r'\section{A precision consequence of sparse-policy bounds}', 1)
    boundary_full = local('two_target_boundary/main_theorem.tex')
    corollary_start = boundary_full.index(r'\begin{corollary}')
    corollary_proof_start = boundary_full.index(r'\begin{proof}', corollary_start)
    corollary_proof_end = boundary_full.index(r'\end{proof}', corollary_proof_start) + len(r'\end{proof}')
    corollary_proof = boundary_full[corollary_proof_start:corollary_proof_end]
    text += (boundary_full[:corollary_proof_start] + r'''
\begin{proof}[Proof sketch]
Add the third contrast $T_3=T_1-T_2$. Querying $t$ alone makes its normalized
width smaller than the lower endpoint of the stated threshold interval.
The first two contrasts retain their adaptive and uniform-batch guarantees;
the theorem's adverse records retain the matching batch upper bound.
The fixed batch $\{t,z_1,z_m\}$ certifies all three. Explicit nonnegative
prediction vectors and the threshold inequalities appear in Online
Resource~1, S17.
\end{proof}
''' + boundary_full[corollary_proof_end:])
    text += local('two_target_boundary/optimal_mixture.tex')
    boundary_execution = r'''
\paragraph{Executable checks.}
Online Resource~1 includes a standard-library rational verifier and a
separate LP calculation for $m=3,5,10$. The rational checks enumerate
1,171 adverse-record/query-set combinations and verify continuum branch
coverage. The 7,131 endpoint and whole-branch LPs agree with the exact
formulas to at most $7.11\times10^{-15}$; the absolute comparison tolerance
is $10^{-7}$ and the primal/dual feasibility tolerances are $10^{-9}$.
The main theorem and the corollary proof here establish the result for
every $m\geq3$; these finite
checks test its implementation, including the third contrast and the
threshold interval. Online Resource~1 provides the commands, pinned environment and exact
input/output hashes in \texttt{CURRENT\_RESULTS\_MAP.txt}. Its solver-free
support check additionally evaluates 126,195 rational widths for seven
family sizes from $m=3$ to $24$.
'''
    text += r'''
\paragraph{Executable checks.}
Online Resource~1, S17 supplies the rational verifier, a separately assembled
LP check, numerical tolerances and exact input/output hashes. The complete
proof of Theorem~\ref{thm:two-target-collapse} above establishes its universal
claim; these finite calculations check the implementation.
'''
    counter_full = (local('counter_adaptive/literature/counter_methods.tex')
                    + local('editorial/counter_half_corollary.tex')
                    + local('counter_adaptive/feedback_triage/math_review.tex'))
    text += local('editorial/joint_counter_setup.tex')
    joint_methods = local('joint_certification/manuscript_methods.tex')
    joint_definition = between(joint_methods,
                               'An auditor comparing several models',
                               'The scalar assumption')
    joint_algorithms = joint_methods[joint_methods.index('For the uncapped exact-total simplex'):]
    inspectable = local('joint_certification/main_inspectable_proof.tex')
    inspectable = inspectable.replace(r'\begin{theorem}',
                                     joint_definition + r'\begin{theorem}', 1)
    text += joint_definition
    text += local('joint_certification/main_planner_algorithm.tex')
    text += local('joint_certification/precision_completion_probe/methods.tex')
    text += local('joint_certification/precision_completion_probe/methods_secondary.tex')
    text += local('joint_certification/reading_budget/methods.tex')
    text += local('joint_certification/review_mechanism/methods.tex')
    text += local('editorial/assurance_feasibility.tex')
    text += local('joint_certification/final_practical_figure/clarification.tex').replace(
        r'Figure~\ref{fig:practical-guarantee-replay}(a)',
        r'Figure~\ref{fig:practical-guarantee-replay}')
    worked_full = local('joint_certification/main_worked_precision_certificate.tex')
    worked_absolute = (local('joint_certification/absolute_width_fragment.tex')
                       + local('joint_certification/absolute_width_results/main_table.tex'))
    text += local('editorial/worked_certificate_short.tex')
    figure_check = json_source('work/risk_adaptivity_revision/joint_certification/final_practical_figure/independent_check.json')
    figure_data = json_source('work/risk_adaptivity_revision/joint_certification/final_practical_figure/figure_data.json')
    assert figure_check['status'] == 'PASS'
    assert figure_check['envelope_equalities'] == 735 and figure_check['replay_points_checked'] == 30
    assert figure_check['figure_data_sha256'] == sha(BASE / 'joint_certification/final_practical_figure/figure_data.json')
    full_figure = local('joint_certification/final_practical_figure/figure_fragment.tex')
    first_panel = full_figure[:full_figure.index(r'\draw[black!12] (59,')]
    first_panel = first_panel.replace(r'\node[anchor=west,font=\small\bfseries] at (53,47) {(b) Recorded precision success};', '')
    first_panel = first_panel.replace('{(a) Choosing the second reading}', '{Choosing the second reading}')
    first_panel = first_panel.replace(r'x=0.0098\linewidth', r'x=0.0140\linewidth').replace(
        r'font=\scriptsize', r'font=\footnotesize')
    text += first_panel + r'''
\end{tikzpicture}
\caption{Choosing the second reading in the HPM~1 worked case. The black
lower envelope selects boundary~4 below the switch and boundary~1 above it.
Its maximum, about $0.47734$, is below the half-width target for every first
answer. Gray curves show the other permitted second readings.}
\label{fig:practical-guarantee-replay}
\end{figure}
'''
    text += '\n\\FloatBarrier\n'
    text += local('editorial/source_protocols_short.tex')
    text += local('editorial/measurement_assumptions.tex')
    protocol_numerics = local('editorial/joint_protocol_summary.tex')
    text += protocol_numerics[protocol_numerics.index(r'\begin{table}'):]
    structured = local('editorial/structured_start.tex')
    compact = between(old, r'\section{Randomized Recovery under a Hard Budget}', r'\subsection{Interpreting the robust objective}')
    compact = compact.replace(r'\section{Randomized Recovery under a Hard Budget}', r'\subsection{Randomized recovery under a hard budget}')
    compact = compact.replace('the sharp comparison with deterministic adaptive recovery.', 'the adaptive optimality certificate below.')
    compact = compact.replace('The separation concerns randomized nonadaptive batches versus all\ndeterministic adaptive policies; it does not establish optimality among\nrandomized adaptive policies.', 'The ratio also compares the optimal randomized adaptive mean width with\nthe deterministic adaptive optimum, by the dual-completion result below.')
    compact = compact.replace('The result does not extend here to overlapping or\nuncertain totals, physical caps, or heterogeneous query costs.', 'This structured gap formula and compact implementation do not extend here\nto overlapping or uncertain totals, physical caps, or heterogeneous query\ncosts. The general information theorem does allow such convex constraints\nand fixed costs.')
    compact = compact.replace(r'\cite{', r'\citep{')
    compact = compact.replace('y_i v_{gi}(Q)', 'y_{gi} v_{gi}(Q)')
    dualproof = local('dual/adaptive_dual_proof.tex')
    computation = ''
    computation += local('editorial/evaluation_intro.tex').replace('tab:risk-solver-comparison', 'tab:risk_paired_solvers')
    computation += local('dual/solver_comparison/paired_solver_table.tex') + '\n\\FloatBarrier\n'
    scaling = between(old, r'\begin{table}[htbp]' + '\n' + r'\centering\small' + '\n' + r'\caption{Frozen compact-policy scaling audit.', r'\subsection{Historical archive evidence and attribution}')
    computation += r'''
The compact method is faster in eight of the 12 paired archived runs;
enumeration is faster in the four six-coordinate single-block cases.
Compact has fewer variables in eight cases and lower whole-process peak
memory in six. Its timing includes executable-policy compilation, whereas
the enumerated method solves the finite game. No repeated-run statistical
speedup claim is made. Online Resource~1 retains all 28 compact settings, including every
small-case comparison and predetermined enumeration skip. Every case has at most 48 underlying target coordinates. The largest
four-block case has 12 targets per block, budget 24, and 38,820 LP variables;
the 48-coordinate, 24-query one-block formulation uses 10,076 variables
for a family containing $32{,}247{,}603{,}683{,}100$ fixed-size batches.

The archived measurements used an Intel Core i7-8565U, Windows 11 and one
numerical thread. Times include construction, solution and compact policy
compilation after imports; peak memory includes interpreter and imports.
Each method/case ran once on a shared host. Enumeration required at most
25,000 fixed-size legal batches and at most 100,000 prefilter candidate
products, which explains the 16 predetermined skips. The 20-second and
1-GiB polling limits did not trigger. Two profiles jointly vary ties and
total heterogeneity, so their effects are not isolated. The largest
normalized primal, stationarity and duality residuals are respectively
$3.78\times10^{-15}$, $5.22\times10^{-15}$ and $5.78\times10^{-16}$;
the archived numerical acceptance threshold is $10^{-7}$. All 560
sampled-policy hard-budget and coordinate-validity checks passed.
'''
    # The complete scaling grid remains in Online Resource 1. The main
    # paper retains every paired eligible comparison plus the range summary.
    computation += '\n\\subsection{Dual completions and adaptive lower bounds}\n'
    computation += local('dual/verification_summary.tex')
    computation += r'''
\subsection{General polytopes and analytic separations}
An independently written implementation constructs the general LPs directly
from six explicit inequality systems with three to five coordinates and a
two-query budget. It covers boxes, a simplex, exact totals, overlapping
constraints and a coupled capacity set. Every legal two-coordinate batch
is evaluated at the computed hardest record. A separately assembled
worst-mean LP checks each dual-derived batch distribution. All 37 batches
and 24 possible first-query choices are retained. Table~\ref{tab:general-values}
distinguishes three objectives instead of calling their different values
optimization discrepancies.
\begin{table}[htbp]\centering\small
\caption{Six constructed polytope checks, with budget two. Mean is the
optimal randomized worst expected width (batch and adaptive); adaptive
and batch columns are deterministic worst widths. Each row's complete
inequalities and witnesses are supplied.}\label{tab:general-values}
\begin{tabular}{lrrr}\toprule
Polytope & Mean & Deterministic adaptive & Deterministic batch\\\midrule
'''
    names = ['Capacity triangle', 'Box with signed contrast', 'Simplex', 'Overlapping constraints', 'Fixed total', 'Coupled capacities']
    for name, case in zip(names, gen['cases']):
        vals = [case['mean']['mean_value'], case['two_query']['optimal_deterministic_adaptive_width'], case['mean']['best_deterministic_batch_width']]
        computation += name + ' & ' + ' & '.join(f'{v:.6g}' for v in vals) + r'\\' + '\n'
    computation += r'''\bottomrule\end{tabular}\end{table}
\FloatBarrier
Maximum primal--dual and hardest-record discrepancies are
$1.12\times10^{-16}$ and $5.56\times10^{-16}$, against a $10^{-8}$
checking tolerance and $10^{-9}$ LP feasibility tolerances. The triangle
returns first-query worst widths $(0.5,1,1)$, selecting its capacity
coordinate. The general hardest-record solves take 0.003--0.048 seconds
on these small instances; the first includes solver initialization.
These six instances check the formulations, not large-scale performance
or all possible adaptive policies by enumeration.

Separate checks solve 3,202 endpoint LPs for 1,601 fibers and 28 finite
games for $K=2,\ldots,8$. They include four scaled/offset converse examples,
the exact rational interior witnesses for precision, and 25 adaptive
records per $K$. The largest absolute width discrepancy is
$3.34\times10^{-16}$; the largest endpoint constraint residual is
$2.23\times10^{-16}$, against a $2\times10^{-8}$ scale-aware width
tolerance. The analytic proofs establish the universal claims;
finite numerical checks do not. In particular, the precision verification
uses interior witnesses rather than assuming vertex-only maximization
for an indicator penalty.
\begin{table}[htbp]\centering\small
\caption{Exact family values from Theorem~\ref{prop:risk_K_family},
also checked numerically for the displayed sizes. Success is the worst-case
probability of width at most $1/K$. These are constructed mathematical
instances, not percentages of empirical forecasting improvement.}
\label{tab:family-values}
\begin{tabular}{rrrrrr}\toprule
$K$ & Budget & Mean, both & Squared, batch/adaptive & Success, batch & Success, adaptive\\\midrule
2 & 2 & $1/2$ & $1/2\; /\;1/4$ & 50\% & 100\%\\
4 & 6 & $1/4$ & $1/4\; /\;1/16$ & 25\% & 100\%\\
8 & 14 & $1/8$ & $1/8\; /\;1/64$ & 12.5\% & 100\%\\
\bottomrule\end{tabular}\end{table}
\FloatBarrier
'''
    text += local('editorial/results_start.tex')
    text += '\n\\subsection{Reading budgets and the shared-query mechanism}\n'
    text += local('joint_certification/reading_budget/results.tex')
    mechanism_prose = local('joint_certification/review_mechanism/results.tex')
    mechanism_split = mechanism_prose.index('The absolute-floor calculation')
    text += mechanism_prose[:mechanism_split].replace(
        r'\paragraph{Which cases isolate sharing, and which depend on absolute precision?}',
        r'\paragraph{Which cases isolate the shared-query mechanism?}')
    joint = json_source('work/risk_adaptivity_revision/joint_certification/empirical_all_panel_report.json')
    assert joint['status'] == 'PASS'
    assert [(joint[c]['blocks'], round(joint[c]['blocks'] * joint[c]['means']['adaptive_recorded_success'])) for c in ('original','external')] == [(819,641),(279,252)]
    precision = json_source('work/risk_adaptivity_revision/joint_certification/precision_all_panel_report.json')
    assert precision['status'] == 'PASS'
    assert [precision['summary'][c]['matching_half'] for c in ('original','external')] == [165,57]
    noise = json_source('work/risk_adaptivity_revision/joint_certification/noise_external_results/report.json')
    assert noise['status'] == 'PASS' and noise['summary']['error_1pct']['adaptive_vs_all_randomized_precision_separations'] == 45
    adverse = json_source('work/risk_adaptivity_revision/joint_certification/noise_external_results/strengthened_batch_bounds.json')
    assert adverse['summary']['error_1pct']['at_most_half'] == 26
    paired = json_source('work/risk_adaptivity_revision/joint_certification/empirical_paired_all_results/report.json')
    assert paired['status'] == 'PASS' and paired['draws'] == 2000 and paired['base_seed'] == 20261013
    text += '\n\\subsection{Joint precision with two shared readings}\\label{sec:joint-results}\n'
    completion_root = 'joint_certification/precision_completion_probe/'
    completion = json_source('work/risk_adaptivity_revision/' + completion_root + 'all_418/report.json')
    completion_check = json_source('work/risk_adaptivity_revision/' + completion_root + 'all_418/independent_check.json')
    assert completion['status'] == completion_check['status'] == 'PASS'
    assert completion['closed'] == completion_check['checks']['matched_continuum_optima'] == 418
    assert completion_check['producer_report_sha256'] == sha(BASE / (completion_root + 'all_418/report.json'))
    READ.add(BASE / (completion_root + 'check_completion.py'))
    assert completion_check['checker_sha256'] == sha(BASE / (completion_root + 'check_completion.py'))
    refined = json_source('work/risk_adaptivity_revision/' + completion_root + 'refined_all/independent_check.json')
    replay = json_source('work/risk_adaptivity_revision/' + completion_root + 'refined_all/recorded_replay_summary.json')
    replay_check = json_source('work/risk_adaptivity_revision/' + completion_root + 'refined_all/recorded_replay_check.json')
    READ.add(BASE / (completion_root + 'refined_all/report.json'))
    assert refined['status'] == replay['status'] == replay_check['status'] == 'PASS'
    assert refined['total_cases'] == refined['checks']['matched_continuum_optima'] == replay['cases'] == replay_check['recorded_blocks'] == 1098
    assert refined['unresolved_cases'] == 0 and replay['policies_changed'] is False
    assert refined['producer_report_sha256'] == replay['policy_sha256_before_recorded_read'] == replay_check['policy_sha256'] == sha(BASE / (completion_root + 'refined_all/report.json'))
    assert replay_check['replay_summary_sha256'] == sha(BASE / (completion_root + 'refined_all/recorded_replay_summary.json'))
    assert replay_check['maximum_numeric_summary_discrepancy'] == 0
    READ.add(BASE / (completion_root + 'check_recorded_replay.py'))
    assert replay_check['checker_sha256'] == sha(BASE / (completion_root + 'check_recorded_replay.py'))
    text += local(completion_root + 'results_exact.tex')
    text += local('joint_certification/final_review_comparators.tex')
    text += local('joint_certification/empirical_manuscript_fragment.tex').replace(
        r'Sections~\ref{sec:external-hpm} and~\ref{sec:counter-precision-results}',
        r'Section~\ref{sec:joint-protocol-summary}').replace('% INSERT COMPLETED PRECISION REPLAY', local('editorial/replay_precision_short.tex'))
    text += local('joint_certification/final_review_results/main_system_table.tex')
    text += local('joint_certification/final_review_dependence_paragraph.tex')
    decision_root = 'joint_certification/decision_tolerance_probe/'
    decision = json_source('work/risk_adaptivity_revision/' + decision_root + 'results/report.json')
    decision_check = json_source('work/risk_adaptivity_revision/' + decision_root + 'results/independent_check.json')
    decision_saved = json_source('work/risk_adaptivity_revision/' + decision_root + 'saved_replay/report.json')
    assert decision['status'] == decision_check['status'] == decision_saved['status'] == 'PASS'
    assert decision['cases'] == decision_check['source_bound_blocks'] == decision_saved['blocks'] == 1098
    assert decision_check['producer_report_sha256'] == decision_saved['producer_report_sha256'] == sha(BASE / (decision_root + 'results/report.json'))
    for name, check in [('check.py', decision_check), ('replay_saved.py', decision_saved)]:
        READ.add(BASE / (decision_root + name))
        assert check['checker_sha256'] == sha(BASE / (decision_root + name))
    assert [[decision['cohorts'][c]['factors']['1/100']['policies'][p]['certified_expected_count']
             for p in ('adaptive','greedy','deterministic_batch')]
            for c in ('original','external')] == [['189','186','188'],['277','277','263']]
    decision_full = local(decision_root + 'manuscript_fragment.tex')
    text += local('editorial/decision_results_short.tex')
    diagnostics = json_source('work/risk_adaptivity_revision/joint_certification/final_challenger_diagnostics/results/report.json')
    diagnostics_check = json_source('work/risk_adaptivity_revision/joint_certification/final_challenger_diagnostics/independent_check.json')
    assert diagnostics['status'] == diagnostics_check['status'] == 'PASS'
    assert diagnostics['blocks'] == diagnostics_check['exact_regime_cases'] == 1098
    assert diagnostics_check['coefficient_derived_cases'] == 279
    assert [(r['fixed_guarantee'], r['adaptive_only_guarantee'], r['no_deterministic_adaptive_guarantee']) for r in diagnostics['regimes']] == [(162,168,489),(128,57,94)]
    challenger_history = local('joint_certification/final_challenger_diagnostics/manuscript_fragment.tex')
    text += challenger_history[:challenger_history.index(r'\paragraph{A stronger fallback check.}')]
    assurance = json_source('work/risk_adaptivity_revision/joint_certification/assurance_feasibility/executed_all/report.json')
    assert assurance['status'] == 'PASS'
    assert assurance['randomized_adaptive_success_upper_bound_on_no_guarantee_cases'] == '19/20'
    assert assurance['actual_check_counts']['seed_independent_adverse_distributions'] == 583
    for cohort, count in [('original', 489), ('external', 94)]:
        assert assurance['regimes'][cohort]['no_deterministic_adaptive_guarantee'] == count
    text += local('editorial/assurance_results.tex')
    mechanism = json_source('work/risk_adaptivity_revision/joint_certification/review_mechanism/executed/report.json')
    mechanism_check = json_source('work/risk_adaptivity_revision/joint_certification/review_mechanism/executed/independent_check.json')
    assert mechanism['status'] == mechanism_check['status'] == 'PASS'
    assert mechanism_check['producer_report_sha256'] == sha(BASE / 'joint_certification/review_mechanism/executed/report.json')
    assert mechanism_check['checker_sha256'] == sha(BASE / 'joint_certification/review_mechanism/check.py')
    assert mechanism['summaries']['all']['joint_only'] == 191
    assert mechanism['summaries']['all']['scalar_obstruction'] == 34
    for name in ['analyze.py', 'check.py', 'check_training.py', 'input_binding.py', 'decision_plan.py']:
        READ.add(BASE / 'joint_certification/review_mechanism' / name)
    assert mechanism['producer_sha256'] == sha(BASE / 'joint_certification/review_mechanism/analyze.py')
    threshold = json_source('work/risk_adaptivity_revision/joint_certification/review_thresholds/executed/report.json')
    threshold_check = json_source('work/risk_adaptivity_revision/joint_certification/review_thresholds/executed/independent_check.json')
    assert threshold['status'] == threshold_check['status'] == 'PASS'
    assert threshold['case_count'] == 222
    assert threshold_check['report_sha256'] == sha(BASE / 'joint_certification/review_thresholds/executed/report.json')
    for name in ['threshold_stability.py', 'check_threshold_stability.py']:
        READ.add(BASE / 'joint_certification/review_thresholds' / name)
    assert threshold['producer_sha256'] == sha(BASE / 'joint_certification/review_thresholds/threshold_stability.py')
    capacity = json_source('work/risk_adaptivity_revision/joint_certification/review_capacity/executed_all/report.json')
    capacity_lp = json_source('work/risk_adaptivity_revision/joint_certification/review_capacity/fresh_capacity_independent.json')
    assert capacity['status'] == capacity_lp['status'] == 'PASS'
    capacity_check = json_source('work/risk_adaptivity_revision/joint_certification/review_capacity/executed_all/independent_check.json')
    assert capacity_check['status'] == 'PASS'
    assert capacity_check['report_sha256'] == sha(BASE / 'joint_certification/review_capacity/executed_all/report.json')
    assert capacity_check['checker_sha256'] == sha(BASE / 'joint_certification/review_capacity/check_capacity.py')
    assert capacity['all_fixed_batches_checked'] == 70272
    assert capacity_lp['endpoint_LP_count'] == 21168
    assert capacity_lp['max_conditional_line_discrepancy'] < 1e-8
    READ.add(BASE / 'joint_certification/review_capacity/analyze_capacity.py')
    READ.add(BASE / 'joint_certification/review_capacity/check_capacity.py')
    assert capacity['source_sha256'] == sha(BASE / 'joint_certification/review_capacity/analyze_capacity.py')
    text += '\n\\subsection{Additional information and precision requirements}\n'
    text += '\\paragraph{Absolute precision.}\n' + mechanism_prose[mechanism_split:]
    text += local('joint_certification/review_thresholds/manuscript_fragment.tex')
    text += local('joint_certification/review_capacity/manuscript_fragment.tex')
    sensitivity_report = json_source('work/risk_adaptivity_revision/joint_certification/review_sensitivity/results/report.json')
    sensitivity_check = json_source('work/risk_adaptivity_revision/joint_certification/review_sensitivity/independent_check.json')
    assert sensitivity_report['status'] == sensitivity_check['status'] == 'PASS'
    assert sensitivity_report['blocks'] == 1098 and sensitivity_report['outcome_rows'] == 5490
    assert sensitivity_report['new_forecast_fits'] == sensitivity_report['new_policy_optimizations'] == 0
    sensitivity_history = local('joint_certification/review_sensitivity/manuscript_fragment.tex')
    sensitivity_replay = sensitivity_history[sensitivity_history.index(r'\paragraph{Sensitivity to the reporting target.}'):]
    # The geometry/replay figure presents these counts; retain the numeric table in S8.
    text += '\n\\FloatBarrier\n'
    text += local('joint_certification/noise_manuscript_fragment.tex')
    text += local('editorial/verification_focused.tex')
    lineage = json_source('work/risk_adaptivity_revision/joint_certification/provenance_chain/executed/table_chain.json')
    assert lineage['status'] == 'PASS' and lineage['all_case_ledger_rows_compared'] == 1098
    assert lineage['maximum_ledger_numeric_difference'] == 0
    assert [lineage['tables'][c]['matched_half_blocks'] for c in ('original','external')] == [165,57]
    counter = json_source('work/risk_adaptivity_revision/counter_adaptive/summary/report.json')
    assert counter['tasks']==4914 and counter['groups']['overall'][0]['strong_separations']==290
    half = json_source('work/risk_adaptivity_revision/counter_adaptive/math_review/half_cover_verification.json')
    assert half['status']=='PASS' and half['strong_cases']==290
    assert half['distribution']['exactly_half']==290
    triage = json_source('work/risk_adaptivity_revision/counter_adaptive/feedback_triage/report.json')
    assert triage['status']=='PASS' and triage['cases']==4914
    assert triage['counts']=={'batch_suffices':4371,'feedback_required':290,'adaptive_not_guaranteed':253}
    assert triage['exact_half_cases']==290
    qualification = json_source('work/risk_adaptivity_revision/external_validation/operational/source_qualification_check.json')
    assert qualification['status'] == 'PASS' and qualification['selected_systems'] == [1, 2, 7]
    assert qualification['verified_cached_response_hashes'] == 41
    lower = json_source('work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/failure_diagnostics/verification.json')
    assert lower['status'] == 'PASS' and lower['case_levels'] == 9
    assert (lower['legal_first_queries_checked'], lower['endpoint_pairs_checked']) == (45, 180)
    fallback = json_source('work/risk_adaptivity_revision/external_validation/stored_error_fallback/report.json')
    assert fallback['status'] == 'PASS' and fallback['cases'] == 29
    assert fallback['hybrid_budget_counts'] == {'1': 0, '2': 22, '3': 7, '4': 0, '5': 0}
    assert (fallback['total_hybrid_reserved_queries'], fallback['total_fixed_reserved_queries']) == (65, 87)
    fallback_exact = json_source('work/risk_adaptivity_revision/external_validation/stored_error_fallback/INDEPENDENT_CERTIFICATE_CHECKS.json')
    assert fallback_exact['status'] == 'PASS' and fallback_exact['fixed_batch_certificates_exactly_checked'] == 29
    assert fallback_exact['maximum_fixed_upper'] < 0.458896
    branch = json_source('work/risk_adaptivity_revision/external_validation/stored_error_fallback/INDEPENDENT_BRANCH_CHECKS.json')
    assert branch['status'] == 'PASS' and branch['whole_answer_domains_certified'] == 22
    assert branch['conditional_affine_dual_lines_checked'] == 44
    execution = json_source('work/risk_adaptivity_revision/external_validation/stored_error_fallback/execution_checks.json')
    assert execution['status'] == 'PASS' and execution['constructed_executions'] == 1015
    assert execution['out_of_model_cases_rejected'] == 29 and execution['online_optimization_calls'] == 0
    sensitivity = local('external_validation/stored_error_sensitivity/manuscript_fragment.tex')
    begin_sensitivity = '% BEGIN MANUSCRIPT BODY'
    end_sensitivity = '% END MANUSCRIPT BODY'
    if begin_sensitivity in sensitivity:
        sensitivity = between(sensitivity, begin_sensitivity, end_sensitivity).replace(begin_sensitivity, '', 1)
    text += local('editorial/api_results_short.tex')
    gate_root = 'work/risk_adaptivity_revision/practical_retrieval_gate/'
    gate = json_source(gate_root + 'results/report.json')
    gate_check = json_source(gate_root + 'results/independent_check.json')
    gate_timing = json_source(gate_root + 'inputs/reported_gate_timing.json')
    assert gate['status'] == gate_check['status'] == gate_timing['status'] == 'PASS'
    assert gate['blocks'] == gate_check['exact_gates_checked'] == 1098
    assert gate_check['direct_vertex_loss_checks'] == 39528
    assert gate_check['exact_live_total_checks'] == 279
    assert gate_check['saved_HTTP_requests_checked'] == 12
    assert gate_check['external_zero_query_decisions_validated'] == 198
    assert gate_check['external_bulk_selected_decisions_validated'] == 81
    for cohort, count, skipped, warm, cold in [
            ('original', 819, 8, 811, 1630), ('external', 279, 198, 81, 360)]:
        row = gate['cohorts'][cohort]
        assert (row['blocks'], row['zero_query_certificates']) == (count, skipped)
        assert row['immediate']['gated_warm']['requests'] == warm
        assert row['immediate']['gated_cold']['requests'] == cold
        assert row['retrospective']['cold_whole_period_bulk']['requests'] == 3
    for script in ['analyze.py', 'check_saved.py', 'time_gate.py', 'run.py',
                   'verify_source_inputs.py']:
        READ.add(ROOT / (gate_root + script))
    READ.add(ROOT / (gate_root + 'inputs/public_decision_inputs_coherent.json'))
    assert gate['source_sha256'] == sha(ROOT / (gate_root + 'analyze.py'))
    assert gate_check['source_sha256'] == sha(ROOT / (gate_root + 'check_saved.py'))
    assert gate_check['analyzed_report_sha256'] == sha(ROOT / (gate_root + 'results/report.json'))
    assert gate['input_sha256'] == gate_check['input_sha256'] == sha(ROOT / (gate_root + 'inputs/public_decision_inputs_coherent.json'))
    assert gate_timing['source_sha256'] == sha(ROOT / (gate_root + 'time_gate.py'))
    gate_full = local('practical_retrieval_gate/manuscript_fragment.tex')
    selector_report = json_source('work/risk_adaptivity_revision/protocol_selection/results/report.json')
    selector_check = json_source('work/risk_adaptivity_revision/protocol_selection/independent_results/report.json')
    assert selector_report['status'] == selector_check['status'] == 'PASS'
    assert selector_report['scenario_cases'] == selector_check['case_scenario_rows'] == 116
    assert selector_check['candidate_exclusion_checks'] == 348
    assert (selector_report['constructed_callback_executions'], selector_report['blocked_dispatches']) == (109, 7)
    assert selector_report['scenarios']['public_bulk']['protocol_counts'] == {'bulk_range': 29}
    assert selector_report['scenarios']['restricted_three_readings']['reserved_scalar_readings'] == 65
    assert selector_report['scenarios']['restricted_one_round']['reserved_scalar_readings'] == 87
    cost = json_source('work/risk_adaptivity_revision/protocol_selection/cost_frontier_results/report.json')
    cost_check = json_source('work/risk_adaptivity_revision/protocol_selection/cost_frontier_independent.json')
    assert cost['status'] == cost_check['status'] == 'PASS'
    assert cost['case_ratio_rows'] == cost_check['case_ratio_rows'] == 174
    assert cost_check['exhaustive_per_case_candidate_evaluations'] == 306
    assert [s['cost_aware_cost_exact'] for s in cost['summaries']] == ['65', '311/4', '181/2', '116', '145', '203']
    historical = local('editorial/evaluation_historical.tex')
    division = historical.index(r'\subsection{The retained adverse recovery result}')
    text += local('editorial/discussion_short.tex')
    # Detailed empirical witnesses and historical protocols are indexed online.
    protocol = between(old, r'\section{Historical Energy Study: Design and Reproducibility}', r'\subsection{Additional designs and reproducibility}')
    # The archival recovery development is supplied, but is not a new core experiment.
    protocol = protocol.replace(r'\subsection{Recovery experiment}', r'\subsection{Archived recovery experiment}')
    protocol = protocol.replace(r'\cite{', r'\citep{')
    protocol = protocol.replace('Section~\\ref{sec:archive-access}', 'Section~\\ref{sec:historical-application}')
    protocol = protocol.replace('primary model', 'historical observation model')
    protocol = protocol.replace('We also executed a fresh fitting replay for all 34 original series and all 30 additional consumers from the pinned raw sources,', 'As archived verification of the earlier study, a fresh fitting replay was executed for all 34 original series plus a separate 30-consumer Portugal replication cohort from the same source/calendar, from the pinned raw sources,')
    protocol = protocol.replace('ordering and regret.', 'ordering.')
    protocol = between(protocol, r'\section{Historical Energy Study: Design and Reproducibility}', r'\subsection{Additional designs and reproducibility}') if r'\subsection{Additional designs and reproducibility}' in protocol else protocol
    start_regret = protocol.index('The minimax rule and')
    end_regret = protocol.index('\n\n', start_regret)
    protocol = protocol[:start_regret] + protocol[end_regret:]
    protocol = protocol.replace(r'\label{app:historical-design}', r'\label{app:historical-design}' + '\nThe following specifications document the reused historical study. Its\narchived broader recovery tests are distinguished from this revision\'s\nnew mathematical checks and extended additional-consumer grid.\nNo new forecast fit is introduced.\n')
    grid = between(old, r'\begin{table}[htbp]' + '\n' + r'\centering\small\setlength{\tabcolsep}{4pt}' + '\n' + r'\caption{Complete historical scenario grid', r'\subsection{Historical robust gain and adverse realized tradeoff}')
    # Preserve the full current supporting methods in one indexed source,
    # rather than requiring a reviewer to search older manuscript versions.
    extended = ('% ONLINE RESOURCE 1: current extended methods and historical controls.\n'
                '% LaTeX content fragment, not a replacement manuscript.\n'
                '% Cross-references retain their semantic labels from the main source.\n'
                + '\\section{S1. Complete compact scaling grid}\n' + scaling
                + '\\section{S2. Historical certification, gates and controls}\n'
                + historical[:division] + local('practical/practical_subsection.tex')
                + local('practical_multi/manuscript_fragment.tex')
                + local('editorial/practical_api.tex') + historical[division:]
                + protocol.replace('\\section{Historical Energy Study: Design and Reproducibility}',
                                   '\\section{S3. Full historical design and reproducibility}')
                + '\\section{S4. Complete historical grid aggregates}\\label{app:certificate-grid}\n'
                + grid + '\\section{S5. Full structured coordinate-recovery construction}\n'
                + structured + compact + dualproof
                + '\\section{S6. Extended counter and measurement checks}\n'
                + local('external_validation/math/counter_two_side.tex')
                + local('counter_adaptive/manuscript_results.tex')
                + local('counter_adaptive/reviewer_diagnostics/complete_witness.tex')
                + local('external_validation/math/manuscript_uncertainty_appendix.tex')
                + local('editorial/stored_error_full.tex')
                + local('external_validation/math/manuscript_caps.tex')
                + local('external_validation/replay/manuscript_fragment.tex')
                + '\\section{S7. Detailed computational verification}\n' + computation
                + '\\section{S8. Shared-query certificates and protocol selection}\n'
                + local('joint_certification/proof_supplement.tex')
                + local('joint_certification/empirical_methods_supplement.tex')
                + local('joint_certification/empirical_paired_all_results/paired_table.tex')
                + local('joint_certification/final_review_methods.tex')
                + local('joint_certification/final_review_results/supporting_dependence_table.tex')
                + local('joint_certification/review_sensitivity/results/threshold_table.tex')
                + local('joint_certification/noise_proof_fragment.tex')
                + local('joint_certification/precision_proof_fragment.tex')
                + '\\subsection{Earlier restricted-cover comparator diagnostics}\n'
                + challenger_history[challenger_history.index(r'\paragraph{A stronger fallback check.}'):]
                + sensitivity_history[:sensitivity_history.index(r'\paragraph{Sensitivity to the reporting target.}')]
                + '\nThe full precision-game completion in the main paper supersedes these earlier open bounds.\n'
                + local(completion_root + 'historical_cover_replay.tex')
                + local('protocol_selection/manuscript_fragment.tex')
                + local('protocol_selection/manuscript_fragment_cost.tex')
                + '\\section{S9. Scalar examples and growing separations}\n'
                + scalar_example
                + growing_support.replace(r'\section{Growing moment and precision separations}',
                                          r'\subsection{Growing scalar-family separation: complete proof}')
                + general_algorithms.replace(
                    r'\section{Computing policies and hardest records on polytopes}',
                    r'\section{S10. Computing policies and hardest records on polytopes}')
                  .replace('The constant $d$ does not affect width.',
                           'The constant $d$ does not affect width. Write '
                           r'$\rho=\max_{y\in F}\min_{Q\in\mathcal Q}W_Q(y)$ '
                           'for the hardest-record value, equal to the optimal '
                           'randomized worst expected width by the scalar theorem in S11.')
                + '\\section{S11. Scalar penalty classification and full information proofs}\n'
                + scalar_setup + classification
                + '\\section{S12. General dimensional precision bound}\n' + helly_full
                + '\\section{S13. Scalar cumulative-counter planning and feedback triage}\n'
                + counter_full
                + '\\section{S14. A separate mean joint-width separation}\n'
                + inspectable + joint_algorithms
                + '\\section{S15. Complete operational and historical controls}\n'
                + local('editorial/pairwise_controls_short.tex')
                + local('editorial/operational_api_results.tex')
                + local('editorial/protocol_selection_short.tex')
                + local('editorial/computation_short.tex')
                + local('editorial/historical_control_short.tex')
                + '\\subsection{Full implementation and source-to-table checks}\n'
                + local('joint_certification/verification_main.tex')
                + local('joint_certification/provenance_chain/manuscript_fragment.tex')
                + '\\section{S16. Certificate-gated retrieval for a model tolerance}\n'
                + gate_full
                + '\\section{S17. Worked certificate and supporting proof details}\n'
                + '\\subsection{Complete proof of the three-model corollary}\n'
                + corollary_proof + boundary_execution
                + worked_full + worked_absolute
                + '\\section{S18. Secondary recorded-policy and model-decision results}\n'
                + local(completion_root + 'results_replay.tex') + decision_full
                + sensitivity_replay + full_figure)
    # Historical S15 extracts repeat four section declarations. Keep the
    # original semantic targets and give only the later declarations unique IDs.
    repeated_labels = {'sec:historical-application', 'sec:counter-precision-results',
                       'sec:stored-error-sensitivity', 'sec:external-hpm'}
    seen_extended_labels = set()
    def unique_extended_label(match):
        label = match.group(1)
        if label in seen_extended_labels:
            assert label in repeated_labels, 'Unexpected duplicate extended label: ' + label
            replacement = label + ':s15'
            assert replacement not in seen_extended_labels
            seen_extended_labels.add(replacement)
            return r'\label{' + replacement + '}'
        seen_extended_labels.add(label)
        return match.group(0)
    extended = re.sub(r'\\label\{([^}]+)\}', unique_extended_label, extended)
    # References to relocated appendices now identify the indexed resource.
    for label, section in [('app:stored-error', 'S6'),
                           ('app:complete-counter-witness', 'S6'),
                           ('app:historical-design', 'S3')]:
        text = text.replace('Appendix~\\ref{' + label + '}',
                            'Online Resource~1, ' + section)

    extended_path = BASE / 'editorial/online_extended_methods.tex'
    text += local('editorial/declarations.tex')

    # Follow the PeerJ research-article structure while keeping the complete
    # mathematical argument in the main manuscript. Semantic labels survive.
    method_start = text.index(r'\section{Model Comparisons and Sharp Information}')
    method_end = text.index(r'\section{Results}', method_start)
    methods = text[method_start:method_end]
    methods = re.sub(r'\\(sub)?section\{',
                     lambda m: r'\subsubsection{' if m.group(1) else r'\subsection{',
                     methods)
    text = (text[:method_start] + r'\section{Methods}\label{sec:methods}' + '\n'
            + methods + text[method_end:])

    bibliography = local('editorial/references.tex') + local('general/new_references.tex') + local('counter_adaptive/literature/references.tex')
    items = re.split(r'(?=\\bibitem\[)', bibliography)
    entries = []
    online_entries = []
    cited = {k.strip() for group in re.findall(r'\\cite(?:p|t)?(?:\[[^]]*\])?\{([^}]+)\}', text) for k in group.split(',')}
    online_cited = {k.strip() for group in re.findall(r'\\cite(?:p|t)?(?:\[[^]]*\])?\{([^}]+)\}', extended) for k in group.split(',')}
    for item in items:
        m = re.match(r'\\bibitem\[([^]]+)\]\{([^}]+)\}', item)
        if not m: continue
        if m.group(2) not in cited | online_cited: continue
        sort = re.sub(r'[^A-Za-z0-9 ]', '', m.group(1)).lower()
        sort = {'krieg2025': 'krieg novak ullrich', 'krieg2026': 'krieg ullrich',
                'novak1995': 'novak 1995', 'novak2008': 'novak wozniakowski 2008'}.get(m.group(2), sort)
        if m.group(2) in cited:
            entries.append((sort, m.group(2), item.strip()))
        if m.group(2) in online_cited:
            online_entries.append((sort, m.group(2), item.strip()))
    entries.sort()
    online_entries.sort()
    assert {k for _, k, _ in online_entries} == online_cited
    extended += '\n\\begin{thebibliography}{99}\n' + '\n\n'.join(i for _, _, i in online_entries) + '\n\\end{thebibliography}\n'
    extended_bytes = extended.replace('\r\n', '\n').encode('utf-8')
    assert {k for _, k, _ in entries} == cited, cited - {k for _, k, _ in entries}
    text += '\n\\FloatBarrier\n\\begin{thebibliography}{99}\n' + '\n\n'.join(i for _, _, i in entries) + '\n\\end{thebibliography}\n\\end{document}\n'
    labels = re.findall(r'\\label\{([^}]+)\}', text)
    refs = re.findall(r'\\(?:ref|eqref)\{([^}]+)\}', text)
    assert len(labels) == len(set(labels)), 'Duplicate labels'
    assert set(refs) <= set(labels), set(refs) - set(labels)
    abstract = between(text, r'\begin{abstract}', r'\end{abstract}')
    words = len(re.findall(r'\S+', abstract)) - 1
    assert 150 <= words <= 250, words
    payload = text.replace('\r\n', '\n').encode('utf-8')
    output = ROOT / 'outputs/revised_manuscript.tex'
    manifest_path = ROOT / 'outputs/risk_release_manifest.json'
    READ.add(Path(__file__))
    record = {'status': 'passed', 'title': 'Adaptive Reading Budgets for Joint Forecast Audits with Cumulative Data',
              'target': 'PeerJ Computer Science', 'input_sha256': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in sorted(READ)},
              'output_sha256': hashlib.sha256(payload).hexdigest(), 'abstract_words_whitespace': words,
              'online_extended_methods_sha256': hashlib.sha256(extended_bytes).hexdigest(),
              'labels': len(labels), 'references': len(entries), 'citation_style': 'author-year; alphabetized first-author surnames',
              'historical_empirical_result_changes': False}
    if not args.freeze:
        previous = json.loads(manifest_path.read_text())
        assert previous == record, 'Composition or inputs changed; review before freezing again'
    output.write_bytes(payload)
    extended_path.write_bytes(extended_bytes)
    if args.freeze:
        manifest_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in record.items() if k != 'input_sha256'}, indent=2))

if __name__ == '__main__':
    main()
