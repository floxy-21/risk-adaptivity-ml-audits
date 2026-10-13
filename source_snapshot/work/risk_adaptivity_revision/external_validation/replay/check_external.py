"""Separate all-case rational/LP checks; imports no external replay producer."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal
from collections import defaultdict,Counter
import csv,hashlib,itertools,json,sys,time
import numpy as np
import pandas as pd
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent;RISK=HERE.parents[1]
sys.path.insert(0,str(RISK/'external_validation/math'))
from counter_two_side import two_side

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp(t):return pd.Timestamp(t).strftime('%Y-%m-%dT%H:%M:%SZ')
def main():
    begin=time.perf_counter(); obj=json.loads((HERE/'geometry.json').read_text()); cases=obj['cases']
    with (RISK/'external_heatpump/hourly/train_test_hourly_counters.csv').open(newline='') as f:
        raw={(int(r['system_id']),r['timestamp_utc']):F(r['counter_kwh']) if r['valid']=='1' else None for r in csv.DictReader(f)}
    # Confirm CSV conversion preserved every provider decimal, rather than
    # silently treating a rounded binary64 export as the original readout.
    decimal_rows=0
    for ident in (1,2,7):
        for suffix in ('train_2025H1','test_2025July'):
            path=RISK/'external_heatpump/hourly'/f'system_{ident}_{suffix}.json'
            for t,value in json.loads(path.read_text(),parse_float=Decimal)['heatpump_elec_kwh']:
                expected=F(value) if value is not None else None
                assert raw[ident,stamp(pd.Timestamp(int(t),unit='s',tz='UTC'))]==expected
                decimal_rows+=1
    frame=pd.read_csv(RISK/'external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv',float_precision='round_trip')
    causality_error=0.;lag_count=0;max_source_time_relation=0
    for r in frame.itertuples():
        t=pd.Timestamp(r.timestamp_utc);issue=pd.Timestamp(r.issue_utc);lag=t-pd.Timedelta(days=1)
        assert lag+pd.Timedelta(hours=1)<=issue
        truth=raw[r.system_id,stamp(lag+pd.Timedelta(hours=1))]-raw[r.system_id,stamp(lag)]
        causality_error=max(causality_error,abs(r.daily-float(truth)));lag_count+=1
    assert causality_error<1e-12
    seen=set();groupseen=set();checks=0;max_lp_error=0.;max_rounded_geometry=0.;half_count=0;exact_interval_checks=0
    for case in cases:
        assert case['id'] not in seen;seen.add(case['id'])
        coeff=list(map(F.from_float,case['c']));d=F.from_float(case['d']);E=F(case['E_exact']);W0=F(case['W0_exact'])
        t0=pd.Timestamp(case['day'],tz='UTC')+pd.Timedelta(hours=case['start_hour'])
        cv=[raw[case['system_id'],stamp(t0+pd.Timedelta(hours=h))] for h in range(7)]
        if any(x is None for x in cv) or any(cv[i+1]<cv[i] for i in range(6)):continue
        y=[cv[i+1]-cv[i] for i in range(6)];assert sum(y)==E
        actual=d+sum(a*b for a,b in zip(coeff,y))
        cspan=max(coeff)-min(coeff);assert W0==E*cspan
        if W0:
            two,values=two_side(coeff)
            assert two['value']/cspan==F(case['exact']['A_over_W0'])
            assert two['first']==case['geometry']['first']
        key=(case['system_id'],case['model_a'],case['model_b'])
        do_lp=key not in groupseen and bool(W0)
        if do_lp:groupseen.add(key)
        batch_success=[]
        for q in itertools.combinations(range(1,6),2):
            cuts=[0,*q,6];lo=hi=d;vertex=[]
            for a,b in zip(cuts,cuts[1:]):
                s=sum(y[a:b]);lo+=s*min(coeff[a:b]);hi+=s*max(coeff[a:b])
                vertex.extend([max(coeff[a:b])-min(coeff[a:b])]*(b-a))
            assert lo<=actual<=hi;exact_interval_checks+=1
            batch_success.append([int(v<=cspan/2) for v in vertex])
            if do_lp:
                M=np.array([[int(h<k) for h in range(6)] for k in (*q,6)],dtype=float)
                rhs=M@np.array(list(map(float,y)));cc=np.array(list(map(float,coeff)))
                l=linprog(cc,A_eq=M,b_eq=rhs,bounds=(0,None),method='highs',options={'primal_feasibility_tolerance':1e-9})
                h=linprog(-cc,A_eq=M,b_eq=rhs,bounds=(0,None),method='highs',options={'primal_feasibility_tolerance':1e-9})
                assert l.success and h.success
                err=max(abs((l.fun+float(d))-float(lo)),abs((-h.fun+float(d))-float(hi)))
                max_lp_error=max(max_lp_error,err);assert err<2e-8*max(1,abs(float(lo)),abs(float(hi)))
                checks+=2
        if W0 and case['exact']['batch_optimum']=='1/2':
            ex=case['exact'];w=list(map(F,ex['adverse_weights']));assert min(w)>=0 and sum(w)==1
            upper=max(sum(x*s for x,s in zip(w,col)) for col in batch_success);assert upper==F(1,2)
            intervals=ex['cover_intervals'];assert len(intervals)==2
            parsed=sorted([(F(z['lo']),F(z['hi']),F(z['a']),F(z['b'])) for z in intervals])
            assert parsed[0][0]==0 and parsed[1][1]==1 and parsed[0][1]>=parsed[1][0]
            for lo,hi,a,b in parsed:
                assert a*lo+b*(1-lo)<=cspan/2 and a*hi+b*(1-hi)<=cspan/2
            half_count+=1
    report=json.loads((HERE/'report.json').read_text())
    assert len(seen)==report['counts']['geometry_tasks'] and half_count==report['counts']['exact_half']
    with (HERE/'replay_cases.csv').open(newline='') as f: rows=list(csv.DictReader(f))
    assert len(rows)==report['verification']['policy_rows']
    for name in ['adaptive','greedy_adaptive','det_batch','mean_batch','uniform_batch','full_trace']:
        selected=[r for r in rows if r['policy']==name]
        assert len(selected)==report['counts']['replay_tasks']
        summaries=[r for r in report['policy_summary'] if r['policy']==name];assert len(summaries)==1
        for metric in ['success_0.5','relative_width','scaled_width','winner_probability','requested_samples']:
            assert abs(sum(float(r[metric]) for r in selected)/len(selected)-summaries[0][metric])<1e-10
    out={'status':'PASS','scope':'Independent internal arithmetic/LP checker; no fresh refit or physical-timestamp validation',
         'geometry_cases':len(seen),'rational_interval_checks':exact_interval_checks,'rational_half_witnesses':half_count,
         'independent_LP_solves':checks,'LP_sample_rule':'earliest positive-width case for each meter/model pair; all10batches',
         'max_LP_endpoint_discrepancy':max_lp_error,'LP_feasibility_tolerance':1e-9,'comparison_tolerance':2e-8,
         'persistence_rows_checked':lag_count,'max_persistence_difference':causality_error,
         'raw_provider_decimal_rows_checked':decimal_rows,'maximum_raw_decimal_export_error':0,
         'chronology_scope':'lag endpoint API-grid labels are no later than declared issue; native sample times and historical delivery are unknown',
         'hashes':{p.name:sha(p) for p in [HERE/'run_external.py',HERE/'geometry.json',HERE/'replay_cases.csv',HERE/'report.json']},
         'seconds':time.perf_counter()-begin}
    (HERE/'independent_checks.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))

if __name__=='__main__':main()
