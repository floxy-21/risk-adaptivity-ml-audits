"""Daily selective evaluation with identical recovered observations for all methods."""
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from run_energy_rank_study import (ROOT, WORK, OUT, daily_design, local_dst_affected,
    load_household, load_portugal, impute, sign)
from study_recovery import prepare_blocks, optimal_queries, pair_interval, decision

BASELINES=['complete_case','uniform','seasonal_profile','historical_donor']
SEEDS=[1103,2207,3301]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def training_days(cohort,series):
    days,x,y,eligible=daily_design(series)
    if cohort in ['portugal','household']:
        eligible &= ~local_dst_affected(days)
    if cohort=='portugal':
        tr=(days.year==2013)&eligible
    elif cohort=='household':
        tr=np.isin(days.year,[2008,2009])&eligible
    else:
        tr=(days<pd.Timestamp('2017-10-01',tz=days.tz))&eligible
    return y[tr],np.stack([y[tr][days[tr].dayofweek==k].mean(axis=0) for k in range(7)])


def evaluator_differences(a,b,observed,totals,profile,donors):
    visible=np.isfinite(observed)
    donor_visible=donors[:,visible]
    scale=observed[visible].sum()/np.maximum(donor_visible.sum(axis=1),1e-12)
    distance=np.mean((donor_visible*scale[:,None]-observed[visible])**2,axis=1)
    donor=donors[int(np.argmin(distance))]
    # Stable paired SSE difference; algebraically the same MSE evaluator.
    diff=[np.mean((a[visible]-b[visible])*((a[visible]-observed[visible])+(b[visible]-observed[visible])))]
    for shape in [np.ones(24),profile,donor]:
        y=impute(observed,totals,shape,6)
        diff.append(np.mean((a-b)*((a-y)+(b-y))))
    return np.array(diff)


def summarize(frame):
    matched=[];curves=[];pairs=[];strata=[]
    for cohort,cohort_data in frame.groupby('cohort',sort=True):
        names=['all_pairs',*sorted(cohort_data.pair.unique())]
        for pair in names:
            allq=cohort_data if pair=='all_pairs' else cohort_data[cohort_data.pair==pair]
            zero=allq[allq.budget==0].sort_values(['meter','day','seed','pair']).copy()
            # Rank-based equal-frequency bins handle repeated references under seeds.
            order=zero.sort_values(['true_margin','meter','day','seed','pair'],kind='stable').index
            bins={idx:min(4,int(rank*5/len(order))) for rank,idx in enumerate(order)}
            keys=['meter','day','seed','pair']
            binmap={tuple(zero.loc[idx,k] for k in keys):v for idx,v in bins.items()}
            for budget,data in allq.groupby('budget',sort=True):
                data=data.sort_values(keys,kind='stable')
                n=len(data);target=int((data.certificate!=0).sum())
                certwrong=int(((data.certificate!=0)&(data.certificate!=data.truth_sign)).sum())
                base={'cohort':cohort,'budget':int(budget),'pair':pair,'comparisons':n,
                      'certificate_decisions':target,'certificate_coverage':target/n,
                      'certificate_wrong':certwrong}
                pairs.append(base)
                for method in BASELINES:
                    ranked=data[data[method+'_decision']!=0].sort_values(
                        [method+'_margin',*keys],ascending=[False,True,True,True,True],kind='stable')
                    def evaluate(count):
                        chosen=ranked.iloc[:count]
                        wrong=int((chosen[method+'_decision']!=chosen.truth_sign).sum())
                        return {'selected':len(chosen),'coverage':len(chosen)/n,'wrong':wrong,
                            'error':wrong/len(chosen) if len(chosen) else None,
                            'threshold':float(chosen[method+'_margin'].iloc[-1]) if len(chosen) else None}
                    item={**base,'method':method,**evaluate(target)}
                    item['coverage_exactly_matched']=item['selected']==target
                    matched.append(item)
                    for coverage in np.arange(.05,1.001,.05):
                        curves.append({**base,'method':method,'requested_coverage':float(round(coverage,2)),
                                       **evaluate(int(np.floor(n*coverage+1e-8)))})
                labels=np.array([binmap[tuple(row)] for row in data[keys].itertuples(index=False,name=None)])
                for binid in range(5):
                    part=data[labels==binid]
                    strata.append({'cohort':cohort,'pair':pair,'budget':int(budget),'margin_quintile':binid+1,
                        'comparisons':len(part),'complete_reference_margin_min':float(part.true_margin.min()),
                        'complete_reference_margin_max':float(part.true_margin.max()),
                        'certificate_coverage':float((part.certificate!=0).mean()),
                        'certificate_wrong':int(((part.certificate!=0)&(part.certificate!=part.truth_sign)).sum())})
    return matched,curves,pairs,strata


def main():
    started=time.perf_counter()
    summary=json.loads((OUT/'study_summary.json').read_text())
    predicted=OUT/'study_predictions.csv'
    assert sha(predicted)==summary['artifacts'][predicted.name]['sha256']
    models=summary['design']['models'];assert models==['daily','ridge','hist_gradient_boosting','mlp']
    frame=pd.read_csv(predicted);frame['day']=frame.timestamp.str[:10]
    portugal=load_portugal();household=load_household()
    blem=pd.read_csv(WORK/'data_blem_hourly.csv',index_col=0,parse_dates=True)
    records=[];query_checks=[]
    for meta in summary['meters']:
        cohort,meter=meta['cohort'],meta['meter']
        series=household if cohort=='household' else portugal[meter] if cohort=='portugal' else blem[meter]
        donors,profiles=training_days(cohort,series)
        assert len(donors)==meta['train_days']
        np.testing.assert_allclose(donors.mean(),meta['training_mean_kwh'],rtol=1e-13)
        norm=max(meta['training_mean_kwh']**2,1e-12)
        for day,group in frame[(frame.cohort==cohort)&(frame.meter==meter)].groupby('day',sort=True):
            group=group.sort_values('timestamp');assert len(group)==24
            truth=group.truth_kwh.to_numpy();pred=group[models].to_numpy().T
            totals=truth.reshape(-1,6).sum(axis=1);timestamp=pd.Timestamp(day)
            for seed in SEEDS:
                rng=np.random.default_rng(np.random.SeedSequence([seed,int(timestamp.value//86400000000000),1]))
                start=int(rng.integers(0,19));observed=truth.copy();observed[start:start+6]=np.nan
                for ai,bi in itertools.combinations(range(4),2):
                    a,b=pred[ai],pred[bi];name=models[ai]+'__'+models[bi]
                    true_diff=float(np.mean((a-b)*((a-truth)+(b-truth))))
                    blocks=prepare_blocks(2*(b-a)/24,observed,totals)
                    queries=optimal_queries(blocks,2)
                    if len(query_checks)<12:
                        query_checks.append({'cohort':cohort,'meter':meter,'day':day,'seed':seed,'pair':name,'query_indices':list(queries)})
                    for budget in [0,2]:
                        visible=observed.copy()
                        if budget:visible[list(queries)]=truth[list(queries)]
                        low,high=pair_interval(a,b,visible,totals)
                        diffs=evaluator_differences(a,b,visible,totals,profiles[timestamp.dayofweek],donors)
                        row={'cohort':cohort,'meter':meter,'day':day,'seed':seed,'pair':name,'budget':budget,
                             'certificate':decision(low,high),'truth_sign':int(sign(true_diff)),
                             'true_margin':abs(true_diff)/norm}
                        for method,diff in zip(BASELINES,diffs):
                            row[method+'_decision']=int(sign(diff));row[method+'_margin']=abs(float(diff))/norm
                        records.append(row)
        print(datetime.now(timezone.utc).isoformat(timespec='seconds'),'daily analysis',cohort,meter,flush=True)
    data=pd.DataFrame(records)
    original=pd.read_csv(OUT/'study_comparisons.csv')
    original=original[(original.gap_hours==6)&(original.pattern=='contiguous')&
        (original.block_hours==6)&(original.total_tolerance==0)]
    checks=0
    for (cohort,meter,pair),rows in data[data.budget==0].groupby(['cohort','meter','pair']):
        a,b=pair.split('__')
        reference=original[(original.cohort==cohort)&(original.meter==meter)&
            (original.model_a==a)&(original.model_b==b)]
        for method in ['paired_bounds',*BASELINES]:
            old=reference[reference.method==method].iloc[0]
            predicted_sign=rows.certificate if method=='paired_bounds' else rows[method+'_decision']
            assert len(rows)==old.trials
            assert int((predicted_sign!=0).sum())==old.decisions,(cohort,meter,pair,method,'decision count')
            assert int(((predicted_sign!=0)&(predicted_sign!=rows.truth_sign)).sum())==old.wrong_decisions,(cohort,meter,pair,method,'error count')
            checks+=1
    matched,curves,pairs,strata=summarize(data)
    # Aggregate outputs only; no per-day BLEM observations or predictions are distributed.
    for name,rows in [('matched',matched),('curves',curves),('pairs',pairs),('margin_strata',strata)]:
        pd.DataFrame(rows).to_csv(OUT/f'study_daily_{name}.csv',index=False)
    result={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.perf_counter()-started,
        'scope':{'gap_hours':6,'pattern':'contiguous','block_hours':6,'total_tolerance':0,'seeds':SEEDS,'budgets':[0,2],
            'query_policy':'pair-specific optimal worst-case-width batch','same_observations_for_all_evaluators':True,
            'selection_score':'absolute evaluator-estimated MSE difference / squared training mean',
            'reference_margin_strata':'retrospective diagnostic only; never used for selective decisions',
            'interpretation':'Post-review descriptive same-panel analysis; repeated days/seeds/pairs are dependent'},
        'records':len(data),'zero_budget_main_aggregate_checks':checks,'matched':matched,'curves':curves,'pairs':pairs,'margin_strata':strata,
        'query_checks':query_checks,'script_sha256':sha(__file__),
        'source_hashes':{n:sha(OUT/n) for n in ['study_summary.json','study_predictions.csv','study_comparisons.csv','run_energy_rank_study.py','study_recovery.py']},
        'protocol_sha256':sha(WORK/'daily_evaluation_protocol.txt'),
        'output_hashes':{f'study_daily_{n}.csv':sha(OUT/f'study_daily_{n}.csv') for n in ['matched','curves','pairs','margin_strata']}}
    (OUT/'study_daily_evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print('COMPLETE daily evaluation',len(data),'records',result['wall_seconds'],'seconds',flush=True)


if __name__=='__main__':
    main()
