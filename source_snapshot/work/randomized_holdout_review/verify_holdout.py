"""Independent arithmetic replay of frozen batches; no policy optimizer imports."""
from pathlib import Path
import hashlib,json,math,itertools
from datetime import datetime,timezone
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lines(name):
    with (HERE/name).open(encoding='utf-8') as f:
        for line in f:yield json.loads(line)
def close(a,b,scale=1.):
    assert np.isfinite(a) and np.isfinite(b)
    assert abs(a-b)<=1e-8*max(1.,scale,abs(a),abs(b)),(a,b,scale)
def main():
    result=json.loads((HERE/'result.json').read_text());selected=json.loads((HERE/'selection_complete.json').read_text())
    for name,h in result['source_hashes'].items():assert sha(ROOT/name)==h,name
    for name,h in result['output_hashes'].items():assert sha(HERE/name)==h,name
    assert sha(HERE/'protocol.txt')==result['protocol_sha256'] and sha(HERE/'policies.jsonl')==selected['policy_sha256']
    source=ROOT/'outputs/study_holdout_consumers_predictions.csv';data=pd.read_csv(source);data['day']=data.timestamp.str[:10]
    assert set(data.cohort)=={'portugal_new_consumers'} and data.groupby(['cohort','meter']).ngroups==30
    frames={(c,m,d):f.sort_values('timestamp') for (c,m,d),f in data.groupby(['cohort','meter','day'])}
    lookup={(c,m,str(pd.Timestamp(t)-pd.Timedelta(days=1))):float(v) for c,m,t,v in data[['cohort','meter','timestamp','daily']].itertuples(index=False,name=None)}
    designs={};days=0
    for d in lines('selection_inputs.jsonl'):
        key=(d['cohort'],d['meter'],d['day']);frame=frames[key];truth=frame.truth_kwh.to_numpy()
        start=int(np.random.default_rng(np.random.SeedSequence([1103,int(pd.Timestamp(d['day']).value//86400000000000),1])).integers(0,19));assert start==d['mask_start']
        np.testing.assert_allclose(frame[['daily','ridge','hist_gradient_boosting','mlp']].to_numpy().T,d['predictions'],rtol=0,atol=0)
        observed=truth.copy();observed[start:start+6]=np.nan;copied=[];deduced=[]
        for i,t in enumerate(frame.timestamp):
            k=(key[0],key[1],str(pd.Timestamp(t)))
            if np.isnan(observed[i]) and k in lookup:observed[i]=lookup[k];copied.append(i)
        totals=truth.reshape(4,6).sum(axis=1);np.testing.assert_allclose(totals,d['totals'],rtol=0,atol=1e-10)
        for g,total in enumerate(totals):
            ids=np.arange(6*g,6*g+6);missing=ids[np.isnan(observed[ids])];residual=max(0.,float(total-np.nansum(observed[ids])))
            if len(missing) and (len(missing)==1 or residual==0):observed[missing]=residual if len(missing)==1 else 0.;deduced.extend(missing.tolist())
        np.testing.assert_allclose(observed,np.asarray(d['visible'],float),rtol=1e-12,atol=1e-8,equal_nan=True)
        assert copied==d['copied'] and deduced==d['deduced'];designs[key]=d;days+=1
    assert days==3210
    cases=pd.read_csv(HERE/'cases.csv').set_index('case_id');count=positive=support=0;maxerr=0.
    for rec in lines('policies.jsonl'):
        count+=1;key=(rec['cohort'],rec['meter'],rec['day']);d=designs[key];frame=frames[key];row=cases.loc[rec['case_id']]
        a=frame[rec['model_a']].to_numpy();b=frame[rec['model_b']].to_numpy();truth=frame.truth_kwh.to_numpy();c=2*(b-a)/24;visible=np.asarray(d['visible'],float);totals=np.asarray(d['totals']);initial=rec['initial_width']
        reference=float(np.mean((a-truth)**2-(b-truth)**2))
        def interval(q):
            assert len(q)<=2 and len(set(q))==len(q) and all(np.isnan(visible[i]) for i in q)
            obs=visible.copy();obs[q]=truth[q];known=np.isfinite(obs)
            lo=hi=float(np.mean(a*a-b*b)+np.dot(c[known],obs[known]))
            for g,total in enumerate(totals):
                ids=np.arange(6*g,6*g+6);rem=ids[~known[ids]];energy=max(0.,float(total-obs[ids[known[ids]]].sum()))
                if len(rem):lo+=energy*float(c[rem].min());hi+=energy*float(c[rem].max())
            eps=1e-9*max(1.,abs(lo),abs(hi));sgn=1 if lo>eps else -1 if hi < -eps else 0
            assert lo-1e-7*max(1.,abs(reference))<=reference<=hi+1e-7*max(1.,abs(reference))
            assert not sgn or sgn==int(np.sign(reference))
            return max(0.,hi-lo),int(bool(sgn))
        expected_blocks=[]
        for g,total in enumerate(totals):
            idx=[i for i in range(6*g,6*g+6) if np.isnan(visible[i])]
            if idx:expected_blocks.append((idx,c[idx],max(0.,float(total-np.nansum(visible[6*g:6*g+6])))))
        assert len(expected_blocks)==len(rec['blocks'])
        for (idx,coeff,energy),bl in zip(expected_blocks,rec['blocks']):
            assert idx==bl['indices'];np.testing.assert_allclose(coeff,bl['coefficients'],rtol=0,atol=0);close(energy,bl['energy'])
        close(sum(energy*(max(coeff)-min(coeff)) for idx,coeff,energy in expected_blocks),initial,initial)
        if initial<=0:
            actual,cert=interval([])
            close(actual,0.,initial)
            for name in ('randomized','original_primary'):close(row[name+'_expected_actual_width'],0.);close(row[name+'_expected_certification'],cert);close(row[name+'_expected_queries'],0.)
            for name in ('deterministic','greedy'):close(row[name+'_actual_width'],0.);close(row[name+'_certification'],cert);close(row[name+'_queries'],0.)
            continue
        positive+=1;blocks=rec['blocks'];queries=rec['batches'];ids=[i for bl in blocks for i in bl['indices']];groups=np.array([g for g,bl in enumerate(blocks) for i in bl['indices']]);matrix=np.zeros((len(ids),len(queries)));offset=0
        for g,bl in enumerate(blocks):
            coeff=dict(zip(bl['indices'],bl['coefficients']))
            for j,q in enumerate(queries):
                retained=[i for i in bl['indices'] if i not in q];assert retained
                width=max(coeff[i] for i in retained)-min(coeff[i] for i in retained)
                for k,i in enumerate(bl['indices']):
                    if i in retained:matrix[offset+k,j]=bl['energy']*width/initial
            offset+=len(bl['indices'])
        dual=np.array(rec['dual_weights']);dualobj=rec['dual_normalized_objective']
        assert min(dual)>=-2e-7 and all(dual[groups==g].sum()<=1+2e-7 for g in range(len(blocks)))
        assert (matrix.T@dual).min()>=dualobj-2e-7
        close(rec['compact_check']['value']/initial,dualobj)
        for name,probs in (('randomized',rec['reference']['probabilities']),('original_primary',rec['probabilities'])):
            probs=np.array(probs);assert np.min(probs)>=0;close(probs.sum(),1.)
            z=matrix@probs;value=sum(z[groups==g].max() for g in range(len(blocks)));assert abs(value-dualobj)<=2e-7
            close(value*initial,row[name+'_worst_expected_width'],initial)
            ew=ec=eq=0.
            for q,p in zip(queries,probs):
                if p<=0:continue
                w,cert=interval(q);ew+=p*w;ec+=p*cert;eq+=p*len(q);support+=1
            close(ew,row[name+'_expected_actual_width'],initial);close(ec,row[name+'_expected_certification']);close(eq,row[name+'_expected_queries'])
            maxerr=max(maxerr,abs(ew-row[name+'_expected_actual_width'])/max(1.,initial))
        for name in ('deterministic','greedy'):
            q=rec[name+'_queries'];w,cert=interval(q);close(w,row[name+'_actual_width'],initial);close(cert,row[name+'_certification']);close(len(q),row[name+'_queries'])
    assert count==19260 and positive==899 and support==result['positive_probability_batches_checked']
    report=dict(status='PASS',check_kind='Independent arithmetic and saved-dual verification; no recovery implementation or optimizer imported',consumers=30,meter_days=days,cases=count,positive_cases=positive,positive_probability_batches=support,maximum_actual_width_discrepancy_scaled=maxerr,source_hashes=result['source_hashes'],protocol_sha256=result['protocol_sha256'],policy_sha256=selected['policy_sha256'],result_sha256=sha(HERE/'result.json'),checker_sha256=sha(__file__),checked_utc=datetime.now(timezone.utc).isoformat())
    (HERE/'independent_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
