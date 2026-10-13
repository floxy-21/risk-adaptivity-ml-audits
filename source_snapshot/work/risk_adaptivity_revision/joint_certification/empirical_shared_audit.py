"""Post-hoc feasibility study: two shared counter queries for all six pairs.

All frozen blocks and all positive-width pairs are retained. Guarantees and
batch mixtures are computed before this script loads internal counter answers.
Float computations are not rational certificates or untouched replication.
"""
from collections import defaultdict,Counter
from datetime import datetime,timedelta,timezone
from fractions import Fraction as F
import argparse,csv,hashlib,itertools,json,os,time
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE.parents[1]
BATCHES=list(itertools.combinations(range(1,6),2));TOL=1e-8
LP_OPTIONS={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf8')
def span(c,a,b):return np.ptp(c[:,a:b],axis=1)
def choose(values,secondary=None):
    values=np.asarray(values);lo=values.min();eligible=np.flatnonzero(values<=lo+1e-12)
    if secondary is not None:
        secondary=np.asarray(secondary);secondary_min=secondary[eligible].min()
        eligible=eligible[secondary[eligible]<=secondary_min+1e-12]
    return int(eligible[0])


def vertex_widths(c,batch):
    v=np.zeros((len(c),6));cuts=(0,*batch,6)
    for a,b in zip(cuts,cuts[1:]):v[:,a:b]=span(c,a,b)[:,None]
    return v


def conditional_lines(c,k):
    result=[];seconds=[]
    for j in range(1,6):
        if j==k:continue
        if j<k:a,b=np.maximum(span(c,0,j),span(c,j,k)),span(c,k,6)
        else:a,b=span(c,0,k),np.maximum(span(c,k,j),span(c,j,6))
        result.append(np.stack([a-b,b],axis=1));seconds.append(j)
    return np.array(result),seconds


def max_envelope(lines):
    flat=lines.reshape(-1,2);points=[0.,1.]
    for left,right in itertools.combinations(flat,2):
        den=left[0]-right[0]
        if abs(den)>1e-14:
            t=(right[1]-left[1])/den
            if 0<=t<=1:points.append(float(t))
    points=np.unique(points)
    values=(points[:,None,None]*lines[None,:,:,0]+lines[None,:,:,1]).max(axis=2).min(axis=1)
    ix=int(np.argmax(values));return float(values[ix]),float(points[ix]),len(points)


def geometry(c):
    pair_vertex=np.stack([vertex_widths(c,q) for q in BATCHES],axis=2)
    V=pair_vertex.max(axis=0)
    primary=linprog(np.r_[np.zeros(10),1.],A_ub=np.c_[V,-np.ones(6)],b_ub=np.zeros(6),
                    A_eq=[np.r_[np.ones(10),0.]],b_eq=[1.],bounds=[(0,None)]*11,
                    method='highs',options=LP_OPTIONS)
    if not primary.success:raise RuntimeError(primary.message)
    secondary=linprog(V.mean(axis=0),A_ub=V,b_ub=np.full(6,primary.fun+1e-10),
                      A_eq=[np.ones(10)],b_eq=[1.],bounds=[(0,None)]*10,
                      method='highs',options=LP_OPTIONS)
    if not secondary.success:raise RuntimeError(secondary.message)
    pi=np.maximum(secondary.x,0);pi/=pi.sum()
    adverse=np.maximum(-primary.ineqlin.marginals,0)
    if adverse.sum()>0:adverse/=adverse.sum()
    else:
        # At zero optimum the nonnegative value-variable bound may absorb
        # all dual mass. Any adverse distribution then has minimum width0.
        if primary.fun>TOL:raise AssertionError('Missing positive-value dual mass')
        adverse=np.full(6,1/6)
    upper=float((V@pi).max());lower=float((adverse@V).min())
    if upper-lower>TOL:raise AssertionError('Joint finite-game primal/dual discrepancy')
    all_lines=[];all_seconds=[];first_values=[];adverse_t=[];point_counts=[]
    for k in range(1,6):
        lines,seconds=conditional_lines(c,k);worst,t,n=max_envelope(lines)
        all_lines.append(lines);all_seconds.append(seconds);first_values.append(worst);adverse_t.append(t);point_counts.append(n)
    first=choose(first_values)+1
    greedy_values=[float(np.maximum(span(c,0,k),span(c,k,6)).max()) for k in range(1,6)]
    greedy=choose(greedy_values,first_values)+1
    det=choose(V.max(axis=0),V.mean(axis=0))
    # A fine grid is only a numerical cross-check of the all-intersections
    # envelope result, not its continuum proof.
    dense=np.linspace(0,1,257)
    max_grid_excess=max(float((dense[:,None,None]*lines[None,:,:,0]+lines[None,:,:,1]).max(axis=2).min(axis=1).max()-bound)
                        for lines,bound in zip(all_lines,first_values))
    if max_grid_excess>TOL:raise AssertionError('Envelope missed a grid value')
    return {'normalized_coefficients':c.tolist(),'joint_vertex_matrix':V.tolist(),
            'adaptive_deterministic_guarantee':float(first_values[first-1]),'first_query':first,
            'first_query_guarantees':first_values,'first_adverse_answers':adverse_t,
            'first_intersection_counts':point_counts,'conditional_lines':np.array(all_lines).tolist(),
            'second_query_dictionaries':all_seconds,'greedy_first_query':greedy,
            'greedy_deterministic_guarantee':float(first_values[greedy-1]),
            'best_deterministic_batch':list(BATCHES[det]),'best_deterministic_batch_index':det,
            'deterministic_batch_guarantee':float(V[:,det].max()),
            'randomized_batch_optimum':float(primary.fun),'randomized_batch_checked_upper':upper,
            'randomized_batch_checked_lower':lower,'randomized_batch_weights':pi.tolist(),
            'adverse_vertex_weights':adverse.tolist(),'primal_dual_gap':upper-lower,
            'max_grid_excess':max_grid_excess}


def input_record(path):
    path=path.resolve()
    return {'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),'sha256':sha(path)}


def read_initial(args):
    paths={f'original_{i}':path for i,path in enumerate(args.original_geometry)} if args.cohort in ['all','original'] else {}
    if args.cohort in ['all','external']:paths['external']=args.external_geometry
    groups=defaultdict(list)
    for source,path in paths.items():
        cohort='external' if source=='external' else 'original'
        for case in json.loads(path.read_text())['cases']:
            key=(cohort,case['meter'],case['day'],case['start_hour']);groups[key].append(case)
    expected={k:v for k,v in {'original':819,'external':279}.items() if args.cohort in ['all',k]}
    assert Counter(k[0] for k in groups)==expected
    result=[]
    for key,rows in sorted(groups.items()):
        assert len(rows)==6 and len({(r['model_a'],r['model_b']) for r in rows})==6
        assert len({r['E'] for r in rows})==1 and all(r['W0']>0 for r in rows)
        rows=sorted(rows,key=lambda r:(r['model_a'],r['model_b']))
        c=np.array([r['c'] for r in rows]);ranges=np.ptp(c,axis=1)
        assert np.all(ranges>0)
        normalized=(c-c.min(axis=1)[:,None])/ranges[:,None]
        cohort,meter,day,hour=key
        result.append({'id':f'{cohort}/{meter}/{day}/{hour:02d}','cohort':cohort,'meter':meter,
            'day':day,'start_hour':hour,'total_energy':rows[0]['E'],
            'pair_case_ids':[r['id'] for r in rows],'positive_width_pairs':6,
            'geometry':geometry(normalized)})
        if len(result)%150==0:print('Planned shared blocks:',len(result),flush=True)
    return result,{name:input_record(path) for name,path in paths.items()}


def load_replay_inputs(args):
    original_path=args.original_answers;external_path=args.external_answers
    original={};external={}
    sources={}
    if args.cohort in ['all','original']:
        with original_path.open(newline='') as f:
            for row in csv.DictReader(f):
                t=datetime.fromisoformat(row['interval_start_utc']);value=F(int(row['end_counter_integer'])-int(row['start_counter_integer']),10**10)
                original[row['meter'],t]=value
        sources['original_endpoints']=input_record(original_path)
    if args.cohort in ['all','external']:
        with external_path.open(newline='') as f:
            for row in csv.DictReader(f):
                if row['valid']=='1':external['hpm_'+row['system_id'],datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))]=F(row['counter_kwh'])
        sources['external_counters']=input_record(external_path)
    return original,external,sources


def replay(case,original,external):
    g=case['geometry'];c=np.array(g['normalized_coefficients'])
    start=datetime.fromisoformat(case['day']).replace(hour=case['start_hour'],tzinfo=timezone.utc)
    if case['cohort']=='original':y=[original[case['meter'],start+timedelta(hours=i)] for i in range(6)]
    else:
        counters=[external[case['meter'],start+timedelta(hours=i)] for i in range(7)]
        y=[b-a for a,b in zip(counters,counters[1:])]
    total=sum(y);assert total>0 and min(y)>=0
    if abs(float(total)-case['total_energy'])>1e-10:raise AssertionError('Replay total differs from retained total')
    x=np.array([float(v/total) for v in y]);all_widths=np.array([float((vertex_widths(c,q)@x).max()) for q in BATCHES])
    def adapt(first):
        t=float(sum(y[:first])/total);lines=np.array(g['conditional_lines'][first-1])
        conditional=(lines[:,:,0]*t+lines[:,:,1]).max(axis=1)
        j=g['second_query_dictionaries'][first-1][choose(conditional)]
        batch=tuple(sorted([first,j]));return float(all_widths[BATCHES.index(batch)]),[first,j]
    aw,aq=adapt(g['first_query']);gw,gq=adapt(g['greedy_first_query'])
    det=all_widths[g['best_deterministic_batch_index']];pi=np.array(g['randomized_batch_weights'])
    if aw>g['adaptive_deterministic_guarantee']+TOL:raise AssertionError('Adaptive replay exceeds guarantee')
    if gw>g['greedy_deterministic_guarantee']+TOL:raise AssertionError('Greedy replay exceeds guarantee')
    result={'id':case['id'],'cohort':case['cohort'],'meter':case['meter'],
        'A_det':g['adaptive_deterministic_guarantee'],'R_batch_mean':g['randomized_batch_optimum'],
        'D_batch':g['deterministic_batch_guarantee'],'mean_risk_gap':g['randomized_batch_optimum']-g['adaptive_deterministic_guarantee'],
        'float_mean_separation':g['randomized_batch_checked_lower']>g['adaptive_deterministic_guarantee']+TOL,
        'adaptive_guarantees_half':g['adaptive_deterministic_guarantee']<=.5+TOL,
        'det_batch_guarantees_half':g['deterministic_batch_guarantee']<=.5+TOL,
        'greedy_guarantees_half':g['greedy_deterministic_guarantee']<=.5+TOL,
        'adaptive_recorded_J':aw,'det_batch_recorded_J':float(det),'randomized_batch_recorded_expected_J':float(pi@all_widths),
        'greedy_recorded_J':gw,'uniform_batch_recorded_expected_J':float(all_widths.mean()),
        'adaptive_recorded_success':float(aw<=.5+TOL),'det_batch_recorded_success':float(det<=.5+TOL),
        'randomized_batch_recorded_success_probability':float(pi@(all_widths<=.5+TOL)),
        'greedy_recorded_success':float(gw<=.5+TOL),
        'uniform_batch_recorded_success_probability':float(np.mean(all_widths<=.5+TOL)),
        'bulk_recorded_J':0.,'bulk_recorded_success':1.,
        'adaptive_first':aq[0],'adaptive_second':aq[1],'greedy_first':gq[0],'greedy_second':gq[1],
        'det_batch_queries':str(g['best_deterministic_batch']),'scalar_queries_per_selective_policy':2,
        'bulk_optional_scalar_values':5,'adaptive_information_rounds':2,'batch_information_rounds':1,
        'bulk_information_rounds':1,'positive_width_pairs':6,'primal_dual_gap':g['primal_dual_gap']}
    return result


def summarize(rows):
    n=len(rows);gap=np.array([r['mean_risk_gap'] for r in rows]);sep=[r for r in rows if r['float_mean_separation']]
    means={key:float(np.mean([r[key] for r in rows])) for key in [
        'A_det','R_batch_mean','D_batch','adaptive_recorded_J','det_batch_recorded_J',
        'randomized_batch_recorded_expected_J','greedy_recorded_J','uniform_batch_recorded_expected_J',
        'adaptive_recorded_success','det_batch_recorded_success',
        'randomized_batch_recorded_success_probability','greedy_recorded_success','uniform_batch_recorded_success_probability']}
    return {'blocks':n,'positive_width_pair_comparisons':6*n,'numerical_mean_risk_separations':len(sep),
        'numerical_mean_risk_separation_fraction':len(sep)/n,
        'adaptive_half_guarantees':sum(r['adaptive_guarantees_half'] for r in rows),
        'det_batch_half_guarantees':sum(r['det_batch_guarantees_half'] for r in rows),
        'greedy_half_guarantees':sum(r['greedy_guarantees_half'] for r in rows),
        'adaptive_half_but_det_batch_not':sum(r['adaptive_guarantees_half'] and not r['det_batch_guarantees_half'] for r in rows),
        'means':means,'gap_quantiles':dict(zip(['min','q25','median','q75','max'],map(float,np.quantile(gap,[0,.25,.5,.75,1])))),
        'positive_gap_median':float(np.median([r['mean_risk_gap'] for r in sep])) if sep else None,
        'positive_gap_max':max((r['mean_risk_gap'] for r in sep),default=None),
        'max_primal_dual_gap':max(r['primal_dual_gap'] for r in rows)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=HERE/'empirical_external_results')
    p.add_argument('--cohort',choices=['all','original','external'],default='external',help='External mode never opens original-source inputs; all/original require separately regenerated BLEM geometry and hourly endpoints')
    p.add_argument('--original-geometry',type=Path,nargs='+',default=[BASE/'counter_adaptive/pilot/geometry.json',BASE/'counter_adaptive/continuation/geometry.json'])
    p.add_argument('--external-geometry',type=Path,default=BASE/'external_validation/replay/geometry.json')
    p.add_argument('--original-answers',type=Path,default=ROOT/'work/data_blem_hourly_endpoints.csv',help='Existing original-source hourly endpoint CSV; loaded only after all plans are saved')
    p.add_argument('--external-answers',type=Path,default=BASE/'external_heatpump/hourly/train_test_hourly_counters.csv',help='Existing external-source hourly cumulative CSV; loaded only after all plans are saved')
    args=p.parse_args()
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True);started=time.perf_counter()
    plans,inputs=read_initial(args)
    # Persist all plans before opening any internal counter values below.
    plan_path=out/'empirical_plans.json';dump(plan_path,{'scope':__doc__,'cohort':args.cohort,'inputs':inputs,'plans':plans})
    original,external,replay_inputs=load_replay_inputs(args);rows=[replay(c,original,external) for c in plans]
    with (out/'empirical_cases.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report={'status':'PASS','scope':f'Post-hoc reused-data numerical feasibility study; {len(plans)} blocks / {6*len(plans)} pairs in declared {args.cohort} cohort; shared2queries, uncapped exact-total/noiseless prefix model. Not rational-certified empirical gaps or independent untouched replication.',
        'cohort':args.cohort,
        'numerical_gap_tolerance':TOL,'half_precision_fraction':.5,
        'lp_tolerance':LP_OPTIONS,'plan_before_replay':True,'plan_sha256':sha(plan_path),
        'secondary_batch_rule':'Uniform mean over six concentration vertices on the primary optimum face +1e-10; independent of withheld replay answers',
        'deterministic_tie_rule':'Earliest optimal first query; deterministic batch ties use lower uniform vertex mean; greedy first minimizes one-query worst joint width then best two-query continuation',
        'baseline_scope':'Batch mean LP exact as formulation by convexity on simplex; A_det exact deterministic planning as formulation by all-line intersections. Floating solutions checked numerically. No randomized adaptive optimum is claimed.',
        **{cohort:summarize([r for r in rows if r['cohort']==cohort]) for cohort in ['original','external'] if any(r['cohort']==cohort for r in rows)},
        'by_meter':{m:summarize([r for r in rows if r['meter']==m]) for m in sorted({r['meter'] for r in rows})},
        'inputs':{**inputs,**replay_inputs},'source_sha256':sha(Path(__file__)),
        'new_network_calls':0,'new_forecast_fits':0,'elapsed_seconds':time.perf_counter()-started}
    dump(out/'empirical_report.json',report);print(json.dumps({k:report[k] for k in ['status','original','external','elapsed_seconds'] if k in report},indent=2))


if __name__=='__main__':main()
