"""Authenticate donor-selected historical ML winners using frozen certificates.

Default input is the redistributable Portugal/French endpoint archive. No
forecast training, target acquisition, retuning, or production action occurs.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
KEYS = ['cohort','meter','gap_hours','pattern','seed','block_hours','total_tolerance','regime']
MODELS = ['daily','ridge','hist_gradient_boosting','mlp']
METHODS = ['historical_donor','paired_bounds','individual_bounds']
POLICY_TOL = 1e-9
CHECK_TOL = 1e-8


def scale_tolerance(*x):
    return POLICY_TOL * max(1.0, *(abs(v) for v in x))


def sign_interval(lo, hi):
    eps = scale_tolerance(lo, hi)
    return -1 if hi < -eps else 1 if lo > eps else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=['public','full'], default='public')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    source = args.input or ROOT/'outputs'/('study_period_archive_public_cases.csv' if args.source == 'public' else 'study_period_archive_cases.csv')
    out = args.output_dir or HERE/f'results_{args.source}'
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    groups = defaultdict(lambda: defaultdict(dict))
    input_rows = 0
    with source.open(newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            if row['regime'] != 'saved_forecast_archive_closed' or row['method'] not in METHODS:
                continue
            if float(row['total_tolerance']) not in (0, .01, .05):
                continue
            key = tuple(row[x] for x in KEYS)
            pair = row['model_a'], row['model_b']
            assert pair not in groups[key][row['method']], (key, pair, row['method'])
            groups[key][row['method']][pair] = {
                'lower': float(row['mean_lower_or_point']), 'upper': float(row['mean_upper_or_point']),
                'truth': float(row['true_mean_gap']), 'decision': int(row['decision']),
                'scale': float(row['normalization_scale']), 'denominator': int(row['full_target_denominator'])}
            input_rows += 1

    cases = []
    max_additivity_error = 0.0
    max_scaled_additivity_error = 0.0
    max_nesting_violation = 0.0
    expected_pairs = {(MODELS[i], MODELS[j]) for i in range(4) for j in range(i+1,4)}
    for key, by_method in sorted(groups.items()):
        # The frozen source exports point imputations only at zero tolerance.
        # For relaxed totals, hold that original proposal fixed; do not claim
        # a fresh donor fit/imputation under the wider information set.
        if float(key[6]) != 0:
            exact_key = (*key[:6], '0.0', key[7])
            assert 'historical_donor' not in by_method
            by_method['historical_donor'] = groups[exact_key]['historical_donor']
        assert set(by_method) == set(METHODS), (key, list(by_method))
        for method, pairs in by_method.items():
            assert set(pairs) == expected_pairs, (key, method)
            for pair, row in pairs.items():
                assert row['lower'] <= row['upper'] + CHECK_TOL*max(1,abs(row['lower']),abs(row['upper']))
                assert row['decision'] == sign_interval(row['lower'], row['upper'])
        all_rows = [row for pairs in by_method.values() for row in pairs.values()]
        assert len({row['denominator'] for row in all_rows}) == 1
        scale = all_rows[0]['scale']
        assert scale > 0 and all(row['scale'] == scale for row in all_rows)

        # Reconstruct scores only up to an irrelevant additive constant.
        # No true_mean_gap or endpoint certificate enters candidate selection.
        donor = by_method['historical_donor']
        scores = {'daily': 0.0}
        for model in MODELS[1:]:
            scores[model] = -donor[('daily',model)]['lower']
        for (a,b), row in donor.items():
            error = abs(scores[a]-scores[b]-row['lower'])
            max_additivity_error = max(max_additivity_error,error)
            scaled = error/max(1,abs(scores[a]),abs(scores[b]),abs(row['lower']))
            max_scaled_additivity_error = max(max_scaled_additivity_error,scaled)
            assert scaled <= CHECK_TOL
        candidates = []
        for model in MODELS:
            favorable = []
            for (a,b), row in donor.items():
                if model in (a,b):
                    favorable.append(row['decision'] == (-1 if model == a else 1))
            assert len(favorable) == 3
            if all(favorable):
                candidates.append(model)
        assert len(candidates) <= 1
        selected = candidates[0] if candidates else ''
        if selected:
            assert selected == min(MODELS,key=lambda model:scores[model])

        case = dict(zip(KEYS,key))
        case.update({'selected_model':selected,'unique_donor_winner':int(bool(selected)),
                     'candidate_source_total_tolerance':0.0,
                     'full_target_denominator':all_rows[0]['denominator'],
                     'training_mean_squared_scale':scale})
        for method in ['paired_bounds','individual_bounds']:
            certified = bool(selected)
            contrary = False
            minimum_advantage = float('nan')
            if selected:
                margins = []
                for (a,b), row in by_method[method].items():
                    if selected not in (a,b):
                        continue
                    needed = -1 if selected == a else 1
                    certified &= row['decision'] == needed
                    contrary |= row['decision'] == -needed
                    margins.append(-row['upper'] if selected == a else row['lower'])
                assert len(margins) == 3
                minimum_advantage = min(margins)
            case[method+'_certified'] = int(certified)
            case[method+'_contrary_certificate'] = int(contrary)
            case[method+'_minimum_advantage'] = minimum_advantage
            case[method+'_minimum_advantage_scaled'] = minimum_advantage/scale
        for pair in expected_pairs:
            paired, individual = by_method['paired_bounds'][pair], by_method['individual_bounds'][pair]
            violation = max(0.0, individual['lower']-paired['lower'], paired['upper']-individual['upper'])
            norm = max(1,abs(paired['lower']),abs(paired['upper']),abs(individual['lower']),abs(individual['upper']))
            max_nesting_violation = max(max_nesting_violation, violation/norm)
            assert violation <= CHECK_TOL*norm
            assert abs(paired['truth']-individual['truth']) <= CHECK_TOL*max(1,abs(paired['truth']))
        assert not(case['individual_bounds_certified'] and not case['paired_bounds_certified'])
        # Reference truth is inspected only after selection and certificates.
        wrong = False
        if selected:
            for (a,b), row in donor.items():
                if selected in (a,b):
                    signed = row['truth'] if selected == a else -row['truth']
                    wrong |= signed > scale_tolerance(signed)
        case['selected_model_reference_error'] = int(wrong)
        cases.append(case)

    assert input_rows == sum(18 if float(row['total_tolerance']) == 0 else 12 for row in cases)
    sensitivity_groups = defaultdict(list)
    for row in cases:
        sensitivity_groups[tuple(row[key] for key in KEYS if key != 'total_tolerance')].append(row)
    for rows in sensitivity_groups.values():
        rows.sort(key=lambda row:float(row['total_tolerance']))
        assert [float(row['total_tolerance']) for row in rows] == [0,.01,.05]
        assert len({row['selected_model'] for row in rows}) == 1
        for old,new in zip(rows,rows[1:]):
            for method in ['paired_bounds','individual_bounds']:
                assert new[method+'_certified'] <= old[method+'_certified']
                if old['unique_donor_winner']:
                    margin_old,margin_new = old[method+'_minimum_advantage'],new[method+'_minimum_advantage']
                    assert margin_new <= margin_old+CHECK_TOL*max(1,abs(margin_old),abs(margin_new))
    with (out/'case_ledger.csv').open('w',newline='',encoding='utf-8') as handle:
        writer = csv.DictWriter(handle,fieldnames=list(cases[0]))
        writer.writeheader()
        writer.writerows(cases)
    summary = []
    for cohort,tolerance in sorted({(row['cohort'],row['total_tolerance']) for row in cases}):
        rows = [r for r in cases if (r['cohort'],r['total_tolerance']) == (cohort,tolerance)]
        n = len(rows)
        paired = sum(r['paired_bounds_certified'] for r in rows)
        separate = sum(r['individual_bounds_certified'] for r in rows)
        by_meter = defaultdict(list)
        for row in rows:
            by_meter[row['meter']].append(row)
        assert len({len(rr) for rr in by_meter.values()}) == 1
        difference = np.array([np.mean([r['paired_bounds_certified']-r['individual_bounds_certified'] for r in rr]) for _,rr in sorted(by_meter.items())])
        interval = None
        if len(by_meter) >= 10:
            rng = np.random.default_rng(20261012)
            draws = rng.integers(0,len(difference),size=(2000,len(difference)))
            interval = (100*np.quantile(difference[draws].mean(axis=1),[.025,.975])).tolist()
        margins = [r['paired_bounds_minimum_advantage_scaled'] for r in rows if r['paired_bounds_certified']]
        item = {'cohort':cohort,'total_tolerance':float(tolerance),'consumers':len(by_meter),
                'scenarios':n,'unique_donor_winners':sum(r['unique_donor_winner'] for r in rows),
                'paired_certified':paired,'separate_certified':separate,'paired_unresolved':n-paired,
                'separate_unresolved':n-separate,'additional_certified':paired-separate,
                'paired_certification_percent':100*paired/n,'separate_certification_percent':100*separate/n,
                'coverage_difference_percentage_points':100*(paired-separate)/n,
                'unresolved_case_reduction_percent':100*(paired-separate)/(n-separate) if n != separate else None,
                'paired_consumer_bootstrap_95_difference_pp':interval,
                'opposite_pair_certificates':sum(r['paired_bounds_contrary_certificate']+r['individual_bounds_contrary_certificate'] for r in rows),
                'selected_model_reference_errors':sum(r['selected_model_reference_error'] for r in rows),
                'selected_models':dict(Counter(r['selected_model'] or 'no_unique_winner' for r in rows)),
                'paired_certified_minimum_advantage_scaled_p10_median_p90':np.quantile(margins,[.1,.5,.9]).tolist() if margins else None}
        summary.append(item)
    report = {'status':'passed','source_mode':args.source,'source_path':str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
              'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'elapsed_seconds':time.perf_counter()-started,'input_rows_used':input_rows,'scenarios':len(cases),
              'policy_sign_margin':POLICY_TOL,'checking_tolerance':CHECK_TOL,
              'maximum_absolute_donor_score_additivity_error':max_additivity_error,
              'maximum_scaled_donor_score_additivity_error':max_scaled_additivity_error,
              'maximum_scaled_interval_nesting_violation':max_nesting_violation,
              'fixed_candidate_sensitivity_groups_checked':len(sensitivity_groups),
              'summary':summary,
              'scope':'Secondary analysis of the same frozen retrospective archive; not an independent replication, production replacement, forecast-accuracy gain, measured labor saving, or recovery-cost reduction.',
              'candidate_selection':'A unique historical-donor-completed MSE winner must have favorable saved donor point comparisons against all three peers. Truth is not used until validation. Nonunique preferences remain in the scenario denominator.',
              'total_tolerance_sensitivity':'The source exports donor point rows only at zero total tolerance. The 1% and 5% analyses hold that original proposed model fixed and test its certificate under widened total constraints; they do not recompute or claim a donor imputation at those tolerances.',
              'certificate_rule':'Authenticate that candidate against all three alternatives using the same-method sharp interval decisions with the existing 1e-9 scaled sign margin.',
              'margin_scale':'Minimum certified MSE advantage over the three competitors divided by the squared training-period mean kWh, already saved as normalization_scale; this is not a percentage relative to unknown test MSE.',
              'uncertainty':'2000 whole-consumer resamples of paired scenario-coverage differences, seed20261012, when at least10 consumers exist. Descriptive convenience-panel stability only; shared calendar shocks and population uncertainty are not captured.'}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    tex = []
    for row in summary:
        label = {'portugal':'Portugal','household':'French household','blem_counters':'Counters'}[row['cohort']]
        tex.append(f"{label} & {100*row['total_tolerance']:.0f}\\% & {row['scenarios']:,} & {row['paired_certified']:,} & {row['separate_certified']:,} & {row['coverage_difference_percentage_points']:.2f} \\\\")
    (out/'table_rows.tex').write_text('\n'.join(tex)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'scenarios':len(cases),'elapsed_seconds':report['elapsed_seconds'],'summary':summary},indent=2))


if __name__ == '__main__':
    main()
