"""Continuum precision-game completion with rational cover proof trees.

The floating-point LP proposes primal/dual witnesses. Only exact rational
inequalities establish feasibility, infeasibility, or matching game bounds.
No hidden fine-resolution target answers are read.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import argparse, hashlib, json, time
import numpy as np
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
Q=list(combinations(range(1,6),2)); HALF=F(1,2)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def write(p,d): p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf8')
def vectors(C):
 out=[]
 for q in Q:
  cuts=(0,*q,6); rows=[]
  for c in C:
   v=[]
   for a,b in zip(cuts,cuts[1:]):v.extend([max(c[a:b])-min(c[a:b])]*(b-a))
   rows.append(v)
  out.append(rows)
 return out

def solve_exact(A,b,n):
 """RREF; set free variables to zero. None means inconsistent."""
 a=[list(row)+[rhs] for row,rhs in zip(A,b)]; piv=[];r=0
 for j in range(n):
  k=next((k for k in range(r,len(a)) if a[k][j]),None)
  if k is None:continue
  a[r],a[k]=a[k],a[r];z=a[r][j];a[r]=[v/z for v in a[r]]
  for k in range(len(a)):
   if k!=r and a[k][j]:
    z=a[k][j];a[k]=[v-z*w for v,w in zip(a[k],a[r])]
  piv.append(j);r+=1
  if r==len(a):break
 if any(not any(row[:n]) and row[n] for row in a):return None
 x=[F(0)]*n
 for k,j in enumerate(piv):x[j]=a[k][n]
 return x

class Oracle:
 def __init__(self,V,deadline):
  self.V=V;self.deadline=deadline;self.nodes=0;self.lp=0;self.duals=0
  self.cache={};self.nondom=[]
  for rows in V:
   keep=[]
   for r,v in enumerate(rows):
    if not any(s!=r and all(a<=b for a,b in zip(v,w)) and
               (v!=w or s<r) for s,w in enumerate(rows)):keep.append(r)
   self.nondom.append(keep)

 def dual(self,rows,res):
  lam=[max(F(0),F(float(-z)).limit_denominator(10**8)) for z in res.ineqlin.marginals]
  if sum(lam):
   lam=[z/sum(lam) for z in lam]
   if max(sum(l*v[i] for l,v in zip(lam,rows)) for i in range(6))<=HALF:return lam
  support=[i for i,z in enumerate(res.ineqlin.marginals) if -z>1e-8]
  if not support:return None
  selected=[rows[i] for i in support]
  # A positive primal coordinate identifies a tight dual column.
  active=[i for i,z in enumerate(res.x[:6]) if z>1e-8]
  if not active:return None
  A=[[F(1)]*len(support)];b=[F(1)]
  for i in active[1:]:A.append([v[i]-v[active[0]] for v in selected]);b.append(F(0))
  sol=solve_exact(A,b,len(support))
  if sol is None or min(sol)<0 or sum(sol)!=1:return None
  lam=[F(0)]*len(rows)
  for i,z in zip(support,sol):lam[i]=z
  if max(sum(l*v[i] for l,v in zip(lam,rows)) for i in range(6))<=HALF:return lam
  return None

 def point(self,rows,res):
  for den in [10**8,10**12,10**16]:
   x=[max(F(0),F(float(z)).limit_denominator(den)) for z in res.x[:6]]
   if not sum(x):continue
   x=[z/sum(x) for z in x]
   if min(dot(v,x) for v in rows)>HALF:return x
  # Recover a rational primal vertex if the strict margin is very small.
  A=[[F(1)]*6+[F(0)]]; b=[F(1)]
  for i,z in enumerate(res.x[:6]):
   if abs(z)<1e-9:A.append([F(int(i==j)) for j in range(6)]+[F(0)]);b.append(F(0))
  for v,slack in zip(rows,res.ineqlin.residual):
   if abs(slack)<1e-8:A.append(v+[F(-1)]);b.append(HALF)
  sol=solve_exact(A,b,7)
  if sol is not None and min(sol[:6])>=0 and sum(sol[:6])==1 and min(dot(v,sol[:6]) for v in rows)>HALF:return sol[:6]
  return None

 def feasible(self,mask):
  """Either a strict-failure record or a complete cover proof tree."""
  def dfs(selected):
   if time.perf_counter()>self.deadline:raise TimeoutError('case time limit')
   self.nodes+=1; rows=[self.V[q][r] for q,r in selected]
   if rows:
    self.lp+=1
    res=linprog([0.]*6+[-1.],A_ub=[[-float(v) for v in row]+[1.] for row in rows],
        b_ub=[-.5]*len(rows),A_eq=[[1.]*6+[0.]],b_eq=[1.],
        bounds=[(0,None)]*6+[(None,None)],method='highs',
        options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    assert res.success,res.message
    x=self.point(rows,res) if res.x[6]>-1e-8 else None
    if x is None:
     lam=self.dual(rows,res)
     if lam is None:raise ArithmeticError('LP decision lacks an exact rational witness')
     self.duals+=1
     return None,{'kind':'infeasible','lambda':list(map(str,lam))}
   else:x=[F(1,6)]*6
   missing=[q for q in range(10) if mask>>q&1 and max(dot(v,x) for v in self.V[q])<=HALF]
   if not missing:return x,None
   used={q for q,r in selected};assert not set(missing)&used
   q=min(missing,key=lambda q:(len(self.nondom[q]),q))
   branches=[]
   for r in self.nondom[q]:
    point,cert=dfs(selected+[(q,r)])
    if point is not None:return point,None
    branches.append({'row':r,'proof':cert})
   return None,{'kind':'branch','batch':q,'branches':branches}
  if mask in self.cache:return self.cache[mask]
  answer=dfs([]);self.cache[mask]=answer;return answer

def pattern(V,x):return [int(max(dot(v,x) for v in rows)<=HALF) for rows in V]

def finite_game(S):
 mat=np.array(S,dtype=float)
 p=linprog(np.r_[np.zeros(10),-1.],A_ub=np.column_stack((-mat,np.ones(len(S)))),b_ub=np.zeros(len(S)),
   A_eq=[np.r_[np.ones(10),0]],b_eq=[1.],bounds=[(0,1)]*11,method='highs')
 d=linprog(np.r_[np.zeros(len(S)),1.],A_ub=np.column_stack((mat.T,-np.ones(10))),b_ub=np.zeros(10),
   A_eq=[np.r_[np.ones(len(S)),0]],b_eq=[1.],bounds=[(0,1)]*(len(S)+1),method='highs')
 assert p.success and d.success
 pi=[max(F(0),F(float(v)).limit_denominator(10**6)) for v in p.x[:10]];pi=[v/sum(pi) for v in pi]
 mu=[max(F(0),F(float(v)).limit_denominator(10**6)) for v in d.x[:-1]];mu=[v/sum(mu) for v in mu]
 lower=min(dot(pi,row) for row in S)
 upper=max(sum(w*S[i][q] for i,w in enumerate(mu)) for q in range(10))
 return pi,mu,lower,upper

def bad_subsets(pi,lower):
 support=[q for q in range(10) if pi[q]]; result=[]
 for size in range(1,len(support)+1):
  for qs in combinations(support,size):
   mass=sum(pi[q] for q in qs)
   if mass<=1-lower:continue
   if all(mass-pi[q]<=1-lower for q in qs):result.append(sum(1<<q for q in qs))
 return result

def complete(row,seconds):
 start=time.perf_counter();C=[[F(z) for z in c] for c in row['normalized_coefficients_exact']];V=vectors(C)
 oracle=Oracle(V,start+seconds)
 profiles=[]
 for i in range(6):profiles.append([F(int(i==j)) for j in range(6)])
 for i,j in combinations(range(6),2):profiles.append([F(int(k in (i,j)),2) for k in range(6)])
 profiles.append([F(1,6)]*6)
 history=[];certificates=[];closed=False;error=None
 pi=[F(1,10)]*10;mu=[];lower=F(0);upper=F(row['precision_upper_exact'])
 try:
  # A single strict all-failure record proves value zero immediately.
  all_point,all_proof=oracle.feasible((1<<10)-1)
  if all_point is not None:profiles.append(all_point)
  for iteration in range(50):
   S=[pattern(V,x) for x in profiles]
   pi,mu,lower,upper=finite_game(S)
   history.append({'iteration':iteration,'profiles':len(profiles),'finite_lower':str(lower),'finite_upper':str(upper)})
   certificates=[];new_point=None
   for mask in bad_subsets(pi,lower):
    point,proof=oracle.feasible(mask)
    if point is not None:
     assert dot(pi,pattern(V,point))<lower
     new_point=point;profiles.append(point);break
    certificates.append({'failure_mask':mask,'proof':proof})
   if new_point is None:
    closed=lower==upper;break
  else:raise TimeoutError('iteration limit')
 except (TimeoutError,ArithmeticError) as exc:error=str(exc)
 if error:
  lower=F(row['precision_lower_exact']);certificates=[]
  pi=list(map(F,row['batch_weights']))
  # Never present the most recent unverified candidate as the fallback.
  # Open cases currently have lower zero; their original saved policy is
  # retained with exactly its already certified lower guarantee.
  if mu:profiles=profiles[:len(mu)]
  else:
   profiles=profiles[:22];mu=list(map(F,row['adverse_profile_weights']))
   upper=F(row['precision_upper_exact'])
 result={'id':row['id'],'cohort':row['cohort'],'meter':row['meter'],
  'status':'MATCHED_EXACT' if closed else 'UNRESOLVED','error':error,
  'old_lower':row['precision_lower_exact'],'old_upper':row['precision_upper_exact'],
  'lower':str(lower),'upper':str(upper),'batch_weights':list(map(str,pi)),
  'profiles':[[str(z) for z in x] for x in profiles],
  'adverse_weights':list(map(str,mu)),'cover_certificates':certificates,
  'normalized_coefficients_exact':row['normalized_coefficients_exact'],
  'coefficient_sha256':hashlib.sha256(json.dumps(row['normalized_coefficients_exact'],separators=(',',':')).encode()).hexdigest(),
  'history':history,'LPs':oracle.lp,'tree_nodes':oracle.nodes,'exact_dual_leaves':oracle.duals,
  'seconds':time.perf_counter()-start,'fine_answers_loaded':False}
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--plans',type=Path,default=HERE/'inputs/precision_catalog.json')
 p.add_argument('--output-dir',type=Path,default=HERE/'pilot')
 p.add_argument('--selection',choices=['first_per_system','all'],default='first_per_system')
 p.add_argument('--seconds-per-case',type=float,default=120.)
 a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True);d=json.loads(a.plans.read_text())
 rows=sorted([r for r in d['plans'] if not r['continuum_optimum_identified']],key=lambda r:r['id'])
 if a.selection=='first_per_system':
  seen=set();chosen=[]
  for row in rows:
   key=(row['cohort'],row['meter'])
   if key not in seen:seen.add(key);chosen.append(row)
  rows=chosen
 report={'protocol_date':'2026-10-15','selection':a.selection,'input_sha256':sha(a.plans),
  'source_sha256':sha(Path(__file__)),'threshold':'1/2','batch_order':[list(q) for q in Q],
  'fine_answers_loaded':False,'LP_tolerances':{'primal':1e-9,'dual':1e-9},'cases':[]}
 for row in rows:
  result=complete(row,a.seconds_per_case);report['cases'].append(result)
  write(a.output_dir/'report.json',report)
  print(json.dumps({k:result[k] for k in ['id','status','old_upper','lower','upper','LPs','seconds','error']}),flush=True)
 report['status']='PASS' if all(r['status']=='MATCHED_EXACT' for r in report['cases']) else 'PARTIAL'
 report['closed']=sum(r['status']=='MATCHED_EXACT' for r in report['cases']);write(a.output_dir/'report.json',report)

if __name__=='__main__':main()
