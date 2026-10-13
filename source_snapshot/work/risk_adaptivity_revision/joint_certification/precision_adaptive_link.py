"""Exact adaptive half-guarantee on the matched batch-half instances."""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import argparse,json,hashlib,time
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def span(c,l,u):return max(c[l:u])-min(c[l:u])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=HERE/'precision_external_results');p.add_argument('--base-plans',type=Path,default=HERE/'empirical_external_results/empirical_plans.json');a=p.parse_args();t=time.perf_counter()
 path=a.directory/'plans.json';d=json.loads(path.read_text());base={r['id']:r for r in json.loads(a.base_plans.read_text())['plans']};out=[]
 for row in d['plans']:
  if not row['precision_lower_exact']==row['precision_upper_exact']=='1/2':continue
  C=[list(map(F,c)) for c in row['normalized_coefficients_exact']];k=base[row['id']]['geometry']['first_query'];lines={}
  for j in range(1,6):
   if j==k:continue
   lines[j]=[]
   for c in C:
    if j<k:L=max(span(c,0,j),span(c,j,k));R=span(c,k,6)
    else:L=span(c,0,k);R=max(span(c,k,j),span(c,j,6))
    lines[j].append((L-R,R))
  points={F(0),F(1)};flat=[x for v in lines.values() for x in v]
  for (m,b),(n,c) in combinations(flat,2):
   if m!=n:
    x=(c-b)/(m-n)
    if 0<x<1:points.add(x)
  points=sorted(points);branches=[]
  for lo,hi in zip(points,points[1:]):
   tmid=(lo+hi)/2;j=min((max(m*tmid+b for m,b in ll),j) for j,ll in lines.items())[1]
   upper=max(m*x+b for m,b in lines[j] for x in (lo,hi))
   assert upper<=F(1,2),(row['id'],str(upper))
   if branches and branches[-1]['second']==j:branches[-1]['hi']=str(hi);branches[-1]['upper_exact']=str(max(F(branches[-1]['upper_exact']),upper))
   else:branches.append({'lo':str(lo),'hi':str(hi),'second':j,'upper_exact':str(upper),'lines':[[str(m),str(b)] for m,b in lines[j]]})
  out.append({'id':row['id'],'cohort':row['cohort'],'first_query':k,'branches':branches,'upper_exact':str(max(F(b['upper_exact']) for b in branches))})
 result={'status':'PASS','precision_plans_sha256':sha(path),'base_plans_sha256':sha(a.base_plans),'checks':{'matched_half_cases':len(out),'branches':sum(len(r['branches']) for r in out)},'cases':out,'scope':'Exact conditional segment maxima on every rational first-answer interval, using the existing first query. Both endpoints and all six contrasts are bounded by1/2. First matching closed interval defines ties. This verifies the adaptive side for the same instances whose batch continuum optimum is1/2.','source_sha256':sha(Path(__file__))}
 (a.directory/'adaptive_half_check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
if __name__=='__main__':main()
