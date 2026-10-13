"""Review regression: a zero contrast coefficient is not an eligibility exclusion.

Uses exact rational vertices for ground truth and executes the frozen production
selectors, trajectories, closure and hindsight driver. No study input is edited.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import hashlib, json, subprocess, sys, tempfile
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'work/decision_revision'))
sys.path.insert(0,str(ROOT/'work/decision_revision/oracle'))
import confirmation as prod
import policy, ridge_policy, acquisition
from study_recovery import prepare_blocks
from hindsight_diagnostic import bounds

def rational_bounds(query):
    c=[F(0),F(1),F(1)]; y=[F(3,5),F(1,5),F(1,5)]
    fixed=F(-1,2)+sum(c[i]*y[i] for i in query)
    missing=[i for i in range(3) if i not in query]
    residual=F(1)-sum(y[i] for i in query)
    vertices=[fixed+residual*c[i] for i in missing] if missing else [fixed]
    return min(vertices),max(vertices)

def minimum(allowed):
    for k in range(len(allowed)+1):
        for q in combinations(allowed,k):
            lo,hi=rational_bounds(q)
            if hi<0 or lo>0:return k,list(q)
    return None,None

expected={():[F(-1,2),F(1,2)],(0,):[F(-1,10),F(-1,10)],
          (1,):[F(-3,10),F(1,2)],(2,):[F(-3,10),F(1,2)]}
for q,v in expected.items():assert list(rational_bounds(q))==v
assert minimum([0,1,2])==(1,[0])
assert minimum([1,2])[0]==2

# MSE difference is the reviewer's D/24; predictions are nonnegative.
a=np.zeros(24);b=np.zeros(24);b[1:3]=.5
y=np.zeros(24);y[:3]=[.6,.2,.2]
observed=y.copy();observed[:3]=np.nan
totals=np.array([1.,0.,0.,0.]);alpha=np.ones(24)
mean=np.full(24,.2);sd=1.
for q,v in expected.items():
    visible=observed.copy();visible[list(q)]=y[list(q)]
    assert np.allclose(np.array(prod.interval(a,b,visible,totals))*24,list(map(float,v)),atol=1e-13)
    assert np.allclose(np.array(bounds(a,b,visible,totals))*24,list(map(float,v)),atol=1e-13)
blocks=prepare_blocks(2*(b-a)/24,observed,totals)
eligible=acquisition._eligible(blocks,[])
assert eligible==[0,1,2]
assert [r['index'] for r in policy.candidate_scores(a,b,observed,totals)]==eligible
assert [r['index'] for r in ridge_policy.candidate_scores(a,b,observed,totals,alpha)]==eligible
for c in [policy.select_one(a,b,observed,totals),policy.select_one(a,b,observed,totals,objective='exact_width_one'),
          ridge_policy.select_one(a,b,observed,totals,alpha)]:assert c['query_indices']==[0]
choices={}
for name in acquisition.POLICIES:
    r=acquisition.select_batch(name,a,b,observed,totals,1,rng=np.random.default_rng(5),surrogate_mean=mean,surrogate_sd=sd)
    assert set(r['query_indices'])<=set(eligible)
    if name in ['exact','greedy','randomized']:assert r['query_indices']==[0]
    if name in ['hara','uniform']:assert r['diagnostics']['draws'][0]['eligible']==eligible
    choices[name]=r['query_indices']

# Whole-block constant contrasts are correctly omitted; individual zero is not.
constant_b=b.copy();constant_b[:3]=.5
assert policy.candidate_scores(a,constant_b,observed,totals)==[]
assert ridge_policy.candidate_scores(a,constant_b,observed,totals,alpha)==[]
assert acquisition._eligible(prepare_blocks(2*(constant_b-a)/24,observed,totals),[])==[]

# Actual free closure determines singleton and zero residual coordinates.
visible=observed.copy();visible[[1,2]]=y[[1,2]]
closed,deductions=prod.closure(visible,totals)
assert np.allclose(closed,y) and len(deductions)==1 and deductions[0]['index']==0
zero_totals=np.zeros(4);closed,deductions=prod.closure(observed.copy(),zero_totals)
assert np.all(closed==0) and len(deductions)==3

run=HERE/'fixture_run';run.mkdir(exist_ok=True)
case={'case_id':'zero-coefficient-review','household_id':'review','day_utc':'2014-01-01',
      'pair':'a vs b','learned_pair':True,'a':a,'b':b,'initial_observed':observed,'totals':totals}
(run/'source_cases.jsonl').write_text(json.dumps(prod.safe(case))+'\n')
(run/'run_result.json').write_text(json.dumps({'status':'passed','scope':'synthetic review fixture'}))
rows=[];traces={}
for name in prod.POLICIES:
    r=prod.trajectory(name,a,b,observed,totals,prod.RevealOracle(y),mean,sd,alpha,case['case_id'])
    rows.append({'case_id':case['case_id'],'household_id':'review','learned_pair':True,'policy':name,
                 'paid_requests':r['paid_requests'],'certification_cost':r['certification_cost'],'final_status':r['final_status']})
    assert r['final_status']=='a'
    traces[name]={'queries':[z['query'] for z in r['trace']],'cost':r['paid_requests']}
pd.DataFrame(rows).to_csv(run/'cases.csv',index=False)
pd.DataFrame({'household_id':['review']*24,'period':['test']*24,
              'timestamp_utc':pd.date_range('2014-01-01',periods=24,freq='h').astype(str),
              'energy_kwh':y}).to_csv(run/'reference_targets.csv',index=False)
temporary=tempfile.TemporaryDirectory(prefix='zero_coefficient_oracle_')
out=Path(temporary.name)/'oracle'
command=[sys.executable,str(ROOT/'work/decision_revision/oracle/confirmation_oracle.py'),
         '--run-dir',str(run),'--reference',str(run/'reference_targets.csv'),'--output-dir',str(out)]
result=subprocess.run(command,text=True,capture_output=True,check=True)
oracle=pd.read_csv(out/'cases.csv').iloc[0]
assert int(oracle.oracle_minimum_requests)==1 and json.loads(oracle.oracle_witness)==[0]
report={'status':'passed','scope':'Synthetic regression, not another empirical effectiveness experiment',
        'exact_rational_bounds':{str(q):list(map(str,v)) for q,v in expected.items()},
        'unrestricted_exact_hindsight':minimum([0,1,2]),'incorrectly_zero_excluded_hindsight':minimum([1,2]),
        'production_eligible_indices':eligible,'production_singleton_choices':choices,
        'production_trajectories':traces,'actual_hindsight_driver_cost':int(oracle.oracle_minimum_requests),
        'actual_hindsight_driver_witness':json.loads(oracle.oracle_witness),
        'constant_block_and_free_closure_checks':True,
        'hara_note':'Coordinate0 is eligible but its published pointwise loss-contrast proposal weight is zero; this is a scoring limitation, not a coefficient-zero eligibility filter.'}
(HERE/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
temporary.cleanup()
