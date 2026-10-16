"""Confirm remote identity, private visibility, commit and uploaded asset bytes."""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
REPO = 'floxy-21/risk-adaptivity-ml-audits'
TAG = 'peerj-cs-2026-10-14-assurance'
PREVIOUS_TAG = 'peerj-cs-2026-10-13-two-target'
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
assert delivery['release_tag']==TAG and delivery['pdf_pages']==28
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
previous=json.loads((ROOT/'outputs/pre_focus_github_delivery_verification.json').read_text())
assert previous['status']=='PASS' and previous['tag']==PREVIOUS_TAG
previous_release=api('/releases/tags/'+PREVIOUS_TAG)
assert api('/commits/'+PREVIOUS_TAG)['sha']==previous['commit']
previous_assets={asset['name']:asset for asset in previous_release['assets']}
assert set(previous_assets)=={asset['name'] for asset in previous['assets']}
for asset in previous['assets']:
    retained=previous_assets[asset['name']]
    assert retained['size']==asset['bytes'] and retained['digest']=='sha256:'+asset['sha256']
prepared=ROOT/'work/github_delivery_20261013'
for name,digest in delivery['delivery_script_sha256'].items():
    relative='verification/delivery_scripts/'+name
    assert sha(Path(__file__).parent/name)==sha(prepared/relative)==digest,name
    committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=prepared)
    assert hashlib.sha256(committed).hexdigest()==digest,name
history_names=[]
for path in sorted((ROOT/'outputs').glob('pre_focus_*')):
    if path.is_file() and path.suffix.lower() in {'.json','.txt','.log','.tex','.pdf'}:
        relative='verification/'+path.name
        assert sha(prepared/relative)==sha(path),relative
        committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=prepared)
        assert hashlib.sha256(committed).hexdigest()==sha(path),relative
        history_names.append(relative)
assert history_names
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
        'pdf_sha256':delivery['pdf_sha256'],'replay_steps':delivery['replay_steps'],
        'two_target_proof_input_sha256':delivery['two_target_boundary']['proof_input_sha256'],
        'assurance_source_sha256':assurance['source_sha256'],
        'assurance_full_report_sha256':assurance['full_report']['sha256'],
        'assurance_external_report_sha256':assurance['external_report']['sha256'],
        'assurance_success_upper_bound':assurance['success_upper_bound'],
        'previous_release_preserved':{'tag':PREVIOUS_TAG,'commit':previous['commit'],
                                      'url':previous_release['html_url'],'asset_count':len(previous_assets)},
        'pre_focus_history_files':history_names,
        'delivery_script_sha256':delivery['delivery_script_sha256'],
        'historical_members_recoverable':delivery['historical_members_recoverable'],
        'historical_editorial_notes_omitted':delivery['historical_editorial_notes_omitted'],
        'release_url':release['html_url'],'assets':checks,
        'journal_submission_status':'not submitted',
        'verification':'GitHub server-provided SHA-256 digests match all six local release assets; remote commit equals local prepared commit.'}
(ROOT/'outputs/github_delivery_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
