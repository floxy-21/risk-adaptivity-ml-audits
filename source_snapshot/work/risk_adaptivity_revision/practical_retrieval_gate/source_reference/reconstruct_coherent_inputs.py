"""Reconstruct coherent rational MSE contrasts from the frozen model vectors.

No withheld six-hour targets are loaded. The original parser is preserved;
missing persistence forecasts use only their documented previous-day input.
"""
from pathlib import Path
from fractions import Fraction as F
from datetime import timedelta
import csv, hashlib, json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MODELS=['daily','ridge','hist_gradient_boosting','mlp']
ORIGINAL=ROOT/'outputs/review_frozen_forecasts.csv'
EXTERNAL=ROOT/'work/risk_adaptivity_revision/external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv'
ENDPOINTS=ROOT/'work/final_chain_20261014T031901Z/run/original_raw/prepared/data_blem_hourly_endpoints.csv'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x): p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')

def main():
    source=HERE/'public_decision_inputs.json'
    data=json.loads(source.read_text())
    pins={str(p.relative_to(ROOT)):sha(p) for p in [source,ORIGINAL,EXTERNAL,ENDPOINTS,Path(__file__)]}
    expected=json.loads((ROOT/'outputs/review_frozen_forecasts.json').read_text())['output_sha256']
    assert sha(ORIGINAL)==expected
    original=pd.read_csv(ORIGINAL,usecols=['cohort','meter','timestamp',*MODELS])
    original=original[original.cohort=='blem_counters'].copy()
    original['timestamp']=pd.to_datetime(original.timestamp,utc=True)
    missing={(r.meter,(r.timestamp-pd.Timedelta(days=1)).isoformat()) for r in original[original.daily.isna()].itertuples()}
    prior={}
    if missing:
        with ENDPOINTS.open(newline='') as h:
            for r in csv.DictReader(h):
                key=(r['meter'],pd.Timestamp(r['interval_start_utc']).isoformat())
                if key in missing:
                    prior[key]=(int(r['end_counter_integer'])-int(r['start_counter_integer']))/10**10
        assert set(prior)==missing
        for i,r in original[original.daily.isna()].iterrows():
            original.at[i,'daily']=prior[r.meter,(r.timestamp-pd.Timedelta(days=1)).isoformat()]
    external=pd.read_csv(EXTERNAL,float_precision='round_trip',usecols=['meter','timestamp_utc',*MODELS])
    external['timestamp']=pd.to_datetime(external.timestamp_utc,utc=True)
    lookup={}
    for cohort,frame in [('original',original),('external',external)]:
        for r in frame.itertuples():
            lookup[cohort,r.meter,r.timestamp]={m:float(getattr(r,m)) for m in MODELS}
    results=[]; maximum=F(0); max_cycle=F(0); old_rounding_matches=0
    for case in data['cases']:
        start=pd.Timestamp(case['day'],tz='UTC')+pd.Timedelta(hours=case['start_hour'])
        vectors={m:[F.from_float(lookup[case['cohort'],case['meter'],start+pd.Timedelta(hours=h)][m]) for h in range(6)] for m in MODELS}
        assert all(np.isfinite(float(v)) for vv in vectors.values() for v in vv)
        pairs=[]; bound=F(0)
        for old in case['pairs']:
            a,b=old['model_a'],old['model_b']; av,bv=vectors[a],vectors[b]
            c=[2*(y-x)/6 for x,y in zip(av,bv)]
            d=sum(x*x-y*y for x,y in zip(av,bv))/6
            # This confirms that the source parser reproduces the original
            # floating-point calculation before replacing it by exact arithmetic.
            aa=np.array(list(map(float,av))); bb=np.array(list(map(float,bv)))
            approx_c=list(2*(bb-aa)/6); approx_d=float(np.mean(aa**2-bb**2))
            assert all(F.from_float(float(v))==F(w) for v,w in zip(approx_c,old['c'])),case['id']
            assert F.from_float(approx_d)==F(old['d']),case['id']
            old_rounding_matches+=1
            error=abs(d-F(old['d']))+F(case['E'])*max(abs(x-F(y)) for x,y in zip(c,old['c']))
            bound=max(bound,error); maximum=max(maximum,error)
            pairs.append({'model_a':a,'model_b':b,'c':list(map(str,c)),'d':str(d)})
        record=dict(case); record['pairs']=pairs
        record['forecast_vectors']={m:list(map(str,v)) for m,v in vectors.items()}
        record['maximum_old_contrast_roundoff_bound']=str(bound)
        # Every directed contrast now derives from one common set of four losses.
        directed={}
        for p in pairs:
            c=list(map(F,p['c'])); d=F(p['d']); a,b=p['model_a'],p['model_b']
            directed[a,b]=(c,d); directed[b,a]=([-x for x in c],-d)
        for a in MODELS:
            for b in MODELS:
                for c in MODELS:
                    if len({a,b,c})!=3: continue
                    ab,bc,ac=directed[a,b],directed[b,c],directed[a,c]
                    assert ab[1]+bc[1]==ac[1]
                    assert all(x+y==z for x,y,z in zip(ab[0],bc[0],ac[0]))
        results.append(record)
    output={'scope':__doc__,'status':'COHERENT_FROZEN_MSE_INPUTS','factor':'1/100','cases':results,
            'source_sha256':pins,'parser_versions':{'pandas':pd.__version__,'numpy':np.__version__}}
    dump(HERE/'public_decision_inputs_coherent.json',output)
    report={'status':'PASS','cases':len(results),'reproduced_original_pair_calculations':old_rounding_matches,
            'exact_pair_cycle_consistency':True,'maximum_original_roundoff_bound':str(maximum),
            'maximum_original_roundoff_bound_float':float(maximum),'source_sha256':pins,
            'coherent_input_sha256':sha(HERE/'public_decision_inputs_coherent.json'),
            'scope':'Preparation only; no claim that old policies remain universally valid after coefficient replacement.'}
    for name,digest in pins.items(): assert sha(ROOT/name)==digest
    dump(HERE/'coherent_inputs_check.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))

if __name__=='__main__': main()
