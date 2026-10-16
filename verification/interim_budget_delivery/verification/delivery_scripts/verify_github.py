"""Confirm remote identity, private visibility, commit and uploaded asset bytes."""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'outputs'
REPO = 'floxy-21/risk-adaptivity-ml-audits'
TAG = 'peerj-cs-2026-10-14-budget'
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
budget=delivery['budget_revision']
assert budget['status']=='PASS' and delivery['replay_steps']==81
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
for name,digest in delivery['delivery_script_sha256'].items():
    relative='verification/delivery_scripts/'+name
    assert sha(Path(__file__).parent/name)==sha(prepared/relative)==digest,name
    committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=prepared)
    assert hashlib.sha256(committed).hexdigest()==digest,name
history_names=[]
for path in sorted(list(OUT.glob('pre_focus_*'))+list(OUT.glob('pre_budget_*'))):
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
        'two_target_proof_input_sha256':delivery['two_target_boundary']['proof_input_sha256'],
        'assurance_source_sha256':assurance['source_sha256'],
        'assurance_full_report_sha256':assurance['full_report']['sha256'],
        'assurance_external_report_sha256':assurance['external_report']['sha256'],
        'assurance_success_upper_bound':assurance['success_upper_bound'],
        'budget_revision':budget,
        'current_claims_review':delivery['current_claims_review'],
        'current_practical_review':delivery['current_practical_review'],
        'previous_release_preserved':{'tag':PREVIOUS_TAG,'commit':previous['commit'],
                                      'url':previous_release['html_url'],'asset_count':len(previous_assets)},
        'prior_release_history':delivery['prior_release_history'],
        'preserved_history_files':history_names,
        'delivery_script_sha256':delivery['delivery_script_sha256'],
        'historical_members_recoverable':delivery['historical_members_recoverable'],
        'historical_editorial_notes_omitted':delivery['historical_editorial_notes_omitted'],
        'release_url':release['html_url'],'assets':checks,
        'journal_submission_status':'not submitted',
        'verification':'GitHub server-provided SHA-256 digests match all six local release assets; remote commit equals local prepared commit.'}
(ROOT/'outputs/github_delivery_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
