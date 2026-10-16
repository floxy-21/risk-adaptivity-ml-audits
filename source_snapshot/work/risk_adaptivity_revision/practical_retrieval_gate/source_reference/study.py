"""Frozen cumulative-counter geometry, then separate fine-register replay."""
from __future__ import annotations
import argparse, csv, hashlib, itertools, json, platform, sys, time
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MODELS = ['daily','ridge','hist_gradient_boosting','mlp']
BATCHES = list(itertools.combinations(range(1,6),2))
FRACTIONS = [.25,.4,.5,.6,.75]
TOL = 1e-9
LP_OPTIONS = {'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v): Path(p).write_text(json.dumps(v,indent=2,allow_nan=False),encoding='utf-8')
def solve(c,**kwargs):
    r=linprog(c,method='highs',options=LP_OPTIONS,**kwargs)
    if not r.success: raise RuntimeError(r.message)
    return r
def span(c,a,b): return float(np.ptp(c[a:b]))
def vertex_widths(c,q):
    v=np.empty(6)
    cuts=[0,*sorted(q),6]
    for a,b in zip(cuts,cuts[1:]): v[a:b]=span(c,a,b)
    return v
def lines(c,k):
    out=[]
    for j in range(1,6):
        if j==k: continue
        a,b=(max(span(c,0,j),span(c,j,k)),span(c,k,6)) if j<k else (span(c,0,k),max(span(c,k,j),span(c,j,6)))
        out.append((j,a,b))
    return out
def envelope(rows):
    candidates=[0.,1.]
    for (_,a,b),(_,aa,bb) in itertools.combinations(rows,2):
        den=(a-b)-(aa-bb)
        if abs(den)>1e-14:
            t=(bb-b)/den
            if 0<=t<=1: candidates.append(t)
    vals=[min(a*t+b*(1-t) for _,a,b in rows) for t in candidates]
    idx=int(np.argmax(vals))
    return float(vals[idx]),float(candidates[idx])
def min_tie(values,secondary=None):
    lo=min(values); eligible=[i for i,v in enumerate(values) if v<=lo+1e-12]
    return min(eligible,key=lambda i: (secondary[i],i) if secondary is not None else (i,))
def geometry(c):
    V=np.stack([vertex_widths(c,q) for q in BATCHES],axis=1)
    env=[envelope(lines(c,k)) for k in range(1,6)]
    ki=min_tie([z[0] for z in env]); first=ki+1
    greedy=min_tie([max(span(c,0,k),span(c,k,6)) for k in range(1,6)],[z[0] for z in env])+1
    det=min_tie(V.max(axis=0),V.mean(axis=0))
    mean=solve(np.r_[np.zeros(10),1.],A_ub=np.c_[V,-np.ones(6)],b_ub=np.zeros(6),A_eq=[np.r_[np.ones(10),0.]],b_eq=[1.],bounds=[(0,None)]*11)
    # Uniform averaging over all vertices eliminates pointwise dominance.
    secondary=solve(V.mean(axis=0),A_ub=V,b_ub=np.full(6,mean.fun+1e-10),A_eq=[np.ones(10)],b_eq=[1.],bounds=[(0,None)]*10)
    p=np.maximum(secondary.x,0); p/=p.sum()
    precision=[]
    for f in FRACTIONS:
        M=(V<=f+TOL).astype(float)
        # min over adversarial vertex mixtures of maximum batch success.
        r=solve(np.r_[np.zeros(6),1.],A_ub=np.c_[M.T,-np.ones(10)],b_ub=np.zeros(10),A_eq=[np.r_[np.ones(6),0.]],b_eq=[1.],bounds=[(0,None)]*7)
        w=np.maximum(r.x[:6],0); w/=w.sum()
        checked=float(np.max(w@M))
        precision.append({'fraction':f,'upper':checked,'weights':w.tolist(),'lp_value':float(r.fun),'dual_check_error':abs(checked-r.fun),'adaptive_guarantee':env[ki][0]<=f-TOL,'separation_le_70':env[ki][0]<=f-TOL and checked<=.7-TOL})
    return {'V':V.tolist(),'A':env[ki][0],'first':first,'first_worst':[x[0] for x in env],'first_adverse_answers':[x[1] for x in env], 'greedy_first':greedy,'det_batch_index':det,'det_value':float(V[:,det].max()),'mean_value':float(mean.fun),'mean_weights':p.tolist(),'mean_checked':float(np.max(V@p)),'mean_residual':float(np.max(V@p)-mean.fun),'precision':precision}

def load_initial(forecasts,endpoints,metadata):
    pinned=json.loads((ROOT/'outputs/review_frozen_forecasts.json').read_text())
    assert sha(forecasts)==pinned['output_sha256'], 'Frozen forecast export changed'
    # Explicit usecols excludes hidden truth from policy construction.
    f=pd.read_csv(forecasts,usecols=['cohort','meter','timestamp',*MODELS])
    f=f[f.cohort=='blem_counters'].copy(); f['timestamp']=pd.to_datetime(f.timestamp,utc=True)
    f['day']=f.timestamp.dt.strftime('%Y-%m-%d')
    # Only the outer counter readings of the declared blocks are retained.
    outer={}; prior_daily={}
    needed_prior={(r.meter,(r.timestamp-pd.Timedelta(days=1)).isoformat()) for r in f[f.daily.isna()].itertuples()}
    with Path(endpoints).open(newline='',encoding='utf-8') as h:
        for r in csv.DictReader(h):
            t=pd.Timestamp(r['interval_start_utc'])
            if (r['meter'],t.isoformat()) in needed_prior:
                prior_daily[r['meter'],t.isoformat()]=(int(r['end_counter_integer'])-int(r['start_counter_integer']))/10**10
            if t.hour in [0,6,12]: outer[r['meter'],t.isoformat(),'start']=int(r['start_counter_integer'])
            if t.hour in [5,11,17]: outer[r['meter'],(t+pd.Timedelta(hours=1)).isoformat(),'end']=int(r['end_counter_integer'])
    meta=json.loads(Path(metadata).read_text(encoding='utf-8-sig'))
    # Historical meter results are a list, with no hidden targets used here.
    if isinstance(meta,dict): meta=meta.get('meters',meta.get('results',meta))
    meta=[r.get('meta',r) for r in meta]
    scales={r['meter']:r['training_mean_kwh']**2 for r in meta if r['cohort']=='blem_counters'}
    for ix,r in f[f.daily.isna()].iterrows():
        f.at[ix,'daily']=prior_daily[r.meter,(r.timestamp-pd.Timedelta(days=1)).isoformat()]
    assert np.isfinite(f[MODELS].to_numpy()).all()
    cases=[]
    for meter,mf in f.groupby('meter',sort=True):
        assert meter in [f'consumer_{i:08d}' for i in range(1,4)]
        assert sorted(mf.day.unique())==pd.date_range('2017-10-01','2017-12-30').strftime('%Y-%m-%d').tolist()
        for day_index,(day,df) in enumerate(mf.groupby('day',sort=True)):
            assert len(df)==24
            for start in [0,6,12]:
                rows=df[df.timestamp.dt.hour.between(start,start+5)].sort_values('timestamp')
                assert len(rows)==6
                t0=rows.timestamp.iloc[0]; t1=t0+pd.Timedelta(hours=6)
                C0=outer[meter,t0.isoformat(),'start']; C6=outer[meter,t1.isoformat(),'end']
                E=(C6-C0)/10**10; assert E>=0
                for a,b in itertools.combinations(MODELS,2):
                    av=rows[a].to_numpy(); bv=rows[b].to_numpy(); c=2*(bv-av)/6
                    cr=float(np.ptp(c)); W0=E*cr
                    cases.append({'id':f'{meter}/{day}/{start:02d}/{a}/{b}','meter':meter,'day':day,'day_index':day_index,'phase':'pilot' if day_index<20 else 'continuation','start_hour':start,'cutoff_utc':t1.isoformat(),'forecast_issue_utc':t0.normalize().isoformat(),'model_a':a,'model_b':b,'E':E,'c':c.tolist(),'c_normalized':((c-c.min())/cr).tolist() if cr>0 else [0.]*6,'d':float(np.mean(av**2-bv**2)),'W0':W0,'normalization_scale':scales[meter]})
    assert len(cases)==4914
    return cases

def make_geometry(args):
    out=args.output_dir; out.mkdir(parents=True,exist_ok=True)
    protocol=HERE/'protocol.txt'
    sources={'protocol':protocol,'forecasts':args.forecasts,'outer_endpoint_source':args.endpoints,'training_metadata':args.metadata,'study_code':Path(__file__)}
    manifest={'frozen_utc':datetime.now(timezone.utc).isoformat(),'phase':args.panel,'thresholds':FRACTIONS,'primary':.5,'inputs':{k:{'path':str(v.relative_to(ROOT)) if v.is_relative_to(ROOT) else str(v),'sha256':sha(v)} for k,v in sources.items()}}
    dump(out/'protocol_manifest.json',manifest)
    initial=load_initial(args.forecasts,args.endpoints,args.metadata)
    selected=[c for c in initial if args.panel=='all' or c['phase']==args.panel]
    started=time.perf_counter(); cases=[]
    for i,c in enumerate(selected):
        c['geometry']=geometry(np.array(c['c_normalized']))
        cases.append(c)
        if (i+1)%300==0: print(f'geometry {i+1}/{len(selected)}',flush=True)
    dump(out/'geometry.json',{'manifest':manifest,'cases':cases,'seconds':time.perf_counter()-started,'python':platform.python_version()})
    rows=[]
    for c in cases:
        p=next(x for x in c['geometry']['precision'] if x['fraction']==.5)
        rows.append({'meter':c['meter'],'pair':c['model_a']+' / '+c['model_b'],'phase':c['phase'],'A':c['geometry']['A'],'U':p['upper'],'strong':p['separation_le_70'] and c['W0']>0,'guarantee':p['adaptive_guarantee'] or c['W0']==0})
    d=pd.DataFrame(rows)
    summary={'tasks':len(cases),'strong_separations':int(d.strong.sum()),'adaptive_guarantees':int(d.guarantee.sum()),'fraction_strong':float(d.strong.mean()),'mean_A':float(d.A.mean()),'by_meter':d.groupby('meter')[['strong','guarantee']].agg(['sum','mean']).to_json(),'by_pair':d.groupby('pair')[['strong','guarantee']].agg(['sum','mean']).to_json(),'seconds':time.perf_counter()-started}
    dump(out/'geometry_summary.json',summary); print(json.dumps(summary,indent=2),flush=True)

def terminal(c,y,q):
    cuts=[0,*sorted(q),6]; lo=hi=c['d']; coeff=np.array(c['c'])
    for a,b in zip(cuts,cuts[1:]):
        total=float(y[a:b].sum()); lo+=total*float(coeff[a:b].min()); hi+=total*float(coeff[a:b].max())
    return lo,hi
def second(c,first,t):
    # Exact conditional minimizer for the serialized coefficient instance.
    # t is the ratio of two INTEGER counter differences in replay.
    coeff=[Fraction.from_float(x) for x in c['c']]
    def ran(a,b): return max(coeff[a:b])-min(coeff[a:b])
    vals=[]
    for j in range(1,6):
        if j==first: continue
        a,b=(max(ran(0,j),ran(j,first)),ran(first,6)) if j<first else (ran(0,first),max(ran(first,j),ran(j,6)))
        vals.append((a*t+b*(1-t),j))
    return min(vals)[1]

def replay(args):
    src=args.output_dir/'geometry.json'; obj=json.loads(src.read_text()); cases=obj['cases']
    # Actual raw cumulative readings enter only in this separate replay phase.
    raw={}
    sys.path.insert(0,str(ROOT/'work'))
    from data_prepare_blem import SHA256
    for meter in sorted(set(c['meter'] for c in cases)):
        p=args.data_dir/f'data_blem_{meter.replace("_","-")}.csv'
        assert sha(p)==SHA256[meter.replace('_','-')], 'Raw counter hash mismatch'
        with p.open(newline='',encoding='utf-8-sig') as f: raw[meter]={int(r['time']):int(r['energy']) for r in csv.DictReader(f)}
    records=[]; traces=[]; max_bound_error=0.; max_sum_error=0.; started=time.perf_counter()
    for c in cases:
        t0=pd.Timestamp(c['day'],tz='UTC')+pd.Timedelta(hours=c['start_hour'])
        stamps=[int((t0+pd.Timedelta(hours=h)).timestamp()*1000) for h in range(7)]
        cv=[raw[c['meter']][s] for s in stamps]
        y=np.array([(cv[i+1]-cv[i])/10**10 for i in range(6)])
        assert np.all(y>=0); max_sum_error=max(max_sum_error,abs(y.sum()-c['E']))
        assert abs(y.sum()-c['E'])<=1e-10*max(1,c['E'])
        E=c['E']; g=c['geometry']; first=g['first']; gf=g['greedy_first']
        t=Fraction(cv[first]-cv[0],cv[6]-cv[0]) if E>0 else Fraction(0)
        gt=Fraction(cv[gf]-cv[0],cv[6]-cv[0]) if E>0 else Fraction(0)
        aq=tuple(sorted((first,second(c,first,t)))); gq=tuple(sorted((gf,second(c,gf,gt))))
        actual=c['d']+float(np.array(c['c'])@y)
        policies={'adaptive':[(aq,1.)], 'greedy_adaptive':[(gq,1.)], 'det_batch':[(BATCHES[g['det_batch_index']],1.)], 'mean_batch':list(zip(BATCHES,g['mean_weights'])), 'uniform_batch':[(q,.1) for q in BATCHES]}
        for name,choices in policies.items():
            widths=[]; wins=[]
            for q,p in choices:
                lo,hi=terminal(c,y,q); max_bound_error=max(max_bound_error,lo-actual,actual-hi)
                assert lo<=actual+1e-9*max(1,abs(actual)) and hi>=actual-1e-9*max(1,abs(actual))
                widths.append((hi-lo,p)); eps=1e-9*max(1,abs(lo),abs(hi)); wins.append((float(hi < -eps or lo > eps),p))
            row={k:c[k] for k in ['id','meter','day','phase','start_hour','model_a','model_b','W0','normalization_scale']}
            row.update(policy=name,mean_width=sum(w*p for w,p in widths),relative_width=sum(w*p for w,p in widths)/c['W0'] if c['W0']>0 else 0.,scaled_width=sum(w*p for w,p in widths)/c['normalization_scale'],winner_probability=sum(w*p for w,p in wins),requests=2 if c['W0']>0 else 0)
            for f in FRACTIONS: row['success_'+str(f)]=sum(p for w,p in widths if w<=f*c['W0']+TOL*max(c['W0'],1e-15))
            records.append(row)
        assert terminal(c,y,aq)[1]-terminal(c,y,aq)[0] <= g['A']*c['W0']+1e-9*max(1,c['W0'])
        traces.append({'id':c['id'],'source':f'data_blem_{c["meter"].replace("_","-")}.csv','first':first,'first_timestamp_ms':stamps[first],'second':second(c,first,t),'second_timestamp_ms':stamps[second(c,first,t)],'first_prefix_fraction':float(t),'first_prefix_exact_ratio':str(t),'chosen_final_cuts':aq,'raw_hourly_sum_error':float(abs(y.sum()-E))})
    df=pd.DataFrame(records); df.to_csv(args.output_dir/'replay_cases.csv',index=False)
    dump(args.output_dir/'query_trace.json',traces)
    numerical={'status':'PASS','geometry_sha256':sha(src),'cases':len(cases),'policy_evaluations':len(df),'max_containment_error':max_bound_error,'max_total_discrepancy':max_sum_error,'seconds':time.perf_counter()-started}
    dump(args.output_dir/'replay_verification.json',numerical)
    metrics=['success_0.5','relative_width','scaled_width','winner_probability','requests']
    summaries={}
    for group in [['policy'],['meter','policy'],['model_a','model_b','policy'],['phase','policy']]:
        agg=df.groupby(group)[metrics].mean().reset_index()
        agg.to_csv(args.output_dir/('_'.join(group)+'_summary.csv'),index=False)
        summaries['_'.join(group)]=agg.to_dict('records')
    dump(args.output_dir/'replay_summary.json',summaries)
    print(json.dumps(numerical)); print(df.groupby('policy')[metrics].mean().to_string(),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('mode',choices=['geometry','replay']); p.add_argument('--panel',choices=['pilot','continuation','all'],default='pilot'); p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--forecasts',type=Path,default=ROOT/'outputs/review_frozen_forecasts.csv');p.add_argument('--endpoints',type=Path,default=ROOT/'work/data_blem_hourly_endpoints.csv');p.add_argument('--metadata',type=Path,default=ROOT/'outputs/study_meter_results.json');p.add_argument('--data-dir',type=Path,default=ROOT/'work')
    args=p.parse_args(); args.output_dir=args.output_dir.resolve()
    if args.mode=='geometry': make_geometry(args)
    else: replay(args)
if __name__=='__main__': main()
