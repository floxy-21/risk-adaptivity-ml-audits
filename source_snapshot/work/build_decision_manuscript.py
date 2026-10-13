"""Rebuild the decision-acquisition paper only from independently checked evidence.

--freeze pins a reviewed composition; ordinary runs require exact input/output
hash agreement. No confirmation result is inferred from development outcomes.
"""
from pathlib import Path
import argparse,csv,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'work/decision_revision'
BASELINE_SHA='86a7423c0be9dc6ff14f441f6b9583b0d587ed372b13bae130d35dcc2da0c2b3'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def local_pin(path):
    value=str(path).replace('\\','/')
    current=str(ROOT).replace('\\','/').rstrip('/')+'/'
    if value.lower().startswith(current.lower()):candidate=ROOT/value[len(current):]
    elif not re.match(r'^[A-Za-z]:|^/',value):candidate=ROOT/value
    else:
        # A copied workspace may itself live under .../work/dreplay_.../.
        # Rebase the final repository directory boundary, not that outer one.
        position=max(value.lower().rfind('/work/'),value.lower().rfind('/outputs/'))
        if position<0:raise AssertionError('Unrecognized external evidence path: '+value)
        candidate=ROOT/value[position+1:]
    candidate=candidate.resolve()
    if not candidate.is_relative_to(ROOT.resolve()):raise AssertionError('Evidence path escapes workspace: '+value)
    return candidate

def validate_pins(pins):
    resolved=[]
    for name,expected in pins.items():
        file=local_pin(name)
        if not file.is_file() or sha(file)!=expected:raise AssertionError('Evidence changed: '+str(file))
        resolved.append(file)
    return resolved

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    baseline=BASE/'prior_release/revised_manuscript.tex'
    if sha(baseline)!=BASELINE_SHA:raise AssertionError('Immutable baseline differs')
    run_dir=BASE/'confirmation';oracle_dir=BASE/'confirmation_oracle'
    paths=[BASE/'confirmation_protocol.json',run_dir/'summary.json',run_dir/'run_result.json',
           run_dir/'independent_verification.json',oracle_dir/'summary.json',
           BASE/'math/confirmation_source_check.json',BASE/'math/ridge_independent_check.json',
           BASE/'prototype/ridge_grid/summary.json',BASE/'prototype/full/summary.json',BASE/'oracle/summary.json']
    if not all(p.is_file() for p in paths):raise AssertionError('Confirmation/checker/oracle gates are not complete')
    protocol,summary,run,check,oracle,source,mathcheck,development,uniform,dev_oracle=map(read,paths)
    for name,value in zip(paths[1:],[summary,run,check,oracle,source,mathcheck,development,uniform,dev_oracle]):
        if value.get('status')!='passed':raise AssertionError('Verification gate did not pass: '+str(name))
    if summary['selected_kappa']!=protocol['selected_kappa'] or development['selected_kappa']!=protocol['selected_kappa']:
        raise AssertionError('Development selection and confirmation differ')
    if check['base_cases']!=summary['case_count'] or oracle['cases']!=summary['case_count'] or run['cases']!=summary['case_count']:
        raise AssertionError('Evidence case counts differ')
    if check.get('oracle_efficiency_primary',{}).get('oracle_summary_sha256')!=sha(oracle_dir/'summary.json'):
        raise AssertionError('Independent primary-oracle verification is absent or stale')
    if 'source_case_chronology' not in check:raise AssertionError('Independent forecast chronology check is absent')
    chronology_helper=BASE/'reviews/verify_forecast_context.py'
    if check['source_case_chronology']['chronology_checker_sha256']!=sha(chronology_helper):
        raise AssertionError('Independent chronology helper changed')
    if run['protocol_sha256']!=sha(paths[0]):raise AssertionError('Confirmation protocol changed')
    fitted_path=BASE/'confirmation_fitted/fit_metadata.json'
    fitted=read(fitted_path)
    with (run_dir/'cases.csv').open(newline='',encoding='utf-8') as rows:
        evaluated_ids={row['household_id'] for row in csv.DictReader(rows)}
    if set(protocol['selected_ids'])-evaluated_ids!={'MAC000028'} or len(evaluated_ids)!=19:
        raise AssertionError('Reported new-cohort attrition differs from verified case inventory')
    if {row['household_id'] for row in fitted['households']}!=set(protocol['selected_ids']) or fitted['model_fit_count']!=60:
        raise AssertionError('Selected consumer fitting inventory differs')
    evidence=paths+[baseline,Path(__file__),chronology_helper,fitted_path]
    for development_run in ['full','ridge_grid']:
        report_path=BASE/'prototype'/development_run/'independent_verification.json'
        report=read(report_path)
        if report['status']!='passed':raise AssertionError('Development selection verification failed')
        evidence.append(report_path)
        evidence+=validate_pins(report['inputs'])
    for pins in [protocol['input_hashes'],check['inputs'],oracle['inputs']]:evidence+=validate_pins(pins)
    checked={str(local_pin(p).resolve()).lower() for p in check['inputs']}
    for name in ['source_cases.jsonl','cases.csv','trajectories.jsonl']:
        if str((run_dir/name).resolve()).lower() not in checked:raise AssertionError('Independent checker does not pin '+name)
    for name,digest in run['outputs'].items():
        if sha(run_dir/name)!=digest:raise AssertionError('Completed run output changed: '+name)
        evidence.append(run_dir/name)
    for name,digest in oracle['outputs'].items():
        if sha(oracle_dir/name)!=digest:raise AssertionError('Oracle output changed: '+name)
        evidence.append(oracle_dir/name)
    if source['manifest_sha256']!=sha(BASE/'confirmation_source/manifest.json') or source['hourly_sha256']!=sha(BASE/'confirmation_source/hourly.csv'):
        raise AssertionError('Source verification is stale')
    sys.path.insert(0,str(BASE/'editorial'))
    from integrate_decision import integrate
    sys.path.insert(0,str(ROOT/'work/external_deadline/editorial'))
    from integrate_external import audit_preservation,_reorder_bibliography
    fragments=[BASE/'math'/name for name in ['decision_section.tex','oracle_efficiency.tex','decision_worstcase_appendix.tex']]
    evidence+=fragments+[BASE/'editorial/integrate_decision.py',ROOT/'work/external_deadline/editorial/integrate_external.py']
    scaling_root=ROOT/'work/randomized_scaling_review'
    for name in ['instances.json','summary.json','C27_compact.json','C28_compact.json']:
        evidence.append(scaling_root/name)
    for name in ['C27_compact.json','C28_compact.json']:
        scale_case=read(scaling_root/name)
        if scale_case['status']!='success' or scale_case['policy_diagnostics']['lp_dimensions']['variables']!=10076:
            raise AssertionError('Abstract scaling example differs from its raw record')
    old=baseline.read_text(encoding='utf-8')
    text,details=integrate(old,*(p.read_text(encoding='utf-8') for p in fragments),summary,oracle,run,development,uniform,dev_oracle)
    if details['primary_criterion_met']!=check['oracle_efficiency_primary']['criterion_met']:
        raise AssertionError('Manuscript primary verdict differs from independent checker')
    review_root=ROOT/'work/eligibility_review_20261011'
    sys.path.insert(0,str(review_root/'editorial'))
    from condense import condense
    text=condense(text)
    evidence.append(review_root/'editorial/condense.py')
    grid_root=ROOT/'work/certificate_grid_review'
    sys.path.insert(0,str(grid_root))
    from integrate_grid import integrate_grid
    grid_report=read(grid_root/'results_full/verification.json')
    if grid_report['script_sha256']!=sha(grid_root/'summarize_certificates.py'):
        raise AssertionError('Historical certificate-grid check is stale')
    for name,digest in grid_report['output_sha256'].items():
        if sha(grid_root/'results_full'/name)!=digest:raise AssertionError('Certificate-grid output changed: '+name)
    text=integrate_grid(text,(grid_root/'results_full/table_rows.tex').read_text(),grid_report)
    evidence.extend(grid_root/name for name in ['integrate_grid.py','summarize_certificates.py',
        'results_full/verification.json','results_full/table_rows.tex','results_full/cohort_counts.csv',
        'results_full/grid_counts.csv','results_full/grid_seed_counts.csv'])
    for relative in ['eligibility/report.json','batch/saved_batch_accounting.json','batch/batch_api_fixtures.json']:
        checked_review=read(review_root/relative)
        if checked_review['status']!='passed':raise AssertionError('Eligibility review failed: '+relative)
        evidence.append(review_root/relative)
    for relative in ['check_review.py','eligibility/check_zero_coefficient.py','batch/check_saved_batches.py','batch/check_api_fixtures.py']:
        evidence.append(review_root/relative)
    details['editorial_consolidation']='Specialized theory in main text; full decision theory, protocol, survey and interpretation retained in appendices.'
    text=_reorder_bibliography(text)
    preservation=audit_preservation(old,text)
    if not 150<=details['abstract_rough_words']<=250:raise AssertionError('Abstract length outside 150--250 words')
    content=text.encode('utf-8');output_sha=hashlib.sha256(content).hexdigest()
    pins={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(evidence))}
    release=ROOT/'outputs/decision_release_manifest.json'
    if args.freeze:
        release.write_text(json.dumps({'status':'frozen','baseline_sha256':BASELINE_SHA,'inputs':pins,
            'manuscript_sha256':output_sha,'scope':'Verified source composition; not a prediction of editorial acceptance.'},indent=2)+'\n')
    else:
        frozen=read(release)
        if frozen['inputs']!=pins or frozen['manuscript_sha256']!=output_sha:raise AssertionError('Exact release reconstruction differs')
    output=ROOT/'outputs/revised_manuscript.tex';output.write_bytes(content)
    report={'status':'passed','manuscript_sha256':sha(output),'exact_manuscript_bytes':True,**details,
            'preservation':preservation,'inputs':pins}
    (ROOT/'outputs/decision_manuscript_reconstruction.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['preservation','inputs']},indent=2))

if __name__=='__main__':main()
