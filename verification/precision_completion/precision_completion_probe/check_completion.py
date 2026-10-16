"""Solver-free verification of continuum precision-game completion.

This does not import the optimizer. Rational inequalities verify every cover
tree, every permitted failure pattern, and the matching adverse distribution.
"""
import argparse, hashlib, json, time
from pathlib import Path
from fractions import Fraction
from itertools import combinations

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]
F=Fraction; HALF=F(1,2)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,r):p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')

def check_selection(d,src):
 expected=sorted([r for r in src['plans'] if d['selection']=='all_full_panel' or not r['continuum_optimum_identified']],key=lambda r:r['id'])
 if d['selection']=='first_per_system':
  seen=set();selected=[]
  for r in expected:
   key=(r['cohort'],r['meter'])
   if key not in seen:seen.add(key);selected.append(r)
  expected=selected
 else:assert d['selection'] in ('all','all_full_panel')
 assert [r['id'] for r in d['cases']]==[r['id'] for r in expected], 'report does not contain its complete declared case selection'

def verify_case(case,source,counts):
 assert case['id']==source['id'] and case['fine_answers_loaded'] is False
 rows=[]
 for cc in source['original_c_binary64']:
  z=[F.from_float(v) for v in cc];a,b=min(z),max(z);assert b>a
  rows.append([(v-a)/(b-a) for v in z])
 assert [[str(v) for v in row] for row in rows]==case['normalized_coefficients_exact']==source['normalized_coefficients_exact']
 V=[]
 for q in combinations(range(1,6),2):
  ends=[0,*q,6];batch=[]
  for row in rows:
   c=[F(0)]*6
   for a,b in zip(ends,ends[1:]):
    for i in range(a,b):c[i]=max(row[a:b])-min(row[a:b])
   batch.append(c)
  V.append(batch)
 counts['source_coefficients']+=36
 pi=list(map(F,case['batch_weights']));mu=list(map(F,case['adverse_weights']))
 lower,upper=F(case['lower']),F(case['upper'])
 assert len(pi)==10 and sum(pi)==1 and min(pi)>=0
 points=[[F(z) for z in x] for x in case['profiles']]
 assert len(mu)==len(points) and min(mu)>=0 and sum(mu)==1
 S=[]
 for x in points:
  assert len(x)==6 and min(x)>=0 and sum(x)==1
  S.append([int(all(sum(v[i]*x[i] for i in range(6))<=HALF for v in batch)) for batch in V])
  counts['adverse_point_batch_evaluations']+=10
 expectations=[sum(mu[i]*S[i][q] for i in range(len(mu))) for q in range(10)]
 assert max(expectations)==upper
 def check_tree(tree,mask,selected):
  counts['proof_tree_nodes']+=1
  if tree['kind']=='infeasible':
   w=list(map(F,tree['lambda']))
   assert len(w)==len(selected) and w and min(w)>=0 and sum(w)==1
   for h in range(6):assert sum(a*V[q][r][h] for a,(q,r) in zip(w,selected))<=HALF
   counts['exact_dual_inequalities']+=6
  else:
   assert tree['kind']=='branch';q=tree['batch']
   assert mask>>q&1 and q not in [j for j,r in selected]
   branches=tree['branches']; indices=[b['row'] for b in branches]
   assert len(indices)==len(set(indices)) and all(0<=r<6 for r in indices)
   # Every possible failing contrast has a retained dominating branch.
   for r in range(6):
    assert any(all(V[q][r][h]<=V[q][s][h] for h in range(6)) for s in indices)
    counts['dominated_row_cover_checks']+=1
   for b in branches:check_tree(b['proof'],mask,selected+[(q,b['row'])])
 masks=[]
 for cert in case['cover_certificates']:
  mask=cert['failure_mask'];assert 0<mask<1024 and mask not in masks
  masks.append(mask);check_tree(cert['proof'],mask,[])
 # Enumerate ALL 2^10 possible sets of failing batches. Every set carrying
 # enough mixture mass to violate the lower guarantee contains a proved
 # infeasible subset. This check avoids trusting the optimizer's enumeration.
 for mask in range(1024):
  mass=sum(pi[q] for q in range(10) if mask>>q&1)
  if mass>1-lower:assert any(mask&m==m for m in masks)
  counts['failure_mass_patterns']+=1
 assert lower==upper and case['status']=='MATCHED_EXACT'
 assert F(source['precision_lower_exact'])<=lower<=F(source['precision_upper_exact'])
 if 'secondary' in case:
  width=max(sum(pi[q]*max(v[h] for v in V[q]) for q in range(10)) for h in range(6))
  assert width==F(case['secondary']['new_worst_expected_width'])
 counts['matched_continuum_optima']+=1

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--results',type=Path,default=HERE/'pilot')
 p.add_argument('--plans',type=Path,default=HERE/'inputs/precision_catalog.json')
 p.add_argument('--completed',type=Path,default=HERE/'all_418/report.json')
 a=p.parse_args();start=time.perf_counter();path=a.results/'report.json';d=json.loads(path.read_text());src=json.loads(a.plans.read_text())
 assert digest(a.plans)==d['input_sha256'] and d['threshold']=='1/2'
 assert d['batch_order']==[list(q) for q in combinations(range(1,6),2)]
 source={r['id']:r for r in src['plans']};assert len(source)==len(src['plans'])
 check_selection(d,src)
 if d['selection']=='all_full_panel':
  assert d['source_sha256']==digest(HERE/'refine_secondary.py')
  assert d['primary_source_sha256']==digest(HERE/'complete_precision.py')
  assert d['primary_completion_sha256']==digest(a.completed)
  complete=json.loads(a.completed.read_text());closed={r['id']:F(r['lower']) for r in complete['cases']}
  for r in d['cases']:
   expected=closed[r['id']] if r['id'] in closed else F(source[r['id']]['precision_lower_exact'])
   assert F(r['lower'])==F(r['upper'])==expected, 'secondary refinement changed primary precision value'
 else:assert d['source_sha256']==digest(HERE/'complete_precision.py'), 'producer source changed since this execution'
 counts={'source_coefficients':0,'adverse_point_batch_evaluations':0,'proof_tree_nodes':0,'exact_dual_inequalities':0,'dominated_row_cover_checks':0,'failure_mass_patterns':0,'matched_continuum_optima':0}
 ids=[]
 for case in d['cases']:
  assert case['id'] not in ids;ids.append(case['id'])
  if case['status']=='MATCHED_EXACT':verify_case(case,source[case['id']],counts)
 report={'status':'PASS','checks':counts,'total_cases':len(d['cases']),'unresolved_cases':len(d['cases'])-counts['matched_continuum_optima'],
  'scope':'Exact rational verification relative to the pinned normalized binary64-derived coefficients. No optimizer verdict is used. Upper profiles are feasible in the complete simplex; cover trees prove lower guarantees for every feasible record. Raw-source provenance is inherited from the pinned source catalog, not independently regenerated here.',
  'arithmetic':'Python fractions; zero numerical tolerance','fine_answers_loaded':False,'input_catalog_sha256':digest(a.plans),
  'producer_report_sha256':digest(path),'checker_sha256':digest(Path(__file__)),'elapsed_seconds':time.perf_counter()-start}
 dump(a.results/'independent_check.json',report);print(json.dumps(report,indent=2))

if __name__=='__main__':main()
