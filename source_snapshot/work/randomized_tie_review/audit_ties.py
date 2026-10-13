"""Post-review target-independent refinement of every saved minimax mixture."""
from pathlib import Path
from datetime import datetime, timezone
from fractions import Fraction
import os
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ.setdefault(name,'1')
import json, hashlib, time, itertools
import numpy as np
import pandas as pd
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
ORIGINAL=ROOT/'work/new_direction_randomized'
TOL=2e-7
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def matrix_for(rec):
    blocks=rec['blocks']; queries=rec['batches']; n=sum(len(b['indices']) for b in blocks)
    matrix=np.zeros((n,len(queries)));groups=[]; ids=[]; offset=0
    for g,b in enumerate(blocks):
        indices=b['indices'];cs=dict(zip(indices,b['coefficients']))
        for j,q in enumerate(queries):
            retained=[i for i in indices if i not in q]
            width=max(cs[i] for i in retained)-min(cs[i] for i in retained)
            for k,i in enumerate(indices):
                if i in retained: matrix[offset+k,j]=b['energy']*width/rec['initial_width']
        groups.extend([g]*len(indices));ids.extend(indices);offset+=len(indices)
    return matrix,np.array(groups),ids

def metrics(matrix,groups,p):
    z=matrix@p
    return z,float(sum(z[groups==g].max() for g in set(groups))),float(sum(z[groups==g].mean() for g in set(groups)))

def refine(rec,kind):
    matrix,groups,ids=matrix_for(rec);p0=np.asarray(rec['probabilities'])
    z0,v0,s0=metrics(matrix,groups,p0);nq=len(p0);ng=len(rec['blocks'])
    objective=np.r_[sum(matrix[groups==g].mean(axis=0) for g in range(ng)),np.zeros(ng)]
    inequalities=np.zeros((len(ids)+1,nq+ng));inequalities[:-1,:nq]=matrix
    inequalities[np.arange(len(ids)),nq+groups]=-1.
    inequalities[-1,nq:]=1.
    if kind=='dominance':
        rhs=np.r_[z0,0.];bounds=[(0,None)]*nq+[(None,None)]*ng
    elif kind=='reference':
        rhs=np.r_[np.zeros(len(ids)),v0];bounds=[(0,None)]*(nq+ng)
    else: raise ValueError(kind)
    equality=np.r_[np.ones(nq),np.zeros(ng)][None,:]
    result=linprog(objective,A_ub=inequalities,b_ub=rhs,A_eq=equality,b_eq=[1.],
                   bounds=bounds,method='highs-ds',options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    if not result.success: raise RuntimeError((rec['case_id'],kind,result.message))
    raw=result.x[:nq];p=np.maximum(0.,raw);p/=p.sum()
    z,value,secondary=metrics(matrix,groups,p)
    delta=float(sum((z-z0)[groups==g].max() for g in range(ng)))
    primary_gap=abs(value-rec['dual_normalized_objective'])
    primal=max(0.,float((inequalities@result.x-rhs).max()),abs(raw.sum()-1.),float(-raw.min()))
    dual_objective=float(rhs@result.ineqlin.marginals+result.eqlin.marginals[0])
    stationarity=objective-inequalities.T@result.ineqlin.marginals-equality.T[:,0]*result.eqlin.marginals[0]-result.lower.marginals-result.upper.marginals
    dual_residual=max(float(np.max(np.abs(stationarity))),float(max(0.,result.ineqlin.marginals.max())))
    dual_gap=abs(secondary-dual_objective)
    assert max(primal,dual_residual,dual_gap,primary_gap)<=TOL,(rec['case_id'],kind,primal,dual_residual,dual_gap,primary_gap)
    assert secondary<=s0+TOL
    if kind=='dominance': assert delta<=TOL
    return {'probabilities':p.tolist(),'expected_coefficients':z.tolist(),
            'primary_normalized':value,'secondary_normalized':secondary,'secondary_original':s0,
            'maximum_expected_width_difference_normalized':delta,
            'primal_violation':primal,'dual_stationarity_error':dual_residual,
            'secondary_duality_gap':dual_gap,'primary_lower_bound_gap':primary_gap,
            'normalization_l1_change':float(np.abs(p-raw).sum())}

def exact_example():
    cs=[0,0,2,3];queries=[(i,) for i in range(4)]
    weights=[Fraction(2,9),Fraction(2,9),Fraction(2,9),Fraction(1,3)]
    vectors=[]
    for q in queries:
        kept=[i for i in range(4) if i not in q];width=max(cs[i] for i in kept)-min(cs[i] for i in kept)
        vectors.append([Fraction(width if i in kept else 0) for i in range(4)])
    bad=[sum(weights[j]*vectors[j][i] for j in range(4)) for i in range(4)]
    good=vectors[3]
    assert bad==[2,2,2,2] and good==[2,2,2,0]
    for vec in vectors+[[Fraction(3)]*4]: assert sum(vec[:3])/3>=2
    return {'coefficients':cs,'total':1,'budget':1,'bad_expected_coefficients':list(map(str,bad)),
            'good_expected_coefficients':list(map(str,good)),'minimax_value':2,'exact_fraction_check':'passed'}

def evaluate_case(rec,policy,d):
    truth=d.truth_kwh.to_numpy();a=d[rec['model_a']].to_numpy();b=d[rec['model_b']].to_numpy()
    c=2*(b-a)/len(d);total=truth.reshape(4,6).sum(axis=1)
    initially_observed=np.array([bool(rec['observed_mask']&(1<<i)) for i in range(24)])
    reference=float(np.mean((a-truth)**2-(b-truth)**2))
    width=cert=queries=0.;support=[]
    for p,q in zip(policy['probabilities'],rec['batches']):
        if p<=0: continue
        assert len(q)<=2 and all(not initially_observed[i] for i in q)
        obs=initially_observed.copy();obs[q]=True
        lo=hi=float(np.mean(a*a-b*b)+np.dot(c[obs],truth[obs]))
        for g,t in enumerate(total):
            indices=np.arange(6*g,6*g+6);remaining=indices[~obs[indices]]
            residual=max(0.,float(t-truth[indices[obs[indices]]].sum()))
            if len(remaining):lo+=residual*float(c[remaining].min());hi+=residual*float(c[remaining].max())
        eps=1e-9*max(1.,abs(lo),abs(hi));sign=1 if lo>eps else -1 if hi < -eps else 0
        assert lo-TOL*max(1.,abs(reference))<=reference<=hi+TOL*max(1.,abs(reference))
        assert not sign or sign==int(np.sign(reference))
        w=max(0.,hi-lo);width+=p*w;cert+=p*bool(sign);queries+=p*len(q)
        support.append({'query':q,'probability':p,'lower':lo,'upper':hi,'width':w,'certified':bool(sign)})
    independent=0.;offset=0
    for block in rec['blocks']:
        n=len(block['indices']);z=np.array(policy['expected_coefficients'][offset:offset+n]);offset+=n
        independent+=np.dot(truth[block['indices']]/block['energy'],z)*rec['initial_width']
    error=abs(independent-width)/max(1.,rec['initial_width'])
    assert error<=TOL
    return {'actual_width':width,'certification':cert,'queries':queries,'width_identity_error_scaled':error,'support':support}

def main():
    started=time.perf_counter()
    inputs=[ORIGINAL/'lp_solutions.jsonl',ORIGINAL/'cases.csv',HERE/'protocol.txt',ROOT/'outputs/review_frozen_forecasts.csv']
    pins={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    records=[json.loads(line) for line in (ORIGINAL/'lp_solutions.jsonl').read_text().splitlines()]
    assert len(records)==1074
    example=exact_example();policies=[]
    # Phase one intentionally cannot access the reference target data.
    for n,rec in enumerate(records,1):
        policies.append({'case_id':rec['case_id'],'dominance':refine(rec,'dominance'),'reference':refine(rec,'reference')})
        if n%250==0: print('selected',n,'of',len(records),flush=True)
    selected=HERE/'policies.jsonl'
    selected.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in policies),encoding='utf-8')
    selection_hash=sha(selected);selection_time=datetime.now(timezone.utc).isoformat()
    (HERE/'selection_complete.json').write_text(json.dumps({'status':'passed','policy_sha256':selection_hash,
        'completed_utc':selection_time,'reference_targets_read_for_selection':False,'inputs':pins},indent=2),encoding='utf-8')
    # Phase two evaluates frozen policies; no optimizer calls below this line.
    data=pd.read_csv(ROOT/'outputs/review_frozen_forecasts.csv')
    data=data[data.cohort.isin(['portugal','household'])].copy();data['day']=data.timestamp.str[:10]
    frames={(a,b,c):d.sort_values('timestamp') for (a,b,c),d in data.groupby(['cohort','meter','day'])}
    cases=pd.read_csv(ORIGINAL/'cases.csv').set_index('case_id',drop=False)
    for kind in ['dominance','reference']:
        for suffix,original in [('actual_width','randomized_expected_actual_width'),('certification','randomized_expected_certification'),
                                ('queries','randomized_expected_queries'),('worst_width','randomized_worst_expected_width')]:
            cases[kind+'_'+suffix]=cases[original]
    supports=[];max_identity=0.
    for rec,pol in zip(records,policies):
        assert rec['case_id']==pol['case_id'];idx=rec['case_id'];d=frames[rec['cohort'],rec['meter'],rec['day']]
        for kind in ['dominance','reference']:
            evaluated=evaluate_case(rec,pol[kind],d);max_identity=max(max_identity,evaluated['width_identity_error_scaled'])
            for key in ['actual_width','certification','queries']:cases.loc[idx,kind+'_'+key]=evaluated[key]
            cases.loc[idx,kind+'_worst_width']=pol[kind]['primary_normalized']*rec['initial_width']
            for supp in evaluated['support']:supports.append({'case_id':idx,'method':kind,**supp})
    fields=['deterministic_worst_width','randomized_worst_expected_width','deterministic_actual_width','randomized_expected_actual_width',
            'deterministic_certification','randomized_expected_certification','dominance_worst_width','reference_worst_width',
            'dominance_actual_width','reference_actual_width','dominance_certification','reference_certification','dominance_queries','reference_queries']
    meters=[]
    for (cohort,meter),group in cases.groupby(['cohort','meter']):
        row={'cohort':cohort,'meter':meter,'cases':len(group)};den=float(group.initial_width.sum())
        for key in fields: row[key]=float(group[key].sum()/den) if 'width' in key else float(group[key].mean())
        meters.append(row)
    meterdf=pd.DataFrame(meters);cohorts=[]
    for cohort,group in meterdf.groupby('cohort'):
        cohorts.append({'cohort':cohort,'meters':len(group),'cases':int(group.cases.sum()),**{key:float(group[key].mean()) for key in fields}})
    positive=cases[cases.initial_width>0];counts={}
    for kind in ['dominance','reference']:
        difference=positive[kind+'_actual_width']-positive.randomized_expected_actual_width
        tolerance=1e-9*np.maximum(1.,positive.initial_width)
        counts[kind]={'realized_improved_vs_original':int((difference < -tolerance).sum()),
                      'realized_worsened_vs_original':int((difference > tolerance).sum()),
                      'realized_tied_vs_original':int((np.abs(difference)<=tolerance).sum()),
                      'secondary_strictly_improved':sum(p[kind]['secondary_normalized']<p[kind]['secondary_original']-1e-9 for p in policies),
                      'max_primary_gap':max(p[kind]['primary_lower_bound_gap'] for p in policies),
                      'max_dominance_violation':max(p[kind]['maximum_expected_width_difference_normalized'] for p in policies),
                      'max_secondary_primal_violation':max(p[kind]['primal_violation'] for p in policies),
                      'max_secondary_dual_residual':max(p[kind]['dual_stationarity_error'] for p in policies),
                      'max_secondary_duality_gap':max(p[kind]['secondary_duality_gap'] for p in policies)}
    assert counts['dominance']['realized_worsened_vs_original']==0
    assert sha(selected)==selection_hash
    for p in inputs: assert sha(p)==pins[str(p.relative_to(ROOT))]
    cases.to_csv(HERE/'cases.csv',index=False);meterdf.to_csv(HERE/'meters.csv',index=False)
    pd.DataFrame(cohorts).to_csv(HERE/'cohorts.csv',index=False)
    pd.DataFrame(supports).to_csv(HERE/'support.csv',index=False)
    report={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),'seconds':time.perf_counter()-started,
            'case_count':len(cases),'positive_cases':len(records),'secondary_lp_count':2*len(records),'cohort_summary':cohorts,
            'checks':counts,'maximum_width_identity_error_scaled':max_identity,'exact_example':example,
            'selection_completed_before_reference_read':True,'selection_sha256':selection_hash,'source_hashes':pins,
            'script_sha256':sha(Path(__file__)),'support_rows':len(supports)}
    (HERE/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
