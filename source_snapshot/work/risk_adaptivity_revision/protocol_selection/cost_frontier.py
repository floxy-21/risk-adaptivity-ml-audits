"""Exact, post-analysis resource tradeoff for the supplied 29 certificates.

No new data, policies, forecasts, retrieval services or measured costs.
Cost units are normalized declared charges, not currency or HTTP latency.
"""
from collections import Counter
from decimal import Decimal
from fractions import Fraction as F
import argparse
import csv
import hashlib
import json
from pathlib import Path
from selector import Selector

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
RATIOS=('0','1/4','1/2','1','2','4')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=HERE/'cost_frontier_results')
    args=parser.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    selector=Selector();interface=selector.scenario('restricted_three_readings')
    cases=[];summaries=[]
    for ratio_token in RATIOS:
        ratio=F(ratio_token);totals={name:F(0) for name in ['fixed_three','adaptive_with_fallback','cost_aware']}
        selected_counts=Counter();selected_readings=selected_rounds=0
        for case_id in sorted(selector.fixed):
            plan=selector.select(case_id,interface)
            candidates=[c for c in plan['candidates'] if c['admissible']]
            if not candidates or any(c['protocol']=='bulk_range' for c in candidates):
                raise ValueError('Expected the declared restricted certified catalogue')
            fixed=next(c for c in candidates if c['protocol']=='fixed_batch')
            adaptive=next((c for c in candidates if c['protocol']=='adaptive'),None)
            def cost(c):return F(c['optional_readings'])+ratio*c['information_rounds']
            selected=min(candidates,key=lambda c:(cost(c),c['information_rounds'],c['optional_readings'],c['protocol']))
            adaptive_baseline=adaptive or fixed
            totals['fixed_three']+=cost(fixed)
            totals['adaptive_with_fallback']+=cost(adaptive_baseline)
            totals['cost_aware']+=cost(selected)
            selected_counts[selected['protocol']]+=1
            selected_readings+=selected['optional_readings'];selected_rounds+=selected['information_rounds']
            cases.append({'case_id':case_id,'system_id':plan['system_id'],
                'round_to_reading_cost_ratio_exact':ratio_token,
                'fixed_three_cost_exact':str(cost(fixed)),
                'adaptive_with_fallback_cost_exact':str(cost(adaptive_baseline)),
                'adaptive_baseline_uses_fixed_fallback':adaptive is None,
                'cost_aware_cost_exact':str(cost(selected)),
                'chosen_protocol':selected['protocol'],
                'reserved_scalar_readings':selected['optional_readings'],
                'information_rounds':selected['information_rounds'],
                'selected_certificate':selected['certificate'],
                'selected_certified_width_over_W0_upper_exact':selected['certified_upper_exact'],
                'selected_query_boundaries':selected.get('query_boundaries'),
                'selected_first_query':selected.get('first_query'),
                'selected_successor_boundaries':selected.get('successor_boundaries',[]),
                'candidate_costs':[{'protocol':c['protocol'],'cost_exact':str(cost(c)),
                    'readings':c['optional_readings'],'rounds':c['information_rounds'],
                    'certificate':c['certificate']} for c in candidates]})
        summaries.append({'round_to_reading_cost_ratio_exact':ratio_token,'cases':29,
            'fixed_three_cost_exact':str(totals['fixed_three']),
            'adaptive_with_fallback_cost_exact':str(totals['adaptive_with_fallback']),
            'cost_aware_cost_exact':str(totals['cost_aware']),
            'cost_aware_protocol_counts':dict(selected_counts),
            'cost_aware_reserved_readings':selected_readings,'cost_aware_information_rounds':selected_rounds,
            'fraction_saved_vs_fixed_exact':str(1-totals['cost_aware']/totals['fixed_three']),
            'fraction_saved_vs_adaptive_with_fallback_exact':str(1-totals['cost_aware']/totals['adaptive_with_fallback'])})
    trials_path=BASE/'external_validation/operational/http_benchmark_20261012/trials.json'
    trials=json.loads(trials_path.read_text(),parse_float=Decimal)
    measured={}
    for policy in ['full_hourly_range','adaptive']:
        rows=[r for r in trials if r['policy']==policy]
        means={key:sum(F(r[key]) for r in rows)/len(rows)
               for key in ['requests','information_rounds','api_io_seconds','body_bytes_received']}
        measured[policy]={'trials':len(rows),**{key+'_mean_exact':str(value) for key,value in means.items()},
                         'api_io_seconds_mean':float(means['api_io_seconds'])}
    report={'status':'PASS','analysis_type':'post-analysis exact declared-cost sensitivity',
        'cases':29,'case_ratio_rows':len(cases),'ratio_grid_exact':list(RATIOS),
        'model':'cost = c_read * reserved_scalar_readings + c_round * information_rounds; c_read=1',
        'switching_condition':'For each of the 22 adaptive-certified cases, adaptive costs 2+2r and fixed costs 3+r: adaptive iff r<1; at r=1 choose fixed for fewer rounds. Seven cases always use fixed-three.',
        'panel_cost_identities':{'fixed_three':'87+29r','adaptive_with_fallback':'65+51r',
                                 'cost_aware':'min(87+29r,65+51r)'},
        'tie_rule':'minimum modeled cost, then fewer information rounds, then fewer readings, then protocol name',
        'summaries':summaries,'recorded_api':measured,
        'recorded_api_scope':'Existing three-task, six-trials-per-policy microbenchmark; separate exact-stored-grid model. Timings are not prices or observations on the 29 error-sensitivity cases.',
        'scope':'Minimum over supplied per-case certified catalogue under a hypothetical restricted interface. No shared requests, stopping optimization, monetary estimates, field benefit or superiority over the best fixed baseline is claimed.',
        'baseline_interpretation':'Fixed-three is already optimal for r>=1 and adaptive-with-fixed-fallback already optimal for r<=1. The selector prevents choosing the wrong resource priority; it does not improve upon either baseline in its favorable region.',
        'source_hashes':{'protocol_lock.json':sha(HERE/'protocol_lock.json'),
                        'selector.py':sha(HERE/'selector.py'),
                        'fixed_batch_certificates.json':sha(BASE/'external_validation/stored_error_fallback/fixed_batch_certificates.json'),
                        'branch_certificates.json':sha(BASE/'external_validation/stored_error_fallback/branch_certificates.json'),
                        'recorded_trials.json':sha(trials_path)},
        'source_sha256':sha(Path(__file__)),'new_network_calls':0,'new_model_fits':0}
    for name,value in [('case_ledger.json',cases),('report.json',report)]:
        (out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    fields=['case_id','system_id','round_to_reading_cost_ratio_exact','chosen_protocol',
            'reserved_scalar_readings','information_rounds','fixed_three_cost_exact',
            'adaptive_with_fallback_cost_exact','adaptive_baseline_uses_fixed_fallback','cost_aware_cost_exact']
    with (out/'case_ledger.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows({k:row[k] for k in fields} for row in cases)
    print(json.dumps({'status':'PASS','rows':len(cases),'summaries':summaries},indent=2))


if __name__=='__main__':main()
