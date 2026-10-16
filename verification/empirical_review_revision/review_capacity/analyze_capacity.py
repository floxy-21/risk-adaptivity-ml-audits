"""Paired capacity attribution with exact minimum fixed reading budgets.

All planning uses coefficients and the declared cap. Recorded cap compatibility
is joined afterwards, keeping cohort selection separate from information.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
from collections import Counter
import argparse, csv, hashlib, importlib.util, json, time

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ROOT = BASE.parents[1]
INPUT = BASE/'joint_certification/assurance_feasibility/verify_assurance.py'
spec=importlib.util.spec_from_file_location('capacity_input_binding', INPUT)
binding=importlib.util.module_from_spec(spec);spec.loader.exec_module(binding)
SETS=tuple(q for b in range(6) for q in combinations(range(1,6),b))
HALF=F(1,2)
TOL=1e-8

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,data):
    p.write_text(json.dumps(binding.clean(data),indent=2)+'\n',encoding='utf-8')

def cap_width(c,q,cap):
    """Exact max joint terminal width over capped records for a fixed batch."""
    assert cap in (F(1,2),F(1,3))
    cuts=(0,*q,6);values=[]
    for row in c:
        slopes=[]
        for a,b in zip(cuts,cuts[1:]):
            ordered=sorted(row[a:b])
            slopes.extend(hi-lo for hi,lo in zip(reversed(ordered),ordered))
        slopes.sort(reverse=True)
        values.append(cap*sum(slopes[:int(1/cap)]))
    return max(values)

def state(budget,adaptive):
    return 'fixed' if budget<=2 else 'adaptive_only' if adaptive else 'neither'

def summarize(rows):
    out={}
    groups=sorted({(r['cohort'],r['cap']) for r in rows})
    groups+=sorted({(r['cohort']+'/'+r['system'],r['cap']) for r in rows})
    for key,cap in groups:
        group=[r for r in rows if r['cap']==cap and key in (r['cohort'],r['cohort']+'/'+r['system'])]
        valid=[r for r in group if r['compatible']]
        saved=[r for r in group if r['was_reading_saving_case']]
        kept=[r for r in saved if r['compatible']]
        transitions=Counter(r['uncapped_state']+'->'+r['capped_state'] for r in valid)
        out[key+'/cap='+cap]={
            'all_blocks':len(group),'compatible_blocks':len(valid),'excluded_blocks':len(group)-len(valid),
            'paired_transitions':dict(sorted(transitions.items())),
            'uncapped_fixed_budget_histogram_on_compatible':dict(sorted(Counter(r['uncapped_fixed_budget'] for r in valid).items())),
            'capped_fixed_budget_histogram_on_compatible':dict(sorted(Counter(r['capped_fixed_budget'] for r in valid).items())),
            'original_reading_saving_cases':len(saved),
            'saving_cases_excluded':len(saved)-len(kept),
            'saving_cases_compatible':len(kept),
            'saving_cases_now_fixed_at_most_two':sum(r['capped_fixed_budget']<=2 for r in kept),
            'saving_cases_still_adaptive_only':sum(r['capped_state']=='adaptive_only' for r in kept),
            'new_adaptive_only_from_uncapped_neither':transitions['neither->adaptive_only'],
            'uncapped_min_fixed_readings_on_compatible':sum(r['uncapped_fixed_budget'] for r in valid),
            'capped_min_fixed_readings_on_compatible':sum(r['capped_fixed_budget'] for r in valid)}
        assert out[key+'/cap='+cap]['saving_cases_now_fixed_at_most_two']+out[key+'/cap='+cap]['saving_cases_still_adaptive_only']==len(kept)
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--chain-dir',type=Path)
    p.add_argument('--capacity-dir',type=Path,default=BASE/'joint_certification/empirical_external_capacity_results')
    p.add_argument('--budget-dir',type=Path,default=BASE/'joint_certification/reading_budget/executed_external')
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();begun=time.perf_counter();inputs,provenance=binding.source_inputs(a.chain_dir)
    budget_report=read(a.budget_dir/'report.json');assert budget_report['status']=='PASS'
    assert sha(a.budget_dir/'ledger.json')==budget_report['ledger_sha256']
    budgets={r['id']:r for r in read(a.budget_dir/'ledger.json')['rows']}
    report=read(a.capacity_dir/'empirical_capacity_report.json')
    assert report['status']=='PASS'
    assert sha(a.capacity_dir/'empirical_capacity_plans.json')==report['capped_plan_sha256']
    original_path=ROOT/report['inputs']['uncapped_plans']['path']
    assert sha(original_path)==report['inputs']['uncapped_plans']['sha256']
    old_plans={r['id']:r for r in read(original_path)['plans']}
    for item in report['inputs'].values():
        assert sha(ROOT/item['path'])==item['sha256']
    with (a.capacity_dir/'empirical_capacity_cases.csv').open(newline='',encoding='utf-8') as f:
        archived={(r['id'],r['cap_fraction']):r for r in csv.DictReader(f)}
    rows=[];max_delta=0.;boundary=[];normalization_delta=0.
    for idx,case in enumerate(inputs):
        c=case['coefficients'];b=budgets[case['id']]
        assert b['coefficient_digest']==case['coefficient_digest']
        previous=old_plans[case['id']]['geometry']['normalized_coefficients']
        normalization_delta=max(normalization_delta,max(abs(float(x)-y) for rr,old in zip(c,previous) for x,y in zip(rr,old)))
        assert normalization_delta<TOL
        for cap in (F(1,2),F(1,3)):
            old=archived[case['id'],str(cap)]
            values=[(q,cap_width(c,q,cap)) for q in SETS]
            q,w=min(((q,w) for q,w in values if w<=HALF),key=lambda qw:(len(qw[0]),qw[0]))
            two=min(w for q,w in values if len(q)==2)
            delta=abs(float(two)-float(old['det_batch_guarantee']));max_delta=max(max_delta,delta)
            assert delta<TOL,(case['id'],cap,delta)
            if abs(float(two)-.5)<=TOL: boundary.append({'id':case['id'],'cap':str(cap),'exact_two_width':str(two)})
            assert (len(q)<=2)==(old['det_batch_guarantees_half']=='True'),(case['id'],cap,two)
            adaptive=old['adaptive_guarantees_half']=='True'
            assert len(q)>2 or adaptive
            uncapped=state(b['fixed_minimum_readings'],b['adaptive_minimum_readings'] is not None)
            capped=state(len(q),adaptive)
            assert len(q)<=b['fixed_minimum_readings']
            assert uncapped!='adaptive_only' or capped in ('fixed','adaptive_only')
            rows.append({'id':case['id'],'cohort':case['cohort'],'system':case['id'].split('/')[1],
                         'cap':str(cap),'coefficient_digest':case['coefficient_digest'],
                         'compatible':old['actual_record_satisfies_cap']=='True',
                         'uncapped_state':uncapped,'capped_state':capped,
                         'uncapped_fixed_budget':b['fixed_minimum_readings'],'capped_fixed_budget':len(q),
                         'capped_minimum_batch':list(q),'capped_batch_worst_width':w,
                         'capped_adaptive_worst_width':float(old['adaptive_guarantee']),
                         'was_reading_saving_case':uncapped=='adaptive_only',
                         'all_fixed_batches':[{'query':list(q),'width':v} for q,v in values]})
        if (idx+1)%200==0:print('Capacity budget cases:',idx+1,flush=True)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    dump(a.output_dir/'ledger.json',{'status':'PASS','rows':rows})
    result={'status':'PASS','summaries':summarize(rows),'case_cap_rows':len(rows),
            'all_fixed_batches_checked':len(rows)*32,'max_saved_batch_discrepancy':max_delta,
            'max_saved_normalization_discrepancy':normalization_delta,'fixed_half_boundary_cases':boundary,
            'cohort_filter':'Recorded cap compatibility joined only after computing geometry-only budgets.',
            'fixed_arithmetic':'exact rational values of source binary64 coefficients',
            'adaptive_arithmetic':'existing capped piecewise-linear planner; threshold tolerance1e-8; independently checked endpoint LPs',
            'uncapped_target_unchanged':'W_r <= W_r0/2 with uncapped W_r0',
            'provenance':provenance,'source_sha256':sha(__file__),'binding_sha256':sha(INPUT),
            'capacity_report_sha256':sha(a.capacity_dir/'empirical_capacity_report.json'),
            'capacity_cases_sha256':sha(a.capacity_dir/'empirical_capacity_cases.csv'),
            'capacity_plans_sha256':sha(a.capacity_dir/'empirical_capacity_plans.json'),
            'budget_ledger_sha256':sha(a.budget_dir/'ledger.json'),
            'ledger_sha256':sha(a.output_dir/'ledger.json'),'elapsed_seconds':time.perf_counter()-begun}
    dump(a.output_dir/'report.json',result)
    print(json.dumps(binding.clean({k:result[k] for k in ('status','summaries','all_fixed_batches_checked','elapsed_seconds')}),indent=2))

if __name__=='__main__':main()
