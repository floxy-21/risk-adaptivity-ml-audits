"""Independent exact checks of exported joint stored-error certificates.

No solver and no producer import. It verifies adaptive upper certificates,
best-batch upper certificates, all-batch lower witnesses and adverse mixtures.
"""
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
import argparse, hashlib, json, time

HERE=Path(__file__).resolve().parent
BATCHES=list(combinations(range(1,6),2))
def read(p):return json.loads(p.read_text())
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def feasible(x,cap):return len(x)==6 and sum(x)==1 and all(0<=v<=cap for v in x)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def branch_upper(C,k,j,lo,hi,delta,cap,cert):
    # Independently form the minimization dual bound, with residual optimized
    # over the complete bounded box rather than trusting numerical stationarity.
    A=[]; b=[]
    r=[F(0)]*13
    for i in range(j):r[i]=1;r[6+i]=-1
    A.extend([r,[-x for x in r]]);b.extend([2*delta]*2)
    for offset in (0,6):
        r=[F(0)]*13
        for i in range(k):r[offset+i]=1
        r[12]=-1
        A.extend([r,[-x for x in r]]);b.extend([delta]*2)
    H=[]
    for offset in (0,6):
        r=[F(0)]*13
        for i in range(6):r[offset+i]=1
        H.append(r)
    f=[-v for v in C]+C+[F(0)]
    lam=list(map(F,cert['ineq_multipliers']));nu=list(map(F,cert['eq_multipliers']))
    assert len(lam)==6 and len(nu)==2 and all(v<=0 for v in lam)
    residual=[f[i]-sum(lam[z]*A[z][i] for z in range(6))-sum(nu[z]*H[z][i] for z in range(2)) for i in range(13)]
    box=[(F(0),cap)]*12+[(lo,hi)]
    value=-dot(lam,b)-sum(nu)-sum(min(r*l,r*u) for r,(l,u) in zip(residual,box))
    assert value==F(cert['upper_exact'])
    return value

def batch_upper(C,Q,delta,cap,cert):
    A=[];b=[]
    for q in Q:
        r=[F(0)]*12
        for i in range(q):r[i]=1;r[6+i]=-1
        A.extend([r,[-x for x in r]]);b.extend([2*delta]*2)
    H=[]
    for offset in (0,6):
        r=[F(0)]*12
        for i in range(6):r[offset+i]=1
        H.append(r)
    f=[-v for v in C]+C;lam=list(map(F,cert['ineq_multipliers']));nu=list(map(F,cert['eq_multipliers']))
    assert len(lam)==4 and len(nu)==2 and max(lam)<=0
    residual=[f[i]-sum(lam[z]*A[z][i] for z in range(4))-sum(nu[z]*H[z][i] for z in range(2)) for i in range(12)]
    value=-dot(lam,b)-sum(nu)-sum(min(F(0),r*cap) for r in residual)
    assert value==F(cert['upper_exact']);return value

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=HERE/'noise_external_results');a=p.parse_args()
    t=time.perf_counter();plans=read(a.directory/'frozen_policies.json');P={x['id']:x for x in plans['policies']}
    # Public external package includes the frozen coefficient geometry.
    # Hash and row checks tie certificates to those source forecasts.
    source_rows={}
    for rel,digest in plans['source_hashes'].items():
        source=HERE.parent/Path(rel.replace('\\','/'))
        assert source.exists(),f'Missing frozen coefficient source: {source}'
        assert sha(source)==digest
        for row in read(source)['cases']:source_rows[row['id']]=row
    for plan in P.values():
        assert [source_rows[key]['c'] for key in plan['pair_case_ids']]==plan['original_c_binary64']
    rows=read(a.directory/'cases.json');R={(x['id'],x['scenario']):x for x in rows};certs=read(a.directory/'certificates.json')
    assert len(R)==len(rows)==len(certs)
    batchfile=a.directory/'batch_upper_certificates.json';batchdata=read(batchfile)
    assert batchdata['certificate_input_sha256']==sha(a.directory/'certificates.json')
    batchduals={(r['id'],r['scenario']):r for r in batchdata['cases']};assert len(batchduals)==len(certs)
    counts={'cases':0,'source_coefficient_rows':sum(len(p['pair_case_ids']) for p in P.values()),'branch_dual_certificates':0,'batch_lower_witnesses':0,'best_batch_dual_certificates':0,'fixed_adverse_records':0,'precision_separations':0}
    for c in certs:
        key=(c['id'],c['scenario']);row=R[key];plan=P[c['id']]
        C=[]
        for raw in plan['original_c_binary64']:
            x=[F.from_float(z) for z in raw];r=max(x)-min(x);assert r>0
            C.append([(z-min(x))/r for z in x])
        assert [[str(v) for v in x] for x in C]==c['normalized_coefficients']==plan['normalized_coefficients_exact']
        delta=F(c['error']);cap=F(c['cap']);k=c['first_query'];assert k==plan['first_query'] and k in range(1,6)
        initial=plan['branches'];assert F(initial[0]['lo'])==0 and F(initial[-1]['hi'])==1
        assert all(F(b['lo'])<=F(b['hi']) and b['second'] in range(1,6) and b['second']!=k for b in initial)
        assert all(F(x['hi'])==F(y['lo']) for x,y in zip(initial,initial[1:]))
        firstlo=max(F(0),1-(6-k)*cap)-delta;firsthi=min(F(1),k*cap)+delta
        expected=[]
        for i,b in enumerate(initial):
            lo=max(firstlo,F(b['lo']) if i else -delta);hi=min(firsthi,F(b['hi']) if i<len(initial)-1 else 1+delta)
            if lo<=hi:expected.append((lo,hi,b['second']))
        assert expected==[(F(b['lo']),F(b['hi']),b['second']) for b in c['branches']]
        assert expected[0][0]==firstlo and expected[-1][1]==firsthi
        assert all(x[1]==y[0] for x,y in zip(expected,expected[1:]))
        uppers=[]
        for branch in c['branches']:
            lo,hi=F(branch['lo']),F(branch['hi']);j=branch['second'];assert lo<=hi and j in range(1,6) and j!=k
            assert sorted(z['contrast'] for z in branch['contrast_certificates'])==list(range(6))
            for cert in branch['contrast_certificates']:
                uppers.append(branch_upper(C[cert['contrast']],k,j,lo,hi,delta,cap,cert));counts['branch_dual_certificates']+=1
        bound=max(uppers);assert bound==F(row['frozen_adaptive_upper_exact']);assert (bound<=F(1,2))==row['adaptive_half_guarantee']
        assert [tuple(b['Q']) for b in c['batch_bounds']]==BATCHES
        lower=[]
        for b in c['batch_bounds']:
            w=b['lower_witness']
            if w is None:assert b['lower_exact'] is None;lower.append(None);continue
            x,v=list(map(F,w['endpoints'][:6])),list(map(F,w['endpoints'][6:]));assert feasible(x,cap) and feasible(v,cap)
            assert all(abs(sum(x[:q])-sum(v[:q]))<=2*delta for q in b['Q'])
            width=dot(C[w['contrast']],[xx-vv for xx,vv in zip(x,v)])
            assert width==F(w['width_exact'])==F(b['lower_exact']) and width<=F(b['upper_exact'])
            lower.append(width);counts['batch_lower_witnesses']+=1
        positive=bound<=F(1,2) and all(v is not None and v>F(1,2) for v in lower)
        bc=batchduals[key];assert tuple(bc['batch']) in BATCHES
        assert sorted(z['contrast'] for z in bc['contrast_certificates'])==list(range(6))
        bupper=max(batch_upper(C[z['contrast']],bc['batch'],delta,cap,z) for z in bc['contrast_certificates'])
        assert bupper==F(bc['upper_exact'])==min(F(b['upper_exact']) for b in c['batch_bounds'])
        counts['best_batch_dual_certificates']+=6
        # Every reported guarantee is proved by a feasible batch's six duals;
        # every reported failure is proved by a >1/2 witness for every batch.
        assert (bupper<=F(1,2))==row['det_batch_half_guarantee']
        if not row['det_batch_half_guarantee']:assert all(v is not None and v>F(1,2) for v in lower)
        assert positive==c['precision_separation']==row['certified_adaptive_vs_all_randomized_batch_precision']
        if positive:
            assert len(c['adverse_records'])==10 and c['batch_success_upper']=='9/10'
            assert [tuple(w['failing_batch']) for w in c['adverse_records']]==BATCHES
            for w in c['adverse_records']:
                x=list(map(F,w['record_x']));e=list(map(F,w['fixed_errors']));v=list(map(F,w['endpoints'][6:]))
                assert x==list(map(F,w['endpoints'][:6])) and feasible(x,cap) and feasible(v,cap)
                assert len(e)==5 and max(map(abs,e))<=delta
                assert all(abs(sum(v[:q])-(sum(x[:q])+e[q-1]))<=delta for q in w['failing_batch'])
                assert dot(C[w['contrast']],[xx-vv for xx,vv in zip(x,v)])>F(1,2)
                counts['fixed_adverse_records']+=1
            counts['precision_separations']+=1
        else:assert not c['adverse_records']
        counts['cases']+=1
    strengthened=a.directory/'strengthened_batch_bounds.json'
    if strengthened.exists():
        data=read(strengthened);lookup={(c['id'],c['scenario']):c for c in certs}
        counts['strengthened_adverse_mixtures']=0;counts['cross_batch_failures']=0
        for row in data['cases']:
            source=lookup[(row['id'],row['scenario'])]
            assert source['precision_separation'] and row['source_adverse_records']==source['adverse_records']
            assert row['normalized_coefficients']==source['normalized_coefficients']
            C=[list(map(F,r)) for r in row['normalized_coefficients']];cap=F(row['cap']);delta=F(row['error'])
            assert cap==F(source['cap']) and delta==F(source['error'])
            weights=list(map(F,row['adverse_weights']));assert len(weights)==10 and min(weights)>=0 and sum(weights)==1
            alts=[list(map(F,x)) for x in row['alternative_endpoints']];assert all(feasible(x,cap) for x in alts)
            U=[[1]*10 for _ in range(10)]
            for w in row['failure_witnesses']:
                atom=source['adverse_records'][w['record']];x=list(map(F,atom['record_x']));e=list(map(F,atom['fixed_errors']));v=alts[w['alternative']];Q=BATCHES[w['batch']]
                assert all(abs(sum(v[:q])-sum(x[:q])-e[q-1])<=delta for q in Q)
                width=abs(dot(C[w['contrast']],[xx-vv for xx,vv in zip(x,v)]))
                assert width>F(1,2) and width==F(w['width_exact'])
                U[w['record']][w['batch']]=0;counts['cross_batch_failures']+=1
            assert U==row['possible_success_matrix']
            vals=[sum(weights[i]*U[i][j] for i in range(10)) for j in range(10)]
            assert list(map(str,vals))==row['batch_expected_upper'] and max(vals)==F(row['success_upper_exact'])<=F(9,10)
            counts['strengthened_adverse_mixtures']+=1
        def quantile(q,p):
            t=F(len(q)-1)*p;i=t.numerator//t.denominator
            return q[i]+(t-i)*(q[min(i+1,len(q)-1)]-q[i])
        for scenario,summary in data['summary'].items():
            q=sorted(F(r['success_upper_exact']) for r in data['cases'] if r['scenario']==scenario)
            assert len(q)==summary['cases']
            assert sum(v<=F(1,2) for v in q)==summary['at_most_half']
            assert sum(v<=F(7,10) for v in q)==summary['at_most_seven_tenths']
            expected={'minimum':q[0],'maximum':q[-1],'median':quantile(q,F(1,2)),'q25':quantile(q,F(1,4)),'q75':quantile(q,F(3,4))}
            assert all(abs(float(v)-summary[k])<1e-14 for k,v in expected.items())
    declared=read(a.directory/'report.json')
    for scenario,summary in declared['summary'].items():
        rr=[r for r in rows if r['scenario']==scenario]
        assert len(rr)==summary['cases']
        assert sum(r['adaptive_half_guarantee'] for r in rr)==summary['adaptive_half_guarantees']
        assert sum(r['det_batch_half_guarantee'] for r in rr)==summary['det_batch_half_guarantees']
        assert sum(r['certified_adaptive_vs_all_randomized_batch_precision'] for r in rr)==summary['adaptive_vs_all_randomized_precision_separations']
    report={'status':'PASS','checks':counts,'scope':'Hashed frozen source coefficient rows and exact normalization; all branch dual residual bounds; coverage of every feasible first answer with first-matching closed-interval policy; feasible deterministic-batch lower witnesses and best-batch dual upper certificates proving every reported half-width guarantee status; fixed full adverse records and randomized-batch precision upper bounds, including strengthened mixtures when present. Numerical LP optimality is not assumed for the verified upper/lower certificates.',
        'inputs_sha256':{name:sha(a.directory/name) for name in ('frozen_policies.json','cases.json','certificates.json')},'checker_sha256':sha(Path(__file__)),'elapsed_seconds':time.perf_counter()-t}
    if strengthened.exists():report['inputs_sha256']['strengthened_batch_bounds.json']=sha(strengthened)
    report['inputs_sha256']['batch_upper_certificates.json']=sha(batchfile)
    (a.directory/'independent_check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
