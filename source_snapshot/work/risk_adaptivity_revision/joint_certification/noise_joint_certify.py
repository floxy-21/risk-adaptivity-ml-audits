"""Rigorous fixed-policy joint-width sensitivity: caps and fixed readout errors.

Uses existing all-block plans, no fine-resolution answers. Policies are frozen
from exact rational normalized contrast geometry before robust evaluation.
The noisy/capped adaptive policy is not asserted globally optimal.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
from collections import Counter
import argparse,json,time,hashlib
import numpy as np
from scipy.optimize import linprog
HERE=Path(__file__).resolve().parent
BATCHES=list(combinations(range(1,6),2))
SCENARIOS={'exact':(F(0),F(1)),'error_1pct':(F(1,100),F(1)),
 'cap_half':(F(0),F(1,2)),'cap_third':(F(0),F(1,3)),
 'cap_half_error_1pct':(F(1,100),F(1,2)),'cap_third_error_1pct':(F(1,100),F(1,3))}
OPTIONS={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n')
def span(c,a,b):return max(c[a:b])-min(c[a:b])
def lines(C,k,j):
 out=[]
 for c in C:
  if j<k:l=max(span(c,0,j),span(c,j,k));r=span(c,k,6)
  else:l=span(c,0,k);r=max(span(c,k,j),span(c,j,6))
  out.append((l-r,r))
 return out
def policy(C,k):
 all_lines={j:lines(C,k,j) for j in range(1,6) if j!=k}
 flat=[v for ll in all_lines.values() for v in ll];points={F(0),F(1)}
 for (a,b),(c,d) in combinations(flat,2):
  if a!=c:
   t=(d-b)/(a-c)
   if 0<t<1:points.add(t)
 p=sorted(points);segments=[]
 for lo,hi in zip(p,p[1:]):
  t=(lo+hi)/2;j=min((max(a*t+b for a,b in ll),j) for j,ll in all_lines.items())[1]
  if segments and segments[-1]['second']==j:segments[-1]['hi']=hi
  else:segments.append({'lo':lo,'hi':hi,'second':j})
 return segments

def capacity_policy(plan):
 """Freeze the previously computed capped planner's piecewise action rule.

 Binary64 line parameters define this executable rule exactly; its noisy
 certificate still uses the original exactly normalized forecast contrasts.
 """
 first=plan['firsts'][plan['first_query']-1];segments=[]
 for cell in first['intervals']:
  lo,hi=F.from_float(cell['lo']),F.from_float(cell['hi'])
  ll={j:[(F.from_float(a),F.from_float(b)) for a,b in lines] for j,lines in zip(first['seconds'],cell['lines'])}
  flat=[v for lines in ll.values() for v in lines];points={lo,hi}
  for (a,b),(c,d) in combinations(flat,2):
   if a!=c:
    t=(d-b)/(a-c)
    if lo<t<hi:points.add(t)
  pts=sorted(points)
  for low,high in zip(pts,pts[1:]):
   mid=(low+high)/2;j=min((max(a*mid+b for a,b in lines),j) for j,lines in ll.items())[1]
   if segments and segments[-1]['second']==j:segments[-1]['hi']=high
   else:segments.append({'lo':low,'hi':high,'second':j})
 assert segments
 # Outside the capped noiseless first-answer range, extend its endpoint
 # action. Sensitivity LPs later restrict to the actual cap/error range.
 segments[0]['lo']=F(0);segments[-1]['hi']=F(1)
 assert all(a['hi']==b['lo'] for a,b in zip(segments,segments[1:]))
 return segments

def select_second(plan,answer,delta,cap=F(1)):
 """Execute the exported policy; choose the first matching closed interval."""
 t=F(answer);delta=F(delta);cap=F(cap);k=int(plan['first_query'])
 lo=max(F(0),1-(6-k)*cap)-delta;hi=min(F(1),k*cap)+delta
 if not lo<=t<=hi:raise ValueError('First answer is outside the declared model')
 clamped=max(F(0),min(F(1),t))
 for branch in plan['branches']:
  if F(branch['lo'])<=clamped<=F(branch['hi']):return int(branch['second'])
 raise AssertionError('Exported policy does not cover this answer')

def matrix(cap,delta,Q,k=None,interval=None):
 n=12+(k is not None);A=[];b=[];H=[];h=[]
 for offset in [0,6]:
  r=[F(0)]*n;r[offset:offset+6]=[F(1)]*6;H.append(r);h.append(F(1))
 for q in Q:
  if q==k:continue
  r=[F(0)]*n;r[:q]=[F(1)]*q;r[6:6+q]=[F(-1)]*q
  A.extend([r,[-v for v in r]]);b.extend([2*delta]*2)
 bounds=[(F(0),cap)]*12
 if k is not None:
  lo,hi=interval;bounds.append((lo,hi))
  for offset in [0,6]:
   r=[F(0)]*n;r[offset:offset+k]=[F(1)]*k;r[12]=F(-1)
   A.extend([r,[-v for v in r]]);b.extend([delta]*2)
 return A,b,H,h,bounds

def solve_bound(c,model,witness=False):
 A,b,H,h,bounds=model;n=len(bounds);f=[-v for v in c]+list(c)+([F(0)] if n==13 else [])
 s=linprog(np.array(f,dtype=float),A_ub=np.array(A,dtype=float) if A else None,b_ub=np.array(b,dtype=float) if b else None,
  A_eq=np.array(H,dtype=float),b_eq=np.array(h,dtype=float),bounds=[(float(l),float(u)) for l,u in bounds],method='highs',options=OPTIONS)
 if not s.success:raise RuntimeError(s.message)
 lam=[min(F(0),F.from_float(float(v))) for v in s.ineqlin.marginals]
 nu=[F.from_float(float(v)) for v in s.eqlin.marginals]
 residual=[f[i]-sum(v*r[i] for v,r in zip(lam,A))-sum(v*r[i] for v,r in zip(nu,H)) for i in range(n)]
 lower=sum(v*x for v,x in zip(lam,b))+sum(v*x for v,x in zip(nu,h))+sum(min(r*l,r*u) for r,(l,u) in zip(residual,bounds))
 upper=-lower
 cert={'upper_exact':str(upper),'ineq_multipliers':list(map(str,lam)),'eq_multipliers':list(map(str,nu))}
 feasible=None
 if witness:
  x=[F(float(v)).limit_denominator(10**8) for v in s.x]
  if all(l<=v<=u for v,(l,u) in zip(x,bounds)) and all(sum(v*z for v,z in zip(r,x))<=bb for r,bb in zip(A,b)) and all(sum(v*z for v,z in zip(r,x))==hh for r,hh in zip(H,h)):
   value=-sum(v*z for v,z in zip(f,x));feasible={'width_exact':str(value),'endpoints':list(map(str,x[:12]))}
 return upper,cert,feasible,abs(float(upper)+float(s.fun))

def evaluate(case,name,C,segments):
 delta,cap=SCENARIOS[name];k=case['geometry']['first_query'];branch_results=[];max_discrepancy=0.;solves=0
 firstlo=max(F(0),1-(6-k)*cap)-delta;firsthi=min(F(1),k*cap)+delta
 for index,seg in enumerate(segments):
  lo=max(firstlo,seg['lo'] if index else -delta)
  hi=min(firsthi,seg['hi'] if index<len(segments)-1 else 1+delta)
  if lo>hi:continue
  j=seg['second'];m=matrix(cap,delta,(k,j),k,(lo,hi));certs=[]
  for r,c in enumerate(C):
   up,cert,_,err=solve_bound(c,m);solves+=1;max_discrepancy=max(max_discrepancy,err)
   cert['contrast']=r;certs.append(cert)
  branch_results.append({'lo':str(lo),'hi':str(hi),'second':j,'contrast_certificates':certs})
 A=max(F(c['upper_exact']) for row in branch_results for c in row['contrast_certificates'])
 batches=[]
 for Q in BATCHES:
  m=matrix(cap,delta,Q);upper=[];witnesses=[]
  for r,c in enumerate(C):
   up,cert,w,err=solve_bound(c,m,True);solves+=1;max_discrepancy=max(max_discrepancy,err);upper.append(up)
   if w:w['contrast']=r;witnesses.append(w)
  best=max(witnesses,key=lambda w:F(w['width_exact'])) if witnesses else None
  batches.append({'Q':list(Q),'upper_exact':str(max(upper)),'lower_exact':best['width_exact'] if best else None,'lower_witness':best})
 Dupper=min(F(b['upper_exact']) for b in batches)
 Dlower=min(F(b['lower_exact']) for b in batches) if all(b['lower_exact'] is not None for b in batches) else None
 fail=all(b['lower_exact'] is not None and F(b['lower_exact'])>F(1,2) for b in batches)
 positive=A<=F(1,2) and fail
 witnesses=[]
 if positive:
  for b in batches:
   w=b['lower_witness'];x=list(map(F,w['endpoints'][:6]));v=list(map(F,w['endpoints'][6:]));errors=[F(0)]*5
   for q in b['Q']:errors[q-1]=(sum(v[:q])-sum(x[:q]))/2
   assert max(map(abs,errors))<=delta
   witnesses.append({'failing_batch':b['Q'],'record_x':list(map(str,x)),'fixed_errors':list(map(str,errors)),**w})
 row={'id':case['id'],'cohort':case['cohort'],'meter':case['meter'],'scenario':name,'error':str(delta),'cap':str(cap),'first_query':k,
  'frozen_adaptive_upper':float(A),'frozen_adaptive_upper_exact':str(A),
  'best_det_batch_upper':float(Dupper),'best_det_batch_lower':float(Dlower) if Dlower is not None else None,
  'adaptive_half_guarantee':A<=F(1,2),'det_batch_half_guarantee':Dupper<=F(1,2),
  'every_batch_fails_half_exact':fail,'certified_adaptive_vs_all_randomized_batch_precision':positive,
  'randomized_batch_success_upper_if_separated':'9/10' if positive else None,'branches':len(branch_results),'lp_solves':solves,
  'max_rational_upper_vs_float_gap':max_discrepancy}
 certificate={'id':case['id'],'scenario':name,'normalized_coefficients':[[str(v) for v in c] for c in C],
  'error':str(delta),'cap':str(cap),'first_query':k,'branches':branch_results,'adverse_records':witnesses,
  'precision_separation':positive,'batch_bounds':batches,'batch_success_upper':'9/10' if positive else None,'argument':'Uniform distribution on ten fixed latent records: each corresponding batch fails on its own atom; hence every batch mixture has success at most9/10 on average. Adaptive branch dual certificates bound all completions by1/2.'}
 return row,certificate

def summary(rows):
 return {'cases':len(rows),'adaptive_half_guarantees':sum(r['adaptive_half_guarantee'] for r in rows),
  'det_batch_half_guarantees':sum(r['det_batch_half_guarantee'] for r in rows),
  'adaptive_vs_all_randomized_precision_separations':sum(r['certified_adaptive_vs_all_randomized_batch_precision'] for r in rows),
  'mean_frozen_adaptive_upper':float(np.mean([r['frozen_adaptive_upper'] for r in rows])),
  'mean_best_det_batch_upper':float(np.mean([r['best_det_batch_upper'] for r in rows])),
  'max_exact_upper_correction':max(r['max_rational_upper_vs_float_gap'] for r in rows),'lp_solves':sum(r['lp_solves'] for r in rows)}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plans',type=Path,default=HERE/'empirical_external_results/empirical_plans.json')
 p.add_argument('--cohort',choices=['external','original','all'],default='external')
 p.add_argument('--scenarios',nargs='+',choices=list(SCENARIOS),default=['exact','error_1pct','cap_half','cap_third'])
 p.add_argument('--limit',type=int);p.add_argument('--output-dir',type=Path,default=HERE/'noise_external_results')
 p.add_argument('--capacity-plans',type=Path);a=p.parse_args()
 t=time.perf_counter();plan_bytes=a.plans.read_bytes();plans=json.loads(plan_bytes)['plans'];cases=[c for c in plans if a.cohort=='all' or c['cohort']==a.cohort]
 if a.limit is not None:cases=cases[:a.limit]
 a.output_dir.mkdir(parents=True,exist_ok=True);rows=[];certificates=[]
 source_paths=[]
 if a.cohort in ('external','all'):source_paths.append(HERE.parent/'external_validation/replay/geometry.json')
 if a.cohort in ('original','all'):source_paths.extend([HERE.parent/'counter_adaptive/pilot/geometry.json',HERE.parent/'counter_adaptive/continuation/geometry.json'])
 source_rows={};source_hashes={}
 for path in source_paths:
  data=path.read_bytes();source_hashes[str(path.relative_to(HERE.parent))]=hashlib.sha256(data).hexdigest()
  for r in json.loads(data)['cases']:source_rows[r['id']]=r
 capplans={};cap_hash=None
 if a.capacity_plans:
  assert len(a.scenarios)==1
  targetcap=str(SCENARIOS[a.scenarios[0]][1]);capbytes=a.capacity_plans.read_bytes();cap_hash=hashlib.sha256(capbytes).hexdigest()
  capplans={r['id']:r for r in json.loads(capbytes)['plans'] if r['cap_fraction']==targetcap}
 policies=[];prepared=[]
 for case in cases:
  raw=[source_rows[key]['c'] for key in case['pair_case_ids']]
  C=[]
  for cc in raw:
   q=list(map(F.from_float,cc));ran=max(q)-min(q);assert ran>0
   C.append([(v-min(q))/ran for v in q])
  assert max(abs(float(v)-w) for q,qq in zip(C,case['geometry']['normalized_coefficients']) for v,w in zip(q,qq))<1e-12
  if capplans:
   case=dict(case);case['geometry']=dict(case['geometry']);case['geometry']['first_query']=capplans[case['id']]['first_query']
   segs=capacity_policy(capplans[case['id']])
  else:segs=policy(C,case['geometry']['first_query'])
  exported={'id':case['id'],'cohort':case['cohort'],'meter':case['meter'],'first_query':case['geometry']['first_query'],
   'pair_case_ids':case['pair_case_ids'],'original_c_binary64':raw,
   'normalized_coefficients_exact':[[str(v) for v in q] for q in C],
   'branches':[{'lo':str(b['lo']),'hi':str(b['hi']),'second':b['second']} for b in segs],
   'execution':'Clamp a model-consistent first answer to[0,1], then take the first matching closed interval; no isolated-tie action is substituted.'}
  policies.append(exported);prepared.append((case,C,segs))
 dump(a.output_dir/'frozen_policies.json',{'source_hashes':source_hashes,'source_plan_sha256':hashlib.sha256(plan_bytes).hexdigest(),'capacity_plan_sha256':cap_hash,'fine_answers_loaded':False,'policies':policies})
 for num,(case,C,segs) in enumerate(prepared,1):
  for name in a.scenarios:
   row,cert=evaluate(case,name,C,segs);rows.append(row)
   if cert:certificates.append(cert)
   if name=='exact':assert abs(row['frozen_adaptive_upper']-case['geometry']['adaptive_deterministic_guarantee'])<1e-8
  if num%20==0:print(json.dumps({'processed':num,'of':len(cases),'seconds':time.perf_counter()-t}),flush=True)
 report={'status':'PASS','cohort':a.cohort,'cases':len(cases),'scenarios':a.scenarios,
  'summary':{name:summary([r for r in rows if r['scenario']==name]) for name in a.scenarios},
  'by_meter':{meter:{name:summary([r for r in rows if r['scenario']==name and r['meter']==meter]) for name in a.scenarios} for meter in sorted({r['meter'] for r in rows})},
  'scope':'All selected frozen blocks, six shared contrasts, two total prefix queries. Original half-width threshold and exact endpoints. Fixed coefficient-derived policy; no global noisy/capped adaptive optimality. Exact rational LP-dual residual corrections and feasible batch endpoints. Exact rational normalization of original source binary64 contrast coefficients defines every checked instance.',
  'policy':'Use saved noiseless first query; compute all-line intervals from exact source-normalized coefficients, extend endpoint branches, dispatch first matching closed interval. Export all frozen policies before sensitivity calculations and without loading fine answers.',
  'profile_lower_bound':'All-randomized precision upper9/10 only when ten feasible endpoint witnesses prove every deterministic batch fails; no vertex-exactness assumption.',
  'input_sha256':hashlib.sha256(plan_bytes).hexdigest(),'coefficient_source_hashes':source_hashes,'frozen_policies_sha256':sha(a.output_dir/'frozen_policies.json'),'checker_source_sha256':sha(Path(__file__)),
  'capacity_plan_sha256':cap_hash,'policy_origin':'Previously computed coefficient-only capped noiseless planner' if cap_hash else 'Original uncapped noiseless planner',
  'new_network_calls':0,'new_fits':0,'fine_answers_loaded':False,'elapsed_seconds':time.perf_counter()-t}
 dump(a.output_dir/'cases.json',rows);dump(a.output_dir/'certificates.json',certificates);dump(a.output_dir/'report.json',report)
 print(json.dumps(report['summary'],indent=2),flush=True)
if __name__=='__main__':main()

