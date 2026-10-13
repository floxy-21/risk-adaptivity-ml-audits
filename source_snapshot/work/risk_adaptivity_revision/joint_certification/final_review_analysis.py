"""Additional descriptive checks requested in final review; no policy refitting.

Seven days remains the primary temporal block. Fourteen days and deleting one
system are sensitivity analyses of the same fixed panels, not new replications.
"""
import argparse, csv, hashlib, json
from collections import Counter
from fractions import Fraction
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, DRAWS = 20261013, 2000

def read(p): return json.loads(p.read_text(encoding='utf8'))
def dump(p, x): p.write_text(json.dumps(x, indent=2, allow_nan=False)+'\n', encoding='utf8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def cells(rows, base):
    valid=[r for r in rows if r['valid']]
    a=np.asarray([r['adaptive'] for r in valid], dtype=float)
    b=np.asarray([r['baselines'][base] for r in valid], dtype=float)
    return dict(all_rows=len(rows), compatible_rows=len(valid), incompatible_rows=len(rows)-len(valid),
                both=float((a*b).sum()), adaptive_only=float((a*(1-b)).sum()),
                baseline_only=float(((1-a)*b).sum()), neither=float(((1-a)*(1-b)).sum()),
                adaptive_success=float(a.sum()), baseline_success=float(b.sum()),
                difference_pp=float(100*(a-b).mean()))

def interval(rows, base, days, draws):
    n=np.zeros(len(days)); d=np.zeros(len(days)); index={day:i for i,day in enumerate(days)}
    for row in rows:
        if row['valid']:
            i=index[row['day']]; n[i]+=float(row['adaptive'])-float(row['baselines'][base]); d[i]+=1
    denomin=d[draws].sum(axis=1)
    assert (denomin>0).all()
    estimates=100*n[draws].sum(axis=1)/denomin
    return [float(x) for x in np.quantile(estimates,[.025,.975],method='linear')]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--outcomes',type=Path,default=HERE/'empirical_paired_all_results/case_outcomes.json')
    p.add_argument('--precision-cases',type=Path,default=HERE/'empirical_precision_all_results/cases.json')
    p.add_argument('--precision-plans',type=Path,help='Optional original full coefficient-only plans; only checks correspondence, not needed for public replay.')
    p.add_argument('--output-dir',type=Path,default=HERE/'final_review_results')
    args=p.parse_args(); rows=read(args.outcomes); precision=read(args.precision_cases)
    assert len([r for r in rows if r['regime']=='exact'])==1098 and len(precision)==1098
    assert len({r['id'] for r in precision})==1098
    if args.precision_plans:
        plans=read(args.precision_plans)['plans']; assert len(plans)==1098
        byid={r['id']:r for r in precision}
        for plan in plans:
            r=byid[plan['id']]
            for field in ['cohort','meter','policy_kind','precision_lower_exact','precision_upper_exact','continuum_optimum_identified']:
                assert plan[field]==r[field], (plan['id'],field)
    out=args.output_dir; out.mkdir(parents=True,exist_ok=True)
    draws_saved={}; summaries=[]; systems=[]
    for cohort,stream in [('original',0),('external',1)]:
        panel=[r for r in rows if r['cohort']==cohort]; days=sorted({r['day'] for r in panel}); draws={}
        draws_saved[cohort]={'days':days,'lengths':{}}
        for length in [7,14]:
            rng=np.random.default_rng(np.random.SeedSequence([SEED,stream,length]))
            starts=rng.integers(0,len(days),size=(DRAWS,(len(days)+length-1)//length))
            indices=((starts[:,:,None]+np.arange(length))%len(days)).reshape(DRAWS,-1)[:,:len(days)]
            draws[length]=indices
            draws_saved[cohort]['lengths'][str(length)]={'seed_sequence':[SEED,stream,length],'starts':starts.tolist(),'indices':indices.tolist()}
        for regime in sorted({r['regime'] for r in panel}):
            rr=[r for r in panel if r['regime']==regime]; meters=sorted({r['meter'] for r in rr}); assert len(meters)==3
            for omitted in [None]+meters:
                selected=[r for r in rr if r['meter']!=omitted]
                for base in ['fixed','greedy','randomized_mean','randomized_precision']:
                    if not all(base in r['baselines'] for r in selected if r['valid']): continue
                    summaries.append(dict(cohort=cohort,regime=regime,omitted_system=omitted,baseline=base,
                        **cells(selected,base),primary_7day=interval(selected,base,days,draws[7]),
                        sensitivity_14day=interval(selected,base,days,draws[14])))
            for meter in meters:
                selected=[r for r in rr if r['meter']==meter]
                for base in ['fixed','greedy']:
                    systems.append(dict(cohort=cohort,regime=regime,meter=meter,baseline=base,**cells(selected,base)))
    catalog=[]; totals={}
    for cohort in ['original','external']:
        cases=[r for r in precision if r['cohort']==cohort]; counts=Counter(r['policy_kind'] for r in cases)
        for r in cases:
            lo,hi=Fraction(r['precision_lower_exact']),Fraction(r['precision_upper_exact'])
            assert 0<=lo<=hi<=1 and (lo==hi)==r['continuum_optimum_identified']
            catalog.append({k:r[k] for k in ['id','cohort','meter','policy_kind','precision_lower_exact','precision_upper_exact','continuum_optimum_identified']})
        totals[cohort]={'cases':len(cases),'policy_counts':dict(counts),
            'closed_gap':sum(Fraction(r['precision_lower_exact'])==Fraction(r['precision_upper_exact']) for r in cases),
            'open_gap':sum(Fraction(r['precision_lower_exact'])!=Fraction(r['precision_upper_exact']) for r in cases),
            'closed_half':sum(Fraction(r['precision_lower_exact'])==Fraction(r['precision_upper_exact'])==Fraction(1,2) for r in cases)}
    dump(out/'draws.json',draws_saved); dump(out/'dependence_sensitivity.json',summaries)
    dump(out/'system_effects.json',systems); dump(out/'precision_catalog.json',catalog)
    for filename,records in [('dependence_sensitivity.csv',summaries),('system_effects.csv',systems)]:
        with (out/filename).open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    tex=[r'\begin{table}[htbp]',r'\centering\small',r'\setlength{\tabcolsep}{4pt}',r'\begin{tabular}{lrrrrrr}',r'\toprule',r'System & $n$ & A / F / G & A-only/F-only & $\Delta_F$ (pp) & A-only/G-only & $\Delta_G$ (pp)\\',r'\midrule']
    for cohort in ['original','external']:
        sr=[r for r in systems if r['cohort']==cohort and r['regime']=='exact']
        for meter in sorted({r['meter'] for r in sr}):
            f=next(r for r in sr if r['meter']==meter and r['baseline']=='fixed');g=next(r for r in sr if r['meter']==meter and r['baseline']=='greedy')
            label=('O'+str(int(meter.split('_')[-1])) if cohort=='original' else 'HPM '+meter.split('_')[-1])
            tex.append(f"{label} & {f['compatible_rows']} & {int(f['adaptive_success'])}/{int(f['baseline_success'])}/{int(g['baseline_success'])} & {int(f['adaptive_only'])}/{int(f['baseline_only'])} & {f['difference_pp']:.2f} & {int(g['adaptive_only'])}/{int(g['baseline_only'])} & {g['difference_pp']:.2f}"+r'\\')
    tex += [r'\bottomrule',r'\end{tabular}',r'\caption{Exact-reading paired joint-precision outcomes by system. A is the exact deterministic adaptive planner; F is the best deterministic batch for worst width; G is greedy adaptation. The two discordant counts identify blocks where only A or only its comparator succeeds. O1--O3 are BLEM consumers 1--3; HPM labels retain provider system identifiers. Blocks are repeated observations within systems.}',r'\label{tab:joint_system_effects}',r'\end{table}']
    (out/'main_system_table.tex').write_text('\n'.join(tex)+'\n',encoding='utf8')
    selected=[r for r in summaries if r['omitted_system'] is None and r['baseline'] in ['fixed','greedy']]
    st=[r'\begin{table}[htbp]',r'\centering\scriptsize',r'\begin{tabular}{lllrlr}',r'\toprule',r'Panel & Regime & Comparator & Effect & 7-day / 14-day 95\% & LOO range\\',r'\midrule']
    labels={'exact':'exact','cap_1/2':r'cap $E/2$','cap_1/3':r'cap $E/3$','error_1pct':r'$1\%$ error','cap_half_error_1pct':'cap + error (U)','cap_half_error_1pct_capacity_aware':'cap + error (C)'}
    for r in selected:
        loo=[s['difference_pp'] for s in summaries if s['cohort']==r['cohort'] and s['regime']==r['regime'] and s['baseline']==r['baseline'] and s['omitted_system'] is not None]
        r['leave_one_system_out_effect_range_pp']=[min(loo),max(loo)]
        ci=' / '.join('['+', '.join(f'{v:.2f}' for v in r[key])+']' for key in ['primary_7day','sensitivity_14day'])
        st.append(f"{r['cohort'][0].upper()} & {labels[r['regime']]} & {r['baseline']} & {r['difference_pp']:.2f} & {ci} & [{min(loo):.2f}, {max(loo):.2f}]"+r'\\')
    st += [r'\bottomrule',r'\end{tabular}',r'\caption{Temporal and leave-one-system-out sensitivity. Primary seven-day intervals are unchanged; fourteen-day intervals are a longer-block sensitivity. LOO gives the range of paired percentage-point effects after omitting each system in turn. All are descriptive for the same fixed panels. O/E denote original/external panels; U/C denote policies frozen from uncapped/capacity-aware planning. Combined-error greedy is the frozen uncapped control.}',r'\label{tab:joint_long_dependence}',r'\end{table}']
    (out/'supporting_dependence_table.tex').write_text('\n'.join(st)+'\n',encoding='utf8')
    report={'status':'PASS','scope':__doc__,'inputs':{'outcomes_sha256':sha(args.outcomes),'precision_cases_sha256':sha(args.precision_cases)},
        'precision_plan_validation':({'sha256':sha(args.precision_plans),'matched_rows':1098} if args.precision_plans else None),
        'draws':DRAWS,'base_seed':SEED,'primary_days':7,'sensitivity_days':14,'interval':'percentile 2.5/97.5%, linear interpolation',
        'paired_unit':'same calendar days across systems and all three intraday blocks; compatible denominator in each resample',
        'precision_summary':totals,'full_panel_fixed_greedy':selected,'system_rows':len(systems),'comparison_rows':len(summaries),
        'source_sha256':sha(Path(__file__))}
    dump(out/'report.json',report)
    print(json.dumps({'status':'PASS','comparisons':len(summaries),'precision_summary':totals,'full_panel_fixed_greedy':selected},indent=2))

if __name__=='__main__': main()
