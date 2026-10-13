"""Frozen finite-game test; never edits the original study or manuscript."""
from __future__ import annotations
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import sys, itertools, hashlib, json, time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs'; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from study_recovery import Block, prepare_blocks, optimal_queries, baseline_queries, worst_width, pair_interval, decision
from study_archive_access import persistence_lookup, reveal_from_archive, DAY_NS
from study_period_archive import close_observations
from run_energy_rank_study import MODELS, PAIRS

BUDGET=2; SEED=1103; CHECK_TOL=2e-7
SOURCES=['study_predictions.csv','study_summary.json','study_recovery.py',
         'study_archive_access.py','study_period_archive.py','run_energy_rank_study.py',
         'study_period_archive.json','study_period_archive_cases.csv','revised_manuscript.tex']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def batches(blocks,budget):
    indices=sorted(i for b in blocks for i in b.indices)
    result=[]
    for k in range(min(budget,len(indices))+1):
        for query in itertools.combinations(indices,k):
            q=set(query)
            if all(not set(b.indices).issubset(q) for b in blocks):result.append(query)
    return result

def game_matrix(blocks,queries):
    initial=worst_width(blocks,())
    assert initial>0
    ids=[i for b in blocks for i in b.indices]
    group_ids=[g for g,b in enumerate(blocks) for _ in b.indices]
    rows={i:j for j,i in enumerate(ids)}
    matrix=np.zeros((len(ids),len(queries)))
    for col,query in enumerate(queries):
        chosen=set(query)
        for block in blocks:
            remain=[(i,c) for i,c in zip(block.indices,block.coefficients) if i not in chosen]
            width=max((c for i,c in remain),default=0)-min((c for i,c in remain),default=0)
            for i,c in remain:matrix[rows[i],col]=block.energy*width/initial
    return matrix,np.array(group_ids,dtype=int),ids,initial

def pricing_oracle(blocks,weights,budget):
    """Exact cost=sum_g range(retained)*sum(retained dual weights)."""
    states={0:(0.,())}
    for block in blocks:
        ordered=sorted(zip(block.coefficients,block.indices));m=len(ordered)
        options=[]
        for k in range(min(budget,m-1)+1):
            retain=m-k
            if retain==1:
                query=tuple(sorted(i for _,i in ordered[:-1]));options.append((0.,query));continue
            best=None
            for left in range(m):
                for right in range(left+retain-1,m):
                    interior=sorted(ordered[left+1:right],key=lambda ci:(weights[ci[1]],ci[1]))[:retain-2]
                    kept=[ordered[left],ordered[right],*interior]
                    cost=(ordered[right][0]-ordered[left][0])*sum(weights[i] for c,i in kept)
                    kept_ids={i for c,i in kept}
                    query=tuple(sorted(i for c,i in ordered if i not in kept_ids))
                    candidate=(float(cost),query)
                    if best is None or candidate<best:best=candidate
            options.append(best)
        nxt={}
        for used,(value,query) in states.items():
            for k,(value2,query2) in enumerate(options[:budget-used+1]):
                candidate=(value+value2,tuple(sorted(query+query2)))
                if used+k not in nxt or candidate<nxt[used+k]:nxt[used+k]=candidate
        states=nxt
    value,used,query=min((v,k,q) for k,(v,q) in states.items())
    return value,query

def solve_game(blocks,budget):
    start=time.perf_counter();queries=batches(blocks,budget)
    matrix,groups,ids,initial=game_matrix(blocks,queries)
    nq=len(queries);ng=len(blocks)
    inequalities=np.zeros((len(ids),nq+ng));inequalities[:,:nq]=matrix
    inequalities[np.arange(len(ids)),nq+groups]=-1
    objective=np.r_[np.zeros(nq),np.ones(ng)]
    equality=np.r_[np.ones(nq),np.zeros(ng)][None,:]
    result=linprog(objective,A_ub=inequalities,b_ub=np.zeros(len(ids)),A_eq=equality,b_eq=[1.],
                   bounds=(0,None),method='highs-ds',options={'dual_feasibility_tolerance':1e-9,
                   'primal_feasibility_tolerance':1e-9})
    if not result.success:raise RuntimeError(result.message)
    raw=result.x[:nq];p=np.maximum(raw,0.);p/=p.sum()
    dual=-np.asarray(result.ineqlin.marginals);dual_objective=float(result.eqlin.marginals[0])
    marginals=matrix@p
    envelopes=np.array([marginals[groups==g].max() for g in range(ng)])
    value=float(envelopes.sum())
    raw_primal=max(0.,float(np.max(inequalities@result.x)),abs(float(raw.sum()-1.)),float(-np.min(result.x)))
    dual_slack=np.array([dual[groups==g].sum() for g in range(ng)])
    dual_error=max(0.,float(-dual.min()),float(dual_slack.max()-1.),float(dual_objective-(matrix.T@dual).min()))
    gap=abs(value-dual_objective)
    assert max(raw_primal,dual_error,gap)<=CHECK_TOL,(raw_primal,dual_error,gap)
    weights={i:max(0.,float(dual[j]))*blocks[groups[j]].energy/initial for j,i in enumerate(ids)}
    oracle_value,oracle_query=pricing_oracle(blocks,weights,budget)
    exhaustive=float((matrix.T@np.maximum(dual,0.)).min())
    oracle_error=abs(oracle_value-exhaustive)
    assert oracle_error<=CHECK_TOL,(oracle_value,exhaustive)
    det=optimal_queries(blocks,budget);greedy=baseline_queries(blocks,budget,'greedy_width_reduction')
    det_value=worst_width(blocks,det)/initial;greedy_value=worst_width(blocks,greedy)/initial
    assert value<=det_value+CHECK_TOL and det_value<=greedy_value+CHECK_TOL
    report={'initial_width':initial,'randomized_worst_expected_width':value*initial,
      'deterministic_worst_width':det_value*initial,'greedy_worst_width':greedy_value*initial,
      'primal_normalized_objective':value,'dual_normalized_objective':dual_objective,
      'primal_violation':raw_primal,'dual_violation':dual_error,'normalized_gap':gap,
      'pricing_oracle_error':oracle_error,'pricing_oracle_query':oracle_query,
      'matrix_coordinate_indices':ids,'matrix_group_indices':groups.tolist(),
      'group_envelopes':envelopes.tolist(),'raw_group_envelopes':result.x[nq:].tolist(),
      'dual_weights':dual.tolist(),'raw_probability_minimum':float(raw.min()),
      'probabilities':p.tolist(),'batches':[list(q) for q in queries],
      'deterministic_queries':det,'greedy_queries':greedy,
      'support_size':int(np.count_nonzero(p)),'expected_queries':float(sum(pi*len(q) for pi,q in zip(p,queries))),
      'seconds':time.perf_counter()-start}
    return report

def verify_synthetic():
    rng=np.random.default_rng(1729);pricing_errors=[]
    for trial in range(64):
        blocks=[];weights={};offset=0
        for group in range(1+trial%3):
            n=int(rng.integers(2,7));ids=tuple(range(offset,offset+n));offset+=n
            cs=tuple(float(x) for x in rng.integers(-4,7,size=n))
            blocks.append(Block(ids,cs,float(rng.integers(1,6))))
            weights.update({i:float(rng.uniform(0,3)) for i in ids})
        budget=trial%5
        def cost(query):
            q=set(query);value=0.
            for b in blocks:
                remain=[(i,c) for i,c in zip(b.indices,b.coefficients) if i not in q]
                if len(remain)>1:value+=(max(c for i,c in remain)-min(c for i,c in remain))*sum(weights[i] for i,c in remain)
            return value
        exact=min(cost(q) for q in batches(blocks,budget));got,_=pricing_oracle(blocks,weights,budget)
        error=abs(exact-got);pricing_errors.append(error);assert error<=1e-10*max(1.,exact)
    example=(Block((0,1,2,3),(0,1,3,4),1.),)
    report=solve_game(example,2)
    np.testing.assert_allclose([report['deterministic_worst_width'],report['randomized_worst_expected_width']],[1.,.5],atol=1e-9,rtol=0)
    return {'synthetic_pricing_cases':64,'max_pricing_error':max(pricing_errors),'analytic_example':report}

def posterior(a,b,visible,totals,truth,query):
    recovered=visible.copy();assert all(np.isnan(recovered[i]) for i in query)
    recovered[list(query)]=truth[list(query)]
    lo,hi=pair_interval(a,b,recovered,totals)
    reference=float(np.mean((a-truth)**2-(b-truth)**2))
    tol=1e-8*max(1.,abs(reference),abs(lo),abs(hi))
    assert lo<=reference+tol and reference<=hi+tol
    sign=decision(lo,hi)
    assert not sign or sign==int(np.sign(reference))
    return max(0.,float(hi-lo)),int(bool(sign)),lo,hi

def summarize(cases):
    fields=['initial_width','randomized_worst_expected_width','deterministic_worst_width','greedy_worst_width',
            'randomized_expected_actual_width','deterministic_actual_width','greedy_actual_width',
            'randomized_expected_queries','deterministic_queries','greedy_queries',
            'randomized_expected_certification','deterministic_certification','greedy_certification']
    meter_rows=[]
    for (cohort,meter),g in cases.groupby(['cohort','meter']):
        for scope in ('all_cases','positive_initial_width'):
            part=g if scope=='all_cases' else g[g.initial_width>0]
            row={'cohort':cohort,'meter':meter,'scope':scope,'cases':len(part),'lp_cases':int(part.lp_solved.sum())}
            row.update({f'mean_{key}':float(part[key].mean()) if len(part) else 0. for key in fields})
            initial=float(part.initial_width.sum())
            row.update({f'fraction_{key}':float(part[key].sum()/initial) if initial else 0.
                        for key in fields if 'width' in key and key!='initial_width'})
            row['summed_initial_width']=initial
            row['summed_deterministic_worst_width']=float(part.deterministic_worst_width.sum())
            row['summed_randomized_worst_expected_width']=float(part.randomized_worst_expected_width.sum())
            row['summed_deterministic_actual_width']=float(part.deterministic_actual_width.sum())
            row['summed_randomized_expected_actual_width']=float(part.randomized_expected_actual_width.sum())
            meter_rows.append(row)
    meters=pd.DataFrame(meter_rows);cohort_rows=[]
    for (cohort,scope),g in meters.groupby(['cohort','scope']):
        row={'cohort':cohort,'scope':scope,'meters':len(g),'cases':int(g.cases.sum()),'lp_cases':int(g.lp_cases.sum())}
        row.update({c:float(g[c].mean()) for c in meters if c.startswith('mean_') or c.startswith('fraction_')})
        for c in [c for c in meters if c.startswith('summed_')]:row[c]=float(g[c].sum())
        cohort_rows.append(row)
    pair_rows=[]
    for keys,g in cases.groupby(['cohort','model_a','model_b']):
        row=dict(zip(['cohort','model_a','model_b'],keys));row.update(cases=len(g),lp_cases=int(g.lp_solved.sum()))
        row.update({f'mean_{c}':float(g[c].mean()) for c in fields});pair_rows.append(row)
    return meters,pd.DataFrame(cohort_rows),pd.DataFrame(pair_rows)

def main():
    start=time.perf_counter();protocol=HERE/'protocol.txt';assert protocol.exists()
    pinned={f:sha(OUT/f) for f in SOURCES};protocol_hash=sha(protocol)
    synthetic=verify_synthetic()
    data=pd.read_csv(OUT/'study_predictions.csv');data=data[data.cohort.isin(['portugal','household'])].copy()
    assert data.groupby(['cohort','meter']).ngroups==31
    cases=[];solutions=0;support_rows=[];max_residuals={k:0. for k in ['primal_violation','dual_violation','normalized_gap','pricing_oracle_error']}
    checked_supports=0;max_expected_identity_error=0.;free_values=0;missing_values=0
    with (HERE/'lp_solutions.jsonl').open('w',encoding='utf-8') as lp_file:
        for (cohort,meter),frame in data.groupby(['cohort','meter'],sort=True):
            lookup=persistence_lookup(frame[['timestamp','daily']])
            for day,d in frame.groupby(frame.timestamp.str[:10],sort=True):
                d=d.sort_values('timestamp');assert len(d)==24
                truth=d.truth_kwh.to_numpy();pred=d[MODELS].to_numpy().T
                rng=np.random.default_rng(np.random.SeedSequence([SEED,int(pd.Timestamp(day).value//DAY_NS),1]))
                missing_start=int(rng.integers(0,19));visible=truth.copy();visible[missing_start:missing_start+6]=np.nan
                totals=truth.reshape(4,6).sum(axis=1)
                visible,copied=reveal_from_archive(d.timestamp.tolist(),visible,lookup)
                np.testing.assert_allclose(visible[list(copied)],truth[list(copied)],rtol=0,atol=0)
                visible,deduced,_,_=close_observations(visible,totals,6,0)
                free_values+=len(copied)+len(deduced);missing_values+=6
                for pair,(ai,bi) in enumerate(PAIRS):
                    a,b=pred[ai],pred[bi];coefficients=2*(b-a)/24
                    blocks=tuple(prepare_blocks(coefficients,visible,totals))
                    initial=worst_width(blocks,());identity={'cohort':cohort,'meter':meter,'day':day,'seed':SEED,'gap_hours':6,
                             'budget':BUDGET,'model_a':MODELS[ai],'model_b':MODELS[bi]}
                    case_id=f'{cohort}/{meter}/{day}/{pair}'
                    row=dict(identity,case_id=case_id,initial_width=initial,free_copied=len(copied),free_deduced=len(deduced),
                             remaining_unknown=int(np.isnan(visible).sum()),lp_solved=initial>0)
                    if initial>0:
                        solution=solve_game(blocks,BUDGET);solutions+=1
                        for key in max_residuals:max_residuals[key]=max(max_residuals[key],solution[key])
                        record={'case_id':case_id,**identity,'observed_mask':sum(1<<int(i) for i in np.flatnonzero(np.isfinite(visible))),
                                'blocks':[{'indices':list(bl.indices),'coefficients':list(bl.coefficients),'energy':bl.energy} for bl in blocks],**solution}
                        lp_file.write(json.dumps(record,allow_nan=False)+'\n')
                        expected_width=0.;expected_cert=0.
                        for query,prob in zip(solution['batches'],solution['probabilities']):
                            if prob<=0:continue
                            actual,cert,lo,hi=posterior(a,b,visible,totals,truth,query);checked_supports+=1
                            chosen=set(query);direct=0.
                            for block in blocks:
                                remain=[(i,c) for i,c in zip(block.indices,block.coefficients) if i not in chosen]
                                if len(remain)>1:direct+=(max(c for i,c in remain)-min(c for i,c in remain))*sum(truth[i] for i,c in remain)
                            error=abs(actual-direct)/max(1.,initial);max_expected_identity_error=max(max_expected_identity_error,error)
                            assert error<=1e-8
                            expected_width+=prob*actual;expected_cert+=prob*cert
                            support_rows.append({'case_id':case_id,'query':json.dumps(query),'probability':prob,'queries':len(query),
                                                 'actual_width':actual,'certified':cert,'lower':lo,'upper':hi})
                        det_actual,det_cert,_,_=posterior(a,b,visible,totals,truth,solution['deterministic_queries'])
                        greedy_actual,greedy_cert,_,_=posterior(a,b,visible,totals,truth,solution['greedy_queries'])
                        assert expected_width<=solution['randomized_worst_expected_width']+1e-8*max(1.,initial)
                        row.update(randomized_worst_expected_width=solution['randomized_worst_expected_width'],
                                   deterministic_worst_width=solution['deterministic_worst_width'],greedy_worst_width=solution['greedy_worst_width'],
                                   randomized_expected_actual_width=expected_width,deterministic_actual_width=det_actual,greedy_actual_width=greedy_actual,
                                   randomized_expected_certification=expected_cert,deterministic_certification=det_cert,greedy_certification=greedy_cert,
                                   randomized_expected_queries=solution['expected_queries'],deterministic_queries=len(solution['deterministic_queries']),
                                   greedy_queries=len(solution['greedy_queries']),support_size=solution['support_size'],solve_seconds=solution['seconds'])
                    else:
                        actual,cert,_,_=posterior(a,b,visible,totals,truth,())
                        assert actual<=1e-8
                        row.update(randomized_worst_expected_width=0.,deterministic_worst_width=0.,greedy_worst_width=0.,
                                   randomized_expected_actual_width=0.,deterministic_actual_width=0.,greedy_actual_width=0.,
                                   randomized_expected_certification=cert,deterministic_certification=cert,greedy_certification=cert,
                                   randomized_expected_queries=0.,deterministic_queries=0,greedy_queries=0,support_size=1,solve_seconds=0.)
                    cases.append(row)
            print(datetime.now(timezone.utc).isoformat(),cohort,meter,'cases',len(cases),'LPs',solutions,flush=True)
    cases=pd.DataFrame(cases);meters,cohorts,pairs=summarize(cases)
    assert len(cases)==len(data)//4
    for f,h in pinned.items():assert sha(OUT/f)==h
    assert sha(protocol)==protocol_hash
    frames={'cases.csv':cases,'meters.csv':meters,'cohorts.csv':cohorts,'pairs.csv':pairs,'support.csv':pd.DataFrame(support_rows)}
    for name,frame in frames.items():frame.to_csv(HERE/name,index=False)
    positive=cases[cases.initial_width>0]
    report={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.perf_counter()-start,
       'protocol_hash':protocol_hash,'script_hash':sha(__file__),'source_hashes':pinned,
       'public_meters':31,'meter_days':len(data)//24,'cases':len(cases),'positive_width_cases':len(positive),'lp_solutions':solutions,
       'positive_probability_batches_checked':checked_supports,'max_numerical_residuals':max_residuals,
       'max_posterior_width_identity_error_scaled':max_expected_identity_error,'free_revealed_or_deduced_values':free_values,
       'original_missing_values':missing_values,'synthetic_checks':synthetic,
       'worst_width_strict_improvements':int((positive.randomized_worst_expected_width<positive.deterministic_worst_width-1e-8*positive.initial_width).sum()),
       'actual_width_strict_improvements':int((positive.randomized_expected_actual_width<positive.deterministic_actual_width-1e-8*positive.initial_width).sum()),
       'actual_width_strict_worsenings':int((positive.randomized_expected_actual_width>positive.deterministic_actual_width+1e-8*positive.initial_width).sum()),
       'cohort_summary':cohorts.to_dict(orient='records'),'original_artifacts_unchanged':True,
       'interpretation':'Frozen exploratory public-UCI archive-aware daily pair-specific B2 screen. Expected worst width uses an oblivious completion adversary. Every selected-batch bound remains valid, but expected improvement is not pathwise dominance. No measured operational cost, external validation or submission claim.'}
    report['output_hashes']={name:sha(HERE/name) for name in [*frames,'lp_solutions.jsonl']}
    (HERE/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=='__main__':main()
