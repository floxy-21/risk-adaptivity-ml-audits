"""Independent generalized Dirichlet score audit, including tiny shapes."""
from pathlib import Path
import hashlib,json,math,sys
import numpy as np
from check_decision_probability import exact_myopic_probability
ROOT=Path(__file__).resolve().parents[3]
PROTO=ROOT/'work/decision_revision/prototype'
sys.path.insert(0,str(PROTO))
import ridge_policy
rng=np.random.default_rng(1011514)
errors=[];checked=0;bad=0;conditioned_alpha_checks=0
for case in range(600):
    G=int(rng.integers(1,5));n=6*G
    a=rng.uniform(0,3,n);b=rng.uniform(0,3,n)
    truth=rng.gamma(2,.5,n);totals=np.array([math.fsum(truth[g*6:(g+1)*6]) for g in range(G)])
    visible=truth.copy()
    for g in range(G):visible[rng.choice(np.arange(g*6,(g+1)*6),int(rng.integers(2,7)),replace=False)]=np.nan
    ridge=rng.uniform(0,3,n);ridge[rng.random(n)<.3]=0.
    kappa=float(rng.choice([.5,1,2,4,8,16]));fixed=ridge_policy.make_alpha(ridge,kappa)
    if case%2:fixed=10**rng.uniform(-8,2,n)
    c=2*(b-a)/n
    d=math.fsum(a*a-b*b)/n+math.fsum(c[i]*visible[i] for i in range(n) if np.isfinite(visible[i]))
    blocks=[]
    for g in range(G):
        idx=np.arange(g*6,(g+1)*6);unknown=idx[np.isnan(visible[idx])]
        E=max(0.,totals[g]-math.fsum(visible[i] for i in idx if np.isfinite(visible[i])))
        blocks.append((unknown,E))
    for row in ridge_policy.candidate_scores(a,b,visible,totals,fixed):
        i=row['index'];g=i//6;idx,E=blocks[g];loc=list(idx).index(i)
        lo=hi=d
        for h,(ids,energy) in enumerate(blocks):
            if h!=g and len(ids):lo+=energy*float(c[ids].min());hi+=energy*float(c[ids].max())
        p=exact_myopic_probability(c[idx],E,lo,hi,loc,fixed[idx])
        error=abs(row['certificate_probability']-p);errors.append(error);checked+=1
        assert error<2e-8,(case,i,p,row,error)
        assert row['alpha']==fixed[i]
        assert row['beta']==math.fsum(fixed[j] for j in idx if j!=i)
        conditioned_alpha_checks+=1
for bad_total in [np.nan,np.inf,-1.]:
    try:ridge_policy.candidate_scores(np.ones(6),np.arange(6),np.full(6,np.nan),[bad_total],np.ones(6))
    except ValueError:bad+=1
    else:raise AssertionError('Invalid total accepted')
report={'status':'passed','fixtures':600,'candidate_scores':checked,
        'maximum_absolute_probability_difference':max(errors),'allowed_absolute_difference':2e-8,
        'fixed_alpha_conditioning_checks':conditioned_alpha_checks,'invalid_total_rejections':bad,
        'alpha_range_tested':'Including arbitrary log-uniform shapes 1e-8 to1e2 and zero-valued Ridge forecasts',
        'make_alpha_floor':'1e-8 * max(mean(max(Ridge,0)) within original block, 1e-12)',
        'inputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [PROTO/'ridge_policy.py',PROTO/'policy.py',Path(__file__).with_name('check_decision_probability.py')]}}
Path(__file__).with_name('ridge_independent_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
