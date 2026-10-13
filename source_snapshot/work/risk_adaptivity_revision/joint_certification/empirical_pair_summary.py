"""Paired block outcomes and descriptive calendar-day-cluster uncertainty.

The primary sensitivity resamples circular seven-day calendar blocks jointly
across systems and intraday blocks. A one-day cluster bootstrap is secondary.
These fixed-panel intervals do not quantify population-level system uncertainty.
"""
import argparse,csv,json
from pathlib import Path
import numpy as np
from empirical_shared_audit import HERE,sha,dump,input_record
SEED=20261013;DRAWS=2000

def csv_rows(path):
    with path.open(newline='',encoding='utf8') as f:return list(csv.DictReader(f))
def integer(value):return value is True or value=='True'
def pack(r,regime,valid,A,baselines):
    return {'id':r['id'],'cohort':r['cohort'],'meter':r['meter'],'day':r['id'].split('/')[-2],
            'regime':regime,'valid':valid,'adaptive':A,'baselines':baselines}

def load(args):
    paths={};rows=[]
    exact=args.exact_cases or HERE/('empirical_external_results/empirical_cases.csv' if args.cohort=='external' else 'empirical_all_panel_cases.csv')
    cap=args.capacity_cases or HERE/('empirical_external_capacity_results/empirical_capacity_cases.csv' if args.cohort=='external' else 'empirical_all_capacity_cases.csv')
    paths['exact']=exact;paths['capacity']=cap
    precision=args.precision_replay_dir or HERE/('empirical_precision_results' if args.cohort=='external' else 'empirical_precision_all_results')
    paths['precision']=precision/'cases.json';precision_rows={r['id']:r for r in json.loads(paths['precision'].read_text())}
    for r in csv_rows(exact):
        pr=precision_rows[r['id']];assert pr['adaptive_success']==float(r['adaptive_recorded_success'])
        rows.append(pack(r,'exact',True,float(r['adaptive_recorded_success']),{
            'fixed':float(r['det_batch_recorded_success']),'greedy':float(r['greedy_recorded_success']),
            'randomized_mean':float(r['randomized_batch_recorded_success_probability']),
            'randomized_precision':pr['precision_batch_success_probability']}))
    for r in csv_rows(cap):
        valid=integer(r['actual_record_satisfies_cap']);A=float(r['adaptive_recorded_J'])<=.5+1e-8 if valid else None
        b={name:float(r[field])<=.5+1e-8 for name,field in [('fixed','det_batch_recorded_J'),('greedy','greedy_recorded_J')]} if valid else {}
        if valid:b['randomized_mean']=float(r['original_randomized_batch_success_probability'])
        rows.append(pack(r,'cap_'+r['cap_fraction'],valid,A,b))
    for name,folder in [('frozen',args.noise_dir),('capacity_aware',args.capacity_noise_dir)]:
        path=folder/'empirical_noise_cases.json';paths[name+'_noise']=path
        for r in json.loads(path.read_text()):
            valid=r['actual_record_satisfies_cap'];regime=r['scenario']+('_capacity_aware' if name=='capacity_aware' else '')
            b={k:r[field] for k,field in [('fixed','robust_det_batch_success'),('greedy','greedy_success'),('randomized_mean','randomized_batch_success_probability')]} if valid else {}
            rows.append(pack(r,regime,valid,r['adaptive_success'],b))
    rows=[r for r in rows if args.cohort in ['all',r['cohort']]]
    return rows,{name:input_record(path) for name,path in paths.items()}

def statistic(rows,base,days,draws,day_draws):
    valid=[r for r in rows if r['valid']];n=len(valid)
    byday={d:[] for d in days}
    for r in valid:byday[r['day']].append(r)
    numer=np.array([sum(float(r['adaptive'])-float(r['baselines'][base]) for r in byday[d]) for d in days])
    denomin=np.array([len(byday[d]) for d in days]);N=denomin[draws].sum(axis=1);assert (N>0).all()
    estimates=100*numer[draws].sum(axis=1)/N
    day_estimates=100*numer[day_draws].sum(axis=1)/denomin[day_draws].sum(axis=1)
    A=np.array([float(r['adaptive']) for r in valid]);B=np.array([float(r['baselines'][base]) for r in valid])
    return {'all_rows':len(rows),'compatible_rows':n,'incompatible_rows':len(rows)-n,
        'both_success':float((A*B).sum()),'adaptive_only':float((A*(1-B)).sum()),
        'baseline_only':float(((1-A)*B).sum()),'neither_success':float(((1-A)*(1-B)).sum()),
        'adaptive_success_count':float(A.sum()),'baseline_success_count':float(B.sum()),
        'difference_percentage_points':float(100*(A-B).mean()),
        'percentile_95_lower':float(np.quantile(estimates,.025,method='linear')),
        'percentile_95_upper':float(np.quantile(estimates,.975,method='linear')),
        'day_percentile_95_lower':float(np.quantile(day_estimates,.025,method='linear')),
        'day_percentile_95_upper':float(np.quantile(day_estimates,.975,method='linear')),
        'cells_are_expected_counts':base.startswith('randomized_'),'calendar_days':len(days)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',choices=['external','original','all'],default='external')
    p.add_argument('--exact-cases',type=Path)
    p.add_argument('--capacity-cases',type=Path)
    p.add_argument('--precision-replay-dir',type=Path)
    p.add_argument('--noise-dir',type=Path,default=HERE/'empirical_noise_results')
    p.add_argument('--capacity-noise-dir',type=Path,default=HERE/'empirical_capacity_noise_results')
    p.add_argument('--output-dir',type=Path,default=HERE/'empirical_paired_external_results');a=p.parse_args()
    rows,inputs=load(a);out=a.output_dir;out.mkdir(parents=True,exist_ok=True)
    cohorts=sorted({r['cohort'] for r in rows});drawsets={};summaries=[]
    for cohort in cohorts:
        days=sorted({r['day'] for r in rows if r['cohort']==cohort});stream=0 if cohort=='original' else 1
        generator=np.random.default_rng(np.random.SeedSequence([SEED,stream]));day_draws=generator.integers(0,len(days),size=(DRAWS,len(days)))
        week_rng=np.random.default_rng(np.random.SeedSequence([SEED,stream,7]));starts=week_rng.integers(0,len(days),size=(DRAWS,(len(days)+6)//7))
        draws=((starts[:,:,None]+np.arange(7))%len(days)).reshape(DRAWS,-1)[:,:len(days)]
        drawsets[cohort]={'days':days,'seed_sequence':[SEED,stream,7],'day_seed_sequence':[SEED,stream],'block_length':7,
                         'indices':draws.tolist(),'day_indices':day_draws.tolist()}
        for regime in sorted({r['regime'] for r in rows if r['cohort']==cohort}):
            panel=[r for r in rows if r['cohort']==cohort and r['regime']==regime]
            for meter in ['ALL']+sorted({r['meter'] for r in panel}):
                selected=panel if meter=='ALL' else [r for r in panel if r['meter']==meter]
                for base in ['fixed','greedy','randomized_mean','randomized_precision']:
                    if all(base in r['baselines'] for r in selected if r['valid']):
                        summaries.append({'cohort':cohort,'regime':regime,'meter':meter,'baseline':base,**statistic(selected,base,days,draws,day_draws)})
    dump(out/'case_outcomes.json',rows);dump(out/'bootstrap_draws.json',drawsets);dump(out/'paired_statistics.json',summaries)
    with (out/'paired_statistics.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
    labels={'exact':'exact','cap_1/2':r'cap $1/2$','cap_1/3':r'cap $1/3$','error_1pct':r'$1\%$ error',
            'cap_half_error_1pct':r'cap $1/2$ + error (U)','cap_half_error_1pct_capacity_aware':r'cap $1/2$ + error (C)'}
    tex=[r'\begin{table}[htbp]',r'\centering\scriptsize',r'\begin{tabular}{llrrrrl}',r'\toprule',
         r'Panel / regime & Comparator & Both & A only & B only & Neither & $\Delta$ pp [95\%]\\',r'\midrule']
    for r in summaries:
        if r['meter']!='ALL' or r['baseline'] not in ['fixed','greedy']:continue
        label=('O' if r['cohort']=='original' else 'E')+', '+labels[r['regime']]
        cells=' & '.join(str(int(r[k])) for k in ['both_success','adaptive_only','baseline_only','neither_success'])
        interval=f"{r['difference_percentage_points']:.2f} [{r['percentile_95_lower']:.2f}, {r['percentile_95_upper']:.2f}]"
        tex.append(label+' & '+r['baseline']+' & '+cells+' & '+interval+r'\\')
    tex += [r'\bottomrule',r'\end{tabular}',r'\caption{Paired joint-precision outcomes. A is adaptive and B is the named comparator. O/E denote original/external panels; U/C denote policies frozen from uncapped/capacity-aware planning. Counts sum to each compatible panel size. Combined-error greedy remains the frozen uncapped control. Intervals use 2,000 synchronized seven-day circular calendar-block draws; they are descriptive for these panels. Randomized-comparator expected cells, individual-system results, and one-day-cluster sensitivity are supplied in the CSV.}',r'\label{tab:joint_paired_outcomes}',r'\end{table}']
    (out/'paired_table.tex').write_text('\n'.join(tex)+'\n',encoding='utf8')
    report={'status':'PASS','scope':__doc__,'cohort':a.cohort,'draws':DRAWS,'base_seed':SEED,
        'interval_method':'Percentile 2.5/97.5%, numpy quantile method=linear; paired difference, ratio of compatible successes to compatible block count in each resampled panel',
        'resampling_unit':'Primary: seven-day circular calendar blocks, concatenated and truncated to original horizon; days synchronized across all three systems and intraday blocks. Secondary: individual calendar days. Identical draws across regimes and baselines.',
        'seed_rule':'numpy PCG64 SeedSequence([20261013,cohort_id,7]) for primary; [20261013,cohort_id] secondary, cohort_id0 original/1 external',
        'dependence_limit':'Conditional descriptive sensitivity; only three systems. Seven-day blocks preserve within-week dependence, not arbitrary long-range dependence or between-organization variability. No population inference.',
        'case_rows':len(rows),'comparison_rows':len(summaries),'inputs':inputs,
        'full_panel_summaries':[r for r in summaries if r['meter']=='ALL'],
        'draw_sha256':sha(out/'bootstrap_draws.json'),'source_sha256':sha(Path(__file__))}
    dump(out/'report.json',report);print(json.dumps({'status':'PASS','comparisons':len(summaries),'full_panel_summaries':report['full_panel_summaries']},indent=2))
if __name__=='__main__':main()
