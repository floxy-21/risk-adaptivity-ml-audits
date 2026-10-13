"""Tighten batch precision upper bounds using exact fixed adverse records.

The ten records were supplied by feasible endpoint certificates. For each,
reuse endpoint alternatives from all batches to prove extra failures; all other
entries are conservatively counted as success. Rational feasible weights give
a rigorous full-continuum upper bound, regardless of LP optimality tolerances.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import argparse,json,hashlib,time
import numpy as np
from scipy.optimize import linprog
HERE=Path(__file__).resolve().parent
BATCHES=list(combinations(range(1,6),2))
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=HERE/'noise_external_results');a=p.parse_args()
    t=time.perf_counter();certs=json.loads((a.directory/'certificates.json').read_text());out=[]
    for case in certs:
        if not case['precision_separation']:continue
        C=[list(map(F,r)) for r in case['normalized_coefficients']];delta=F(case['error']);cap=F(case['cap'])
        alts=[]
        for b in case['batch_bounds']:
            w=b['lower_witness']
            for offset in (0,6):
                v=list(map(F,w['endpoints'][offset:offset+6]))
                if v not in alts:alts.append(v)
        U=np.ones((10,10));failures=[]
        for ai,atom in enumerate(case['adverse_records']):
            x=list(map(F,atom['record_x']));e=list(map(F,atom['fixed_errors']));z=[sum(x[:q])+e[q-1] for q in range(1,6)]
            for bi,Q in enumerate(BATCHES):
                found=None
                for vi,v in enumerate(alts):
                    if not all(abs(sum(v[:q])-z[q-1])<=delta for q in Q):continue
                    diff=[xx-vv for xx,vv in zip(x,v)]
                    for ri,c in enumerate(C):
                        width=abs(dot(c,diff))
                        if width>F(1,2):found={'record':ai,'batch':bi,'alternative':vi,'contrast':ri,'width_exact':str(width)};break
                    if found:break
                if found:U[ai,bi]=0;failures.append(found)
        assert all(U[i,i]==0 for i in range(10))
        # min_z max_batch expected upper-indicator. Every nonzero returned
        # weight is rationalized then normalized; direct evaluation is final.
        A=np.column_stack((U.T,-np.ones(10)));res=linprog(np.r_[np.zeros(10),1.],A_ub=A,b_ub=np.zeros(10),A_eq=[np.r_[np.ones(10),0]],b_eq=[1],bounds=[(0,1)]*11,method='highs')
        assert res.success
        weights=[max(F(0),F(float(v)).limit_denominator(10**8)) for v in res.x[:10]];total=sum(weights);assert total>0;weights=[w/total for w in weights]
        vals=[sum(weights[i]*int(U[i,j]) for i in range(10)) for j in range(10)];bound=max(vals)
        # Uniform weights always provide <=.9; avoid numerical solver output
        # weakening that already established bound.
        if bound>F(9,10):weights=[F(1,10)]*10;vals=[sum(weights[i]*int(U[i,j]) for i in range(10)) for j in range(10)];bound=max(vals)
        out.append({'id':case['id'],'scenario':case['scenario'],'adverse_weights':list(map(str,weights)),'success_upper_exact':str(bound),'success_upper':float(bound),'batch_expected_upper':list(map(str,vals)),
            'possible_success_matrix':U.astype(int).tolist(),'alternative_endpoints':[[str(v) for v in x] for x in alts],'failure_witnesses':failures,'source_adverse_records':case['adverse_records'],'error':case['error'],'cap':case['cap'],'normalized_coefficients':case['normalized_coefficients']})
    summary={}
    for scenario in sorted({r['scenario'] for r in out}):
        rr=[r for r in out if r['scenario']==scenario];q=np.array([r['success_upper'] for r in rr]);summary[scenario]={'cases':len(rr),'minimum':float(min(q)),'median':float(np.median(q)),'q25':float(np.quantile(q,.25)),'q75':float(np.quantile(q,.75)),'maximum':float(max(q)),'at_most_half':sum(F(r['success_upper_exact'])<=F(1,2) for r in rr),'at_most_seven_tenths':sum(F(r['success_upper_exact'])<=F(7,10) for r in rr)}
    result={'status':'PASS','scope':'Exact feasible adverse weights and endpoint alternatives certify upper bounds on every randomized batch precision success for the full latent-record domain, not equality with the continuum optimum. Unknown success entries are set to one. No fine answers are read. This reuses only existing certificate endpoints; it does not solve every profile-by-batch interval LP.',
        'summary':summary,'cases':out,'certificate_input_sha256':sha(a.directory/'certificates.json'),'source_sha256':sha(Path(__file__)),'elapsed_seconds':time.perf_counter()-t}
    (a.directory/'strengthened_batch_bounds.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
