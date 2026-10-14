"""Standalone stdlib checker for regime certificates and paired fallback replay.

The checker independently builds each batch's segment-width vectors, takes
prefix/suffix maxima, and verifies all interval endpoints and uncovered answers.
It also reconstructs the replay and descriptive summaries from the frozen input.
"""
import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path

HERE=Path(__file__).resolve().parent
BATCHES=list(combinations(range(1,6),2))
H=F(1,2)


def vectors(C,Q):
    out=[]
    boundaries=[0,*Q,6]
    for c in C:
        v=[]
        for start,end in zip(boundaries,boundaries[1:]):
            v.extend([max(c[start:end])-min(c[start:end])]*(end-start))
        out.append(v)
    return out


def envelope_value(parts,t):
    return min(max(a*t+b*(1-t) for a,b in action) for action in parts)


def full_intersection_value(parts):
    lines=[(a-b,b) for action in parts for a,b in action]
    points={F(0),F(1)}
    for (m,b),(n,d) in combinations(lines,2):
        if m!=n:
            t=(d-b)/(m-n)
            if 0<=t<=1:points.add(t)
    return max(envelope_value(parts,t) for t in points)


def linear_quantile(values,q):
    values=sorted(values);pos=(len(values)-1)*q;i=int(pos);fraction=pos-i
    return values[i]+fraction*(values[min(i+1,len(values)-1)]-values[i])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=HERE/'frozen_inputs.json')
    p.add_argument('--results',type=Path,default=HERE/'results')
    p.add_argument('--output',type=Path,default=HERE/'independent_check.json')
    p.add_argument('--precision-plans',type=Path,help='Complete catalog from the pinned raw route for original coefficient verification.')
    a=p.parse_args();inputs=json.loads(a.input.read_text());rows={r['id']:r for r in inputs['cases']}
    if a.precision_plans:
        catalog={r['id']:r for r in json.loads(a.precision_plans.read_text())['plans']}
        assert set(rows)==set(catalog)
        for key,r in rows.items():
            C=catalog[key]['normalized_coefficients_exact']
            assert hashlib.sha256(json.dumps(C,separators=(',',':')).encode()).hexdigest()==r['coefficient_digest']
            r['normalized_coefficients_exact']=C
    certs=json.loads((a.results/'regime_certificates.json').read_text())
    assert len(rows)==len(certs)==1098
    representatives={min(r['id'] for r in rows.values() if r['meter']==m) for m in {r['meter'] for r in rows.values()}}
    observed=[];intersection_checks=[];max_float_discrepancy=0
    for q in certs:
        r=rows[q['id']];C=[[F(v) for v in c] for c in r['normalized_coefficients_exact']] if 'normalized_coefficients_exact' in r else None
        if C is None:
            assert q==r['saved_regime_certificate']
            V=None;D=F(q['D_exact'])
        else:
            V={Q:vectors(C,Q) for Q in BATCHES}
            D=min(max(max(c) for c in v) for v in V.values())
        assert str(D)==q['D_exact']
        feasible_first=[]
        for k in range(1,6):
            parts=[];intervals=[]
            for j in range(1,6):
                if j==k:continue
                if C is None:
                    z=q['first_query_checks'][k-1]['conditional_success_intervals'][len(parts)]
                    assert z['second']==j
                    parts.append(None)
                    if z['lo'] is not None:
                        lo,hi=F(z['lo']),F(z['hi']);assert 0<=lo<=hi<=1
                        intervals.append((lo,hi))
                    else:assert z['hi'] is None
                    continue
                v=V[tuple(sorted((k,j)))]
                lines=[(max(c[:k]),max(c[k:])) for c in v];parts.append(lines)
                lows=[F(0)];highs=[F(1)];impossible=False
                for x,y in lines:
                    if x==y:
                        if x>H:impossible=True
                    elif x>y:highs.append((H-y)/(x-y))
                    else:lows.append((H-y)/(x-y))
                lo=max(lows);hi=min(highs)
                value=None if impossible or lo>hi else (lo,hi)
                z=q['first_query_checks'][k-1]['conditional_success_intervals'][len(parts)-1]
                assert z['second']==j
                assert (z['lo'],z['hi'])==((str(lo),str(hi)) if value else (None,None))
                if value:intervals.append(value)
            points=sorted({F(0),F(1)}|{v for pair in intervals for v in pair})
            probes=points+[(lo+hi)/2 for lo,hi in zip(points,points[1:])]
            covered=all(any(lo<=t<=hi for lo,hi in intervals) for t in probes)
            z=q['first_query_checks'][k-1];assert covered==z['guarantees_half']
            feasible_first.append(covered)
            if not covered:
                t=F(z['uncovered_answer']);assert 0<=t<=1
                assert not any(lo<=t<=hi for lo,hi in intervals)
                if C is not None:
                    margin=envelope_value(parts,t)-H
                    assert margin>0 and str(margin)==z['failure_margin']
                else:assert F(z['failure_margin'])>0
            else:assert z['uncovered_answer'] is None and z['failure_margin'] is None
            if C is not None and r['id'] in representatives:
                value=full_intersection_value(parts)
                discrepancy=abs(float(value)-r['saved_first_guarantees_binary64'][k-1])
                assert discrepancy<1e-12
                max_float_discrepancy=max(max_float_discrepancy,discrepancy)
                assert (value<=H)==covered
                intersection_checks.append({'id':r['id'],'first':k,'max_min_exact':str(value),'saved_float_discrepancy':discrepancy})
        adaptive=any(feasible_first);greedy=feasible_first[r['greedy_first']-1]
        assert feasible_first[r['adaptive_first']-1]==adaptive
        if C is not None:
            saved_fixed_width=max(max(c) for c in V[BATCHES[r['fixed_batch_index']]])
            assert (saved_fixed_width<=H)==(D<=H)
        regime='fixed_guarantee' if D<=H else 'adaptive_only_guarantee' if adaptive else 'no_deterministic_adaptive_guarantee'
        assert regime==q['regime'] and adaptive==q['adaptive_guarantees_half_exact']
        assert greedy==q['greedy_first_guarantees_half_exact']
        assert q['adaptive_guarantees_but_greedy_first_does_not']==(adaptive and not greedy)
        matched=F(r['lower'])==F(r['upper'])==H
        assert matched==q['matched_half'] and q['matched_half_greedy_first_failure']==(matched and not greedy)
        observed.append(q)
    summaries=json.loads((a.results/'regime_summary.json').read_text())
    for s in summaries:
        z=[r for r in observed if r['cohort']==s['cohort'] and (s['meter']=='ALL' or r['meter']==s['meter'])]
        assert len(z)==s['blocks']
        for name in ['fixed_guarantee','adaptive_only_guarantee','no_deterministic_adaptive_guarantee']:
            assert sum(r['regime']==name for r in z)==s.get(name,0)
        for name in ['matched_half','matched_half_greedy_first_failure','adaptive_guarantees_but_greedy_first_does_not']:
            assert sum(r[name] for r in z)==s[name]
        ids={r['id'] for r in z if r['matched_half_greedy_first_failure']}
        assert sum(F(rows[key]['batch_widths'][rows[key]['greedy_batch_index']])<=H for key in ids)==s['greedy_recorded_success_among_matched_first_failures']
    replay=json.loads((a.results/'replay_cases.json').read_text())
    assert len(replay)==2196
    for z in replay:
        r=rows[z['id']];threshold=H+(F(1,10**8) if z['convention']=='original_tolerance' else 0)
        hit=[int(F(v)<=threshold) for v in r['batch_widths']]
        old=[F(v) for v in r['randomized_half_precision_weights']]
        fallback=r['policy_kind'].startswith('mean_width')
        new=[F(i==r['fixed_batch_index']) for i in range(10)] if fallback else old
        assert sum(new)==1 and min(new)>=0 and z['new_batch_weights_exact']==list(map(str,new))
        assert fallback==z['fallback_replaced']
        expected={'adaptive':F(hit[r['adaptive_batch_index']]),'fixed':F(hit[r['fixed_batch_index']]),
            'greedy':F(hit[r['greedy_batch_index']]),'cover_mean_fallback':sum(p*v for p,v in zip(old,hit)),
            'cover_fixed_fallback':sum(p*v for p,v in zip(new,hit))}
        assert z['success']=={k:str(v) for k,v in expected.items()}
    paired=json.loads((a.results/'paired_summary.json').read_text())
    attribution=json.loads((a.results/'fallback_attribution.json').read_text())
    attribution_counts=[]
    for source in ['original','external']:
        for convention in ['strict','original_tolerance']:
            selected=[r for r in replay if r['cohort']==source and r['convention']==convention]
            total_difference=F(0);matched_fixed=F(0);matched_cover=F(0);nmatched=0
            for z in selected:
                r=rows[z['id']];matched=F(r['lower'])==F(r['upper'])==H
                fixed=F(z['success']['fixed']);cover=F(z['success']['cover_fixed_fallback'])
                total_difference+=fixed-cover
                if matched:nmatched+=1;matched_fixed+=fixed;matched_cover+=cover
                else:assert fixed==cover
            assert total_difference==matched_fixed-matched_cover
            expected_counts=(165,F(155),F(108),F(47)) if source=='original' else (57,F(51),F(37),F(14))
            assert (nmatched,matched_fixed,matched_cover,total_difference)==expected_counts
            summary=next(s for s in attribution['source_summaries'] if s['cohort']==source and s['convention']==convention and s['group']=='matched_half')
            assert summary['blocks']==nmatched and F(summary['fixed_success_count_exact'])==matched_fixed and F(summary['cover_success_count_exact'])==matched_cover and F(summary['deficit_exact'])==total_difference
            attribution_counts.append({'cohort':source,'convention':convention,'matched_blocks':nmatched,'fixed_successes':str(matched_fixed),'cover_expected_successes':str(matched_cover),'entire_panel_deficit':str(total_difference)})
    boot=json.loads((a.results/'bootstrap_draws.json').read_text());max_summary_discrepancy=0
    for s in paired:
        z=[r for r in replay if r['cohort']==s['cohort'] and r['convention']==s['convention'] and (s['meter']=='ALL' or r['meter']==s['meter'])]
        n=len(z);a_values=[F(r['success']['adaptive']) for r in z];b_values=[F(r['success'][s['baseline']]) for r in z]
        expected={'adaptive_success_count':float(sum(a_values)),'baseline_success_count':float(sum(b_values)),
            'adaptive_percent':float(100*sum(a_values)/n),'baseline_percent':float(100*sum(b_values)/n),
            'difference_pp':float(100*(sum(a_values)-sum(b_values))/n),
            'both_success':float(sum(x*y for x,y in zip(a_values,b_values))),
            'adaptive_only':float(sum(x*(1-y) for x,y in zip(a_values,b_values))),
            'baseline_only':float(sum((1-x)*y for x,y in zip(a_values,b_values))),
            'neither':float(sum((1-x)*(1-y) for x,y in zip(a_values,b_values)))}
        days=boot[s['cohort']]['days'];indices=boot[s['cohort']]['indices']
        day_diff=[sum(float(F(r['success']['adaptive'])-F(r['success'][s['baseline']])) for r in z if r['day']==d) for d in days]
        day_n=[sum(r['day']==d for r in z) for d in days]
        estimates=[100*sum(day_diff[i] for i in draw)/sum(day_n[i] for i in draw) for draw in indices]
        expected['lower_95']=linear_quantile(estimates,.025);expected['upper_95']=linear_quantile(estimates,.975)
        for name,value in expected.items():
            delta=abs(s[name]-value);max_summary_discrepancy=max(max_summary_discrepancy,delta)
            assert delta<1e-9,(name,s[name],value)
    report={'status':'PASS','scope':'Independent same-study stdlib reconstruction, not external validation.',
        'exact_regime_cases':len(certs),'exact_conditional_intervals':1098*5*4,
        'coefficient_derived_cases':sum('normalized_coefficients_exact' in r for r in rows.values()),
        'original_scope':'Original coefficient inequalities freshly checked against the supplied raw-route precision catalog.' if a.precision_plans else 'Original saved interval endpoints, coverage and outcomes checked; original coefficient derivation requires the separate --precision-plans route.',
        'representative_all_intersection_checks':intersection_checks,
        'max_saved_guarantee_discrepancy':max_float_discrepancy,
        'replay_cases':len(replay),'paired_summaries':len(paired),
        'max_summary_discrepancy':max_summary_discrepancy,
        'fallback_deficit_attribution':attribution_counts,
        'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='representative_all_intersection_checks'},indent=2))


if __name__=='__main__':main()
