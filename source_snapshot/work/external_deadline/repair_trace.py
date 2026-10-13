"""Repair observation-snapshot aliasing without reselecting or reevaluating a policy.

Only each stage's `after` field is changed. Original compressed traces, run
metadata, and the executed evaluator are preserved for independent comparison.
"""
from pathlib import Path
import argparse, copy, gzip, hashlib, json, math, shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def reconstruct(stage, totals):
    result=list(stage['before'])
    for i,v in zip(stage['batch'],stage['revealed']):
        assert result[i] is None
        result[i]=v
    for g,total in enumerate(totals):
        indices=list(range(6*g,6*g+6))
        missing=[i for i in indices if result[i] is None]
        residual=max(0.,float(total)-math.fsum(result[i] for i in indices if result[i] is not None))
        if len(missing)==1:result[missing[0]]=residual
        elif missing and residual==0:
            for i in missing:result[i]=0.
    return result

def repair(period):
    folder=HERE/period
    trace=folder/'trajectories.jsonl'
    old_gz=folder/'trajectories_before_trace_repair.jsonl.gz'
    old_result=folder/'run_result_before_trace_repair.json'
    report_path=folder/'trace_logging_repair.json'
    assert not report_path.exists(), 'Repair already recorded; do not overwrite provenance'
    original_hash=sha(trace)
    original=json.loads((folder/'run_result.json').read_text())
    assert original['outputs'][trace.name]==original_hash
    old_code=HERE/'evaluate_before_trace_alias_fix.py.txt'
    assert sha(old_code)==original['input_hashes']['work/external_deadline/evaluate.py']
    shutil.copyfile(folder/'run_result.json',old_result)
    with trace.open('rb') as src, old_gz.open('wb') as target:
        with gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as dst:
            shutil.copyfileobj(src,dst)
    untouched={p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.suffix in ['.csv','.json'] and p.name not in ['run_result.json',old_result.name,'independent_verification.json','trace_logging_repair.json']}
    temporary=folder/'trajectories_repaired.tmp'
    rows=stages=changed=0
    with trace.open(encoding='utf-8') as src,temporary.open('w',encoding='utf-8',newline='\n') as dst:
        for line in src:
            record=json.loads(line);before=copy.deepcopy(record)
            for policy in record['policies'].values():
                sequence=policy['stages']
                for n,stage in enumerate(sequence):
                    after=reconstruct(stage,record['totals'])
                    aliased=list(after)
                    if n+1<len(sequence):
                        successor=sequence[n+1]
                        assert after==successor['before'], (record['case_id'],n,'next before')
                        for i,v in zip(successor['batch'],successor['revealed']):aliased[i]=v
                    assert stage['after']==aliased,(record['case_id'],n,'alias signature')
                    changed+=stage['after']!=after
                    stage['after']=after;stages+=1
            # Establish that no scientific result or other logged field changed.
            normalized=copy.deepcopy(record)
            for name,policy in before['policies'].items():
                for n,stage in enumerate(policy['stages']):normalized['policies'][name]['stages'][n]['after']=stage['after']
            assert normalized==before
            dst.write(json.dumps(record,separators=(',',':'),allow_nan=False)+'\n');rows+=1
    temporary.replace(trace)
    assert untouched=={name:sha(folder/name) for name in untouched}
    report={'status':'repaired_logging_only','original_trajectories_gzip':old_gz.relative_to(ROOT).as_posix(),
            'original_trajectories_sha256':original_hash,'original_run_result':old_result.relative_to(ROOT).as_posix(),
            'original_run_result_sha256':sha(old_result),'executed_evaluator_path':old_code.relative_to(ROOT).as_posix(),
            'executed_evaluator_sha256':sha(old_code),'corrected_evaluator_sha256':sha(HERE/'evaluate.py'),
            'repaired_trace_sha256':sha(trace),'rows':rows,'stages':stages,'changed_after_snapshots':changed,
            'repair_script_sha256':sha(__file__),'unchanged_outcome_files':untouched,
            'scope':'Only saved after arrays reconstructed from before, recorded batch answers, and totals. No fits, selections, costs, bounds, decisions, or numerical summaries changed.'}
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    original['outputs'][trace.name]=sha(trace)
    for p in [old_gz,old_result,report_path]:original['outputs'][p.name]=sha(p)
    original['logging_correction']='trace_logging_repair.json'
    (folder/'run_result.json').write_text(json.dumps(original,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('period',choices=['validation','test']);args=parser.parse_args();repair(args.period)
