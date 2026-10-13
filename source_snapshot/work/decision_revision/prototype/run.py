"""Fixed development-only comparison on all external validation cases.

--pilot uses the first 100 cases from each of the first 3 sorted households.
No test input can be selected. Policies receive only the current observed set.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math,sys,time
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
EXTERNAL=ROOT/'work/external_deadline'
sys.path.insert(0,str(EXTERNAL))
from evaluate import interval,closure,decision,stream,RevealOracle
from acquisition import select_batch
from policy import select_one
POLICIES=['decision_probability','exact_width_one','greedy_width_one','hara_one','uniform_one']

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def trajectory(policy,a,b,initial,totals,reference,mean,sd,key):
    observed=initial.copy();oracle=RevealOracle(reference)
    low,high=interval(a,b,observed,totals);status,_=decision(low,high)
    initial_status=status;paid=[];trace=[];planning=0.
    oracle.validate_interval(a,b,low,high)
    while status=='unresolved' and len(paid)<6:
        started=time.perf_counter()
        if policy in ['decision_probability','exact_width_one','greedy_width_one']:
            selected=select_one(a,b,observed,totals,objective=policy)
        else:
            selected=select_batch(policy.removesuffix('_one'),a,b,observed,totals,1,
                                  rng=stream('decision-prototype',key,policy,len(paid)),surrogate_mean=mean,surrogate_sd=sd)
        planning+=time.perf_counter()-started
        query=selected['query_indices']
        assert len(query)==1 and query[0] not in paid and np.isnan(observed[query[0]])
        before=observed.copy();before_bounds=[low,high]
        values=oracle.reveal(query);observed[query]=values;paid.extend(query)
        observed,deductions=closure(observed,totals)
        low,high=interval(a,b,observed,totals);status,_=decision(low,high)
        oracle.validate_interval(a,b,low,high)
        assert low>=before_bounds[0]-1e-9 and high<=before_bounds[1]+1e-9
        trace.append({'query':query[0],'value':float(values[0]),'bounds':[low,high],'status':status,
                      'chosen_probability':selected.get('chosen',{}).get('certificate_probability')})
    return {'initial_status':initial_status,'final_status':status,'paid_requests':len(paid),
            'certification_cost':len(paid) if status in ['a','b'] else None,'planning_seconds':planning,
            'trace':trace}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pilot',action='store_true');args=parser.parse_args()
    out=HERE/('pilot' if args.pilot else 'full');out.mkdir(exist_ok=False)
    started=time.perf_counter()
    paths=[HERE/'policy.py',Path(__file__),EXTERNAL/'validation/trajectories.jsonl',EXTERNAL/'fitted/reference_targets.csv']
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'Only validation cases evaluated; shared frozen reference file filtered to validation before lookup',
              'pilot':args.pilot,'objective':'Exact uniform-simplex probability of a strict sign certificate after one query',
              'tie_break':'Minimum worst remaining width, then coordinate index','batch_size':1,'cap':6,
              'policies':POLICIES,'input_hashes':{str(p.relative_to(ROOT)):digest(p) for p in paths}}
    (out/'pre_run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    reference=pd.read_csv(EXTERNAL/'fitted/reference_targets.csv')
    reference=reference[reference.period=='validation'].copy()
    reference['stamp']=pd.to_datetime(reference.timestamp_utc,utc=True)
    refs=reference.set_index(['household_id','stamp']).energy_kwh
    counts={};rows=[];n=0;strict_errors=0
    with (EXTERNAL/'validation/trajectories.jsonl').open() as infile,(out/'trajectories.jsonl').open('w') as trace:
      for line in infile:
        case=json.loads(line);house=case['household_id']
        counts.setdefault(house,0)
        if args.pilot and (list(counts).index(house)>=3 or counts[house]>=100):continue
        counts[house]+=1
        day=pd.Timestamp(case['day_utc'])
        stamps=pd.date_range(day,periods=24,freq='h')
        hidden=refs.loc[[(house,s) for s in stamps]].to_numpy(float)
        a,b,initial,totals,mean=(np.array(case[k],float) for k in ['a','b','initial_observed','totals','surrogate_mean'])
        results={}
        for policy in POLICIES:
            result=trajectory(policy,a,b,initial,totals,hidden,mean,case['surrogate_sd'],case['case_id'])
            results[policy]=result
            rows.append({k:case[k] for k in ['case_id','household_id','day_utc','pair','learned_pair']}|
                        {'policy':policy}|{k:v for k,v in result.items() if k!='trace'})
        assert results['exact_width_one']['trace']==results['greedy_width_one']['trace']
        trace.write(json.dumps({'case_id':case['case_id'],'policies':results},separators=(',',':'),allow_nan=False)+'\n')
        n+=1
        if n%1000==0:print(json.dumps({'cases':n,'seconds':time.perf_counter()-started}),flush=True)
    df=pd.DataFrame(rows);df.to_csv(out/'cases.csv',index=False,float_format='%.17g')
    summaries=[];curves=[]
    for subgroup,d in [('all',df),('learned',df[df.learned_pair])]:
      for policy,f in d.groupby('policy'):
        f=f[~f.initial_status.isin(['a','b'])]
        coverage=[]
        for budget in range(7):
            value=float(f.assign(cert=f.certification_cost.notna()&(f.certification_cost<=budget)).groupby('household_id').cert.mean().mean())
            coverage.append(value);curves.append({'subgroup':subgroup,'policy':policy,'budget':budget,'coverage':value})
        summaries.append({'subgroup':subgroup,'policy':policy,'initially_unresolved':len(f),'households':f.household_id.nunique(),
                          'macro_mean_requests':float(f.groupby('household_id').paid_requests.mean().mean()),
                          'pooled_mean_requests':float(f.paid_requests.mean()),'B80':next((b for b,v in enumerate(coverage) if v>=.8),None),
                          'coverage':coverage,'unresolved_at_stop':int((f.final_status=='unresolved').sum()),
                          'planning_milliseconds_per_unresolved_case':float(f.planning_seconds.mean()*1000)})
    pd.DataFrame(curves).to_csv(out/'coverage_curves.csv',index=False,float_format='%.17g')
    result={'status':'passed','scope':'Exploratory development-only; not independent confirmation, not replacement of frozen test criterion',
            'cases':n,'households':sum(v>0 for v in counts.values()),'seconds':time.perf_counter()-started,'summaries':summaries,
            'reference_enclosure_and_sign_checks':'every stage passed','singleton_exact_and_greedy':'identical query traces for every case'}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
