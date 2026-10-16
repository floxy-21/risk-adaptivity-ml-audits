"""Export and directly verify a floor-aware plan for the original57 cases.

Each plan uses a minimum fixed batch where sufficient, otherwise the exact
two-query adaptive cover. No optional evaluation answer is used.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
from itertools import combinations
import hashlib
import json
from pathlib import Path
from input_binding import frozen

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
SETS=tuple(q for b in range(6) for q in combinations(range(1,6),b))
def ran(row,a,b):return max(row[a:b])-min(row[a:b])
def fixed_good(c,ts,q):
    cuts=(0,*q,6)
    return all(all(ran(v,a,b)<=t for a,b in zip(cuts,cuts[1:])) for v,t in zip(c,ts))

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',required=True,type=Path);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    inp,provenance,training,_,totals,raw=frozen();sources={x['id']:x for x in inp}
    ledger=read(a.results/'ledger.json')['rows'];subset=[r for r in ledger if r['cohort']=='external' and r['baseline_saving']]
    assert len(subset)==57
    path=a.results/'decision_plan.json'
    if not a.verify_only:
        decisions=[]
        for r in subset:
            v=r['floors']['1/100'];isfixed=v['fixed_minimum']<=2
            decisions.append({'id':r['id'],'coefficient_digest':r['coefficient_digest'],
              'kind':'fixed' if isfixed else 'adaptive','readings':v['fixed_minimum'] if isfixed else 2,
              'epsilon_exact':v['epsilon_exact'],'thresholds_normalized':v['thresholds_normalized'],
              'fixed_minimum':v['fixed_minimum'],'fixed_queries':v['fixed_batch'] if isfixed else None,
              'adaptive_rule':None if isfixed else v['adaptive_cover']})
        path.write_text(json.dumps({'status':'PASS','selection':'All original57 external relative-half-width two-versus-three cases; cohort unchanged.',
          'criterion':'W_r <= max(W_r0/2, .01*training_second_moment) for every contrast',
          'online_rule':'For an adaptive plan, observe the first prefix divided by the retained total, then choose the smallest second timestamp among closed intervals containing that answer. All listed intervals are certified.',
          'ledger_sha256':sha(a.results/'ledger.json'),'decisions':decisions},indent=2)+'\n',encoding='utf-8')
    doc=read(path);assert doc['ledger_sha256']==sha(a.results/'ledger.json')
    assert {x['id'] for x in doc['decisions']}=={x['id'] for x in subset}
    counts=Counter();systems={}
    for d in doc['decisions']:
        ident=d['id'];source=sources[ident];c=source['coefficients'];assert d['coefficient_digest']==source['coefficient_digest']
        system='/'.join(ident.split('/')[:2]);m2=F(training[system]['second_moment_exact']);epsilon=m2/100
        rawc=[list(map(F.from_float,v)) for v in raw[ident]['original_c_binary64']]
        W0=[totals[ident]*(max(v)-min(v)) for v in rawc]
        ts=[max(F(1,2),epsilon/w) for w in W0]
        assert F(d['epsilon_exact'])==epsilon and list(map(F,d['thresholds_normalized']))==ts
        minimum=min(len(q) for q in SETS if fixed_good(c,ts,q))
        assert minimum==d['fixed_minimum'];counts['all_fixed_batches_checked']+=32
        if d['kind']=='fixed':
            q=tuple(d['fixed_queries']);assert len(q)==minimum==d['readings']<=2 and fixed_good(c,ts,q)
            counts['fixed_certificates']+=1
        else:
            assert minimum==3 and d['readings']==2
            rule=d['adaptive_rule'];k=rule['first'];assert k in range(1,6)
            frontier=F(0)
            for interval in sorted(rule['intervals'],key=lambda z:(F(z['lower']),F(z['upper']),z['second'])):
                j=interval['second'];assert j in range(1,6) and j!=k
                low,high=F(interval['lower']),F(interval['upper']);assert 0<=low<=high<=1 and low<=frontier
                frontier=max(frontier,high)
                for v,t in zip(c,ts):
                    if j<k:aa=max(ran(v,0,j),ran(v,j,k));bb=ran(v,k,6)
                    else:aa=ran(v,0,k);bb=max(ran(v,k,j),ran(v,j,6))
                    assert aa*low+bb*(1-low)<=t and aa*high+bb*(1-high)<=t
                    counts['rational_branch_endpoint_inequalities']+=2
            assert frontier==1;counts['adaptive_covers']+=1
        sums=systems.setdefault(system,Counter());sums['cases']+=1;sums['selected_readings']+=d['readings'];sums['minimum_fixed_readings']+=minimum
    selected=sum(x['readings'] for x in doc['decisions']);fixed=sum(x['fixed_minimum'] for x in doc['decisions'])
    assert (selected,fixed)==(70,88)
    out={'status':'PASS','assured_cases':57,'selected_readings':selected,'minimum_fixed_readings':fixed,
      'saving_percent':100*(fixed-selected)/fixed,'system_counts':systems,'checks':counts,'decision_plan_sha256':sha(path),
      'checker_sha256':sha(__file__),'input_provenance':provenance,
      'scope':'Exact uncapped noiseless audit, primary prespecified loss floor, original57 cohort. Readings are authorization counts, not HTTP requests, money or measured latency.'}
    (a.results/'decision_plan_check.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['status','assured_cases','selected_readings','minimum_fixed_readings','saving_percent','checks']},indent=2))

if __name__=='__main__':main()
