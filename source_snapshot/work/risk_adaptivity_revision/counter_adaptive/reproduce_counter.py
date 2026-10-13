"""Regenerate counter-dependent geometry/replay from pinned original downloads.

Run from the extracted supplement root:
  python work/risk_adaptivity_revision/counter_adaptive/reproduce_counter.py
Optional --data-dir supplies an existing raw-file cache. Missing sources are
downloaded by the pinned preparer; its three original SHA256 checks are mandatory.
No forecasting estimator is fitted. This creates a NEW output tree and never
overwrites archived geometry or manuscript results. Approximately31MB raw data
may be downloaded. The generated raw/geometry/trace files stay local.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,help='Pinned raw source cache; missing files are downloaded there.')
    parser.add_argument('--output-dir',type=Path,help='Must not already exist; default is a timestamped outputs directory.')
    parser.add_argument('--panel',choices=['pilot','continuation','all'],default='all')
    parser.add_argument('--reference-report',type=Path,default=HERE/'summary/report.json')
    args=parser.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=(args.output_dir or ROOT/'outputs'/f'counter_replay_{stamp}').resolve()
    out.mkdir(parents=True,exist_ok=False)
    data=(args.data_dir or out/'raw').resolve()
    prepared=out/'prepared'; results=out/'results';steps=[]
    manifest=ROOT/'outputs/review_frozen_forecasts.json'
    frozen=json.loads(manifest.read_text())
    assert sha(ROOT/'outputs/review_frozen_forecasts.csv')==frozen['output_sha256']
    environment=os.environ.copy()
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
        environment.setdefault(key,'1')
    def run(relative,*arguments):
        path=ROOT/relative;log=out/f'{len(steps)+1:02d}_{path.stem}.log'
        # Long-path-safe sibling imports, using the same entry behavior as the
        # existing supplement wrappers; never synthesize a shell command.
        bootstrap='import runpy,sys;from pathlib import Path;p=Path(sys.argv[1]);sys.argv=sys.argv[1:];sys.path.insert(0,str(p.parent));runpy.run_path(str(p),run_name="__main__")'
        start=time.perf_counter()
        with log.open('w',encoding='utf-8') as f:
            done=subprocess.run([sys.executable,'-c',bootstrap,str(path),*map(str,arguments)],cwd=ROOT,env=environment,stdout=f,stderr=subprocess.STDOUT)
        steps.append({'script':relative,'arguments':list(map(str,arguments)),'returncode':done.returncode,'elapsed_seconds':time.perf_counter()-start,'log':str(log)})
        if done.returncode:raise RuntimeError(f'Counter reproduction failed; inspect {log}')
    reference=json.loads(args.reference_report.read_text())
    reference_hash=sha(args.reference_report)
    started=time.perf_counter()
    report={'status':'running','scope':'Raw-source regeneration of the declared counter experiment, using frozen learned forecasts; no model refit.','output_dir':str(out),'panel':args.panel,'steps':steps}
    try:
        run('work/data_prepare_blem.py','--download','--data-dir',data,'--output-dir',prepared)
        run('work/risk_adaptivity_revision/counter_adaptive/data_audit/audit_counter_interface.py','--data-dir',data,'--output',out/'interface_verification.json')
        run('work/risk_adaptivity_revision/counter_adaptive/study.py','geometry','--panel',args.panel,'--output-dir',results,'--endpoints',prepared/'data_blem_hourly_endpoints.csv')
        geometry_hash=sha(results/'geometry.json')
        run('work/risk_adaptivity_revision/counter_adaptive/study.py','replay','--panel',args.panel,'--output-dir',results,'--data-dir',data)
        assert sha(results/'geometry.json')==geometry_hash
        replay=json.loads((results/'replay_verification.json').read_text())
        assert replay['status']=='PASS'
        run('work/risk_adaptivity_revision/counter_adaptive/summarize.py','--input-dirs',results,'--output-dir',out/'summary')
        run('work/risk_adaptivity_revision/counter_adaptive/math_review/check_saved_geometry.py',results/'geometry.json','--full','--output',out/'geometry_verification.json')
        independent=json.loads((out/'geometry_verification.json').read_text())
        assert independent['status']=='PASS' and independent['full']
        fresh=json.loads((out/'summary/report.json').read_text())
        comparison={'status':'not_run','reason':'The archived reference is the entire panel; this run selected one phase.'}
        if args.panel=='all':
            counts={'numeric_fields':0,'exact_fields':0,'maximum_absolute_numeric_difference':0.}
            def compare(left,right,path):
                if isinstance(left,dict):
                    assert isinstance(right,dict) and set(left)==set(right),path
                    for key in left:compare(left[key],right[key],path+'/'+key)
                elif isinstance(left,list):
                    assert isinstance(right,list) and len(left)==len(right),path
                    for i,(x,y) in enumerate(zip(left,right)):compare(x,y,path+'/'+str(i))
                elif isinstance(left,bool) or left is None or isinstance(left,str):
                    assert left==right,(path,left,right);counts['exact_fields']+=1
                elif isinstance(left,int):
                    assert left==right,(path,left,right);counts['exact_fields']+=1
                else:
                    error=abs(float(left)-float(right))
                    assert error<=1e-8,(path,left,right,error)
                    counts['numeric_fields']+=1
                    counts['maximum_absolute_numeric_difference']=max(counts['maximum_absolute_numeric_difference'],error)
            scientific_fields=['status','tasks','meters','model_pairs','primary_fraction','groups','replay','screening_criteria','screening_all_met','zero_width_cases','max_mean_optimal_face_residual']
            for field in scientific_fields:compare(reference[field],fresh[field],field)
            assert sha(args.reference_report)==reference_hash
            comparison={'status':'passed','reference_sha256':reference_hash,'fields':scientific_fields,'absolute_numeric_tolerance':1e-8,**counts,
                        'excluded_fields':'Source paths, phase-file partitioning, geometry hashes and measured runtimes; all declared counts, group counts, policy metrics and criteria are compared.'}
            run('work/risk_adaptivity_revision/counter_adaptive/feedback_triage/analyze.py','--geometry',results/'geometry.json','--replay',results/'replay_cases.csv','--output-dir',out/'feedback_triage')
            run('work/risk_adaptivity_revision/counter_adaptive/feedback_triage/verify_bundled.py','--input-dir',out/'feedback_triage','--output',out/'feedback_triage_verification.json')
            triage=json.loads((out/'feedback_triage/report.json').read_text())
            assert triage['status']=='PASS' and triage['counts']=={'batch_suffices':4371,'feedback_required':290,'adaptive_not_guaranteed':253}
            run('work/risk_adaptivity_revision/counter_adaptive/reviewer_diagnostics/analyze.py','--directories',results,'--data-dir',data,'--output-dir',out/'reviewer_diagnostics')
            report['feedback_triage']={'status':'PASS','classification_counts':triage['counts'],'scope':'Post-analysis fixed-threshold diagnostic; exact-rational geometry before recorded replay joins.'}
        report.update(status='passed',geometry_sha256=geometry_hash,interface=json.loads((out/'interface_verification.json').read_text()),replay=replay,
                      independent_geometry={k:v for k,v in independent.items() if k!='primary_exact_witnesses'},scientific_reference_comparison=comparison,
                      source_sha256={'study.py':sha(HERE/'study.py'),'protocol.txt':sha(HERE/'protocol.txt'),'public_forecasts':frozen['output_sha256']},
                      interpretation='A fresh execution. Compare counts, declared numerical tolerances and summaries with archived aggregate evidence; differing runtime or alternative optimal LP witnesses need not be errors. This wrapper does not claim independently implemented training or formally rounded certificates.')
    except Exception as exc:
        report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        report['elapsed_seconds']=time.perf_counter()-started
        (out/'reproduction_report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(str(out/'reproduction_report.json'),flush=True)


if __name__=='__main__':main()
