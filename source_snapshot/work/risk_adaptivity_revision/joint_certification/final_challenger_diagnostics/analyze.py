"""Exact regime and greedy-first diagnostics; exploratory fixed-fallback replay.

Geometry uses rational arithmetic on the serialized binary64-derived contrasts.
No fitted model, hidden-record-dependent policy choice, or new optimum is used.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
import numpy as np
from fallback_attribution import run as attribute_fallback

HERE = Path(__file__).resolve().parent
BATCHES = list(combinations(range(1,6),2))
HALF = F(1,2)
REPLAY_TOL = F(1,10**8)
BASELINES = ['fixed','greedy','cover_mean_fallback','cover_fixed_fallback']


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf8')


def csv_write(path, rows):
    with path.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def ranges(C,lo,hi): return [max(c[lo:hi])-min(c[lo:hi]) for c in C]


def lines(C,k,j):
    if j<k:
        a=[max(u,v) for u,v in zip(ranges(C,0,j),ranges(C,j,k))];b=ranges(C,k,6)
    else:
        a=ranges(C,0,k);b=[max(u,v) for u,v in zip(ranges(C,k,j),ranges(C,j,6))]
    return list(zip(a,b)) # a*t+b*(1-t)


def interval(rows):
    lo,hi=F(0),F(1)
    for a,b in rows:
        slope=a-b;offset=HALF-b
        if slope>0: hi=min(hi,offset/slope)
        elif slope<0: lo=max(lo,offset/slope)
        elif offset<0: return None
        if lo>hi: return None
    return lo,hi


def coverage(intervals):
    """Exact closed interval cover or a rational uncovered answer."""
    nonempty=sorted((F(v['lo']),F(v['hi'])) for v in intervals if v['lo'] is not None)
    if not nonempty or nonempty[0][0]>0: return False,F(0)
    end=F(0)
    for lo,hi in nonempty:
        if lo>end: return False,(lo+end)/2
        end=max(end,hi)
    return (True,None) if end>=1 else (False,F(1))


def exact_geometry(row):
    C=[[F(v) for v in c] for c in row['normalized_coefficients_exact']]
    assert len(C)==6 and all(len(c)==6 and min(c)==0 and max(c)==1 for c in C)
    D=[]
    for Q in BATCHES:
        cuts=(0,*Q,6)
        D.append(max(max(c[a:b])-min(c[a:b]) for c in C for a,b in zip(cuts,cuts[1:])))
    first=[]
    for k in range(1,6):
        intervals=[]
        for j in range(1,6):
            if j==k: continue
            value=interval(lines(C,k,j))
            intervals.append({'second':j,'lo':str(value[0]) if value else None,'hi':str(value[1]) if value else None})
        success,t=coverage(intervals)
        gap=None
        if not success:
            gap=min(max(a*t+b*(1-t) for a,b in lines(C,k,j)) for j in range(1,6) if j!=k)-HALF
            assert gap>0
        first.append({'first':k,'guarantees_half':success,'conditional_success_intervals':intervals,
            'uncovered_answer':str(t) if t is not None else None,'failure_margin':str(gap) if gap is not None else None})
    fixed=min(D)<=HALF;adapt=any(r['guarantees_half'] for r in first)
    assert not fixed or adapt
    greedy=first[row['greedy_first']-1]['guarantees_half']
    regime='fixed_guarantee' if fixed else 'adaptive_only_guarantee' if adapt else 'no_deterministic_adaptive_guarantee'
    matched=F(row['lower'])==F(row['upper'])==HALF
    if matched: assert adapt and not fixed
    return {'id':row['id'],'cohort':row['cohort'],'meter':row['meter'],'day':row['day'],
        'regime':regime,'D_exact':str(min(D)),'adaptive_guarantees_half_exact':adapt,
        'greedy_first':row['greedy_first'],'greedy_first_guarantees_half_exact':greedy,
        'adaptive_guarantees_but_greedy_first_does_not':adapt and not greedy,
        'matched_half':matched,'matched_half_greedy_first_failure':matched and not greedy,
        'first_query_checks':first}


def replay(row,tolerance):
    w=list(map(F,row['batch_widths']));hit=[int(v<=HALF+tolerance) for v in w]
    old=list(map(F,row['randomized_half_precision_weights']));assert len(old)==10 and sum(old)==1 and min(old)>=0
    fallback=row['policy_kind'].startswith('mean_width')
    new=[F(int(i==row['fixed_batch_index'])) for i in range(10)] if fallback else old
    values={'adaptive':F(hit[row['adaptive_batch_index']]),'fixed':F(hit[row['fixed_batch_index']]),
        'greedy':F(hit[row['greedy_batch_index']]),'cover_mean_fallback':sum(a*b for a,b in zip(old,hit)),
        'cover_fixed_fallback':sum(a*b for a,b in zip(new,hit))}
    return {k:row[k] for k in ['id','cohort','meter','day']} | {'fallback_replaced':fallback,
        'new_batch_weights_exact':list(map(str,new)),'success':{k:str(v) for k,v in values.items()}}


def paired(rows,baseline,cohort,meter,convention,draws,days):
    a=np.array([float(F(r['success']['adaptive'])) for r in rows]);b=np.array([float(F(r['success'][baseline])) for r in rows])
    numerator=np.array([sum(float(F(r['success']['adaptive'])-F(r['success'][baseline])) for r in rows if r['day']==d) for d in days])
    denominator=np.array([sum(r['day']==d for r in rows) for d in days])
    boot=100*numerator[draws].sum(axis=1)/denominator[draws].sum(axis=1)
    return {'cohort':cohort,'meter':meter,'convention':convention,'baseline':baseline,'blocks':len(rows),
        'adaptive_success_count':float(a.sum()),'baseline_success_count':float(b.sum()),
        'adaptive_percent':float(100*a.mean()),'baseline_percent':float(100*b.mean()),
        'difference_pp':float(100*(a-b).mean()),'both_success':float((a*b).sum()),
        'adaptive_only':float((a*(1-b)).sum()),'baseline_only':float(((1-a)*b).sum()),
        'neither':float(((1-a)*(1-b)).sum()),'lower_95':float(np.quantile(boot,.025,method='linear')),
        'upper_95':float(np.quantile(boot,.975,method='linear')),'counts_are_expectations':baseline.startswith('cover_')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=HERE/'frozen_inputs.json')
    p.add_argument('--output-dir',type=Path,default=HERE/'results')
    p.add_argument('--precision-plans',type=Path,help='Optional complete raw-route precision catalog to freshly reconstruct original coefficient certificates as well.')
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    source=json.loads(a.input.read_text());rows=source['cases']
    assert len(rows)==len({r['id'] for r in rows})==1098
    assert Counter(r['cohort'] for r in rows)=={'original':819,'external':279}
    catalog={r['id']:r for r in json.loads(a.precision_plans.read_text())['plans']} if a.precision_plans else {}
    proofs=[]
    for r in rows:
        if r['id'] in catalog:
            C=catalog[r['id']]['normalized_coefficients_exact']
            assert hashlib.sha256(json.dumps(C,separators=(',',':')).encode()).hexdigest()==r['coefficient_digest']
            proof=exact_geometry(r|{'normalized_coefficients_exact':C})
            if r['cohort']=='original':assert proof==r['saved_regime_certificate']
        elif 'normalized_coefficients_exact' in r:proof=exact_geometry(r)
        else:proof=r['saved_regime_certificate']
        proofs.append(proof)
    dump(a.output_dir/'regime_certificates.json',proofs)
    flat=[{k:v for k,v in r.items() if k!='first_query_checks'} for r in proofs]
    csv_write(a.output_dir/'regime_cases.csv',flat)
    regimes=[]
    for cohort in ['original','external']:
        for meter in ['ALL']+sorted({r['meter'] for r in proofs if r['cohort']==cohort}):
            z=[r for r in proofs if r['cohort']==cohort and (meter=='ALL' or r['meter']==meter)]
            regimes.append({'cohort':cohort,'meter':meter,'blocks':len(z),**dict(Counter(r['regime'] for r in z)),
                'matched_half':sum(r['matched_half'] for r in z),
                'matched_half_greedy_first_failure':sum(r['matched_half_greedy_first_failure'] for r in z),
                'adaptive_guarantees_but_greedy_first_does_not':sum(r['adaptive_guarantees_but_greedy_first_does_not'] for r in z),
                'greedy_recorded_success_among_matched_first_failures':sum(
                    F(v['batch_widths'][v['greedy_batch_index']])<=HALF for v in rows
                    if any(t['id']==v['id'] and t['matched_half_greedy_first_failure'] for t in z))})
    dump(a.output_dir/'regime_summary.json',regimes)
    csv_write(a.output_dir/'regime_summary.csv',regimes)
    outcomes=[]
    for convention,tol in [('strict',F(0)),('original_tolerance',REPLAY_TOL)]:
        outcomes += [replay(r,tol)|{'convention':convention} for r in rows]
    dump(a.output_dir/'replay_cases.json',outcomes)
    csv_write(a.output_dir/'replay_cases.csv',[{k:v for k,v in r.items() if k not in ['success','new_batch_weights_exact']}|r['success'] for r in outcomes])
    summaries=[];draw_records={}
    for cohort,stream in [('original',0),('external',1)]:
        days=sorted({r['day'] for r in rows if r['cohort']==cohort})
        gen=np.random.default_rng(np.random.SeedSequence([20261014,stream,7]))
        starts=gen.integers(0,len(days),size=(2000,(len(days)+6)//7))
        draws=((starts[:,:,None]+np.arange(7))%len(days)).reshape(2000,-1)[:,:len(days)]
        draw_records[cohort]={'seed_sequence':[20261014,stream,7],'days':days,'indices':draws.tolist()}
        for convention in ['strict','original_tolerance']:
            for meter in ['ALL']+sorted({r['meter'] for r in rows if r['cohort']==cohort}):
                z=[r for r in outcomes if r['cohort']==cohort and r['convention']==convention and (meter=='ALL' or r['meter']==meter)]
                for baseline in BASELINES:summaries.append(paired(z,baseline,cohort,meter,convention,draws,days))
    dump(a.output_dir/'paired_summary.json',summaries);csv_write(a.output_dir/'paired_summary.csv',summaries)
    dump(a.output_dir/'bootstrap_draws.json',draw_records)
    report={'status':'PASS','scope':'Retrospective diagnostic and fixed-fallback extension on the existing panels, not a locked confirmation.',
        'geometry':'Exact rational half-width classification for the stored binary64-derived contrast vectors, uncapped simplex with exact endpoint/prefix observations.',
        'coefficient_reconstruction_scope':'Both panels freshly reconstructed from the supplied source catalog.' if a.precision_plans else 'External 279 coefficients reconstructed; original 819 saved derived interval certificates replayed. Use --precision-plans with the complete pinned raw-route catalog to reconstruct original coefficient inequalities.',
        'coefficient_cases_freshly_reconstructed':1098 if a.precision_plans else 279,
        'policy':'Retain the certified deterministic or two-batch cover. On the original no-cover fallback blocks only, use the saved deterministic worst-width batch instead of the saved mean-width mixture. The replacement depends only on pre-query coefficient geometry.',
        'greedy_scope':'The code selects a one-step worst-width first query, breaking ties by the best two-query continuation. Its second step minimizes the conditional joint-width envelope. The diagnostic certifies failure of the saved first query even if the second query is chosen optimally; it is not a claim about every greedy heuristic.',
        'uncertainty':'2,000 percentile draws, linear quantiles, synchronized seven-day circular calendar blocks within each source; SeedSequence([20261014,source_id,7]), PCG64. Pointwise descriptive intervals on the three observed systems per source.',
        'new_network_calls':0,'new_forecast_fits':0,'new_general_precision_optimizations':0,
        'blocks':1098,'regime_rows':len(proofs),'replay_rows':len(outcomes),'paired_summary_rows':len(summaries),
        'inputs_sha256':sha(a.input),'source_sha256':sha(Path(__file__)),'source_manifests':source['sources'],
        'regimes':[r for r in regimes if r['meter']=='ALL'],
        'full_panel_replay':[r for r in summaries if r['meter']=='ALL']}
    dump(a.output_dir/'report.json',report)
    attribute_fallback(a.input,a.output_dir)
    print(json.dumps({'status':'PASS','regimes':report['regimes'],'replay':[r for r in report['full_panel_replay'] if r['baseline']=='cover_fixed_fallback']},indent=2))


if __name__=='__main__': main()
