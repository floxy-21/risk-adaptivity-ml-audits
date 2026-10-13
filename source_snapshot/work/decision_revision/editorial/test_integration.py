"""Synthetic branch tests only; never writes a manuscript or empirical result."""
from pathlib import Path
import copy,json,sys
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'work/external_deadline/editorial'))
from integrate_external import audit_preservation,_reorder_bibliography
from integrate_decision import integrate,POLICIES

def main():
    baseline=(BASE/'prior_release/revised_manuscript.tex').read_text(encoding='utf-8')
    fragments=[(BASE/'math'/name).read_text(encoding='utf-8') for name in ['decision_section.tex','oracle_efficiency.tex','decision_worstcase_appendix.tex']]
    summary={'eligible_households':20,'eligible_days':100,'case_count':1800,'initially_uncertified_cases':800,
             'relative_mean_reduction':.02,'descriptive_consumer_bootstrap_interval':[-.01,.05],'summaries':[]}
    oracle={'subsets_checked':9999,'summaries':[]};run={'late_strict_certified':1800}
    for name in POLICIES:
        summary['summaries'].append({'population':'initially_uncertified','policy':name,'macro_mean_requests':1.9,
                                    'B80':3,'coverage':[0,.5,.79,.95,1,1,1],'unresolved':0,'numerical_ties':0})
        oracle['summaries'].append({'population':'initially_uncertified','policy':name,'ratio_of_macro_means':1.05,
             'ratio_at_most_1_10':True,'no_finite_strict_oracle_cases':0,'all_case_strict_coverage_at_cap':1,
             'oracle_macro_mean_requests_on_same_cases':1.8,'descriptive_household_bootstrap_ratio_95':[1.02,1.08]})
    development=json.loads((BASE/'prototype/ridge_grid/summary.json').read_text())
    uniform=json.loads((BASE/'prototype/full/summary.json').read_text())
    dev_oracle=json.loads((BASE/'oracle/summary.json').read_text())
    reports=[]
    for case in ['success','large_ratio','tie_retained','adverse_mean','threshold_interval_crossing']:
        s,o=copy.deepcopy(summary),copy.deepcopy(oracle)
        if case=='large_ratio':o['summaries'][0].update(ratio_of_macro_means=1.2,ratio_at_most_1_10=False)
        if case=='tie_retained':
            o['summaries'][0].update(no_finite_strict_oracle_cases=1,all_case_strict_coverage_at_cap=.99)
            s['summaries'][0]['numerical_ties']=1
        if case=='adverse_mean':s['relative_mean_reduction']=-.02
        if case=='threshold_interval_crossing':
            s['eligible_households']=19
            o['summaries'][0]['descriptive_household_bootstrap_ratio_95']=[1.02,1.14]
        text,details=integrate(baseline,*fragments,s,o,run,development,uniform,dev_oracle)
        text=_reorder_bibliography(text)
        preserved=audit_preservation(baseline,text)
        assert details['primary_criterion_met']==(case in ['success','adverse_mean','threshold_interval_crossing'])
        assert 150<=details['abstract_rough_words']<=250
        assert r'artificial intelligence; machine learning; model evaluation;' in text
        if case=='adverse_mean':assert r'2.00\% higher requests' in text
        if case=='threshold_interval_crossing':
            assert 'crosses 1.10' in text and r'\texttt{MAC000028}' in text
        reports.append({'synthetic_branch':case,**details,'preservation':preserved})
    report={'status':'passed','scope':'Five artificial editorial fixtures only; no new empirical result or manuscript written','checks':reports}
    (HERE/'integration_test.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'passed','branches':5,'abstract_words':[r['abstract_rough_words'] for r in reports],
                      'baseline_named_environments_preserved':reports[0]['preservation']['original_named_environments_preserved']},indent=2))

if __name__=='__main__':main()
