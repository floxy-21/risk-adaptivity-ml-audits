"""Generate manuscript tables from final archived study outputs."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'
COHORTS=['portugal','household','blem_counters']
NAMES={'portugal':'Portugal','household':'Household','blem_counters':'Counter meters'}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    s=json.loads((OUT/'study_summary.json').read_text())
    assert s['cohorts']['portugal']['meters']==30
    assert s['cohorts']['blem_counters']['meters']==3
    for name, meta in s['artifacts'].items():
        path=OUT/name
        if path.exists():
            assert digest(path)==meta['sha256'] and path.stat().st_size==meta['bytes'],name
        elif name=='study_predictions.csv':
            omission=json.loads((ROOT/'work'/'prediction_archive_omission.json').read_text())
            assert omission['filename']==name and omission['sha256']==meta['sha256'] and omission['bytes']==meta['bytes'],name
        else:
            raise FileNotFoundError(path)
    df=pd.read_csv(OUT/'study_comparisons.csv')
    d=df.groupby(['cohort','meter','gap_hours','pattern','block_hours','total_tolerance','method'],as_index=False).agg(
        trials=('trials','sum'),decisions=('decisions','sum'),wrong=('wrong_decisions','sum'),width=('mean_bound_width','mean'))
    d['resolved']=d.decisions/d.trials
    d['error']=d.wrong/d.decisions.replace(0,np.nan)
    g=d.groupby(['cohort','gap_hours','pattern','block_hours','total_tolerance','method'],as_index=False).agg(
        resolved=('resolved','mean'),error=('error','mean'),width=('width','mean'),trials=('trials','sum'),decisions=('decisions','sum'),wrong=('wrong','sum'))
    def row(cohort,gap,block,method,pattern='contiguous',tau=0):
        q=g[(g.cohort==cohort)&(g.gap_hours==gap)&(g.block_hours==block)&(g.method==method)&(g.pattern==pattern)&(g.total_tolerance==tau)]
        assert len(q)==1
        return q.iloc[0].to_dict()
    daily=[]
    for co in COHORTS:
        for gap in (2,6,12):
            for bs in (6,24):
                r={'cohort':co,'gap':gap,'block':bs}
                for method in ('paired_bounds','individual_bounds','complete_case','uniform','seasonal_profile','historical_donor'):
                    z=row(co,gap,bs,method)
                    r[method+'_resolved']=z['resolved']
                    r[method+'_error']=z['error']
                    r[method+'_wrong']=int(z['wrong'])
                daily.append(r)
    pf=pd.read_csv(OUT/'study_period_comparisons.csv')
    p=pf.groupby(['cohort','meter','gap_hours','pattern','block_hours','total_tolerance','method'],as_index=False).agg(
        trials=('decision','size'),decisions=('decision',lambda x:(x!=0).sum()),wrong=('wrong_decision','sum'))
    p['resolved']=p.decisions/p.trials
    p['error']=p.wrong/p.decisions.replace(0,np.nan)
    pg=p.groupby(['cohort','gap_hours','pattern','block_hours','total_tolerance','method'],as_index=False).agg(
        resolved=('resolved','mean'),error=('error','mean'),trials=('trials','sum'),decisions=('decisions','sum'),wrong=('wrong','sum'))
    period=pg[(pg.pattern=='contiguous')&(pg.block_hours==6)&(pg.total_tolerance==0)].to_dict('records')
    sel=pd.read_csv(OUT/'study_selections.csv')
    sel=sel[(sel.pattern=='contiguous')&(sel.gap_hours==6)&(sel.block_hours==6)&(sel.total_tolerance==0)]
    sr=sel.groupby(['cohort','selector'],as_index=False).agg(mean_regret=('mean_normalized_regret','mean'),
        p95_regret=('p95_normalized_regret','mean'),fraction_best=('fraction_best','mean'),
        worst_bound=('mean_worst_case_bound','mean'),bound_coverage=('regret_bound_coverage','mean'))
    sensitivity=g[(g.gap_hours==6)&(g.block_hours==6)&(g.method=='paired_bounds')].to_dict('records')
    normal_mse=[]
    for co in COHORTS:
        meters=[m for m in s['meters'] if m['cohort']==co]
        normal_mse.append({'cohort':co,**{mod:float(np.mean([m['mse'][mod]/m['training_mean_kwh']**2 for m in meters])) for mod in s['design']['models']}})
    rng=np.random.default_rng(90431)
    delta={}
    for bs in (6,24):
        q=d[(d.cohort=='portugal')&(d.gap_hours==6)&(d.block_hours==bs)&(d.pattern=='contiguous')&(d.total_tolerance==0)]
        w=q.pivot(index='meter',columns='method',values='resolved')
        diff=(w.paired_bounds-w.individual_bounds).to_numpy()
        boot=rng.choice(diff,(2000,len(diff)),replace=True).mean(axis=1)
        delta[str(bs)]={'improvement':float(diff.mean()),'ci95':np.quantile(boot,[.025,.975]).tolist()}
    result={'study_completed_utc':s['completed_utc'],'cohort_meters':{c:s['cohorts'][c]['meters'] for c in COHORTS},
            'cohort_test_days':{c:s['cohorts'][c]['test_days'] for c in COHORTS},'daily':daily,'period':period,
            'selection':sr.to_dict('records'),'sensitivity':sensitivity,'normalized_forecast_mse':normal_mse,
            'portugal_direct_resolution_gain':delta,'source_hashes':{n:digest(OUT/n) for n in ('study_summary.json','study_comparisons.csv','study_period_comparisons.csv','study_selections.csv')}}
    def finite_json(value):
        if isinstance(value,dict):
            return {k:finite_json(v) for k,v in value.items()}
        if isinstance(value,list):
            return [finite_json(v) for v in value]
        if isinstance(value,float) and not np.isfinite(value):
            return None
        return value
    result=finite_json(result)
    (OUT/'manuscript_result_tables.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print('COHORTS',result['cohort_test_days'],'seconds',s['wall_seconds'])
    print('DAILY PRIMARY CONTIGUOUS EXACT TOTALS')
    print(pd.DataFrame(daily).to_string(index=False))
    print('PERIOD PRIMARY (6H TOTALS)')
    print(pd.DataFrame(period).to_string(index=False))
    print('REGRET PRIMARY (6 MISSING, 6H TOTALS)')
    print(sr.to_string(index=False))
    print('SENSITIVITY (6 MISSING, 6H TOTALS)')
    print(pd.DataFrame(sensitivity).to_string(index=False))
    print('NORMALIZED MSE',normal_mse)
    print('PAIRED DIFFERENCE BOOTSTRAP',delta)


if __name__=='__main__':
    main()
