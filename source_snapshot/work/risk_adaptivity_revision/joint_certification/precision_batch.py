"""Coefficient-only precision-matched batch challenger and exact certificates.

Exact endpoints, no hourly cap or register error. Threshold remains one half
of the original paired widths. This does not assert general precision
optimality unless a full-domain lower guarantee matches an adverse upper.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import argparse,json,hashlib,time,os
import numpy as np
from scipy.optimize import linprog
HERE=Path(__file__).resolve().parent
BATCHES=list(combinations(range(1,6),2));H=F(1,2)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def profile_list():
 out=[]
 for i in range(6):x=[F(0)]*6;x[i]=1;out.append(x)
 for i,j in combinations(range(6),2):x=[F(0)]*6;x[i]=x[j]=H;out.append(x)
 out.append([F(1,6)]*6);return out
def vectors(C,Q):
 cuts=[0,*Q,6];out=[]
 for c in C:
  v=[]
  for lo,hi in zip(cuts,cuts[1:]):v += [max(c[lo:hi])-min(c[lo:hi])]*(hi-lo)
  out.append(v)
 return out
def multiplier(a,b):
 lo,hi=F(0),F(1)
 for aa,bb in zip(a,b):
  d=aa-bb;r=H-bb
  if d>0:hi=min(hi,r/d)
  elif d<0:lo=max(lo,r/d)
  elif r<0:return None
  if lo>hi:return None
 return (lo+hi)/2
def paircover(V,i,j):
 out=[]
 for r,a in enumerate(V[i]):
  for s,b in enumerate(V[j]):
   lam=multiplier(a,b)
   if lam is None:return None
   out.append({'first_contrast':r,'second_contrast':s,'lambda':str(lam)})
 return out
def evaluate(case,raw):
 C=[]
 for cc in raw:
  q=list(map(F.from_float,cc));span=max(q)-min(q);assert span>0;C.append([(v-min(q))/span for v in q])
 V=[vectors(C,Q) for Q in BATCHES];vertex=[[max(c[i] for c in v) for i in range(6)] for v in V]
 det=[q for q in range(10) if max(vertex[q])<=H];proof=[];selected=[];lower=F(0)
 if det:
  selected=[min(det,key=lambda q:(max(vertex[q]),sum(vertex[q])/6,q))];kind='deterministic_precision_guarantee';lower=F(1)
 else:
  candidates=[]
  for i,j in combinations(range(10),2):
   cert=paircover(V,i,j)
   if cert is not None:
    values=[(x+y)/2 for x,y in zip(vertex[i],vertex[j])]
    candidates.append(((max(values),sum(values)/6,i,j),cert))
  if candidates:
   key,proof=min(candidates,key=lambda v:v[0]);selected=list(key[-2:]);kind='certified_uniform_pair';lower=H
  else:kind='mean_width_fallback_no_positive_precision_guarantee'
 if selected:
  weights=[F(1,len(selected)) if i in selected else F(0) for i in range(10)]
 else:
  weights=[max(F(0),F.from_float(float(w))) for w in case['geometry']['randomized_batch_weights']];total=sum(weights);assert total>0;weights=[w/total for w in weights]
 profiles=profile_list();S=[[int(max(dot(c,x) for c in v)<=H) for v in V] for x in profiles]
 # A feasible adverse distribution upper-bounds every batch policy. No
 # sufficiency claim is made for vertices or this finite set of profiles.
 matrix=np.array(S,dtype=float);res=linprog(np.r_[np.zeros(22),1],A_ub=np.column_stack((matrix.T,-np.ones(10))),b_ub=np.zeros(10),A_eq=[np.r_[np.ones(22),0]],b_eq=[1],bounds=[(0,1)]*23,method='highs')
 assert res.success
 mu=[max(F(0),F(float(v)).limit_denominator(10**8)) for v in res.x[:22]];total=sum(mu);assert total>0;mu=[m/total for m in mu]
 expectations=[sum(m*S[i][j] for i,m in enumerate(mu)) for j in range(10)];upper=max(expectations);assert lower<=upper
 return {'id':case['id'],'cohort':case['cohort'],'meter':case['meter'],'pair_case_ids':case['pair_case_ids'],'original_c_binary64':raw,
  'normalized_coefficients_exact':[[str(x) for x in c] for c in C],'policy_kind':kind,'batch_weights':list(map(str,weights)),
  'selected_batches':[list(BATCHES[i]) for i in selected],'selected_indices':selected,'pair_cover_multipliers':proof,
  'precision_lower_exact':str(lower),'precision_upper_exact':str(upper),'certified_gap_exact':str(upper-lower),'continuum_optimum_identified':lower==upper,
  'adverse_profile_weights':list(map(str,mu)),'adverse_success_matrix':S,'batch_adverse_success':list(map(str,expectations))}
def summarize(rows):
 return {'cases':len(rows),'deterministic_guarantee':sum(r['policy_kind']=='deterministic_precision_guarantee' for r in rows),
  'certified_pair':sum(r['policy_kind']=='certified_uniform_pair' for r in rows),'fallback':sum(r['policy_kind'].startswith('mean_width') for r in rows),
  'matching_continuum_bounds':sum(r['continuum_optimum_identified'] for r in rows),
  'matching_half':sum(r['precision_lower_exact']==r['precision_upper_exact']=='1/2' for r in rows),
  'mean_certified_gap':sum(float(F(r['certified_gap_exact'])) for r in rows)/len(rows)}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plans',type=Path,default=HERE/'empirical_external_results/empirical_plans.json');p.add_argument('--cohort',choices=['original','external','all'],default='external');p.add_argument('--output-dir',type=Path,default=HERE/'precision_external_results');p.add_argument('--original-geometry',type=Path,nargs='+',help='Regenerated original-cohort geometry file(s), required when historical source files are unavailable.');a=p.parse_args()
 t=time.perf_counter();data=json.loads(a.plans.read_text());cases=[r for r in data['plans'] if a.cohort=='all' or r['cohort']==a.cohort]
 paths=[]
 if a.cohort in ('external','all'):paths.append(HERE.parent/'external_validation/replay/geometry.json')
 if a.cohort in ('original','all'):paths.extend(a.original_geometry or [HERE.parent/'counter_adaptive/pilot/geometry.json',HERE.parent/'counter_adaptive/continuation/geometry.json'])
 source={};hashes={}
 for path in paths:
  hashes[os.path.relpath(path,HERE.parent).replace('\\','/')]=sha(path)
  for r in json.loads(path.read_text())['cases']:source[r['id']]=r
 results=[];a.output_dir.mkdir(parents=True,exist_ok=True)
 for i,case in enumerate(cases,1):
  results.append(evaluate(case,[source[key]['c'] for key in case['pair_case_ids']]))
  if i%100==0:print(json.dumps({'processed':i,'total':len(cases),'seconds':time.perf_counter()-t}),flush=True)
 plans={'status':'PASS','source_hashes':hashes,'input_plan_sha256':sha(a.plans),'profiles':[[str(x) for x in v] for v in profile_list()],
  'query_batches':[list(Q) for Q in BATCHES],'threshold':'1/2','scope':'Exact uncapped endpoints and prefixes; no stored-reading errors. Coefficient-only policy; fine answers are not loaded. Pair-cover lower bounds hold on the entire simplex; finite-profile distributions provide upper bounds only.',
  'policy_rule':'First use a deterministic batch with full half-width guarantee, tied by smallest worst then mean vertex joint width and index. Otherwise use a certified equal pair, tied by smallest worst then mean vertex joint width and lexicographic pair. If no pair certificate exists, retain the saved mean-width-optimal mixture with only the trivial precision lower bound zero.',
  'plans':results,'fine_answers_loaded':False,'source_sha256':sha(Path(__file__))}
 dump(a.output_dir/'plans.json',plans)
 report={'status':'PASS','summary':{cohort:summarize([r for r in results if r['cohort']==cohort]) for cohort in sorted({r['cohort'] for r in results})},'plan_sha256':sha(a.output_dir/'plans.json'),'elapsed_seconds':time.perf_counter()-t,'new_fits':0,'new_network_calls':0,'fine_answers_loaded':False}
 dump(a.output_dir/'report.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
