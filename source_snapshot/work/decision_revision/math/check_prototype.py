"""Independent compare prototype versus beta-integral scorer on multiple blocks."""
from pathlib import Path
import importlib.util,hashlib,json,math
import numpy as np
from check_decision_probability import exact_myopic_probability

ROOT=Path(__file__).resolve().parents[3]
policy_path=ROOT/'work/decision_revision/prototype/policy.py'
spec=importlib.util.spec_from_file_location('decision_prototype_policy_review',policy_path)
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
rng=np.random.default_rng(514016)
max_error=0.;checked=0
for case in range(400):
    G=int(rng.integers(1,5)); n=G*6
    a=rng.uniform(0,3,n);b=rng.uniform(0,3,n)
    if case%5==0:b[:3]=a[:3]+.5
    truth=rng.gamma(2,.5,n)
    if case%17==0:truth[:6]=0.
    totals=np.array([math.fsum(truth[g*6:(g+1)*6]) for g in range(G)])
    obs=truth.copy()
    for g in range(G):
        missing=rng.choice(np.arange(g*6,(g+1)*6),int(rng.integers(0,7)),replace=False)
        obs[missing]=np.nan
    c=2*(b-a)/n
    fixed=math.fsum(a*a-b*b)/n+math.fsum(c[j]*obs[j] for j in range(n) if np.isfinite(obs[j]))
    blocks=[]
    for g in range(G):
        inds=np.arange(g*6,(g+1)*6);unknown=inds[np.isnan(obs[inds])]
        e=totals[g]-math.fsum(obs[j] for j in inds if np.isfinite(obs[j]))
        blocks.append((unknown,max(0.,e)))
    for row in policy.candidate_scores(a,b,obs,totals):
        i=row['index'];g=i//6;ids,e=blocks[g];j=list(ids).index(i)
        olo=fixed;ohi=fixed
        for h,(js,eh) in enumerate(blocks):
            if h!=g and len(js):olo+=eh*min(c[js]);ohi+=eh*max(c[js])
        expected=exact_myopic_probability(c[ids],e,olo,ohi,j)
        error=abs(expected-row['certificate_probability']);max_error=max(max_error,error);checked+=1
        assert error<1e-10,(case,i,expected,row,error)
result={'status':'passed','random_multiblock_fixtures':400,'candidate_scores_checked':checked,
        'maximum_absolute_probability_error':max_error,'scope':'Independent beta-integral oracle vs prototype; random synthetic fixtures with known coordinates and coefficient ties',
        'policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest()}
Path(__file__).with_name('prototype_independent_check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
