"""Nominal recorded-answer replay under bounded stored-readout uncertainty.

Uses the separately exported, verified branch policies and LP bounds. Stored
answers are the recorded values; +/-1% is a compatible-record allowance, not
a sampled noise process or device specification. Exact endpoints, two shared
prefix queries, six pairs, original half-width threshold. No rows are dropped.
"""
import argparse,csv,json,time
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from empirical_shared_audit import (HERE,BASE,ROOT,BATCHES,TOL,LP_OPTIONS,
    choose,sha,dump,input_record,load_replay_inputs)
from empirical_capacity import original_answer_vector,widths_at_record
from noise_joint_certify import select_second,policy


def fiber_widths(c,Q,answers,cap,delta):
    rows=[];rhs=[]
    for k in Q:
        q=np.zeros(6);q[:k]=1;z=float(answers[k-1])
        rows.extend([q,-q]);rhs.extend([z+delta,-z+delta])
    widths=[];max_violation=0.
    for contrast in c:
        values=[]
        for sign in [-1,1]:
            r=linprog(sign*contrast,A_ub=rows,b_ub=rhs,A_eq=[np.ones(6)],b_eq=[1.],
                      bounds=[(0,cap)]*6,method='highs',options=LP_OPTIONS)
            if not r.success:raise AssertionError(r.message)
            max_violation=max(max_violation,float(np.max(np.array(rows)@r.x-np.array(rhs))),
                              abs(float(r.x.sum())-1.),float(-r.x.min()),float(r.x.max()-cap))
            values.append(float(r.fun))
        widths.append(-sum(values))
    return np.array(widths),max_violation


def summary(rows):
    valid=[r for r in rows if r['actual_record_satisfies_cap']]
    fields=['adaptive_J','greedy_J','robust_det_batch_J','original_det_batch_J','randomized_batch_expected_J']
    success=['adaptive_success','greedy_success','robust_det_batch_success','original_det_batch_success','randomized_batch_success_probability']
    return {'all_blocks':len(rows),'compatible_records':len(valid),'incompatible_records':len(rows)-len(valid),
        'success_counts_among_compatible':{k:float(sum(r[k] for r in valid)) for k in success},
        'mean_width_among_compatible':{k:float(np.mean([r[k] for r in valid])) if valid else None for k in fields},
        'compatible_adaptive_guarantees':sum(r['adaptive_guarantees_half'] for r in valid),
        'compatible_robust_batch_guarantees':sum(r['robust_det_guarantees_half'] for r in valid)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plans',type=Path,default=HERE/'empirical_external_results/empirical_plans.json')
    p.add_argument('--certification-dir',type=Path,default=HERE/'noise_external_results')
    p.add_argument('--cohort',choices=['external','original','all'],default='external')
    p.add_argument('--original-answers',type=Path,default=ROOT/'work/data_blem_hourly_endpoints.csv')
    p.add_argument('--external-answers',type=Path,default=BASE/'external_heatpump/hourly/train_test_hourly_counters.csv')
    p.add_argument('--output-dir',type=Path,default=HERE/'empirical_noise_results');args=p.parse_args()
    started=time.perf_counter();out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    saved=json.loads(args.plans.read_text());cases={c['id']:c for c in saved['plans'] if args.cohort in ['all',c['cohort']]}
    cert_report=json.loads((args.certification_dir/'report.json').read_text())
    policies=json.loads((args.certification_dir/'frozen_policies.json').read_text())['policies']
    certificates=json.loads((args.certification_dir/'certificates.json').read_text())
    cert_rows={(r['id'],r['scenario']):r for r in json.loads((args.certification_dir/'cases.json').read_text())}
    pi={r['id']:r for r in policies};prepared=[]
    for cert in certificates:
        if cert['id'] not in cases:continue
        case=cases[cert['id']];g=case['geometry'];cp=pi[cert['id']];C=[[F(v) for v in row] for row in cp['normalized_coefficients_exact']]
        assert len(C)==6 and max(abs(float(v)-w) for row,old in zip(C,g['normalized_coefficients']) for v,w in zip(row,old))<1e-12
        greedy_segments=policy(C,g['greedy_first_query'])
        greedy={'first_query':g['greedy_first_query'],'branches':[{'lo':str(v['lo']),'hi':str(v['hi']),'second':v['second']} for v in greedy_segments]}
        batch_bounds=[float(F(b['upper_exact'])) for b in cert['batch_bounds']]
        batch_index=choose(batch_bounds);batch=cert['batch_bounds'][batch_index]['Q']
        prepared.append({'id':case['id'],'scenario':cert['scenario'],'error':cert['error'],'cap':cert['cap'],
            'adaptive':cp,'greedy':greedy,'robust_det_batch':batch,
            'robust_det_batch_upper_exact':cert['batch_bounds'][batch_index]['upper_exact'],
            'original_det_batch':g['best_deterministic_batch'],'randomized_batch_weights':g['randomized_batch_weights']})
    expected={'all':1098,'external':279,'original':819}[args.cohort]
    assert len(cases)==expected and all(sum(p['scenario']==s for p in prepared)==expected for s in cert_report['scenarios'])
    # No fine answer is loaded before the complete policy/batch catalog is saved.
    plan_path=out/'empirical_noise_replay_plans.json';dump(plan_path,{'fine_answers_loaded':False,'plans':prepared})
    original,external,inputs=load_replay_inputs(args);rows=[];max_violation=max_decrease=0.;lp_count=0
    for n,prep in enumerate(prepared,1):
        case=cases[prep['id']];x=original_answer_vector(case,original,external);cap=F(prep['cap']);delta=F(prep['error'])
        valid=max(x)<=cap;cr=cert_rows[prep['id'],prep['scenario']]
        row={'id':case['id'],'cohort':case['cohort'],'meter':case['meter'],'scenario':prep['scenario'],
             'error':str(delta),'cap':str(cap),'actual_record_satisfies_cap':valid,
             'largest_recorded_hour_fraction':float(max(x)),
             'adaptive_guarantees_half':cr['adaptive_half_guarantee'],
             'robust_det_guarantees_half':F(prep['robust_det_batch_upper_exact'])<=F(1,2),
             'adaptive_Q':None,'greedy_Q':None,'robust_det_batch_Q':prep['robust_det_batch'],
             'adaptive_J':None,'greedy_J':None,'robust_det_batch_J':None,'original_det_batch_J':None,
             'randomized_batch_expected_J':None,'adaptive_success':None,'greedy_success':None,
             'robust_det_batch_success':None,'original_det_batch_success':None,'randomized_batch_success_probability':None,
             'evaluated_batch_joint_widths':{}}
        if valid:
            c=np.array([[float(F(v)) for v in q] for q in prep['adaptive']['normalized_coefficients_exact']])
            answers=[sum(x[:k]) for k in range(1,6)];qs={}
            for name in ['adaptive','greedy']:
                pl=prep[name];k=pl['first_query'];j=select_second(pl,answers[k-1],delta,cap);qs[name]=tuple(sorted([k,j]));row[name+'_Q']=[k,j]
            qs['robust_det_batch']=tuple(prep['robust_det_batch']);qs['original_det_batch']=tuple(prep['original_det_batch'])
            weights=np.array(prep['randomized_batch_weights']);required=set(qs.values())|{q for q,w in zip(BATCHES,weights) if w>0}
            widths={}
            for q in sorted(required):
                pair,err=fiber_widths(c,q,answers,float(cap),float(delta));lp_count+=12;max_violation=max(max_violation,err)
                value=float(pair.max());widths[q]=value
                exact=widths_at_record(c,q,x,float(cap));max_decrease=max(max_decrease,float((exact-pair).max()))
            for name,q in qs.items():row[name+'_J']=widths[q];row[name+'_success']=int(widths[q]<=.5+TOL)
            row['randomized_batch_expected_J']=sum(float(w)*widths[q] for q,w in zip(BATCHES,weights) if w>0)
            row['randomized_batch_success_probability']=sum(float(w)*(widths[q]<=.5+TOL) for q,w in zip(BATCHES,weights) if w>0)
            row['evaluated_batch_joint_widths']={','.join(map(str,q)):w for q,w in widths.items()}
            assert row['adaptive_J']<=cr['frozen_adaptive_upper']+TOL
            assert row['robust_det_batch_J']<=float(F(prep['robust_det_batch_upper_exact']))+TOL
        rows.append(row)
        if n%100==0:print('Noisy nominal replay cases:',n,flush=True)
    assert max_violation<TOL and max_decrease<TOL
    dump(out/'empirical_noise_cases.json',rows)
    report={'status':'PASS','scope':__doc__,'cohort':args.cohort,'cases':len(cases),'rows':len(rows),
        'scenarios':cert_report['scenarios'],'plan_before_replay':True,'threshold':.5,
        'normalization':'Original uncapped width; exact normalization of source binary64 coefficients',
        'baseline':'Original mean-optimal randomized batch is frozen, not asserted optimal under caps/errors. Robust deterministic batch chosen from certified all-ten-batch bounds before answers. Greedy is the original uncapped policy with exact branch dispatch; in the capacity-aware adaptive variant it remains an explicitly frozen uncapped control, not an optimized capacity-aware greedy comparator.',
        'summaries':{s:summary([r for r in rows if r['scenario']==s]) for s in cert_report['scenarios']},
        'by_meter':{f'{m}/{s}':summary([r for r in rows if r['meter']==m and r['scenario']==s]) for m in sorted({r['meter'] for r in rows}) for s in cert_report['scenarios']},
        'lp_endpoint_solves':lp_count,'max_primal_violation':max_violation,'max_noisy_width_decrease':max_decrease,
        'inputs':{'uncapped_plans':input_record(args.plans),'frozen_policy':input_record(args.certification_dir/'frozen_policies.json'),
                  'certificates':input_record(args.certification_dir/'certificates.json'),**inputs},
        'replay_plan_sha256':sha(plan_path),'source_sha256':sha(Path(__file__)),'tolerance':TOL,
        'elapsed_seconds':time.perf_counter()-started}
    dump(out/'empirical_noise_report.json',report);print(json.dumps({k:report[k] for k in ['status','summaries','lp_endpoint_solves','elapsed_seconds']},indent=2))

if __name__=='__main__':main()
