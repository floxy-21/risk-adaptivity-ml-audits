"""Independently reconstruct frozen-challenger replay and paired summaries."""
from pathlib import Path
from fractions import Fraction as F
import argparse,hashlib,json,time
import numpy as np
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--results',type=Path,default=HERE/'refined_all')
 p.add_argument('--recorded-inputs',type=Path,default=HERE.parent/'final_challenger_diagnostics/frozen_inputs.json')
 p.add_argument('--bootstrap-draws',type=Path,default=HERE.parent/'final_challenger_diagnostics/results/bootstrap_draws.json')
 a=p.parse_args();start=time.perf_counter();d=json.loads((a.results/'report.json').read_text())
 summary=json.loads((a.results/'recorded_replay_summary.json').read_text())
 assert summary['status']=='PASS' and summary['policies_changed'] is False and summary['cases']==1098
 assert summary['source_sha256']==sha(HERE/'replay_completed.py')
 assert summary['policy_sha256_before_recorded_read']==sha(a.results/'report.json')
 assert summary['independent_check_sha256']==sha(a.results/'independent_check.json')
 certificate_check=json.loads((a.results/'independent_check.json').read_text())
 assert certificate_check['status']=='PASS' and certificate_check['checks']['matched_continuum_optima']==1098
 assert certificate_check['producer_report_sha256']==sha(a.results/'report.json')
 assert summary['recorded_inputs_sha256']==sha(a.recorded_inputs) and summary['bootstrap_draws_sha256']==sha(a.bootstrap_draws)
 original={r['id']:r for r in json.loads(a.recorded_inputs.read_text())['cases']};policy={r['id']:r for r in d['cases']}
 ledger=json.loads((a.results/'recorded_replay_cases.json').read_text());actual={(r['id'],r['convention']):r for r in ledger}
 assert len(actual)==len(ledger)==2196 and set(original)==set(policy)
 expected={};checks=0
 for key,s in original.items():
  pi=[F(x) for x in policy[key]['batch_weights']];width=[F(x) for x in s['batch_widths']]
  assert len(pi)==len(width)==10 and min(pi)>=0 and sum(pi)==1
  assert hashlib.sha256(json.dumps(policy[key]['normalized_coefficients_exact'],separators=(',',':')).encode()).hexdigest()==s['coefficient_digest']
  for name,tol in [('strict',F(0)),('original_tolerance',F(1,10**8))]:
   hit=[int(x<=F(1,2)+tol) for x in width]
   ac=hit[s['adaptive_batch_index']];bc=sum(pi[q]*hit[q] for q in range(10))
   r={'id':key,'cohort':s['cohort'],'meter':s['meter'],'day':s['day'],'convention':name,
      'precision_optimum':policy[key]['lower'],'adaptive_success':ac,'batch_success_exact':str(bc),
      'adaptive_J':str(width[s['adaptive_batch_index']]),'batch_expected_J_exact':str(sum(x*w for x,w in zip(pi,width))),
      'both_success_exact':str(ac*bc),'adaptive_only_exact':str(ac*(1-bc)),
      'batch_only_exact':str((1-ac)*bc),'neither_exact':str((1-ac)*(1-bc)),
      'fixed_success':hit[s['fixed_batch_index']],'greedy_success':hit[s['greedy_batch_index']]}
   assert actual[key,name]==r;expected[key,name]=r;checks+=10
 draws=json.loads(a.bootstrap_draws.read_text());groupkeys=set();maxdisc=0.
 for g in summary['groups']:
  gkey=(g['cohort'],g['meter'],g['subset'],g['convention']);assert gkey not in groupkeys;groupkeys.add(gkey)
  z=[r for r in expected.values() if r['cohort']==g['cohort'] and r['convention']==g['convention'] and
     (g['meter']=='ALL' or r['meter']==g['meter']) and
     (g['subset']=='all' or r['precision_optimum']==('1/2' if g['subset']=='matched_half' else '0'))]
  assert len(z)==g['blocks'];ac=sum(r['adaptive_success'] for r in z);bc=sum(F(r['batch_success_exact']) for r in z)
  assert ac==g['adaptive_success_count'] and str(bc)==g['precision_batch_expected_success_exact']
  for name in ['both_success','adaptive_only','batch_only','neither']:
   assert str(sum(F(r[name+'_exact']) for r in z))==g['paired_expected_counts'][name]
  assert sum(F(g['paired_expected_counts'][x]) for x in g['paired_expected_counts'])==len(z)
  numeric={'adaptive_percent':100*ac/len(z),'precision_batch_percent':100*float(bc)/len(z),
    'adaptive_minus_batch_pp':100*(ac-float(bc))/len(z),
    'adaptive_mean_J':sum(float(F(r['adaptive_J'])) for r in z)/len(z),
    'batch_expected_mean_J':sum(float(F(r['batch_expected_J_exact'])) for r in z)/len(z)}
  for k,v in numeric.items():maxdisc=max(maxdisc,abs(v-g[k]));assert abs(v-g[k])<1e-9
  daymap={day:i for i,day in enumerate(draws[g['cohort']]['days'])};num=np.zeros(len(daymap));den=np.zeros(len(daymap))
  for r in z:
   i=daymap[r['day']];num[i]+=r['adaptive_success']-float(F(r['batch_success_exact']));den[i]+=1
  ix=np.asarray(draws[g['cohort']]['indices']);ds=den[ix].sum(axis=1);mask=ds>0
  values=100*num[ix].sum(axis=1)[mask]/ds[mask];ci=np.percentile(values,[2.5,97.5],method='linear')
  assert np.max(np.abs(ci-np.asarray(g['descriptive_95_percentile_pp'])))<1e-9
 assert len(groupkeys)==48
 report={'status':'PASS','recorded_blocks':1098,'case_convention_rows':len(ledger),'batch_outcome_evaluations':checks,
   'paired_summary_groups':len(groupkeys),'maximum_numeric_summary_discrepancy':maxdisc,'summary_tolerance':1e-9,
   'exact_scope':'All per-case probabilities and paired expected counts are reconstructed with rational arithmetic.',
   'bootstrap_scope':'Saved synchronized seven-day draws; independent aggregation, descriptive percentile intervals.',
   'policy_sha256':sha(a.results/'report.json'),'replay_summary_sha256':sha(a.results/'recorded_replay_summary.json'),
   'replay_ledger_sha256':sha(a.results/'recorded_replay_cases.json'),'checker_sha256':sha(Path(__file__)),
   'elapsed_seconds':time.perf_counter()-start}
 (a.results/'recorded_replay_check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
