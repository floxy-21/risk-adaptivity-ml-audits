"""Replay a frozen precision-matched batch challenger with identical resources.

Uses exact rational widths and known-loss constants at stored records. Policy
mixtures and full-domain bounds are fixed in the separate precision manifest.
"""
import argparse,csv,json,time
from datetime import datetime,timedelta,timezone
from fractions import Fraction as F
from pathlib import Path
from empirical_shared_audit import HERE,BASE,ROOT,BATCHES,sha,dump,input_record
from decision_replay import load_data,decision

def width(C,x,q):
    cuts=(0,*q,6)
    return max(sum(sum(x[a:b])*(max(c[a:b])-min(c[a:b])) for a,b in zip(cuts,cuts[1:])) for c in C)
def aggregate(rows):
    fields=['adaptive_J','precision_batch_expected_J','adaptive_success','precision_batch_success_probability',
            'adaptive_winner','precision_batch_winner_probability','adaptive_ranking','precision_batch_ranking_probability']
    return {'blocks':len(rows),'means':{k:sum(r[k] for r in rows)/len(rows) for k in fields},
            'totals':{k:sum(r[k] for r in rows) for k in fields},
            'exact_vs_original_threshold_mismatches':sum(r['exact_vs_original_success_mismatch'] for r in rows)}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',choices=['external','all'],default='external')
    p.add_argument('--precision-plans',type=Path,default=HERE/'precision_external_results/plans.json')
    p.add_argument('--plans',type=Path,default=HERE/'empirical_external_results/empirical_plans.json')
    p.add_argument('--ledger',type=Path,default=HERE/'empirical_external_results/empirical_cases.csv')
    p.add_argument('--original-geometry',type=Path,nargs='+',default=[BASE/'counter_adaptive/pilot/geometry.json',BASE/'counter_adaptive/continuation/geometry.json'])
    p.add_argument('--external-geometry',type=Path,default=BASE/'external_validation/replay/geometry.json')
    p.add_argument('--original-answers',type=Path,default=ROOT/'work/data_blem_hourly_endpoints.csv')
    p.add_argument('--external-answers',type=Path,default=BASE/'external_heatpump/hourly/train_test_hourly_counters.csv')
    p.add_argument('--output-dir',type=Path,default=HERE/'empirical_precision_results');a=p.parse_args();start_time=time.perf_counter()
    precision=json.loads(a.precision_plans.read_text());policies={r['id']:r for r in precision['plans']}
    plans=json.loads(a.plans.read_text())['plans'];assert len(plans)==(279 if a.cohort=='external' else 1098)
    assert set(policies)=={r['id'] for r in plans} and precision['fine_answers_loaded'] is False
    with a.ledger.open(newline='') as f:ledger={r['id']:r for r in csv.DictReader(f)}
    # The complete challenger catalog already exists and is hash-recorded before answers are read.
    plan_sha=sha(a.precision_plans);case_map,original,external,sources=load_data(a);rows=[]
    for p in plans:
        first=datetime.fromisoformat(p['day']).replace(hour=p['start_hour'],tzinfo=timezone.utc)
        if p['cohort']=='original':y=[original[p['meter'],first+timedelta(hours=i)] for i in range(6)]
        else:
            counters=[external[p['meter'],first+timedelta(hours=i)] for i in range(7)];y=[v-u for u,v in zip(counters,counters[1:])]
        assert sum(y)>0 and min(y)>=0;x=[v/sum(y) for v in y]
        frozen=policies[p['id']];C=[[F(v) for v in c] for c in frozen['normalized_coefficients_exact']]
        pi=list(map(F,frozen['batch_weights']));assert sum(pi)==1 and min(pi)>=0
        widths=[width(C,x,q) for q in BATCHES];success=[int(w<=F(1,2)) for w in widths]
        old=ledger[p['id']];aq=tuple(sorted([int(old['adaptive_first']),int(old['adaptive_second'])]));ai=BATCHES.index(aq)
        pairs=[case_map[k] for k in p['pair_case_ids']];decisions=[decision(pairs,y,q) for q in BATCHES]
        r={k:p[k] for k in ['id','cohort','meter']}
        r.update({'adaptive_J':float(widths[ai]),'precision_batch_expected_J':float(sum(w*v for w,v in zip(pi,widths))),
            'adaptive_success':success[ai],'precision_batch_success_probability':float(sum(w*v for w,v in zip(pi,success))),
            'adaptive_winner':decisions[ai]['winner'],'precision_batch_winner_probability':float(sum(w*v['winner'] for w,v in zip(pi,decisions))),
            'adaptive_ranking':decisions[ai]['ranking'],'precision_batch_ranking_probability':float(sum(w*v['ranking'] for w,v in zip(pi,decisions))),
            'policy_kind':frozen['policy_kind'],'precision_lower_exact':frozen['precision_lower_exact'],
            'precision_upper_exact':frozen['precision_upper_exact'],'continuum_optimum_identified':frozen['continuum_optimum_identified'],
            'batch_joint_widths_exact':list(map(str,widths)),'batch_successes':success,'batch_weights_exact':list(map(str,pi)),
            'adaptive_queries':list(aq),'exact_vs_original_success_mismatch':success[ai]!=int(float(old['adaptive_recorded_success']))})
        rows.append(r)
    out=a.output_dir;out.mkdir(parents=True,exist_ok=True);dump(out/'cases.json',rows)
    report={'status':'PASS','scope':__doc__,'cohort':a.cohort,'cases':len(rows),
        'cohorts':{k:aggregate([r for r in rows if r['cohort']==k]) for k in sorted({r['cohort'] for r in rows})},
        'by_meter':{k:aggregate([r for r in rows if r['meter']==k]) for k in sorted({r['meter'] for r in rows})},
        'strict_threshold':'Exact rational half-width and strict zero for winner decisions; no numerical tolerance in outcome indicators',
        'inputs':{'precision_plans':input_record(a.precision_plans),'shared_plans':input_record(a.plans),'ledger':input_record(a.ledger)},
        'data_source_hashes':sources,'frozen_challenger_sha256':plan_sha,'source_sha256':sha(Path(__file__)),
        'new_network_calls':0,'new_fits':0,'elapsed_seconds':time.perf_counter()-start_time}
    dump(out/'report.json',report);print(json.dumps({k:report[k] for k in ['status','cohorts','elapsed_seconds']},indent=2))
if __name__=='__main__':main()
