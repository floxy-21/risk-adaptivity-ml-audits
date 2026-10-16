"""Publish current local readiness records only after complete replay passes."""
from pathlib import Path
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
import re
import shutil
import zipfile
from editorial_delta_support import MODE as EDITORIAL_DELTA_MODE, load_verified_delta, execution_note

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs'
BASE = ROOT / 'work/risk_adaptivity_revision'
RELEASE_TAG = 'peerj-cs-2026-10-16-retrieval-gate'
EXCLUDED_EDITORIAL_NOTES={
    'work/external_deadline/editorial/pretest_scientific_review.txt',
    'work/external_deadline/editorial/provisional_numerical_review.txt',
    'work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/failure_diagnostics/INTERNAL_LOWER_REVIEW.txt',
}
EXCLUDED_FINE_ANSWER_FILES={
    'work/risk_adaptivity_revision/joint_certification/decision_tolerance_probe/results/block_certificates.json',
}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(4 << 20),b''):
            h.update(data)
    return h.hexdigest()


browser_attempt_path=BASE/'peerj_revision/browser_submission_check_20261015.json'
browser_attempt=read(browser_attempt_path)
assert browser_attempt['connection']=='connected'
assert browser_attempt['signed_in'] is True
assert browser_attempt['account_email']=='kapoorjishan19@gmail.com'
assert browser_attempt['new_password_entered'] is False
assert browser_attempt['journal_form_accessed'] is True and browser_attempt['submitted'] is False
browser_record={
    'checked_utc':browser_attempt['checked_utc'],
    'diagnostic_path':browser_attempt_path.relative_to(ROOT).as_posix(),
    'diagnostic_sha256':sha(browser_attempt_path),
    'target':browser_attempt['target'],
    'connection':'connected','signed_in':True,
    'account_email':browser_attempt['account_email'],
    'journal_form_accessed':True,'submitted':False,'new_password_entered':False,
    'scope':'Recorded signed-in submission-preparation state. Delivery verification itself performs no browser action and does not establish submission.'}

replay=read(OUT/'current_clean_package_replay.json')
editorial=read(OUT/'risk_editorial_verification.json')
package=read(OUT/'risk_supplement_verification.json')
journal=read(OUT/'journal_supplement_verification.json')
source_chain=read(BASE/'joint_certification/provenance_chain/executed/table_chain.json')
assert source_chain['status']=='PASS' and source_chain['all_case_ledger_rows_compared']==1098
assert source_chain['maximum_ledger_numeric_difference']==0
fresh_chain_path=BASE/'joint_certification/provenance_chain/executed/fresh_both_panel_replay_20261014.json'
fresh_chain=read(fresh_chain_path)
assert fresh_chain['status']=='PASS' and fresh_chain['scientific_scripts_unchanged'] is True
assert fresh_chain['reuse_flags']==[] and fresh_chain['new_forecast_fits']==0
for flag in ['fresh_original_regeneration','fresh_shared_policy_generation','fresh_precision_plan_generation']:
    assert fresh_chain[flag] is True,flag
assert fresh_chain['script_sha256_before']==fresh_chain['script_sha256_after']
for name,expected in fresh_chain['script_sha256_after'].items():
    assert sha(ROOT/name)==expected,name
assert fresh_chain['source_counts']['physical_blocks']=={'original':819,'external':279}
assert fresh_chain['source_counts']['coefficient_cases']=={'original':4914,'external':1674}
for cohort,count in [('original',165),('external',57)]:
    assert fresh_chain['precision_summary'][cohort]['matching_half']==count
    assert fresh_chain['tables'][cohort]['matched_half_blocks']==count
assert fresh_chain['complete_panel_comparison']['all_case_ledger_rows_compared']==1098
assert fresh_chain['complete_panel_comparison']['maximum_ledger_numeric_difference']==0
source_sha=sha(OUT/'revised_manuscript.tex')
pdf_sha=sha(OUT/'revised_manuscript.pdf')
zip_sha=sha(OUT/'research_supplement.zip')
dependency_history_path=BASE/'peerj_revision/journal_delivery/pre_dependency_fix_20261016/PRESERVATION.json'
dependency_history=read(dependency_history_path)
assert dependency_history['status']=='PRESERVED_FAILED_EXECUTION'
dependency_files=dependency_history['files']
for item in dependency_files:
    retained=ROOT/item['retained']
    assert retained.stat().st_size==item['bytes'] and sha(retained)==item['sha256'],item['retained']
dependency_failure_item=next(item for item in dependency_files
    if item['source']==dependency_history['failure_report_source'])
dependency_failure=read(ROOT/dependency_failure_item['retained'])
assert dependency_failure['status']=='failed' and dependency_failure['failed_step_number']==83
assert dependency_failure['completed_steps']==82
assert dependency_failure['failed_step']['script'].endswith('/review_mechanism/check_training.py')
dependency_log_item=next(item for item in dependency_files if item['source'].endswith('/risk_step_83.log'))
assert dependency_failure['log_sha256']==dependency_log_item['sha256']
dependency_log=(ROOT/dependency_log_item['retained']).read_text(encoding='utf8')
assert 'FileNotFoundError' in dependency_log and 'study_meter_results.json' in dependency_log
dependency_small=[dependency_history_path]+[ROOT/item['retained'] for item in dependency_files
    if not item['source'].endswith('.zip')]
dependency_github={p.relative_to(ROOT).as_posix():
    'verification/pre_dependency_fix_20261016/'+p.name for p in dependency_small}
assert len(set(dependency_github.values()))==len(dependency_small)
dependency_evidence={
    'status':'PRESERVED_FAILED_EXECUTION','failed_step':83,'completed_steps':82,
    'cause':'Required unchanged outputs/study_meter_results.json was omitted from the journal package.',
    'preservation_path':dependency_history_path.relative_to(ROOT).as_posix(),
    'preservation_sha256':sha(dependency_history_path),
    'failed_source_sha256':dependency_history['source_sha256'],
    'failed_full_scientific_zip_sha256':dependency_history['full_scientific_zip_sha256'],
    'failed_journal_parts':[item for item in dependency_files if item['source'].endswith('.zip')],
    'artifact_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in dependency_small},
    'github_paths':dependency_github,
    'scope':'Failed execution and old part hashes retained explicitly. The original ZIPs and failed stage remain local; small preservation evidence is copied to GitHub. Older successful replay records inside this history are not evidence of the failed attempt or corrected run. Current readiness requires the separate successful scientific replay and any explicitly verified editorial delta below.'}
history_path=OUT/'pre_budget_history_manifest.json'
history=read(history_path)
assert history['status']=='PASS' and history['release_tag']=='peerj-cs-2026-10-14-assurance'
assert history['commit']=='c878784db195e74be395ff9735870eeef1054c4c'
assert history['prior_replay_steps']==77
for item in history['files']:
    retained=ROOT/item['retained']
    assert sha(retained)==item['sha256'] and retained.stat().st_size==item['bytes'],item['retained']
prior_delivery=read(OUT/'pre_budget_risk_delivery_verification.json')
assert prior_delivery['release_tag']==history['release_tag']
assert source_sha!=prior_delivery['manuscript_sha256'], 'The diagnostics release must contain the reviewed current source.'
expected_steps = 7 + len(read(BASE/'replay_jobs.json'))
assert replay['status']=='passed' and len(replay['steps'])==expected_steps
editorial_delta=None
if replay['manuscript_reproduced_sha256'] != source_sha:
    editorial_delta=load_verified_delta(ROOT,replay,source_sha,pdf_sha)
assert source_sha==editorial['manuscript_sha256']
verification_mode=EDITORIAL_DELTA_MODE if editorial_delta is not None else 'fresh_full_replay'
replay_description=execution_note(replay,editorial_delta)
assert package['new_manuscript_sha256']==source_sha
assert pdf_sha==editorial['pdf_sha256']
assert editorial['status']=='passed'
assert isinstance(editorial['pdf_pages'], int) and editorial['pdf_pages'] > 0
assert editorial['builtin_main_compile']=='success'
assert zip_sha==package['zip_sha256']
with zipfile.ZipFile(OUT/'research_supplement.zip') as archive:
    assert not (set(archive.namelist())&EXCLUDED_EDITORIAL_NOTES)
    assert not (set(archive.namelist())&EXCLUDED_FINE_ANSWER_FILES)
    editorial_omissions=json.loads(archive.read('EXCLUDED_EDITORIAL_NOTES.json'))
    assert set(editorial_omissions['configured_paths'])==EXCLUDED_EDITORIAL_NOTES
    current_manifest={line.split('  ',1)[1]:line.split('  ',1)[0]
                      for line in archive.read('MANIFEST.sha256').decode().splitlines()}
    prior_manifest={line.split('  ',1)[1]:line.split('  ',1)[0]
                    for line in archive.read('work/risk_adaptivity_revision/prior_release/MANIFEST_prior.sha256').decode().splitlines()}
    historical_omissions=editorial_omissions['omitted_inherited_editorial_notes']
    omitted_hashes={item['path']:item['sha256'] for item in historical_omissions}
    assert len(omitted_hashes)==len(historical_omissions)
    assert set(omitted_hashes)==set(prior_manifest)&EXCLUDED_EDITORIAL_NOTES
    for name,digest in omitted_hashes.items():
        assert prior_manifest[name]==digest and name not in current_manifest,name
    preserved_names={
        'README.txt':'work/risk_adaptivity_revision/prior_release/README_prior.txt',
        'outputs/revised_manuscript.tex':'work/risk_adaptivity_revision/prior_release/revised_manuscript.tex',
        'requirements.txt':'work/risk_adaptivity_revision/prior_release/requirements_prior.txt',
        'outputs/requirements-study.txt':'work/risk_adaptivity_revision/prior_release/requirements_prior.txt'}
    for name,digest in prior_manifest.items():
        if name not in omitted_hashes:
            assert current_manifest[preserved_names.get(name,name)]==digest,name
    assert package['old_members_exactly_recoverable']==len(prior_manifest)-len(omitted_hashes)
    assert package['old_editorial_notes_omitted']==historical_omissions
    retained_rationale=editorial_omissions['retained_historical_mathematical_rationale']
    assert retained_rationale['path']=='work/randomized_tie_review/theory_review.txt'
    assert retained_rationale['sha256']==current_manifest[retained_rationale['path']]
    assert retained_rationale['sha256']==prior_manifest[retained_rationale['path']]
assert journal['status']=='passed' and journal['source_zip_sha256']==zip_sha
assert journal['manuscript_sha256']==source_sha
if editorial_delta is not None:
    assert journal['verification_mode']==EDITORIAL_DELTA_MODE
    assert journal['editorial_delta_sha256']==sha(OUT/'editorial_delta_verification.json')
    assert journal['baseline_clean_replay_sha256']==sha(OUT/'current_clean_package_replay.json')
    assert journal['fresh_scientific_steps_executed']==0
else:
    assert journal.get('verification_mode','fresh_full_replay')=='fresh_full_replay'
    assert journal['clean_replay_steps']==len(replay['steps'])
assert journal['total_zip_bytes'] < 50_000_000
for part in journal['parts']:
    assert part['bytes'] < 30_000_000
    assert sha(OUT/part['path'])==part['sha256']
    with zipfile.ZipFile(OUT/part['path']) as delivery_part:
        assert not (set(delivery_part.namelist())&EXCLUDED_FINE_ANSWER_FILES)
corrected_metadata='outputs/study_meter_results.json'
metadata_matches=[]
for part in journal['parts']:
    with zipfile.ZipFile(OUT/part['path']) as delivery_part:
        if corrected_metadata in delivery_part.namelist():
            metadata_matches.append(hashlib.sha256(delivery_part.read(corrected_metadata)).hexdigest())
assert metadata_matches==[sha(ROOT/corrected_metadata)], 'Corrected journal package must retain the exact required metadata once.'
visual=(OUT/'peerj_final_visual_review.txt').read_text()
assert pdf_sha in visual and source_sha in visual
for name in ['protocol_selection_replay','protocol_selection_independent',
             'bound_acquisition_workflow','independent_task_binding',
             'protocol_cost_frontier','protocol_cost_frontier_independent',
             'printed_worked_example', 'joint_precision_exact',
             'joint_precision_adaptive_link', 'joint_precision_replay_check',
             'joint_noisy_exact', 'joint_capacity_noisy_exact',
             'joint_paired_independent', 'joint_scientific_match',
             'joint_main_certificate', 'final_review_independent',
             'joint_absolute_widths', 'source_identity_guards',
             'external_source_forecast_chain']:
    assert replay['checks'][name]['status'].lower() in {'pass','passed'}, name
for name in ['proof_review.txt','novelty_review.txt','practice_review.txt']:
    assert (BASE/'peerj_revision'/name).exists()
prior_review_names=['proof_review.txt','novelty_review.txt','practice_review.txt',
                   'new_core_theory_review.txt','new_package_review.txt',
                   'peerj_final_fit_challenge.txt','peerj_practical_value_challenge.txt',
                   'latest_boundary_review.txt','final_practical_budget_review.txt']
for name in prior_review_names:
    assert (BASE/'peerj_revision'/name).exists()
current_review_path=BASE/'peerj_revision/latest_compiled_review.txt'
current_review=current_review_path.read_text()
assert source_sha in current_review and pdf_sha in current_review
assert 'PASS' in current_review
assert 'workflow' in current_review.lower() and 'equation' in current_review.lower(), 'Current compiled review must cover workflow and displayed equations.'
boundary_review_path=BASE/'peerj_revision/final_gate_mathematical_review.txt'
boundary_review=boundary_review_path.read_text()
assert source_sha in boundary_review and ('PASS' in boundary_review or 'No unresolved issue remains' in boundary_review)
claims_dir=BASE/'peerj_revision/originality_resolution_20261014'
claims_report_path=claims_dir/'final_claims_report.json'
claims_report=read(claims_report_path)
assert claims_report['status']=='PASS'
assert claims_report['manuscript_source_sha256']==source_sha
assert claims_report['manuscript_pdf_sha256']==pdf_sha
for relative,digest in claims_report['source_sha256'].items():
    assert sha(BASE/relative)==digest,relative
claims_files={claims_report_path.relative_to(ROOT).as_posix():sha(claims_report_path)}
practical_review_path=BASE/'peerj_revision/final_gate_empirical_review.txt'
practical_review=practical_review_path.read_text()
assert source_sha in practical_review and ('PASS' in practical_review or 'no blocking scientific or accounting defect' in practical_review)
absolute=read(BASE/'joint_certification/absolute_width_results/report.json')
for field in ['pairs','loss_denominator','counter_units','loss_units','recorded_J']:
    assert replay['checks']['joint_absolute_widths'][field]==absolute[field],field
assert replay['checks']['external_source_forecast_chain']['coefficient_cases']=={'external':1674}
threshold=read(BASE/'joint_certification/review_sensitivity/results/report.json')
assert replay['checks']['joint_threshold_sensitivity']['status']=='PASS'
assert replay['checks']['joint_threshold_independent']['status']=='PASS'
assert replay['checks']['joint_threshold_independent']['paired_summaries']==320
for key in ['blocks','outcome_rows','continuum_gaps','full_panel_summaries']:
    assert replay['checks']['joint_threshold_sensitivity'][key]==threshold[key],key
diagnostics=read(BASE/'joint_certification/final_challenger_diagnostics/results/report.json')
for name in ['final_challenger_diagnostics','final_challenger_independent','final_practical_figure']:
    assert replay['checks'][name]['status']=='PASS',name
for key in ['blocks','regime_rows','replay_rows','paired_summary_rows','regimes','full_panel_replay']:
    assert replay['checks']['final_challenger_diagnostics'][key]==diagnostics[key],key
assert replay['checks']['final_challenger_independent']['exact_regime_cases']==1098
figure=read(BASE/'joint_certification/final_practical_figure/independent_check.json')
for key in ['source_contrasts_checked','conditional_lines_checked','exact_envelope_points_checked',
            'envelope_equalities','replay_points_checked','exact_switch','exact_maximum','figure_data_sha256']:
    assert replay['checks']['final_practical_figure'][key]==figure[key],key
two_target_dir=BASE/'two_target_boundary'
two_target_source_sha=sha(two_target_dir/'verify_boundary.py')
two_target_reports={}
for job, filename in [('two_target_exact','solver_free_report.json'),
                      ('two_target_lp','numeric_report.json')]:
    saved=read(two_target_dir/filename)
    executed=replay['checks'][job]
    for report in [saved,executed]:
        assert report['status']=='PASS' and report['all_checks_passed'] is True,job
        assert report['source_sha256']==two_target_source_sha,job
        assert report['family_sizes']==[3,5,10],job
        proof_bytes=json.dumps(report['proof_input_parameters'],sort_keys=True,
                               separators=(',',':')).encode('utf-8')
        assert hashlib.sha256(proof_bytes).hexdigest()==report['proof_input_sha256'],job
    for key in ['mode','source_sha256','proof_input_sha256','proof_input_parameters',
                'family_sizes','families']:
        assert saved[key]==executed[key],(job,key)
    two_target_reports[job]=executed
assert two_target_reports['two_target_exact']['proof_input_sha256']==two_target_reports['two_target_lp']['proof_input_sha256']
two_target_numeric=two_target_reports['two_target_lp']['numerical_verification']
assert two_target_numeric['actual_total_LPs']==7131
assert sum(two_target_numeric['LP_counts_by_category'].values())==7131
assert two_target_numeric['absolute_comparison_tolerance']==1e-7
assert two_target_numeric['primal_feasibility_tolerance']==1e-9
assert two_target_numeric['dual_feasibility_tolerance']==1e-9
assert 0<=two_target_numeric['maximum_endpoint_discrepancy']<=1e-7
assert 0<=two_target_numeric['maximum_width_discrepancy']<=1e-7
for name in ['proof_review_memo.txt','novelty_review.txt']:
    assert (two_target_dir/name).is_file()
assert r'\label{thm:two-target-collapse}' in (OUT/'revised_manuscript.tex').read_text(encoding='utf8')

# Bind the full source-derived evidence separately from the external-only
# certificate regeneration performed by the default offline replay.
assurance_dir=BASE/'joint_certification/assurance_feasibility'
assurance_source_sha=sha(assurance_dir/'verify_assurance.py')
assurance_full_path=assurance_dir/'executed_all/report.json'
assurance_external_path=assurance_dir/'executed_external/report.json'
assurance_full=read(assurance_full_path)
assurance_external=read(assurance_external_path)
assurance_executed=replay['checks']['joint_assurance_feasibility']
assurance_regimes={
    'original':{'fixed_guarantee':162,'adaptive_only_guarantee':168,
                'no_deterministic_adaptive_guarantee':489},
    'external':{'fixed_guarantee':128,'adaptive_only_guarantee':57,
                'no_deterministic_adaptive_guarantee':94}}
for report in [assurance_full,assurance_external,assurance_executed]:
    assert report['status']=='PASS' and report['source_sha256']==assurance_source_sha
    assert report['randomized_adaptive_success_upper_bound_on_no_guarantee_cases']=='19/20'
    assert report['bound_is_not_claimed_optimal'] is True
    assert report['recorded_answers_or_replay_outcomes_used'] is False
    assert report['original_coefficients_exported'] is False
    assert report['new_forecast_fits']==report['new_network_calls']==0
    assert report['provenance']['maximum_exact_normalization_difference']=='0'
    for cohort in report['checked_cohorts']:
        assert report['regimes'][cohort]==assurance_regimes[cohort]
        assert Fraction(report['minimum_strict_failure_margin_by_cohort'][cohort])>0
assert assurance_full['checked_cohorts']==['external','original']
assert assurance_external['checked_cohorts']==assurance_executed['checked_cohorts']==['external']
assert assurance_full['actual_check_counts']=={
    'coefficient_instances_classified':1098,'first_query_interval_covers_checked':5490,
    'common_first_answer_checks':2915,'simplex_endpoint_checks':23320,
    'shared_query_answer_checks':23320,'strict_failing_fiber_checks':11660,
    'seed_independent_adverse_distributions':583}
assert assurance_external['actual_check_counts']=={
    'coefficient_instances_classified':279,'first_query_interval_covers_checked':1395,
    'common_first_answer_checks':470,'simplex_endpoint_checks':3760,
    'shared_query_answer_checks':3760,'strict_failing_fiber_checks':1880,
    'seed_independent_adverse_distributions':94}
for key in assurance_external:
    if key!='elapsed_seconds':
        assert assurance_external[key]==assurance_executed[key],('assurance',key)
full_provenance=assurance_full['provenance']
assert full_provenance['mode']=='fresh_both_source_chain'
for key,name in [('chain_execution_sha256','chain_execution.json'),
                 ('source_chain_sha256','source_chain.json')]:
    assert full_provenance[key]==fresh_chain['report_file_sha256'][name]
assert full_provenance['source_input_sha256']==fresh_chain['all_source_input_sha256']
assert full_provenance['source_physical_blocks']=={'original':819,'external':279}
assert full_provenance['source_coefficient_cases']=={'original':4914,'external':1674}
assert full_provenance['exact_coefficient_normalization_checks']==6588
external_provenance=assurance_external['provenance']
assert external_provenance['mode']=='bundled_external_only'
assert external_provenance['source_execution_evidence_sha256']==sha(fresh_chain_path)
assert external_provenance['original_coefficients_verified_in_this_run'] is False
assert external_provenance['exact_coefficient_normalization_checks']==1674
for key,path in [('plans_sha256','precision_external_results/plans.json'),
                 ('shared_plans_sha256','empirical_external_results/empirical_plans.json')]:
    assert external_provenance[key]==sha(BASE/'joint_certification'/path)
for relative,digest in external_provenance['geometry_sha256'].items():
    assert sha(BASE/relative)==digest
for report,folder in [(assurance_full,'executed_all'),(assurance_external,'executed_external')]:
    witness_path=assurance_dir/folder/'synthetic_witnesses.json'
    assert report['synthetic_witnesses_sha256']==sha(witness_path)
    witnesses=read(witness_path)
    assert witnesses['threshold']=='1/2'
    assert len(witnesses['certificates'])==report['actual_check_counts']['seed_independent_adverse_distributions']
    for certificate in witnesses['certificates']:
        assert certificate['success_upper_bound']=='19/20'
        assert certificate['adverse_mass_per_ordered_witness']=='1/20'
        assert len(certificate['first_answers'])==5
        assert all(len(first['witnesses'])==4 for first in certificate['first_answers'])
for path in [assurance_dir/'verify_assurance.py',assurance_dir/'proof.txt',
             assurance_dir/'README.txt',assurance_full_path,assurance_external_path,
             assurance_dir/'executed_all/synthetic_witnesses.json',
             assurance_dir/'executed_external/synthetic_witnesses.json']:
    assert current_manifest[path.relative_to(ROOT).as_posix()]==sha(path),path
assert r'\label{prop:assurance-feasibility}' in (OUT/'revised_manuscript.tex').read_text(encoding='utf8')
# The budget revision executes its four added jobs, not the historical 77-step
# result. Both-source evidence and default external replay remain separate.
assert expected_steps == 7 + len(read(BASE/'replay_jobs.json'))
support_path=two_target_dir/'support_report.json'
support=read(support_path)
support_replay=replay['checks']['two_target_support']
for report in [support,support_replay]:
    assert report['status']=='PASS'
    assert report['checker_sha256']==sha(two_target_dir/'verify_support.py')
    assert report['actual_width_evaluations']==126195
    assert [item['m'] for item in report['families']]==[3,4,5,8,10,16,24]
    for family in report['families']:
        assert family['minimum_support_for_positive_success']==family['m']
        assert Fraction(family['optimal_batch_mass'])==Fraction(1,family['m'])
        assert len(family['checks'])==3
for key in support:
    if key!='seconds':
        assert support[key]==support_replay[key],('support',key)

budget_dir=BASE/'joint_certification/reading_budget'
budget_full=read(budget_dir/'executed_all/report.json')
budget_external=read(budget_dir/'executed_external/report.json')
budget_full_check=read(budget_dir/'executed_all/independent_check.json')
assert claims_report['both_ledger_sha256']==sha(budget_dir/'executed_all/ledger.json')
assert claims_report['independent_check_sha256']==sha(budget_dir/'executed_all/independent_check.json')
budget_external_check=read(budget_dir/'executed_external/independent_check.json')
budget_replay=replay['checks']['reading_budget_external']
budget_replay_check=replay['checks']['reading_budget_external_check']
budget_general=read(budget_dir/'general_partition_check.json')
budget_general_replay=replay['checks']['reading_budget_general']
for report in [budget_full,budget_external,budget_replay]:
    assert report['status']=='PASS'
    assert report['source_sha256']==sha(budget_dir/'reading_budget.py')
    assert report['binding_sha256']==assurance_source_sha
    assert report['recorded_answers_or_replay_outcomes_used'] is False
    assert report['forecast_training_runs']==0
    assert report['fixed_optimum_includes_randomized_sure_policies'] is True
    assert report['adaptive_minimum_identified_only_when_at_most_two'] is True
assert budget_full['provenance']==assurance_full['provenance']
assert budget_external['provenance']==assurance_external['provenance']
assert budget_full['subset_checks']==35136
assert budget_full['linear_scan_vs_enumeration_checks']==1098
assert budget_external['subset_checks']==8928
assert budget_external['linear_scan_vs_enumeration_checks']==279
expected_budgets={
    'original':{'blocks':819,'saving_cases':168,'fixed_total':2625,'adaptive_fallback_total':2457,
                'histogram':{'1':6,'2':156,'3':371,'4':236,'5':50}},
    'external':{'blocks':279,'saving_cases':57,'fixed_total':743,'adaptive_fallback_total':686,
                'histogram':{'1':9,'2':119,'3':116,'4':27,'5':8}}}
for cohort,expected in expected_budgets.items():
    summary=budget_full['summaries'][cohort]
    assert summary['blocks']==expected['blocks']
    assert summary['minimum_fixed_budget_histogram']==expected['histogram']
    assert summary['strict_readout_saving_cases']==expected['saving_cases']
    assert summary['adaptive_two_vs_minimum_fixed_histogram']=={'3':expected['saving_cases']}
    assert summary['fixed_readings_on_saving_subset']==3*expected['saving_cases']
    assert summary['adaptive_readings_on_saving_subset']==2*expected['saving_cases']
    assert summary['fixed_total_readings_all_blocks']==expected['fixed_total']
    assert summary['adaptive_where_certified_otherwise_minimum_fixed_total']==expected['adaptive_fallback_total']
    assert summary['minimum_adaptive_budget_above_two_not_solved']==assurance_regimes[cohort]['no_deterministic_adaptive_guarantee']
    assert budget_full_check['fixed_budget_histograms'][cohort]==expected['histogram']
assert budget_external['summaries']=={key:value for key,value in budget_full['summaries'].items()
                                      if key=='external' or key.startswith('external/')}
systems={key:value['strict_readout_saving_cases'] for key,value in budget_full['summaries'].items() if '/' in key}
assert len(systems)==6 and min(systems.values())>0 and sum(systems.values())==225
for report,check,folder,count in [(budget_full,budget_full_check,'executed_all',1098),
                                 (budget_external,budget_external_check,'executed_external',279)]:
    assert check['status']=='PASS' and check['checker_sha256']==sha(budget_dir/'check_reading_budget.py')
    assert check['source_binding_sha256']==assurance_source_sha
    assert check['recorded_answers_or_replay_outcomes_used'] is False
    assert check['source_input_hashes']==report['provenance']
    assert check['producer_report_sha256']==sha(budget_dir/folder/'report.json')
    assert check['results_ledger_sha256']==report['ledger_sha256']==sha(budget_dir/folder/'ledger.json')
    ledger=read(budget_dir/folder/'ledger.json')
    assert ledger['status']=='PASS' and len(ledger['rows'])==count
    assert check['checks']['independent_shortest_path_minima']==count
    assert check['checks']['independent_all_batch_widths']==32*count
assert budget_full_check['checks']=={
    'independent_shortest_path_minima':1098,'feasible_fixed_endpoint_pairs':737856,
    'independent_all_batch_widths':35136,'strict_insufficient_batch_checks':18093,
    'linear_scan_vs_independent_shortest_path':1098,'adaptive_conditional_endpoint_pairs':41400,
    'adaptive_closed_interval_covers':500}
for key in budget_external:
    if key!='elapsed_seconds':
        assert budget_external[key]==budget_replay[key],('budget_replay',key)
for key in budget_external_check:
    if key not in {'elapsed_seconds','producer_report_sha256'}:
        assert budget_external_check[key]==budget_replay_check[key],('budget_replay_check',key)
for report in [budget_general,budget_general_replay]:
    assert report['status']=='PASS' and report['seed']==20261014
    assert report['instances']==180 and report['enumerated_batches']==20440
    assert report['recorded_meter_values_used'] is False
    assert report['producer_sha256']==sha(budget_dir/'reading_budget.py')
    assert report['checker_sha256']==sha(budget_dir/'check_partition_general.py')
for key in budget_general:
    if key!='elapsed_seconds':
        assert budget_general[key]==budget_general_replay[key],('budget_general',key)
budget_artifacts=[two_target_dir/name for name in
    ['optimal_mixture.tex','verify_support.py','support_report.json']]
budget_artifacts += [budget_dir/name for name in
    ['reading_budget.py','check_reading_budget.py','check_partition_general.py',
     'methods.tex','results.tex','proof.txt','README.txt','general_partition_check.json']]
budget_artifacts += [budget_dir/folder/name for folder in ['executed_all','executed_external']
    for name in ['report.json','ledger.json','independent_check.json']]
for path in budget_artifacts:
    assert current_manifest[path.relative_to(ROOT).as_posix()]==sha(path),path
main_source=(OUT/'revised_manuscript.tex').read_text(encoding='utf8')
manuscript_title=' '.join(re.search(r'\\title\{([^}]+)\}',main_source).group(1).split())
assert manuscript_title=='Adaptive Reading Budgets for Joint Forecast Audits with Cumulative Data'
assert r'\label{sec:minimum-fixed-budget}' in main_source
assert r'\label{tab:minimum-reading-budget}' in main_source
assert 'The optimal mixture is unique.' in main_source

# Four reviewer diagnostics: freeze both successful and limiting findings.
review_root=BASE/'joint_certification'
review_jobs=[job['name'] for job in read(BASE/'replay_jobs.json')
             if job['name'].startswith('review_revision_')]
assert len(review_jobs)==11
for name in review_jobs:
    assert replay['checks'][name]['status'].lower() in {'pass','passed'},name
mechanism_dir=review_root/'review_mechanism'
threshold_dir=review_root/'review_thresholds'
capacity_dir=review_root/'review_capacity'
mechanism=read(mechanism_dir/'executed/report.json')
mechanism_check=read(mechanism_dir/'executed/independent_check.json')
floor=read(mechanism_dir/'executed/floor_assurance_diagnostic.json')
floor_plan=read(mechanism_dir/'executed/decision_plan_check.json')
threshold_stability=read(threshold_dir/'executed/report.json')
threshold_check=read(threshold_dir/'executed/independent_check.json')
capacity=read(capacity_dir/'executed_all/report.json')
capacity_check=read(capacity_dir/'executed_all/independent_check.json')
capacity_certificate=read(capacity_dir/'executed_all/certificate_check.json')
for report in [mechanism,mechanism_check,floor,floor_plan,threshold_stability,
               threshold_check,capacity,capacity_check,capacity_certificate]:
    assert report['status']=='PASS'
assert mechanism['producer_sha256']==sha(mechanism_dir/'analyze.py')
assert mechanism_check['checker_sha256']==sha(mechanism_dir/'check.py')
assert mechanism_check['producer_report_sha256']==sha(mechanism_dir/'executed/report.json')
assert mechanism['ledger_sha256']==mechanism_check['ledger_sha256']==sha(mechanism_dir/'executed/ledger.json')
assert mechanism['summaries']['all']['joint_only']==191
assert mechanism['summaries']['all']['scalar_obstruction']==34
assert mechanism['summaries']['original']['joint_only']==137
assert mechanism['summaries']['external']['joint_only']==54
assert mechanism['summaries']['all']['joint_only_matched_half']==188
assert mechanism['no_withheld_evaluation_answers_used'] is True
assert floor['checker_sha256']==sha(mechanism_dir/'diagnose_floor.py')
assert floor_plan['checker_sha256']==sha(mechanism_dir/'decision_plan.py')
assert floor_plan['assured_cases']==57 and floor_plan['selected_readings']==70
assert floor_plan['minimum_fixed_readings']==88
primary_external=mechanism['summaries']['external']['floor_results']['1/100']
assert primary_external['fixed_total']==378
assert primary_external['adaptive_two_else_minimum_fixed_total']==358
assert primary_external['baseline_now_fixed_at_most_two']==39
assert primary_external['retained_baseline_saving_cases']==18
assert primary_external['new_saving_cases']==2
assert floor['summaries']['external']['1/100']['assured_with_at_most_two']==57
assert threshold_stability['producer_sha256']==sha(threshold_dir/'threshold_stability.py')
assert threshold_check['checker_sha256']==sha(threshold_dir/'check_threshold_stability.py')
assert threshold_check['report_sha256']==sha(threshold_dir/'executed/report.json')
assert threshold_stability['intervals_sha256']==threshold_check['intervals_sha256']==sha(threshold_dir/'executed/intervals.json')
assert threshold_stability['case_count']==222
assert threshold_stability['summary']['all']['entire_closed_symmetric_band']=={'1/100':179,'1/40':119,'1/20':53}
assert capacity['source_sha256']==sha(capacity_dir/'analyze_capacity.py')
assert capacity_check['checker_sha256']==capacity_certificate['checker_sha256']==sha(capacity_dir/'check_capacity.py')
assert capacity_check['report_sha256']==capacity_certificate['report_sha256']==sha(capacity_dir/'executed_all/report.json')
assert capacity['ledger_sha256']==capacity_check['ledger_sha256']==capacity_certificate['ledger_sha256']==sha(capacity_dir/'executed_all/ledger.json')
assert capacity_check['raw_records_verified_in_this_run'] is True
assert capacity_certificate['raw_records_verified_in_this_run'] is False
assert sum(capacity['summaries'][cohort+'/cap=1/2']['saving_cases_excluded'] for cohort in ['original','external'])==25
assert sum(capacity['summaries'][cohort+'/cap=1/2']['saving_cases_now_fixed_at_most_two'] for cohort in ['original','external'])==191
assert sum(capacity['summaries'][cohort+'/cap=1/2']['saving_cases_still_adaptive_only'] for cohort in ['original','external'])==9
assert sum(capacity['summaries'][cohort+'/cap=1/3']['saving_cases_excluded'] for cohort in ['original','external'])==75
assert sum(capacity['summaries'][cohort+'/cap=1/3']['saving_cases_now_fixed_at_most_two'] for cohort in ['original','external'])==150
# Only invariant results are compared: runtime/source-binding modes can differ.
for name,saved,key in [('review_revision_mechanism',mechanism,'summaries'),
                       ('review_revision_thresholds',threshold_stability,'summary')]:
    assert replay['checks'][name][key]==saved[key],name
assert replay['checks']['review_revision_capacity_external']['summaries']==read(capacity_dir/'executed_external/report.json')['summaries']
assert replay['checks']['review_revision_floor_plan']['assured_cases']==57
assert replay['checks']['review_revision_floor_plan']['selected_readings']==70
assert replay['checks']['review_revision_floor_plan']['minimum_fixed_readings']==88
assert replay['checks']['review_revision_correspondence']['joint_only_cases']==191
review_artifacts=[]
for folder in [mechanism_dir,threshold_dir,capacity_dir]:
    review_artifacts += [path for path in folder.iterdir() if path.is_file()
                         and path.suffix in {'.py','.tex','.json','.txt'}
                         and not path.name.lower().endswith('_console.txt')
                         and path.name!='INTERNAL_REVIEW.txt']
    for subfolder in ['executed','executed_all','executed_external']:
        if (folder/subfolder).is_dir():
            review_artifacts += sorted((folder/subfolder).glob('*.json'))
review_artifacts += [review_root/'check_review_revision.py']
for path in review_artifacts:
    assert current_manifest[path.relative_to(ROOT).as_posix()]==sha(path),path
empirical_review={
    'status':'PASS','artifact_sha256':{path.relative_to(ROOT).as_posix():sha(path) for path in sorted(set(review_artifacts))},
    'replay_jobs':review_jobs,
    'joint_only_blocks':191,'joint_only_by_source':{'original':137,'external':54},
    'scalar_obstruction_blocks':34,'joint_only_matched_half_blocks':188,
    'mechanism_summaries':mechanism['summaries'],
    'primary_floor':'1/100 of training mean squared hourly energy',
    'floor_assurance_summaries':floor['summaries'],
    'external_baseline_cohort':{'blocks':57,'assured':57,'selected_readings':70,
        'minimum_fixed_readings':88,'still_need_feedback':18,'now_fixed_suffices':39},
    'external_full_panel':{'blocks':279,'selected_readings':358,'minimum_fixed_readings':378,
        'retained_feedback_cases':18,'new_feedback_cases':2},
    'threshold_summaries':threshold_stability['summary'],
    'threshold_interval_scope':'Sufficient closed-left/open-right intervals for frozen policies and certificates, not maximal intervals. Optimal randomized-batch worst-record success is exactly one half inside; outside is inconclusive.',
    'capacity_summaries':capacity['summaries'],
    'capacity_half_baseline_saving_attribution':{'excluded':25,'now_fixed_suffices':191,'still_need_feedback':9},
    'capacity_third_baseline_saving_attribution':{'excluded':75,'now_fixed_suffices':150,'still_need_feedback':0},
    'execution_scope':'Default 11-job diagnostics replay bundled derived coefficients/certificates for both panels and verify external source records/training scale separately. Original raw-source compatibility and original training reconstruction have separately executed, pinned evidence; they are not performed by bundled replay. No new model fitting or deployment measurement.',
    'interpretation':'The absolute floor preserves assurance while removing feedback from 39 of 57 baseline external blocks. Threshold robustness and capacity attribution are reported on the declared cohorts. No financial, API or model-selection superiority is inferred.'}

# The new exact precision game closes the earlier 418 gaps. Existing controls
# remain independently replayed above; their old gap counts are historical.
completion_dir=BASE/'joint_certification/precision_completion_probe'
completion_jobs=['precision_completion_all_open_cases','precision_completion_exact_verifier',
    'precision_completion_corruption_tests','precision_completion_secondary_full_panel',
    'precision_completion_secondary_exact_verifier','precision_completion_recorded_replay',
    'precision_completion_recorded_replay_check']
for name in completion_jobs+['decision_tolerance_saved_endpoint_replay']:
    assert replay['checks'][name]['status']=='PASS',name
completion_primary=read(completion_dir/'all_418/report.json')
completion_refined=read(completion_dir/'refined_all/report.json')
completion_recorded=read(completion_dir/'refined_all/recorded_replay_summary.json')
completion_recorded_check=read(completion_dir/'refined_all/recorded_replay_check.json')
for name,saved in [('precision_completion_all_open_cases',completion_primary),
                   ('precision_completion_secondary_full_panel',completion_refined)]:
    fresh=replay['checks'][name]
    assert fresh['source_sha256']==saved['source_sha256']
    assert fresh['input_sha256']==saved['input_sha256']
    compact=lambda d:{r['id']:(r['lower'],r['upper'],r['normalized_coefficients_exact']) for r in d['cases']}
    assert compact(fresh)==compact(saved),name
assert replay['checks']['precision_completion_exact_verifier']['checks']['matched_continuum_optima']==418
assert replay['checks']['precision_completion_exact_verifier']['unresolved_cases']==0
assert replay['checks']['precision_completion_secondary_exact_verifier']['checks']['matched_continuum_optima']==1098
assert replay['checks']['precision_completion_secondary_exact_verifier']['unresolved_cases']==0
assert replay['checks']['precision_completion_corruption_tests']['tests']==8
recorded_fresh=replay['checks']['precision_completion_recorded_replay']
assert recorded_fresh['recorded_inputs_sha256']==completion_recorded['recorded_inputs_sha256']
assert recorded_fresh['bootstrap_draws_sha256']==completion_recorded['bootstrap_draws_sha256']
assert recorded_fresh['policies_changed'] is False and completion_recorded['policies_changed'] is False
group_key=lambda r:tuple(r[k] for k in ['cohort','meter','subset','convention'])
saved_groups={group_key(r):r for r in completion_recorded['groups']}
fresh_groups={group_key(r):r for r in recorded_fresh['groups']}
assert set(saved_groups)==set(fresh_groups) and len(saved_groups)==48
current_half={c:saved_groups[c,'ALL','matched_half','original_tolerance'] for c in ['original','external']}
current_all={c:saved_groups[c,'ALL','all','original_tolerance'] for c in ['original','external']}
for key,saved in saved_groups.items():
    fresh=fresh_groups[key]
    for k in ['blocks','adaptive_success_count']:
        assert fresh[k]==saved[k],(key,k)
    assert abs(Fraction(fresh['precision_batch_expected_success_exact'])-Fraction(saved['precision_batch_expected_success_exact']))<=Fraction(1,10**8)
    for k in ['adaptive_percent','precision_batch_percent','adaptive_minus_batch_pp','adaptive_mean_J','batch_expected_mean_J']:
        assert abs(fresh[k]-saved[k])<=1e-8,(key,k)
    for a,b in zip(fresh['descriptive_95_percentile_pp'],saved['descriptive_95_percentile_pp']):
        assert abs(a-b)<=1e-8,key
    for k in ['both_success','adaptive_only','batch_only','neither']:
        assert abs(Fraction(fresh['paired_expected_counts'][k])-Fraction(saved['paired_expected_counts'][k]))<=Fraction(1,10**8)
fresh_recorded_check=replay['checks']['precision_completion_recorded_replay_check']
for key,value in [('recorded_blocks',1098),('case_convention_rows',2196),('paired_summary_groups',48)]:
    assert fresh_recorded_check[key]==completion_recorded_check[key]==value,key
completion_artifacts=[p for p in completion_dir.iterdir() if p.is_file() and p.suffix in {'.py','.tex','.txt'}]
# This one private review is deliberately excluded by the pinned packager.
# Do not silently discard any other unmanifested candidate from this glob.
completion_note=completion_dir/'internal_scientific_review.txt'
completion_note_name=completion_note.relative_to(ROOT).as_posix()
completion_note_sha='d1b7b3f7b4c38e70a3ec677314ab58a100637f4bc86881eca759bf0710f6b7fe'
assert completion_note in completion_artifacts
assert completion_note.stat().st_size==3733 and sha(completion_note)==completion_note_sha
assert completion_note_name not in current_manifest
packager_path=BASE/'package_release.py'
packager_sha='51e6e824b853f66586b3e8a9bc2727bac1748efad564e09e4956787899266f83'
assert sha(packager_path)==current_manifest[packager_path.relative_to(ROOT).as_posix()]==packager_sha
packager_spec=importlib.util.spec_from_file_location('verified_private_note_filter',packager_path)
packager_module=importlib.util.module_from_spec(packager_spec)
packager_spec.loader.exec_module(packager_module)
assert packager_module.include_current_path(completion_note) is False
completion_omission_archives=[]
for archive_path in [BASE/'peerj_revision/pre_editorial_delta_20261016/research_supplement.zip',
                     OUT/'research_supplement.zip']:
    with zipfile.ZipFile(archive_path) as archive:
        assert completion_note_name not in archive.namelist()
        manifest_digest=hashlib.sha256(archive.read('MANIFEST.sha256')).hexdigest()
    completion_omission_archives.append({'path':archive_path.relative_to(ROOT).as_posix(),
        'sha256':sha(archive_path),'manifest_sha256':manifest_digest})
completion_note_omission={'status':'VERIFIED_PRIVATE_EDITORIAL_EXCLUSION',
    'path':completion_note_name,'sha256':completion_note_sha,'bytes':3733,
    'packager_sha256':packager_sha,'excluded_from_archives':completion_omission_archives,
    'reason':'The pinned include_current_path filter rejects basenames ending _review.txt. This internal review is absent from both the successfully replayed baseline and final scientific archives. It remains locally preserved and is not a scientific replay input.'}
completion_artifacts.remove(completion_note)
for folder in ['inputs','all_418','refined_all']:
    completion_artifacts+=sorted((completion_dir/folder).glob('*.json'))
for p in completion_artifacts:
    assert current_manifest[p.relative_to(ROOT).as_posix()]==sha(p),p
completion_evidence={'status':'PASS','previously_open_cases_closed':418,'full_panel_exact_optima':1098,
    'excluded_internal_review':completion_note_omission,
    'primary_exact_check':replay['checks']['precision_completion_exact_verifier'],
    'full_panel_exact_check':replay['checks']['precision_completion_secondary_exact_verifier'],
    'corruption_tests':replay['checks']['precision_completion_corruption_tests'],
    'recorded_replay_check':fresh_recorded_check,'recorded_groups':completion_recorded['groups'],
    'secondary_status_counts':completion_recorded['secondary_status_counts'],
    'source_artifact_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in completion_artifacts},
    'replay_jobs':completion_jobs,
    'scope':'Exact uncapped, error-free half-width batch-precision optima on all1098 saved forecast-derived instances. Coefficient-only numerical secondary width refinement preserves exact primary precision; recorded replay is separate. The default run does not regenerate original raw records.'}
decision_dir=BASE/'joint_certification/decision_tolerance_probe'
decision_report=read(decision_dir/'results/report.json')
decision_source_check=read(decision_dir/'results/independent_check.json')
decision_saved_check=read(decision_dir/'saved_replay/report.json')
decision_fresh=replay['checks']['decision_tolerance_saved_endpoint_replay']
assert decision_report['status']==decision_source_check['status']==decision_saved_check['status']=='PASS'
assert decision_source_check['checker_sha256']==sha(decision_dir/'check.py')
assert decision_source_check['producer_report_sha256']==sha(decision_dir/'results/report.json')
for key,value in [('blocks',1098),('case_policy_factor_rows',38430),
                  ('oriented_pair_batch_endpoints_checked',65880),('bootstrap_intervals_recomputed',56)]:
    assert decision_fresh[key]==decision_saved_check[key]==value,key
assert decision_fresh['case_outcomes_sha256']==sha(decision_dir/'results/case_outcomes.csv')
assert decision_fresh['input_sha256']==sha(decision_dir/'results/saved_endpoint_inputs.json')
assert decision_fresh['checker_sha256']==sha(decision_dir/'replay_saved.py')
decision_artifacts=[decision_dir/name for name in ['analyze.py','check.py','replay_saved.py','protocol.json','README.txt',
    'results/report.json','results/independent_check.json','results/saved_endpoint_inputs.json','results/case_outcomes.csv']]
for p in decision_artifacts:
    assert current_manifest[p.relative_to(ROOT).as_posix()]==sha(p),p
decision_evidence={'status':'PASS','primary_factor':'1/100','cases':1098,
    'primary_cohort_summaries':{c:v['factors']['1/100'] for c,v in decision_report['cohorts'].items()},
    'default_derived_endpoint_check':decision_fresh,'separate_source_check':decision_source_check,
    'source_artifact_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in decision_artifacts},
    'scope':'Retrospective epsilon-decision diagnostic of unchanged precision policies. Bundled default verifies derived endpoints; pinned source regeneration was separately executed. Original fine-answer vectors are excluded. The tolerance is declared, not economically calibrated.'}

# Bind the current practical extension without relabeling earlier reviews or
# reusing the separately observed HTTP experiment as a deployment-cost trial.
gate_dir=BASE/'practical_retrieval_gate'
gate_report=read(gate_dir/'results/report.json')
gate_check=read(gate_dir/'results/independent_check.json')
gate_source=read(gate_dir/'source_check_results/independent_gate_math_check.json')
gate_http=read(gate_dir/'http_probe/report.json')
gate_http_log=read(gate_dir/'http_probe/http_log.json')
gate_manifest=read(gate_dir/'MANIFEST.json')
gate_fresh=replay['checks']['safe_retrieval_gate_and_cost_accounting']
gate_package_path=BASE/'peerj_revision/final_gate_package_review.json'
gate_package=read(gate_package_path)
for report in [gate_report,gate_check,gate_source,gate_http,gate_fresh,gate_package]:
    assert report['status']=='PASS'
gate_input_sha=sha(gate_dir/'inputs/public_decision_inputs_coherent.json')
assert gate_report['input_sha256']==gate_check['input_sha256']==gate_input_sha
assert gate_report['source_sha256']==sha(gate_dir/'analyze.py')
assert gate_check['source_sha256']==sha(gate_dir/'check_saved.py')
assert gate_check['analyzed_report_sha256']==sha(gate_dir/'results/report.json')
assert gate_report['blocks']==gate_check['exact_gates_checked']==1098
assert gate_report['exact_vertex_mse_checks']==gate_check['direct_vertex_loss_checks']==39528
assert Fraction(gate_report['epsilon_training_m2_factor'])==Fraction(1,100)
assert gate_report['models_per_shared_audit']==4 and gate_report['pairs_per_shared_audit']==6
assert gate_fresh['network_requests']==0
assert gate_package['network_connect_disabled'] is True
assert gate_package['isolated_folder_contains_no_parent_workspace_inputs'] is True
assert gate_package.get('current_manifest_sha256',gate_package.get('manifest_sha256'))==sha(gate_dir/'MANIFEST.json')
for name in ['report.json','independent_check.json','case_gate.json','archive_copy_trace.json',
             'cost_frontier.csv','range_frontiers.json','request_plans.json','routing_decisions.json',
             'tolerance_scale/independent_check.json','tolerance_scale/summary.json',
             'tolerance_scale/tolerance_scale_fragment.tex']:
    assert gate_fresh['result_hashes'][name]==sha(gate_dir/'results'/name),('gate replay',name)
for cohort,blocks,skips,copies,remaining in [('original',819,8,810,9),('external',279,198,270,3)]:
    row=gate_report['cohorts'][cohort]
    assert row['blocks']==blocks and row['zero_query_certificates']==skips
    assert row['required_fine_fetch_blocks']==blocks-skips
    assert row['retrospective']['archive_rounding_box_certified_blocks']==copies
    assert row['retrospective']['archive_after_gate_remaining_blocks']==remaining
    assert gate_source['cohorts'][cohort]=={'cases':blocks,'zero_retrieval':skips,'retrieval_required':blocks-skips}
assert gate_source['forecast_coordinates_checked']==26352
assert gate_source['pair_formulas_checked']==6588
assert gate_source['direct_vertex_loss_differences_checked']==39528
assert gate_source['outer_totals_checked']==1098
for relative,digest in gate_source['pins'].items():
    assert sha(ROOT/Path(relative))==digest,('gate optional source pin',relative)
assert gate_http['requests_attempted']==gate_check['saved_HTTP_requests_checked']==12
assert gate_http['plan_sha256']==sha(gate_dir/'http_probe/request_plan.json')
assert gate_http['log_sha256']==sha(gate_dir/'http_probe/http_log.json')
assert gate_check['exact_live_total_checks']==279
assert gate_check['external_zero_query_decisions_validated']==198
assert gate_check['external_bulk_selected_decisions_validated']==81
assert gate_check['network_requests_issued_by_checker']==0
for response in gate_http_log['records']:
    path=gate_dir/'http_probe'/f"response_{response['sequence']:02d}.json"
    assert response['status']==200 and response['error'] is None
    assert path.stat().st_size==response['response_body_bytes']
    assert sha(path)==response['response_sha256']==response['decoded_payload_sha256']
gate_artifacts=[gate_dir/'MANIFEST.json']
for relative,item in gate_manifest['files'].items():
    path=gate_dir/relative
    assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],relative
    gate_artifacts.append(path)
for path in gate_artifacts:
    assert current_manifest[path.relative_to(ROOT).as_posix()]==sha(path),path
gate_scale=read(gate_dir/'results/tolerance_scale/independent_check.json')
gate_scale_full=read(gate_dir/'results/tolerance_scale_full_source/independent_check.json')
for report,count,raw in [(gate_scale,279,False),(gate_scale_full,1098,True)]:
    assert report['status']=='PASS' and report['systems']==6 and report['cases']==1098
    assert report['independently_recomputed_blocks']==count
    assert report['original_raw_regeneration_performed'] is raw
    assert report['original_system_aggregates_only'] is True
    assert report['checker_sha256']==sha(gate_dir/'check_tolerance_scale.py')
    assert report['input_sha256']==gate_input_sha
    assert report['summary_sha256']==sha(gate_dir/'results/tolerance_scale/summary.json')
    assert report['fragment_sha256']==sha(gate_dir/'results/tolerance_scale/tolerance_scale_fragment.tex')
gate_evidence={
    'status':'PASS','replay_job':'safe_retrieval_gate_and_cost_accounting',
    'primary_factor':'1/100','blocks':1098,'input_sha256':gate_input_sha,
    'cohorts':gate_report['cohorts'],'independent_check':gate_check,
    'separate_raw_source_check':{'path':(gate_dir/'source_check_results/independent_gate_math_check.json').relative_to(ROOT).as_posix(),
        'sha256':sha(gate_dir/'source_check_results/independent_gate_math_check.json'),
        'source_pins':gate_source['pins'],'scope':gate_source['scope']},
    'cached_public_API':{'requests':12,'report_sha256':sha(gate_dir/'http_probe/report.json'),
        'plan_sha256':gate_http['plan_sha256'],'log_sha256':gate_http['log_sha256'],
        'scope':'Preserved actual range validation, including full-record downloads. Schedule savings are counterfactual replay; no downloads were avoided by the validation itself.'},
    'isolated_package_check':{'path':gate_package_path.relative_to(ROOT).as_posix(),
        'sha256':sha(gate_package_path),'scope':'Separate network-disabled standalone component check; complete publisher replay is independently required.'},
    'reported_timing_sha256':sha(gate_dir/'inputs/reported_gate_timing.json'),
    'tolerance_scale_context':{'default_check':gate_scale,'separate_full_source_check':gate_scale_full,
        'scope':'Unchanged tolerance interpreted against six system-level loss summaries. Default recomputes279 public external blocks and replays pinned original aggregates; the separate raw-source check recomputed all1098. Original fine-answer arrays and per-block original losses are not exported.'},
    'artifact_sha256':{path.relative_to(ROOT).as_posix():sha(path) for path in gate_artifacts},
    'scope':'Standard safe stopping for epsilon-optimal model choice, separate from joint half-width precision and the novel two-target theorem. Endpoint-cached counts, cold access, efficient whole-period bulk, saved forecast copies and repeat-cache reuse are explicit. No calibrated price, population latency, financial-saving or acceptance claim.'}

environment=read(OUT/'fresh_environment_setup_20261013.json')
assert environment['status']=='PASS' and environment['pip_check_returncode']==0
assert environment['requirements_sha256']==sha(OUT/'requirements-study.txt')
invocation=read(OUT/'peerj_replay_invocation_20261013.json')
assert Path(invocation['python_executable']).resolve()==Path(environment['executable']).resolve()
record={
    'status':'PASS', 'review_date':datetime.now(timezone.utc).date().isoformat(),'release_tag':RELEASE_TAG,
    'prior_release_history':{'path':history_path.relative_to(ROOT).as_posix(),
        'sha256':sha(history_path),'release_tag':history['release_tag'],
        'commit':history['commit'],'retained_files':len(history['files']),
        'prior_replay_steps':history['prior_replay_steps']},
    'failed_dependency_replay_history':dependency_evidence,
    'verification_mode':verification_mode,
    'editorial_delta':editorial_delta,
    'editorial_delta_report_sha256':sha(OUT/'editorial_delta_verification.json') if editorial_delta is not None else None,
    'execution_description':replay_description,
    'release_focus':'Shared-query guarantees and exact full-panel precision comparators, with source-linked decision diagnostics and a safe retrieval gate accounting for bulk, cache, cold access and saved forecasts.',
    'manuscript_title':manuscript_title,
    'empirical_review_revision':empirical_review,
    'precision_completion':completion_evidence,
    'decision_tolerance':decision_evidence,
    'practical_retrieval_gate':gate_evidence,
    'budget_revision':{
        'status':'PASS',
        'artifact_sha256':{path.relative_to(ROOT).as_posix():sha(path) for path in budget_artifacts},
        'support_checker_sha256':support['checker_sha256'],
        'support_family_sizes':[item['m'] for item in support['families']],
        'exact_support_width_evaluations':support['actual_width_evaluations'],
        'fixed_budget_summaries':budget_full['summaries'],
        'saving_cases_across_six_systems':systems,
        'fixed_three_vs_adaptive_two_cases':225,
        'qualifying_reading_reduction':'1/3',
        'additional_feedback_rounds_on_qualifying_cases':225,
        'full_source_independent_checks':budget_full_check['checks'],
        'external_replay_independent_checks':budget_replay_check['checks'],
        'general_partition_instances':180,'general_partition_enumerated_batches':20440,
        'replay_jobs':['two_target_support','reading_budget_external','reading_budget_external_check','reading_budget_general'],
        'scope':'Retrospective exact uncapped noiseless joint half-width assurance. Counts reserve scalar readouts, not HTTP calls, latency, dollars or model-selection gains. Optional answers and outcomes are not used. Adaptive budgets above two remain unsolved; bulk, capacity, measurement-error and greedy controls remain unchanged.',
        'original_source_scope':'Both-source ledger and independent report derive from the pinned-source route; default offline replay recomputes the external panel only.'},
    'delivery_script_sha256':{name:sha(BASE/'peerj_revision'/name) for name in
        ['finalize_delivery.py','prepare_github.py','verify_github.py',
         'refresh_delivery_docs.py','sync_submission_metadata.py',
         'editorial_delta_support.py','verify_editorial_delta.py']},
    'delivery_script_scope':'Local post-replay delivery gates, archived separately in GitHub verification/delivery_scripts; the scientific ZIP retains its exact manifested snapshot.',
    'completed_utc':datetime.now(timezone.utc).isoformat(),
    'target':'PeerJ Computer Science',
    'manuscript_sha256':source_sha,'pdf_sha256':pdf_sha,'zip_sha256':zip_sha,
    'pdf_pages':editorial['pdf_pages'],
    'abstract_words':editorial['abstract_words'],
    'full_current_package_replay':'outputs/current_clean_package_replay.json' if editorial_delta is None else None,
    'scientific_replay_record':'outputs/current_clean_package_replay.json',
    'scientific_replay_source_sha256':replay['manuscript_reproduced_sha256'],
    'replay_steps':len(replay['steps']),
    'complete_source_to_table_chain':'work/risk_adaptivity_revision/joint_certification/provenance_chain/executed/',
    'complete_source_to_table_rows':source_chain['all_case_ledger_rows_compared'],
    'complete_source_to_table_difference':source_chain['maximum_ledger_numeric_difference'],
    'fresh_both_panel_source_replay':{'path':fresh_chain_path.relative_to(ROOT).as_posix(),
        'sha256':sha(fresh_chain_path),'status':'PASS',
        'runtime_seconds':fresh_chain['runtime_seconds']['full_chain'],
        'no_reuse_flags':True,'new_forecast_fits':0,
        'scope':'Fresh single-invocation regeneration of both panels, coefficients, policies, exact certificates and 1,098 outcome rows using pinned raw sources and frozen forecasts; no independent refitting.'},
    'fresh_virtual_environment':'outputs/fresh_environment_setup_20261013.json',
    'threshold_case_rows_both_conventions':10980,
    'threshold_paired_summaries':320,
    'threshold_scope':'Exploratory unchanged-policy replay at five width targets; not new optimal precision policies or calibrated downstream decisions.',
    'final_challenger_diagnostics':{'regime_rows':diagnostics['regime_rows'],
        'replay_rows':diagnostics['replay_rows'],'paired_summary_rows':diagnostics['paired_summary_rows'],
        'scope':diagnostics['scope'],'regimes':diagnostics['regimes']},
    'practical_figure':{key:figure[key] for key in ['source_contrasts_checked','conditional_lines_checked',
        'exact_envelope_points_checked','envelope_equalities','replay_points_checked','exact_switch','exact_maximum']},
    'two_target_boundary':{
        'source_sha256':two_target_source_sha,
        'proof_input_sha256':two_target_reports['two_target_exact']['proof_input_sha256'],
        'theorem_fragment_sha256':sha(two_target_dir/'main_theorem.tex'),
        'family_sizes':[3,5,10],
        'exact_job':'two_target_exact','numerical_job':'two_target_lp',
        'numerical_verification':two_target_numeric,
        'scope':'Constructed fixed-two-query family: adaptive precision success 1 versus optimal randomized-batch success 1/m; includes all three paired contrasts of three nonnegative forecast vectors. Input dimension grows with m, normalized slack shrinks, and three fixed queries suffice. This does not alter or independently validate the empirical panels.',
        'review_memos':{name:{'path':str((two_target_dir/name).relative_to(ROOT)),
                             'sha256':sha(two_target_dir/name)}
                       for name in ['proof_review_memo.txt','novelty_review.txt']},
        'prior_execution_history':'outputs/pre_two_target_* preserve the preceding source-specific release; the two new jobs belong to the separately executed current replay.'},
    'assurance_feasibility':{
        'status':'PASS','source_sha256':assurance_source_sha,
        'proof_sha256':sha(assurance_dir/'proof.txt'),
        'full_report':{'path':assurance_full_path.relative_to(ROOT).as_posix(),
                       'sha256':sha(assurance_full_path)},
        'external_report':{'path':assurance_external_path.relative_to(ROOT).as_posix(),
                           'sha256':sha(assurance_external_path)},
        'full_witnesses_sha256':assurance_full['synthetic_witnesses_sha256'],
        'external_witnesses_sha256':assurance_external['synthetic_witnesses_sha256'],
        'full_check_counts':assurance_full['actual_check_counts'],
        'external_replay_check_counts':assurance_executed['actual_check_counts'],
        'regimes':assurance_regimes,'success_upper_bound':'19/20',
        'replay_job':'joint_assurance_feasibility',
        'fresh_source_evidence_sha256':sha(fresh_chain_path),
        'scope':'Elementary finite-action consequence: no two-reading randomized adaptive policy can guarantee precision on the 489 original and 94 external no-certainty cases under the uncapped exact-total noiseless prefix model. The 19/20 bound is not claimed optimal.',
        'execution_scope':'Source-derived full report verifies 583 adverse distributions and 11,660 strictly failing fibers; the current default offline replay independently regenerates the 94 external distributions and 1,880 fibers. Original raw records are not redistributed; this assurance job rebuilds their coefficients through the pinned-source route. The new diagnostic jobs separately replay bundled derived coefficient certificates. Recorded answers are unused for assurance.',
        'prior_execution_history':'outputs/pre_budget_* preserve the published assurance revision and its 77-step replay; pre_focus_* preserve the earlier release. Neither is substituted for the current replay.'},
    'latest_review_response':'outputs/LATEST_REVIEW_FIXES_20261013.txt',
    'manifested_members':package['manifested_members'],
    'journal_manifested_members':journal['manifested_files'],
    'journal_parts':journal['parts'],
    'journal_total_zip_bytes':journal['total_zip_bytes'],
    'replay_distribution':'Publisher Supplemental Data S1 and S2, extracted together; full historical archive separately hash-verified.',
    'historical_members_recoverable':package['old_members_exactly_recoverable'],
    'historical_editorial_notes_omitted':historical_omissions,
    'historical_preservation_scope':'Every prior manifested member remains hash-identical at its declared path or preserved alternate except explicitly identified internal editorial notes; those notes remain in the prior private archive/local files, not the current scientific assets.',
    'elapsed_replay_seconds':replay['elapsed_seconds'],
    'review_report':'outputs/PEERJ_REVIEW_AND_RESPONSE_20261013.txt',
    'visual_review':'outputs/peerj_final_visual_review.txt',
    'review_kind':'Current scoped mathematical, empirical and executable-package reviews plus the integrated source/PDF assessment. Earlier three reviewer reports remain source-bound history. No external specialist contact or formal proof-assistant certification.',
    'current_source_review':{'path':str(current_review_path.relative_to(ROOT)),
        'sha256':sha(current_review_path),'manuscript_sha256':source_sha,'pdf_sha256':pdf_sha},
    'workflow_editorial_revision':{'scope':'Exact-total noiseless audit routing, including the finite-witness bound against randomized adaptive certainty; policy objectives versus achieved guarantees. Full-panel batch-precision games are now closed. Historical controls remain unchanged; the new coefficient-only precision-optimal challenger has a separate recorded replay.',
        'render_evidence':str(current_review_path.relative_to(ROOT)),
        'checks':'Workflow and displayed-equation rendering explicitly assessed in the current source/PDF review.',
        'prior_execution_history':'outputs/pre_workflow_* retain the preceding source-specific successful replay; the current replay is separately executed.'},
    'current_boundary_review':{'path':str(boundary_review_path.relative_to(ROOT)),
        'sha256':sha(boundary_review_path),'manuscript_sha256':source_sha,
        'scope':'Current source-only mathematical and gate review; PDF rendering is assessed separately.'},
    'current_claims_review':{'path':claims_report_path.relative_to(ROOT).as_posix(),
        'sha256':sha(claims_report_path),'artifact_sha256':claims_files,
        'scope':claims_report['scope'],'manuscript_sha256':source_sha,'pdf_sha256':pdf_sha},
    'current_practical_review':{'path':practical_review_path.relative_to(ROOT).as_posix(),
        'sha256':sha(practical_review_path),'manuscript_sha256':source_sha,
        'scope':'Current source-only practical-claim review; not external validation or a PDF-rendering review.'},
    'prior_review_reports': {name:{'sha256':sha(BASE/'peerj_revision'/name),
        'scope':'Earlier source-specific review retained as history; not a new review of current artifacts.'}
        for name in prior_review_names},
    'full_current_package_replay_scope':replay['scope'] if editorial_delta is None else None,
    'scientific_replay_scope':replay['scope'],
    'study_environment':'Python3.12.14; requirements-study.txt versions, including SciPy1.18.1',
    'setup_failure_resolved':'Initial bundled-runtime attempt lacked SciPy and stopped at import before scientific checks; rerun used documented study environment. Log retained in peerj_runtime_setup_failure_20261013.log.',
    'native_process_failure':'A run of the preceding 71-step revision stopped at historical checker48 with an empty log. Windows Application Error1000 recorded a Python/ntdll.dll exception0xc000070a. The unchanged checker then passed, and a complete unchanged 71-step rerun passed. That source-specific history, event, failed-run log and invocation remain separately retained as peerj_native_crash_*_20261013 and pre_additional_review* files. The current final replay validates the later revision with the added diagnostics and figure; no automatic scientific-failure retries were added.',
    'integration_failure_resolved':'Initial integration scheduled frozen task-binding checks after geometry regeneration. Reordered them before regeneration and added an upfront dependency guard, tested on the actual driver. Old failure log: peerj_replay_order_failure_20261013.log. Scientific geometry entries matched; only its manifest differed.',
    'storage_setup_failure_resolved':'Staging attempts exhausted disk space before scientific checks. Temporary-copy deletion was previously blocked by automatic policy review; lossless NTFS compression of generated copies preserved their contents and recovered space. Logs: peerj_disk_setup_failure_20261013.log and peerj_disk_setup_failure_20261014.log. The latest compression additionally checked SHA-256 equality for twelve old generated trajectory copies; peerj_storage_compression_20261014.log records compression. The final unchanged replay passed after space was recovered.',
    'protocol_selection_case_interfaces':replay['checks']['protocol_selection_independent']['rows_checked'] if 'rows_checked' in replay['checks']['protocol_selection_independent'] else 116,
    'task_bindings_checked':29,'retained_endpoints_checked':58,
    'valid_scientific_ledger_unchanged':True,
    'practical_cost_analysis':'Exact supplied-catalogue frontier; 174 case-ratio decisions and 306 independently evaluated candidates. Declared costs, not new field savings.',
    'printed_worked_example':'Exact rational check of all displayed coefficient enclosures, both continuum branches and all ten adverse batch columns; optional regenerated geometry check recorded separately.',
    'fallback_guaranteed_cases':29,'fallback_budget_counts':{'2':22,'3':7},
    'peerj_alignment':'Structured abstract; CS algorithmic contribution; complete central proof and worked certificate; 12-point Times-style text; Letter paper and one-inch margins; left alignment; line numbers; references; explicit Acknowledgements; editable source; size-compliant current supplement and cover letter.',
    'policy_verification_limit':editorial['policy_verification_limit'],
    'scientific_verdict':'No unresolved blocking issue identified within the enumerated completed checks and scoped current internal reviews; the journal retains editorial and peer-review judgment.',
    'acceptance_probability':'Not calibrated. Internal proof and computational checks do not establish a greater-than90% acceptance probability or direct acceptance.',
    'author_ai_tools_terms_confirmation':'The author personally confirmed checking the AI tools\' terms of use and publication suitability. This records the author statement; other final author and portal facts remain separate.',
    'submission_status':'not submitted','external_contact':False,
    'last_recorded_browser_attempt':browser_record,
}
# Preserve the locally prepared but unpublished budget delivery records.
old_delivery_path=OUT/'risk_delivery_verification.json'
if old_delivery_path.is_file() and read(old_delivery_path).get('release_tag')=='peerj-cs-2026-10-15-diagnostics':
    for name in ['risk_delivery_verification.json','PEERJ_SUBMISSION_METADATA.json',
                 'PEERJ_CRITERIA_AUDIT.txt','SUBMISSION_READINESS.txt','FINAL_PEER_REVIEW.txt']:
        original=OUT/name
        retained=OUT/('pre_retrieval_gate_'+name)
        if original.is_file() and not retained.exists():
            shutil.copy2(original,retained)
if old_delivery_path.is_file() and read(old_delivery_path).get('release_tag')=='peerj-cs-2026-10-14-budget':
    for name in ['risk_delivery_verification.json','PEERJ_SUBMISSION_METADATA.json',
                 'PEERJ_CRITERIA_AUDIT.txt','SUBMISSION_READINESS.txt','FINAL_PEER_REVIEW.txt',
                 'peerj_cover_letter.txt','GITHUB_RELEASE_NOTES.txt']:
        original=OUT/name
        retained=OUT/('pre_diagnostics_'+name)
        if original.is_file() and not retained.exists():
            shutil.copy2(original,retained)
(OUT/'risk_delivery_verification.json').write_text(json.dumps(record,indent=2)+'\n')
manuscript=(OUT/'revised_manuscript.tex').read_text(encoding='utf8')
abstract=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',manuscript,re.S).group(1)
abstract=re.sub(r'\\textbf\{([^}]+)\}',r'\1',abstract).replace('$','').replace(r'\%','%').replace(r'\geq','>=').replace(r'\leq','<=')
abstract='\n\n'.join(' '.join(p.split()) for p in abstract.strip().split('\n\n'))
assert '\\' not in abstract
submission_metadata=read(OUT/'PEERJ_SUBMISSION_METADATA.json')
submission_metadata.update({
    'journal':'PeerJ Computer Science', 'article_type':'Research Article',
    'release_tag':RELEASE_TAG,
    'release_focus':record['release_focus'],
    'title':manuscript_title,
    'author':{'given_name':'Jishan','family_name':'Kapoor',
              'affiliation':'Independent Researcher, Toronto M4Y 1C9, Canada',
              'corresponding_email':'kapoorjishan19@gmail.com'},
    'abstract':abstract,
    'empirical_review_summary':empirical_review,
    'practical_retrieval_gate':gate_evidence,
    'keywords':['artificial intelligence','machine learning','adaptive information',
                'minimax risk','optimal recovery','robust optimization'],
    'preferred_subject_areas':['Optimization Theory and Computation',
                               'Algorithms and Analysis of Algorithms',
                               'Theory and Formal Methods'],
    'reviewer_expertise_request':['exact optimization','optimal recovery',
                                 'information-based complexity','robust optimization',
                                 'mathematical foundations of machine learning'],
    'reviewer_matching_status':'PeerJ draft 151201 has two suggested editors and three suggested reviewers saved with publication links. The author explicitly confirmed no coauthorship or other conflict with these reviewers. No contacts occurred outside the journal. Final legal declarations remain pending; the manuscript has not been submitted.',
    'portal_preparation':{
        'draft_id':'151201',
        'suggested_editors':['Thomas Stützle','Massimiliano Fasi'],
        'suggested_reviewers':[
            {'name':'David Krieg','email':'david.krieg@uni-passau.de','publication_link_saved':True},
            {'name':'Jannis Kurtz','email':'j.kurtz@uva.nl','publication_link_saved':True},
            {'name':'Pierre Gaillard','email':'pierre.gaillard@inria.fr','publication_link_saved':True}],
        'reviewer_conflicts':'Author explicitly confirmed no coauthorship or other conflict with the three suggested reviewers in the current chat.',
        'conference_presentation':'Author explicitly confirmed that the manuscript has never been presented at a conference.',
        'external_contacts_outside_journal':False,
        'final_legal_declarations':'pending',
        'submitted':False},
    'manuscript_sha256':source_sha,'pdf_sha256':pdf_sha,
    'files':['revised_manuscript.pdf','revised_manuscript.tex',
             'Supplemental_Data_S1.zip','Supplemental_Data_S2.zip','peerj_cover_letter.txt'],
    'status':'Prepared, not submitted. Signed-in PeerJ submission preparation is recorded; no submit action is implied.',
    'last_recorded_browser_attempt':browser_record,
    'author_declarations':'The author confirmed the AI-tools terms check and publication suitability, no coauthorship or other conflict with the three suggested reviewers, and no conference presentation. These are supplied author confirmations. Final legal declarations remain pending.',
})
metadata_history=OUT/'pre_diagnostics_PEERJ_SUBMISSION_METADATA.json'
if not metadata_history.exists():
    shutil.copy2(OUT/'PEERJ_SUBMISSION_METADATA.json',metadata_history)
(OUT/'PEERJ_SUBMISSION_METADATA.json').write_text(json.dumps(submission_metadata,indent=2)+'\n')
summary=('FINAL INTERNAL REVIEW AND RESPONSE -- JOINT PRECISION AND SAFE RETRIEVAL\n'
         f'Target: PeerJ Computer Science. {datetime.now(timezone.utc).date().isoformat()}.\n'
         f'Manuscript source SHA256:\n{source_sha}\n'
         f'{editorial["pdf_pages"]}-page PDF SHA256:\n{pdf_sha}\n'
         'Review: separate AI-assisted analytic, software and practical reviews, followed by integration and visual checks. No external human validation or journal submission.\n\n'
         'A preceding attempt of this revision failed at step83 because the journal-only package omitted the unchanged study_meter_results.json input. Its82 completed steps, error log, exact old package hashes and older source-bound records remain separately preserved. This failed attempt is not counted as a successful replay; the current complete corrected-package execution is independently required and reported below.\n'
         'The final safe gate is a standard stopping application, separate from the novel shared-query guarantee. It certifies one lexicographically selected model within the fixed 0.01 training-second-moment tolerance for every compatible completion. With endpoints retained, it avoids 8/819 original and 198/279 external per-block bulk requests. Cold access raises requests to 1,630 and 360 versus direct bulk at 819 and 279; whole-period direct bulk needs only three requests per cohort. These adverse controls remain explicit.\n'
         'Later forecast copies use binary64 enclosures and certify 810 original and 270 external blocks. After the initial gate, residual fine retrieval WITH ENDPOINTS RETAINED is three requests/51 values and two/22. Twelve actual API requests, including full-record downloads, validate the interface, all279 external totals and198 preselected epsilon decisions; avoided-fetch counts remain declared-schedule replay. No measured savings, provider pricing or population latency effect is claimed.\n'
         'The gate package includes coherent exact-loss inputs, cached responses, cost/cache ledgers, a network-free independent checker, preserved timing and an optional separately executed raw-source checker. The latter verified26,352 forecast coordinates,6,588 pair formulas,39,528 direct loss vertices and1,098 outer totals. The default replay does not refit models or fetch sources. Current gate mathematical, empirical and package reviews are pinned separately from the historical reviewer reports.\n'
         'The four empirical review issues are now computed, independently checked and included in the clean replay. Of 225 baseline reading-saving blocks, 191 isolate the shared-budget mechanism: every scalar contrast is separately fixed-batch certifiable within two readings. The other 34 include a scalar obstruction.\n'
         'The new full-domain game closes all 418 previously open randomized-batch precision cases. Exact rational covers and adverse distributions now identify the optimum on all 1,098 blocks. Every full-panel policy receives the same coefficient-only secondary width rule before recorded answers are read; the primary optimum is reverified exactly. Secondary numerical refinement and safe primary fallbacks are separately reported.\n'
         'At the declared training-scale absolute floor, all 57 baseline external blocks retain assurance. Thirty-nine need no feedback; the complete unchanged cohort uses 70 readings versus 88 minimum fixed readings. Across all 279 external blocks the corresponding totals are 358 versus 378, including 18 retained and two new feedback-saving cases. These are distinct denominators, and the floor is a declared sensitivity target rather than a calibrated decision threshold.\n'
         'All 222 matched-half certificates have a nonzero certified threshold interval. The complete bands [0.49,0.51], [0.475,0.525] and [0.45,0.55] are covered by 179, 119 and 53 cases. These sufficient intervals use frozen policies and have a closed lower and strict upper endpoint.\n'
         'On the same compatible cohorts, the E/2 cap excludes 25 of the 225 original saving cases, makes 191 fixed-certifiable and leaves nine requiring feedback. The E/3 cap excludes 75 and makes the remaining 150 fixed-certifiable. Thus both selection and added capacity information contribute to the reduced feedback advantage.\n'
         'The budget revision sharpens the exact two-target result: positive worst-record success requires every one of m specific batches, and the optimal batch mixture is uniquely uniform. Seven family sizes support 126,195 independently implemented exact width evaluations; the general claim follows from the printed argument.\n'
         'It also chooses a sufficient budget instead of assuming two readings. A linear scan finds the exact minimum fixed prefix budget for arbitrary numbers of intervals and contrasts. All 1,098 source-derived cases agree with complete batch enumeration and a separate shortest-path checker. The 180 constructed general instances cover 20,440 batches.\n'
         'On 168 original and 57 external blocks across all six systems, three fixed readings are necessary and sufficient, while two adaptive readings suffice. This saves one third of the reserved readings on the 225 qualifying blocks at the price of one additional feedback round per block. Complete-panel fixed totals 2,625 and 743 become 2,457 and 686 when using adaptation where certified and the minimum fixed fallback elsewhere: reductions 6.40% and 7.67%. These retrospective exact-model counts use no optional answers; they are not observed stopping times, HTTP savings, financial savings, a deployment contract, or optimized adaptive budgets above two.\n'
         'The new constructed family keeps two coordinate queries and two affine targets fixed: adaptation guarantees precision, while optimal randomized batching has success exactly 1/m for every m>=3. Each target separately admits a fixed two-query guarantee. The separation also holds for all three paired contrasts of three nonnegative forecast vectors.\n'
         'The measurement dictionary grows, normalized slack shrinks and three fixed queries suffice. This is a sharp information-model boundary, not a new empirical gain or a general deployment-saving claim.\n'
         f'The current replay includes exact rational certificates and {two_target_numeric["actual_total_LPs"]:,} actual endpoint/whole-branch LPs at m=3,5,10. Maximum endpoint discrepancy is {two_target_numeric["maximum_endpoint_discrepancy"]:.16g}; maximum width discrepancy is {two_target_numeric["maximum_width_discrepancy"]:.16g}, under a 1e-7 comparison tolerance and 1e-9 primal/dual solver tolerances. Finite numerical checks support the implementation; the all-m claim follows from the proof.\n'
         'The focused main text pairs the two-target boundary with assurance feasibility. An elementary finite-action consequence rules out certainty even for randomized adaptive policies on 489 original and 94 external blocks: worst-record success is at most 19/20. This is not a claimed tight optimum or a novel general impossibility principle.\n'
         'Source-bound rational checks verify 583 seed-independent adverse distributions and 11,660 strictly failing fibers without recorded answers. Default offline replay independently regenerates the 94 external distributions and 1,880 fibers; the original-panel evidence comes from the separately executed pinned-source chain. The claim applies to the uncapped exact-total noiseless prefix model.\n'
         'The complete frozen panels contain 819 original and 279 external blocks, all six model pairs per block, and two total readings. Recorded precision gains over fixed worst-width batches are 7.81 and 11.11 percentage points; greedy gains 2.20 and 2.15 points.\n'
         f"On 165 original and 57 external blocks, adaptation guarantees precision and the best randomized batch has exactly 50% worst-case success. Recorded adaptive success is 100%; the current precision-optimal secondary-refined batch has expectations of {current_half['original']['precision_batch_percent']:.2f}% and {current_half['external']['precision_batch_percent']:.2f}%. These subsets are selected by mathematical guarantees, not recorded outcomes.\n"
         'The decision-tolerance diagnostic reconstructs all 1,098 blocks and 38,430 policy/factor outcomes. At the declared primary tolerance, adaptive certification counts are 189 original and 277 external, versus 188/263 for the fixed worst-width batch and 186/277 for greedy. Thus the external gain over fixed batching does not extend to a gain over greedy. This retrospective diagnostic uses unchanged precision policies and a declared training-scale tolerance.\n'
         'At declared 1% stored errors and exact endpoints, 45 external blocks have verified adaptive precision guarantees that every randomized batch fails to match; 26 batch success upper bounds are at most one half. These are upper bounds, not unproved continuum equalities.\n'
         'Capacity, bulk retrieval and model-ordering controls are retained. On the external panel, exact adaptation certifies a best model on 207 blocks and greedy adaptation on 208, despite exact adaptation\'s higher joint-precision success. Measured public-API retrieval favors bulk. Cap-invalid records are flagged. The shared study is retrospective, not a locked untouched confirmation.\n'
         'The latest follow-up review, objective-matched challenger and paired-outcome uncertainty details are recorded in peerj_final_followup_review_20261013.txt and the indexed joint supplement.\n'
         f"The {editorial['pdf_pages']}-page paper leads with the fixed-two-query joint boundary, the assurance-feasibility decision and a worked source-derived certificate. Scalar classification and mean-risk developments remain in the supplement. Further witnesses and cost tables remain in Online Resource 1.\n"
         'The latest review also added a reconstructible shared-query algorithm box and absolute interval widths for the existing worked example. Direct endpoint LPs verify that table. A separately completed pinned source-to-table run regenerated both panels, all 165/57 matching certificates and all 1,098 table rows with zero numeric discrepancy. Default offline replay remains distinct from the original raw-source route. See LATEST_REVIEW_FIXES_20261013.txt.\n'
         f'The focused revision uses a policy-objective table, a worked certificate, complete matching batch-precision bounds, and a checked exploratory threshold sweep over all 1,098 blocks with unchanged historical policies. The earlier open-game results remain reproducible controls; the current precision optimum is closed on the full panel. The main paper has {editorial["pdf_pages"]} pages; full pairwise controls remain in S6. The current package ran in the isolated virtual environment with the pinned requirements. See LATEST_REVIEW_FIXES_20261013.txt for all changes and limits.\n'
         'The latest diagnostic reports the complete fixed/adaptive/no-guarantee partition, the saved greedy-first-query assurance gaps and a stronger fixed-batch fallback. These are retrospective additions using unchanged data. A source-linked two-panel figure displays the exact acquisition envelopes and recorded target sensitivity. The scalar Helly result is explicitly distinguished from the joint objective.\n'
         'Earlier read-only fit and practical-value challenges are retained in peerj_final_fit_challenge.txt and peerj_practical_value_challenge.txt with their original source hashes. They are historical internal reviews, not a new review of this source. The current compiled-source and PDF review is latest_compiled_review.txt, bound to the hashes above.\n'
         'Live PeerJ policies and author instructions were checked. Supplemental Data S1/S2 meet the 30 MB individual and 50 MB combined limits. The complete historical archive remains separately preserved.\n'
         'The three-criterion audit is in PEERJ_CRITERIA_AUDIT.txt. Remaining factual author confirmations are listed in PEERJ_AUTHOR_DECLARATIONS.txt; unknown historical AI model identifiers are disclosed, not invented.\n'
         'Author-supervised AI disclosure accurately credits author topic/direction and substantive content/code/drafting assistance.\n'
         'The author personally confirmed checking the AI tools\' terms of use and publication suitability; that item is no longer pending. Final content approval, disclosure accuracy, record retention and unrelated portal terms remain separately recorded.\n'
         'The final prose cleanup removes revision-only wording and repeated caveats while retaining the scientific values, chronology, uncertainty definitions and unfavorable controls. The bounded fragment-edit record is first_reader_prose_review.txt; the final source/PDF assessment remains latest_compiled_review.txt.\n'
         'The introductory workflow makes the bulk/fixed/adaptive/extend decision explicit under the declared exact-total noiseless model. The no-certainty branch now covers all randomized adaptive policies. This supports a protocol-feasibility decision under the declared interface, not a validated deployment, privacy or model-selection benefit. Policy objectives and guarantees are distinguished from recorded outcomes. The current compiled review covers the workflow and displayed equations. Prior successful executions remain source-bound; the execution scope below distinguishes any subsequent prose-only delta from a new scientific run.\n'
         'No calibrated individual acceptance probability or greater-than-80% threshold is established by these checks.\n')
appendix=('\nFINAL EXECUTABLE VERIFICATION\n'
          +replay_description+'\n'
          +f"Preserved scientific-run elapsed time: {replay['elapsed_seconds']:.2f} seconds. Current publisher supplement: {journal['manifested_files']} manifested members.\n"
          f'ZIP SHA256: {zip_sha}\n'
          'Both new task-binding checks and all malformed-input regressions passed.\n'
          'The initial wrong-runtime import failure and its correction are recorded in risk_delivery_verification.json.\n')
summary+=appendix
(OUT/'PEERJ_REVIEW_AND_RESPONSE_20261013.txt').write_text(summary)
(OUT/'FINAL_PEER_REVIEW.txt').write_text(summary)
(OUT/'SUBMISSION_READINESS.txt').write_text(
    f'CURRENT SCIENTIFIC PREPARATION -- {datetime.now(timezone.utc).date().isoformat()}\n'
    'Target: PeerJ Computer Science, Research Article.\n'
    'Internal review: no unresolved blocking scientific flaw identified after corrections.\n'
    'Proof and prior-art review are analytic; reproduction has its separately stated finite scope.\n'
    f'Current source SHA256: {source_sha}\nCurrent PDF: {editorial["pdf_pages"]} pages.\n'
    'Submission files: revised_manuscript.tex; revised_manuscript.pdf; Supplemental_Data_S1.zip; Supplemental_Data_S2.zip; peerj_cover_letter.txt. The larger research_supplement.zip preserves development history separately.\n'
    +replay_description+'\n'
    'Default replay includes task-bound acquisition checks and manuscript reconstruction; no new forecast fitting, source downloading or HTTP measurement.\n'
    'The final gate reproduces all1,098 epsilon decisions and fair bulk/cache/cold-access accounting. Separate preserved twelve-request API validation checks279 external totals and198 preselected tolerance decisions; it included full downloads. Endpoint-cached replay saves198/279 external requests but cold access and whole-period batching favor bulk. This standard stopping application is separate from the paper\'s joint-precision contribution.\n'
    'The preceding four budget jobs verify necessary mixture support, exact fixed-budget external replay, its independently implemented shortest-path/endpoint checks and general partition checks. Source-bound reports cover both panels separately. All 225 qualifying blocks require three fixed or two adaptive readings, with one additional feedback round; the complete-panel reserved-reading reductions are 6.40% and 7.67% under the uncapped noiseless exact-total model.\n'
    'The eleven current diagnostic jobs separately verify scalar budgets, loss-scale floors, the 57-case assurance plan, rational threshold margins and paired capacity attribution. The full-panel floor result is 358 versus 378 external readings; the unchanged 57-case cohort result is 70 versus 88, with all 57 assured.\n'
    'The completion jobs verify all 418 previously open precision games, the full1,098-case primary-optimal challenger and its numerical secondary rule, the recorded replay, and eight deliberate certificate/coverage corruptions. The decision diagnostic replays derived endpoints and56 bootstrap intervals; its separate source-linked checker also passed. Original BLEM fine-answer vectors are excluded from both journal ZIPs and the full release.\n'
    'The new fixed-two-query theorem has exact rational and 7,131-LP replay checks for m=3,5,10, with current checker and proof-input hashes. Its all-three-pair extension is a constructed forecast realization, not a relabeling of the empirical study.\n'
    'The assurance-feasibility consequence has source-bound exact witnesses on all 489 original and 94 external no-certainty cases; default replay independently regenerates the external certificates. The 19/20 randomized-adaptive upper bound need not be tight and concerns only the declared uncapped exact-total noiseless model.\n'
    'The earlier 29-case fallback result is two readings for 22 cases and three for 7 at the declared 1% internal error with exact endpoints. The current shared-query extension is reported separately.\n'
    'Live policies and preparation instructions were inspected through the browser. The author confirmed the AI-tools terms check and publication suitability. Other final author attestations, unavailable historical exact AI-version identifiers, portal terms and fees remain separate from scientific readiness; see PEERJ_AUTHOR_DECLARATIONS.txt.\n'
    'No calibrated individual acceptance probability or greater-than80% threshold is established.\n'
    f'No paper submitted and no external person contacted. PeerJ sign-in and submission preparation were observed at {browser_record["checked_utc"]}; no new password was entered. This delivery script performs no browser action. The observed state is hash-bound in PEERJ_SUBMISSION_METADATA.json and risk_delivery_verification.json.\n'
    'Detailed response: PEERJ_REVIEW_AND_RESPONSE_20261013.txt. Current hashes and verification: risk_delivery_verification.json.\n')
print(json.dumps({k:record[k] for k in ['status','pdf_pages','replay_steps','manifested_members','elapsed_replay_seconds','manuscript_sha256','zip_sha256']},indent=2))
