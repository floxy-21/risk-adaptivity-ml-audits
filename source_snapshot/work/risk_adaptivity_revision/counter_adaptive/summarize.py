"""Summarize every predeclared counter task; never select by fine-answer outcomes."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd

def main():
    p=argparse.ArgumentParser(); p.add_argument('--input-dirs',nargs='+',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args(); a.output_dir.mkdir(parents=True,exist_ok=True)
    cases=[]; dfs=[]; phases=[]
    for path in a.input_dirs:
        g=json.loads((path/'geometry.json').read_text()); cases+=g['cases']; dfs.append(pd.read_csv(path/'replay_cases.csv')); phases.append({'path':path.as_posix(),'geometry_sha256':hashlib.sha256((path/'geometry.json').read_bytes()).hexdigest(),'replay_sha256':hashlib.sha256((path/'replay_cases.csv').read_bytes()).hexdigest(),'tasks':len(g['cases']),'geometry_seconds':g['seconds']})
    assert len({c['id'] for c in cases})==len(cases)
    d=pd.concat(dfs,ignore_index=True); assert len(d)==len(cases)*5
    led=[]
    for c in cases:
        for x in c['geometry']['precision']:
            led.append({k:c[k] for k in ['id','meter','day','phase','start_hour','model_a','model_b']}|{'fraction':x['fraction'],'positive_width':c['W0']>0,'A_relative':c['geometry']['A'],'adaptive_guarantee':x['adaptive_guarantee'] or c['W0']==0,'batch_upper':x['upper'],'strong_separation':x['separation_le_70'] and c['W0']>0,'adversary_weights':json.dumps(x['weights']),'mean_optimum':c['geometry']['mean_value'],'mean_residual':c['geometry']['mean_residual']})
    l=pd.DataFrame(led); l.to_csv(a.output_dir/'certificate_ledger.csv',index=False)
    primary=l[l.fraction==.5]; strong=set(primary[primary.strong_separation].id)
    assert len(primary)==len(cases)
    groups={}
    for name,keys in [('overall',[]),('meter',['meter']),('pair',['model_a','model_b']),('phase',['phase'])]:
        items=[('all',primary)] if not keys else primary.groupby(keys)
        out=[]
        for key,frame in items:
            row={'group':str(key),'tasks':len(frame),'adaptive_guarantees':int(frame.adaptive_guarantee.sum()),'strong_separations':int(frame.strong_separation.sum()),'batch_at_most_half':int(((frame.batch_upper<=.5+1e-12)&frame.strong_separation).sum()),'batch_upper_max_in_separation':float(frame[frame.strong_separation].batch_upper.max()) if frame.strong_separation.any() else None}
            out.append(row)
        groups[name]=out
    subsets={}
    for name,df in [('all',d),('separation',d[d.id.isin(strong)])]:
        tab=df.groupby('policy')[['success_0.5','relative_width','scaled_width','winner_probability','requests']].mean().reset_index()
        subsets[name]=tab.to_dict('records'); tab.to_csv(a.output_dir/f'{name}_policy_summary.csv',index=False)
        for by in ['meter','phase','model_a,model_b']:
            keys=by.split(','); df.groupby(keys+['policy'])[['success_0.5','relative_width','winner_probability']].mean().reset_index().to_csv(a.output_dir/f'{name}_{by.replace(",","_")}_summary.csv',index=False)
    curve=l.groupby('fraction')[['adaptive_guarantee','strong_separation']].agg(['sum','mean']); curve.to_csv(a.output_dir/'precision_guarantee_curve.csv')
    d.groupby('policy')[[f'success_{x}' for x in [.25,.4,.5,.6,.75]]].mean().to_csv(a.output_dir/'precision_replay_curve.csv')
    overall=d.groupby('policy')['success_0.5'].mean(); bymeter=d.groupby(['meter','policy'])['success_0.5'].mean()
    tests={'at_least_10_percent_strong':float(primary.strong_separation.mean())>=.1,'all_three_meters':sum(x['strong_separations']>0 for x in groups['meter'])==3,'at_least_three_pairs':sum(x['strong_separations']>0 for x in groups['pair'])>=3,'observed_exceeds_every_nonadaptive_overall':all(overall['adaptive']>overall[p]+1e-12 for p in ['det_batch','mean_batch','uniform_batch']),'observed_exceeds_every_nonadaptive_each_meter':all(bymeter[m,'adaptive']>bymeter[m,p]+1e-12 for m in d.meter.unique() for p in ['det_batch','mean_batch','uniform_batch'])}
    report={'status':'PASS','tasks':len(cases),'meters':3,'model_pairs':6,'primary_fraction':.5,'groups':groups,'replay':subsets,'screening_criteria':tests,'screening_all_met':all(tests.values()),'zero_width_cases':int((~primary.positive_width).sum()),'max_mean_optimal_face_residual':float(primary.mean_residual.max()),'source_phases':phases,'scope':'All tasks retained; strong subset chosen only by pre-answer geometry, not replay outcomes. Only three meters, no iid task inference.'}
    (a.output_dir/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
