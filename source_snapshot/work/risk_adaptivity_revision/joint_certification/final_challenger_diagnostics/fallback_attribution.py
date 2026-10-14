"""Exact attribution of cover/fixed-fallback versus pure-fixed replay outcomes."""
import argparse
import csv
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

HERE=Path(__file__).resolve().parent


def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def run(input_path,output):
    inputs=json.loads(input_path.read_text());rows=[]
    for r in inputs['cases']:
        kind=r['policy_kind']
        if kind.startswith('mean_width'):group='fixed_fallback'
        elif F(r['lower'])==F(r['upper'])==F(1,2):group='matched_half'
        else:
            assert F(r['lower'])==F(r['upper'])==1
            assert kind=='deterministic_precision_guarantee'
            group='deterministic_guarantee'
        for convention,tol in [('strict',F(0)),('original_tolerance',F(1,10**8))]:
            hit=[int(F(v)<=F(1,2)+tol) for v in r['batch_widths']]
            fixed=F(hit[r['fixed_batch_index']])
            cover=fixed if group=='fixed_fallback' else sum(F(w)*h for w,h in zip(r['randomized_half_precision_weights'],hit))
            if group!='matched_half':assert cover==fixed
            rows.append({k:r[k] for k in ['id','cohort','meter']}|{'group':group,'convention':convention,
                'fixed_success':str(fixed),'cover_fixed_fallback_success':str(cover),'fixed_minus_cover':str(fixed-cover),
                'fixed_worst_case_success_exact':'0' if group=='matched_half' else '1' if group=='deterministic_guarantee' else 'not_evaluated',
                'cover_worst_case_success_exact':'1/2' if group=='matched_half' else '1' if group=='deterministic_guarantee' else 'not_evaluated'})
    summaries=[]
    for source in ['original','external']:
        for meter in ['ALL']+sorted({r['meter'] for r in rows if r['cohort']==source}):
            for convention in ['strict','original_tolerance']:
                for group in ['ALL','deterministic_guarantee','matched_half','fixed_fallback']:
                    z=[r for r in rows if r['cohort']==source and (meter=='ALL' or r['meter']==meter) and r['convention']==convention and (group=='ALL' or r['group']==group)]
                    n=len(z);fixed=sum(F(r['fixed_success']) for r in z);cover=sum(F(r['cover_fixed_fallback_success']) for r in z)
                    summaries.append({'cohort':source,'meter':meter,'convention':convention,'group':group,'blocks':n,
                        'fixed_success_count_exact':str(fixed),'cover_success_count_exact':str(cover),'deficit_exact':str(fixed-cover),
                        'fixed_percent':float(100*fixed/n),'cover_percent':float(100*cover/n),
                        'both_expected':str(sum(F(r['fixed_success'])*F(r['cover_fixed_fallback_success']) for r in z)),
                        'fixed_only_expected':str(sum(F(r['fixed_success'])*(1-F(r['cover_fixed_fallback_success'])) for r in z)),
                        'cover_only_expected':str(sum((1-F(r['fixed_success']))*F(r['cover_fixed_fallback_success']) for r in z)),
                        'neither_expected':str(sum((1-F(r['fixed_success']))*(1-F(r['cover_fixed_fallback_success'])) for r in z)),
                        'blocks_with_different_success_probability':sum(F(r['fixed_minus_cover'])!=0 for r in z)})
    output.mkdir(parents=True,exist_ok=True)
    write_csv(output/'fallback_attribution_cases.csv',rows)
    write_csv(output/'fallback_attribution_groups.csv',summaries)
    report={'status':'PASS','scope':'Exact retrospective attribution from the unchanged stored replay widths and policy weights; no new policy fitting or selection.',
        'proof_of_zero_fixed_worst_case_success':'On a matched-half instance, optimal randomized-batch worst-case precision success is exactly 1/2. A fixed deterministic batch has worst-case success either 0 or 1. If it were 1, the randomized optimum would be at least 1, a contradiction. Hence every fixed batch, including the recorded worst-width choice, has worst-case precision success 0 on that instance. This statement concerns all feasible completions, not the empirical fraction of recorded successes.',
        'all_nonmatched_block_differences_zero':True,'case_rows':len(rows),'summary_rows':len(summaries),
        'input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_summaries':[r for r in summaries if r['meter']=='ALL']}
    (output/'fallback_attribution.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,default=HERE/'frozen_inputs.json');p.add_argument('--output-dir',type=Path,default=HERE/'results');a=p.parse_args()
    r=run(a.input,a.output_dir);print(json.dumps(r,indent=2))
