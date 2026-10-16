"""Reproduce the gate, cost ledger, cached API checks, timing and loss scales offline."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys

HERE=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=HERE/'results');args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    commands=[['analyze.py','--out',str(out)],['check_saved.py','--results',str(out)],
              ['time_gate.py','--results',str(out)],
              ['check_tolerance_scale.py','--out',str(out/'tolerance_scale')]]
    for script,*arguments in commands:
        subprocess.run([sys.executable,str(HERE/script),*arguments],check=True)
    report={'status':'PASS','scope':__doc__,'network_requests':0,'steps':len(commands),
        'commands':commands,'result_hashes':{p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='run_report.json'}}
    (out/'run_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','steps':len(commands),'network_requests':0,'output':str(out)},indent=2))

if __name__=='__main__':main()
