"""Validate the bounded editorial/fresh-refit archive delta against a passed baseline.

No unchanged full-period analysis is rerun. Every prior member outside the
explicit editorial/packaging allowlist must remain byte-identical. New public
refit arithmetic and exact TeX reconstruction execute in a fresh extraction;
the optional-refit prerequisite is exercised through pinned raw restoration
and fresh preparation, without redundantly training another192 estimators.
The complete current archive can instead be tested from scratch with
work/validate_submission_archive.py.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from revision_extension_inputs import REFIT_DIR, REFIT_FILES, ALLOWED_FRAGMENT_TEX

ROOT=Path(__file__).resolve().parents[1]
BASELINE_SHA='6d9a25d921c21c252ed41f6237131cdd23b44f06cd6055b32038e335770a41c4'
BASELINE_REPORT_SHA='0a233c42aa4610c873c7a8cf9ad11750f467ffaa767bebf2ab38348d87289faf'
ALLOWED_CHANGED=frozenset([
    'README.txt','MANIFEST.sha256','outputs/REPRODUCE.txt',
    'outputs/manuscript_reconstruction_check.json',
    'work/build_research_supplement.py','work/check_manuscript_reconstruction.py',
    'work/integrate_randomized_revision.py','work/revision_extension_inputs.py',
    'work/build_final_manuscript.py','work/final_sections.json',
    'work/validate_submission_archive.py'])
ALLOWED_ADDED=frozenset([
    *(REFIT_DIR+'/'+name for name in REFIT_FILES),
    'work/final_peer_review/editorial_trim.py',
    'work/reproduce_final_revision.py','work/validate_supplement_delta.py',
    'work/packaging_baseline_manifest.json','work/packaging_baseline_verification.json'])

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def execute(stage,args,name):
    log=stage/'work'/('delta_'+name+'.log')
    with log.open('w',encoding='utf-8') as stream:
        completed=subprocess.run([sys.executable,*args],cwd=stage,stdout=stream,stderr=subprocess.STDOUT,text=True)
    if completed.returncode:
        print(log.read_text(encoding='utf-8',errors='replace')[-9000:],flush=True)
        raise RuntimeError('Delta stage failed; preserved log: '+str(log))
    text=log.read_text(encoding='utf-8');entry=json.loads(text[text.rfind('\n{')+1:])
    path=Path(entry['report']);assert path.resolve().is_relative_to(stage.resolve())
    return json.loads(path.read_text()),str(path.relative_to(stage)),str(log.relative_to(stage))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-zip',type=Path,default=ROOT/'work/final_peer_review/baseline_research_supplement.zip')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'work')
    args=parser.parse_args()
    baseline=json.loads((ROOT/'work/packaging_baseline_manifest.json').read_text())
    baseline_report=ROOT/'work/packaging_baseline_verification.json'
    assert sha(baseline_report)==BASELINE_REPORT_SHA
    proof=json.loads(baseline_report.read_text())
    assert proof['status']=='passed' and proof['archive_sha256']==BASELINE_SHA==baseline['sha256']
    assert proof['fresh_extract_tests_run']==41 and proof['test_failures']==proof['test_errors']==0
    old={v['path']:v['sha256'] for v in baseline['manifest']}
    baseline_bytes_checked=args.baseline_zip.exists()
    if baseline_bytes_checked:
        assert sha(args.baseline_zip)==BASELINE_SHA
        with zipfile.ZipFile(args.baseline_zip) as z:
            assert set(z.namelist())==set(old)
            assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in old.items())
    archive_path=ROOT/'outputs/research_supplement.zip'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    stage=ROOT/'work'/('supplement_delta_verify_'+stamp);stage.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive_path) as z:
        assert z.testzip() is None
        new={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
        assert len(new)==len(z.namelist())
        changed={n for n in old.keys()&new.keys() if old[n]!=new[n]}
        added=set(new)-set(old);removed=set(old)-set(new)
        assert not removed,removed
        assert changed<=ALLOWED_CHANGED,('Unpermitted changed files',sorted(changed-ALLOWED_CHANGED))
        assert added==ALLOWED_ADDED,('Unexpected added files',sorted(added^ALLOWED_ADDED))
        assert {n for n in new if n.endswith('.tex')}==set(ALLOWED_FRAGMENT_TEX)
        assert not any(n.endswith(('.pdf','.pkl')) or n in ['outputs/study_predictions.csv',REFIT_DIR+'/fresh_predictions.csv'] for n in new)
        for n in new:assert (stage/n).resolve().is_relative_to(stage.resolve())
        z.extractall(stage)
    for line in (stage/'MANIFEST.sha256').read_text().splitlines():
        expected,name=line.split('  ',1);assert new[name]==expected
    print('Archive member delta verified; running new public-refit replay and source rebuild.',flush=True)
    replay,replay_path,replay_log=execute(stage,['work/reproduce_final_revision.py','--refit-check-only'],'public_refit')
    assert replay['status']=='passed' and replay['exact_manuscript_bytes'] and replay['models_fitted_in_this_run']==0
    print('Public refit/source replay passed; testing raw restoration and clean preparation.',flush=True)
    preparation,preparation_path,preparation_log=execute(stage,['work/reproduce_final_revision.py','--prepare-refit-only','--data-dir',str(args.data_dir.resolve())],'refit_preparation')
    assert preparation['status']=='passed' and preparation['models_fitted_in_this_run']==0
    restored=preparation['raw_reference_restoration'];assert restored['exact_original_bytes'] and restored['rows']==89496
    prepared=preparation['fresh_preparation'];assert not prepared['old_hourly_cache_reads'] and not prepared['model_state_reads']
    assert len(prepared['jobs'])==64
    assert all(sha(stage/n)==h for n,h in new.items()),'Extracted archive member changed'
    result={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
            'validation_kind':'full passed baseline plus explicitly bounded fresh delta',
            'archive_sha256':sha(archive_path),'archive_bytes':archive_path.stat().st_size,'archive_files':len(new),
            'baseline_archive_sha256':BASELINE_SHA,'baseline_full_report_sha256':BASELINE_REPORT_SHA,
            'baseline_zip_bytes_independently_checked':baseline_bytes_checked,
            'unchanged_members':len(set(old)-changed),'changed_members':{n:{'before':old[n],'after':new[n]} for n in sorted(changed)},
            'added_members':{n:new[n] for n in sorted(added)},'removed_members':[],
            'all_prior_scientific_inputs_and_results_byte_identical':True,
            'fresh_public_refit_check':replay['refit_public_check'],
            'exact_current_manuscript_reconstruction':True,'optional_refit_prerequisite_tested':True,
            'raw_reference_restoration':restored,'fresh_preparation_series':len(prepared['jobs']),
            'fresh_preparation_old_cache_reads':False,'models_refitted_during_delta_validation':0,
            'new_reports':{'public_replay':replay_path,'preparation':preparation_path},
            'logs':[replay_log,preparation_log],
            'fresh_extract_directory':str(stage.relative_to(ROOT)),
            'script_sha256':sha(Path(__file__)),
            'scope':'The earlier complete fresh validation applies to byte-identical scientific inputs/results. This fresh delta runs the new public-refit checker, reconstructs the exact revised source, and tests raw restoration plus clean64-series preparation. It does not repeat unchanged full-period analyses or another model fit; completed fresh64-series fitting and independent full/public audit remain separately archived.'}
    target=ROOT/'outputs/supplement_delta_verification.json';target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'passed','archive_sha256':result['archive_sha256'],'changed_members':len(changed),'added_members':len(added),'unchanged_members':result['unchanged_members'],'report':str(target)},indent=2),flush=True)

if __name__=='__main__':main()
