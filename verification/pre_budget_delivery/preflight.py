"""Check current PeerJ manuscript correspondence and record review scope."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'work/risk_adaptivity_revision'
OUT = ROOT / 'outputs'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


source = OUT / 'revised_manuscript.tex'
pdf = OUT / 'revised_manuscript.pdf'
s = source.read_text(encoding='utf-8')
normalized = re.sub(r'\s+', ' ', s)
extended_source = BASE / 'editorial/online_extended_methods.tex'
extended = extended_source.read_text(encoding='utf-8')
combined = s + '\n' + extended
combined_normalized = re.sub(r'\s+', ' ', combined)
release = json.loads((OUT / 'risk_release_manifest.json').read_text())
assert sha(source) == release['output_sha256']
for name, expected in release['input_sha256'].items():
    assert sha(ROOT / name) == expected, name
reader = PdfReader(pdf)
text = '\n'.join(page.extract_text() or '' for page in reader.pages)
log = (ROOT / 'work/pdf_export/decision_build/revised_manuscript.log').read_text(errors='replace')
bad = re.findall(r'^.*(?:Overfull|Underfull|undefined|Missing character|^!).*$', log, re.M)
assert not bad, bad
for section in ['Introduction', 'Methods', 'Results', 'Discussion', 'Conclusions']:
    assert r'\section{' + section + '}' in s, section
for phrase in ['Background.', 'Methods.', 'Results.', 'Conclusions.']:
    assert r'\textbf{' + phrase + '}' in s
assert 'kapoorjishan19@gmail.com' in s
assert 'kapoorjishan2@gmail.com' not in s
assert 'supplied certified protocols' in extended
assert 'Theorems~2--3 and~5' in s
assert 'one fixed error vector' in s
assert 'two adaptive readings for 22 cases and a fixed three-reading batch for seven' in combined_normalized
assert '0.407 and 0.119' in normalized
assert '0.9738064' in extended
assert 'Bulk retrieval uses one request' in normalized
assert '0.331' in s and '0.497' in s
assert 'protocol-selection' in s
assert 'operational wrapper' in extended
for section in ['S11. Scalar penalty classification and full information proofs',
                'S12. General dimensional precision bound',
                'S13. Scalar cumulative-counter planning and feedback triage',
                'S14. A separate mean joint-width separation',
                'S15. Complete operational and historical controls']:
    assert r'\section{' + section + '}' in extended, section
labels = re.findall(r'\\label\{([^}]+)\}', s)
references = re.findall(r'\\(?:eqref|ref)\{([^}]+)\}', s)
assert labels and references
assert len(labels) == len(set(labels))
assert set(references) <= set(labels)
for filename in ['proof_review.txt', 'novelty_review.txt', 'practice_review.txt']:
    assert (BASE / 'peerj_revision' / filename).is_file()
checks = {
    'selector': BASE / 'protocol_selection/independent_results/report.json',
    'task_binding': BASE / 'protocol_selection/binding_checks/report.json',
    'joint_full_independent': BASE / 'joint_certification/independent_shared_review.json',
    'joint_noise_exact': BASE / 'joint_certification/noise_external_results/independent_check.json',
    'joint_cap_noise_exact': BASE / 'joint_certification/noise_external_capacity_results/independent_check.json',
    'joint_precision_exact': BASE / 'joint_certification/precision_all_panel_check.json',
    'joint_precision_adaptive_link': BASE / 'joint_certification/precision_all_panel_adaptive_check.json',
    'joint_paired_outcomes': BASE / 'joint_certification/empirical_paired_all_independent.json',
    'threshold_independent': BASE / 'joint_certification/review_sensitivity/independent_check.json',
    'threshold_source': BASE / 'joint_certification/review_sensitivity/source_verification.json',
    'final_practical_figure': BASE / 'joint_certification/final_practical_figure/independent_check.json',
    'final_challenger': BASE / 'joint_certification/final_challenger_diagnostics/independent_check.json',
    'final_challenger_both_source': BASE / 'joint_certification/final_challenger_diagnostics/full_source_independent_check.json',
    'two_target_exact': BASE / 'two_target_boundary/solver_free_report.json',
    'two_target_lp': BASE / 'two_target_boundary/numeric_report.json',
    'assurance_external': BASE / 'joint_certification/assurance_feasibility/executed_external/report.json',
    'assurance_both_sources': BASE / 'joint_certification/assurance_feasibility/executed_all/report.json',
}
for path in checks.values():
    assert json.loads(path.read_text())['status'].lower() in {'pass', 'passed'}
assert '165 of 819' in normalized and '57 of 279' in normalized
assert '65.45' in s and '64.91' in s
assert '2,000 seven-day circular' in normalized
assert '169/200' in s and '166/200' in s
assert 'shared-query analysis is retrospective on both panels' in normalized
assert 'not additional independent replications' in normalized
assert 'thm:shared-prefix-separation' in extended
assert 'prop:risk_classification' in extended
assert 'thm:two-target-collapse' in s and 'cor:all-pairs-collapse' in s
assert '7,131' in s and '1,171' in s
assert 'two exact scalar readings' in normalized
assert 'fixed finite query dictionary' in normalized
assert 'tab:guarantee-recorded-tradeoff' in s
assert 'tab:numerical-conventions' in s
assert 'sec:worked-joint-certificate' in s
assert 'tab:measurement-assumptions' in s and 'tab:joint_system_effects' in s
assert 'fourteen-day' in s and '0.47743079' in s
assert r'\usepackage[letterpaper,margin=1in]{geometry}' in s
assert r'\documentclass[12pt]{article}' in s
assert r'\usepackage{newtxtext,ragged2e}' in s
assert r'\AtBeginDocument{\raggedright\linenumbers}' in s
assert r'\section*{Acknowledgements}' in s
assert 'Supplemental Data S1 and S2' in s
assert 'sec:shared-planner-algorithm' in s
assert 'tab:absolute_joint_widths' in s
assert 'widths and width targets' in s
assert 'fig:practical-guarantee-replay' in s
assert 'fig:audit-workflow' in s and 'No two-reading' in s
assert '25 and 13 blocks' in normalized and '64.71' in s
assert 'These unresolved gaps are substantial' in s
assert 'prop:assurance-feasibility' in s and '19/20' in s
assert 'All 489 original and 94 external blocks' in normalized
assert '6,588' in s and '5,490' in s and '11,660' in s
assert '207 blocks and greedy on 208' in normalized
assert 'restricted benchmark' in normalized
assert 'Neither public source documents a service that enforces this particular limit' in normalized
assurance = json.loads(checks['assurance_both_sources'].read_text())
assert assurance['checked_cohorts'] == ['external', 'original']
assert assurance['regimes']['original'] == {
    'fixed_guarantee': 162, 'adaptive_only_guarantee': 168,
    'no_deterministic_adaptive_guarantee': 489}
assert assurance['regimes']['external'] == {
    'fixed_guarantee': 128, 'adaptive_only_guarantee': 57,
    'no_deterministic_adaptive_guarantee': 94}
assert assurance['randomized_adaptive_success_upper_bound_on_no_guarantee_cases'] == '19/20'
assert assurance['bound_is_not_claimed_optimal'] is True
assert assurance['recorded_answers_or_replay_outcomes_used'] is False
assert assurance['actual_check_counts']['strict_failing_fiber_checks'] == 11660
assert assurance['provenance']['exact_coefficient_normalization_checks'] == 6588
record = {
    'status': 'passed', 'review_date': datetime.now(timezone.utc).date().isoformat(),
    'completed_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'PeerJ structure and source/PDF correspondence; analytic and software reviews are separate. Full clean ZIP replay reported separately.',
    'manuscript_sha256': sha(source), 'pdf_sha256': sha(pdf),
    'extended_methods_sha256': sha(extended_source),
    'pdf_pages': len(reader.pages), 'abstract_words': release['abstract_words_whitespace'],
    'builtin_main_compile': 'success', 'manuscript_overfull_or_undefined_warnings': 0,
    'visual_review': 'outputs/peerj_final_visual_review.txt',
    'export_environment_advisory': 'Fontconfig and lineno source-comment encoding advisories; rendered pages separately inspected.',
    'proof_review_kind': 'separate AI-assisted internal analytic review; not external human or formal proof-assistant validation',
    'novelty_repair': 'Fixed-budget two-target boundary, all-three-model-pair realization, complete matching bounds, threshold margin; distinguished from sparse scalar policy bounds and established vector recovery. Existing Osipenko and objective-specific comparisons retained.',
    'practical_repairs': ['strict interface schema', 'canonical typed task/plan binding', 'controlled readout rejection', 'both task-binding checks integrated into default replay'],
    'valid_scientific_ledger_unchanged': True,
    'input_verification_reports': {key: sha(value) for key,value in checks.items()},
    'historical_empirical_result_changes': False,
    'new_assurance_result_scope': 'Finite-witness upper bound on randomized adaptive certainty in the existing uncapped exact-total two-prefix-reading model; external default replay and separate both-source execution remain distinct.',
    'target': 'PeerJ Computer Science',
    'policy_evidence': ['User-supplied current Research Article editorial criteria',
                        'Live browser: https://peerj.com/journals/computer-science/policies/',
                        'Live browser: https://peerj.com/journals/computer-science/author-instructions'],
    'policy_verification_limit': 'Live preparation, code/data, authorship, AI and copyright policies inspected on 2026-10-13. The author confirmed checking AI-tool terms and publication suitability. Separate final-content/record-retention attestations and precise historical AI-version identifiers remain unverified; final portal declarations and fees have not been accepted. Supplement upload limits require the separately checked S1/S2 package, not the larger private development archive.',
    'acceptance_probability': 'No calibrated individual acceptance probability follows from internal corrections or numerical checks.',
    'submission_status': 'not submitted', 'external_contact': False,
}
(OUT / 'risk_editorial_verification.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({key: record[key] for key in ['status','manuscript_sha256','pdf_sha256','pdf_pages','abstract_words']},indent=2))
