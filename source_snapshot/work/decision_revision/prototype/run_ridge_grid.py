"""Finite declared six-concentration DEVELOPMENT grid; all validation cases."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys,time
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];EXTERNAL=ROOT/'work/external_deadline'
sys.path.insert(0,str(EXTERNAL))
from evaluate import interval,closure,decision,RevealOracle
from ridge_policy import make_alpha,select_one
KAPPAS=[.5,1.,2.,4.,8.,16.]

def clean(value):
    if isinstance(value,np.ndarray):return [clean(x) for x in value.tolist()]
    if isinstance(value,float):return value if np.isfinite(value) else None
    if isinstance(value,dict):return {key:clean(v) for key,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    return value

def trajectory(a,b,initial,totals,reference,alpha):
    observed=initial.copy();oracle=RevealOracle(reference)
    low,high=interval(a,b,observed,totals);status,_=decision(low,high)
    initial_status=status;paid=[];stages=[];planning=0.
    oracle.validate_interval(a,b,low,high)
    while status=='unresolved' and len(paid)<6:
        started=time.perf_counter();selected=select_one(a,b,observed,totals,alpha);planning+=time.perf_counter()-started
        query=selected['query_indices']
        assert len(query)==1 and query[0] not in paid and np.isnan(observed[query[0]])
        before=observed.copy();previous=[low,high]
        values=oracle.reveal(query);observed[query]=values;paid.extend(query)
        observed,deductions=closure(observed,totals)
        low,high=interval(a,b,observed,totals);status,_=decision(low,high)
        oracle.validate_interval(a,b,low,high)
        assert low>=previous[0]-1e-9 and high<=previous[1]+1e-9
        stages.append({'query':query[0],'value':float(values[0]),'before':before,'after':observed.copy(),
                       'before_bounds':previous,'bounds':[low,high],'deductions':deductions,'status':status,
                       'cost':len(paid),'chosen':selected['chosen'],'scores':selected['scores']})
    return {'initial_status':initial_status,'final_status':status,'paid_requests':len(paid),
            'certification_cost':len(paid) if status in ['a','b'] else None,'planning_seconds':planning,
            'initial_alpha':alpha,'stages':stages}

def main():
    out=HERE/'ridge_grid';out.mkdir(exist_ok=False);started=time.perf_counter()
    paths=[HERE/'policy.py',HERE/'ridge_policy.py',Path(__file__),EXTERNAL/'validation/trajectories.jsonl',EXTERNAL/'fitted/reference_targets.csv']
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'Development validation only; shared reference CSV filtered before lookup',
              'kappa_grid':KAPPAS,'selection':'Minimum household-macro mean requests among initially unresolved; exact ties smaller kappa',
              'prior':'alpha_i=kappa*6*max(Ridge_i,1e-8*max(mean(nonnegative Ridge in whole block),1e-12))/sum whole-block floored weights',
              'conditioning':'Alpha fixed for whole blocks; retain remaining coordinates original alpha after every observation',
              'tie_break':'Maximum one-query probability; minimum worst residual width; lowest index','batch_size':1,'cap':6,
              'input_hashes':{str(p.relative_to(ROOT)):digest(p) for p in paths}}
    (out/'pre_run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    reference=pd.read_csv(EXTERNAL/'fitted/reference_targets.csv');reference=reference[reference.period=='validation'].copy()
    reference['stamp']=pd.to_datetime(reference.timestamp_utc,utc=True)
    refs=reference.set_index(['household_id','stamp']).energy_kwh
    rows=[];n=0
    with (EXTERNAL/'validation/trajectories.jsonl').open() as inf,(out/'trajectories.jsonl').open('w') as tr:
      for line in inf:
        case=json.loads(line);house=case['household_id'];stamps=pd.date_range(pd.Timestamp(case['day_utc']),periods=24,freq='h')
        hidden=refs.loc[[(house,stamp) for stamp in stamps]].to_numpy(float)
        a,b,initial,totals,mean=(np.array(case[key],float) for key in ['a','b','initial_observed','totals','surrogate_mean'])
        results={}
        for kappa in KAPPAS:
            alpha=make_alpha(mean,kappa)
            result=trajectory(a,b,initial,totals,hidden,alpha)
            results[str(kappa)]=result
            rows.append({key:case[key] for key in ['case_id','household_id','day_utc','pair','learned_pair']}|
                        {'kappa':kappa}|{key:value for key,value in result.items() if key not in ['stages','initial_alpha']})
        tr.write(json.dumps(clean({'case_id':case['case_id'],'policies':results}),separators=(',',':'),allow_nan=False)+'\n')
        n+=1
        if n%1000==0:print(json.dumps({'cases':n,'seconds':time.perf_counter()-started}),flush=True)
    for path in paths:assert digest(path)==manifest['input_hashes'][str(path.relative_to(ROOT))]
    df=pd.DataFrame(rows);df.to_csv(out/'cases.csv',index=False,float_format='%.17g')
    summaries=[];curves=[]
    for subgroup,d in [('all',df),('learned',df[df.learned_pair])]:
      for kappa,f in d.groupby('kappa'):
        f=f[~f.initial_status.isin(['a','b'])];coverage=[]
        for budget in range(7):
            value=float(f.assign(cert=f.certification_cost.notna()&(f.certification_cost<=budget)).groupby('household_id').cert.mean().mean())
            coverage.append(value);curves.append({'subgroup':subgroup,'kappa':kappa,'budget':budget,'coverage':value})
        summaries.append({'subgroup':subgroup,'kappa':kappa,'initially_unresolved':len(f),'households':f.household_id.nunique(),
                          'macro_mean_requests':float(f.groupby('household_id').paid_requests.mean().mean()),
                          'pooled_mean_requests':float(f.paid_requests.mean()),'B80':next((b for b,v in enumerate(coverage) if v>=.8),None),
                          'coverage':coverage,'unresolved_at_stop':int((f.final_status=='unresolved').sum()),
                          'planning_milliseconds_per_unresolved_case':float(f.planning_seconds.mean()*1000)})
    pd.DataFrame(curves).to_csv(out/'coverage_curves.csv',index=False,float_format='%.17g')
    selected=min((row for row in summaries if row['subgroup']=='all'),key=lambda row:(row['macro_mean_requests'],row['kappa']))
    result={'status':'passed','scope':'Concentration selection on DEVELOPMENT ONLY; independent confirmation required',
            'cases':n,'seconds':time.perf_counter()-started,'summaries':summaries,'selected_kappa':selected['kappa'],
            'selection_metric':selected['macro_mean_requests'],'reference_enclosure_and_sign_checks':'every stage passed'}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
