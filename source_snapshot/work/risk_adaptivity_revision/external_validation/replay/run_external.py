"""Frozen external API-grid counter geometry, followed by separate answer replay.

No network, refitting, parameter tuning, source replacement or threshold selection.
"""
from __future__ import annotations
import csv, hashlib, itertools, json, sys, time
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
RISK=HERE.parents[1]
sys.path.insert(0,str(RISK/'counter_adaptive'))
import study
sys.path.insert(0,str(RISK/'counter_adaptive'/'feedback_triage'))
import analyze as exact
sys.path.insert(0,str(RISK/'counter_adaptive'/'math_review'))
from check_half_cover import make_cover

FORECAST=RISK/'external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv'
COUNTERS=RISK/'external_heatpump/hourly/train_test_hourly_counters.csv'
TRAIN=FORECAST.with_name('training_report.json')
LOCK=RISK/'external_validation/operational/protocol_lock.json'
EXPECTED_FORECAST='04dc64193fbcf00879e4f7ba5224d5626def79a8caad474fb3242d3d8d69b12f'
EXPECTED_COUNTER='b66ed33d2b1b00ac680bf564c3329231317b8176b7e88ac318ee0714494077da'
MODELS=study.MODELS
BATCHES=study.BATCHES
FRACS=[F(1,4),F(2,5),F(1,2),F(3,5),F(3,4)]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def write(path,rows):
    if not rows:
        path.write_text('',encoding='utf-8');return
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def stamp(t):return pd.Timestamp(t).strftime('%Y-%m-%dT%H:%M:%SZ')
def interval(coeff,d,y,q):
    cuts=[0,*sorted(q),6];lo=hi=d
    for a,b in zip(cuts,cuts[1:]):
        mass=sum(y[a:b]);lo+=mass*min(coeff[a:b]);hi+=mass*max(coeff[a:b])
    return lo,hi
def chosen_second(coeff,k,t):
    return min((a*t+b*(1-t),j) for j in range(1,6) if j!=k
               for a,b in [exact.conditional(coeff,k,j)])[1]

def main():
    HERE.mkdir(parents=True,exist_ok=True);started=time.perf_counter()
    assert sha(FORECAST)==EXPECTED_FORECAST and sha(COUNTERS)==EXPECTED_COUNTER
    frame=pd.read_csv(FORECAST,float_precision='round_trip')
    assert set(frame.system_id)=={1,2,7} and len(frame)==2232
    frame['timestamp']=pd.to_datetime(frame.timestamp_utc,utc=True)
    frame['issue']=pd.to_datetime(frame.issue_utc,utc=True)
    assert not frame.duplicated(['system_id','timestamp']).any()
    assert (frame.issue==frame.timestamp.dt.normalize()).all()
    assert (frame.timestamp>=frame.issue).all()
    scales={r['system_id']:r['training_mean_kwh']**2 for r in json.loads(TRAIN.read_text())['systems']}
    # Stage 1 reads ONLY outer endpoints, ignoring all internal values.
    outer={}
    with COUNTERS.open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t=pd.Timestamp(row['timestamp_utc'])
            if t.month==7 and t.hour in (0,6,12,18):
                outer[int(row['system_id']),stamp(t)]=F(row['counter_kwh']) if row['valid']=='1' else None
    intake=[];cases=[];witnesses=[]
    for ident in (1,2,7):
        for day in pd.date_range('2025-07-01','2025-07-31',tz='UTC'):
            for start in (0,6,12):
                t0=day+pd.Timedelta(hours=start);t1=t0+pd.Timedelta(hours=6)
                df=frame[(frame.system_id==ident)&(frame.timestamp>=t0)&(frame.timestamp<t1)].sort_values('timestamp')
                C0=outer.get((ident,stamp(t0)));C6=outer.get((ident,stamp(t1)))
                reason='eligible' if len(df)==6 and np.isfinite(df[MODELS].to_numpy()).all() and C0 is not None and C6 is not None and C6>=C0 else 'unavailable_forecast_or_outer_endpoints'
                intake.append({'system_id':ident,'day':day.strftime('%Y-%m-%d'),'start_hour':start,'initial_status':reason,'planned_pairs':6})
                if reason!='eligible':continue
                E=C6-C0
                for a,b in itertools.combinations(MODELS,2):
                    av=df[a].to_numpy();bv=df[b].to_numpy();c=2*(bv-av)/6;d=float(np.mean(av**2-bv**2))
                    cf=list(map(F.from_float,c));ran=max(cf)-min(cf);W0=E*ran
                    row={'id':f'hpm_{ident}/{day.strftime("%Y-%m-%d")}/{start:02d}/{a}/{b}',
                         'system_id':ident,'meter':f'hpm_{ident}','day':day.strftime('%Y-%m-%d'),
                         'start_hour':start,'cutoff_utc':stamp(t1),'forecast_issue_utc':stamp(day),
                         'model_a':a,'model_b':b,'E':float(E),'E_exact':str(E),'c':c.tolist(),'d':d,
                         'W0':float(W0),'W0_exact':str(W0),'normalization_scale':scales[ident],
                         'forecast_a':av.tolist(),'forecast_b':bv.tolist()}
                    if not W0:
                        row.update(triage='zero_width',geometry=None,exact=None)
                    else:
                        normalized=np.array([float((v-min(cf))/ran) for v in cf])
                        g=study.geometry(normalized)
                        profiles=[exact.batch_profile(cf,q) for q in BATCHES]
                        worst=[max(v) for v in profiles];env=[exact.worst_envelope(cf,k)[0] for k in range(1,6)]
                        k=env.index(min(env))+1
                        det=min(range(10),key=lambda j:(worst[j],sum(profiles[j]),j))
                        greedy=min(range(1,6),key=lambda j:(max(exact.ran(cf,0,j),exact.ran(cf,j,6)),env[j-1],j))
                        # Exact arithmetic realizes the same declared objectives/ties.
                        g['first']=k;g['greedy_first']=greedy;g['det_batch_index']=det
                        g['A']=float(min(env)/ran);g['det_value']=float(worst[det]/ran)
                        upper,adverse,finite_pi=exact.finite_upper(profiles,ran/2)
                        category='batch_suffices' if min(worst)<=ran/2 else ('feedback_required' if min(env)<=ran/2 else 'adaptive_not_guaranteed')
                        cover=[]
                        if min(env)<=ran/2:
                            _,cover=make_cover(cf,k,ran/2)
                        lower=F(1) if min(worst)<=ran/2 else (F(1,2) if cover else F(0))
                        assert lower<=upper
                        ex={'A_over_W0':str(min(env)/ran),'D_over_W0':str(min(worst)/ran),
                            'upper':str(upper),'lower':str(lower),'batch_optimum':str(upper) if upper==lower else 'not established',
                            'adverse_weights':list(map(str,adverse)), 'finite_game_pi':list(map(str,finite_pi)),
                            'cover_batches':[sorted((k,z['j'])) for z in cover],
                            'cover_intervals':[{key:str(z[key]) for key in ['j','a','b','lo','hi']} for z in cover]}
                        row.update(triage=category,geometry=g,exact=ex)
                        if lower==upper==F(1,2):witnesses.append({'id':row['id'],**ex})
                    cases.append(row)
                    if len(cases)%300==0: print(f'geometry {len(cases)}/1674',flush=True)
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Frozen external API-grid stored cumulative increments; exact stored-sample model, not physical energy truth',
        'forecast_sha256':sha(FORECAST),'counter_sha256':sha(COUNTERS),'protocol_lock_sha256':sha(LOCK),
        'script_sha256':sha(Path(__file__)),'threshold':'1/2 W0','policy_stage':'geometry before internal counter answers',
        'original_routines_sha256':{'study.py':sha(RISK/'counter_adaptive/study.py'),'triage_analyze.py':sha(RISK/'counter_adaptive/feedback_triage/analyze.py')},
        'query_scope':'two of five internal hourly API-grid cumulative samples per pair; six-hour endpoints initially known',
        'forecast_time_scope':'declared retrospective issue schedule, no measured historical arrival times'}
    dump(HERE/'geometry.json',{'manifest':manifest,'cases':cases})
    dump(HERE/'half_witnesses.json',witnesses);write(HERE/'initial_intake.csv',intake)
    # Stage 2: every policy/threshold is frozen before internal samples are read.
    raw={}
    with COUNTERS.open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            raw[int(row['system_id']),row['timestamp_utc']]=F(row['counter_kwh']) if row['valid']=='1' else None
    records=[];trace=[];eligible=[];attrition=[];containment=0.;affine_error=0.;max_total=0.
    for case in cases:
        t0=pd.Timestamp(case['day'],tz='UTC')+pd.Timedelta(hours=case['start_hour'])
        times=[stamp(t0+pd.Timedelta(hours=h)) for h in range(7)]
        vals=[raw.get((case['system_id'],t)) for t in times]
        reason='eligible' if all(v is not None for v in vals) and all(vals[i+1]>=vals[i] for i in range(6)) else 'missing_or_negative_internal_increment'
        attrition.append({'id':case['id'],'system_id':case['system_id'],'status':reason})
        if reason!='eligible':continue
        eligible.append(case);y=[vals[i+1]-vals[i] for i in range(6)];E=F(case['E_exact'])
        assert sum(y)==E
        coeff=list(map(F.from_float,case['c']));d=F.from_float(case['d']);W0=F(case['W0_exact'])
        actual=d+sum(a*b for a,b in zip(coeff,y))
        mse=sum((F.from_float(a)-v)**2-(F.from_float(b)-v)**2 for a,b,v in zip(case['forecast_a'],case['forecast_b'],y))/6
        affine_error=max(affine_error,float(abs(mse-actual)))
        if W0:
            g=case['geometry'];k=g['first'];kg=g['greedy_first']
            second=chosen_second(coeff,k,(vals[k]-vals[0])/E)
            secondg=chosen_second(coeff,kg,(vals[kg]-vals[0])/E)
            choices={'adaptive':[(tuple(sorted((k,second))),1.)],
                'greedy_adaptive':[(tuple(sorted((kg,secondg))),1.)],
                'det_batch':[(BATCHES[g['det_batch_index']],1.)],
                'mean_batch':list(zip(BATCHES,g['mean_weights'])),
                'uniform_batch':[(q,.1) for q in BATCHES],
                'full_trace':[((1,2,3,4,5),1.)]}
            if case['exact']['batch_optimum']=='1/2':
                choices['precision_optimal_cover']=[(tuple(q),.5) for q in case['exact']['cover_batches']]
            trace.append({'id':case['id'],'first':k,'first_time':times[k],'second':second,'second_time':times[second],
                          'first_prefix_ratio_exact':str((vals[k]-vals[0])/E),'greedy_first':kg,'greedy_second':secondg})
        else:
            choices={name:[((),1.)] for name in ['adaptive','greedy_adaptive','det_batch','mean_batch','uniform_batch','full_trace']}
        for policy,options in choices.items():
            intervals=[(*interval(coeff,d,y,q),p,q) for q,p in options]
            for lo,hi,_,q in intervals:
                assert lo<=actual<=hi
                if len(q)==5:assert hi==lo==actual
                if policy=='adaptive' and W0:assert hi-lo<=F(case['exact']['A_over_W0'])*W0
            width=sum(float(hi-lo)*p for lo,hi,p,_ in intervals)
            winner=sum(p for lo,hi,p,_ in intervals if float(hi)<-1e-9*max(1,abs(float(lo)),abs(float(hi))) or float(lo)>1e-9*max(1,abs(float(lo)),abs(float(hi))))
            out={key:case[key] for key in ['id','system_id','meter','day','start_hour','model_a','model_b','triage','W0']}
            out.update(policy=policy,mean_width=width,relative_width=width/float(W0) if W0 else 0.,
                       scaled_width=width/case['normalization_scale'],winner_probability=winner,
                       requested_samples=sum(len(q)*p for _,_,p,q in intervals))
            for f in FRACS:out['success_'+str(float(f))]=sum(p for lo,hi,p,_ in intervals if hi-lo<=f*W0)
            records.append(out)
    df=pd.DataFrame(records);write(HERE/'replay_cases.csv',records);write(HERE/'replay_attrition.csv',attrition);dump(HERE/'query_trace.json',trace)
    metrics=['success_0.5','relative_width','scaled_width','winner_probability','requested_samples']
    summaries={}
    for name,group in [('policy',['policy']),('meter_policy',['system_id','policy']),('pair_policy',['model_a','model_b','policy']),('meter_pair_policy',['system_id','model_a','model_b','policy'])]:
        tab=df.groupby(group)[metrics].mean().reset_index();tab['cases']=df.groupby(group).size().to_numpy()
        tab.to_csv(HERE/f'{name}_summary.csv',index=False);summaries[name]=tab.to_dict('records')
    halfids={w['id'] for w in witnesses}
    subset=df[df.id.isin(halfids)]
    halfsummary=subset.groupby('policy')[metrics].mean().reset_index() if len(subset) else pd.DataFrame()
    if len(subset):halfsummary['cases']=subset.groupby('policy').size().to_numpy();halfsummary.to_csv(HERE/'half_policy_summary.csv',index=False)
    groups=[]
    for field in ['system_id','model_a_model_b','system_pair']:
        mapped=[]
        for c in cases:
            key=str(c['system_id']) if field=='system_id' else c['model_a']+'/'+c['model_b'] if field=='model_a_model_b' else str(c['system_id'])+'/'+c['model_a']+'/'+c['model_b']
            mapped.append((key,c))
        for key in sorted({k for k,_ in mapped}):
            rows=[c for k,c in mapped if k==key]
            groups.append({'grouping':field,'group':key,'cases':len(rows),**{x:sum(c['triage']==x for c in rows) for x in ['zero_width','batch_suffices','feedback_required','adaptive_not_guaranteed']},'exact_half':sum(c['id'] in halfids for c in rows)})
    write(HERE/'geometry_group_counts.csv',groups)
    paired=[]
    for label,selection in [('all',df),('half',subset)]:
        for metric in ['success_0.5','winner_probability']:
            a=selection[selection.policy=='adaptive'].set_index('id')[metric]
            b=selection[selection.policy=='det_batch'].set_index('id')[metric]
            tally=Counter((int(x),int(b.loc[key])) for key,x in a.items())
            paired.append({'subset':label,'metric':metric,'n':len(a),'both':tally[1,1],'adaptive_only':tally[1,0],'batch_only':tally[0,1],'neither':tally[0,0]})
    verification={'status':'PASS','containment':'exact rational containment in all replayed terminal intervals',
                  'sum':'exact rational hourly increments sum to retained total','max_affine_loss_rounding_discrepancy':affine_error,
                  'geometry_cases':len(cases),'replay_cases':len(eligible),'policy_rows':len(df),'all_31_days_per_meter':len(intake)==279,
                  'no_bootstrap':'three systems and dependent pair/block cases: report meter and paired counts, no IID intervals',
                  'independence':'new source and frozen pipeline; same-study implementation, not external human validation'}
    report={'status':'PASS','manifest':manifest,'counts':{'planned_calendar_blocks':279,'planned_pair_tasks':1674,
        'geometry_tasks':len(cases),'replay_tasks':len(eligible),'zero_width':sum(not c['W0'] for c in cases),
        'triage':dict(Counter(c['triage'] for c in cases)),'exact_half':len(witnesses),
        'replay_unavailable':len(cases)-len(eligible)},'groups':groups,'policy_summary':summaries['policy'],
        'half_policy_summary':halfsummary.to_dict('records'),'paired':paired,'verification':verification,
        'seconds':time.perf_counter()-started}
    dump(HERE/'report.json',report);dump(HERE/'verification.json',verification)
    print(json.dumps({key:report[key] for key in ['counts','policy_summary','half_policy_summary','paired','seconds']},indent=2))

if __name__=='__main__':main()
