"""Predeclared household-macro curves and integer stopping budgets; all outcomes retained."""
from pathlib import Path
from datetime import datetime,timezone
import argparse, hashlib, json
import numpy as np
import pandas as pd

POLICIES=['exact','greedy','hara','uniform','randomized']

def b80(values):
    found=values[values.coverage>=.8]
    return int(found.budget.min()) if len(found) else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-dir',type=Path,required=True);args=ap.parse_args()
    out=args.run_dir.resolve();d=pd.read_csv(out/'cases.csv',dtype={'household_id':str})
    d['initially_unresolved']=~d.initial_status.isin(['a','b'])
    rows=[];house_rows=[];stats=[];pair_rows=[];month_rows=[]
    for subgroup,df in [('all',d),('learned',d[d.learned_pair])]:
        for (regime,policy),g in df.groupby(['regime','policy'],sort=True):
            for population,f in [('all',g),('initially_unresolved',g[g.initially_unresolved])]:
                households=f.household_id.nunique()
                for budget in range(7):
                    eligible=f.certification_cost.notna()&(f.certification_cost<=budget)
                    byhouse=f.assign(certified=eligible).groupby('household_id').certified.mean()
                    rows.append({'subgroup':subgroup,'regime':regime,'policy':policy,'population':population,'budget':budget,
                        'cases':len(f),'households':households,'excluded_zero_denominator_households':g.household_id.nunique()-households,
                        'coverage':float(byhouse.mean()) if len(byhouse) else None,'pooled_coverage':float(eligible.mean()) if len(f) else None})
                    if subgroup=='all':
                        for household,v in byhouse.items():house_rows.append({'household_id':household,'regime':regime,'policy':policy,'population':population,'budget':budget,'coverage':float(v),'cases':int((f.household_id==household).sum())})
                housecost=f.groupby('household_id').paid_requests.mean()
                stats.append({'subgroup':subgroup,'regime':regime,'policy':policy,'population':population,'cases':len(f),
                    'household_macro_mean_requests':float(housecost.mean()) if len(housecost) else None,
                    'pooled_mean_requests':float(f.paid_requests.mean()) if len(f) else None,
                    'pooled_median_requests':float(f.paid_requests.median()) if len(f) else None,
                    'unresolved_at_stop':int((f.final_status=='unresolved').sum()),
                    'unresolved_at_cap':int(((f.final_status=='unresolved')&(f.paid_requests>=6)).sum()),
                    'numerical_tie_stops':int((f.final_status=='numerical_tie').sum()),
                    'exact_reference_ties':int(f.exact_reference_tie.sum()),
                    'near_reference_ties':int(f.near_reference_tie.sum()),
                    'planning_seconds_total':float(f.planning_seconds.sum()),
                    'planning_seconds_mean_case':float(f.planning_seconds.mean()) if len(f) else None,
                    'planning_seconds_p95_case':float(f.planning_seconds.quantile(.95)) if len(f) else None})
    early=d[d.regime=='early']
    for column,destination in [('pair',pair_rows),('month',month_rows)]:
        for (level,policy),g in early.groupby([column,'policy']):
            f=g[g.initially_unresolved]
            for budget in range(7):
                x=f.assign(certified=f.certification_cost.notna()&(f.certification_cost<=budget))
                destination.append({column:level,'policy':policy,'budget':budget,'cases':len(f),
                    'coverage':float(x.groupby('household_id').certified.mean().mean()) if len(f) else None})
    curves=pd.DataFrame(rows);hc=pd.DataFrame(house_rows);pc=pd.DataFrame(pair_rows)
    curves.to_csv(out/'coverage_curves.csv',index=False,float_format='%.17g')
    hc.to_csv(out/'household_curves.csv',index=False,float_format='%.17g')
    pc.to_csv(out/'pair_curves.csv',index=False,float_format='%.17g')
    pd.DataFrame(month_rows).to_csv(out/'month_curves.csv',index=False,float_format='%.17g')
    pd.DataFrame(stats).to_csv(out/'cost_summary.csv',index=False,float_format='%.17g')
    budgets={}
    for subgroup in ['all','learned']:
        primary=curves[(curves.subgroup==subgroup)&(curves.regime=='early')&(curves.population=='initially_unresolved')]
        budgets[subgroup]={p:b80(primary[primary.policy==p]) for p in POLICIES}
    ex=budgets['all']['exact'];others=[budgets['all'][p] for p in ['greedy','hara'] if budgets['all'][p] is not None]
    strongest=min(others) if others else None
    saving=(strongest-ex)/strongest if ex is not None and strongest not in [None,0] else None
    final=curves[(curves.subgroup=='all')&(curves.regime=='early')&(curves.population=='initially_unresolved')&(curves.budget==6)].set_index('policy').coverage
    cap_ok=float(final['exact'])+1e-12>=max(float(final[p]) for p in ['greedy','hara'])
    house_budgets=[]
    for house,g in hc[(hc.regime=='early')&(hc.population=='initially_unresolved')].groupby('household_id'):
        b={p:b80(g[g.policy==p]) for p in POLICIES};vals=[b[p] for p in ['greedy','hara'] if b[p] is not None]
        best=min(vals) if vals else None
        house_budgets.append({'household_id':house,**b,'strongest_baseline':best,'exact_strictly_better':b['exact'] is not None and best is not None and b['exact']<best})
    pair_budgets=[]
    for pair,g in pc.groupby('pair'):
        b={p:b80(g[g.policy==p]) for p in POLICIES};vals=[b[p] for p in ['greedy','hara'] if b[p] is not None]
        best=min(vals) if vals else None
        pair_budgets.append({'pair':pair,**b,'strongest_baseline':best,'exact_strictly_better':b['exact'] is not None and best is not None and b['exact']<best})
    summary={'status':'passed','created_utc':datetime.now(timezone.utc).isoformat(),
        'period':json.loads((out/'run_result.json').read_text())['period'],'B80':budgets,
        'strongest_greedy_hara_B80':strongest,'exact_relative_B80_reduction':saving,
        'exact_no_lower_cap_coverage':bool(cap_ok),'fifteen_percent_budget_criterion_met':bool(saving is not None and saving>=.15 and cap_ok),
        'uniform_has_lower_B80_than_exact':bool(budgets['all']['uniform'] is not None and ex is not None and budgets['all']['uniform']<ex),
        'conditional_denominator_rule':'initially_unresolved is regime-specific; the primary comparison uses early initially uncertified cases. Late-after-copy conditional coverage is not the same population.',
        'household_B80':house_budgets,'pair_B80':pair_budgets,
        'households_exact_strictly_better':sum(x['exact_strictly_better'] for x in house_budgets),
        'pairs_exact_strictly_better':sum(x['exact_strictly_better'] for x in pair_budgets),
        'learned_pairs_exact_strictly_better':sum(x['exact_strictly_better'] and 'daily' not in x['pair'] for x in pair_budgets),
        'counts':{'case_rows':len(d),'base_cases':int(d.case_id.nunique()),'households':int(d.household_id.nunique()),'household_days':len(d[['household_id','day_utc']].drop_duplicates()),
                  'initial_unresolved_base_cases':int(d[(d.regime=='early')&(d.policy=='exact')].initially_unresolved.sum())},
        'claim_scope':'B80 is an integer per-pair executable stopping budget; three seeded paths, household-macro coverage. No monetary/latency measurement or global stopping-optimality claim.',
        'source_sha256':hashlib.sha256((out/'cases.csv').read_bytes()).hexdigest(),
        'summary_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'headline_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['household_B80','pair_B80']},indent=2))

if __name__=='__main__':main()
