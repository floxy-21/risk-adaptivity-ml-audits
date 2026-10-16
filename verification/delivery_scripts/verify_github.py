"""Confirm remote identity, private visibility, commit and uploaded asset bytes."""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from editorial_delta_support import load_verified_delta

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'outputs'
REPO = 'floxy-21/risk-adaptivity-ml-audits'
TAG = 'peerj-cs-2026-10-16-retrieval-gate'
PREVIOUS_TAG = 'peerj-cs-2026-10-14-assurance'
def api(suffix=''):
    return json.loads(subprocess.check_output(['gh','api','repos/'+REPO+suffix],encoding='utf-8'))
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4<<20),b''):h.update(block)
    return h.hexdigest()
repo=api()
assert repo['full_name']==REPO and repo['private'] is True
delivery=json.loads((ROOT/'outputs/risk_delivery_verification.json').read_text())
assert delivery['status']=='PASS'
assert delivery['release_tag']==TAG
assert delivery['manuscript_title']=='Adaptive Reading Budgets for Joint Forecast Audits with Cumulative Data'
editorial=json.loads((OUT/'risk_editorial_verification.json').read_text())
assert editorial['status']=='passed'
assert editorial['manuscript_sha256']==delivery['manuscript_sha256']
assert editorial['pdf_sha256']==delivery['pdf_sha256']
assert delivery['pdf_pages']==editorial['pdf_pages'] and delivery['pdf_pages']>0
assert delivery['submission_status']=='not submitted'
editorial_delta=None
if delivery.get('editorial_delta') is not None:
    assert delivery['editorial_delta_report_sha256']==sha(OUT/'editorial_delta_verification.json')
    editorial_delta=load_verified_delta(ROOT,json.loads((OUT/'current_clean_package_replay.json').read_text()),
        delivery['manuscript_sha256'],delivery['pdf_sha256'])
    assert editorial_delta==delivery['editorial_delta']
dependency_history=delivery['failed_dependency_replay_history']
assert dependency_history['status']=='PRESERVED_FAILED_EXECUTION'
assert dependency_history['failed_step']==83 and dependency_history['completed_steps']==82
assert sha(ROOT/dependency_history['preservation_path'])==dependency_history['preservation_sha256']
for item in dependency_history['failed_journal_parts']:
    retained=ROOT/item['retained']
    assert retained.stat().st_size==item['bytes'] and sha(retained)==item['sha256']
for key,name in [('manuscript_sha256','revised_manuscript.tex'),
                 ('pdf_sha256','revised_manuscript.pdf'),
                 ('zip_sha256','research_supplement.zip')]:
    assert delivery[key]==sha(ROOT/'outputs'/name)
assert delivery['two_target_boundary']['numerical_verification']['actual_total_LPs']==7131
assurance=delivery['assurance_feasibility']
assurance_dir=ROOT/'work/risk_adaptivity_revision/joint_certification/assurance_feasibility'
assert assurance['status']=='PASS' and assurance['success_upper_bound']=='19/20'
assert assurance['source_sha256']==sha(assurance_dir/'verify_assurance.py')
assert assurance['proof_sha256']==sha(assurance_dir/'proof.txt')
for key in ['full_report','external_report']:
    assert assurance[key]['sha256']==sha(ROOT/assurance[key]['path'])
diagnostics=delivery['empirical_review_revision']
assert diagnostics['status']=='PASS' and diagnostics['joint_only_blocks']==191
assert diagnostics['external_baseline_cohort']=={'blocks':57,'assured':57,'selected_readings':70,
    'minimum_fixed_readings':88,'still_need_feedback':18,'now_fixed_suffices':39}
assert diagnostics['external_full_panel']['selected_readings']==358
assert diagnostics['external_full_panel']['minimum_fixed_readings']==378
for relative,digest in diagnostics['artifact_sha256'].items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
gate=delivery['practical_retrieval_gate']
assert gate['status']=='PASS' and gate['blocks']==1098 and gate['primary_factor']=='1/100'
assert [(gate['cohorts'][c]['zero_query_certificates'],gate['cohorts'][c]['blocks'])
        for c in ['original','external']]==[(8,819),(198,279)]
for relative,digest in gate['artifact_sha256'].items():
    assert sha(ROOT/relative)==digest,relative
budget=delivery['budget_revision']
assert budget['status']=='PASS' and delivery['replay_steps']==7+len(json.loads((ROOT/'work/risk_adaptivity_revision/replay_jobs.json').read_text()))
assert budget['exact_support_width_evaluations']==126195
assert budget['fixed_three_vs_adaptive_two_cases']==225
assert budget['qualifying_reading_reduction']=='1/3'
assert budget['additional_feedback_rounds_on_qualifying_cases']==225
for relative,digest in budget['artifact_sha256'].items():
    assert sha(ROOT/relative)==digest,relative
package=json.loads((ROOT/'outputs/risk_supplement_verification.json').read_text())
assert package['zip_sha256']==delivery['zip_sha256']
assert delivery['historical_members_recoverable']==package['old_members_exactly_recoverable']
assert delivery['historical_editorial_notes_omitted']==package['old_editorial_notes_omitted']
local=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'work/github_delivery_20261013',text=True).strip()
remote=api('/commits/main')['sha']
assert local==remote
release=api('/releases/tags/'+TAG)
assert api('/commits/'+TAG)['sha']==remote
# A new tag must not replace the source-bound release retained before narrowing.
previous=json.loads((ROOT/'outputs/pre_budget_github_delivery_verification.json').read_text())
assert previous['status']=='PASS' and previous['tag']==PREVIOUS_TAG
assert previous['commit']=='c878784db195e74be395ff9735870eeef1054c4c'
previous_release=api('/releases/tags/'+PREVIOUS_TAG)
assert api('/commits/'+PREVIOUS_TAG)['sha']==previous['commit']
previous_assets={asset['name']:asset for asset in previous_release['assets']}
assert set(previous_assets)=={asset['name'] for asset in previous['assets']}
for asset in previous['assets']:
    retained=previous_assets[asset['name']]
    assert retained['size']==asset['bytes'] and retained['digest']=='sha256:'+asset['sha256']
prepared=ROOT/'work/github_delivery_20261013'
if editorial_delta is not None:
    sources=[OUT/'editorial_delta_verification.json']+[ROOT/n for n in editorial_delta['artifact_sha256']]
    assert len({p.name for p in sources})==len(sources)
    for path in sources:
        destination='verification/editorial_delta/'+path.name
        assert sha(path)==sha(prepared/destination)
        committed=subprocess.check_output(['git','show','HEAD:'+destination],cwd=prepared)
        assert hashlib.sha256(committed).hexdigest()==sha(path),destination
for relative,digest in dependency_history['artifact_sha256'].items():
    destination=dependency_history['github_paths'][relative]
    assert destination.startswith('verification/pre_dependency_fix_20261016/')
    assert not destination.endswith('.zip')
    assert sha(ROOT/relative)==sha(prepared/destination)==digest,destination
    committed=subprocess.check_output(['git','show','HEAD:'+destination],cwd=prepared)
    assert hashlib.sha256(committed).hexdigest()==digest,destination
practical_review=ROOT/delivery['current_practical_review']['path']
practical_destination='verification/'+practical_review.name
assert sha(practical_review)==sha(prepared/practical_destination)==delivery['current_practical_review']['sha256']
committed=subprocess.check_output(['git','show','HEAD:'+practical_destination],cwd=prepared)
assert hashlib.sha256(committed).hexdigest()==delivery['current_practical_review']['sha256']
for relative,digest in delivery['current_claims_review']['artifact_sha256'].items():
    path=ROOT/relative
    destination='verification/current_claims_review/'+path.name
    assert sha(path)==sha(prepared/destination)==digest,destination
    committed=subprocess.check_output(['git','show','HEAD:'+destination],cwd=prepared)
    assert hashlib.sha256(committed).hexdigest()==digest,destination
for relative,digest in budget['artifact_sha256'].items():
    category=('two_target_boundary' if 'two_target_boundary/' in relative
              else 'reading_budget')
    component=relative.split(category+'/',1)[1]
    destination='verification/budget_revision/'+category+'/'+component
    assert sha(prepared/destination)==digest,destination
    committed=subprocess.check_output(['git','show','HEAD:'+destination],cwd=prepared)
    assert hashlib.sha256(committed).hexdigest()==digest,destination
for relative,digest in diagnostics['artifact_sha256'].items():
    component=relative.split('joint_certification/',1)[1]
    destination='verification/empirical_review_revision/'+component
    assert sha(ROOT/relative)==sha(prepared/destination)==digest,destination
    committed=subprocess.check_output(['git','show','HEAD:'+destination],cwd=prepared)
    assert hashlib.sha256(committed).hexdigest()==digest,destination
for name,digest in delivery['delivery_script_sha256'].items():
    relative='verification/delivery_scripts/'+name
    assert sha(Path(__file__).parent/name)==sha(prepared/relative)==digest,name
    committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=prepared)
    assert hashlib.sha256(committed).hexdigest()==digest,name
history_names=[]
for path in sorted(list(OUT.glob('pre_focus_*'))+list(OUT.glob('pre_budget_*'))+list(OUT.glob('pre_diagnostics_*'))+list(OUT.glob('pre_retrieval_gate_*'))):
    if path.is_file() and path.suffix.lower() in {'.json','.txt','.log','.tex','.pdf'}:
        relative='verification/'+path.name
        assert sha(prepared/relative)==sha(path),relative
        committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=prepared)
        assert hashlib.sha256(committed).hexdigest()==sha(path),relative
        history_names.append(relative)
assert history_names
history_manifest=ROOT/delivery['prior_release_history']['path']
assert sha(history_manifest)==delivery['prior_release_history']['sha256']
history=json.loads(history_manifest.read_text())
assert history['status']=='PASS' and history['release_tag']==PREVIOUS_TAG
assert history['commit']==previous['commit'] and history['prior_replay_steps']==77
for item in history['files']:
    path=ROOT/item['retained']
    assert sha(path)==item['sha256'],item['retained']
    relative=('verification/'+path.name if path.parent==OUT
              else 'verification/pre_budget_delivery/'+path.name)
    assert sha(prepared/relative)==item['sha256'],relative
    committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=prepared)
    assert hashlib.sha256(committed).hexdigest()==item['sha256'],relative
expected={'RELEASE_SHA256.txt','research_supplement.zip','revised_manuscript.pdf','revised_manuscript.tex',
          'Supplemental_Data_S1.zip','Supplemental_Data_S2.zip'}
assert {a['name'] for a in release['assets']}==expected
checks=[]
for asset in release['assets']:
    path=ROOT/'outputs'/asset['name']
    digest=sha(path)
    assert asset['state']=='uploaded' and asset['size']==path.stat().st_size
    assert asset['digest']=='sha256:'+digest
    checks.append({'name':asset['name'],'bytes':asset['size'],'sha256':digest})
result={'status':'PASS','verified_utc':datetime.now(timezone.utc).isoformat(),
        'repository_url':repo['html_url'],'private':True,'commit':remote,
        'tag':TAG,'manuscript_sha256':delivery['manuscript_sha256'],
        'manuscript_title':delivery['manuscript_title'],
        'pdf_sha256':delivery['pdf_sha256'],'replay_steps':delivery['replay_steps'],
        'verification_mode':delivery['verification_mode'],
        'execution_description':delivery['execution_description'],
        'editorial_delta_report_sha256':delivery.get('editorial_delta_report_sha256'),
        'two_target_proof_input_sha256':delivery['two_target_boundary']['proof_input_sha256'],
        'assurance_source_sha256':assurance['source_sha256'],
        'assurance_full_report_sha256':assurance['full_report']['sha256'],
        'assurance_external_report_sha256':assurance['external_report']['sha256'],
        'assurance_success_upper_bound':assurance['success_upper_bound'],
        'budget_revision':budget,
        'empirical_review_revision':diagnostics,
        'practical_retrieval_gate':gate,
        'current_claims_review':delivery['current_claims_review'],
        'current_practical_review':delivery['current_practical_review'],
        'previous_release_preserved':{'tag':PREVIOUS_TAG,'commit':previous['commit'],
                                      'url':previous_release['html_url'],'asset_count':len(previous_assets)},
        'prior_release_history':delivery['prior_release_history'],
        'failed_dependency_replay_history':dependency_history,
        'preserved_history_files':history_names,
        'delivery_script_sha256':delivery['delivery_script_sha256'],
        'historical_members_recoverable':delivery['historical_members_recoverable'],
        'historical_editorial_notes_omitted':delivery['historical_editorial_notes_omitted'],
        'release_url':release['html_url'],'assets':checks,
        'journal_submission_status':'not submitted',
        'verification':'GitHub server-provided SHA-256 digests match all six local release assets; remote commit equals local prepared commit.'}
(ROOT/'outputs/github_delivery_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
