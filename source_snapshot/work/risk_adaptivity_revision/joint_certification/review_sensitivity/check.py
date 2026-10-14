"""Solver-free cross-check of the sensitivity ledgers and saved source results.

This checker imports no producer functions. It verifies frozen widths against
the existing precision replay, choices against the original shared ledger,
all threshold outcomes, paired cells, gap summaries and bootstrap intervals.
It does not substitute for the separately executed raw-source chain.
"""
import argparse, ast, csv, hashlib, json, math
from collections import Counter
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path

HERE=Path(__file__).resolve().parent
BATCHES=list(combinations(range(1,6),2))
NAMES=['adaptive','fixed','greedy','randomized_mean','randomized_half_precision']


def percentile(values,p):
    values=sorted(values); x=(len(values)-1)*p;i=math.floor(x);f=x-i
    return values[i]+f*(values[min(i+1,len(values)-1)]-values[i])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,default=HERE/'results')
    p.add_argument('--output',type=Path,default=HERE/'independent_check.json')
    args=p.parse_args();out=args.results
    data=json.loads((HERE/'frozen_inputs.json').read_text());inputs={r['id']:r for r in data['cases']}
    source_run=json.loads((HERE/'source_verification.json').read_text())
    assert source_run['status']=='PASS'
    assert source_run['inputs'][0]['sha256']==hashlib.sha256((HERE/'frozen_inputs.json').read_bytes()).hexdigest()
    source={r['id']:r for r in json.loads((HERE.parent/'empirical_precision_all_results/cases.json').read_text())}
    with (HERE.parent/'empirical_all_panel_cases.csv').open(newline='') as f: original={r['id']:r for r in csv.DictReader(f)}
    observed=json.loads((out/'threshold_cases.json').read_text())
    strict_observed=json.loads((out/'strict_threshold_cases.json').read_text())
    assert len(inputs)==len(source)==len(original)==1098 and len(observed)==5490
    assert Counter(r['cohort'] for r in inputs.values())=={'original':819,'external':279}
    for r in inputs.values():
        s=source[r['id']]; l=original[r['id']]
        assert r['batch_widths']==s['batch_joint_widths_exact']
        assert r['randomized_half_precision_weights']==s['batch_weights_exact']
        assert r['lower']==s['precision_lower_exact'] and r['upper']==s['precision_upper_exact']
        assert BATCHES[r['adaptive_batch_index']]==tuple(sorted(s['adaptive_queries']))
        assert BATCHES[r['fixed_batch_index']]==tuple(ast.literal_eval(l['det_batch_queries']))
        assert BATCHES[r['greedy_batch_index']]==tuple(sorted([int(l['greedy_first']),int(l['greedy_second'])]))
    independent={}
    strict_independent={}
    for row in observed:
        frozen=inputs[row['id']];threshold=F(row['threshold'])+F(1,10**8)
        successes=[int(F(w)<=threshold) for w in frozen['batch_widths']]
        expected=[F(successes[frozen[name+'_batch_index']]) for name in NAMES[:3]]
        expected.extend(sum(F(w)*s for w,s in zip(frozen[name+'_weights'],successes)) for name in NAMES[3:])
        assert expected==[F(row['success'][name]) for name in NAMES]
        independent[row['id'],row['threshold']]=dict(zip(NAMES,expected))
    for row in strict_observed:
        frozen=inputs[row['id']]; success=[int(F(w)<=F(row['threshold'])) for w in frozen['batch_widths']]
        expected=[F(success[frozen[name+'_batch_index']]) for name in NAMES[:3]]
        expected.extend(sum(F(w)*s for w,s in zip(frozen[name+'_weights'],success)) for name in NAMES[3:])
        assert expected==[F(row['success'][name]) for name in NAMES]
        strict_independent[row['id'],row['threshold']]=dict(zip(NAMES,expected))
    # Reconcile all half-target means to the previously published ledger.
    mappings={'adaptive':'adaptive_recorded_success','fixed':'det_batch_recorded_success',
              'greedy':'greedy_recorded_success','randomized_mean':'randomized_batch_recorded_success_probability'}
    max_half_difference=0
    for case_id,r in original.items():
        for name,key in mappings.items():
            delta=abs(float(independent[case_id,'1/2'][name])-float(r[key]));max_half_difference=max(max_half_difference,delta)
            assert delta<1e-8
        # The pre-existing precision replay used an exact threshold, unlike
        # the general shared replay. Verify its saved result under its own rule.
        strict=sum(F(w)*int(F(v)<=F(1,2)) for w,v in zip(inputs[case_id]['randomized_half_precision_weights'],inputs[case_id]['batch_widths']))
        assert abs(float(strict)-source[case_id]['precision_batch_success_probability'])<1e-12
    gaps=json.loads((out/'continuum_gaps.json').read_text())
    for row in gaps:
        panel=[r for r in inputs.values() if r['cohort']==row['cohort']]
        values=[F(r['upper'])-F(r['lower']) for r in panel]
        if row['subset']=='unresolved': values=[v for v in values if v>0]
        assert len(values)==row['blocks']
        assert Counter(map(str,values))==row['histogram_exact']
        assert abs(float(sum(values)/len(values))-row['mean'])<1e-15
        for key,pct in [('min',0),('q25',.25),('median',.5),('q75',.75),('max',1)]:
            assert abs(percentile(list(map(float,values)),pct)-row[key])<1e-15
    summaries=[('primary',r) for r in json.loads((out/'threshold_summary.json').read_text())]
    summaries += [('strict',r) for r in json.loads((out/'strict_threshold_summary.json').read_text())]
    draws=json.loads((out/'bootstrap_draws.json').read_text())
    max_interval_delta=0
    for convention,row in summaries:
        cases=[r for r in inputs.values() if r['cohort']==row['cohort'] and (row['meter']=='ALL' or r['meter']==row['meter'])]
        lookup=independent if convention=='primary' else strict_independent
        outcomes=[lookup[r['id'],row['threshold']] for r in cases]
        A=[v['adaptive'] for v in outcomes];B=[v[row['baseline']] for v in outcomes]
        expected={'both_success':sum(a*b for a,b in zip(A,B)), 'adaptive_only':sum(a*(1-b) for a,b in zip(A,B)),
                  'baseline_only':sum((1-a)*b for a,b in zip(A,B)), 'neither':sum((1-a)*(1-b) for a,b in zip(A,B)),
                  'adaptive_success_count':sum(A), 'baseline_success_count':sum(B),
                  'difference_pp':100*sum(a-b for a,b in zip(A,B))/len(A)}
        for k,v in expected.items(): assert abs(float(v)-row[k])<1e-9,(row,k)
        scheme=draws[row['cohort']];days=scheme['days']
        day_sums={d:[F(0),0] for d in days}
        for r,a,b in zip(cases,A,B):day_sums[r['day']][0]+=a-b;day_sums[r['day']][1]+=1
        nums=[float(day_sums[d][0]) for d in days];dens=[day_sums[d][1] for d in days]
        estimates=[100*sum(nums[i] for i in indices)/sum(dens[i] for i in indices) for indices in scheme['indices']]
        for key,pct in [('lower_95',.025),('upper_95',.975)]:
            delta=abs(percentile(estimates,pct)-row[key]);max_interval_delta=max(max_interval_delta,delta);assert delta<1e-9
    report={'status':'PASS','saved_source_cases':1098,'saved_source_batch_widths':10980,'threshold_case_rows':len(observed),
        'strict_threshold_case_rows':len(strict_observed),'paired_summaries':len(summaries),'gap_summaries':len(gaps),'max_original_half_replay_difference':max_half_difference,
        'max_bootstrap_interval_discrepancy_pp':max_interval_delta,'comparison_tolerance':1e-9,
        'scope':'Independent implementation from saved widths and choices. All original/external source inputs independently checked by verify_source.py in its separate execution record. No fresh models fitted.',
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
