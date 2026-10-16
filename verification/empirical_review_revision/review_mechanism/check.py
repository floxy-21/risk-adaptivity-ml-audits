"""Independent shortest-path and rational cell verification of diagnostics.

Does not import the analysis producer or reading-budget optimizer. Uses the
existing source-binding routine solely for coefficient provenance.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
import importlib.util
from itertools import combinations
import json
from pathlib import Path
import time
from input_binding import frozen

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('binding_only',HERE.parent/'assurance_feasibility/verify_assurance.py')
binding=importlib.util.module_from_spec(spec);spec.loader.exec_module(binding)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
SETS=tuple(q for n in range(6) for q in combinations(range(1,6),n))

def range_(v,a,b):return max(v[a:b])-min(v[a:b])

def shortest(c,thresholds):
    distance=[0]+[100]*6
    for stop in range(1,7):
        for start in range(stop):
            if all(range_(v,start,stop)<=t for v,t in zip(c,thresholds)):
                distance[stop]=min(distance[stop],distance[start]+1)
    return distance[6]-1

def second_ranges(c,k,j):
    if j<k:return [(max(range_(v,0,j),range_(v,j,k)),range_(v,k,6)) for v in c]
    return [(range_(v,0,k),max(range_(v,k,j),range_(v,j,6))) for v in c]

def covered(c,k,thresholds,counts):
    """All exact breakpoints and open-cell midpoints, not interval union."""
    rows={j:second_ranges(c,k,j) for j in range(1,6) if j!=k}
    points={F(0),F(1)}
    for pairs in rows.values():
        for (a,b),t in zip(pairs,thresholds):
            if a!=b:
                cross=(t-b)/(a-b)
                if 0<=cross<=1:points.add(cross)
    points=sorted(points);probes=points+[(a+b)/2 for a,b in zip(points,points[1:])]
    for x in probes:
        counts['exact_first_answer_cell_probes']+=1
        if not any(all(a*x+b*(1-x)<=t for (a,b),t in zip(pairs,thresholds)) for pairs in rows.values()):
            return False
    return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--chain-dir',type=Path);p.add_argument('--results',type=Path,required=True);a=p.parse_args()
    start=time.perf_counter();report=read(a.results/'report.json');given=read(a.results/'ledger.json')['rows'];training=read(a.results/'training_scales.json')
    assert report['status']=='PASS' and report['ledger_sha256']==sha(a.results/'ledger.json')
    assert report['training_scales_sha256']==sha(a.results/'training_scales.json')
    if a.chain_dir:
        for path,digest in training['input_hashes'].items():
            path=path.replace('<WORKSPACE>',str(binding.ROOT))
            assert sha(path)==digest,path
        inputs,provenance=binding.source_inputs(a.chain_dir)
        plans={r['id']:r for r in read(a.chain_dir/'precision/plans.json')['plans']}
    else:
        inputs,provenance,declared_training,_,_,plans=frozen()
        assert declared_training==training['systems']
    counts=Counter();aggregate={}
    for saved,inp in zip(given,inputs):
        assert saved['id']==inp['id'] and saved['coefficient_digest']==inp['coefficient_digest']
        c=inp['coefficients'];system=saved['cohort']+'/'+saved['system'];scale=F(training['systems'][system]['second_moment_exact'])
        raw=plans[saved['id']]['original_c_binary64'];E=F(saved['known_total_exact'])
        widths=[E*(max(map(F.from_float,row))-min(map(F.from_float,row))) for row in raw]
        scalar=[shortest([v],[F(1,2)]) for v in c]
        base=shortest(c,[F(1,2)]*6)
        assert base==saved['baseline_fixed_minimum']
        for i,pair in enumerate(saved['contrasts']):
            assert pair['scalar_minimum_fixed']==scalar[i]
            assert F(pair['W0_exact'])==widths[i]
            assert F(pair['W0_over_training_second_moment'])==widths[i]/scale
            deleted=shortest(c[:i]+c[i+1:],[F(1,2)]*5)
            assert deleted==pair['minimum_fixed_after_deletion']
            assert (deleted<base)==pair['deletion_binding']
            counts['scalar_and_row_deletion_shortest_paths']+=2
        assert saved['joint_only']==(saved['baseline_saving'] and max(scalar)<=2)
        if saved['baseline_saving']:
            minimum=saved['minimum_obstruction_contrasts']
            found=[]
            for n in range(1,minimum+1):
                subsets=[sub for sub in combinations(range(6),n) if shortest([c[i] for i in sub],[F(1,2)]*n)>2]
                counts['contrast_subset_shortest_paths']+=len(list(combinations(range(6),n)))
                if n<minimum:assert not subsets
                else:found=subsets
            assert found==list(map(tuple,saved['minimum_obstruction_subsets'])) and found
        prior=6;coverage_cache={}
        for factor,value in saved['floors'].items():
            factor=F(factor);epsilon=factor*scale
            ts=[max(F(1,2),epsilon/w) for w in widths]
            assert epsilon==F(value['epsilon_exact']) and ts==list(map(F,value['thresholds_normalized']))
            fixed=shortest(c,ts);assert fixed==value['fixed_minimum']<=prior;prior=fixed
            # Enumerate every fixed action independently, and check all stated minima.
            satisfying=[]
            for q in SETS:
                boundary=(0,*q,6)
                ok=all(all(range_(row,l,r)<=t for l,r in zip(boundary,boundary[1:])) for row,t in zip(c,ts))
                if ok:satisfying.append(q)
                counts['enumerated_fixed_batch_feasibility']+=1
            assert fixed==min(map(len,satisfying)) and tuple(value['fixed_batch']) in satisfying
            key=tuple(ts)
            if key in coverage_cache:
                allfirst=coverage_cache[key];counts['identical_threshold_cover_reuses']+=1
            else:
                allfirst=[k for k in range(1,6) if covered(c,k,ts,counts)];coverage_cache[key]=allfirst
            adaptive=fixed if fixed<=1 else 2 if allfirst else None
            assert adaptive==value['adaptive_minimum_at_most_two']
            counts['adaptive_coverage_decisions']+=1
            if value['adaptive_cover'] is not None:
                rule=value['adaptive_cover'];k=rule['first'];assert k in allfirst
                end=F(0)
                for interval in sorted(rule['intervals'],key=lambda v:(F(v['lower']),F(v['upper']),v['second'])):
                    lo,hi=F(interval['lower']),F(interval['upper']);assert 0<=lo<=hi<=1
                    assert lo<=end;end=max(end,hi)
                    pairs=second_ranges(c,k,interval['second'])
                    for x in [lo,hi]:
                        assert all(aa*x+bb*(1-x)<=t for (aa,bb),t in zip(pairs,ts))
                        counts['returned_branch_endpoint_checks']+=len(c)
                assert end==1
            selected=min(fixed,adaptive if adaptive is not None else fixed)
            assert selected==value['selected_budget'] and (selected<fixed)==value['saving']
            group=aggregate.setdefault(saved['cohort'],{}).setdefault(str(factor),Counter())
            group['fixed_total']+=fixed;group['adaptive_two_else_minimum_fixed_total']+=selected
            group['saving_cases']+=selected<fixed
            group['retained_baseline_saving_cases']+=saved['baseline_saving'] and selected<fixed
            group['retained_joint_only_baseline']+=saved['joint_only'] and selected<fixed
    assert len(given)==len(inputs)==1098
    for cohort,results in aggregate.items():
        for factor,sums in results.items():
            for key,value in sums.items():assert report['summaries'][cohort]['floor_results'][factor][key]==value
    output={'status':'PASS','checks':counts,'ledger_sha256':sha(a.results/'ledger.json'),'producer_report_sha256':sha(a.results/'report.json'),
      'checker_sha256':sha(__file__),'input_provenance':provenance,'method':'Independent DAG shortest paths, exhaustive fixed sets, rational first-answer cell probes, and direct branch endpoint inequalities. Producer and optimizer are not imported.',
      'training_scale_check_scope':'Hashes and exact exported second-moment use. Training scale construction is separately checked by check_training.py.',
      'elapsed_seconds':time.perf_counter()-start}
    (a.results/'independent_check.json').write_text(json.dumps(binding.clean(output),indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:output[k] for k in ['status','checks','elapsed_seconds']},indent=2))

if __name__=='__main__':main()
