"""Exact lower witnesses for all unchanged failed positive-error cases."""
from collections import Counter
import csv
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent
SENS=HERE.parent


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def pair_constraints(first,second,t,delta):
    """12 true increments; errors are eliminated, then restored exactly."""
    A=[];b=[];E=[];h=[]
    for start in [0,6]:
        total=[F(int(start<=i<start+6)) for i in range(12)]
        E.append(total);h.append(F(1))
        prefix=[F(int(start<=i<start+first)) for i in range(12)]
        A.extend([prefix,[-z for z in prefix]])
        b.extend([t+delta,delta-t])
    difference=[F(int(i<second)-int(6<=i<6+second)) for i in range(12)]
    A.extend([difference,[-z for z in difference]])
    b.extend([2*delta,2*delta])
    return A,b,E,h


def first_proposal(c,first,delta):
    seconds=[j for j in range(1,6) if j!=first]
    n=12*len(seconds)+2;eta=n-2;t=n-1
    A=[];b=[];E=[];h=[]
    for block,second in enumerate(seconds):
        offset=12*block
        for start in [offset,offset+6]:
            row=np.zeros(n);row[start:start+6]=1.;E.append(row);h.append(1.)
            prefix=np.zeros(n);prefix[start:start+first]=1.;prefix[t]=-1.
            A.extend([prefix,-prefix]);b.extend([float(delta)]*2)
        diff=np.zeros(n);diff[offset:offset+second]=1.;diff[offset+6:offset+6+second]=-1.
        A.extend([diff,-diff]);b.extend([float(2*delta)]*2)
        width=np.zeros(n);width[offset:offset+6]=-np.array(c,dtype=float)
        width[offset+6:offset+12]=np.array(c,dtype=float);width[eta]=1.
        A.append(width);b.append(0.)
    objective=np.zeros(n);objective[eta]=-1.
    result=linprog(objective,A_ub=np.array(A),b_ub=np.array(b),A_eq=np.array(E),b_eq=np.array(h),
        bounds=[(0.,1.)]*(n-2)+[(0.,1.),(-float(delta),1.+float(delta))],method='highs',
        options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    assert result.success,result.message
    # A lower certificate may use any feasible first answer. Round only this
    # proposal to an exact rational grid, avoiding spurious binary64 offsets
    # from simple error-band breakpoints. Every resulting endpoint is checked
    # with exact arithmetic; this does not alter the evaluation or threshold.
    answer=min(F(1)+delta,max(-delta,F(round(float(result.x[t])*10**10),10**10)))
    return answer,float(-result.fun)


def solve_exact_basis(rows,n):
    basis={}
    for original,rhs in rows:
        row=list(original)+[rhs]
        for pivot in sorted(basis):
            amount=row[pivot]
            if amount:row=[x-amount*y for x,y in zip(row,basis[pivot])]
        candidates=[j for j in range(n) if row[j]]
        if not candidates:continue
        pivot=candidates[0];factor=row[pivot];row=[x/factor for x in row]
        for old in list(basis):
            amount=basis[old][pivot]
            if amount:basis[old]=[x-amount*y for x,y in zip(basis[old],row)]
        basis[pivot]=row
        if len(basis)==n:return [basis[j][-1] for j in range(n)]
    raise AssertionError('Active constraints did not determine a vertex')


def exact_pair(c,first,second,t,delta):
    A,b,E,h=pair_constraints(first,second,t,delta)
    objective=np.array([-z for z in c]+c,dtype=float)
    solved=linprog(objective,A_ub=np.array(A,dtype=float),b_ub=np.array(b,dtype=float),
        A_eq=np.array(E,dtype=float),b_eq=np.array(h,dtype=float),bounds=[(0.,1.)]*12,
        method='highs',options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    assert solved.success,solved.message
    candidates=[]
    for row,rhs in zip(A,b):
        candidates.append((abs(float(np.array(row,dtype=float)@solved.x)-float(rhs)),row,rhs))
    for i in range(12):
        row=[F(int(j==i)) for j in range(12)]
        candidates.extend([(abs(solved.x[i]),row,F(0)),(abs(solved.x[i]-1),row,F(1))])
    candidates.sort(key=lambda z:z[0])
    point=solve_exact_basis([*zip(E,h),*((row,rhs) for _,row,rhs in candidates)],12)
    assert all(F(0)<=z<=F(1) for z in point)
    assert all(sum(a*z for a,z in zip(row,point))==rhs for row,rhs in zip(E,h))
    assert all(sum(a*z for a,z in zip(row,point))<=rhs for row,rhs in zip(A,b))
    u,v=point[:6],point[6:]
    eu=[F(0)]*5;ev=[F(0)]*5
    eu[first-1]=t-sum(u[:first]);ev[first-1]=t-sum(v[:first])
    difference=sum(u[:second])-sum(v[:second])
    eu[second-1]=-difference/2;ev[second-1]=difference/2
    assert all(abs(z)<=delta for z in eu+ev)
    assert sum(u[:first])+eu[first-1]==sum(v[:first])+ev[first-1]==t
    answer=sum(u[:second])+eu[second-1]
    assert answer==sum(v[:second])+ev[second-1]
    contrast=sum(a*(x-y) for a,x,y in zip(c,u,v))
    assert contrast>F(1,2),(first,second,str(contrast))
    return {'second':second,'u_increments':list(map(str,u)),'v_increments':list(map(str,v)),
        'u_errors':list(map(str,eu)),'v_errors':list(map(str,ev)),
        'common_second_answer_exact':str(answer),'contrast_exact':str(contrast),
        'margin_exact':str(contrast-F(1,2)),'proposal_value':float(-solved.fun)}


def main():
    begin=time.perf_counter();ledger_path=SENS/'case_ledger.csv'
    geometry_path=SENS.parent/'replay/geometry.json'
    with ledger_path.open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    selected=[r for r in rows if F(r['delta'])>0 and r['adaptive_guarantee']=='False']
    assert Counter(F(r['delta']) for r in selected)=={F(1,1000):2,F(1,100):7}
    zero={r['id']:r for r in rows if F(r['delta'])==0}
    geometry={r['id']:r for r in json.loads(geometry_path.read_text())['cases']}
    witnesses=[];summary=[]
    for row in selected:
        raw=[F.from_float(float(z)) for z in geometry[row['id']]['c']]
        span=max(raw)-min(raw);c=[x/span for x in raw];delta=F(row['delta'])
        firsts=[]
        for first in range(1,6):
            t,proposal=first_proposal(c,first,delta)
            pairs=[exact_pair(c,first,j,t,delta) for j in range(1,6) if j!=first]
            lower=min(F(p['contrast_exact']) for p in pairs)
            firsts.append({'first':first,'first_answer_exact':str(t),'pairs':pairs,
                'certified_first_lower_exact':str(lower),'proposal_first_value':proposal})
        lower=min(F(x['certified_first_lower_exact']) for x in firsts)
        assert lower>F(1,2)
        witnesses.append({'id':row['id'],'delta_exact':str(delta),
            'original_coefficients_exact':list(map(str,raw)),'range_exact':str(span),
            'normalized_coefficients_exact':list(map(str,c)),'threshold_exact':'1/2',
            'first_query_witnesses':firsts,'deterministic_optimum_lower_exact':str(lower),
            'strict_impossibility_margin_exact':str(lower-F(1,2))})
        summary.append({'id':row['id'],'system_id':row['system_id'],'pair':row['pair'],
            'delta_exact':str(delta),'zero_error_A':zero[row['id']]['adaptive_worst_width_over_original_W0'],
            'reported_noisy_A':row['adaptive_worst_width_over_original_W0'],
            'certified_lower_exact':str(lower),'certified_lower':float(lower),
            'margin_exact':str(lower-F(1,2)),'margin':float(lower-F(1,2)),
            'legal_first_queries':5,'endpoint_pairs':20})
    bundle={'schema':'fixed-error-deterministic-impossibility-v1','inputs':{
        'case_ledger_sha256':sha(ledger_path),'geometry_sha256':sha(geometry_path),
        'diagnostic_protocol_sha256':sha(HERE/'PROTOCOL.txt')},'witnesses':witnesses}
    (HERE/'witnesses.json').write_text(json.dumps(bundle,indent=2)+'\n')
    with (HERE/'case_ledger.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    report={'status':'PASS','failed_case_levels':9,'unique_cases':len({r['id'] for r in selected}),
        'by_delta':{'1/1000':2,'1/100':7},'legal_first_query_witnesses':45,'exact_endpoint_pairs':180,
        'minimum_strict_margin_exact':str(min(F(r['margin_exact']) for r in summary)),
        'minimum_strict_margin':min(r['margin'] for r in summary),
        'maximum_lower_vs_previous_numeric_gap':max(abs(r['certified_lower']-float(r['reported_noisy_A'])) for r in summary),
        'scope':'Exact feasible lower witnesses prove deterministic two-query impossibility in the declared model; no randomized adaptive or physical-device impossibility claim',
        'source_sha256':sha(Path(__file__)),'witnesses_sha256':sha(HERE/'witnesses.json'),
        'seconds':time.perf_counter()-begin}
    (HERE/'generation_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
