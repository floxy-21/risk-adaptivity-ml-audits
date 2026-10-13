"""One-command reproduction of the corrected review analyses.

Default (no downloads/refits): verify the distributed period traces and interval
aggregates, every randomized public case, the hard-budget policy sampler and
NOAA excerpt arithmetic, independent tie/holdout-policy replay and archived scaling
consistency, then reconstruct the same TeX. New checks run on
separate copies so frozen reports used by the manuscript remain unchanged.
  python work/reproduce_review_revision.py

Optional raw-data analysis (downloads up to about 314 MB if not locally cached):
  python work/reproduce_review_revision.py --raw
  python work/reproduce_review_revision.py --raw --data-dir /path/to/raw/cache

Optional fresh scaling measurements (archived measurements remain unchanged):
  python work/reproduce_review_revision.py --rerun-scaling

Both modes operate in a NEW isolated work directory. Original manuscript,
reports, scripts and data are never overwritten. Use the pinned study Python
and packages in outputs/requirements-study.txt. No mode fits a forecasting model.
--raw restores the exact original mixed prediction CSV from the additive,
lossless export plus the pinned raw targets, checks its original SHA256, and
reruns the two new analyses before verification and manuscript reconstruction.
--raw --reconstruct-only tests the raw reconstruction/hash without analyses.
This command generates TeX only; it neither compiles a PDF nor submits anything.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from revision_extension_inputs import (extension_paths, validate_extension_inputs,
                                      RANDOM_DIR, COMPACT_DIR, NOAA_DIR,
                                      TIE_DIR, SCALING_DIR, HOLDOUT_DIR)

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def stage_sources(source, stage):
    """Copy flat inputs plus explicit nested extensions; never copy caches."""
    copied = {}
    for folder in ('work','outputs'):
        destination = stage/folder
        destination.mkdir(parents=True,exist_ok=False)
        for p in sorted((source/folder).iterdir()):
            if not p.is_file():
                continue
            allowed = p.suffix in ('.py','.json','.csv','.txt','.tex') or p.name.endswith('.csv.gz')
            if not allowed or p.name=='study_predictions.csv':
                continue
            if folder=='work' and p.name.startswith(('data_','study_predictions')) and p.name!='data_prepare_blem.py':
                continue
            # Internal reviews, old cover letters and private correspondence
            # have no role in reconstruction and are not copied.
            if folder=='outputs' and p.name.startswith(('peer_review_','cover_','submission_')):
                continue
            shutil.copy2(p,destination/p.name)
            copied[f'{folder}/{p.name}'] = sha(p)
    for relative in extension_paths(source):
        destination=stage/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/relative,destination)
        copied[relative]=sha(source/relative)
    return copied


def run_script(stage, relative, arguments=()):
    log = stage/'work'/('reproduction_'+Path(relative).stem+'.log')
    print('Running',relative,flush=True)
    before = time.perf_counter()
    # On Windows, CPython can leave sys.path[0] empty when an absolute script
    # path exceeds MAX_PATH, even though the script itself opens successfully.
    # Bootstrap its sibling-import directory explicitly while preserving the
    # intended workspace cwd and normal script argv/__main__ semantics.
    bootstrap=("import runpy,sys;from pathlib import Path;"
               "script=sys.argv[1];sys.argv=sys.argv[1:];"
               "sys.path.insert(0,str(Path(script).parent));"
               "runpy.run_path(script,run_name='__main__')")
    with log.open('w',encoding='utf-8') as stream:
        completed = subprocess.run([sys.executable,'-c',bootstrap,str(stage/relative),*map(str,arguments)],
                                   cwd=stage,stdout=stream,stderr=subprocess.STDOUT,text=True)
    if completed.returncode:
        tail = log.read_text(encoding='utf-8',errors='replace').splitlines()[-35:]
        print('\n'.join(tail),flush=True)
        raise RuntimeError(f'{relative} failed; full diagnostic log: {log}')
    return {'script':relative,'wall_seconds':time.perf_counter()-before,
            'log':str(log.relative_to(stage)),'returncode':completed.returncode}


def immutable_raw_copy(source, destination, expected):
    """A verified raw file is immutable; link if possible, else copy."""
    if sha(source)!=expected:
        raise ValueError('Raw checksum mismatch: '+str(source))
    if destination.exists():
        if sha(destination)!=expected:
            raise ValueError('Unexpected staged raw file: '+str(destination))
        return
    try:
        os.link(source,destination)
    except OSError:
        shutil.copy2(source,destination)


def verify_new_extensions(stage, rerun_scaling=False):
    """Run extension checks in a sibling scientific tree, preserving reports."""
    validate_extension_inputs(stage)
    check_root=stage/'work/extension_verification'
    check_root.mkdir(parents=True,exist_ok=False)
    paths=(*extension_paths(stage),'outputs/review_frozen_forecasts.csv',
           'outputs/study_holdout_consumers_predictions.csv',
           'outputs/study_recovery.py','outputs/study_archive_access.py',
           'outputs/study_period_archive.py','outputs/run_energy_rank_study.py')
    preserved={relative:sha(stage/relative) for relative in paths}
    for relative in paths:
        destination=check_root/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(stage/relative,destination)
    steps=[]
    for script,arguments in [('work/verify_randomized_revision.py',()),
                             (COMPACT_DIR+'/verify_compact_policy.py',()),
                             (NOAA_DIR+'/reproduce_extracted_panel.py',()),
                             (TIE_DIR+'/verify_ties.py',()),
                             (HOLDOUT_DIR+'/verify_holdout.py',()),
                             (SCALING_DIR+'/verify_scaling.py',('--write-report','--rerun') if rerun_scaling else ('--write-report',))]:
        step=run_script(check_root,script,arguments)
        step['verification_workspace']=str(check_root.relative_to(stage))
        steps.append(step)
    reports={label:json.loads((check_root/relative).read_text(encoding='utf-8'))
             for label,relative in [('randomized',RANDOM_DIR+'/independent_verification.json'),
                                    ('compact_policy',COMPACT_DIR+'/policy_verification.json'),
                                    ('noaa',NOAA_DIR+'/lightweight_reproduction.json'),
                                    ('tie_policies',TIE_DIR+'/independent_verification.json'),
                                    ('randomized_holdout',HOLDOUT_DIR+'/independent_verification.json'),
                                    ('scaling',SCALING_DIR+'/archival_verification.json')]}
    for report in reports.values():assert report['status'].lower() in ('passed','pass')
    assert reports['randomized']['cases']==20736
    assert reports['randomized']['compact_versus_finite_game_checks']==1074
    assert reports['compact_policy']['cases']==48
    assert reports['noaa']['days']==52
    assert reports['tie_policies']['original_cases_retained']==20736
    assert reports['tie_policies']['secondary_optimality_checks']==2148
    assert reports['tie_policies']['positive_support_checks']==4693
    assert reports['randomized_holdout']['cases']==19260
    assert reports['randomized_holdout']['positive_probability_batches']==3958
    assert reports['scaling']['compact_cases']==28
    assert reports['scaling']['finite_comparisons']==12
    for relative,expected in preserved.items():
        assert sha(stage/relative)==expected,'Archived generation input overwritten: '+relative
    return {'status':'passed','stage':str(check_root.relative_to(stage)),
            'fresh_scaling_measurements_requested':rerun_scaling,
            'archived_generation_inputs_unchanged':True,'steps':steps,'reports':reports}


def reconstruct_raw(stage, data_dir):
    """Rebuild omitted target values through the pinned original loader path."""
    import numpy as np
    import pandas as pd
    sys.path.insert(0,str(stage/'work'))
    sys.path.insert(0,str(stage/'outputs'))
    # Imports are from the isolated copies. Their source files remain unchanged.
    downloader = importlib.import_module('download_study_data')
    prepare_blem = importlib.import_module('data_prepare_blem')
    study = importlib.import_module('run_energy_rank_study')
    assert study.WORK.resolve()==(stage/'work').resolve()
    assert Path(downloader.__file__).resolve()==(stage/'work/download_study_data.py').resolve()
    assert Path(prepare_blem.__file__).resolve()==(stage/'work/data_prepare_blem.py').resolve()
    frozen = json.loads((stage/'outputs/review_frozen_forecasts.json').read_text(encoding='utf-8'))
    table = stage/'outputs/review_frozen_forecasts.csv'
    assert sha(table)==frozen['output_sha256']
    assert sha(stage/'outputs/export_review_frozen_forecasts.py')==frozen['script_sha256']
    assert sha(stage/'outputs/study_summary.json')==frozen['study_summary_sha256']
    raw_hashes = {}
    for record in downloader.SOURCES:
        filename = record['destination']
        cached = data_dir/filename
        target = stage/'work'/filename
        if cached.exists():
            immutable_raw_copy(cached,target,record['text_sha256'])
        else:
            archive = data_dir/record['archive']
            if archive.exists():
                immutable_raw_copy(archive,stage/'work'/record['archive'],record['archive_sha256'])
            downloader.fetch_uci(record,stage/'work')
        downloader.require_hash(target,record['text_sha256'])
        raw_hashes[filename] = sha(target)
    for meter, expected in prepare_blem.SHA256.items():
        name = f'data_blem_{meter}.csv'
        cached = data_dir/name
        if cached.exists():
            immutable_raw_copy(cached,stage/'work'/name,expected)
    prepare_blem.prepare(stage/'work',stage/'work',download=True)
    for meter, expected in prepare_blem.SHA256.items():
        name = f'data_blem_{meter}.csv'
        assert sha(stage/'work'/name)==expected
        raw_hashes[name]=expected
    print('Rebuilding hourly targets using original loaders; no models are fitted.',flush=True)
    household, portugal = study.load_household(),study.load_portugal()
    # Original study loaded this generated hourly CSV with default pandas
    # parsing before writing the target/persistence strings to its archive.
    blem = pd.read_csv(stage/'work/data_blem_hourly.csv',index_col=0,parse_dates=True)
    output = stage/'outputs/study_predictions.csv'
    row_count = omitted = uci_target_checks = uci_daily_checks = 0
    with table.open(newline='',encoding='utf-8') as src, output.open('w',newline='',encoding='utf-8') as dst:
        reader,writer = csv.reader(src),csv.writer(dst)
        header = next(reader)
        assert header==['cohort','meter','timestamp','truth_kwh','daily','ridge','hist_gradient_boosting','mlp']
        writer.writerow(header)
        for row in reader:
            cohort,meter,timestamp = row[:3]
            stamp = pd.Timestamp(timestamp)
            series = household if cohort=='household' else portugal[meter] if cohort=='portugal' else blem[meter]
            target = float(series.loc[stamp])
            previous = float(series.loc[stamp-pd.Timedelta(hours=24)])
            assert np.isfinite(target) and np.isfinite(previous) and target>=0 and previous>=0
            if cohort=='blem_counters':
                assert row[3]==row[4]==''
                row[3],row[4] = str(target),str(previous)
                omitted += 1
            else:
                # Retain the original text; verify every included UCI target
                # and persistence value independently against pinned raw inputs.
                assert float(row[3])==target,(cohort,meter,timestamp,'target')
                assert float(row[4])==previous,(cohort,meter,timestamp,'daily')
                uci_target_checks += 1
                uci_daily_checks += 1
            writer.writerow(row)
            row_count += 1
    rebuilt_hash = sha(output)
    if rebuilt_hash!=frozen['original_predictions_sha256']:
        raise AssertionError('Raw reconstruction did not reproduce the original prediction CSV byte hash. '
                             'Do not bypass this check: use the pinned study runtime/package versions. '
                             f'Expected {frozen["original_predictions_sha256"]}; got {rebuilt_hash}.')
    assert row_count==frozen['rows'] and omitted==frozen['omitted_blem_target_and_daily_rows']
    result = {'status':'passed','rows':row_count,'reconstructed_blem_rows':omitted,
              'uci_raw_target_checks':uci_target_checks,'uci_raw_persistence_checks':uci_daily_checks,
              'original_predictions_sha256':frozen['original_predictions_sha256'],
              'reconstructed_predictions_sha256':rebuilt_hash,'exact_original_bytes':True,
              'raw_source_hashes':raw_hashes,'lossless_export_sha256':sha(table),
              'model_refitting':False,'older_lossy_export_used':False,
              'scope':'The new export preserves original fitted-forecast strings. All UCI targets/persistence are checked against pinned raw loaders; BLEM targets/persistence are rebuilt from original counters and original hourly CSV parsing. This restores the exact original evaluation archive, not independently trained models.'}
    (stage/'outputs/review_raw_reconstruction.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Exact original prediction archive restored:',rebuilt_hash,flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--raw',action='store_true',help='Restore raw targets and rerun the corrected period and interval analyses')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'work',help='Read-only cache of pinned raw source files; missing data are downloaded only into the new stage')
    parser.add_argument('--reconstruct-only',action='store_true',help='With --raw, test exact input reconstruction and stop before analyses')
    parser.add_argument('--rerun-scaling',action='store_true',help='Repeat the frozen scaling measurements in an isolated workspace; default only verifies the archived measurements')
    args = parser.parse_args()
    if args.reconstruct_only and not args.raw:
        parser.error('--reconstruct-only requires --raw')
    if args.reconstruct_only and args.rerun_scaling:
        parser.error('--rerun-scaling cannot be combined with --reconstruct-only')
    required = ['outputs/review_frozen_forecasts.csv',
                'outputs/review_frozen_forecasts.json','outputs/requirements-study.txt']
    if not (ROOT/'outputs/revised_manuscript.tex').is_file():
        required.append('outputs/manuscript_reconstruction_check.json')
    if not args.reconstruct_only:
        required += ['outputs/study_period_archive.json','outputs/study_interval_trace_recovery.json',
                     'work/verify_period_archive.py','work/verify_interval_trace.py',
                     'work/compose_final_sections.py','work/build_final_manuscript.py']
    for relative in required:
        if not (ROOT/relative).is_file():
            raise FileNotFoundError('Required distributed file missing: '+relative)
    started = time.perf_counter()
    original_prediction_path = ROOT/'outputs/study_predictions.csv'
    original_prediction_hash = sha(original_prediction_path) if original_prediction_path.is_file() else None
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    stage = (ROOT/'work'/('review_revision_reproduction_'+stamp)).resolve()
    if not stage.is_relative_to((ROOT/'work').resolve()):
        raise ValueError('Invalid staging directory')
    stage.mkdir(parents=True,exist_ok=False)
    print('Isolated reproduction workspace:',stage,flush=True)
    copied = stage_sources(ROOT,stage)
    if 'outputs/revised_manuscript.tex' in copied:
        original_manuscript_hash = copied['outputs/revised_manuscript.tex']
    else:
        reconstruction_record = json.loads((stage/'outputs/manuscript_reconstruction_check.json').read_text(encoding='utf-8'))
        assert reconstruction_record['status']=='passed'
        original_manuscript_hash = reconstruction_record['source_hashes']['outputs/revised_manuscript.tex']
    steps = []
    extension_checks = None
    raw = reconstruct_raw(stage,args.data_dir.resolve()) if args.raw else None
    if not args.reconstruct_only:
        if args.raw:
            steps.append(run_script(stage,'outputs/study_period_archive.py'))
            steps.append(run_script(stage,'outputs/study_interval_trace_recovery.py'))
        steps.append(run_script(stage,'work/verify_period_archive.py'))
        steps.append(run_script(stage,'work/verify_interval_trace.py'))
        extension_checks=verify_new_extensions(stage,args.rerun_scaling)
        steps.append(run_script(stage,'work/compose_final_sections.py'))
        steps.append(run_script(stage,'work/build_final_manuscript.py'))
        manuscript_hash = sha(stage/'outputs/revised_manuscript.tex')
        if manuscript_hash!=original_manuscript_hash:
            raise AssertionError('Reconstructed manuscript differs from distributed manuscript. '
                                 'The differing stage is retained; no original file was overwritten.')
    else:
        manuscript_hash = None
    # The source tree is read-only throughout this program. Check the scientifically
    # important inputs, not unrelated live reports another analyst may be writing.
    preserved = ['outputs/revised_manuscript.tex','outputs/study_summary.json',
                 'outputs/review_frozen_forecasts.csv','outputs/review_frozen_forecasts.json',
                 'outputs/run_energy_rank_study.py','outputs/study_recovery.py',
                 'outputs/interval_total_recovery.py']
    for relative in preserved:
        if relative=='outputs/revised_manuscript.tex' and relative not in copied:
            continue
        assert sha(ROOT/relative)==copied[relative],'Original changed during reproduction: '+relative
    for relative in extension_paths(ROOT):
        assert sha(ROOT/relative)==copied[relative],'Original extension changed: '+relative
    if original_prediction_hash is not None:
        assert sha(original_prediction_path)==original_prediction_hash,'Original mixed target archive changed'
    if raw is not None:
        raw.update(completed_utc=datetime.now(timezone.utc).isoformat(),
                   runner_sha256=sha(Path(__file__)),
                   original_source_files_unchanged=True,
                   original_mixed_archive_present=original_prediction_hash is not None,
                   original_mixed_archive_sha256=original_prediction_hash,
                   executed_mode='raw_reconstruction_only' if args.reconstruct_only else 'raw_analysis',
                   full_corrected_analysis_rerun=not args.reconstruct_only)
        (stage/'outputs/review_raw_reconstruction.json').write_text(json.dumps(raw,indent=2)+'\n',encoding='utf-8')
    result = {'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
              'mode':'raw_reconstruction_only' if args.reconstruct_only else 'raw_analysis' if args.raw else 'distributed_verification',
              'wall_seconds':time.perf_counter()-started,'model_refitting':False,
              'original_files_unchanged':True,'raw_reconstruction':raw,'steps':steps,
              'extension_checks':extension_checks,
              'original_manuscript_sha256':original_manuscript_hash,'reconstructed_manuscript_sha256':manuscript_hash,
              'exact_manuscript_bytes':manuscript_hash==original_manuscript_hash if manuscript_hash else None,
              'script_sha256':sha(Path(__file__)),'stage':str(stage),
              'scope':'Default verifies distributed period traces/interval aggregates, all randomized public cases, compact policy compilation, NOAA decoded excerpts, independent tie/holdout-policy replay and archived scaling consistency, then rebuilds TeX. Extension checks use separate copies preserving archived reports. It is not fresh NOAA GRIB/raw-source decoding or fresh scaling measurement. --rerun-scaling additionally repeats the frozen scaling measurements in isolation. --raw additionally restores original energy targets without refitting and runs both corrected energy analyses. --reconstruct-only stops after exact raw-input reconstruction. No PDF compilation or journal submission.'}
    target = stage/'outputs/review_revision_reproduction.json'
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'passed','mode':result['mode'],'wall_seconds':result['wall_seconds'],
                      'exact_manuscript_bytes':result['exact_manuscript_bytes'],'stage':str(stage),'report':str(target)},indent=2),flush=True)


if __name__=='__main__':
    main()
