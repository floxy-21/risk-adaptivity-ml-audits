"""Check released outcome ledgers and the complete rational empirical witness.

This checks supplied outcomes; analyze.py reopens source registers and
regenerated forecasts/geometry. No claim of model refitting is made here.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import argparse,csv,json,itertools
HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=json.loads((HERE/'report.json').read_text())
    with (HERE/'outcome_ledger.csv').open(newline='') as f: rows=list(csv.DictReader(f))
    with (HERE/'precision_cover_ledger.csv').open(newline='') as f: cover=list(csv.DictReader(f))
    assert len({r['id'] for r in rows})==len(rows)==4914 and len({r['id'] for r in cover})==290
    assert {r['id'] for r in cover}=={r['id'] for r in rows if r['separation']=='1'}
    for result in report['paired']:
        rr=rows if result['subset']=='all' else [r for r in rows if r['separation']=='1']
        keys={'precision':('adaptive_precision','batch_precision'),'ordering':('adaptive_ordering','batch_ordering')}[result['outcome']]
        cc=Counter((int(r[keys[0]]),int(r[keys[1]])) for r in rr)
        assert result['n']==len(rr)
        for key,pair in [('both',(1,1)),('adaptive_only',(1,0)),('batch_only',(0,1)),('neither',(0,0))]:assert result[key]==cc[pair]
    summary=next(r for r in report['summaries'] if r['policy']=='precision_optimal_cover')
    for key in ['success','relative_width','winner']:assert abs(sum(float(r[key]) for r in cover)/290-summary[key])<1e-12
    w=report['fully_specified_witness'];q=[F(n,w['denominator']) for n in w['normalized_coefficient_numerators']]
    assert min(q)==0 and max(q)==1
    adverse=list(map(F,w['cover']['adverse_weights_exact']));assert sum(adverse)==1
    assert [tuple(r['Q']) for r in w['batches']]==list(itertools.combinations(range(1,6),2))
    for row in w['batches']:
        cuts=(0,)+tuple(row['Q'])+(6,);v=[]
        for left,right in zip(cuts[:-1],cuts[1:]):v.extend([max(q[left:right])-min(q[left:right])]*(right-left))
        assert v==[F(n,w['denominator']) for n in row['range_numerators']]
        assert sum(ww*int(vv<=F(1,2)) for ww,vv in zip(adverse,v))==F(row['adverse_success'])<=F(1,2)
    # Independently check all endpoints of both branches of the printed rule.
    k=3
    for j,lo,hi in [(5,F(0),F(1,4)),(2,F(1,4),F(1))]:
        def span(a,b):return max(q[a:b])-min(q[a:b])
        left=span(0,k) if j>k else max(span(0,j),span(j,k))
        right=max(span(k,j),span(j,6)) if j>k else span(k,6)
        assert max(left*t+right*(1-t) for t in [lo,hi])<=F(1,2)
    result={'status':'PASS','paired_outcome_rows':4914,'precision_optimal_outcome_rows':290,'exact_empirical_witness_batches':10,'scope':'Bundled-ledger arithmetic and exact rational printed witness; raw counterpart is analyze.py.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
