"""Demonstrate that changed source bytes fail the actual input identity gates."""
import argparse,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
from check_source_chain import require_hash, EXTERNAL_FORECAST
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1];ROOT=BASE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();checks=[]
    with tempfile.TemporaryDirectory(prefix='audit_source_guard_') as tmp:
        tmp=Path(tmp);raw=tmp/'raw';raw.mkdir()
        (raw/'data_blem_consumer-00000001.csv').write_text('changed source bytes\n')
        script=ROOT/'work/data_prepare_blem.py'
        result=subprocess.run([sys.executable,str(script),'--data-dir',str(raw),'--output-dir',str(tmp/'prepared')],cwd=ROOT,capture_output=True,text=True)
        assert result.returncode!=0 and 'Checksum mismatch' in result.stderr
        checks.append({'guard':'Pinned original raw-source bytes','script_sha256':sha(script),'exit_code':result.returncode,'expected_message':'Checksum mismatch','passed':True})
        changed=tmp/'changed_forecasts.csv';changed.write_text('changed forecast bytes\n')
        endpoints=tmp/'endpoints.csv';endpoints.write_text('sentinel\n')
        metadata=tmp/'metadata.json';metadata.write_text('{}\n')
        script=BASE/'counter_adaptive/study.py'
        result=subprocess.run([sys.executable,str(script),'geometry','--panel','pilot','--forecasts',str(changed),
            '--endpoints',str(endpoints),'--metadata',str(metadata),'--output-dir',str(tmp/'geometry')],cwd=ROOT,capture_output=True,text=True)
        assert result.returncode!=0 and 'Frozen forecast export changed' in result.stderr, result.stderr
        checks.append({'guard':'Pinned original frozen-forecast bytes','script_sha256':sha(script),'exit_code':result.returncode,'expected_message':'Frozen forecast export changed','passed':True})
        rejected=False
        try:require_hash(changed,EXTERNAL_FORECAST)
        except ValueError as exc:rejected='Pinned source mismatch' in str(exc)
        assert rejected
        checks.append({'guard':'External frozen-forecast gate in source-chain checker','script_sha256':sha(HERE/'check_source_chain.py'),'passed':True,'expected_message':'Pinned source mismatch'})
    report={'status':'PASS','checks':checks,'mutations':'Temporary sentinel files only; no archived source or scientific artifact changed.',
            'source_sha256':sha(Path(__file__)),'scope':'Fail-closed checksum regression, not a new scientific experiment.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
