"""Outcome-informed LP-face diagnostic. These oracle extrema are not policies.

All selected cohort blocks retained. Optimizing with the held-out answers is only a
diagnostic for sensitivity to choosing among mean-risk-optimal batch mixtures.
"""
import argparse,csv,hashlib,itertools,json,time
from datetime import datetime,timedelta,timezone
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];D=HERE/'empirical_results'
FACE_ALLOWANCE=1e-9;CHECK=1e-8
OPTIONS={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}
Q=list(itertools.combinations(range(1,6),2))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    global D
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort',choices=['external','all'],default='external')
    parser.add_argument('--results-dir',type=Path)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    D=args.results_dir or HERE/('empirical_external_results' if args.cohort=='external' else 'empirical_results')
    diagnostic_dir=args.output_dir or HERE/('independent_tie_external' if args.cohort=='external' else 'independent_tie_all')
    diagnostic_dir.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();report=json.loads((D/'empirical_report.json').read_text())
    plans=json.loads((D/'empirical_plans.json').read_text())['plans']
    outputs={r['id']:r for r in csv.DictReader((D/'empirical_cases.csv').open(newline=''))}
    orig={};ext={}
    if 'original_endpoints' in report['inputs']:
        for r in csv.DictReader((ROOT/Path(report['inputs']['original_endpoints']['path'].replace(chr(92),'/'))).open(newline='')):
            orig[r['meter'],datetime.fromisoformat(r['interval_start_utc'])]=Fraction(int(r['end_counter_integer'])-int(r['start_counter_integer']),10**10)
    for r in csv.DictReader((ROOT/Path(report['inputs']['external_counters']['path'].replace(chr(92),'/'))).open(newline='')):
        if r['valid']=='1':ext['hpm_'+r['system_id'],datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'))]=Fraction(r['counter_kwh'])
    results=[];max_violation=0.;lp_count=0
    for p in plans:
        g=p['geometry'];c=np.array(g['normalized_coefficients']);V=np.array(g['joint_vertex_matrix']);R=g['randomized_batch_optimum']
        start=datetime.fromisoformat(p['day']).replace(hour=p['start_hour'],tzinfo=timezone.utc)
        if p['cohort']=='original':y=[orig[p['meter'],start+timedelta(hours=i)] for i in range(6)]
        else:
            counter=[ext[p['meter'],start+timedelta(hours=i)] for i in range(7)]
            y=[b-a for a,b in zip(counter,counter[1:])]
        allwidth=[]
        for q in Q:
            endpoints=(0,*q,6)
            w=sum(float(sum(y[a:b])/sum(y))*(c[:,a:b].max(axis=1)-c[:,a:b].min(axis=1)) for a,b in zip(endpoints,endpoints[1:]))
            allwidth.append(max(w))
        widths=np.array(allwidth);success=(widths<=.5+CHECK).astype(float)
        out=outputs[p['id']]
        row={'id':p['id'],'cohort':p['cohort'],'meter':p['meter'],
            'adaptive_recorded_J':float(out['adaptive_recorded_J']),
            'adaptive_recorded_success':float(out['adaptive_recorded_success']),
            'declared_batch_recorded_J':float(out['randomized_batch_recorded_expected_J']),
            'declared_batch_recorded_success':float(out['randomized_batch_recorded_success_probability'])}
        for name,objective in [('width',widths),('success',success)]:
            for sense in ['min','max']:
                sign=1 if sense=='min' else -1
                r=linprog(sign*objective,A_ub=V,b_ub=np.full(6,R+FACE_ALLOWANCE),A_eq=[np.ones(10)],b_eq=[1],bounds=[(0,None)]*10,method='highs',options=OPTIONS)
                if not r.success:raise AssertionError((p['id'],name,sense,r.message))
                violation=max(float((V@r.x).max()-R-FACE_ALLOWANCE),abs(r.x.sum()-1),-float(r.x.min()),0.)
                max_violation=max(max_violation,violation);assert violation<CHECK
                row[f'oracle_{sense}_{name}']=float(objective@r.x)
                lp_count+=1
        assert row['oracle_min_width']-CHECK<=row['declared_batch_recorded_J']<=row['oracle_max_width']+CHECK
        assert row['oracle_min_success']-CHECK<=row['declared_batch_recorded_success']<=row['oracle_max_success']+CHECK
        row['width_face_range']=row['oracle_max_width']-row['oracle_min_width']
        row['success_face_range']=row['oracle_max_success']-row['oracle_min_success']
        results.append(row)
    def summarize(rows):
        keys=[k for k in rows[0] if k not in ['id','cohort','meter']]
        means={k:float(np.mean([r[k] for r in rows])) for k in keys}
        return {'blocks':len(rows),'means':means,
            'nontrivial_width_face_range':sum(r['width_face_range']>1e-6 for r in rows),
            'nontrivial_success_face_range':sum(r['success_face_range']>1e-6 for r in rows),
            'adaptive_width_strictly_better_than_any_primary_face_batch_on_record':sum(r['adaptive_recorded_J']+CHECK<r['oracle_min_width'] for r in rows),
            'adaptive_success_strictly_better_than_any_primary_face_batch_on_record':sum(r['adaptive_recorded_success']>r['oracle_max_success']+CHECK for r in rows),
            'max_width_face_range':max(r['width_face_range'] for r in rows),'max_success_face_range':max(r['success_face_range'] for r in rows)}
    target=diagnostic_dir/'cases.csv'
    with target.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    final={'status':'PASS','scope':'All-block outcome-informed extrema over primary minimax-mean-joint-width optimum face. These record-specific oracle choices use withheld answers and are not deployable policies or precision-optimal minimax solutions.',
        'primary_face_allowance':FACE_ALLOWANCE,'numerical_check_tolerance':CHECK,'lp_options':OPTIONS,'lp_count':lp_count,'maximum_feasibility_violation':max_violation,
        **({'original':summarize([r for r in results if r['cohort']=='original'])} if args.cohort=='all' else {}),
        'external':summarize([r for r in results if r['cohort']=='external']),
        'by_meter':{m:summarize([r for r in results if r['meter']==m]) for m in sorted({r['meter'] for r in results})},
        'elapsed_seconds':time.perf_counter()-started,'checker_sha256':sha(Path(__file__)),'plan_sha256':sha(D/'empirical_plans.json'),'cases_sha256':sha(D/'empirical_cases.csv'),'diagnostic_rows_sha256':sha(target)}
    (diagnostic_dir/'report.json').write_text(json.dumps(final,indent=2)+'\n')
    print(json.dumps({k:final[k] for k in [x for x in ['status','original','external','lp_count','maximum_feasibility_violation','elapsed_seconds'] if x in final]},indent=2))

if __name__=='__main__':main()
