"""Recompute paired cells and percentile limits from exported day draws."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def quantile(sorted_values,p):
    x=(len(sorted_values)-1)*p;i=int(x);f=x-i
    return sorted_values[i]*(1-f)+sorted_values[min(i+1,len(sorted_values)-1)]*f
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',type=Path,default=HERE/'empirical_paired_external_results')
    p.add_argument('--output',type=Path,default=HERE/'empirical_paired_independent.json');a=p.parse_args()
    rows=json.loads((a.results_dir/'case_outcomes.json').read_text());draws=json.loads((a.results_dir/'bootstrap_draws.json').read_text())
    reports=json.loads((a.results_dir/'paired_statistics.json').read_text());maximum=0.
    for cohort,saved in draws.items():
        n=len(saved['days']);starts=np.random.default_rng(np.random.SeedSequence(saved['seed_sequence'])).integers(0,n,size=(2000,(n+6)//7))
        expected=((starts[:,:,None]+np.arange(7))%n).reshape(2000,-1)[:,:n].tolist();assert expected==saved['indices']
        day=np.random.default_rng(np.random.SeedSequence(saved['day_seed_sequence'])).integers(0,n,size=(2000,n)).tolist();assert day==saved['day_indices']
    for r in reports:
        subset=[v for v in rows if v['cohort']==r['cohort'] and v['regime']==r['regime'] and (r['meter']=='ALL' or v['meter']==r['meter'])]
        valid=[v for v in subset if v['valid']];base=r['baseline'];cells=[0.,0.,0.,0.]
        for v in valid:
            x=float(v['adaptive']);y=float(v['baselines'][base]);cells=[z+t for z,t in zip(cells,[x*y,x*(1-y),(1-x)*y,(1-x)*(1-y)])]
        for key,x in zip(['both_success','adaptive_only','baseline_only','neither_success'],cells):maximum=max(maximum,abs(x-r[key]))
        assert len(subset)==r['all_rows'] and len(valid)==r['compatible_rows']
        saved=draws[r['cohort']];days=saved['days'];numer=[];denom=[]
        for day in days:
            vs=[v for v in valid if v['day']==day];numer.append(sum(float(v['adaptive'])-float(v['baselines'][base]) for v in vs));denom.append(len(vs))
        estimates=sorted(100*sum(numer[i] for i in draw)/sum(denom[i] for i in draw) for draw in saved['indices'])
        day_estimates=sorted(100*sum(numer[i] for i in draw)/sum(denom[i] for i in draw) for draw in saved['day_indices'])
        for key,x in [('difference_percentage_points',100*sum(numer)/sum(denom)),('percentile_95_lower',quantile(estimates,.025)),('percentile_95_upper',quantile(estimates,.975))]:maximum=max(maximum,abs(x-r[key]))
        for key,x in [('day_percentile_95_lower',quantile(day_estimates,.025)),('day_percentile_95_upper',quantile(day_estimates,.975))]:maximum=max(maximum,abs(x-r[key]))
    assert maximum<1e-8
    out={'status':'PASS','paired_comparisons':len(reports),'draws_per_cohort':2000,'max_discrepancy':maximum,
         'scope':'Independent scalar sums and sorted-order percentile reconstruction; verifies seeded draw arrays and all paired cells, not validity of unmodeled cross-day independence assumptions'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
