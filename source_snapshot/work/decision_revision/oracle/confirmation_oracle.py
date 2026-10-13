"""Post-run hindsight certificate lower bounds; never an acquisition input.

Run ONLY after the frozen new-consumer policy run has completed. Exhaustive
subsets use hidden answers and are a diagnostic lower bound for every policy.
"""
from pathlib import Path
from itertools import combinations
from datetime import datetime, timezone
import argparse
import json
import math
import time
import numpy as np
import pandas as pd
from hindsight_diagnostic import bounds, corner_check, sha, sign


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--reference-period',default='test')
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();started=time.perf_counter()
    completed=json.loads((args.run_dir/'run_result.json').read_text())
    assert completed['status']=='passed', 'Oracle must follow completed acquisition'
    args.output_dir.mkdir(exist_ok=False)
    source=args.run_dir/'source_cases.jsonl'
    inputs={str(f.resolve()):sha(f) for f in [source,args.reference,args.run_dir/'cases.csv',args.run_dir/'run_result.json',Path(__file__),Path(__file__).with_name('hindsight_diagnostic.py')]}
    (args.output_dir/'input_manifest.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'inputs':inputs},indent=2)+'\n')
    ref=pd.read_csv(args.reference,dtype={'household_id':str})
    ref=ref[ref.period==args.reference_period].copy();ref['day']=ref.timestamp_utc.str[:10]
    reference={(h,d):g.sort_values('timestamp_utc').energy_kwh.to_numpy(float) for (h,d),g in ref.groupby(['household_id','day']) if len(g)==24}
    rows=[];subsets=vertices=0;max_error=0.
    with source.open() as stream:
        for line in stream:
            case=json.loads(line)
            a,b,observed,totals=(np.asarray(case[k],float) for k in ['a','b','initial_observed','totals'])
            truth=reference[(case['household_id'],case['day_utc'][:10])]
            true_difference=float(np.mean((a-truth)**2-(b-truth)**2))
            initial=bounds(a,b,observed,totals)
            known=np.isfinite(observed)
            assert np.max(np.abs(observed[known]-truth[known]),initial=0.)<=1e-9
            missing=list(np.flatnonzero(~known))
            cost=witness=verdict=None;examined=0
            for size in range(len(missing)+1):
                for query in combinations(missing,size):
                    visible=observed.copy()
                    if query:visible[list(query)]=truth[list(query)]
                    endpoints=bounds(a,b,visible,totals);examined+=1
                    verdict=sign(*endpoints)
                    if verdict:
                        assert (verdict=='a' and true_difference<0) or (verdict=='b' and true_difference>0)
                        cost=size;witness=list(map(int,query))
                        n,error=corner_check(a,b,visible,totals,endpoints)
                        vertices+=n;max_error=max(max_error,error)
                        break
                if cost is not None:break
            if cost is None:
                assert sign(*bounds(a,b,truth,totals)) is None, 'Missed finite full-record certificate'
            subsets+=examined
            rows.append({k:case[k] for k in ['case_id','household_id','day_utc','pair','learned_pair']}|
                        {'initially_uncertified':sign(*initial) is None,'oracle_minimum_requests':cost,
                         'oracle_witness':json.dumps(witness),'oracle_sign':verdict,'subsets_tested':examined,
                         'full_reference_difference':true_difference})
    oracle=pd.DataFrame(rows)
    oracle.to_csv(args.output_dir/'cases.csv',index=False,float_format='%.17g')
    policies=pd.read_csv(args.run_dir/'cases.csv')
    joined=policies.merge(oracle[['case_id','oracle_minimum_requests','initially_uncertified']],on='case_id',validate='many_to_one')
    assert len(joined)==len(policies) and set(policies.case_id)==set(oracle.case_id)
    certified=joined.certification_cost.notna()
    assert joined.loc[certified,'oracle_minimum_requests'].notna().all()
    assert (joined.loc[certified,'oracle_minimum_requests']<=joined.loc[certified,'certification_cost']).all()
    summaries=[];households=[];curve_rows=[]
    for population,d in [('all',joined),('initially_uncertified',joined[joined.initially_uncertified]),
                         ('learned_initially_uncertified',joined[joined.initially_uncertified & joined.learned_pair])]:
        for policy,group in d.groupby('policy'):
            finite=group[group.oracle_minimum_requests.notna()]
            means=finite.groupby('household_id')[['paid_requests','oracle_minimum_requests']].mean()
            x=float(means.paid_requests.mean());y=float(means.oracle_minimum_requests.mean())
            ratio=x/y if y>0 else None
            samples=None;interval=None
            if y>0:
                matrix=means.to_numpy()
                draw=np.random.default_rng(8241).integers(0,len(matrix),(2000,len(matrix)))
                replicate=matrix[draw].mean(axis=1)
                assert np.all(replicate[:,1]>0)
                samples=replicate[:,0]/replicate[:,1]
                interval=np.quantile(samples,[.025,.975]).tolist()
            summaries.append({'population':population,'policy':policy,'all_cases':len(group),
                'strictly_certifiable_cases':len(finite),'no_finite_strict_oracle_cases':int(group.oracle_minimum_requests.isna().sum()),
                'households':len(means),'policy_macro_mean_requests_on_certifiable_cases':x,
                'oracle_macro_mean_requests_on_same_cases':y,'ratio_of_macro_means':ratio,
                'descriptive_household_bootstrap_ratio_95':interval,
                'ratio_at_most_1_10':bool(ratio is not None and ratio<=1.10),
                'all_case_strict_coverage_at_cap':float(group.assign(cert=group.certification_cost.notna()).groupby('household_id').cert.mean().mean()),
                'unresolved_final_cases':int((group.final_status=='unresolved').sum()),
                'numerical_tie_final_cases':int((group.final_status=='numerical_tie').sum())})
            for house,row in means.iterrows():households.append({'population':population,'policy':policy,'household_id':house,
                'policy_mean_requests':row.paid_requests,'oracle_mean_requests':row.oracle_minimum_requests})
        unique=d.drop_duplicates('case_id')
        for budget in range(7):
            coverage=unique.assign(cert=unique.oracle_minimum_requests.notna()&(unique.oracle_minimum_requests<=budget)).groupby('household_id').cert.mean().mean()
            curve_rows.append({'population':population,'budget':budget,'oracle_coverage':float(coverage)})
    pd.DataFrame(households).to_csv(args.output_dir/'household_means.csv',index=False,float_format='%.17g')
    pd.DataFrame(curve_rows).to_csv(args.output_dir/'coverage_curves.csv',index=False,float_format='%.17g')
    for file,expected in inputs.items():assert sha(file)==expected
    report={'status':'passed','scope':'Hindsight enumeration after completed acquisition; hidden values never supplied to policies. Every strictly certifying trace costs at least its per-case minimum. Report every policy; this is not new-method superiority.',
        'cases':len(oracle),'subsets_checked':subsets,'squared_loss_vertices_checked':vertices,
        'maximum_vertex_endpoint_discrepancy':max_error,'summaries':summaries,'seconds':time.perf_counter()-started,
        'tie_rule':'No finite strict certificate is reported as missing oracle cost and retained in all-case coverage/counts. Ratios use exactly matched certifiable cases per household; zero denominator gives no ratio.',
        'weighting':'Same household weights for policy and oracle; ratio of macro means, not mean of case ratios.',
        'bootstrap':'2000 paired household resamples, seed8241; descriptive deterministic-panel stability, not a population confidence guarantee.',
        'inputs':inputs,'outputs':{f.name:sha(f) for f in args.output_dir.iterdir() if f.is_file()}}
    (args.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['inputs','outputs']},indent=2))


if __name__=='__main__':main()
