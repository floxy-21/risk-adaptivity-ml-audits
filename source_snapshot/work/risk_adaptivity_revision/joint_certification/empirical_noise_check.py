"""Independent two-endpoint LP check of nominal noisy shared-query replay."""
import argparse,csv,hashlib,json
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];TOL=1e-8
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def locate(s):
    p=Path(s);return p if p.is_absolute() else ROOT/p
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',type=Path,default=HERE/'empirical_noise_results')
    p.add_argument('--output',type=Path,default=HERE/'empirical_noise_independent_check.json');a=p.parse_args()
    report=json.loads((a.results_dir/'empirical_noise_report.json').read_text())
    for spec in report['inputs'].values():assert sha(locate(spec['path']))==spec['sha256']
    rows=json.loads((a.results_dir/'empirical_noise_cases.json').read_text())
    plans=json.loads((a.results_dir/'empirical_noise_replay_plans.json').read_text())['plans']
    plans={(r['id'],r['scenario']):r for r in plans}
    cases={r['id']:r for r in json.loads(locate(report['inputs']['uncapped_plans']['path']).read_text())['plans']}
    groups=defaultdict(list)
    for cid in sorted({r['id'] for r in rows}):groups[cases[cid]['meter']].append(cid)
    selected={ids[i] for ids in groups.values() for i in [0,len(ids)//2,len(ids)-1]}
    external={};original={}
    if 'external_counters' in report['inputs']:
        with locate(report['inputs']['external_counters']['path']).open(newline='') as f:
            for r in csv.DictReader(f):
                if r['valid']=='1':external['hpm_'+r['system_id'],datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'))]=F(r['counter_kwh'])
    if 'original_endpoints' in report['inputs']:
        with locate(report['inputs']['original_endpoints']['path']).open(newline='') as f:
            for r in csv.DictReader(f):original[r['meter'],datetime.fromisoformat(r['interval_start_utc'])]=F(int(r['end_counter_integer'])-int(r['start_counter_integer']),10**10)
    maximum=0.;count=0;checked=0
    for row in rows:
        case=cases[row['id']];plan=plans[row['id'],row['scenario']];cap=F(row['cap']);delta=F(row['error'])
        start=datetime.fromisoformat(case['day']).replace(hour=case['start_hour'],tzinfo=timezone.utc)
        if case['cohort']=='original':x=[original[case['meter'],start+timedelta(hours=k)] for k in range(6)]
        else:
            q=[external[case['meter'],start+timedelta(hours=k)] for k in range(7)];x=[v-u for u,v in zip(q,q[1:])]
        x=[v/sum(x) for v in x];valid=max(x)<=cap
        assert row['actual_record_satisfies_cap']==valid
        if not valid:
            assert row['adaptive_J'] is None and row['robust_det_batch_J'] is None;continue
        for label in ['adaptive','greedy']:
            pol=plan[label];k=pol['first_query'];t=sum(x[:k]);branch=next(v for v in pol['branches'] if F(v['lo'])<=t<=F(v['hi']))
            assert row[label+'_Q']==[k,branch['second']]
        if row['id'] not in selected:continue
        checked+=1;c=np.array([[float(F(v)) for v in q] for q in plan['adaptive']['normalized_coefficients_exact']])
        for batch,stored in row['evaluated_batch_joint_widths'].items():
            Q=list(map(int,batch.split(',')));A=[];b=[]
            for k in Q:
                z=float(sum(x[:k]))
                for off in [0,6]:
                    v=np.zeros(12);v[off:off+k]=1;A.extend([v,-v]);b.extend([z+float(delta),-z+float(delta)])
            H=np.zeros((2,12));H[0,:6]=1;H[1,6:]=1;answer=[]
            for contrast in c:
                r=linprog(np.r_[-contrast,contrast],A_ub=A,b_ub=b,A_eq=H,b_eq=[1,1],bounds=[(0,float(cap))]*12,
                          method='highs',options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
                assert r.success,r.message;answer.append(float(-r.fun));count+=1
            maximum=max(maximum,abs(max(answer)-stored))
    assert maximum<TOL
    out={'status':'PASS','scope':__doc__,'all_rows_checked_for_cap_and_dispatch':len(rows),
         'fixed_position_block_ids':sorted(selected),'compatible_selected_scenario_rows':checked,
         'independent_two_endpoint_LPs':count,'max_joint_width_discrepancy':maximum,'tolerance':TOL,
         'source_sha256':sha(Path(__file__)),'replay_rows_sha256':sha(a.results_dir/'empirical_noise_cases.json')}
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
