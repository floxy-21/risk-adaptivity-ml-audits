"""Compare freshly regenerated complete-case outcomes and certificates to tables."""
import argparse,csv,hashlib,json
from fractions import Fraction as F
from pathlib import Path
HERE=Path(__file__).resolve().parent;JC=HERE.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(path):
    with path.open(newline='') as f:return {r['id']:r for r in csv.DictReader(f)}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cohort',choices=['external','all'],default='external')
    p.add_argument('--shared-dir',type=Path,required=True);p.add_argument('--precision-dir',type=Path,required=True)
    p.add_argument('--replay-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    ref=JC/('empirical_all_panel_cases.csv' if a.cohort=='all' else 'empirical_external_results/empirical_cases.csv')
    fresh=rows(a.shared_dir/'empirical_cases.csv');old=rows(ref);assert set(fresh)==set(old)
    maxdiff=0.;numeric=0
    for key,row in fresh.items():
        assert set(row)==set(old[key])
        for field,value in row.items():
            if value==old[key][field]:continue
            try:delta=abs(float(value)-float(old[key][field]))
            except ValueError:raise AssertionError((key,field,value,old[key][field]))
            assert delta<1e-10,(key,field,delta);maxdiff=max(maxdiff,delta);numeric+=1
    plans=json.loads((a.precision_dir/'plans.json').read_text())['plans'];byid={r['id']:r for r in plans}
    replay=json.loads((a.replay_dir/'cases.json').read_text());assert set(byid)==set(fresh)=={r['id'] for r in replay}
    table={}
    for cohort in ('original','external'):
        cohortrows=[r for r in replay if r['cohort']==cohort]
        if not cohortrows:continue
        selected=[r for r in cohortrows if byid[r['id']]['precision_lower_exact']==byid[r['id']]['precision_upper_exact']=='1/2']
        expected=165 if cohort=='original' else 57;assert len(selected)==expected
        assert all(r['adaptive_success']==1 for r in selected)
        numerator=sum(r['precision_batch_success_probability'] for r in selected)
        assert numerator==(108 if cohort=='original' else 37)
        full=[r for r in fresh.values() if r['cohort']==cohort]
        table[cohort]={'complete_blocks':len(full),'matched_half_blocks':len(selected),'adaptive_matched_success_count':len(selected),
            'matched_batch_expected_success_count':numerator,'matched_batch_success_percent':100*numerator/len(selected),
            'adaptive_full_success_count':sum(float(r['adaptive_recorded_success']) for r in full),
            'fixed_full_success_count':sum(float(r['det_batch_recorded_success']) for r in full),
            'greedy_full_success_count':sum(float(r['greedy_recorded_success']) for r in full),
            'matched_case_ids':[r['id'] for r in selected]}
    certificate=json.loads((a.precision_dir/'independent_check.json').read_text());adaptive=json.loads((a.precision_dir/'adaptive_half_check.json').read_text())
    assert certificate['status']==adaptive['status']=='PASS'
    assert certificate['plan_sha256']==adaptive['precision_plans_sha256']==sha(a.precision_dir/'plans.json')
    assert adaptive['checks']['matched_half_cases']==sum(v['matched_half_blocks'] for v in table.values())
    replaycheck=json.loads((a.replay_dir/'independent_replay_check.json').read_text());assert replaycheck['status']=='PASS'
    result={'status':'PASS','cohort':a.cohort,'tables':table,'all_case_ledger_rows_compared':len(fresh),
        'maximum_ledger_numeric_difference':maxdiff,'numeric_fields_with_different_serialization':numeric,
        'exact_certificate_checks':certificate['checks'],'adaptive_certificate_checks':adaptive['checks'],
        'independent_recorded_replay_checks':replaycheck,
        'scope':'Complete cohorts compared case-by-case before reporting matched subsets. Exact half optimum combines all-domain lower and adverse upper certificates; recorded success is a distinct calculation.',
        'source_sha256':sha(Path(__file__)),'inputs_sha256':{str(p):sha(p) for p in [ref,a.shared_dir/'empirical_cases.csv',a.precision_dir/'plans.json',a.precision_dir/'independent_check.json',a.precision_dir/'adaptive_half_check.json',a.replay_dir/'cases.json',a.replay_dir/'independent_replay_check.json']}}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['tables','independent_recorded_replay_checks','inputs_sha256']},indent=2))
if __name__=='__main__':main()
