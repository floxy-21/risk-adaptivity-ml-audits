"""Small scientific verification route, independent of external raw downloads."""
from pathlib import Path
from datetime import datetime,timezone
import argparse, hashlib, json, subprocess, sys
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from evaluate import trajectory,closure,RevealOracle,POLICIES

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path);args=ap.parse_args()
    commands=[['acquisition/check_acquisition.py'],['forecast/check_design.py'],['review/verify_external.py','--self-test']]
    steps=[]
    for command in commands:
        # The acquisition fixture filename is fixed by its distributed module.
        p=HERE/command[0]
        if not p.exists():raise FileNotFoundError(p)
        done=subprocess.run([sys.executable,str(p),*command[1:]],text=True,capture_output=True)
        if done.returncode:raise RuntimeError(done.stdout+'\n'+done.stderr)
        steps.append({'command':command,'returncode':0,'stdout':done.stdout[-3000:]})
    rng=np.random.default_rng(9871);count=0
    for k in range(30):
        y=rng.uniform(.1,2,24);a=np.maximum(0,y+rng.normal(0,.3,24));b=np.maximum(0,y+rng.normal(0,.3,24))
        totals=y.reshape(4,6).sum(1);obs=y.copy();start=int(rng.integers(0,19));obs[start:start+6]=np.nan
        obs,_=closure(obs,totals)
        for policy in POLICIES:
            result=trajectory(policy,a,b,obs,totals,RevealOracle(y),a,.3,('synthetic',k))
            assert result['paid_requests']<=6
            assert len(set(result['paid_indices']))==result['paid_requests']
            assert result['final_status'] in ['a','b','numerical_tie']
            count+=1
    report={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),'steps':steps,
            'synthetic_full_trajectories':count,'external_data_read':False,
            'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if args.output:args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'passed','small_checks':len(steps),'synthetic_full_trajectories':count}))

if __name__=='__main__':main()
