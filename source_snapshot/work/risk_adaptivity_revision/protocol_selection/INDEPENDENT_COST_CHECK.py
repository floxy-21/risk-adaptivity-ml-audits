"""Independent exact enumeration of the supplied per-case cost catalogue.

Does not import the producer or selector. Prior source checkers establish
mathematical certificate validity; this checks cost, provenance and selection.
"""
from collections import Counter
from decimal import Decimal
from fractions import Fraction as F
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;BASE=HERE.parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',type=Path,default=HERE/'cost_frontier_results')
    p.add_argument('--output',type=Path,default=HERE/'cost_frontier_independent.json')
    args=p.parse_args()
    report=json.loads((args.results_dir/'report.json').read_text())
    rows=json.loads((args.results_dir/'case_ledger.json').read_text())
    folder=BASE/'external_validation/stored_error_fallback'
    fixed={r['id']:r for r in json.loads((folder/'fixed_batch_certificates.json').read_text())['certificates']}
    adaptive={r['id']:r for r in json.loads((folder/'branch_certificates.json').read_text())['certificates']}
    expected_ratios=['0','1/4','1/2','1','2','4']
    assert report['ratio_grid_exact']==expected_ratios and len(fixed)==29 and len(adaptive)==22
    assert len(rows)==174
    summaries={r['round_to_reading_cost_ratio_exact']:r for r in report['summaries']}
    candidate_checks=0
    for token in expected_ratios:
        ratio=F(token);subset=[r for r in rows if r['round_to_reading_cost_ratio_exact']==token]
        assert len(subset)==29 and {r['case_id'] for r in subset}==set(fixed)
        counts=Counter();readings=rounds=0;costs=[F(0),F(0),F(0)]
        for row in subset:
            case=row['case_id'];f=fixed[case];a=adaptive.get(case)
            assert len(f['query_boundaries'])==3 and F(f['certified_upper_exact'])<=F(1,2)
            options=[('fixed_batch',3,1,'fixed_batch_certificates.json',f['certified_upper_exact'])]
            if a:
                assert F(a['certified_worst_branch_bound_exact'])<=F(1,2)
                options.append(('adaptive',2,2,'branch_certificates.json',a['certified_worst_branch_bound_exact']))
            candidate_checks+=len(options)
            scored=[(F(n)+ratio*q,q,n,name,path,upper) for name,n,q,path,upper in options]
            best=min(scored);cost,q,n,name,path,upper=best
            assert row['chosen_protocol']==name and row['reserved_scalar_readings']==n and row['information_rounds']==q
            assert row['system_id']==f['system_id']
            assert F(row['cost_aware_cost_exact'])==cost
            assert F(row['fixed_three_cost_exact'])==3+ratio
            baseline=(2+2*ratio) if a else (3+ratio)
            assert F(row['adaptive_with_fallback_cost_exact'])==baseline
            assert row['adaptive_baseline_uses_fixed_fallback']==(a is None)
            certificate=row['selected_certificate']
            assert certificate['case_id']==case and certificate['path']=='external_validation/stored_error_fallback/'+path
            assert certificate['sha256']==sha(folder/path)
            assert F(row['selected_certified_width_over_W0_upper_exact'])==F(upper)
            assert {r['protocol']:F(r['cost_exact']) for r in row['candidate_costs']}=={
                item[3]:item[0] for item in scored}
            if name=='fixed_batch':assert row['selected_query_boundaries']==f['query_boundaries']
            else:
                assert row['selected_first_query']==a['first_query']
                assert row['selected_successor_boundaries']==[v['second_query'] for v in a['lines']]
            counts[name]+=1;readings+=n;rounds+=q
            costs=[costs[0]+3+ratio,costs[1]+baseline,costs[2]+cost]
        summary=summaries[token]
        assert costs==[87+29*ratio,65+51*ratio,min(87+29*ratio,65+51*ratio)]
        assert list(map(F,[summary['fixed_three_cost_exact'],summary['adaptive_with_fallback_cost_exact'],summary['cost_aware_cost_exact']]))==costs
        assert summary['cost_aware_protocol_counts']==dict(counts)
        assert (summary['cost_aware_reserved_readings'],summary['cost_aware_information_rounds'])==(readings,rounds)
        assert F(summary['fraction_saved_vs_fixed_exact'])==1-costs[2]/costs[0]
        assert F(summary['fraction_saved_vs_adaptive_with_fallback_exact'])==1-costs[2]/costs[1]
    # Algebraic identity certifies the entire nonnegative ratio domain, not
    # merely these six scenarios: (3+r)-(2+2r)=1-r in each adaptive case.
    assert F(3)-F(2)==1 and F(1)-F(2)==-1
    trials_path=BASE/'external_validation/operational/http_benchmark_20261012/trials.json'
    trials=json.loads(trials_path.read_text(),parse_float=Decimal)
    for policy,saved in report['recorded_api'].items():
        selected=[t for t in trials if t['policy']==policy]
        assert len(selected)==saved['trials']==6
        for key in ['requests','information_rounds','api_io_seconds','body_bytes_received']:
            assert F(saved[key+'_mean_exact'])==sum(F(t[key]) for t in selected)/6
    assert report['source_hashes']=={'protocol_lock.json':sha(HERE/'protocol_lock.json'),
        'selector.py':sha(HERE/'selector.py'),'fixed_batch_certificates.json':sha(folder/'fixed_batch_certificates.json'),
        'branch_certificates.json':sha(folder/'branch_certificates.json'),'recorded_trials.json':sha(trials_path)}
    assert report['source_sha256']==sha(HERE/'cost_frontier.py')
    result={'status':'PASS','cases':29,'ratios':6,'case_ratio_rows':len(rows),
        'exhaustive_per_case_candidate_evaluations':candidate_checks,
        'exact_threshold_ratio':'1','universal_fixed_cost':'87+29r',
        'adaptive_with_fixed_fallback_cost':'65+51r',
        'cost_aware_catalogue_cost':'min(87+29r,65+51r)',
        'recorded_api_policies_checked':2,'recorded_api_trials_checked':12,
        'ledger_sha256':sha(args.results_dir/'case_ledger.json'),
        'producer_report_sha256':sha(args.results_dir/'report.json'),
        'scope':'Exact supplied-catalogue cost accounting and source correspondence, not measured monetary savings or new scientific certificate verification'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
