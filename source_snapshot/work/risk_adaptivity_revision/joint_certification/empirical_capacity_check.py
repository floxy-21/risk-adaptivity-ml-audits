"""Independent endpoint-LP verification of equal-cap shared-query outputs.

No segment-width or marginal-convolution code is imported from the producer.
Checks use fixed-position first/middle/last blocks per available meter.
"""
import argparse,csv,hashlib,itertools,json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];TOL=1e-8
OPTIONS={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def locate(s):
    p=Path(s);return p if p.is_absolute() else ROOT/p

def width(c,cap,first=None,second=None,t=None,batch=None):
    A=np.zeros((2,12));A[0,:6]=1;A[1,6:]=1;rhs=[1.,1.]
    if first is not None:
        row=np.zeros(12);row[:first]=1;A=np.vstack([A,row]);rhs.append(t)
        row=np.zeros(12);row[6:6+first]=1;A=np.vstack([A,row]);rhs.append(t)
        row=np.zeros(12);row[:second]=1;row[6:6+second]=-1;A=np.vstack([A,row]);rhs.append(0.)
    else:
        for k in batch:
            row=np.zeros(12);row[:k]=1;row[6:6+k]=-1;A=np.vstack([A,row]);rhs.append(0.)
    r=linprog(np.r_[-c,c],A_eq=A,b_eq=rhs,bounds=[(0,cap)]*12,method='highs',options=OPTIONS)
    assert r.success,r.message
    return float(-r.fun)

def envelope(parts):
    answer=-1.
    for part in parts:
        lo,hi,lines=part;f=lines.reshape(-1,2);ts=[lo,hi]
        for a,b in itertools.combinations(f,2):
            d=a[0]-b[0]
            if abs(d)>1e-14:
                t=(b[1]-a[1])/d
                if lo<=t<=hi:ts.append(t)
        for t in ts:answer=max(answer,float((lines[:,:,0]*t+lines[:,:,1]).max(axis=1).min()))
    return answer

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',type=Path,default=HERE/'empirical_external_capacity_results')
    p.add_argument('--output',type=Path,default=HERE/'empirical_capacity_independent_check.json');args=p.parse_args()
    report=json.loads((args.results_dir/'empirical_capacity_report.json').read_text())
    plans=json.loads((args.results_dir/'empirical_capacity_plans.json').read_text())['plans']
    for spec in report['inputs'].values():assert sha(locate(spec['path']))==spec['sha256']
    original=json.loads(locate(report['inputs']['uncapped_plans']['path']).read_text())['plans']
    original={c['id']:c for c in original};by=defaultdict(list)
    for pid in sorted({p['id'] for p in plans}):by[original[pid]['meter']].append(pid)
    selected=[ids[i] for ids in by.values() for i in [0,len(ids)//2,len(ids)-1]]
    index={(p['id'],p['cap_fraction']):p for p in plans};batches=list(itertools.combinations(range(1,6),2))
    count=0;max_line=max_batch=max_plan=0.
    for pid in selected:
        c=np.array(original[pid]['geometry']['normalized_coefficients'])
        for cap_string in report['caps']:
            cap=float(Fraction(cap_string));saved=index[pid,cap_string];firsts=[]
            for k in range(1,6):
                js=[j for j in range(1,6) if j!=k];conditional_cache={};parts=[]
                for part in saved['firsts'][k-1]['intervals']:
                    lo,hi=part['lo'],part['hi'];line=np.array(part['lines'])
                    ends=[]
                    for t in [lo,hi]:
                        key=round(t,14)
                        if key not in conditional_cache:
                            conditional_cache[key]=np.array([[width(contrast,cap,k,j,t) for contrast in c] for j in js]);count+=len(js)*len(c)
                        ends.append(conditional_cache[key])
                        max_line=max(max_line,float(np.max(abs(conditional_cache[key]-(line[:,:,0]*t+line[:,:,1])))))
                    # One non-knot answer checks the affine interpolation separately.
                    t=(2*lo+hi)/3
                    actual=np.array([[width(contrast,cap,k,j,t) for contrast in c] for j in js]);count+=len(js)*len(c)
                    max_line=max(max_line,float(np.max(abs(actual-(line[:,:,0]*t+line[:,:,1])))))
                    slope=(ends[1]-ends[0])/(hi-lo);parts.append((lo,hi,np.stack([slope,ends[0]-slope*lo],axis=2)))
                firsts.append(envelope(parts))
            max_plan=max(max_plan,float(np.max(abs(np.array(firsts)-saved['first_guarantees']))))
            exact_batches=[]
            for q in batches:
                exact_batches.append(max(width(contrast,cap,batch=q) for contrast in c));count+=len(c)
            max_batch=max(max_batch,float(np.max(abs(np.array(exact_batches)-saved['batch_guarantees']))))
    assert max_line<TOL and max_batch<TOL and max_plan<TOL
    result={'status':'PASS','scope':__doc__,'selected_ids':selected,'selected_blocks':len(selected),
            'all_plan_rows':len(plans),'endpoint_LP_count':count,'max_conditional_line_discrepancy':max_line,
            'max_batch_guarantee_discrepancy':max_batch,'max_adaptive_guarantee_discrepancy':max_plan,
            'tolerance':TOL,'floating_point_not_rational_certificate':True,
            'producer_plan_sha256':sha(args.results_dir/'empirical_capacity_plans.json'),'source_sha256':sha(Path(__file__))}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
