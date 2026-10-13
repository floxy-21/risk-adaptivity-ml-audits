"""Export only derived provenance records; never copy original raw geometry."""
import argparse,hashlib,json,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;JC=HERE.parent;BASE=JC.parent;ROOT=BASE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--chain-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,default=HERE/'executed');a=p.parse_args()
    chain=json.loads((a.chain_dir/'chain_execution.json').read_text());assert chain['status']=='PASS' and chain['cohort']=='all'
    out=a.output_dir;out.mkdir(parents=True,exist_ok=True)
    for name in ['source_chain.json','table_chain.json','source_guards.json','chain_execution.json']:
        shutil.copyfile(a.chain_dir/name,out/name)
    rawpath=Path(chain['original_raw_report']['path']);assert sha(rawpath)==chain['original_raw_report']['sha256'];raw=json.loads(rawpath.read_text())
    allowed=['status','scope','panel','steps','scientific_reference_comparison','source_sha256','interpretation','elapsed_seconds']
    derived={k:raw[k] for k in allowed};derived['original_full_report_sha256']=sha(rawpath)
    derived['source_version']='QuantLet/BLEM commit 756b2c1265f964b70f72625a95d98413cdfb78bd'
    (out/'original_raw_execution.json').write_text(json.dumps(derived,indent=2)+'\n')
    generated={}
    for label,path in chain['reused_generated_paths'].items():
        if path:
            directory=Path(path);name='empirical_report.json' if label=='shared' else 'report.json'
            report=json.loads((directory/name).read_text());generated[label]={'report_sha256':sha(directory/name),
                'source_report':str(directory/name),'elapsed_seconds':report['elapsed_seconds'],'status':report['status'],
                'reused_in_final_wrapper':'Freshly generated earlier in the same source-to-table execution; recorded explicitly.'}
    manifest={'status':'PASS','date':'2026-10-13','files':{p.name:sha(p) for p in sorted(out.glob('*.json')) if p.name!='record_manifest.json'},
        'preceding_fresh_generators':generated,'scope':'Derived counts, IDs, hashes and execution records only; no raw BLEM counters, original geometry, forecast coefficients or query answers are copied.',
        'script_sha256':sha(Path(__file__))}
    (out/'record_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
