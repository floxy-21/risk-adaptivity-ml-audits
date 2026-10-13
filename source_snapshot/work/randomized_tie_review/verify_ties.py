"""Independent offline replay of post-review minimax tie refinements.

No import of audit_ties, no forecast fit, and no original full-study rerun.
The small secondary LPs use a product-vertex formulation with no auxiliary
group variables, independently of the archived implementation.
"""
from pathlib import Path
from datetime import datetime, timezone
from fractions import Fraction as F
import ast
import hashlib
import itertools
import json
import os
import time
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ.setdefault(name,'1')
import numpy as np
import pandas as pd
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OLD=ROOT/'work/new_direction_randomized'
TOL=2e-7

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def close(a,b,scale=1.):
    assert np.isfinite(a) and np.isfinite(b)
    assert abs(a-b)<=TOL*max(1.,abs(a),abs(b),scale),(a,b,scale)

def decision(lo,hi):
    epsilon=1e-9*max(1.,abs(lo),abs(hi))
    return 1 if lo>epsilon else -1 if hi < -epsilon else 0

def exact_regressions():
    results=[]
    examples=[
        ([0,0,2,3],1,{(0,1,2):F(1,3),(0,1,3):F(2,9),(0,2,3):F(2,9),(1,2,3):F(2,9)},
         {(0,1,2):F(1)},[F(1,3),F(1,3),F(1,3),F(0)],F(2)),
        ([0,2,4,12],2,{(0,1):F(4,5),(2,3):F(1,5)},
         {(0,1):F(2,5),(0,2):F(1,5),(1,2):F(2,5)},[F(1,5),F(3,5),F(1,5),F(0)],F(8,5))]
    for cs,budget,bad,good,dual,value in examples:
        def vec(kept):
            span=F(max(cs[i] for i in kept)-min(cs[i] for i in kept)) if len(kept)>1 else F(0)
            return [span if i in kept else F(0) for i in range(4)]
        def mean(policy):
            assert sum(policy.values())==1
            return [sum(p*vec(k)[i] for k,p in policy.items()) for i in range(4)]
        b,g=mean(bad),mean(good)
        assert b==[value]*4 and g==[value,value,value,F(0)]
        assert max(b)==max(g)==value and sum(dual)==1
        legal=[]
        for n in range(budget+1):
            for queried in itertools.combinations(range(4),n):
                kept=tuple(i for i in range(4) if i not in queried)
                legal.append(sum(z*v for z,v in zip(dual,vec(kept))))
        assert min(legal)==value
        results.append({'coefficients':cs,'budget':budget,'total':1,
                        'dominated_coefficients':list(map(str,b)),
                        'dominating_coefficients':list(map(str,g)),
                        'dual':list(map(str,dual)),'minimax_value':str(value),
                        'all_at_most_budget_batches':len(legal),'exact_fraction_check':'passed'})
    return results

def exact_contrast_regime():
    # A transparent analytic fixture, not another empirical case or tuned test.
    energy,delta,separation=F(3),F(2),F(5)
    cs=[F(0),delta,separation,separation+delta]
    assert separation>=2*delta>0
    policy={(0,1):F(1,2),(2,3):F(1,2)}
    expected=[sum(p*(max(cs[j] for j in kept)-min(cs[j] for j in kept))*(i in kept)
                  for kept,p in policy.items()) for i in range(4)]
    assert expected==[delta/2]*4
    lower=[]
    for n in range(3):
        for query in itertools.combinations(range(4),n):
            kept=[i for i in range(4) if i not in query]
            lower.append(energy*(max(cs[i] for i in kept)-min(cs[i] for i in kept))*F(len(kept),4))
    assert min(lower)==energy*delta/2
    rows=[]
    for share in [F(0),F(1,4),F(1,2),F(3,4),F(1)]:
        truth=[energy*share/2]*2+[energy*(1-share)/2]*2
        deterministic=delta*sum(truth[:2]);randomized=sum(a*b for a,b in zip(expected,truth))
        assert deterministic==energy*delta*share and randomized==energy*delta/2
        rows.append({'first_pair_mass_share':str(share),'deterministic_width':str(deterministic),'randomized_expected_width':str(randomized),
                     'randomized_comparison':'better' if randomized<deterministic else 'worse' if randomized>deterministic else 'tie'})
    return {'energy':str(energy),'delta':str(delta),'separation':str(separation),
            'minimax_lower_bound':str(min(lower)),'rows':rows,'exact_fraction_check':'passed'}

def main():
    started=time.perf_counter()
    sources=[Path(__file__),HERE/'protocol.txt',HERE/'provenance_wording_amendment.txt',HERE/'audit_ties.py',HERE/'theory_review.txt',
             HERE/'policies.jsonl',HERE/'selection_complete.json',HERE/'result.json',
             HERE/'cases.csv',HERE/'meters.csv',HERE/'cohorts.csv',HERE/'support.csv',
             OLD/'lp_solutions.jsonl',OLD/'cases.csv',ROOT/'outputs/review_frozen_forecasts.csv']
    pins={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sources}
    result=json.loads((HERE/'result.json').read_text())
    marker=json.loads((HERE/'selection_complete.json').read_text())
    assert result['status']==marker['status']=='passed'
    assert result['script_sha256']==sha(HERE/'audit_ties.py')
    assert marker['policy_sha256']==result['selection_sha256']==sha(HERE/'policies.jsonl')
    assert marker['reference_targets_read_for_selection'] is False
    assert result['selection_completed_before_reference_read'] is True
    assert datetime.fromisoformat(marker['completed_utc'])<datetime.fromisoformat(result['completed_utc'])
    for manifest in [marker['inputs'],result['source_hashes']]:
        for relative,expected in manifest.items():assert sha(ROOT/relative.replace('\\','/'))==expected
    # Source-order evidence is reproducible, but is not an independent timestamp
    # attestation or proof that the human authors had never seen these targets.
    tree=ast.parse((HERE/'audit_ties.py').read_text())
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    selection_names={'matrix_for','metrics','refine'}
    for name in selection_names:
        node=functions[name]
        names={n.id for n in ast.walk(node) if isinstance(n,ast.Name)}
        assert not names.intersection({'pd','data','truth','frames','HERE','ROOT','ORIGINAL'})
        attrs={n.attr for n in ast.walk(node) if isinstance(n,ast.Attribute)}
        assert not attrs.intersection({'read_csv','read_text','read_bytes','open'})
    main_node=functions['main']
    call_lines=lambda pred:[n.lineno for n in ast.walk(main_node) if isinstance(n,ast.Call) and pred(n)]
    refine_lines=call_lines(lambda n:isinstance(n.func,ast.Name) and n.func.id=='refine')
    csv_lines=call_lines(lambda n:isinstance(n.func,ast.Attribute) and n.func.attr=='read_csv')
    writes=call_lines(lambda n:isinstance(n.func,ast.Attribute) and n.func.attr=='write_text')
    marker_write=min(n.lineno for n in ast.walk(main_node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='write_text' and 'selection_complete.json' in ast.unparse(n))
    assert max(refine_lines)<marker_write<min(csv_lines)
    assert any(max(refine_lines)<line<marker_write for line in writes)

    records={r['case_id']:r for r in map(json.loads,(OLD/'lp_solutions.jsonl').read_text().splitlines())}
    policies={r['case_id']:r for r in map(json.loads,(HERE/'policies.jsonl').read_text().splitlines())}
    assert len(records)==len(policies)==1074 and set(records)==set(policies)
    original=pd.read_csv(OLD/'cases.csv').set_index('case_id',drop=False)
    cases=pd.read_csv(HERE/'cases.csv').set_index('case_id',drop=False)
    assert len(cases)==len(original)==20736 and cases.index.is_unique
    assert cases.index.equals(original.index)
    pd.testing.assert_frame_equal(cases[original.columns],original,check_exact=False,atol=1e-12,rtol=1e-12)
    supports=pd.read_csv(HERE/'support.csv')
    support_groups={k:g for k,g in supports.groupby(['case_id','method'])}
    assert set(support_groups)==set(itertools.product(records,['dominance','reference']))
    # The data are available only to validation here; secondary optimality is
    # reconstructed from public aggregate/forecast records, not these targets.
    data=pd.read_csv(ROOT/'outputs/review_frozen_forecasts.csv')
    data=data[data.cohort.isin(['portugal','household'])].copy()
    data['day']=data.timestamp.str[:10]
    frames={(a,b,c):d.sort_values('timestamp') for (a,b,c),d in data.groupby(['cohort','meter','day'])}
    archive={(a,b):dict(zip(d.timestamp,d.daily)) for (a,b),d in data.groupby(['cohort','meter'])}
    evaluated=cases.copy()
    maxima={'secondary_optimum_error':0.,'primary_lower_bound_gap':0.,'dominance_excess':0.,
            'saved_expected_coefficient_error':0.,'endpoint_error_scaled':0.,'secondary_lp_primal_violation':0.,
            'secondary_lp_dual_violation':0.,'secondary_lp_duality_gap':0.}
    checks=0;batch_checks=0;counts={kind:{'realized_improved_vs_original':0,'realized_worsened_vs_original':0,'realized_tied_vs_original':0,'secondary_strictly_improved':0} for kind in ['dominance','reference']}
    for idx,rec in records.items():
        blocks=rec['blocks'];queries=[tuple(q) for q in rec['batches']];initial=rec['initial_width']
        groups=[];indices=[];rows=[]
        for g,block in enumerate(blocks):
            cs=dict(zip(block['indices'],block['coefficients']))
            for i in block['indices']:
                rows.append([block['energy']/initial*(max(cs[j] for j in cs if j not in q)-min(cs[j] for j in cs if j not in q)) if i not in q else 0. for q in queries])
                groups.append(g);indices.append(i)
        matrix=np.asarray(rows);groups=np.asarray(groups)
        assert indices==rec['matrix_coordinate_indices'] and list(groups)==rec['matrix_group_indices']
        p0=np.asarray(rec['probabilities']);z0=matrix@p0
        group_rows=[np.flatnonzero(groups==g) for g in range(len(blocks))]
        vertices=list(itertools.product(*group_rows))
        robust=np.asarray([matrix[list(v)].sum(axis=0) for v in vertices])
        primary0=float((robust@p0).max())
        objective=sum(matrix[ids].mean(axis=0) for ids in group_rows)
        secondary0=float(objective@p0)
        old_dual=np.asarray(rec['dual_weights']);lower=rec['dual_normalized_objective']
        assert old_dual.min()>=-1e-10 and all(old_dual[ids].sum()<=1+1e-10 for ids in group_rows)
        assert (matrix.T@old_dual).min()>=lower-1e-10
        close(primary0,lower)
        d=frames[rec['cohort'],rec['meter'],rec['day']];assert len(d)==24
        y=d.truth_kwh.to_numpy();a=d[rec['model_a']].to_numpy();b=d[rec['model_b']].to_numpy();c=2*(b-a)/24
        totals=y.reshape(4,6).sum(axis=1)
        rng=np.random.default_rng(np.random.SeedSequence([1103,int(pd.Timestamp(rec['day']).value//86400000000000),1]))
        start=int(rng.integers(0,19));visible=y.copy();visible[start:start+6]=np.nan
        saved=archive[rec['cohort'],rec['meter']]
        for i,stamp in enumerate(d.timestamp):
            future=(pd.Timestamp(stamp)+pd.Timedelta(days=1)).isoformat()
            if np.isnan(visible[i]) and future in saved:visible[i]=saved[future];assert visible[i]==y[i]
        for g,total in enumerate(totals):
            block_ids=np.arange(g*6,g*6+6);missing=block_ids[np.isnan(visible[block_ids])]
            residual=max(0.,float(total-np.nansum(visible[block_ids])))
            if len(missing)==1 or len(missing)>0 and residual==0:visible[missing]=residual if len(missing)==1 else 0.
        assert sum(1<<int(i) for i in np.flatnonzero(np.isfinite(visible)))==rec['observed_mask']
        for block in blocks:
            ids=np.asarray(block['indices']);g=int(ids[0]//6)
            assert all(i//6==g and np.isnan(visible[i]) for i in ids)
            np.testing.assert_allclose(c[ids],block['coefficients'],atol=1e-12,rtol=1e-12)
            close(max(0.,totals[g]-np.nansum(visible[g*6:g*6+6])),block['energy'])
        reference=float(np.mean((a-y)**2-(b-y)**2))
        for kind in ['dominance','reference']:
            policy=policies[idx][kind];p=np.asarray(policy['probabilities']);assert len(p)==len(queries)
            assert np.isfinite(p).all() and p.min()>=0;close(float(p.sum()),1.)
            z=matrix@p;primary=float((robust@p).max());secondary=float(objective@p)
            rhs=np.asarray([z0[list(v)].sum() for v in vertices]) if kind=='dominance' else np.full(len(vertices),primary0)
            assert float(np.max(robust@p-rhs))<=TOL
            solved=linprog(objective,A_ub=robust,b_ub=rhs,A_eq=np.ones((1,len(p))),b_eq=[1.],bounds=(0,None),method='highs-ipm',options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
            assert solved.success,(idx,kind,solved.message)
            optimum=float(solved.fun);duals=solved.ineqlin.marginals;eq=float(solved.eqlin.marginals[0])
            dual_objective=float(rhs@duals+eq)
            stationarity=objective-robust.T@duals-eq-solved.lower.marginals
            primal=max(0.,float((robust@solved.x-rhs).max()),abs(float(solved.x.sum())-1.),-float(solved.x.min()))
            dual_violation=max(float(np.max(np.abs(stationarity))),0.,float(duals.max()),-float(solved.lower.marginals.min()))
            assert max(primal,dual_violation,abs(optimum-dual_objective))<=TOL
            close(secondary,optimum);close(primary,lower)
            close(secondary,policy['secondary_normalized']);close(secondary0,policy['secondary_original']);close(primary,policy['primary_normalized'])
            coefficient_error=float(np.max(np.abs(z-np.asarray(policy['expected_coefficients']))));assert coefficient_error<=TOL
            delta=float(sum((z-z0)[ids].max() for ids in group_rows))
            close(delta,policy['maximum_expected_width_difference_normalized'])
            if kind=='dominance':assert delta<=TOL;maxima['dominance_excess']=max(maxima['dominance_excess'],delta)
            maxima['secondary_optimum_error']=max(maxima['secondary_optimum_error'],abs(secondary-optimum))
            maxima['primary_lower_bound_gap']=max(maxima['primary_lower_bound_gap'],abs(primary-lower))
            maxima['saved_expected_coefficient_error']=max(maxima['saved_expected_coefficient_error'],coefficient_error)
            maxima['secondary_lp_primal_violation']=max(maxima['secondary_lp_primal_violation'],primal)
            maxima['secondary_lp_dual_violation']=max(maxima['secondary_lp_dual_violation'],dual_violation)
            maxima['secondary_lp_duality_gap']=max(maxima['secondary_lp_duality_gap'],abs(optimum-dual_objective))
            supp=support_groups[idx,kind];listed={tuple(json.loads(r.query)):r for r in supp.itertuples()}
            expected={q:float(prob) for q,prob in zip(queries,p) if prob>0}
            assert len(listed)==len(supp) and set(listed)==set(expected)
            actual=cert=paid=0.
            for q,prob in expected.items():
                assert len(q)<=2 and len(q)==len(set(q)) and all(np.isnan(visible[i]) for i in q)
                sr=listed[q];close(prob,sr.probability)
                obs=visible.copy();obs[list(q)]=y[list(q)];known=np.isfinite(obs)
                lo=hi=float(np.mean(a*a-b*b)+np.dot(c[known],obs[known]))
                for g,total in enumerate(totals):
                    bid=np.arange(g*6,g*6+6);missing=bid[~known[bid]]
                    residual=max(0.,float(total-np.nansum(obs[bid])))
                    if len(missing):lo+=residual*float(c[missing].min());hi+=residual*float(c[missing].max())
                width=max(0.,hi-lo);sign=decision(lo,hi)
                assert lo-TOL*max(1.,abs(reference))<=reference<=hi+TOL*max(1.,abs(reference))
                assert not sign or sign==int(np.sign(reference))
                close(lo,sr.lower,initial);close(hi,sr.upper,initial);close(width,sr.width,initial)
                assert bool(sign)==bool(sr.certified)
                maxima['endpoint_error_scaled']=max(maxima['endpoint_error_scaled'],abs(lo-sr.lower)/max(1.,initial),abs(hi-sr.upper)/max(1.,initial))
                actual+=prob*width;cert+=prob*bool(sign);paid+=prob*len(q);batch_checks+=1
            for field,value in [('actual_width',actual),('certification',cert),('queries',paid),('worst_width',primary*initial)]:
                close(value,cases.loc[idx,kind+'_'+field],initial if 'width' in field else 1.)
                evaluated.loc[idx,kind+'_'+field]=value
            change=actual-original.loc[idx,'randomized_expected_actual_width'];epsilon=1e-9*max(1.,initial)
            outcome='improved' if change < -epsilon else 'worsened' if change>epsilon else 'tied'
            counts[kind]['realized_'+outcome+'_vs_original']+=1
            counts[kind]['secondary_strictly_improved']+=int(secondary<secondary0-1e-9)
            checks+=1
    zero=original.initial_width<=0
    for kind in ['dominance','reference']:
        for field,oldfield in [('actual_width','randomized_expected_actual_width'),('certification','randomized_expected_certification'),('queries','randomized_expected_queries'),('worst_width','randomized_worst_expected_width')]:
            np.testing.assert_allclose(cases.loc[zero,kind+'_'+field],original.loc[zero,oldfield],atol=1e-12,rtol=1e-12)
    for kind in counts:
        for key,value in counts[kind].items():assert value==result['checks'][kind][key]
    meter_saved=pd.read_csv(HERE/'meters.csv').set_index(['cohort','meter'])
    cohort_saved=pd.read_csv(HERE/'cohorts.csv').set_index('cohort')
    fields=[f for f in meter_saved if f!='cases'];meter_records=[]
    for (cohort,meter),frame in evaluated.groupby(['cohort','meter']):
        row={'cohort':cohort,'meter':meter,'cases':len(frame)}
        denominator=float(frame.initial_width.sum());assert denominator>0
        assert meter_saved.loc[(cohort,meter),'cases']==len(frame)
        for field in fields:
            value=float(frame[field].sum()/denominator) if 'width' in field else float(frame[field].mean())
            close(value,meter_saved.loc[(cohort,meter),field]);row[field]=value
        meter_records.append(row)
    meter_rebuilt=pd.DataFrame(meter_records)
    for cohort,frame in meter_rebuilt.groupby('cohort'):
        record=next(r for r in result['cohort_summary'] if r['cohort']==cohort)
        assert record['meters']==cohort_saved.loc[cohort,'meters']==len(frame)
        assert record['cases']==cohort_saved.loc[cohort,'cases']==int(frame.cases.sum())
        for field in fields:
            value=float(frame[field].mean());close(value,cohort_saved.loc[cohort,field]);close(value,record[field])
    assert checks==2148 and batch_checks==len(supports)==result['support_rows']
    assert len(meter_records)==31 and len(cohort_saved)==2
    examples=exact_regressions()
    assert examples[0]['dominated_coefficients']==result['exact_example']['bad_expected_coefficients']
    assert examples[0]['dominating_coefficients']==result['exact_example']['good_expected_coefficients']
    for relative,expected in pins.items():assert sha(ROOT/relative)==expected
    report={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
            'script_sha256':sha(Path(__file__)),'source_hashes':pins,
            'original_cases_retained':len(cases),'original_columns_reconciled':len(original.columns),
            'zero_width_cases_unchanged':int(zero.sum()),'finite_game_matrices_reconstructed':len(records),
            'secondary_optimality_checks':checks,'positive_support_checks':batch_checks,
            'meter_rows_rebuilt':len(meter_records),'cohort_rows_rebuilt':len(cohort_saved),
            'counts':counts,'maxima':maxima,'exact_fraction_examples':examples,'separated_pair_contrast_regime':exact_contrast_regime(),
            'selection_scope':{'static_source_order_checked':True,'policy_hash_before_evaluation_matches':True,
                'selection_functions_read_reference_data':False,'target_file_bytes_hashed_before_selection':True,
                'limitation':'The source and marker establish the archived pipeline ordering; hashes/timestamps are not independent preregistration or evidence that authors had never inspected these historical targets.'},
            'scope':'All 1,074 positive-width cases, both secondary policies and every saved positive support. Secondary LPs independently solved using product-vertex constraints and HiGHS IPM; no import of audit_ties, no forecast fit, no original full-study rerun. Frozen zero-width cases and all case/meter/cohort aggregates reconciled. Ordinary floating-point tolerances, not outward-rounded formal certificates.',
            'seconds':time.perf_counter()-started}
    (HERE/'independent_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_hashes']},indent=2))

if __name__=='__main__':main()
