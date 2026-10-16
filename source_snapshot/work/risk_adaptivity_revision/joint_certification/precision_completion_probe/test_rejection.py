"""Bounded corruption tests for the independent exact verifier."""
from pathlib import Path
from copy import deepcopy
from collections import defaultdict
from fractions import Fraction as F
import argparse,json,hashlib
import check_completion as checker

HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=HERE/'pilot');a=p.parse_args()
 d=json.loads((a.results/'report.json').read_text())
 catalog=json.loads((HERE/'inputs/precision_catalog.json').read_text())
 sources={r['id']:r for r in catalog['plans']}
 original=next(r for r in d['cases'] if r['status']=='MATCHED_EXACT' and r['cover_certificates'])
 checker.verify_case(original,sources[original['id']],defaultdict(int))
 def coef(r):r['normalized_coefficients_exact'][0][0]=str(F(r['normalized_coefficients_exact'][0][0])+F(1,10))
 def point(r):r['profiles'][0][0]='-1'
 def branch(r):r['cover_certificates'][0]['proof']['branches'].pop()
 def pi(r):r['batch_weights'][0]=str(F(r['batch_weights'][0])+F(1,10))
 def adverse(r):r['adverse_weights'][0]=str(F(r['adverse_weights'][0])+F(1,10))
 def bound(r):r['lower']=str(F(r['lower'])+F(1,100))
 results=[]
 for name,mutate in [('altered_coefficients',coef),('infeasible_profile',point),('missing_cover_branch',branch),('invalid_batch_probability',pi),('invalid_adverse_probability',adverse),('inflated_claimed_lower_bound',bound)]:
  bad=deepcopy(original);mutate(bad)
  try:checker.verify_case(bad,sources[bad['id']],defaultdict(int))
  except (AssertionError,ValueError,IndexError):results.append({'mutation':name,'rejected':True})
  else:raise AssertionError('corrupted certificate accepted: '+name)
 for name,cases in [('empty_case_selection',[]),('truncated_case_selection',d['cases'][:-1])]:
  bad=deepcopy(d);bad['cases']=cases
  try:checker.check_selection(bad,catalog)
  except AssertionError:results.append({'mutation':name,'rejected':True})
  else:raise AssertionError('incomplete declared selection accepted: '+name)
 report={'status':'PASS','cases':results,'tests':len(results),'source_case':original['id'],
  'checker_sha256':hashlib.sha256(Path(checker.__file__).read_bytes()).hexdigest(),
  'report_sha256':hashlib.sha256((a.results/'report.json').read_bytes()).hexdigest()}
 (a.results/'mutation_checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
