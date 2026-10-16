"""Summarize exact precision completion and join the fixed-budget evidence."""
from pathlib import Path
from collections import Counter
from fractions import Fraction as F
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=HERE/'all_418')
 p.add_argument('--catalog',type=Path,default=HERE/'inputs/precision_catalog.json')
 p.add_argument('--budget-ledger',type=Path,default=HERE.parent/'reading_budget/executed_all/ledger.json')
 a=p.parse_args();d=json.loads((a.results/'report.json').read_text());catalog=json.loads(a.catalog.read_text())
 complete={r['id']:r for r in d['cases']};assert len(complete)==418 and all(r['status']=='MATCHED_EXACT' for r in complete.values())
 rows=[]
 for r in catalog['plans']:
  val=complete[r['id']]['lower'] if r['id'] in complete else r['precision_lower_exact']
  if r['id'] not in complete:assert r['precision_lower_exact']==r['precision_upper_exact']
  rows.append({'id':r['id'],'cohort':r['cohort'],'meter':r['meter'],'precision_optimum':val})
 by_id={r['id']:r for r in rows};budgets=json.loads(a.budget_ledger.read_text())['rows']
 assert set(by_id)=={r['id'] for r in budgets}
 qualifying=[r for r in budgets if r['fixed_minimum_readings']==3 and r['adaptive_minimum_readings']==2]
 assert len(qualifying)==225
 extra=[by_id[r['id']] for r in qualifying if by_id[r['id']]['precision_optimum']!='1/2']
 assert len(extra)==3 and all(r['precision_optimum']=='1/3' for r in extra)
 summary={}
 for c in ['original','external','all']:
  z=[r for r in rows if c=='all' or r['cohort']==c]
  new=[r for r in d['cases'] if c=='all' or r['cohort']==c]
  summary[c]={'blocks':len(z),'exact_precision_distribution':dict(Counter(r['precision_optimum'] for r in z)),
    'previously_open':len(new),'closed':len(new),'upper_bound_strictly_lowered':sum(F(r['upper'])<F(r['old_upper']) for r in new),
    'positive_lower_bound_newly_proved':sum(F(r['lower'])>F(r['old_lower']) for r in new)}
 out={'status':'PASS','summaries':summary,'all_1098_exact_values':rows,'reading_saving_cases':225,
   'reading_saving_batch_value_half':222,'additional_reading_saving_cases':extra,
   'primary_producer_total_seconds':sum(r['seconds'] for r in d['cases']),
   'primary_case_max_seconds':max(r['seconds'] for r in d['cases']),
   'total_LPs':sum(r['LPs'] for r in d['cases']),'maximum_case_LPs':max(r['LPs'] for r in d['cases']),
   'maximum_case_tree_nodes':max(r['tree_nodes'] for r in d['cases']),
   'maximum_case_certificate_json_bytes':max(len(json.dumps(r['cover_certificates']).encode()) for r in d['cases']),
   'producer_report_bytes':(a.results/'report.json').stat().st_size,'producer_report_sha256':sha(a.results/'report.json'),
   'source_catalog_sha256':sha(a.catalog),'budget_ledger_sha256':sha(a.budget_ledger),'fine_answers_loaded':False}
 (a.results/'summary.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:v for k,v in out.items() if k!='all_1098_exact_values'},indent=2))
if __name__=='__main__':main()
