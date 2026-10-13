"""Final isolated reproduction entry point, preserving every frozen report.

Default: run the earlier complete analysis replay, then independently compare
the distributed fresh-refit rows and rebuild the exact current manuscript.
--refit-check-only omits the earlier analysis replay; it is used only by the
declared archive-delta audit, which separately pins the passed baseline.
--fresh-refit restores the omitted original reference archive from pinned raw
sources, reparses the raw data and executes the unchanged 64-series trainer.
--prepare-refit-only tests that regeneration prerequisite without fitting.
Use the pinned outputs/requirements-study.txt environment. All writes occur
inside a new work/final_revision_reproduction_* directory.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import shutil
import time
from reproduce_review_revision import stage_sources, reconstruct_raw, run_script, sha
from revision_extension_inputs import REFIT_DIR, validate_extension_inputs

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--refit-check-only',action='store_true')
    mode.add_argument('--fresh-refit',action='store_true')
    mode.add_argument('--prepare-refit-only',action='store_true')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'work')
    args=parser.parse_args()
    started=time.perf_counter()
    validate_extension_inputs(ROOT)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    stage=ROOT/'work'/('final_revision_reproduction_'+stamp)
    stage.mkdir(parents=True,exist_ok=False)
    print('Isolated final reproduction workspace:',stage,flush=True)
    copied=stage_sources(ROOT,stage)
    steps=[];baseline=None;public=None;full=None;restoration=None;prepared=None
    refitting=args.fresh_refit or args.prepare_refit_only
    if refitting:
        # Keep the entire shipped evidence beside the new execution. The
        # unchanged driver requires a clean directory and never overwrites it.
        archived=stage/'work/fresh_refit_archived_reference'
        (stage/REFIT_DIR).rename(archived)
        fresh=stage/REFIT_DIR;fresh.mkdir()
        for name in ['refit.py','protocol.txt','comparison_protocol.txt','verify_refit.py','export_public.py']:
            shutil.copy2(archived/name,fresh/name)
        # The historical raw-reconstruction report is a pinned refit input.
        # Save the NEW restoration result separately, then restore those
        # historical report bytes. This does not reuse hourly data for fitting:
        # refit.py prepare reparses all five raw sources into its own directory.
        report_path=stage/'outputs/review_raw_reconstruction.json'
        pinned_record=report_path.read_bytes()
        restoration=reconstruct_raw(stage,args.data_dir.resolve())
        (stage/'outputs/fresh_refit_reference_restoration.json').write_text(json.dumps(restoration,indent=2)+'\n')
        report_path.write_bytes(pinned_record)
        assert sha(report_path)==json.loads((archived/'prepared.json').read_text())['source_hashes']['outputs/review_raw_reconstruction.json']
        steps.append(run_script(stage,REFIT_DIR+'/refit.py',('prepare',)))
        prepared=json.loads((fresh/'prepared.json').read_text())
        assert prepared['source_hashes']==json.loads((archived/'prepared.json').read_text())['source_hashes']
        if args.fresh_refit:
            steps.append(run_script(stage,REFIT_DIR+'/refit.py',('fit',)))
            steps.append(run_script(stage,REFIT_DIR+'/verify_refit.py'))
            full=json.loads((fresh/'independent_verification.json').read_text())
            assert full['status']=='passed' and full['rows_compared']==166536
            steps.append(run_script(stage,REFIT_DIR+'/export_public.py'))
            steps.append(run_script(stage,REFIT_DIR+'/verify_refit.py',('--public',)))
            public=json.loads((fresh/'independent_verification_public.json').read_text())
    else:
        if not args.refit_check_only:
            steps.append(run_script(stage,'work/reproduce_review_revision.py'))
            candidates=list((stage/'work').glob('review_revision_reproduction_*/outputs/review_revision_reproduction.json'))
            assert len(candidates)==1
            baseline=json.loads(candidates[0].read_text())
            assert baseline['status']=='passed' and baseline['exact_manuscript_bytes']
        # Only the disposable copy is updated by this checker.
        steps.append(run_script(stage,REFIT_DIR+'/verify_refit.py',('--public',)))
        public=json.loads((stage/REFIT_DIR/'independent_verification_public.json').read_text())
        # Restore frozen reports before manuscript composition, whose input
        # manifests intentionally pin their original bytes/timestamps.
        for name in ['independent_verification_public.json','independent_metrics_public.csv']:
            shutil.copy2(ROOT/REFIT_DIR/name,stage/REFIT_DIR/name)
        steps.append(run_script(stage,'work/compose_final_sections.py'))
        steps.append(run_script(stage,'work/build_final_manuscript.py'))
        expected=json.loads((stage/'outputs/manuscript_reconstruction_check.json').read_text())['source_hashes']['outputs/revised_manuscript.tex']
        assert sha(stage/'outputs/revised_manuscript.tex')==expected
    if public:
        assert public['status']=='passed'
        assert (public['rows_compared'],public['series_compared'],public['forecast_values_compared'])==(159984,61,639936)
        assert all(v['outside_tolerance']==0 for v in public['per_model_discrepancies'].values())
        # Archived replay reproduces the already observed exact agreement.
        # A new fit is judged by the independently enforced frozen tolerances;
        # valid small numerical changes must not be rejected by this wrapper.
        if not args.fresh_refit:
            assert all(v['max_absolute_error']==0 for v in public['per_model_discrepancies'].values())
    for relative,expected in copied.items():
        assert sha(ROOT/relative)==expected,'Original input changed: '+relative
    result={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
            'mode':'fresh_refit' if args.fresh_refit else 'refit_preparation_only' if args.prepare_refit_only else 'new_refit_check_only' if args.refit_check_only else 'complete_distributed_verification',
            'wall_seconds':time.perf_counter()-started,'original_files_unchanged':True,
            'script_sha256':sha(Path(__file__)),'stage':str(stage),'steps':steps,
            'baseline_replay':baseline,'refit_public_check':public,'refit_full_check':full,
            'raw_reference_restoration':restoration,'fresh_preparation':prepared,
            'exact_manuscript_bytes':True if not refitting else None,
            'models_fitted_in_this_run':192 if args.fresh_refit else 0,
            'scope':'Public replay checks61 UCI series plus64-series metadata; full64 target/feature checks require optional raw reconstruction and fresh fitting. Preparation-only does not fit. Previously archived scientific results and reports remain unchanged.'}
    target=stage/'outputs/final_revision_reproduction.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'passed','mode':result['mode'],'stage':str(stage),'report':str(target),'wall_seconds':result['wall_seconds']},indent=2),flush=True)

if __name__=='__main__':main()
