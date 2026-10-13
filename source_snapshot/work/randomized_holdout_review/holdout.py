"""Fixed-rule randomized holdout audit with distinct preparation/selection/evaluation."""
from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,hashlib,time
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent; OUT=ROOT/'outputs'
for p in (OUT,ROOT/'work/new_direction_randomized',ROOT/'work/randomized_tie_review',ROOT/'work/randomized_recovery_root'):sys.path.insert(0,str(p))
import numpy as np,pandas as pd
from randomized_recovery_screen import solve_game,posterior,summarize,MODELS,PAIRS,prepare_blocks,worst_width
from study_archive_access import persistence_lookup,reveal_from_archive,DAY_NS
from study_period_archive import close_observations
from audit_ties import refine
from compact_randomized import solve_compact
SOURCE=OUT/'study_holdout_consumers_predictions.csv'
DEPENDENCIES=[SOURCE,OUT/'study_recovery.py',OUT/'study_archive_access.py',OUT/'study_period_archive.py',OUT/'run_energy_rank_study.py',ROOT/'work/new_direction_randomized/randomized_recovery_screen.py',ROOT/'work/randomized_tie_review/audit_ties.py',ROOT/'work/randomized_recovery_root/compact_randomized.py']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
def save(name,obj): (HERE/name).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')
def readlines(name):
    with (HERE/name).open(encoding='utf-8') as f:
        for line in f:yield json.loads(line)
def prepare():
    assert not (HERE/'selection_inputs.jsonl').exists(),'Refuse to overwrite selection inputs'
    pins={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in DEPENDENCIES}
    data=pd.read_csv(SOURCE);assert data.groupby(['cohort','meter']).ngroups==30
    assert set(data.cohort)=={'portugal_new_consumers'} and len(data)==3210*24
    days=0;free=missing=0
    with (HERE/'selection_inputs.jsonl').open('w',encoding='utf-8') as f:
        for (cohort,meter),frame in data.groupby(['cohort','meter'],sort=True):
            lookup=persistence_lookup(frame[['timestamp','daily']])
            for day,d in frame.groupby(frame.timestamp.str[:10],sort=True):
                d=d.sort_values('timestamp');assert len(d)==24
                truth=d.truth_kwh.to_numpy();rng=np.random.default_rng(np.random.SeedSequence([1103,int(pd.Timestamp(day).value//DAY_NS),1]))
                start=int(rng.integers(0,19));visible=truth.copy();visible[start:start+6]=np.nan
                totals=truth.reshape(4,6).sum(axis=1)
                visible,copied=reveal_from_archive(d.timestamp.tolist(),visible,lookup)
                np.testing.assert_allclose(visible[list(copied)],truth[list(copied)],rtol=0,atol=0)
                visible,deduced,_,_=close_observations(visible,totals,6,0)
                record=dict(cohort=cohort,meter=meter,day=day,timestamps=d.timestamp.tolist(),predictions=d[MODELS].to_numpy().T.tolist(),visible=[None if np.isnan(v) else float(v) for v in visible],totals=totals.tolist(),copied=list(copied),deduced=list(deduced),mask_start=start)
                f.write(json.dumps(record,allow_nan=False)+'\n');days+=1;free+=len(copied)+len(deduced);missing+=6
    assert days==3210
    save('prepared.json',dict(status='PASS',completed_utc=stamp(),meter_days=days,consumers=30,cohorts=['portugal_new_consumers'],source_hashes=pins,protocol_sha256=sha(HERE/'protocol.txt'),script_sha256=sha(__file__),selection_input_sha256=sha(HERE/'selection_inputs.jsonl'),free_revealed_or_deduced_values=free,original_missing_values=missing,scope='Preparation forms masked observations and exact measurement totals. Individual withheld values are absent from selection_inputs.jsonl.'))
def select():
    assert not (HERE/'policies.jsonl').exists(),'Refuse to overwrite frozen policies'
    prepared=json.loads((HERE/'prepared.json').read_text());assert sha(HERE/'selection_inputs.jsonl')==prepared['selection_input_sha256']
    count=positive=0;maxcompact=0.;started=time.perf_counter()
    with (HERE/'policies.jsonl').open('w',encoding='utf-8') as f:
        for d in readlines('selection_inputs.jsonl'):
            pred=np.asarray(d['predictions']);visible=np.array(d['visible'],dtype=float);totals=np.array(d['totals'])
            for pair,(ai,bi) in enumerate(PAIRS):
                blocks=tuple(prepare_blocks(2*(pred[bi]-pred[ai])/24,visible,totals));initial=worst_width(blocks,())
                rec=dict(case_id=f"{d['cohort']}/{d['meter']}/{d['day']}/{pair}",cohort=d['cohort'],meter=d['meter'],day=d['day'],pair=pair,model_a=MODELS[ai],model_b=MODELS[bi],initial_width=initial,blocks=[dict(indices=list(b.indices),coefficients=list(b.coefficients),energy=b.energy) for b in blocks])
                if initial>0:
                    rec.update(solve_game(blocks,2));rec['reference']=refine(rec,'reference')
                    c=solve_compact([list(b.coefficients) for b in blocks],[b.energy for b in blocks],2)
                    error=abs(c['value']-rec['randomized_worst_expected_width'])/max(1.,initial)
                    assert error<=2e-7;rec['compact_check']=dict(value=c['value'],normalized_error=error,feasibility_max=c['feasibility_max'],variables=c['variables'],equalities=c['equalities'],inequalities=c['inequalities'])
                    maxcompact=max(maxcompact,error);positive+=1
                f.write(json.dumps(rec,allow_nan=False)+'\n');count+=1
            if count%3000==0:print('Selected',count,'cases;',positive,'positive-width',flush=True)
    assert count==19260
    save('selection_complete.json',dict(status='PASS',completed_utc=stamp(),case_count=count,positive_cases=positive,policy_sha256=sha(HERE/'policies.jsonl'),selection_input_sha256=prepared['selection_input_sha256'],protocol_sha256=prepared['protocol_sha256'],script_sha256=sha(__file__),max_compact_discrepancy_normalized=maxcompact,seconds=time.perf_counter()-started,reference_target_archive_opened_by_selection=False,secondary_rule='uniform-within-block barycenter width on primary minimax face; audit_ties.refine(reference)'))
    print('Selection frozen',count,positive,flush=True)
def evaluation(write=True):
    checkpoint=json.loads((HERE/'selection_complete.json').read_text());prepared=json.loads((HERE/'prepared.json').read_text())
    assert sha(HERE/'policies.jsonl')==checkpoint['policy_sha256'];assert sha(HERE/'selection_inputs.jsonl')==checkpoint['selection_input_sha256']
    for p,h in prepared['source_hashes'].items():assert sha(ROOT/p)==h,p
    assert sha(HERE/'protocol.txt')==checkpoint['protocol_sha256']
    data=pd.read_csv(SOURCE);data['day']=data.timestamp.str[:10]
    frames={(c,m,d):f.sort_values('timestamp') for (c,m,d),f in data.groupby(['cohort','meter','day'])}
    design={(d['cohort'],d['meter'],d['day']):d for d in readlines('selection_inputs.jsonl')}
    rows=[];supports=[];positive=0;maxidentity=0.;maxcontain=0.
    for rec in readlines('policies.jsonl'):
        key=(rec['cohort'],rec['meter'],rec['day']);d=design[key];frame=frames[key]
        a=frame[rec['model_a']].to_numpy();b=frame[rec['model_b']].to_numpy();truth=frame.truth_kwh.to_numpy();visible=np.asarray(d['visible'],float);totals=np.array(d['totals']);initial=rec['initial_width']
        row={k:rec[k] for k in ('case_id','cohort','meter','day','model_a','model_b','initial_width')}
        row.update(seed=1103,gap_hours=6,budget=2,free_copied=len(d['copied']),free_deduced=len(d['deduced']),remaining_unknown=int(np.isnan(visible).sum()),lp_solved=initial>0)
        if initial>0:
            positive+=1
            for name,probs in (('randomized',rec['reference']['probabilities']),('original_primary',rec['probabilities'])):
                expected=certification=queries=0.
                for q,p in zip(rec['batches'],probs):
                    if p<=0:continue
                    assert len(q)<=2 and len(set(q))==len(q)
                    actual,cert,lo,hi=posterior(a,b,visible,totals,truth,q)
                    direct=0.
                    for block in rec['blocks']:
                        kept=[(i,c) for i,c in zip(block['indices'],block['coefficients']) if i not in q]
                        if len(kept)>1:direct+=(max(c for i,c in kept)-min(c for i,c in kept))*sum(truth[i] for i,c in kept)
                    err=abs(actual-direct)/max(1.,initial);maxidentity=max(maxidentity,err);assert err<=1e-8
                    expected+=p*actual;certification+=p*cert;queries+=p*len(q)
                    supports.append(dict(case_id=rec['case_id'],method=name,query=json.dumps(q),probability=p,queries=len(q),actual_width=actual,certified=cert,lower=lo,upper=hi))
                worst=(rec['reference']['primary_normalized']*initial if name=='randomized' else rec['randomized_worst_expected_width'])
                assert expected<=worst+2e-7*max(1.,initial)
                row.update({name+'_worst_expected_width':worst,name+'_expected_actual_width':expected,name+'_expected_certification':certification,name+'_expected_queries':queries})
            for name in ('deterministic','greedy'):
                q=rec[name+'_queries'];actual,cert,lo,hi=posterior(a,b,visible,totals,truth,q)
                row.update({name+'_worst_width':rec[name+'_worst_width'],name+'_actual_width':actual,name+'_certification':cert,name+'_queries':len(q)})
            row['support_size']=sum(p>0 for p in rec['reference']['probabilities']);row['solve_seconds']=rec['seconds']
        else:
            actual,cert,lo,hi=posterior(a,b,visible,totals,truth,());assert actual<=1e-8
            for name in ('randomized','original_primary'):row.update({name+'_worst_expected_width':0.,name+'_expected_actual_width':0.,name+'_expected_certification':cert,name+'_expected_queries':0.})
            for name in ('deterministic','greedy'):row.update({name+'_worst_width':0.,name+'_actual_width':0.,name+'_certification':cert,name+'_queries':0})
            row.update(support_size=1,solve_seconds=0.)
        rows.append(row)
    cases=pd.DataFrame(rows);assert len(cases)==19260 and positive==checkpoint['positive_cases']
    meters,cohorts,pairs=summarize(cases)
    original=cases.copy()
    for suffix in ('worst_expected_width','expected_actual_width','expected_certification','expected_queries'):original['randomized_'+suffix]=original['original_primary_'+suffix]
    om,oc,op=summarize(original)
    pos=cases[cases.initial_width>0];tol=1e-8*np.maximum(1.,pos.initial_width)
    counts={}
    for name in ('randomized','original_primary'):
        diff=pos[name+'_expected_actual_width']-pos.deterministic_actual_width
        counts[name]=dict(actual_strict_improvements=int((diff < -tol).sum()),actual_strict_worsenings=int((diff>tol).sum()),actual_ties=int((np.abs(diff)<=tol).sum()),worst_strict_improvements=int((pos[name+'_worst_expected_width'] < pos.deterministic_worst_width-tol).sum()))
    residuals={}
    for rec in readlines('policies.jsonl'):
        if rec['initial_width']<=0:continue
        for k in ('primal_violation','dual_violation','normalized_gap','pricing_oracle_error'):residuals[k]=max(residuals.get(k,0.),rec[k])
        for k in ('primal_violation','dual_stationarity_error','secondary_duality_gap','primary_lower_bound_gap'):residuals['secondary_'+k]=max(residuals.get('secondary_'+k,0.),rec['reference'][k])
        residuals['compact_discrepancy_normalized']=max(residuals.get('compact_discrepancy_normalized',0.),rec['compact_check']['normalized_error'])
    report=dict(status='PASS',completed_utc=stamp(),consumers=30,meter_days=3210,cases=19260,positive_width_cases=positive,zero_width_cases=19260-positive,positive_probability_batches_checked=len(supports),maximum_width_identity_error_scaled=maxidentity,numerical_residuals=residuals,counts=counts,cohort_summary=cohorts.to_dict(orient='records'),original_primary_cohort_summary=oc.to_dict(orient='records'),selection_before_evaluation=True,selection_policy_sha256=checkpoint['policy_sha256'],source_hashes=prepared['source_hashes'],protocol_sha256=checkpoint['protocol_sha256'],free_revealed_or_deduced_values=prepared['free_revealed_or_deduced_values'],original_missing_values=prepared['original_missing_values'],secondary_rule=checkpoint['secondary_rule'],interpretation='Post-review fixed-rule audit of the existing 30-consumer Portugal replication, same data source. Default randomized results use barycenter refinement; primary optimizer retained as context. No refits, new source, or operational-cost claim.')
    outputs={'cases.csv':cases,'meters.csv':meters,'cohorts.csv':cohorts,'pairs.csv':pairs,'support.csv':pd.DataFrame(supports),'original_primary_meters.csv':om,'original_primary_cohorts.csv':oc,'original_primary_pairs.csv':op}
    if write:
        assert not (HERE/'result.json').exists(),'Refuse to overwrite archived evaluation'
        for name,frame in outputs.items():frame.to_csv(HERE/name,index=False)
        report['output_hashes']={n:sha(HERE/n) for n in [*outputs,'policies.jsonl','selection_inputs.jsonl','prepared.json','selection_complete.json']};report['script_sha256']=sha(__file__)
        save('result.json',report);print(json.dumps(report,indent=2),flush=True)
    else:
        old=json.loads((HERE/'result.json').read_text())
        for n,h in old['output_hashes'].items():assert sha(HERE/n)==h,n
        for name,frame in outputs.items():
            expected=pd.read_csv(HERE/name);pd.testing.assert_frame_equal(frame.reset_index(drop=True),expected,check_dtype=False,check_exact=False,rtol=1e-11,atol=1e-10)
        for k in ('cases','positive_width_cases','zero_width_cases','counts','numerical_residuals'):assert report[k]==old[k],k
        verification=dict(status='PASS',check_kind='Frozen-policy evaluation replay without optimization; independently rebuilt posterior intervals and width identities',cases=len(cases),positive_cases=positive,support_batches=len(supports),selection_sha256=checkpoint['policy_sha256'],source_hashes=prepared['source_hashes'],result_sha256=sha(HERE/'result.json'),script_sha256=sha(__file__),checked_utc=stamp())
        save('verification.json',verification);print(json.dumps(verification,indent=2),flush=True)
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='prepare':prepare()
    elif mode=='select':select()
    elif mode=='evaluate':evaluation(True)
    elif mode=='verify':evaluation(False)
    else:raise ValueError(mode)
