"""Portable, isolated reproduction of the external fixed-deadline revision.

Default: small scientific checks, bundled literal-source verification,
independent replay of both periods and their headline tables, exact new TeX.
--small: small checks only; no dataset is staged or read.
--refit: fresh fitting/acquisition from bundled hourly references.
--raw --raw-archive ZIP --raw-csv CSV: rebuild those references from the
official full source first, then fresh fitting/acquisition. Raw inputs are
read-only; all generated files live in a new disposable workspace.

Unchanged historical results are carried forward by their separately
validated byte hashes; this command does not rerun the old full suite.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = Path('work/external_deadline')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def require(value, message):
    if not value:
        raise AssertionError(message)


def stage_inputs(destination, small):
    files = set()
    for folder in ('work', 'outputs'):
        files.update(p for p in (ROOT/folder).glob('*.py'))
    files.update((ROOT/'work/randomized_recovery_root').glob('*.py'))
    files.update((ROOT/EXTERNAL).glob('*.py'))
    for folder in ('acquisition','forecast','review','editorial','source'):
        files.update((ROOT/EXTERNAL/folder).glob('*.py'))
    if not small:
        source_manifest_path = ROOT/EXTERNAL/'source/source_package_manifest.json'
        source_manifest = read(source_manifest_path)
        require(source_manifest['status'] == 'passed','Bounded source package manifest did not pass')
        files.add(source_manifest_path)
        for item in source_manifest['files']:
            candidate = ROOT/item['path']
            require(sha(candidate) == item['sha256'],'Bounded source package file changed: '+item['path'])
            files.add(candidate)
        allowed_directories = {'acquisition','editorial','fitted','forecast','prior_release','review','reproduction','validation','test'}
        for path in (ROOT/EXTERNAL).rglob('*'):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT/EXTERNAL)
            if len(relative.parts) > 1 and relative.parts[0] not in allowed_directories:
                continue
            if any(part in {'__pycache__','raw','lcl_raw','7zip'} for part in relative.parts):
                continue
            if path.suffix.lower() in {'.py','.json','.jsonl','.csv','.gz','.npz','.txt','.tex','.md','.html'}:
                files.add(path)
        for name in ('revised_manuscript.tex','external_manuscript_reconstruction.json','external_release_manifest.json',
                     'requirements-study.txt','supplement_delta_verification.json',
                     'external_supplement_delta_verification.json'):
            path = ROOT/'outputs'/name
            if path.exists():
                files.add(path)
    copied = {}
    for path in sorted(files):
        if '__pycache__' in path.parts:
            continue
        relative = path.relative_to(ROOT)
        target = destination/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied[relative.as_posix()] = sha(path)
    (destination/'outputs').mkdir(exist_ok=True)
    return copied


def run(stage, steps, script, *arguments):
    sequence = len(steps)+1
    log = stage/'outputs'/f'external_step_{sequence:02d}_{Path(script).stem}.log'
    # Explicit sibling import path avoids the CPython Windows long-path trap.
    boot = ('import runpy,sys;from pathlib import Path;'
            'p=sys.argv[1];sys.argv=sys.argv[1:];'
            'sys.path.insert(0,str(Path(p).parent));runpy.run_path(p,run_name="__main__")')
    before = time.perf_counter()
    print('Running:', script, *map(str,arguments), flush=True)
    with log.open('w', encoding='utf-8') as output:
        result = subprocess.run([sys.executable,'-c',boot,str(stage/script),*map(str,arguments)],
                                cwd=stage,stdout=output,stderr=subprocess.STDOUT,text=True)
    record = dict(script=str(script), arguments=list(map(str,arguments)), returncode=result.returncode,
                  wall_seconds=time.perf_counter()-before, log=log.relative_to(stage).as_posix())
    steps.append(record)
    if result.returncode:
        print('\n'.join(log.read_text(encoding='utf-8',errors='replace').splitlines()[-45:]), flush=True)
        raise RuntimeError('Reproduction step failed; preserved log: '+str(log))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--small',action='store_true')
    modes.add_argument('--refit',action='store_true')
    modes.add_argument('--raw',action='store_true')
    parser.add_argument('--raw-archive',type=Path)
    parser.add_argument('--raw-csv',type=Path)
    args = parser.parse_args()
    if args.raw and not (args.raw_archive and args.raw_csv):
        parser.error('--raw requires --raw-archive and --raw-csv; see reproduction/README.txt')
    if not args.raw and (args.raw_archive or args.raw_csv):
        parser.error('Raw input paths require --raw')
    started = time.perf_counter()
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    stage = ROOT/'work'/('external_replay_'+tag)
    stage.mkdir(parents=True,exist_ok=False)
    copied = stage_inputs(stage,args.small)
    print('Isolated reproduction workspace:',stage,flush=True)
    steps, checks = [], {}
    run(stage,steps,EXTERNAL/'small_verify.py','--output','outputs/external_small_verification.json')
    checks['small'] = read(stage/'outputs/external_small_verification.json')
    require(checks['small']['status'] == 'passed','Small verification failed')
    run(stage,steps,EXTERNAL/'review/check_snapshot_copy.py')
    checks['snapshot_copy'] = read(stage/EXTERNAL/'review/snapshot_copy_check.json')
    require(checks['snapshot_copy']['status'] == 'passed','Multistage snapshot regression failed')
    fresh = args.refit or args.raw
    if not args.small:
        fit_script_hash = sha(stage/EXTERNAL/'forecast/forecast.py')
        require(read(stage/EXTERNAL/'fitted/prepared.json')['script_sha256'] == fit_script_hash,
                'Preparation code differs from distributed forecast implementation')
        require(read(stage/EXTERNAL/'fitted/fit_metadata.json')['script_sha256'] == fit_script_hash,
                'Fitting code differs from distributed forecast implementation')
        if args.raw:
            manifest = read(stage/EXTERNAL/'data/lcl/manifest.json')
            require(sha(args.raw_archive) == manifest['archive']['sha256'],'Official ZIP hash differs from frozen source')
            require(sha(args.raw_csv) == manifest['member']['sha256'],'Extracted official CSV hash differs from frozen source')
            old_hourly_hash = sha(stage/EXTERNAL/'data/lcl/hourly.csv')
            old_selected = read(stage/EXTERNAL/'data/lcl/selection.json')['selected_ids']
            run(stage,steps,EXTERNAL/'source/prepare_lcl.py','--archive',args.raw_archive.resolve(),'--csv',args.raw_csv.resolve())
            require(sha(stage/EXTERNAL/'data/lcl/hourly.csv') == old_hourly_hash,'Raw regeneration changed frozen hourly references')
            require(read(stage/EXTERNAL/'data/lcl/selection.json')['selected_ids'] == old_selected,'Raw source cohort changed')
            checks['raw_reconstruction'] = {'status':'passed','hourly_sha256':old_hourly_hash,'selected_ids':old_selected,
                                           'full_official_archive_reparsed':True}
        run(stage,steps,EXTERNAL/'source/verify_lcl_reference.py')
        checks['literal_source'] = read(stage/EXTERNAL/'source/lcl_reference_verification.json')
        require(checks['literal_source']['status'] == 'passed','Literal-source verification failed')
        if fresh:
            # Retain the shipped archive beside the new run, never overwrite it.
            for folder in ('fitted','validation','test'):
                current = stage/EXTERNAL/folder
                if current.exists():
                    current.rename(stage/EXTERNAL/(folder+'_distributed_reference'))
            config = read(stage/EXTERNAL/'fitted_distributed_reference/frozen_config.json')
            protocol = str(config['protocol_path']).replace('\\','/')
            if not protocol.startswith('work/'):
                require('/work/' in protocol,'Cannot rebase archived protocol path')
                protocol = 'work/'+protocol.rsplit('/work/',1)[1]
            config['protocol_path'] = str(stage/protocol)
            config_path = stage/EXTERNAL/'fresh_refit_config.json'
            config_path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
            run(stage,steps,EXTERNAL/'forecast/forecast.py','prepare','--hourly',EXTERNAL/'data/lcl/hourly.csv',
                '--config',EXTERNAL/'fresh_refit_config.json','--output-dir',EXTERNAL/'fitted')
            run(stage,steps,EXTERNAL/'forecast/forecast.py','fit','--prepared',EXTERNAL/'fitted')
            checks['fresh_fit'] = read(stage/EXTERNAL/'fitted/fit_metadata.json')
            require(checks['fresh_fit']['status'] == 'passed','Fresh fitting failed')
        for period in ('validation','test'):
            run_dir = EXTERNAL/period
            if fresh:
                run(stage,steps,EXTERNAL/'evaluate.py','--forecast-dir',EXTERNAL/'fitted','--period',period,'--output-dir',run_dir)
                run(stage,steps,EXTERNAL/'summarize.py','--run-dir',run_dir)
            run(stage,steps,EXTERNAL/'review/verify_external.py','--forecast-dir',EXTERNAL/'fitted','--run-dir',run_dir)
            checks[period] = read(stage/run_dir/'independent_verification.json')
            require(checks[period]['status'] == 'passed','Independent '+period+' verification failed')
        if not fresh:
            # Reports contain fresh execution timestamps. Preserve them in the
            # wrapper result, then restore archived bytes needed by the builder.
            for relative, original_hash in copied.items():
                target = stage/relative
                if not target.exists() or sha(target) != original_hash:
                    shutil.copy2(ROOT/relative,target)
            builder = Path('work/build_external_manuscript.py')
            require((stage/builder).is_file(),'Final manuscript builder is missing')
            expected = copied['outputs/revised_manuscript.tex']
            run(stage,steps,builder)
            actual = sha(stage/'outputs/revised_manuscript.tex')
            require(actual == expected,'Final manuscript bytes differ after reconstruction')
            checks['manuscript'] = read(stage/'outputs/external_manuscript_reconstruction.json')
            checks['exact_manuscript_sha256'] = actual
    for relative, original_hash in copied.items():
        require(sha(ROOT/relative) == original_hash,'Original release file changed: '+relative)
    mode = 'small' if args.small else 'raw_refit_and_acquisition' if args.raw else 'fresh_refit_and_acquisition' if args.refit else 'frozen_external_replay'
    report = dict(status='passed',completed_utc=datetime.now(timezone.utc).isoformat(),mode=mode,
        stage=str(stage),wall_seconds=time.perf_counter()-started,steps=steps,checks=checks,
        original_files_unchanged=True,staged_file_count=len(copied),script_sha256=sha(Path(__file__)),
        models_fitted=int(checks.get('fresh_fit',{}).get('model_fit_count',0)),
        exact_current_manuscript_rebuilt=not args.small and not fresh,
        historical_full_suite_reexecuted=False,
        scope='Fresh checks are explicitly listed. Unchanged historical evidence remains covered by its archived full-run report and byte-hash carry-forward. Raw mode reparses the pinned full official source; refit-only uses bundled references. Fresh-fit mode produces new outcomes without silently replacing distributed tables.')
    target = stage/'outputs/external_revision_reproduction.json'
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='passed',mode=mode,report=str(target),wall_seconds=report['wall_seconds']),indent=2),flush=True)


if __name__ == '__main__':
    main()
