"""Exact source-linked check of the compact main-text empirical certificate."""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import json,hashlib
HERE=Path(__file__).resolve().parent
CASE='external/hpm_1/2025-07-05/12'
TABLE=[['.1476','.7072','.0905','.0027'],['.6304','.6749','.2134','.1257'],['.0900','.8534','.0657','0'],['.4960','.3885','.3222','.1180'],['.3096','.5153','.2955','.0062'],['1','.1453','.2820','.2281']]
COEFFICIENT_LOWER=[['1','.2928','.0571','.1475','0','.0026'],['1','.3251','.6303','.4169','.1256','0'],['1','.1466','.0899','.0242','0','0'],['0','.3884','1','.6778','.6220','.5040'],['1','.4847','.0140','.3095','0','.0061'],['.2093','.3546','1','.7180','.2280','0']]
LAM=[[F(1)]*6,[F(1,2)]*6,[F(1)]*6,[F(1)]*6,[F(1)]*6,[F(1,3),F(1,3),F(3,7),F(0),F(1,4),F(0)]]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def span(c,a,b):return max(c[a:b])-min(c[a:b])
def joint(C,Q,x):
 cuts=[0,*Q,6]
 return max(sum(sum(x[a:b])*span(c,a,b) for a,b in zip(cuts,cuts[1:])) for c in C)
def main():
 path=HERE/'precision_external_results/plans.json';data=json.loads(path.read_text())
 row=next(r for r in data['plans'] if r['precision_lower_exact']==r['precision_upper_exact']=='1/2');assert row['id']==CASE
 source_rows={}
 for rel,h in data['source_hashes'].items():
  p=HERE.parent/rel.replace(chr(92),'/');assert sha(p)==h
  for r in json.loads(p.read_text())['cases']:source_rows[r['id']]=r
 raw=[source_rows[key]['c'] for key in row['pair_case_ids']];assert raw==row['original_c_binary64']
 C=[]
 for c in raw:
  c=list(map(F.from_float,c));lo,hi=min(c),max(c);assert hi>lo;C.append([(v-lo)/(hi-lo) for v in c])
 assert [[str(v) for v in c] for c in C]==row['normalized_coefficients_exact']
 for cc,ll in zip(C,COEFFICIENT_LOWER):
  for value,lower in zip(cc,map(F,ll)):
   if lower in (0,1):assert value==lower
   else:assert lower<=value<lower+F(1,10000)
 actual=[[span(c,2,6),span(c,0,2),span(c,2,4),span(c,4,6)] for c in C];U=[list(map(F,r)) for r in TABLE]
 for rr,uu in zip(actual,U):
  for v,u in zip(rr,uu):
   assert u-F(1,10000)<v<=u or v==u
   if u in (0,1):assert v==u
 # Every one of the 36 pair-cover checks is reduced to the three
 # segment-coordinate inequalities shown in the main text.
 rowmax=[]
 for r in range(6):
  values=[]
  for s in range(6):
   lam=LAM[r][s];assert 0<=lam<=1
   v=[(1-lam)*U[s][1],lam*U[r][0]+(1-lam)*U[s][2],lam*U[r][0]+(1-lam)*U[s][3]]
   assert max(v)<=F(1,2);values.extend(v)
  rowmax.append(max(values))
 assert rowmax==list(map(F,['.1476','.4763','.09','.496','.3096']))+[F(4267,8750)]
 # Direct source inequalities make the upper adverse certificate inspectable.
 assert F('.1466')<=C[2][1]<=F('.1467') and C[2][0]==1
 assert F('.3546')<=C[5][1]<=F('.3547') and C[5][2]==1 and C[5][5]==0
 e2=[F(0),F(1),F(0),F(0),F(0),F(0)];mid=[F(0),F(0),F(0),F(1,2),F(1,2),F(0)]
 Q=list(combinations(range(1,6),2));w1=[joint(C,q,e2) for q in Q];w2=[joint(C,q,mid) for q in Q]
 assert w1[0]==0 and w2[0]==1 and min(w1[1:])>=F('.6453')
 success=[(int(a<=F(1,2))+int(b<=F(1,2)))/2 for a,b in zip(w1,w2)];assert max(success)==.5
 # Use the existing exact adaptive certificate, with an outward enclosure
 # of its switch. Both enlarged branch domains must still satisfy precision.
 ap=HERE/'precision_external_results/adaptive_half_check.json';ad=json.loads(ap.read_text());ar=next(r for r in ad['cases'] if r['id']==CASE)
 assert ad['precision_plans_sha256']==sha(path) and ar['first_query']==2 and len(ar['branches'])==2
 b0,b1=ar['branches'];theta=F(b0['hi'])
 assert b0['second']==4 and b1['second']==1 and F(b0['lo'])==0 and F(b1['lo'])==theta and F(b1['hi'])==1
 assert F('.5226')<=theta<=F('.5227')
 left=max(max(b*t+max(c,d)*(1-t) for t in (F(0),F('.5227'))) for a,b,c,d in U)
 right=max(a*(1-F('.5226')) for a,b,c,d in U);assert left==F('.47743079') and right==F('.4774')
 result={'status':'PASS','case':CASE,'selection':'First exact-half case in the frozen external ledger; no new case selection based on recorded answers',
  'precision_plans_sha256':sha(path),'source_hashes':data['source_hashes'],'contrasts':row['pair_case_ids'],
  'normalized_coefficients_exact':row['normalized_coefficients_exact'],'coefficient_lower_enclosures':COEFFICIENT_LOWER,'range_upper_enclosures':TABLE,
  'pair_cover_multipliers':[[str(x) for x in r] for r in LAM],'pair_cover_row_maxima':list(map(str,rowmax)),
  'batch_mixture':{'12':'1/2','24':'1/2'},'lower_precision_guarantee':'1/2','adverse_profiles':{'e2':'1/2','(e4+e5)/2':'1/2'},
  'adverse_joint_widths_exact':[list(map(str,w1)),list(map(str,w2))],'adverse_success_expectations':success,'upper_precision_guarantee':'1/2',
  'adaptive_certificate_sha256':sha(ap),'checked_adaptive_policy':'The existing exact policy certificate queries2 then4 below its switch and1 above; both actions are safe throughout the displayed switch enclosure. No evaluated policy or ledger is replaced.',
  'exact_switch':str(theta),'switch_enclosure':['.5226','.5227'],
  'adaptive_conditional_upper_bounds':[str(left),str(right)],'checks':{'source_contrasts':6,'coefficient_enclosures':36,'range_enclosures':24,'pair_cover_multipliers':36,'component_inequalities':108,'adverse_batch_widths':20,'full_first_answer_branches':2},'checker_sha256':sha(Path(__file__))}
 (HERE/'main_inspectable_certificate_check.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k in ['status','case','checks','adaptive_conditional_upper_bounds','pair_cover_row_maxima']},indent=2))
if __name__=='__main__':main()
