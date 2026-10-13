"""Turn existing sparse-support duals into certified affine decision rules.

No optimizer is called.  All arithmetic uses exact rational numbers.  A
conditional worst-width upper bound is affine in the first readout, so the
online second-query choice needs only comparisons of rational affine lines.
"""
from fractions import Fraction as F
import itertools
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent


def conditional_rows(first, second):
    A=[]; b=[]
    for offset in (0,11):
        row=[F(0)]*22
        row[offset:offset+6]=[F(1)]*6
        A.extend([row,[-x for x in row]]); b.extend([F(1),F(-1)])
    E=[]
    for offset in (0,11):
        row=[F(0)]*22
        row[offset:offset+first]=[F(1)]*first
        row[offset+6+first-1]=F(1)
        E.append(row)
    row=[F(0)]*22
    for i in range(second): row[i]=F(1); row[11+i]=F(-1)
    row[6+second-1]=F(1); row[17+second-1]=F(-1)
    E.append(row)
    return A,b,E


def main():
    started=time.perf_counter()
    source=json.loads((HERE.parent/'stored_error_sensitivity/exact_certificates/certificates.json').read_text())
    branches=[]
    for proof in source['certificates']:
        delta=F(proof['delta_exact'])
        if delta != F(1,100): continue
        c=list(map(F,proof['normalized_coefficients_exact']))
        f=[-x for x in c]+[F(0)]*5+c+[F(0)]*5
        lam=list(map(F,proof['inequality_multipliers']))
        nu=list(map(F,proof['equality_multipliers']))
        m=len(proof['seconds']); lines=[]
        boxes=([(F(0),F(1))]*6+[(-delta,delta)]*5)*2
        for j,second in enumerate(proof['seconds']):
            weight=-lam[4*m+j]
            if weight==0: continue
            assert weight>0
            l=[x/weight for x in lam[4*j:4*j+4]]
            n=[x/weight for x in nu[3*j:3*j+3]]
            A,b,E=conditional_rows(proof['first'],second)
            residual=[f[k]-sum(a[k]*z for a,z in zip(A,l))-sum(e[k]*z for e,z in zip(E,n)) for k in range(22)]
            correction=sum(min(r*lo,r*hi) for r,(lo,hi) in zip(residual,boxes))
            intercept=-(sum(x*y for x,y in zip(l,b))+correction)
            slope=-(n[0]+n[1])
            lines.append({'second_query':second,'source_width_weight_exact':str(weight),
                          'inequality_multipliers':list(map(str,l)),
                          'equality_multipliers':list(map(str,n)),
                          'stationarity_residual':list(map(str,residual)),
                          'box_correction_exact':str(correction),
                          'intercept_exact':str(intercept),'slope_exact':str(slope)})
        domain=(-delta,F(1)+delta)
        candidates=set(domain)
        for a,b in itertools.combinations(lines,2):
            ia,sa=F(a['intercept_exact']),F(a['slope_exact'])
            ib,sb=F(b['intercept_exact']),F(b['slope_exact'])
            if sa!=sb:
                t=(ib-ia)/(sa-sb)
                if domain[0]<=t<=domain[1]: candidates.add(t)
        values=[(t,min(F(line['intercept_exact'])+t*F(line['slope_exact']) for line in lines)) for t in sorted(candidates)]
        upper=max(v for t,v in values)
        assert upper<=F(1,2),(proof['id'],str(upper))
        branches.append({'id':proof['id'],'system_id':proof['system_id'],
                         'first_query':proof['first'],'delta_exact':str(delta),
                         'normalized_coefficients_exact':list(map(str,c)),
                         'first_answer_domain_exact':list(map(str,domain)),
                         'lines':lines,'breakpoint_checks':[[str(t),str(v)] for t,v in values],
                         'certified_worst_branch_bound_exact':str(upper),
                         'certified_margin_exact':str(F(1,2)-upper)})
    assert len(branches)==22
    (HERE/'branch_certificates.json').write_text(json.dumps({'schema':'affine-conditional-dual-box-v1','certificates':branches},indent=2)+'\n')
    report={'status':'PASS','cases':len(branches),'optimizer_calls':0,
            'arithmetic':'Exact rational conditional dual bounds and envelope intersections',
            'minimum_branch_margin_exact':str(min(F(x['certified_margin_exact']) for x in branches)),
            'maximum_branch_upper_exact':str(max(F(x['certified_worst_branch_bound_exact']) for x in branches)),
            'seconds':time.perf_counter()-started}
    (HERE/'branch_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
