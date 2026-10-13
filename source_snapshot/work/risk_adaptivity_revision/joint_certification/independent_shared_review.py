"""Second implementation: all-case geometry/replay/table audit and fiber LP checks.

No imports from the producer or its checker. Numerical tolerances are explicit.
This verifies stored-data calculations, not temporal preregistration or deployment.
"""
import argparse, csv, hashlib, itertools, json, time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RESULTS=HERE/'empirical_results'
TOL=1e-8
OPTIONS={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}
BATCHES=list(itertools.combinations(range(1,6),2))
errors=defaultdict(float)

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def check(name,a,b,tol=TOL):
    delta=float(np.max(np.abs(np.asarray(a)-np.asarray(b))))
    errors[name]=max(errors[name],delta)
    if delta>tol: raise AssertionError((name,delta,a,b))
def select(values,secondary=None):
    optimum=min(values)
    inds=[i for i,v in enumerate(values) if v<=optimum+1e-12]
    if secondary is not None:
        second=min(secondary[i] for i in inds)
        inds=[i for i in inds if secondary[i]<=second+1e-12]
    return min(inds)
def widths(coeff,q):
    # A coefficient per hour equals the range within its information segment.
    M=np.empty((6,6))
    boundaries=[0]+list(q)+[6]
    for hour in range(6):
        lo=max(b for b in boundaries if b<=hour)
        hi=min(b for b in boundaries if b>hour)
        M[:,hour]=np.max(coeff[:,lo:hi],axis=1)-np.min(coeff[:,lo:hi],axis=1)
    return M
def conditional_from_batches(matrices,k):
    js=[j for j in range(1,6) if j!=k]
    # Optimize linear width over the two first-answer simplices separately.
    ab=[]
    for j in js:
        M=matrices[BATCHES.index(tuple(sorted((j,k))))]
        ab.append(np.stack((M[:,:k].max(axis=1),M[:,k:].max(axis=1)),axis=1))
    return np.array(ab),js
def envelope(ab):
    lines=ab.reshape(-1,2)
    events={0.,1.}
    for x,y in itertools.combinations(lines,2):
        slope=(x[0]-x[1])-(y[0]-y[1])
        if slope!=0:
            t=(y[1]-x[1])/slope
            if 0<t<1:events.add(float(t))
    t=np.array(sorted(events))
    score=(t[:,None,None]*ab[None,:,:,0]+(1-t[:,None,None])*ab[None,:,:,1]).max(axis=2).min(axis=1)
    return float(score.max()),float(t[np.argmax(score)])
def endpoint_lp(c,A,b):
    r=linprog(c,A_eq=A,b_eq=b,bounds=[(0,None)]*len(c),method='highs',options=OPTIONS)
    if not r.success:raise AssertionError(r.message)
    return float(r.fun)

def main():
    global RESULTS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort',choices=['external','all'],default='external')
    parser.add_argument('--results-dir',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    RESULTS=args.results_dir or HERE/('empirical_external_results' if args.cohort=='external' else 'empirical_results')
    output=args.output or HERE/('independent_shared_external.json' if args.cohort=='external' else 'independent_shared_all.json')
    expected_n=279 if args.cohort=='external' else 1098
    started=time.perf_counter()
    report=json.loads((RESULTS/'empirical_report.json').read_text())
    plans=json.loads((RESULTS/'empirical_plans.json').read_text())['plans']
    data=list(csv.DictReader((RESULTS/'empirical_cases.csv').open(newline='')))
    outcomes={r['id']:r for r in data}
    assert len(outcomes)==len(data)==len(plans)==expected_n
    assert report['plan_sha256']==digest(RESULTS/'empirical_plans.json')
    source={}; expected=defaultdict(list)
    for name,entry in report['inputs'].items():
        path=ROOT/Path(entry['path'].replace(chr(92),'/')); assert digest(path)==entry['sha256']
        if name in ['original_endpoints','external_counters']:continue
        for r in json.loads(path.read_text())['cases']:
            assert r['id'] not in source; source[r['id']]=r
            cohort='external' if name=='external' else 'original'
            expected[(cohort,r['meter'],r['day'],r['start_hour'])].append(r['id'])
    assert len(source)==6*expected_n and len(expected)==expected_n
    originals={};externals={}
    if 'original_endpoints' in report['inputs']:
        for r in csv.DictReader((ROOT/Path(report['inputs']['original_endpoints']['path'].replace(chr(92),'/'))).open(newline='')):
            originals[r['meter'],datetime.fromisoformat(r['interval_start_utc'])]=Fraction(int(r['end_counter_integer'])-int(r['start_counter_integer']),10**10)
    for r in csv.DictReader((ROOT/Path(report['inputs']['external_counters']['path'].replace(chr(92),'/'))).open(newline='')):
        if r['valid']=='1':externals['hpm_'+r['system_id'],datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'))]=Fraction(r['counter_kwh'])
    groups=defaultdict(list);recomputed=[];secondary_calls=0;near_threshold=0
    for ix,p in enumerate(plans):
        key=(p['cohort'],p['meter'],p['day'],p['start_hour'])
        assert sorted(expected[key])==sorted(p['pair_case_ids'])
        sr=[source[k] for k in p['pair_case_ids']]
        names=sorted(set(r['model_a'] for r in sr)|set(r['model_b'] for r in sr))
        assert len(names)==4
        assert {frozenset((r['model_a'],r['model_b'])) for r in sr}=={frozenset(q) for q in itertools.combinations(names,2)}
        for r in sr:
            issue=datetime.fromisoformat(r['forecast_issue_utc'].replace('Z','+00:00'))
            cutoff=datetime.fromisoformat(r['cutoff_utc'].replace('Z','+00:00'))
            assert issue<=cutoff
            check('initial_width_identity',r['W0'],r['E']*np.ptp(r['c']))
        raw=np.array([r['c'] for r in sr]); normalized=(raw-raw.min(axis=1)[:,None])/np.ptp(raw,axis=1)[:,None]
        g=p['geometry'];out=outcomes[p['id']]
        check('normalized_coefficients',normalized,g['normalized_coefficients'])
        M=np.array([widths(normalized,q) for q in BATCHES]);V=M.max(axis=1).T
        check('vertex_matrix',V,g['joint_vertex_matrix'])
        pi=np.array(g['randomized_batch_weights']);lam=np.array(g['adverse_vertex_weights'])
        assert min(pi)>=0 and min(lam)>=0
        check('batch_mass',pi.sum(),1);check('adversary_mass',lam.sum(),1)
        lower=float((lam@V).min());upper=float((V@pi).max())
        check('game_primal_dual',upper,lower)
        check('primary_lp_value',g['randomized_batch_optimum'],lower)
        check('saved_upper',upper,g['randomized_batch_checked_upper'])
        check('saved_lower',lower,g['randomized_batch_checked_lower'])
        secondary=linprog(V.mean(axis=0),A_ub=V,b_ub=np.full(6,g['randomized_batch_optimum']+1e-10),A_eq=[np.ones(10)],b_eq=[1],bounds=[(0,None)]*10,method='highs',options=OPTIONS)
        assert secondary.success;secondary_calls+=1
        check('secondary_objective',V.mean(axis=0)@pi,secondary.fun)
        values=[];all_ab=[]
        for k in range(1,6):
            ab,js=conditional_from_batches(M,k);all_ab.append(ab)
            check('conditional_lines',np.stack((ab[:,:,0]-ab[:,:,1],ab[:,:,1]),axis=2),g['conditional_lines'][k-1])
            assert js==g['second_query_dictionaries'][k-1]
            val,t=envelope(ab);values.append(val)
        check('all_first_query_guarantees',values,g['first_query_guarantees'])
        first=select(values)+1;assert first==g['first_query']
        greedy_one=[float(widths(normalized,(k,)).max()) for k in range(1,6)]
        greedy=select(greedy_one,values)+1
        if greedy!=g['greedy_first_query']:
            raise AssertionError(('greedy_tie',p['id'],greedy,g['greedy_first_query'],greedy_one,values,g['first_query_guarantees']))
        deterministic=select(V.max(axis=0),V.mean(axis=0));assert deterministic==g['best_deterministic_batch_index']
        assert list(BATCHES[deterministic])==g['best_deterministic_batch']
        start=datetime.fromisoformat(p['day']).replace(hour=p['start_hour'],tzinfo=timezone.utc)
        if p['cohort']=='original':y=[originals[p['meter'],start+timedelta(hours=h)] for h in range(6)]
        else:
            counters=[externals[p['meter'],start+timedelta(hours=h)] for h in range(7)]
            y=[b-a for a,b in zip(counters,counters[1:])]
        assert min(y)>=0 and sum(y)>0; check('retained_total',float(sum(y)),p['total_energy'])
        x=np.array([float(v/sum(y)) for v in y])
        # Direct physical-energy segment sums, divided by the source W0.
        observed=[]
        for q in BATCHES:
            edges=(0,*q,6);pw=[]
            for rr in sr:
                pw.append(sum(float(sum(y[a:b]))*(max(rr['c'][a:b])-min(rr['c'][a:b])) for a,b in zip(edges,edges[1:]))/rr['W0'])
            observed.append(max(pw))
        observed=np.array(observed)
        def follow(k):
            t=float(sum(y[:k])/sum(y));ab=all_ab[k-1]
            scores=(t*ab[:,:,0]+(1-t)*ab[:,:,1]).max(axis=1)
            j=[j for j in range(1,6) if j!=k][select(scores)]
            return observed[BATCHES.index(tuple(sorted((k,j))))],j
        aw,second=follow(first);gw,gj=follow(greedy)
        assert int(out['adaptive_first'])==first and int(out['adaptive_second'])==second
        assert int(out['greedy_first'])==greedy and int(out['greedy_second'])==gj
        new={'id':p['id'],'cohort':p['cohort'],'meter':p['meter'],'A_det':values[first-1],
             'R_batch_mean':g['randomized_batch_optimum'],'D_batch':float(V[:,deterministic].max()),
             'mean_risk_gap':g['randomized_batch_optimum']-values[first-1],
             'adaptive_recorded_J':aw,'greedy_recorded_J':gw,'det_batch_recorded_J':observed[deterministic],
             'randomized_batch_recorded_expected_J':float(pi@observed),'uniform_batch_recorded_expected_J':float(observed.mean()),
             'adaptive_recorded_success':float(aw<=.5+TOL),'greedy_recorded_success':float(gw<=.5+TOL),
             'det_batch_recorded_success':float(observed[deterministic]<=.5+TOL),
             'randomized_batch_recorded_success_probability':float(pi@(observed<=.5+TOL)),
             'uniform_batch_recorded_success_probability':float(np.mean(observed<=.5+TOL)),
             'float_mean_separation':lower>values[first-1]+TOL,
             'adaptive_guarantees_half':values[first-1]<=.5+TOL,
             'det_batch_guarantees_half':V[:,deterministic].max()<=.5+TOL,
             'greedy_guarantees_half':values[greedy-1]<=.5+TOL}
        for k,v in new.items():
            if k in ['id','cohort','meter']:assert out[k]==v
            elif isinstance(v,(bool,np.bool_)):assert out[k]==str(v)
            else:check('replay_'+k,v,float(out[k]))
        assert int(out['scalar_queries_per_selective_policy'])==2 and int(out['positive_width_pairs'])==6
        near_threshold+=sum(abs(observed-.5)<1e-7)
        recomputed.append(new);groups[p['meter']].append((p,normalized,M,x,all_ab))
        if (ix+1)%250==0:print('All-case geometry/replay checks',ix+1,flush=True)
    for label,rows,target in [(name,[r for r in recomputed if r['cohort']==name],report[name]) for name in ['original','external'] if name in report]+[(m,[r for r in recomputed if r['meter']==m],report['by_meter'][m]) for m in sorted(groups)]:
        assert len(rows)==target['blocks'] and len(rows)*6==target['positive_width_pair_comparisons']
        for k,v in target['means'].items():check('table_'+label+'_'+k,np.mean([r[k] for r in rows]),v)
        for rk,tk in [('float_mean_separation','numerical_mean_risk_separations'),('adaptive_guarantees_half','adaptive_half_guarantees'),('det_batch_guarantees_half','det_batch_half_guarantees'),('greedy_guarantees_half','greedy_half_guarantees')]:assert sum(r[rk] for r in rows)==target[tk]
        assert sum(r['adaptive_guarantees_half'] and not r['det_batch_guarantees_half'] for r in rows)==target['adaptive_half_but_det_batch_not']
        check('quantiles_'+label,np.quantile([r['mean_risk_gap'] for r in rows],[0,.25,.5,.75,1]),list(target['gap_quantiles'].values()))
    # First/middle/last for every meter: selected independently of performance.
    chosen=[]
    for meter,items in sorted(groups.items()):
        items.sort(key=lambda q:q[0]['id']);chosen.extend(items[i] for i in [0,len(items)//2,len(items)-1])
    endpoint_calls=conditional_calls=0
    for p,c,M,x,ab_all in chosen:
        profiles=[x,*np.eye(6),np.ones(6)/6,(np.eye(6)[0]+np.eye(6)[5])/2]
        for profile in profiles:
            for qi,q in enumerate(BATCHES):
                A=np.array([np.ones(6),*[np.array([float(h<k) for h in range(6)]) for k in q]])
                b=A@profile;scalar=[]
                for coeff in c:
                    scalar.append(-endpoint_lp(-coeff,A,b)-endpoint_lp(coeff,A,b));endpoint_calls+=2
                check('direct_fiber_joint_width',max(scalar),float((M[qi]@profile).max()))
        for k in range(1,6):
            js=[j for j in range(1,6) if j!=k]
            for ji,j in enumerate(js):
                A=np.zeros((5,12));A[0,:6]=1;A[1,6:]=1;A[2,:k]=1;A[3,6:6+k]=1;A[4,:j]=1;A[4,6:6+j]=-1
                for t in [0.,.5,1.]:
                    for ri,coeff in enumerate(c):
                        val=-endpoint_lp(np.r_[-coeff,coeff],A,[1,1,t,t,0]);conditional_calls+=1
                        check('direct_conditional_endpoint_width',val,t*ab_all[k-1][ji,ri,0]+(1-t)*ab_all[k-1][ji,ri,1])
        print('Direct fiber LP case complete:',p['id'],flush=True)
    positive=[r['mean_risk_gap'] for r in recomputed if r['float_mean_separation']]
    result={'status':'PASS','scope':'Independent all-case numerical reconstruction, replay and table audit, plus direct LP checks at recorded and boundary profiles; no producer/checker imports, no claim of untouched replication or interval-arithmetic proof.',
        'blocks':len(plans),'pair_cases':len(source),'cohort_counts':dict(Counter(r['cohort'] for r in recomputed)),
        'secondary_lp_checks':secondary_calls,'endpoint_lp_calls':endpoint_calls,'conditional_endpoint_lp_calls':conditional_calls,
        'selected_lp_case_ids':[q[0]['id'] for q in chosen],
        'numerical_mean_separation_cases':len(positive),'minimum_positive_gap':min(positive),
        'separation_gaps_below_1e_6':int(sum(v<1e-6 for v in positive)),'batch_profile_widths_within_1e_7_of_half':int(near_threshold),
        'max_errors':dict(errors),'tolerance':TOL,'elapsed_seconds':time.perf_counter()-started,
        'source_sha256':digest(Path(__file__)),'producer_sha256':digest(HERE/'empirical_shared_audit.py'),
        'plan_sha256':digest(RESULTS/'empirical_plans.json'),'report_sha256':digest(RESULTS/'empirical_report.json'),'cases_sha256':digest(RESULTS/'empirical_cases.csv')}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['max_errors','selected_lp_case_ids']},indent=2))

if __name__=='__main__':main()
