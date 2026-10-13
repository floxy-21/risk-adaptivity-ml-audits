"""Execute the source/forecast/certificate/table chain in a new output tree.

Default external route is entirely offline. --cohort all regenerates the
original BLEM source route and needs its pinned cache, or downloads missing
public sources. No estimator is fitted. Original raw-dependent outputs remain
local and must not be redistributed as supplementary data.
"""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;JC=HERE.parent;BASE=JC.parent;ROOT=BASE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cohort',choices=['external','all'],default='external')
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--raw-dir',type=Path)
    p.add_argument('--raw-run',type=Path,help='Explicitly reuse a completed documented original-source run; its report and source chain are rechecked.')
    p.add_argument('--shared-run',type=Path,help='Explicitly reuse freshly generated shared plans, with source identities checked below.')
    p.add_argument('--precision-run',type=Path,help='Explicitly reuse generated challenger plans; exact source and certificate checks still execute.')
    a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();steps=[];env=os.environ.copy()
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:env.setdefault(key,'1')
    def run(script,*args):
        script=Path(script);log=out/f'{len(steps)+1:02d}_{script.stem}.log';t=time.perf_counter()
        argv=[sys.executable,str(script),*map(str,args)]
        with log.open('w',encoding='utf8') as f:r=subprocess.run(argv,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
        steps.append({'command':argv,'script_sha256':sha(script),'returncode':r.returncode,'log':str(log),'log_sha256':sha(log),'elapsed_seconds':time.perf_counter()-t})
        if r.returncode:raise RuntimeError(f'Failed: {log}')
    report={'status':'running','cohort':a.cohort,'steps':steps,'new_forecast_fits':0,'same_study_execution':True}
    try:
        run(HERE/'check_source_guards.py','--output',out/'source_guards.json')
        raw=None;original=[];answers=[]
        if a.cohort=='all':
            raw=(a.raw_run or out/'original_raw').resolve()
            if not a.raw_run:
                args=['--output-dir',raw]
                if a.raw_dir:args+=['--data-dir',a.raw_dir.resolve()]
                run(BASE/'counter_adaptive/reproduce_counter.py',*args)
            rawreport=json.loads((raw/'reproduction_report.json').read_text());assert rawreport['status']=='passed' and rawreport['panel']=='all'
            report['original_raw_report']={'path':str(raw/'reproduction_report.json'),'sha256':sha(raw/'reproduction_report.json'),'reused_completed_run':bool(a.raw_run),'recorded_elapsed_seconds':rawreport['elapsed_seconds']}
            original=['--original-geometry',raw/'results/geometry.json'];answers=['--original-answers',raw/'prepared/data_blem_hourly_endpoints.csv']
        sourceargs=['--cohort',a.cohort,'--output',out/'source_chain.json']
        if raw:sourceargs += ['--raw-dir',(a.raw_dir or raw/'raw').resolve(),*original,'--original-endpoints',raw/'prepared/data_blem_hourly_endpoints.csv']
        run(HERE/'check_source_chain.py',*sourceargs)
        shared=(a.shared_run or out/'shared').resolve()
        if not a.shared_run:run(JC/'empirical_shared_audit.py','--cohort',a.cohort,*original,*answers,'--output-dir',shared)
        shared_doc=json.loads((shared/'empirical_plans.json').read_text())
        for source in shared_doc['inputs'].values():
            path=Path(source['path']);path=path if path.is_absolute() else ROOT/path
            assert sha(path)==source['sha256']
        if raw:assert shared_doc['inputs']['original_0']['sha256']==sha(raw/'results/geometry.json')
        precision=(a.precision_run or out/'precision').resolve()
        if not a.precision_run:run(JC/'precision_batch.py','--cohort',a.cohort,'--plans',shared/'empirical_plans.json',*original,'--output-dir',precision)
        run(JC/'precision_batch_check.py','--directory',precision)
        run(JC/'precision_adaptive_link.py','--directory',precision,'--base-plans',shared/'empirical_plans.json')
        replay=out/'recorded_replay'
        run(JC/'empirical_precision_replay.py','--cohort',a.cohort,'--precision-plans',precision/'plans.json','--plans',shared/'empirical_plans.json','--ledger',shared/'empirical_cases.csv',*original,*answers,'--output-dir',replay)
        run(JC/'independent_precision_replay_check.py','--cohort',a.cohort,'--replay-dir',replay,'--output',replay/'independent_replay_check.json')
        run(HERE/'check_table_chain.py','--cohort',a.cohort,'--shared-dir',shared,'--precision-dir',precision,'--replay-dir',replay,'--output',out/'table_chain.json')
        report.update(status='PASS',source_chain_sha256=sha(out/'source_chain.json'),table_chain_sha256=sha(out/'table_chain.json'),
            complete_scope='Source identities and readings -> frozen forecast restoration/linkage -> all coefficients -> shared policies -> exact continuum certificates -> direct recorded outcomes -> complete-panel and matched-subset tables.',
            limitation='Frozen-predictor verification, not independent refitting, external human replication, native device calibration or proof of the universal theorem.',
            reused_generated_paths={'shared':str(shared) if a.shared_run else None,'precision':str(precision) if a.precision_run else None})
    except Exception as exc:report.update(status='FAIL',error=f'{type(exc).__name__}: {exc}');raise
    finally:
        report.update(elapsed_seconds=time.perf_counter()-start,runner_sha256=sha(Path(__file__)))
        (out/'chain_execution.json').write_text(json.dumps(report,indent=2)+'\n');print(str(out/'chain_execution.json'),flush=True)
if __name__=='__main__':main()
