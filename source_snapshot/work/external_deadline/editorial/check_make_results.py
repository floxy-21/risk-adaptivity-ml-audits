"""Synthetic editorial gating/wording checks; no real outcomes are opened."""
from pathlib import Path
import hashlib
import json
import tempfile

import pandas as pd

from make_results import POLICIES, generate


HERE = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root, budgets, crossing_curves=False):
    ext = root/'work/external_deadline'
    fd = ext/'fitted'
    fd.mkdir(parents=True)
    (ext/'summarize.py').write_text('# EXPLICIT SYNTHETIC FIXTURE ONLY\n')
    write_json(fd/'frozen_config.json', {'household_ids': ['fixture_A', 'fixture_B']})
    pd.DataFrame([{'household_id':'fixture_A','period':period,'eligible':True}
                  for period in ('validation','test') for _ in range(2)]).to_csv(fd/'candidate_days.csv', index=False)
    for name in ('forecast_archive.csv', 'reference_targets.csv'):
        (fd/name).write_text('EXPLICIT SYNTHETIC FIXTURE ONLY\n')
    fit = {'status':'passed','model_fit_count':6,
           'households':[{'household_id':h,'training_days':n,'models':[{'warnings':[]} for _ in range(3)]}
                         for h,n in [('fixture_A',30),('fixture_B',40)]],
           'output_hashes':{p.name:sha(p) for p in fd.glob('*.csv')}}
    write_json(fd/'fit_metadata.json',fit)
    for period in ('validation','test'):
        rd=ext/period;rd.mkdir()
        for name in ('cases.csv','trajectories.jsonl','archive_snapshots.json'):
            (rd/name).write_text('EXPLICIT SYNTHETIC FIXTURE ONLY\n')
        curves=[];costs=[]
        for subgroup in ('all','learned'):
            for population in ('all','initially_unresolved'):
                for p in POLICIES:
                    first=budgets[p]
                    for b in range(7):
                        rate=(0.0 if b==0 else min(.79,b*.12)) if first is None else (min(.79,b*.15) if b<first else min(1.,.8+.04*(b-first)))
                        if crossing_curves and p in ('exact','greedy'):
                            if b==2:rate=.77 if p=='exact' else .75
                            elif b==3:rate=.78
                            elif b==4:rate=.995 if p=='exact' else .996
                            elif b>=5:rate=1.
                        if population=='all':rate=.25+.75*rate
                        curves.append(dict(subgroup=subgroup,regime='early',policy=p,population=population,budget=b,
                                           cases=36 if population=='all' else 27,households=1,
                                           excluded_zero_denominator_households=0,coverage=rate,pooled_coverage=rate))
                    costs.append(dict(subgroup=subgroup,regime='early',policy=p,population=population,
                                      household_macro_mean_requests=float(first or 6),unresolved_at_stop=0,
                                      numerical_tie_stops=0,exact_reference_ties=0,near_reference_ties=0,
                                      pooled_median_requests=2.,unresolved_at_cap=0,
                                      planning_seconds_mean_case=.001,planning_seconds_p95_case=.002))
                for b in range(7):
                    curves.append(dict(subgroup=subgroup,regime='late',policy='free_archive',population=population,budget=b,
                                       cases=36 if population=='all' else 0,households=1 if population=='all' else 0,
                                       excluded_zero_denominator_households=0 if population=='all' else 1,
                                       coverage=1. if population=='all' else None,pooled_coverage=1. if population=='all' else None))
                costs.append(dict(subgroup=subgroup,regime='late',policy='free_archive',population=population,
                                  household_macro_mean_requests=0.,unresolved_at_stop=0,numerical_tie_stops=0,
                                  exact_reference_ties=0,near_reference_ties=0))
        c=pd.DataFrame(curves)
        c.to_csv(rd/'coverage_curves.csv',index=False)
        c.to_csv(rd/'independent_curves.csv',index=False)
        pd.DataFrame(costs).to_csv(rd/'cost_summary.csv',index=False)
        for name in ('household_curves.csv','pair_curves.csv','month_curves.csv'):
            (rd/name).write_text('EXPLICIT SYNTHETIC FIXTURE ONLY\n')
        ex=budgets['exact'];finite=[budgets[p] for p in ('greedy','hara') if budgets[p] is not None]
        best=min(finite) if finite else None
        reduction=(best-ex)/best if best and ex is not None else None
        cap=c[(c.subgroup=='all')&(c.regime=='early')&(c.population=='initially_unresolved')&(c.budget==6)].set_index('policy').coverage
        cap_ok=float(cap['exact'])>=max(float(cap[p]) for p in ('greedy','hara'))
        headline={'status':'passed','period':period,'B80':{'all':budgets,'learned':budgets},
                  'strongest_greedy_hara_B80':best,'exact_relative_B80_reduction':reduction,
                  'exact_no_lower_cap_coverage':cap_ok,
                  'fifteen_percent_budget_criterion_met':bool(reduction is not None and reduction>=.15 and cap_ok),
                  'uniform_has_lower_B80_than_exact':budgets['uniform'] is not None and ex is not None and budgets['uniform']<ex,
                  'counts':{'households':1,'household_days':2,'base_cases':36,'initial_unresolved_base_cases':27},
                  'households_exact_strictly_better':int(ex is not None and best is not None and ex<best),
                  'pairs_exact_strictly_better':0,'learned_pairs_exact_strictly_better':0,
                  'household_B80':[{'household_id':'fixture_A',**budgets}],
                  'pair_B80':[{'pair':'daily vs ridge',**budgets}],
                  'source_sha256':sha(rd/'cases.csv'),'summary_code_sha256':sha(ext/'summarize.py')}
        write_json(rd/'headline_summary.json',headline)
        run={'status':'passed','period':period,'households':1,'eligible_days':2,'base_cases':36,
             'outputs':{name:sha(rd/name) for name in ('cases.csv','trajectories.jsonl','archive_snapshots.json')},
             'input_hashes':{'work/external_deadline/summarize.py':sha(ext/'summarize.py')}}
        write_json(rd/'run_result.json',run)
        report={'status':'passed','period':period,'B80_household_macro':headline['B80'],
                'headline_practical_criterion_met':headline['fifteen_percent_budget_criterion_met'],
                'strict_grid_checks':'passed','imported_evaluator_or_acquisition':False,
                'base_cases':36,'eligible_days':2,'household_count':1,'fully_replayed_batches':12,
                'hashes':{str(p.relative_to(root)):sha(p) for p in [*fd.glob('*.csv'),*rd.glob('*.csv'),rd/'trajectories.jsonl',rd/'archive_snapshots.json',rd/'headline_summary.json']}}
        report.update({k:0 for k in ('bound_enclosure_failures','incorrect_certificates','timestamp_violations',
                                    'duplicate_paid_queries','cap_violations','early_missing_direct_copies')})
        write_json(rd/'independent_verification.json',report)
    return ext


def rejected(callback):
    try:
        callback()
    except (ValueError,FileNotFoundError):
        return True
    return False


def main():
    scenarios=[dict(exact=2,greedy=4,hara=4,uniform=4,randomized=4),
               dict(exact=4,greedy=2,hara=3,uniform=1,randomized=4),
               dict(exact=None,greedy=4,hara=4,uniform=3,randomized=None),
               dict(exact=4,greedy=4,hara=4,uniform=4,randomized=4)]
    records=[]
    for index,budgets in enumerate(scenarios):
        with tempfile.TemporaryDirectory(prefix='external_editorial_fixture_') as temporary:
            root=Path(temporary)
            ext=fixture(root,budgets,crossing_curves=(index==3))
            text,summary=generate(root)
            assert (text,summary)==generate(root)
            assert 150<=summary['abstract_word_count']<=250
            assert '17.45\\%' in summary['abstract_latex']
            assert '(a) All eligible comparisons' in text and '(b) Initially uncertified comparisons' in text
            assert '\\label{tab:external-costs}' in text
            assert summary['evidence']['model_fit_count']==6
            if index==0:
                assert 'criterion is met' in summary['abstract_latex']
            else:
                assert 'criterion is not met' in summary['abstract_latex']
            if index==1:
                assert "budget is lower than the exact policy's" in text
            if index==2:
                assert 'it attains 80\\% whereas the exact policy does not' in text
            if index==3:
                assert 'Neither of these two curves dominates' in text
                assert 'All five policies have $B_{80}=4$' in text
            cost=ext/'test/cost_summary.csv';original=cost.read_bytes();cost.write_bytes(original+b'\n')
            assert rejected(lambda:generate(root));cost.write_bytes(original)
            report=ext/'test/independent_verification.json';original=report.read_bytes()
            payload=json.loads(original);payload['status']='pending';write_json(report,payload)
            assert rejected(lambda:generate(root));report.write_bytes(original)
            records.append({'synthetic_scenario':index,'abstract_words':summary['abstract_word_count'],
                            'changed_summary_rejected':True,'unverified_results_rejected':True,
                            'pure_identical_output':True})
    report={'status':'passed','scope':'Synthetic editorial fixture only; no external outcomes read and no manuscript written.',
            'scenarios':records,'sha256':sha(HERE/'make_results.py')}
    write_json(HERE/'results_generator_check.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
