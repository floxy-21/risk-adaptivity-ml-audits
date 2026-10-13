"""Reconstruct interval-trace aggregates without the mixed raw target archive.

Aggregation is independently implemented here with csv/math and no imports of
the study aggregation helpers. The LP integration fixtures deliberately reuse
the study helper, disclosed in the report. This is not a raw-trace re-execution.
Only the new audit JSON is written; existing artifacts are read-only.
"""
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs'
RAW = ('pair_trials','decisions','wrong_decisions','enclosed_truth','initial_width_sum',
       'actual_width_sum','worst_width_sum','queries_sum','free_copy_sum','deduced_sum',
       'original_missing_sum')
INTEGER = {'pair_trials','decisions','wrong_decisions','enclosed_truth','queries_sum',
           'free_copy_sum','deduced_sum','original_missing_sum'}
METRIC = ('certification','mean_queries','free_copy_fraction','deduced_fraction',
          'mean_initial_width','mean_actual_width','mean_worst_width',
          'normalized_initial_width','normalized_actual_width','normalized_worst_width',
          'actual_width_fraction','worst_width_fraction')
MKEY = ('cohort','meter','tolerance','regime','budget','policy')
CKEY = ('cohort','tolerance','regime','budget','policy')
MAX_ERROR = defaultdict(float)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(name):
    with (OUT/name).open(newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))


def key(row, names):
    return tuple(float(row[k]) if k == 'tolerance' else int(row[k]) if k in ('budget','mask_seed')
                 else row[k] for k in names)


def compare(actual, expected, field, exact=False):
    a, b = float(actual), float(expected)
    assert math.isfinite(a) and math.isfinite(b)
    MAX_ERROR[field] = max(MAX_ERROR[field],abs(a-b))
    if exact:
        assert a.is_integer() and b.is_integer() and int(a)==int(b),(field,a,b)
    else:
        assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(field,a,b)


def main():
    report = json.loads((OUT/'study_interval_trace_recovery.json').read_text(encoding='utf-8'))
    assert report['status'] == 'passed'
    names = ['study_interval_trace_recovery.json',*report['output_hashes']]
    before = {name:sha(OUT/name) for name in names}
    checked_sources, unavailable_sources = {}, []
    for name, expected in report['source_hashes'].items():
        path = OUT/name
        if path.exists():
            assert sha(path)==expected,name
            checked_sources[name]=expected
        else:
            unavailable_sources.append(name)
    for name, expected in report['output_hashes'].items():
        assert before[name]==expected,name
    protocol = ROOT/'work/interval_trace_protocol.txt'
    assert sha(protocol)==report['protocol_sha256']
    detail = read_rows('study_interval_trace_recovery_pair_seed.csv')
    meters = read_rows('study_interval_trace_recovery.csv')
    cohorts = read_rows('study_interval_trace_recovery_cohorts.csv')
    gaps = read_rows('study_interval_trace_recovery_gaps.csv')
    summary = json.loads((OUT/'study_summary.json').read_text(encoding='utf-8'))
    norms = {(r['cohort'],r['meter']):max(r['training_mean_kwh']**2,1e-12) for r in summary['meters']}
    groups = defaultdict(list)
    unique = set()
    for r in detail:
        fullkey = key(r,(*MKEY,'mask_seed','model_a','model_b'))
        assert fullkey not in unique
        unique.add(fullkey)
        groups[key(r,MKEY)].append(r)
        compare(r['training_mean_squared'],norms[r['cohort'],r['meter']],'training_normalization')
        n = float(r['pair_trials'])
        assert n > 0 and 0 <= float(r['decisions']) <= n
        compare(r['wrong_decisions'],0,'wrong_decisions',True)
        compare(r['enclosed_truth'],n,'enclosed_truth',True)
        compare(r['original_missing_sum'],6*n,'original_missing_sum',True)
        assert 0 <= float(r['queries_sum']) <= int(r['budget'])*n
        assert 0 <= float(r['free_copy_sum'])+float(r['deduced_sum']) <= 6*n
        assert float(r['actual_width_sum']) <= float(r['worst_width_sum']) + 1e-8*max(1,float(r['initial_width_sum']))
        assert float(r['worst_width_sum']) <= float(r['initial_width_sum']) + 1e-8*max(1,float(r['initial_width_sum']))
    meter_index = {key(r,MKEY):r for r in meters}
    assert len(meter_index)==len(meters)==len(groups)
    reconstructed_meters = []
    for group_key, group in sorted(groups.items()):
        assert len(group)==18 # three seeds times six named pairs
        assert {int(r['mask_seed']) for r in group}=={1103,2207,3301}
        expected = {k:math.fsum(float(r[k]) for r in group) for k in RAW}
        actual = meter_index[group_key]
        norm = norms[actual['cohort'],actual['meter']]
        for k in RAW:
            compare(actual[k],expected[k],k,k in INTEGER)
        n = expected['pair_trials']
        expected.update(certification=expected['decisions']/n, mean_queries=expected['queries_sum']/n,
                        free_copy_fraction=expected['free_copy_sum']/expected['original_missing_sum'],
                        deduced_fraction=expected['deduced_sum']/expected['original_missing_sum'])
        for width in ('initial','actual','worst'):
            expected['mean_'+width+'_width'] = expected[width+'_width_sum']/n
            expected['normalized_'+width+'_width'] = expected[width+'_width_sum']/n/norm
        for width in ('actual','worst'):
            expected[width+'_width_fraction'] = (expected[width+'_width_sum']/expected['initial_width_sum']
                                                 if expected['initial_width_sum']>0 else 0.)
        for k in METRIC:
            compare(actual[k],expected[k],k)
        expected.update(dict(zip(MKEY,group_key)))
        reconstructed_meters.append(expected)
    cgroups = defaultdict(list)
    for r in reconstructed_meters:
        cgroups[key(r,CKEY)].append(r)
    cohort_index = {key(r,CKEY):r for r in cohorts}
    json_index = {key(r,CKEY):r for r in report['cohort_results']}
    assert len(cohort_index)==len(cohorts)==len(cgroups)==len(json_index)
    reconstructed_cohorts = {}
    for ck, group in cgroups.items():
        expected = {k:math.fsum(r[k] for r in group)/len(group) for k in METRIC}
        for k in ('pair_trials','decisions','wrong_decisions','enclosed_truth'):
            expected[k] = sum(int(r[k]) for r in group)
        expected['pooled_certification'] = expected['decisions']/expected['pair_trials']
        for actual in (cohort_index[ck],json_index[ck]):
            for k,value in expected.items():
                compare(actual[k],value,'cohort_'+k,k in INTEGER)
        reconstructed_cohorts[ck] = expected
    gkeys = ('cohort','tolerance','regime')
    gap_index = {key(r,gkeys):r for r in gaps}
    json_gaps = {key(r,gkeys):r for r in report['exact_vs_greedy']}
    assert len(gap_index)==len(gaps)==len(json_gaps)==18
    for gk, actual in gap_index.items():
        exact = reconstructed_cohorts[(*gk,2,'optimal_minimax_width')]
        greedy = reconstructed_cohorts[(*gk,2,'greedy_width_reduction')]
        expected = {
            'exact_minus_greedy_certification_pp':100*(exact['certification']-greedy['certification']),
            'exact_minus_greedy_normalized_actual_width':exact['normalized_actual_width']-greedy['normalized_actual_width'],
            'exact_minus_greedy_normalized_worst_width':exact['normalized_worst_width']-greedy['normalized_worst_width'],
            'exact_mean_queries':exact['mean_queries'],'greedy_mean_queries':greedy['mean_queries']}
        for r in (actual,json_gaps[gk]):
            for k,value in expected.items():
                compare(r[k],value,k)
    evaluations = sum(int(float(r['pair_trials'])) for r in detail)
    compare(evaluations,report['checks']['policy_budget_evaluations'],'dependent_evaluations',True)
    assert len(detail)==14688 and len(meters)==816 and len(cohorts)==72
    # Only this fixture function is reused: it compares endpoints to SciPy HiGHS.
    sys.path.insert(0,str(OUT))
    from study_interval_trace_recovery import integration_checks
    fixture = integration_checks()
    assert fixture['independent_lp_endpoint_calls']==192
    for k,v in fixture.items():
        if isinstance(v,bool):
            assert v and report['integration_checks'][k]
        else:
            compare(v,report['integration_checks'][k],'fixture_'+k)
    for name,digest in before.items():
        assert sha(OUT/name)==digest,'Changed artifact: '+name
    for name,digest in checked_sources.items():
        assert sha(OUT/name)==digest,'Changed source: '+name
    result = {
        'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
        'aggregation_counts':{'pair_seed_rows':len(detail),'meter_rows':len(meters),
                              'cohort_rows':len(cohorts),'policy_difference_rows':len(gaps),
                              'dependent_policy_budget_evaluations':evaluations},
        'replayed_integration_fixtures':fixture,
        'maximum_absolute_discrepancies':dict(MAX_ERROR),
        'source_hashes':{**before,**checked_sources},'unavailable_source_files':unavailable_sources,
        'protocol_sha256':sha(protocol),'script_sha256':sha(Path(__file__)),
        'existing_artifacts_unchanged':True,
        'scope':'Independent stdlib reconstruction of pair/seed aggregates into meter, cohort and exact-versus-greedy tables; report JSON reconciled to CSVs. The 192 LP endpoint fixtures are rerun by importing the original helper, explicitly not an independent fixture implementation.',
        'limitations':'No raw-trace re-execution, no retraining, no independent recovery-solver implementation, and no independent per-case certificate or query verification. Missing mixed target archive is permitted for supplement-only reconstruction. Separate editorial review examined closure, greedy selection and witness functions. Constructed uncertainty and dependent historical cases do not measure calibration, costs or production latency.'}
    target = OUT/'study_interval_trace_audit.json'
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'passed','aggregation_counts':result['aggregation_counts'],
                      'LP_checks':fixture,'unavailable_sources':unavailable_sources},indent=2))


if __name__ == '__main__':
    main()
