"""Independent audit from distributed public targets, predictions and LP traces.

No raw downloads or fitted models are needed. Rebuild the allowed persistence
copies and exact-total closure, check every case/support endpoint, and compare
each archived finite-game optimum with the independent compact formulation.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, itertools, json, sys, time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'work/new_direction_randomized'
sys.path.insert(0,str(ROOT/'work/randomized_recovery_root'))
from compact_randomized import solve_compact

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b,scale=1.):
    assert abs(a-b)<=2e-7*max(1.,abs(a),abs(b),scale),(a,b)
def sign(lo,hi):
    tol=1e-9*max(1.,abs(lo),abs(hi))
    return 1 if lo>tol else -1 if hi < -tol else 0

def main():
    started=time.perf_counter()
    data=pd.read_csv(ROOT/'outputs/review_frozen_forecasts.csv')
    data=data[data.cohort.isin(['household','portugal'])]
    rows=pd.read_csv(HERE/'cases.csv').set_index('case_id')
    reports={r['case_id']:r for r in map(json.loads,(HERE/'lp_solutions.jsonl').read_text().splitlines())}
    support=pd.read_csv(HERE/'support.csv')
    supports={k:g for k,g in support.groupby('case_id')}
    models=['daily','ridge','hist_gradient_boosting','mlp']
    pairs=list(itertools.combinations(models,2))
    checked=0; batch_checks=0; compact_checks=0; free_copy_checks=0
    max_compact_error=0.; copy_trace=[]
    mixture_checks=0;max_mixture_primal_violation=0.;max_mixture_dual_violation=0.;max_mixture_gap=0.
    for (cohort,meter),meter_data in data.groupby(['cohort','meter']):
        saved=dict(zip(meter_data.timestamp,meter_data.daily))
        for day,d in meter_data.groupby(meter_data.timestamp.str[:10]):
            d=d.sort_values('timestamp');assert len(d)==24
            y=d.truth_kwh.to_numpy(); totals=y.reshape(4,6).sum(axis=1)
            rng=np.random.default_rng(np.random.SeedSequence([1103,int(pd.Timestamp(day).value//86400000000000),1]))
            start=int(rng.integers(0,19)); visible=y.copy();visible[start:start+6]=np.nan
            copied=0;deduced=0
            for i,stamp in enumerate(d.timestamp):
                key=(pd.Timestamp(stamp)+pd.Timedelta(days=1)).isoformat()
                if np.isnan(visible[i]) and key in saved:
                    visible[i]=saved[key];assert visible[i]==y[i]
                    copied+=1;free_copy_checks+=1
                    copy_trace.append({'cohort':cohort,'meter':meter,'target_timestamp':stamp,'forecast_row_timestamp':key,'model':'daily','value':visible[i]})
            for g,total in enumerate(totals):
                ids=np.arange(6*g,6*g+6);missing=ids[np.isnan(visible[ids])]
                residual=max(0.,float(total-np.nansum(visible[ids])))
                if len(missing)==1 or (len(missing)>0 and residual==0):
                    visible[missing]=residual if len(missing)==1 else 0.;deduced+=len(missing)
            for pair,(ma,mb) in enumerate(pairs):
                key=f'{cohort}/{meter}/{day}/{pair}';row=rows.loc[key]
                a=d[ma].to_numpy();b=d[mb].to_numpy();c=2*(b-a)/24
                assert row.free_copied==copied and row.free_deduced==deduced
                blocks=[]
                for g,total in enumerate(totals):
                    ids=np.arange(6*g,6*g+6);missing=ids[np.isnan(visible[ids])]
                    e=max(0.,float(total-np.nansum(visible[ids])))
                    if len(missing)>1 and e>0 and np.ptp(c[missing])>0:
                        blocks.append((missing,c[missing],e))
                initial=sum(e*np.ptp(co) for ids,co,e in blocks);close(initial,row.initial_width)
                reference=float(np.mean((a-y)**2-(b-y)**2))
                def interval(query):
                    assert len(query)<=2 and all(np.isnan(visible[i]) for i in query)
                    v=visible.copy();v[list(query)]=y[list(query)]
                    obs=np.isfinite(v)
                    lo=hi=float(np.mean(a*a-b*b)+np.dot(c[obs],v[obs]))
                    for g,total in enumerate(totals):
                        ids=np.arange(6*g,6*g+6);missing=ids[~obs[ids]]
                        e=max(0.,float(total-np.nansum(v[ids])))
                        if len(missing):lo+=e*float(c[missing].min());hi+=e*float(c[missing].max())
                    tol=2e-7*max(1.,abs(lo),abs(hi),abs(reference))
                    assert lo-tol<=reference<=hi+tol
                    assert not sign(lo,hi) or sign(lo,hi)==int(np.sign(reference))
                    return max(0.,hi-lo),int(bool(sign(lo,hi))),lo,hi
                if initial>0:
                    rec=reports[key];assert len(blocks)==len(rec['blocks'])
                    for (ids,cs,e),old in zip(blocks,rec['blocks']):
                        assert list(ids)==old['indices'];np.testing.assert_allclose(cs,old['coefficients'],atol=1e-12,rtol=1e-12);close(e,old['energy'])
                    mask=sum(1<<int(i) for i in np.flatnonzero(np.isfinite(visible)))
                    assert mask==rec['observed_mask']
                    solved=solve_compact([co for ids,co,e in blocks],[e for ids,co,e in blocks],2)
                    close(solved['value'],rec['randomized_worst_expected_width'],initial)
                    max_compact_error=max(max_compact_error,abs(solved['value']-rec['randomized_worst_expected_width'])/max(1.,initial))
                    compact_checks+=1
                    # Reconstruct the finite game directly from archived blocks;
                    # do not trust either the solver's objective or its residuals.
                    probabilities=np.asarray(rec['probabilities'],dtype=float)
                    batches=[tuple(q) for q in rec['batches']]
                    assert len(batches)==len(probabilities)==len(set(batches))
                    assert np.isfinite(probabilities).all() and np.min(probabilities)>=0.
                    close(float(probabilities.sum()),1.)
                    block_sets=[set(int(i) for i in ids) for ids,co,e in blocks]
                    all_indices=set().union(*block_sets)
                    expected_batches=set()
                    for k in range(3):
                        for q in itertools.combinations(sorted(all_indices),k):
                            if not any(group.issubset(q) for group in block_sets):expected_batches.add(q)
                    assert set(batches)==expected_batches
                    matrix=[];matrix_groups=[];matrix_indices=[]
                    for group,(ids,cs,e) in enumerate(blocks):
                        for coordinate in ids:
                            coefficients=[]
                            for query in batches:
                                remaining=[float(cs[j]) for j,i in enumerate(ids) if int(i) not in query]
                                span=max(remaining)-min(remaining) if len(remaining)>1 else 0.
                                coefficients.append(e*span/initial if int(coordinate) not in query else 0.)
                            matrix.append(coefficients);matrix_groups.append(group);matrix_indices.append(int(coordinate))
                    matrix=np.asarray(matrix);matrix_groups=np.asarray(matrix_groups)
                    assert matrix_indices==rec['matrix_coordinate_indices']
                    assert matrix_groups.tolist()==rec['matrix_group_indices']
                    expected_coefficients=matrix@probabilities
                    envelopes=np.asarray(rec['group_envelopes']);dual=np.asarray(rec['dual_weights'])
                    assert len(envelopes)==len(blocks) and len(dual)==len(matrix)
                    assert np.isfinite(envelopes).all() and np.isfinite(dual).all()
                    assert np.min(envelopes)>=0.
                    mixture_value=sum(float(expected_coefficients[matrix_groups==g].max()) for g in range(len(blocks)))
                    primal_violation=max(0.,float(np.max(expected_coefficients-envelopes[matrix_groups])),abs(float(probabilities.sum())-1.))
                    dual_value=float(rec['dual_normalized_objective'])
                    dual_violation=max(0.,-float(dual.min()),max(float(dual[matrix_groups==g].sum())-1. for g in range(len(blocks))),float(np.max(dual_value-matrix.T@dual)))
                    gap=abs(mixture_value-dual_value)
                    assert primal_violation<=1e-8 and dual_violation<=1e-8 and gap<=1e-8
                    close(mixture_value*initial,rec['randomized_worst_expected_width'],initial)
                    close(mixture_value*initial,row.randomized_worst_expected_width,initial)
                    close(mixture_value,rec['primal_normalized_objective'])
                    support_rows=supports[key]
                    declared_support={q:float(p) for q,p in zip(batches,probabilities) if p>0.}
                    saved_support={tuple(json.loads(s.query)):float(s.probability) for _,s in support_rows.iterrows()}
                    assert len(saved_support)==len(support_rows)==rec['support_size']
                    assert set(saved_support)==set(declared_support)
                    for q,p in declared_support.items():close(p,saved_support[q])
                    mixture_checks+=1
                    max_mixture_primal_violation=max(max_mixture_primal_violation,primal_violation)
                    max_mixture_dual_violation=max(max_mixture_dual_violation,dual_violation)
                    max_mixture_gap=max(max_mixture_gap,gap)
                    expected_width=expected_cert=expected_queries=0.;p_sum=0.
                    for _,s in supports[key].iterrows():
                        q=json.loads(s.query);assert s.queries==len(q);w,cert,lo,hi=interval(q)
                        close(w,s.actual_width,initial);close(lo,s.lower,initial);close(hi,s.upper,initial);assert cert==s.certified
                        expected_width+=s.probability*w;expected_cert+=s.probability*cert;expected_queries+=s.probability*len(q);p_sum+=s.probability;batch_checks+=1
                    close(p_sum,1.);close(expected_width,row.randomized_expected_actual_width,initial)
                    close(expected_cert,row.randomized_expected_certification);close(expected_queries,row.randomized_expected_queries)
                    for name in ['deterministic','greedy']:
                        w,cert,_,_=interval(rec[name+'_queries'])
                        close(w,row[name+'_actual_width'],initial);assert cert==row[name+'_certification']
                        assert row[name+'_queries']==len(rec[name+'_queries'])
                    # Full deterministic enumeration independently checks its baseline.
                    minimum=float('inf')
                    indices=[int(i) for ids,co,e in blocks for i in ids]
                    for k in range(3):
                        for q in itertools.combinations(indices,k):
                            value=0.
                            for ids,co,e in blocks:
                                remain=[co[j] for j,i in enumerate(ids) if i not in q]
                                if len(remain)>1:value+=e*np.ptp(remain)
                            minimum=min(minimum,value)
                    close(minimum,row.deterministic_worst_width,initial)
                else:
                    w,cert,_,_=interval(())
                    close(w,0.,initial)
                    for name in ['deterministic','greedy','randomized_expected']:
                        assert row[name+'_certification']==cert
                checked+=1
    assert checked==20736 and compact_checks==1074 and batch_checks==2341
    summary=json.loads((HERE/'result.json').read_text())
    for filename,h in summary['output_hashes'].items():assert sha(HERE/filename)==h
    # Regenerate all reported cohort macro summaries from the individual cases.
    frame=rows.reset_index();fields=[c for c in frame if any(c.startswith(p) for p in ['randomized_','deterministic_','greedy_']) and c not in ['randomized_worst_expected_width']]+['randomized_worst_expected_width','initial_width']
    fields=list(dict.fromkeys(fields))
    aggregate_checks=0
    for cohort,group in frame.groupby('cohort'):
        expected=next(s for s in summary['cohort_summary'] if s['cohort']==cohort and s['scope']=='all_cases')
        for col in fields:
            close(float(group.groupby('meter')[col].mean().mean()),expected['mean_'+col]);aggregate_checks+=1
        for col in [c for c in fields if 'width' in c and c!='initial_width']:
            summed=group.groupby('meter')[[col,'initial_width']].sum()
            ratio=float((summed[col]/summed.initial_width).fillna(0.).mean())
            close(ratio,expected['fraction_'+col]);aggregate_checks+=1
    pd.DataFrame(copy_trace).to_csv(HERE/'independent_free_copy_trace.csv',index=False)
    report={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),'cases':checked,'compact_versus_finite_game_checks':compact_checks,'every_positive_support_checked':batch_checks,'permitted_copy_checks':free_copy_checks,'cohort_aggregate_checks':aggregate_checks,'max_normalized_compact_error':max_compact_error,'saved_mixture_primal_dual_linkage_checks':mixture_checks,'max_saved_mixture_primal_violation':max_mixture_primal_violation,'max_saved_mixture_dual_violation':max_mixture_dual_violation,'max_saved_mixture_primal_dual_gap':max_mixture_gap,'wall_seconds':time.perf_counter()-started,'source_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [Path(__file__),ROOT/'outputs/review_frozen_forecasts.csv',HERE/'cases.csv',HERE/'support.csv',HERE/'lp_solutions.jsonl',HERE/'result.json',ROOT/'work/randomized_recovery_root/compact_randomized.py']},'scope':'Distributed public UCI inputs; no fit, raw download, or independent optimization of randomized adaptive policies. Every case and positive support checked, not a sample. Saved support probabilities and queries are linked bidirectionally to the finite-game LP; its matrix, worst expected mixture objective, primal and dual feasibility, and gap are reconstructed independently.'}
    (HERE/'independent_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
