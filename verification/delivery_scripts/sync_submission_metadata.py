"""Keep prepared portal fields consistent with the saved manuscript."""
from pathlib import Path
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs'
path = OUT / 'PEERJ_SUBMISSION_METADATA.json'
history = OUT / 'pre_diagnostics_PEERJ_SUBMISSION_METADATA.json'
if not history.exists():
    shutil.copy2(path, history)
data = json.loads(path.read_text())
assert 'not submitted' in data['status'].lower()
assert data['last_recorded_browser_attempt']['submitted'] is False
assert data['last_recorded_browser_attempt']['journal_form_accessed'] is True
assert data['last_recorded_browser_attempt']['signed_in'] is True
source = (OUT / 'revised_manuscript.tex').read_text(encoding='utf-8')
title=' '.join(re.search(r'\\title\{([^}]+)\}',source).group(1).split())
assert title=='Adaptive Reading Budgets for Joint Forecast Audits with Cumulative Data'
data['title']=title
assert r'\label{thm:two-target-collapse}' in source
assert r'\label{prop:assurance-feasibility}' in source
abstract = source.split(r'\begin{abstract}', 1)[1].split(r'\end{abstract}', 1)[0]
abstract = re.sub(r'\\textbf\{([^}]+)\}', r'\1', abstract)
abstract = abstract.replace(r'\geq', '>=').replace(r'\leq', '<=').replace(r'\%', '%').replace('$', '')
abstract = '\n\n'.join(' '.join(p.split()) for p in abstract.strip().split('\n\n'))
assert '\\' not in abstract
assert '1/m' in abstract and 'two exact scalar readings' in abstract
assert 'compact convex' in abstract
data['abstract'] = abstract
keywords = re.search(r'\\noindent\\textbf\{Keywords:\}\s*(.*?)\n\s*\n', source, re.S).group(1)
data['keywords'] = [' '.join(term.split()).rstrip('.') for term in keywords.split(';')]
assert 'artificial intelligence' in data['keywords'] and 'machine learning' in data['keywords']
assert all('\\' not in term for term in data['keywords'])
data['release_tag'] = 'peerj-cs-2026-10-16-retrieval-gate'
data['release_focus'] = 'Shared-query mechanisms, loss-scale floors, certified threshold stability, matched-cohort capacity diagnostics, exact batch-precision completion for all 1,098 instances, decision-tolerance evaluation of unchanged policies, and a supplementary safe retrieval gate with warm, cold and archive-aware access accounting.'
delivery = json.loads((OUT / 'risk_delivery_verification.json').read_text())
assert delivery['status']=='PASS' and delivery['release_tag']==data['release_tag']
assert delivery['manuscript_title']==title
assert delivery['replay_steps']==7+len(json.loads((ROOT/'work/risk_adaptivity_revision/replay_jobs.json').read_text()))
assert delivery['manuscript_sha256']==hashlib.sha256((OUT / 'revised_manuscript.tex').read_bytes()).hexdigest()
assert delivery['pdf_sha256']==hashlib.sha256((OUT / 'revised_manuscript.pdf').read_bytes()).hexdigest()
assert delivery['abstract_words']==len(abstract.split())
assert delivery['verification_mode'] in {'fresh_full_replay','full_replay_plus_verified_editorial_delta'}
assert isinstance(delivery['execution_description'],str) and delivery['execution_description'].strip()
data['verification_mode']=delivery['verification_mode']
data['execution_description']=delivery['execution_description']

# Run only after the current delivery verification has passed; pin the application
# evidence rather than copying stale prose or extrapolating from a timing.
gate_dir=ROOT/'work/risk_adaptivity_revision/practical_retrieval_gate'
gate_report_path=gate_dir/'results/report.json'
gate_check_path=gate_dir/'results/independent_check.json'
gate=json.loads(gate_report_path.read_text())
gate_check=json.loads(gate_check_path.read_text())
assert gate['status']==gate_check['status']=='PASS'
assert gate['input_sha256']==hashlib.sha256((gate_dir/'inputs/public_decision_inputs_coherent.json').read_bytes()).hexdigest()
assert gate['source_sha256']==hashlib.sha256((gate_dir/'analyze.py').read_bytes()).hexdigest()
assert gate_check['source_sha256']==hashlib.sha256((gate_dir/'check_saved.py').read_bytes()).hexdigest()
assert gate_check['analyzed_report_sha256']==hashlib.sha256(gate_report_path.read_bytes()).hexdigest()
assert gate_check['input_sha256']==gate['input_sha256']
assert gate_check['exact_gates_checked']==gate['blocks']==1098
assert gate_check['direct_vertex_loss_checks']==gate['exact_vertex_mse_checks']==39528
assert gate['epsilon_training_m2_factor']=='1/100'
gate_cohorts=gate['cohorts']
assert [(gate_cohorts[c]['zero_query_certificates'],gate_cohorts[c]['blocks']) for c in ['original','external']]==[(8,819),(198,279)]
assert r'\label{sec:retrieval-gate}' in (gate_dir/'manuscript_fragment.tex').read_text()
data['practical_retrieval_gate_summary']={
    'location':'Supplementary methods S16; not a primary novelty claim',
    'contract':'Return an epsilon-optimal fixed candidate for every completion; epsilon is 0.01 of the training second moment. This differs from joint half-width precision.',
    'immediate_with_retained_endpoints':{
        c:{'blocks':v['blocks'],'avoided_block_fetches':v['zero_query_certificates'],
           'bulk_requests':v['immediate']['always_bulk_warm']['requests'],
           'gated_requests':v['immediate']['gated_warm']['requests']}
        for c,v in gate_cohorts.items()},
    'archive_with_retained_endpoints':{
        c:{'remaining_blocks':v['retrospective']['archive_after_gate_remaining_blocks'],
           'minimum_request_fine_plan':v['retrospective']['archive_first_fine_frontier'][0]}
        for c,v in gate_cohorts.items()},
    'scope':'Exploratory access-schedule replay with one shared fetch for all four models. The warm saving is against unconditional per-block bulk. Cold request-oriented access selects direct bulk; whole-period access uses permitted archive records and range batching. No monetary saving, general cost dominance, or population latency advantage is claimed.',
    'source_artifact_sha256':{
        p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [gate_report_path,gate_check_path,gate_dir/'analyze.py',gate_dir/'check_saved.py',gate_dir/'inputs/public_decision_inputs_coherent.json']}}

data['empirical_review_summary']=delivery['empirical_review_revision']
data['precision_completion_summary']=delivery['precision_completion']
data['decision_tolerance_summary']=delivery['decision_tolerance']
assert data['precision_completion_summary']['full_panel_exact_optima']==1098
assert data['decision_tolerance_summary']['cases']==1098
assert data['empirical_review_summary']['joint_only_blocks']==191
budget=delivery['budget_revision']
assert budget['status']=='PASS' and budget['fixed_three_vs_adaptive_two_cases']==225
data['budget_result_summary']={
    'fixed_three_vs_adaptive_two_blocks':225,
    'systems':6,'qualifying_reserved_readout_reduction':'1/3',
    'one_additional_feedback_round_per_qualifying_block':True,
    'full_panel_fixed_to_adaptive_with_fixed_fallback':{'original':[2625,2457],'external':[743,686]},
    'scope':budget['scope']}
for key, filename in [('manuscript_sha256', 'revised_manuscript.tex'),
                      ('pdf_sha256', 'revised_manuscript.pdf')]:
    data[key] = hashlib.sha256((OUT / filename).read_bytes()).hexdigest()
path.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'status': 'PASS', 'source': data['manuscript_sha256'],
                  'prepared_abstract_words': len(abstract.split()),
                  'submission_status': data['status']}))
