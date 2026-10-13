"""Independent numerical checks of shared-query feasibility outputs.

Uses endpoint LPs for 18 fixed-position blocks, not the producer's width or
envelope routines. This remains floating-point validation, not exact proof.
"""
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from fractions import Fraction as F
import argparse,csv,hashlib,itertools,json
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OPTIONS={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}
TOL=1e-8


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def location(value):
    p=Path(value);return p if p.is_absolute() else ROOT/p
def solve(objective,A,b):
    r=linprog(objective,A_eq=A,b_eq=b,bounds=[(0,None)]*len(objective),method='highs',options=OPTIONS)
    if not r.success:raise AssertionError(r.message)
    return float(r.fun)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',type=Path,default=HERE/'empirical_external_results')
    p.add_argument('--output',type=Path,default=HERE/'empirical_independent_check.json');args=p.parse_args()
    report=json.loads((args.results_dir/'empirical_report.json').read_text())
    saved=json.loads((args.results_dir/'empirical_plans.json').read_text());plans=saved['plans']
    cohort=report.get('cohort','all')
    assert len(plans)=={'all':1098,'original':819,'external':279}[cohort]
    for source in report['inputs'].values():assert sha(location(source['path']))==source['sha256']
    original_cases={}
    for name,spec in report['inputs'].items():
        if name not in ['original_endpoints','external_counters']:
            for row in json.loads(location(spec['path']).read_text())['cases']:original_cases[row['id']]=row
    batches=list(itertools.combinations(range(1,6),2));max_matrix_error=max_game_gap=0.
    groups=defaultdict(list)
    for case in plans:
        g=case['geometry'];coeff=np.array([original_cases[k]['c'] for k in case['pair_case_ids']])
        c=(coeff-coeff.min(axis=1)[:,None])/np.ptp(coeff,axis=1)[:,None]
        assert np.max(abs(c-np.array(g['normalized_coefficients'])))<=TOL and len(c)==6
        # Independently form each joint vertex value by locating the hour's
        # information segment and comparing every model-pair coefficient.
        V=np.zeros((6,10))
        for h in range(6):
            for qi,q in enumerate(batches):
                cuts=(0,*q,6);a,b=next((a,b) for a,b in zip(cuts,cuts[1:]) if a<=h<b)
                V[h,qi]=max(max(row[a:b])-min(row[a:b]) for row in c)
        max_matrix_error=max(max_matrix_error,float(np.max(abs(V-np.array(g['joint_vertex_matrix'])))))
        pi=np.array(g['randomized_batch_weights']);w=np.array(g['adverse_vertex_weights'])
        assert min(pi)>=-TOL and min(w)>=-TOL and abs(pi.sum()-1)<TOL and abs(w.sum()-1)<TOL
        gap=float((V@pi).max()-(w@V).min());max_game_gap=max(max_game_gap,gap)
        assert gap<TOL
        assert g['adaptive_deterministic_guarantee']<=g['deterministic_batch_guarantee']+TOL
        groups[case['meter']].append(case)
    # Predetermined first, middle and last block of each of six meter series,
    # without conditioning on any effect size or successful outcome.
    selected=[]
    for meter,cases in sorted(groups.items()):
        cases=sorted(cases,key=lambda c:c['id']);selected.extend(cases[i] for i in [0,len(cases)//2,len(cases)-1])
    original={};external={}
    if 'original_endpoints' in report['inputs']:
        with location(report['inputs']['original_endpoints']['path']).open(newline='') as f:
            for row in csv.DictReader(f):original[row['meter'],datetime.fromisoformat(row['interval_start_utc'])]=F(int(row['end_counter_integer'])-int(row['start_counter_integer']),10**10)
    if 'external_counters' in report['inputs']:
        with location(report['inputs']['external_counters']['path']).open(newline='') as f:
            for row in csv.DictReader(f):
                if row['valid']=='1':external['hpm_'+row['system_id'],datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))]=F(row['counter_kwh'])
    with (args.results_dir/'empirical_cases.csv').open(newline='') as f:outcomes={r['id']:r for r in csv.DictReader(f)}
    conditional_lps=endpoint_lps=0;max_conditional_error=max_endpoint_error=0.
    for case in selected:
        g=case['geometry'];c=np.array(g['normalized_coefficients']);n=6
        for k in range(1,6):
            for j in range(1,6):
                if j==k:continue
                ji=g['second_query_dictionaries'][k-1].index(j)
                for t in [1/3,2/3]:
                    A=np.zeros((5,12));A[0,:6]=1;A[1,6:]=1;A[2,:k]=1;A[3,6:6+k]=1
                    A[4,:j]=1;A[4,6:6+j]=-1
                    for ri,contrast in enumerate(c):
                        actual=-solve(np.r_[-contrast,contrast],A,[1,1,t,t,0]);conditional_lps+=1
                        slope,intercept=g['conditional_lines'][k-1][ji][ri]
                        max_conditional_error=max(max_conditional_error,abs(actual-(slope*t+intercept)))
        start=datetime.fromisoformat(case['day']).replace(hour=case['start_hour'],tzinfo=timezone.utc)
        if case['cohort']=='original':y=[original[case['meter'],start+timedelta(hours=i)] for i in range(6)]
        else:
            counter=[external[case['meter'],start+timedelta(hours=i)] for i in range(7)]
            y=[b-a for a,b in zip(counter,counter[1:])]
        x=np.array([float(v/sum(y)) for v in y]);outcome=outcomes[case['id']]
        choices={'adaptive_recorded_J':sorted([int(outcome['adaptive_first']),int(outcome['adaptive_second'])]),
                 'det_batch_recorded_J':g['best_deterministic_batch']}
        for field,q in choices.items():
            A=np.zeros((3,6));A[0]=1
            for i,k in enumerate(q,1):A[i,:k]=1
            b=[1,*[x[:k].sum() for k in q]];widths=[]
            for contrast in c:
                widths.append(-solve(-contrast,A,b)-solve(contrast,A,b));endpoint_lps+=2
            max_endpoint_error=max(max_endpoint_error,abs(max(widths)-float(outcome[field])))
    assert max_matrix_error<TOL and max_conditional_error<TOL and max_endpoint_error<TOL
    result={'status':'PASS','all_blocks_checked':len(plans),'all_positive_width_pairs':6*len(plans),
        'fixed_position_blocks_for_lp_crosscheck':len(selected),'conditional_endpoint_lps':conditional_lps,
        'recorded_endpoint_lps':endpoint_lps,'max_joint_vertex_error':max_matrix_error,
        'max_primal_dual_gap':max_game_gap,'max_conditional_line_error':max_conditional_error,
        'max_recorded_width_error':max_endpoint_error,'tolerance':TOL,
        'selected_block_ids':[c['id'] for c in selected],
        'scope':'Independent numerical endpoint-LP and finite-game checks; not exact rational certification or exhaustive verification of empirical adaptive policies',
        'source_sha256':sha(Path(__file__)),'plan_sha256':sha(args.results_dir/'empirical_plans.json')}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
