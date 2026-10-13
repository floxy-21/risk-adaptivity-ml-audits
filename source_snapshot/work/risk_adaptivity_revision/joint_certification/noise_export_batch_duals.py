"""Export dual certificates for each reported best deterministic batch.

The original run already saved exact lower witnesses for every batch. These
selected-batch duals let a solver-free checker verify both sides of every
reported half-width guarantee decision.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse,json,hashlib
from noise_joint_certify import matrix,solve_bound
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=HERE/'noise_external_results');a=p.parse_args()
    path=a.directory/'certificates.json';cases=json.loads(path.read_text());out=[]
    for case in cases:
        C=[list(map(F,r)) for r in case['normalized_coefficients']];delta=F(case['error']);cap=F(case['cap'])
        batch=min(case['batch_bounds'],key=lambda b:F(b['upper_exact']));Q=batch['Q'];model=matrix(cap,delta,Q);certs=[]
        for r,c in enumerate(C):
            up,cert,_,_=solve_bound(c,model);cert['contrast']=r;certs.append(cert)
        value=max(F(c['upper_exact']) for c in certs)
        assert value==F(batch['upper_exact'])
        out.append({'id':case['id'],'scenario':case['scenario'],'batch':Q,'upper_exact':str(value),'contrast_certificates':certs})
    result={'status':'PASS','cases':out,'certificate_input_sha256':sha(path),'source_sha256':sha(Path(__file__))}
    (a.directory/'batch_upper_certificates.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','cases':len(out),'dual_certificates':sum(len(c['contrast_certificates']) for c in out)}))
if __name__=='__main__':main()
