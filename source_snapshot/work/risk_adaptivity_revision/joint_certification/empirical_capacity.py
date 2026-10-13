"""Post-hoc equal-cap, noiseless sensitivity for the shared two-query audit.

The threshold stays half of EACH ORIGINAL uncapped initial width. All six
positive-width pairs and every input block are retained. A declared cap is
not a device specification; truth-incompatible recorded blocks are flagged.
No capped randomized-batch optimality claim is made.
"""
import argparse,csv,itertools,json,time
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from empirical_shared_audit import (HERE,BASE,ROOT,BATCHES,TOL,LP_OPTIONS,
    choose,sha,dump,load_replay_inputs,input_record)


def slopes(c,a,b):
    s=np.sort(c[:,a:b],axis=1)
    return s[:,::-1]-s


def value(marginals,mass,cap):
    """Concave PL width/max-convolution; every slope piece has length cap."""
    mass=float(mass);n=marginals.shape[1]
    if mass < -1e-9 or mass>n*cap+1e-9:raise ValueError('Infeasible segment mass')
    mass=min(max(mass,0.),n*cap)
    lengths=np.minimum(cap,np.maximum(0.,mass-cap*np.arange(n)))
    return marginals@lengths


def segment_width(c,a,b,mass,cap):return value(slopes(c,a,b),mass,cap)


def conditional(c,k,j,t,cap):
    if j<k:
        left=np.sort(np.concatenate([slopes(c,0,j),slopes(c,j,k)],axis=1),axis=1)[:,::-1]
        right=slopes(c,k,6)
    else:
        left=slopes(c,0,k)
        right=np.sort(np.concatenate([slopes(c,k,j),slopes(c,j,6)],axis=1),axis=1)[:,::-1]
    return value(left,t,cap)+value(right,1-t,cap)


def interval_lines(c,k,cap):
    low=max(0.,1-(6-k)*cap);high=min(1.,k*cap)
    knots=[low,high]
    for m in range(7):
        for t in [m*cap,1-m*cap]:
            if low+1e-12<t<high-1e-12:knots.append(t)
    knots=sorted(set(round(t,14) for t in knots))
    seconds=[j for j in range(1,6) if j!=k];intervals=[]
    for lo,hi in zip(knots,knots[1:]):
        atlo=np.array([conditional(c,k,j,lo,cap) for j in seconds])
        athi=np.array([conditional(c,k,j,hi,cap) for j in seconds])
        slope=(athi-atlo)/(hi-lo);intercept=atlo-slope*lo
        intervals.append({'lo':lo,'hi':hi,'lines':np.stack([slope,intercept],axis=2).tolist()})
    return seconds,intervals


def first_bound(c,k,cap):
    seconds,intervals=interval_lines(c,k,cap);best=-1.;adverse=None
    for part in intervals:
        lo,hi=part['lo'],part['hi'];lines=np.array(part['lines']);flat=lines.reshape(-1,2)
        points=[lo,hi]
        for left,right in itertools.combinations(flat,2):
            den=left[0]-right[0]
            if abs(den)>1e-14:
                t=(right[1]-left[1])/den
                if lo<=t<=hi:points.append(float(t))
        points=np.unique(points)
        vals=(points[:,None,None]*lines[None,:,:,0]+lines[None,:,:,1]).max(axis=2).min(axis=1)
        index=int(np.argmax(vals))
        if vals[index]>best:best=float(vals[index]);adverse=float(points[index])
    return {'value':best,'adverse_first_answer':adverse,'seconds':seconds,'intervals':intervals}


def batch_bound(c,q,cap):
    cuts=(0,*q,6)
    marginal=np.sort(np.concatenate([slopes(c,a,b) for a,b in zip(cuts,cuts[1:])],axis=1),axis=1)[:,::-1]
    return float(value(marginal,1.,cap).max())


def plan(c,cap):
    firsts=[first_bound(c,k,cap) for k in range(1,6)]
    values=[v['value'] for v in firsts];first=choose(values)+1
    one=[batch_bound(c,[k],cap) for k in range(1,6)]
    greedy=choose(one,values)+1
    batches=[batch_bound(c,q,cap) for q in BATCHES];det=choose(batches)
    return {'cap_fraction':str(F(cap).limit_denominator()),'first_query':first,
            'adaptive_guarantee':values[first-1],'first_guarantees':values,
            'firsts':firsts,'greedy_first_query':greedy,'greedy_guarantee':values[greedy-1],
            'best_deterministic_batch':list(BATCHES[det]),'deterministic_batch_index':det,
            'batch_guarantees':batches,'deterministic_batch_guarantee':batches[det]}


def original_answer_vector(case,original,external):
    start=datetime.fromisoformat(case['day']).replace(hour=case['start_hour'],tzinfo=timezone.utc)
    if case['cohort']=='original':y=[original[case['meter'],start+timedelta(hours=i)] for i in range(6)]
    else:
        counters=[external[case['meter'],start+timedelta(hours=i)] for i in range(7)]
        y=[b-a for a,b in zip(counters,counters[1:])]
    total=sum(y)
    assert total>0 and min(y)>=0 and abs(float(total)-case['total_energy'])<1e-10
    return [v/total for v in y]


def widths_at_record(c,q,x,cap):
    cuts=(0,*q,6);width=np.zeros(len(c))
    for a,b in zip(cuts,cuts[1:]):width+=segment_width(c,a,b,sum(x[a:b]),cap)
    return width


def adaptive_choice(c,plan,x,cap,greedy=False):
    k=plan['greedy_first_query'] if greedy else plan['first_query'];t=float(sum(x[:k]))
    js=[j for j in range(1,6) if j!=k]
    vals=[conditional(c,k,j,t,cap).max() for j in js];j=js[choose(vals)]
    return [k,j]


def uncapped_choice(case,x,greedy=False):
    g=case['geometry'];k=g['greedy_first_query'] if greedy else g['first_query']
    t=float(sum(x[:k]));lines=np.array(g['conditional_lines'][k-1])
    vals=(lines[:,:,0]*t+lines[:,:,1]).max(axis=1)
    return [k,g['second_query_dictionaries'][k-1][choose(vals)]]


def replay_case(case,p,original,external):
    cap=F(p['cap_fraction']);x=original_answer_vector(case,original,external);valid=max(x)<=cap
    row={'id':case['id'],'cohort':case['cohort'],'meter':case['meter'],'cap_fraction':str(cap),
         'actual_record_satisfies_cap':valid,'largest_recorded_hour_fraction':float(max(x)),
         'adaptive_guarantee':p['adaptive_guarantee'],'det_batch_guarantee':p['deterministic_batch_guarantee'],
         'greedy_guarantee':p['greedy_guarantee'],
         'adaptive_guarantees_half':p['adaptive_guarantee']<=.5+TOL,
         'det_batch_guarantees_half':p['deterministic_batch_guarantee']<=.5+TOL,
         'greedy_guarantees_half':p['greedy_guarantee']<=.5+TOL,
         'adaptive_queries':None,'greedy_queries':None,'det_batch_queries':p['best_deterministic_batch'],
         'adaptive_recorded_J':None,'det_batch_recorded_J':None,'greedy_recorded_J':None,
         'original_adaptive_recorded_J':None,'original_greedy_recorded_J':None,
         'original_det_batch_recorded_J':None,'original_randomized_batch_expected_J':None,
         'original_randomized_batch_success_probability':None}
    if valid:
        c=np.array(case['geometry']['normalized_coefficients']);cf=float(cap)
        aq=adaptive_choice(c,p,x,cf);gq=adaptive_choice(c,p,x,cf,True)
        allwidths=np.array([float(widths_at_record(c,q,x,cf).max()) for q in BATCHES])
        for label,q in [('adaptive',aq),('greedy',gq),('det_batch',p['best_deterministic_batch']),
                        ('original_adaptive',uncapped_choice(case,x)),('original_greedy',uncapped_choice(case,x,True)),
                        ('original_det_batch',case['geometry']['best_deterministic_batch'])]:
            row[label+'_recorded_J']=float(allwidths[BATCHES.index(tuple(sorted(q)))])
        row['adaptive_queries']=aq;row['greedy_queries']=gq
        pi=np.array(case['geometry']['randomized_batch_weights'])
        row['original_randomized_batch_expected_J']=float(pi@allwidths)
        row['original_randomized_batch_success_probability']=float(pi@(allwidths<=.5+TOL))
        assert row['adaptive_recorded_J']<=p['adaptive_guarantee']+TOL
        assert row['det_batch_recorded_J']<=p['deterministic_batch_guarantee']+TOL
        assert row['greedy_recorded_J']<=p['greedy_guarantee']+TOL
    return row


def summary(rows):
    valid=[r for r in rows if r['actual_record_satisfies_cap']]
    fields=['adaptive_recorded_J','det_batch_recorded_J','greedy_recorded_J',
            'original_adaptive_recorded_J','original_greedy_recorded_J','original_det_batch_recorded_J']
    return {'all_blocks':len(rows),'record_compatible_blocks':len(valid),'record_incompatible_blocks':len(rows)-len(valid),
            'all_block_guarantees':{k:sum(r[k] for r in rows) for k in ['adaptive_guarantees_half','det_batch_guarantees_half','greedy_guarantees_half']},
            'compatible_record_guarantees':{k:sum(r[k] for r in valid) for k in ['adaptive_guarantees_half','det_batch_guarantees_half','greedy_guarantees_half']},
            'adaptive_but_no_deterministic_batch_guarantee':sum(r['adaptive_guarantees_half'] and not r['det_batch_guarantees_half'] for r in rows),
            'compatible_adaptive_but_no_deterministic_batch_guarantee':sum(r['adaptive_guarantees_half'] and not r['det_batch_guarantees_half'] for r in valid),
            'compatible_record_success_counts':{k:sum(r[k]<=.5+TOL for r in valid) for k in fields},
            'compatible_record_mean_widths':{k:float(np.mean([r[k] for r in valid])) if valid else None for k in fields},
            'all_block_mean_guarantees':{k:float(np.mean([r[k] for r in rows])) for k in ['adaptive_guarantee','det_batch_guarantee','greedy_guarantee']}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plans',type=Path,default=HERE/'empirical_external_results/empirical_plans.json')
    p.add_argument('--cohort',choices=['all','original','external'],default='external')
    p.add_argument('--caps',nargs='+',default=['1/2','1/3'])
    p.add_argument('--original-answers',type=Path,default=ROOT/'work/data_blem_hourly_endpoints.csv')
    p.add_argument('--external-answers',type=Path,default=BASE/'external_heatpump/hourly/train_test_hourly_counters.csv')
    p.add_argument('--output-dir',type=Path,default=HERE/'empirical_external_capacity_results');args=p.parse_args()
    begun=time.perf_counter();saved=json.loads(args.plans.read_text());cases=[c for c in saved['plans'] if args.cohort in ['all',c['cohort']]]
    assert len(cases)=={'all':1098,'original':819,'external':279}[args.cohort]
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True);plans=[]
    for i,case in enumerate(cases):
        c=np.array(case['geometry']['normalized_coefficients'])
        for cap in args.caps:plans.append({'id':case['id'],**plan(c,float(F(cap)))})
        if (i+1)%150==0:print('Capped plans:',i+1,flush=True)
    # All capped choices fixed before loading either withheld-answer CSV.
    plan_path=out/'empirical_capacity_plans.json';dump(plan_path,{'input_plan':input_record(args.plans),'plans':plans})
    original,external,inputs=load_replay_inputs(args);index={c['id']:c for c in cases}
    rows=[replay_case(index[p['id']],p,original,external) for p in plans]
    with (out/'empirical_capacity_cases.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    by={(cohort,cap):summary([r for r in rows if r['cohort']==cohort and r['cap_fraction']==cap]) for cohort in ['original','external'] for cap in args.caps if any(r['cohort']==cohort for r in rows)}
    report={'status':'PASS','scope':__doc__,'cohort':args.cohort,'all_plans_before_replay':True,
       'threshold':.5,'normalization':'Original uncapped initial width for every pair; no capacity renormalization',
       'caps':args.caps,'comparison_tolerance':TOL,'floating_point_not_exact_rational':True,
       'tie_rule':'Smallest index within 1e-12 primary and secondary tolerance',
       'summaries':{f'{cohort}/cap={cap}':s for (cohort,cap),s in by.items()},
       'by_meter':{f'{meter}/cap={cap}':summary([r for r in rows if r['meter']==meter and r['cap_fraction']==cap]) for meter in sorted({r['meter'] for r in rows}) for cap in args.caps},
       'inputs':{'uncapped_plans':input_record(args.plans),**inputs},'source_sha256':sha(Path(__file__)),
       'capped_plan_sha256':sha(plan_path),'elapsed_seconds':time.perf_counter()-begun}
    dump(out/'empirical_capacity_report.json',report);print(json.dumps({k:report[k] for k in ['status','summaries','elapsed_seconds']},indent=2))


if __name__=='__main__':main()
