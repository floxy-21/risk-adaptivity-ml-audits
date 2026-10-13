"""Solver-free exact verification of precision-matched batch certificates."""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import argparse,json,hashlib,time
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=HERE/'precision_external_results');a=p.parse_args();t=time.perf_counter()
 path=a.directory/'plans.json';d=json.loads(path.read_text());Q=list(combinations(range(1,6),2));assert d['query_batches']==[list(q) for q in Q] and d['threshold']=='1/2'
 records={}
 for rel,h in d['source_hashes'].items():
  source=HERE.parent/rel.replace(chr(92),'/');assert source.exists() and sha(source)==h
  for r in json.loads(source.read_text())['cases']:records[r['id']]=r
 profiles=[list(map(F,x)) for x in d['profiles']];assert len(profiles)==22
 assert all(len(v)==6 and sum(v)==1 and min(v)>=0 for v in profiles)
 checks={'cases':0,'pair_cover_multipliers':0,'finite_profile_batch_evaluations':0,'matching_continuum_bounds':0};summary={}
 for row in d['plans']:
  raw=[records[key]['c'] for key in row['pair_case_ids']];assert raw==row['original_c_binary64']
  C=[]
  for rawc in raw:
   c=list(map(F.from_float,rawc));lo,hi=min(c),max(c);assert hi>lo;C.append([(v-lo)/(hi-lo) for v in c])
  assert [[str(v) for v in c] for c in C]==row['normalized_coefficients_exact']
  V=[]
  for q in Q:
   cuts=[0,*q,6];VV=[]
   for c in C:
    v=[F(0)]*6
    for l,u in zip(cuts,cuts[1:]):
     for i in range(l,u):v[i]=max(c[l:u])-min(c[l:u])
    VV.append(v)
   V.append(VV)
  weights=list(map(F,row['batch_weights']));assert len(weights)==10 and min(weights)>=0 and sum(weights)==1
  chosen=row['selected_indices'];assert row['selected_batches']==[list(Q[i]) for i in chosen]
  kind=row['policy_kind'];lower=F(row['precision_lower_exact'])
  if kind=='deterministic_precision_guarantee':
   assert len(chosen)==1 and weights[chosen[0]]==1 and lower==1
   assert max(v for c in V[chosen[0]] for v in c)<=F(1,2)
   assert not row['pair_cover_multipliers']
  elif kind=='certified_uniform_pair':
   assert len(chosen)==2 and len(set(chosen))==2 and lower==F(1,2)
   assert all(weights[i]==F(1,2) for i in chosen)
   certs=row['pair_cover_multipliers'];assert {(c['first_contrast'],c['second_contrast']) for c in certs}==set((r,s) for r in range(6) for s in range(6)) and len(certs)==36
   for c in certs:
    lam=F(c['lambda']);assert 0<=lam<=1;a1=V[chosen[0]][c['first_contrast']];a2=V[chosen[1]][c['second_contrast']]
    assert all(lam*x+(1-lam)*y<=F(1,2) for x,y in zip(a1,a2));checks['pair_cover_multipliers']+=1
  else:assert kind=='mean_width_fallback_no_positive_precision_guarantee' and lower==0 and not chosen and not row['pair_cover_multipliers']
  S=[]
  for x in profiles:
   S.append([int(max(sum(cc*xx for cc,xx in zip(c,x)) for c in vv)<=F(1,2)) for vv in V]);checks['finite_profile_batch_evaluations']+=10
  assert S==row['adverse_success_matrix']
  mu=list(map(F,row['adverse_profile_weights']));assert len(mu)==22 and min(mu)>=0 and sum(mu)==1
  vals=[sum(mu[i]*S[i][j] for i in range(22)) for j in range(10)];upper=max(vals)
  assert list(map(str,vals))==row['batch_adverse_success'] and upper==F(row['precision_upper_exact'])
  assert lower<=upper and upper-lower==F(row['certified_gap_exact']) and (lower==upper)==row['continuum_optimum_identified']
  checks['cases']+=1;checks['matching_continuum_bounds']+=lower==upper
  s=summary.setdefault(row['cohort'],{'cases':0,'deterministic_guarantee':0,'certified_pair':0,'fallback':0,'matching_continuum_bounds':0,'matching_half':0,'sum_gap':F(0)})
  s['cases']+=1;s['deterministic_guarantee']+=kind=='deterministic_precision_guarantee';s['certified_pair']+=kind=='certified_uniform_pair';s['fallback']+=kind.startswith('mean_width');s['matching_continuum_bounds']+=lower==upper;s['matching_half']+=lower==upper==F(1,2);s['sum_gap']+=upper-lower
 for s in summary.values():s['mean_certified_gap']=float(s.pop('sum_gap')/s['cases'])
 report={'status':'PASS','checks':checks,'summary':summary,'scope':'Full-simplex deterministic and pair-cover lower guarantees; exact feasible finite-profile adversarial upper bounds. Equality is claimed only where these match. No statement of finite-profile sufficiency or precision optimality elsewhere. Same-study independent checker, not external verification.','plan_sha256':sha(path),'source_sha256':sha(Path(__file__)),'elapsed_seconds':time.perf_counter()-t}
 (a.directory/'independent_check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
