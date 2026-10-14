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
    workflow_marker = 'Our primary contribution is the mathematical classification'
    assert text.count(workflow_marker) == 1
    text = text.replace(workflow_marker,
                        local('editorial/audit_workflow.tex') + '\n' + workflow_marker, 1)
    old_prior = between(text, 'The width of an information fiber', 'Information-dependent decisions')
    text = text.replace(old_prior, local('general/prior_art_precision.tex') + '\n')
    # Pinpoint related-work prose carries the comparison without a duplicate table.
    theory = local('math/theorem_proof.tex')
    for title in ('Universal classification of width penalties', 'Sharp growing separations'):
        start = theory.index(r'\begin{proposition}[' + title + ']')
        end = theory.index(r'\end{proposition}', start) + len(r'\end{proposition}')
        theory = theory[:start] + theory[start:end].replace('{proposition}', '{theorem}') + theory[end:]
    theory = theory.replace("Sion's minimax theorem\ntherefore", "Sion's minimax theorem \\citep{sion1958}\ntherefore")
    text += theory + local('general/algorithms.tex')
    text += local('editorial/helly_focused.tex')
    text += local('counter_adaptive/literature/counter_methods.tex')
    text += local('editorial/counter_half_corollary.tex')
    text += local('counter_adaptive/feedback_triage/math_review.tex')
    joint_methods = local('joint_certification/manuscript_methods.tex')
    joint_definition = between(joint_methods,
                               'An auditor comparing several models',
                               'The scalar assumption')
    joint_algorithms = joint_methods[joint_methods.index('For the uncapped exact-total simplex'):]
    inspectable = local('joint_certification/main_inspectable_proof.tex')
    inspectable = inspectable.replace(r'\begin{theorem}',
                                     joint_definition + r'\begin{theorem}', 1)
    text += inspectable + joint_algorithms
    text += local('joint_certification/main_planner_algorithm.tex')
    text += local('joint_certification/final_practical_figure/clarification.tex')
    text += local('joint_certification/main_worked_precision_certificate.tex')
    text += local('joint_certification/absolute_width_fragment.tex')
    text += local('joint_certification/absolute_width_results/main_table.tex')
    figure_check = json_source('work/risk_adaptivity_revision/joint_certification/final_practical_figure/independent_check.json')
    figure_data = json_source('work/risk_adaptivity_revision/joint_certification/final_practical_figure/figure_data.json')
    assert figure_check['status'] == 'PASS'
    assert figure_check['envelope_equalities'] == 735 and figure_check['replay_points_checked'] == 30
    assert figure_check['figure_data_sha256'] == sha(BASE / 'joint_certification/final_practical_figure/figure_data.json')
    text += local('joint_certification/final_practical_figure/figure_fragment.tex')
    text += local('editorial/measurement_assumptions.tex')
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
    text += ('Table~\\ref{tab:joint_objectives} separates the planning objectives from\n'
             'recorded precision success. Table~\\ref{tab:joint_precision_status}\n'
             'identifies where the precision challenger has matching bounds.\n')
    text += local('joint_certification/final_review_comparators.tex')
    text += local('joint_certification/empirical_manuscript_fragment.tex')
    text += local('joint_certification/final_review_results/main_system_table.tex')
    text += local('joint_certification/final_review_dependence_paragraph.tex')
    text += local('joint_certification/precision_manuscript_fragment.tex')
    diagnostics = json_source('work/risk_adaptivity_revision/joint_certification/final_challenger_diagnostics/results/report.json')
    diagnostics_check = json_source('work/risk_adaptivity_revision/joint_certification/final_challenger_diagnostics/independent_check.json')
    assert diagnostics['status'] == diagnostics_check['status'] == 'PASS'
    assert diagnostics['blocks'] == diagnostics_check['exact_regime_cases'] == 1098
    assert diagnostics_check['coefficient_derived_cases'] == 279
    assert [(r['fixed_guarantee'], r['adaptive_only_guarantee'], r['no_deterministic_adaptive_guarantee']) for r in diagnostics['regimes']] == [(162,168,489),(128,57,94)]
    text += local('joint_certification/final_challenger_diagnostics/manuscript_fragment.tex')
    sensitivity_report = json_source('work/risk_adaptivity_revision/joint_certification/review_sensitivity/results/report.json')
    sensitivity_check = json_source('work/risk_adaptivity_revision/joint_certification/review_sensitivity/independent_check.json')
    assert sensitivity_report['status'] == sensitivity_check['status'] == 'PASS'
    assert sensitivity_report['blocks'] == 1098 and sensitivity_report['outcome_rows'] == 5490
    assert sensitivity_report['new_forecast_fits'] == sensitivity_report['new_policy_optimizations'] == 0
    text += local('joint_certification/review_sensitivity/manuscript_fragment.tex')
    # Figure 1(b) presents these same counts; retain the numeric table in S8.
    text += '\n\\FloatBarrier\n'
    text += local('joint_certification/noise_manuscript_fragment.tex')
    text += local('joint_certification/verification_main.tex')
    lineage = json_source('work/risk_adaptivity_revision/joint_certification/provenance_chain/executed/table_chain.json')
    assert lineage['status'] == 'PASS' and lineage['all_case_ledger_rows_compared'] == 1098
    assert lineage['maximum_ledger_numeric_difference'] == 0
    assert [lineage['tables'][c]['matched_half_blocks'] for c in ('original','external')] == [165,57]
    text += local('joint_certification/provenance_chain/manuscript_fragment.tex')
    counter = json_source('work/risk_adaptivity_revision/counter_adaptive/summary/report.json')
    assert counter['tasks']==4914 and counter['groups']['overall'][0]['strong_separations']==290
    half = json_source('work/risk_adaptivity_revision/counter_adaptive/math_review/half_cover_verification.json')
    assert half['status']=='PASS' and half['strong_cases']==290
    assert half['distribution']['exactly_half']==290
    triage = json_source('work/risk_adaptivity_revision/counter_adaptive/feedback_triage/report.json')
    assert triage['status']=='PASS' and triage['cases']==4914
    assert triage['counts']=={'batch_suffices':4371,'feedback_required':290,'adaptive_not_guaranteed':253}
    assert triage['exact_half_cases']==290
    text += local('editorial/pairwise_controls_short.tex')
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
    text += local('editorial/operational_api_results.tex')
    text += local('editorial/protocol_selection_short.tex')
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
    text += local('editorial/computation_short.tex')
    text += local('editorial/historical_control_short.tex')
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
                + local('protocol_selection/manuscript_fragment.tex')
                + local('protocol_selection/manuscript_fragment_cost.tex'))
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
    record = {'status': 'passed', 'title': 'Risk and Adaptivity in Certifying Machine-Learning Model Comparisons',
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
