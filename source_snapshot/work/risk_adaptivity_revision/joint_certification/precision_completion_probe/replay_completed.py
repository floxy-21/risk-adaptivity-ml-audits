"""Replay the frozen precision-optimal challenger, without policy selection.

Saved policy/proof hashes are recorded before loading recorded batch widths.
The saved seven-day synchronized bootstrap draws are reused unchanged.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import argparse,hashlib,json,time
import numpy as np
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf8')

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--results',type=Path,default=HERE/'refined_all')
 p.add_argument('--recorded-inputs',type=Path,default=HERE.parent/'final_challenger_diagnostics/frozen_inputs.json')
 p.add_argument('--bootstrap-draws',type=Path,default=HERE.parent/'final_challenger_diagnostics/results/bootstrap_draws.json')
 a=p.parse_args();start=time.perf_counter()
 policy_path=a.results/'report.json';policies=json.loads(policy_path.read_text());policy_sha=sha(policy_path)
 assert policies['status']=='PASS' and policies['policies_frozen_before_recorded_replay'] and policies['fine_answers_loaded'] is False
 check=json.loads((a.results/'independent_check.json').read_text())
 assert check['status']=='PASS' and check['checks']['matched_continuum_optima']==1098 and check['producer_report_sha256']==policy_sha
 # Only after the complete policy file and its verifier pass are read and
 # fixed do we load any recorded-answer replay values.
 recorded=json.loads(a.recorded_inputs.read_text());source={r['id']:r for r in recorded['cases']}
 assert set(source)=={r['id'] for r in policies['cases']}
 draws=json.loads(a.bootstrap_draws.read_text());out=[]
 for r in policies['cases']:
  s=source[r['id']];assert hashlib.sha256(json.dumps(r['normalized_coefficients_exact'],separators=(',',':')).encode()).hexdigest()==s['coefficient_digest']
  pi=list(map(F,r['batch_weights']));widths=list(map(F,s['batch_widths']))
  for convention,tol in [('strict',F(0)),('original_tolerance',F(1,10**8))]:
   hits=[int(w<=F(1,2)+tol) for w in widths]
   success=sum(w*h for w,h in zip(pi,hits));adaptive=hits[s['adaptive_batch_index']]
   out.append({'id':r['id'],'cohort':r['cohort'],'meter':r['meter'],'day':s['day'],'convention':convention,
    'precision_optimum':r['lower'],'adaptive_success':adaptive,'batch_success_exact':str(success),
    'adaptive_J':str(widths[s['adaptive_batch_index']]),'batch_expected_J_exact':str(sum(p*w for p,w in zip(pi,widths))),
    'both_success_exact':str(adaptive*success),'adaptive_only_exact':str(adaptive*(1-success)),
    'batch_only_exact':str((1-adaptive)*success),'neither_exact':str((1-adaptive)*(1-success)),
    'fixed_success':hits[s['fixed_batch_index']],'greedy_success':hits[s['greedy_batch_index']]})
 groups=[]
 for cohort in ['original','external']:
  for convention in ['strict','original_tolerance']:
   for subset in ['all','matched_half','zero_precision']:
    eligible=[r for r in out if r['cohort']==cohort and r['convention']==convention and (subset=='all' or r['precision_optimum']==('1/2' if subset=='matched_half' else '0'))]
    for meter in ['ALL']+sorted({r['meter'] for r in eligible}):
     z=[r for r in eligible if meter=='ALL' or r['meter']==meter]
     a_count=sum(r['adaptive_success'] for r in z);b_count=sum(F(r['batch_success_exact']) for r in z)
     days=draws[cohort]['days'];indices=np.array(draws[cohort]['indices'],dtype=int)
     num=np.array([sum(r['adaptive_success']-float(F(r['batch_success_exact'])) for r in z if r['day']==day) for day in days])
     den=np.array([sum(r['day']==day for r in z) for day in days]);ds=den[indices].sum(axis=1);keep=ds>0
     boot=100*num[indices].sum(axis=1)[keep]/ds[keep]
     groups.append({'cohort':cohort,'meter':meter,'subset':subset,'convention':convention,'blocks':len(z),
      'adaptive_success_count':a_count,'precision_batch_expected_success_exact':str(b_count),
      'adaptive_percent':100*a_count/len(z),'precision_batch_percent':100*float(b_count)/len(z),
      'adaptive_minus_batch_pp':100*(a_count-float(b_count))/len(z),
      'descriptive_95_percentile_pp':[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],
      'paired_expected_counts':{k:str(sum(F(r[k+'_exact']) for r in z)) for k in ['both_success','adaptive_only','batch_only','neither']},
      'adaptive_mean_J':sum(float(F(r['adaptive_J'])) for r in z)/len(z),
      'batch_expected_mean_J':sum(float(F(r['batch_expected_J_exact'])) for r in z)/len(z)})
 write(a.results/'recorded_replay_cases.json',out)
 summary={'status':'PASS','policy_sha256_before_recorded_read':policy_sha,'independent_check_sha256':sha(a.results/'independent_check.json'),
  'recorded_inputs_sha256':sha(a.recorded_inputs),'bootstrap_draws_sha256':sha(a.bootstrap_draws),
  'source_sha256':sha(Path(__file__)),'policies_changed':False,'cases':1098,'conventions':['strict','original_tolerance'],
  'bootstrap':'Unchanged saved 2000 seven-day circular calendar-block draws synchronized across systems and intraday blocks; counts for randomized policies are exact expectations.',
  'secondary_status_counts':dict(Counter(r['secondary']['status'] for r in policies['cases'])),
  'secondary_lexicographic_incomplete':sum(r['secondary'].get('lexicographic_completed') is False for r in policies['cases']),
  'secondary_total_seconds':sum(r['secondary']['seconds'] for r in policies['cases']),
  'secondary_max_seconds':max(r['secondary']['seconds'] for r in policies['cases']),
  'secondary_total_LPs':sum(r['secondary']['LPs'] for r in policies['cases']),
  'groups':groups,'elapsed_seconds':time.perf_counter()-start}
 write(a.results/'recorded_replay_summary.json',summary)
 print(json.dumps({k:v for k,v in summary.items() if k!='groups'},indent=2))
 for r in groups:
  if r['meter']=='ALL' and r['subset']=='all':print(json.dumps(r))

if __name__=='__main__':main()
