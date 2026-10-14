"""Independently rebuild all saved batch widths from counters and coefficients.

This optional full-source check requires the original BLEM regeneration inputs.
It does not refit forecasts or derive optimal policies. See README for the
separate raw-source chain. Do not present the default saved-ledger check as this
source-data check.
"""
import argparse, csv, hashlib, json, sys, time
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BATCHES=list(combinations(range(1,6),2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--precision-plans',type=Path,required=True)
    p.add_argument('--original-geometry',type=Path,nargs='+',required=True)
    p.add_argument('--external-geometry',type=Path,default=HERE.parents[1]/'external_validation/replay/geometry.json')
    p.add_argument('--original-answers',type=Path,default=ROOT/'work/data_blem_hourly_endpoints.csv')
    p.add_argument('--external-answers',type=Path,default=HERE.parents[1]/'external_heatpump/hourly/train_test_hourly_counters.csv')
    p.add_argument('--output',type=Path,default=HERE/'source_verification.json')
    a=p.parse_args(); start=time.perf_counter()
    derived=json.loads((HERE/'frozen_inputs.json').read_text())['cases']
    plans={r['id']:r for r in json.loads(a.precision_plans.read_text())['plans']}
    source={}
    for path in a.original_geometry+[a.external_geometry]:
        source.update({r['id']:r for r in json.loads(path.read_text())['cases']})
    original,external={},{}
    with a.original_answers.open(newline='') as f:
        for r in csv.DictReader(f):
            original[r['meter'],datetime.fromisoformat(r['interval_start_utc'])]=F(int(r['end_counter_integer'])-int(r['start_counter_integer']),10**10)
    with a.external_answers.open(newline='') as f:
        for r in csv.DictReader(f):
            if r['valid']=='1': external['hpm_'+r['system_id'],datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'))]=F(r['counter_kwh'])
    checked=0; coefficient_rows=0; lp_count=0; max_lp_error=0; seen=set(); lp_cases=[]
    for row in sorted(derived,key=lambda r:r['id']):
        cohort,meter,day,hour=row['id'].split('/')
        dt=datetime.fromisoformat(day).replace(hour=int(hour),tzinfo=timezone.utc)
        if cohort=='original': y=[original[meter,dt+timedelta(hours=h)] for h in range(6)]
        else:
            registers=[external[meter,dt+timedelta(hours=h)] for h in range(7)]
            y=[registers[h+1]-registers[h] for h in range(6)]
        assert min(y)>=0 and sum(y)>0
        x=[v/sum(y) for v in y]
        plan=plans[row['id']]; C=[]
        for case_id, raw, saved in zip(plan['pair_case_ids'],plan['original_c_binary64'],plan['normalized_coefficients_exact']):
            assert source[case_id]['c']==raw
            rational=list(map(F.from_float,raw)); lo=min(rational); span=max(rational)-lo
            coeff=[(v-lo)/span for v in rational]
            assert coeff==list(map(F,saved)); C.append(coeff); coefficient_rows+=1
        for index,q in enumerate(BATCHES):
            cuts=[0,*q,6]
            contrasts=[]
            for c in C:
                # Separate extrema over each observed segment.
                maxima=sum(sum(x[i:j])*max(c[i:j]) for i,j in zip(cuts,cuts[1:]))
                minima=sum(sum(x[i:j])*min(c[i:j]) for i,j in zip(cuts,cuts[1:]))
                contrasts.append(maxima-minima)
            assert max(contrasts)==F(row['batch_widths'][index]),row['id']
            checked+=1
            if meter not in seen:
                # First chronological block per meter: independent endpoint LPs
                # for every pair and batch, with no segment-width helper.
                matrix=np.zeros((3,6)); rhs=[]
                for k,(i,j) in enumerate(zip(cuts,cuts[1:])):
                    matrix[k,i:j]=1;rhs.append(float(sum(x[i:j])))
                for c,value in zip(C,contrasts):
                    cf=np.array(list(map(float,c)))
                    low=linprog(cf,A_eq=matrix,b_eq=rhs,bounds=[(0,None)]*6,method='highs')
                    high=linprog(-cf,A_eq=matrix,b_eq=rhs,bounds=[(0,None)]*6,method='highs')
                    assert low.success and high.success
                    err=abs(-high.fun-low.fun-float(value));max_lp_error=max(max_lp_error,err)
                    assert err<1e-10;lp_count+=2
        if meter not in seen:lp_cases.append(row['id']);seen.add(meter)
    inputs=[HERE/'frozen_inputs.json',a.precision_plans,*a.original_geometry,a.external_geometry,a.original_answers,a.external_answers]
    report={'status':'PASS','blocks':len(derived),'coefficient_rows':coefficient_rows,'exact_batch_widths':checked,
        'exact_width_discrepancies':0,'endpoint_LP_solves':lp_count,'endpoint_LP_cases':lp_cases,
        'max_endpoint_LP_discrepancy':max_lp_error,'LP_comparison_tolerance':1e-10,
        'coefficients':'Exact rational values of stored binary64 forecast-contrast coefficients, normalized in rational arithmetic; not exact decimal measurements or uncertainty bounds on fitted coefficients.',
        'scope':'Recorded original and external counter values joined to existing frozen coefficients. No new model fitting or raw-source authentication; source identity is separately verified by provenance_chain.',
        'inputs':[{'path':str(x),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in inputs],
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'elapsed_seconds':time.perf_counter()-start}
    a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ['status','blocks','coefficient_rows','exact_batch_widths','endpoint_LP_solves','max_endpoint_LP_discrepancy','elapsed_seconds']},indent=2))

if __name__=='__main__':main()
