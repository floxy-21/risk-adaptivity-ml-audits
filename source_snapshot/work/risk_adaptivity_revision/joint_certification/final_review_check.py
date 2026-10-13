"""Independently recount paired outcomes and bootstrap by sampled-day multiplicity.

Does not import the producer. Checks printed fixed/greedy cells against the
original outcome ledger, percentile interpolation by sorting scalar results,
the unchanged seven-day summaries, and exact precision-bound classifications.
"""
import argparse, hashlib, json, math
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent

def read(p): return json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rational(x): return F(int(x)) if isinstance(x,bool) else F(str(x))
def percentile(values,p):
    ordered=sorted(values); h=(len(ordered)-1)*p; low=math.floor(h)
    return ordered[low]+(h-low)*(ordered[min(low+1,len(ordered)-1)]-ordered[low])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',type=Path,default=HERE/'final_review_results')
    p.add_argument('--outcomes',type=Path,default=HERE/'empirical_paired_all_results/case_outcomes.json')
    p.add_argument('--precision-cases',type=Path,default=HERE/'empirical_precision_all_results/cases.json')
    p.add_argument('--output',type=Path,default=HERE/'final_review_independent.json')
    a=p.parse_args(); rows=read(a.outcomes); result=read(a.results_dir/'report.json')
    assert result['inputs']=={'outcomes_sha256':sha(a.outcomes),'precision_cases_sha256':sha(a.precision_cases)}
    summaries=read(a.results_dir/'dependence_sensitivity.json'); drawsets=read(a.results_dir/'draws.json')
    weights={}; discrepancies=[]; draws_checked=0
    for cohort,ds in drawsets.items():
        days=sorted({r['day'] for r in rows if r['cohort']==cohort});assert days==ds['days']
        for length in [7,14]:
            saved=ds['lengths'][str(length)];stream=0 if cohort=='original' else 1
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([20261013,stream,length])))
            starts=rng.integers(len(days),size=(2000,math.ceil(len(days)/length))).tolist()
            assert starts==saved['starts'];freq=[]
            for start,indices in zip(starts,saved['indices']):
                rebuilt=[(s+offset)%len(days) for s in start for offset in range(length)][:len(days)]
                assert rebuilt==indices; freq.append(list(Counter(rebuilt).items()));draws_checked+=1
            assert len(freq)==2000;weights[cohort,length]=freq
    def close(x,y):
        error=abs(float(x)-float(y));discrepancies.append(error);assert error<1e-9,(x,y,error)
    for item in summaries+read(a.results_dir/'system_effects.json'):
        rr=[r for r in rows if r['cohort']==item['cohort'] and r['regime']==item['regime']]
        if 'meter' in item:rr=[r for r in rr if r['meter']==item['meter']]
        else:rr=[r for r in rr if r['meter']!=item['omitted_system']]
        valid=[r for r in rr if r['valid']];base=item['baseline'];t=defaultdict(F)
        for r in valid:
            A=rational(r['adaptive']);B=rational(r['baselines'][base])
            t['both']+=A*B;t['adaptive_only']+=A*(1-B);t['baseline_only']+=(1-A)*B;t['neither']+=(1-A)*(1-B)
            t['adaptive_success']+=A;t['baseline_success']+=B
        assert item['all_rows']==len(rr) and item['compatible_rows']==len(valid) and item['incompatible_rows']==len(rr)-len(valid)
        for key,value in t.items():close(value,item[key])
        close(100*(t['adaptive_success']-t['baseline_success'])/len(valid),item['difference_pp'])
        if 'meter' in item:continue
        days=drawsets[item['cohort']]['days']; daily=defaultdict(lambda:[0.0,0])
        for r in valid:
            daily[r['day']][0]+=float(r['adaptive'])-float(r['baselines'][base]);daily[r['day']][1]+=1
        for length,key in [(7,'primary_7day'),(14,'sensitivity_14day')]:
            num=[daily[d][0] for d in days];den=[daily[d][1] for d in days];estimates=[]
            for multiplicities in weights[item['cohort'],length]:
                n=sum(num[i]*count for i,count in multiplicities);d=sum(den[i]*count for i,count in multiplicities)
                assert d>0;estimates.append(100*n/d)
            close(percentile(estimates,.025),item[key][0]);close(percentile(estimates,.975),item[key][1])
    old=read(HERE/'empirical_paired_all_results/paired_statistics.json')
    oldkey={(r['cohort'],r['regime'],r['baseline']):r for r in old if r['meter']=='ALL'}
    for row in summaries:
        if row['omitted_system'] is None:
            other=oldkey[row['cohort'],row['regime'],row['baseline']]
            close(row['primary_7day'][0],other['percentile_95_lower']);close(row['primary_7day'][1],other['percentile_95_upper'])
    precision={r['id']:r for r in read(a.precision_cases)};catalog=read(a.results_dir/'precision_catalog.json')
    assert len(precision)==len(catalog)==1098
    counts={c:Counter() for c in ['original','external']}
    for row in catalog:
        oldrow=precision[row['id']]
        for key,value in row.items():assert oldrow[key]==value
        lo,hi=F(row['precision_lower_exact']),F(row['precision_upper_exact']);assert 0<=lo<=hi<=1
        assert row['continuum_optimum_identified']==(lo==hi)
        cc=counts[row['cohort']];cc['cases']+=1;cc[row['policy_kind']]+=1;cc['closed_gap' if lo==hi else 'open_gap']+=1
        if lo==hi==F(1,2):cc['closed_half']+=1
    for cohort,cc in counts.items():
        reported=result['precision_summary'][cohort]
        for field in ['cases','closed_gap','open_gap','closed_half']:assert reported[field]==cc[field]
        for kind,count in reported['policy_counts'].items():assert cc[kind]==count
    for r in result['full_panel_fixed_greedy']:
        chosen=[x['difference_pp'] for x in summaries if x['cohort']==r['cohort'] and x['regime']==r['regime'] and x['baseline']==r['baseline'] and x['omitted_system'] is not None]
        close(min(chosen),r['leave_one_system_out_effect_range_pp'][0]);close(max(chosen),r['leave_one_system_out_effect_range_pp'][1])
    output={'status':'PASS','paired_comparisons':len(summaries),'system_rows':len(read(a.results_dir/'system_effects.json')),
            'draws_structurally_checked':draws_checked,'precision_catalog_rows':len(catalog),'seven_day_unchanged':True,
            'maximum_discrepancy':max(discrepancies),'source_sha256':sha(Path(__file__))}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(output,indent=2)+'\n',encoding='utf8');print(json.dumps(output,indent=2))

if __name__=='__main__':main()
