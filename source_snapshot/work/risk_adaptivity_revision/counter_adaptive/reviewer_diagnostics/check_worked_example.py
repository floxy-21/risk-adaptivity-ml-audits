"""Verify the compact printed witness using exact rational outward bounds.

No scientific implementation import, network, training, or hidden-answer search.
The actual case is the existing earliest qualifying meter-1 witness.
"""
from fractions import Fraction as F
from pathlib import Path
from itertools import combinations
import argparse, hashlib, json
HERE=Path(__file__).resolve().parent
CASE='consumer_00000001/2017-10-01/06/daily/hist_gradient_boosting'
BOUNDS=[(F(1),F(1)),(F('0.9061'),F('0.9062')),(F(0),F(0)),
        (F('0.5717'),F('0.5718')),(F('0.8607'),F('0.8608')),(F('0.2988'),F('0.2989'))]
EXPECTED=[[1,0,0,0,1,1,1,0,0,0],[0,0,0,0,0,0,0,0,1,1]]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def span_bounds(a,b):
    v=BOUNDS[a:b]
    if b-a==1:return F(0),F(0)
    return max(F(0),max(x[0] for x in v)-min(x[1] for x in v)),max(x[1] for x in v)-min(x[0] for x in v)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=HERE/'worked_example_verification.json')
    p.add_argument('--geometry',type=Path,help='Optional regenerated raw-source geometry; not required by bundled replay')
    args=p.parse_args()
    report_path=HERE/'report.json'
    saved=json.loads(report_path.read_text())['fully_specified_witness']
    assert saved['id']==CASE
    c=[F.from_float(v) for v in saved['original_c_binary64']];span=max(c)-min(c)
    q=[(v-min(c))/span for v in c]
    assert q==[F(n,saved['denominator']) for n in saved['normalized_coefficient_numerators']]
    assert all(lo<=v<=hi for v,(lo,hi) in zip(q,BOUNDS))
    E=F(saved['total_kWh_exact']);assert E==F('4.6129961798')
    W0=E*span
    assert F('1.31295')<W0<F('1.31296')
    source_hashes={'report.json':sha(report_path),
                   'worked_example_main.tex':sha(HERE/'worked_example_main.tex')}
    geometry_check=None
    if args.geometry is not None:
        geometry=json.loads(args.geometry.read_text())['cases']
        row=next(x for x in geometry if x['id']==CASE)
        assert row['c']==saved['original_c_binary64']
        exact_geometry=json.loads(args.geometry.read_text(),parse_float=F)['cases']
        assert next(x for x in exact_geometry if x['id']==CASE)['E']==E
        discrepancy=abs(W0-F.from_float(row['W0']))
        assert discrepancy<F(1,10**14)
        source_hashes['optional_geometry']=sha(args.geometry)
        geometry_check={'status':'PASS','case_id':CASE,
                        'saved_float_width_discrepancy_exact':str(discrepancy),
                        'scope':'Cross-check against supplied regenerated geometry; no raw source retrieval or refit by this checker'}
    # The two conditional width coefficients follow solely from segment ranges.
    left35=span_bounds(0,3)[1]
    right35=max(span_bounds(3,5)[1],span_bounds(5,6)[1])
    left32=max(span_bounds(0,2)[1],span_bounds(2,3)[1])
    right32=span_bounds(3,6)[1]
    assert (left35,right35,left32,right32)==(F(1),F('.2891'),F('.0939'),F('.5620'))
    upper35=max(left35*t+right35*(1-t) for t in [F(0),F(1,4)])
    upper32=max(left32*t+right32*(1-t) for t in [F(1,4),F(1)])
    assert upper35==F('.466825')<F(1,2) and upper32==F('.444975')<F(1,2)
    # Verify each printed adverse entry for EVERY coefficient vector in the box.
    batches=list(combinations(range(1,6),2));checked=[]
    for i,Q in enumerate(batches):
        cuts=(0,)+Q+(6,);column=[]
        for profile,h in enumerate([1,4]):
            a,b=next((a,b) for a,b in zip(cuts,cuts[1:]) if a<=h<b)
            lo,hi=span_bounds(a,b);success=EXPECTED[profile][i]
            assert (hi<=F(1,2)) if success else (lo>F(1,2))
            actual=max(q[a:b])-min(q[a:b]);assert int(actual<=F(1,2))==success
            column.append(success)
        assert sum(column)<=1
        checked.append({'batch':list(Q),'e2_success':column[0],'e5_success':column[1],'adverse_success_exact':str(F(sum(column),2))})
    assert EXPECTED[0][8]==0 and EXPECTED[1][8]==1
    result={'status':'PASS','case_id':CASE,'normalized_coefficients_exact':list(map(str,q)),
        'displayed_outward_intervals':[[str(a),str(b)] for a,b in BOUNDS],
        'retained_total_kWh_exact':str(E),'initial_width_exact':str(W0),
        'threshold_exact':str(W0/2),'optional_geometry_check':geometry_check,
        'conditional_upper_coefficients_exact':list(map(str,[left35,right35,left32,right32])),
        'branch_maxima_exact':[str(upper35),str(upper32)],'adverse_batches':checked,
        'adaptive_success_exact':'1','batch_success_exact':'1/2',
        'source_hashes':source_hashes,
        'checker_sha256':sha(Path(__file__)),
        'scope':'Bundled-witness exact check of saved binary64 coefficients, reported exact total, printed rational enclosures, all ten adverse columns and both continuum branches. Default replay does not require raw-derived geometry. Optional geometry cross-check is separately flagged; no raw retrieval, refitting or new sample is performed.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'PASS','case_id':CASE,'adverse_batches':10,'branch_maxima_exact':result['branch_maxima_exact'],'initial_width':float(W0)}))
if __name__=='__main__':main()


