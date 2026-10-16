"""Coefficient-only width refinement on the exact precision-optimal face.

All 1,098 cases use the same rule. Zero precision value retains the existing
coefficient-only mean-width mixture. Positive values receive a constrained
mean-width LP with deterministic lexicographic numerical ties. Exact rational
cover trees recheck precision after every proposed policy change. Secondary
width optimality is numerical; the primary precision value is exact.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import argparse,hashlib,json,time
import numpy as np
from scipy.optimize import linprog
import complete_precision as primary

HERE=Path(__file__).resolve().parent;HALF=F(1,2)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf8')

def old_case(row):
 profiles=[]
 for i in range(6):profiles.append([F(int(i==j)) for j in range(6)])
 for i,j in combinations(range(6),2):profiles.append([F(int(k in (i,j)),2) for k in range(6)])
 profiles.append([F(1,6)]*6)
 certs=[];chosen=row['selected_indices']
 if row['precision_lower_exact']=='1':
  q=chosen[0]
  certs=[{'failure_mask':1<<q,'proof':{'kind':'branch','batch':q,'branches':[{'row':r,'proof':{'kind':'infeasible','lambda':['1']}} for r in range(6)]}}]
 elif row['precision_lower_exact']=='1/2':
  i,j=chosen;lams={(z['first_contrast'],z['second_contrast']):F(z['lambda']) for z in row['pair_cover_multipliers']}
  certs=[{'failure_mask':(1<<i)|(1<<j),'proof':{'kind':'branch','batch':i,'branches':[
   {'row':r,'proof':{'kind':'branch','batch':j,'branches':[
    {'row':s,'proof':{'kind':'infeasible','lambda':[str(lams[r,s]),str(1-lams[r,s])]}} for s in range(6)]}} for r in range(6)]}}]
 else:assert row['precision_lower_exact']=='0'
 return {'id':row['id'],'cohort':row['cohort'],'meter':row['meter'],'status':'MATCHED_EXACT','lower':row['precision_lower_exact'],'upper':row['precision_upper_exact'],
   'old_lower':row['precision_lower_exact'],'old_upper':row['precision_upper_exact'],
   'batch_weights':row['batch_weights'],'adverse_weights':row['adverse_profile_weights'],
   'profiles':[[str(z) for z in x] for x in profiles],'cover_certificates':certs,
   'normalized_coefficients_exact':row['normalized_coefficients_exact'],'fine_answers_loaded':False}

def project_precision(pi,S,value):
 """Rationalize free coordinates while preserving active integer equalities."""
 for tol in [1e-8,1e-10,1e-12]:
  A=[[F(1)]*10];b=[F(1)]
  for s in S:
   if abs(sum(float(v)*float(w) for v,w in zip(s,pi))-float(value))<=tol:A.append(list(map(F,s)));b.append(value)
  for i,v in enumerate(pi):
   if abs(v)<=tol:A.append([F(int(j==i)) for j in range(10)]);b.append(F(0))
  matrix=[r+[rhs] for r,rhs in zip(A,b)];piv=[];row=0
  for col in range(10):
   k=next((k for k in range(row,len(matrix)) if matrix[k][col]),None)
   if k is None:continue
   matrix[row],matrix[k]=matrix[k],matrix[row];scale=matrix[row][col];matrix[row]=[v/scale for v in matrix[row]]
   for k in range(len(matrix)):
    if k!=row and matrix[k][col]:
     scale=matrix[k][col];matrix[k]=[v-scale*w for v,w in zip(matrix[k],matrix[row])]
   piv.append(col);row+=1
  if any(not any(r[:10]) and r[10] for r in matrix):continue
  free=[i for i in range(10) if i not in piv]
  x=[F(float(v)).limit_denominator(10**8) for v in pi]
  for k,j in enumerate(piv):x[j]=matrix[k][10]-sum(matrix[k][i]*x[i] for i in free)
  if min(x)>=0 and sum(x)==1 and all(primary.dot(x,s)>=value for s in S):return x
 return None

def proposed_policy(V,S,value):
 vertex=[[max(row[h] for row in batch) for h in range(6)] for batch in V]
 A=[[-float(v) for v in s]+[0.] for s in S]
 b=[-float(value)]*len(S)
 A += [[float(vertex[q][h]) for q in range(10)]+[-1.] for h in range(6)];b += [0.]*6
 options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}
 kwargs=dict(A_ub=A,b_ub=b,A_eq=[[1.]*10+[0.]],b_eq=[1.],bounds=[(0,1)]*11,method='highs',options=options)
 res=linprog([0.]*10+[1.],**kwargs);assert res.success,res.message
 lower=float(res.fun);initial=res.x.copy();calls=1
 # Numerical lexicographic refinement within an explicitly declared width
 # slack. No recorded answer enters either objective or tie resolution.
 kwargs['A_ub']=A+[[0.]*10+[1.]];kwargs['b_ub']=b+[lower+1e-10]
 eq=[[1.]*10+[0.]];rhs=[1.];lex_complete=True
 for q in range(9):
  obj=[0.]*11;obj[q]=1.
  kwargs['A_eq']=eq;kwargs['b_eq']=rhs
  z=linprog(obj,**kwargs);calls+=1
  if not z.success:lex_complete=False;break
  res=z;v=max(0.,min(1.,float(z.x[q])))
  eq=eq+[[float(j==q) for j in range(10)]+[0.]];rhs=rhs+[v]
 pi=project_precision(res.x[:10],S,value)
 if pi is None:pi=project_precision(initial[:10],S,value);lex_complete=False
 return pi,lower,calls,lex_complete

def refine(case,row,seconds):
 start=time.perf_counter();value=F(case['lower']);assert value==F(case['upper'])
 out=json.loads(json.dumps(case));V=primary.vectors([[F(x) for x in c] for c in row['normalized_coefficients_exact']])
 vertex=[[max(v[h] for v in rows) for h in range(6)] for rows in V]
 def width(pi):return max(sum(pi[q]*vertex[q][h] for q in range(10)) for h in range(6))
 old_pi=list(map(F,case['batch_weights']));old_width=width(old_pi)
 if value==0:
  out['batch_weights']=row['batch_weights'];out['cover_certificates']=[]
  out['secondary']={'status':'REUSED_COEFFICIENT_ONLY_MEAN_POLICY','reason':'Every batch mixture is precision-optimal at value zero; retain the saved mean-width optimizer.','LPs':0,'old_worst_expected_width':str(old_width),'new_worst_expected_width':str(width(list(map(F,out['batch_weights'])))),'seconds':time.perf_counter()-start}
  return out
 oracle=primary.Oracle(V,start+seconds);profiles=[[F(z) for z in x] for x in case['profiles']]
 mu=list(map(F,case['adverse_weights']));LPs=0;status='PENDING';lex=True;lower=None
 try:
  for iteration in range(40):
   if time.perf_counter()>oracle.deadline:raise TimeoutError('secondary case limit')
   S=[primary.pattern(V,x) for x in profiles]
   pi,lower,calls,lex_step=proposed_policy(V,S,value);LPs+=calls;lex &= lex_step
   if pi is None:raise ArithmeticError('failed exact projection onto the precision face')
   certs=[];newpoint=None
   for mask in primary.bad_subsets(pi,value):
    point,proof=oracle.feasible(mask)
    if point is not None:
     assert primary.dot(pi,primary.pattern(V,point))<value
     newpoint=point;profiles.append(point);mu.append(F(0));break
    certs.append({'failure_mask':mask,'proof':proof})
   if newpoint is None:
    assert width(pi)<=old_width+F(1,10**7), 'secondary refinement worsened its width objective materially'
    out.update(batch_weights=list(map(str,pi)),profiles=[[str(z) for z in x] for x in profiles],adverse_weights=list(map(str,mu)),cover_certificates=certs)
    status='EXACT_PRECISION_REVERIFIED';break
  else:raise TimeoutError('secondary cut limit')
 except (TimeoutError,ArithmeticError) as exc:status='SAFE_PRIMARY_FALLBACK: '+str(exc)
 out['secondary']={'status':status,'lexicographic_completed':lex,'LPs':LPs+oracle.lp,
  'old_worst_expected_width':str(old_width),'new_worst_expected_width':str(width(list(map(F,out['batch_weights'])))),
  'finite_LP_width_lower_numeric':lower,'maximum_numerical_width_face_slack':1e-10,
  'primary_precision':'exactly preserved and separately verified','secondary_optimality':'Numerical LP refinement; exact global secondary optimality is not asserted.',
  'seconds':time.perf_counter()-start,'oracle_nodes':oracle.nodes}
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--catalog',type=Path,default=HERE/'inputs/precision_catalog.json')
 p.add_argument('--completed',type=Path,default=HERE/'all_418/report.json')
 p.add_argument('--output-dir',type=Path,default=HERE/'refined_all')
 p.add_argument('--seconds-per-case',type=float,default=90.)
 a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
 catalog=json.loads(a.catalog.read_text());new=json.loads(a.completed.read_text());completed={r['id']:r for r in new['cases']}
 assert len(completed)==418 and all(r['status']=='MATCHED_EXACT' for r in completed.values())
 report={'status':'RUNNING','selection':'all_full_panel','protocol_date':'2026-10-15',
  'input_sha256':sha(a.catalog),'primary_completion_sha256':sha(a.completed),'source_sha256':sha(Path(__file__)),
  'primary_source_sha256':sha(Path(primary.__file__)),'threshold':'1/2','batch_order':[list(q) for q in primary.Q],
  'fine_answers_loaded':False,'scope':'All 1098 source-bound blocks. Exact primary continuum precision optimum; coefficient-only constrained mean-width secondary refinement with declared numerical lexicographic convention.','cases':[]}
 for i,row in enumerate(sorted(catalog['plans'],key=lambda r:r['id']),1):
  case=completed[row['id']] if row['id'] in completed else old_case(row)
  result=refine(case,row,a.seconds_per_case);report['cases'].append(result)
  if i%25==0:
   write(a.output_dir/'report.json',report)
   print(json.dumps({'done':i,'total':1098,'last':result['id'],'secondary':result['secondary']['status']}),flush=True)
 assert len(report['cases'])==1098
 report['status']='PASS';report['policies_frozen_before_recorded_replay']=True;write(a.output_dir/'report.json',report)
 print(json.dumps({'status':'PASS','cases':1098,'seconds':sum(r['secondary']['seconds'] for r in report['cases'])}),flush=True)

if __name__=='__main__':main()
