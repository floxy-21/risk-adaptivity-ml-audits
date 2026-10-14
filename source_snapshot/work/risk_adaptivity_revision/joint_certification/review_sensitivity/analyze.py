"""Exploratory threshold replay of unchanged policies and continuum-gap audit.

Run from any directory. No optimization, forecasting, network access, or hidden
record selection occurs. The input preserves saved choices and policy weights.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
THRESHOLDS = ['2/5', '9/20', '1/2', '11/20', '3/5']
POLICIES = ['adaptive', 'fixed', 'greedy', 'randomized_mean', 'randomized_half_precision']
BASELINES = POLICIES[1:]
SEED = 20261013
DRAWS = 2000
TOL = F(1, 10**8)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf8')


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def quantiles(values):
    a = np.array([float(v) for v in values])
    return dict(zip(['min', 'q25', 'median', 'q75', 'max'], map(float, np.quantile(a, [0, .25, .5, .75, 1], method='linear'))))


def gap_summary(rows, cohort, subset):
    gaps = [F(r['upper']) - F(r['lower']) for r in rows]
    return {'cohort': cohort, 'subset': subset, 'blocks': len(rows),
            'systems': len({r['meter'] for r in rows}),
            'zero_gaps': sum(v == 0 for v in gaps), 'mean': float(sum(gaps) / len(gaps)),
            **quantiles(gaps),
            'gt_0_1': sum(v > F(1, 10) for v in gaps),
            'gt_0_25': sum(v > F(1, 4) for v in gaps),
            'gt_0_5': sum(v > F(1, 2) for v in gaps),
            'equal_1': sum(v == 1 for v in gaps),
            'histogram_exact': dict(sorted(Counter(map(str, gaps)).items(), key=lambda p: F(p[0])))}


def paired_summary(rows, baseline, cohort, meter, threshold, draws, days):
    a = np.array([float(F(r['success']['adaptive'])) for r in rows])
    b = np.array([float(F(r['success'][baseline])) for r in rows])
    numerator = np.array([sum(float(F(r['success']['adaptive'])) - float(F(r['success'][baseline])) for r in rows if r['day'] == day) for day in days])
    denominator = np.array([sum(r['day'] == day for r in rows) for day in days])
    estimates = 100 * numerator[draws].sum(axis=1) / denominator[draws].sum(axis=1)
    return {'cohort': cohort, 'meter': meter, 'threshold': threshold, 'baseline': baseline,
            'blocks': len(rows), 'systems': len({r['meter'] for r in rows}), 'calendar_days': len(days),
            'adaptive_success_count': float(a.sum()), 'baseline_success_count': float(b.sum()),
            'adaptive_percent': float(100 * a.mean()), 'baseline_percent': float(100 * b.mean()),
            'difference_pp': float(100 * (a-b).mean()),
            'both_success': float((a*b).sum()), 'adaptive_only': float((a*(1-b)).sum()),
            'baseline_only': float(((1-a)*b).sum()), 'neither': float(((1-a)*(1-b)).sum()),
            'lower_95': float(np.quantile(estimates, .025, method='linear')),
            'upper_95': float(np.quantile(estimates, .975, method='linear')),
            'expected_counts': baseline.startswith('randomized')}


def run(input_path, output):
    output.mkdir(parents=True, exist_ok=True)
    data = json.loads(input_path.read_text(encoding='utf8'))
    rows = data['cases']
    assert len(rows) == len({r['id'] for r in rows}) == 1098
    assert Counter(r['cohort'] for r in rows) == {'original': 819, 'external': 279}
    gaps = []
    for cohort in ['original', 'external']:
        panel = [r for r in rows if r['cohort'] == cohort]
        gaps.append(gap_summary(panel, cohort, 'all'))
        gaps.append(gap_summary([r for r in panel if F(r['upper']) > F(r['lower'])], cohort, 'unresolved'))
    flat_gaps = [{k:v for k,v in r.items() if k != 'histogram_exact'} for r in gaps]
    write_csv(output / 'continuum_gaps.csv', flat_gaps)
    dump(output / 'continuum_gaps.json', gaps)

    outcomes, strict_outcomes, boundary_changes = [], [], []
    for row in rows:
        widths = list(map(F, row['batch_widths']))
        assert len(widths) == 10 and min(widths) >= 0 and max(widths) <= 1
        weights = {name: list(map(F, row[name + '_weights'])) for name in POLICIES[3:]}
        assert all(min(pi) >= 0 and sum(pi) == 1 and len(pi) == 10 for pi in weights.values())
        for threshold in THRESHOLDS:
            strict = [int(w <= F(threshold)) for w in widths]
            success = [int(w <= F(threshold)+TOL) for w in widths]
            values = {name: F(success[row[name + '_batch_index']]) for name in POLICIES[:3]}
            values.update({name: sum(p*s for p,s in zip(pi, success)) for name,pi in weights.items()})
            exact_values = {name: F(strict[row[name + '_batch_index']]) for name in POLICIES[:3]}
            exact_values.update({name: sum(p*s for p,s in zip(pi, strict)) for name,pi in weights.items()})
            for name in POLICIES:
                if values[name] != exact_values[name]:
                    boundary_changes.append({'id':row['id'], 'cohort':row['cohort'], 'threshold':threshold,
                        'policy':name, 'primary_success_probability':str(values[name]),
                        'strict_success_probability':str(exact_values[name]),
                        'difference':str(values[name]-exact_values[name]),
                        'near_boundary_batches':[{'index':i, 'width':str(w), 'excess_above_threshold':str(w-F(threshold))}
                            for i,w in enumerate(widths) if strict[i]!=success[i]]})
            outcomes.append({k:row[k] for k in ['id', 'cohort', 'meter', 'day']} | {
                'threshold': threshold, 'success': {k:str(v) for k,v in values.items()}})
            strict_outcomes.append({k:row[k] for k in ['id', 'cohort', 'meter', 'day']} | {
                'threshold': threshold, 'success': {k:str(v) for k,v in exact_values.items()}})
    # Two exact baseline counts from the original half-width replay are invariants.
    for cohort, expected in [('original', (641, 577, 623)), ('external', (252, 221, 246))]:
        half = [r for r in outcomes if r['cohort'] == cohort and r['threshold'] == '1/2']
        assert tuple(sum(F(r['success'][p]) for r in half) for p in POLICIES[:3]) == expected
    dump(output / 'threshold_cases.json', outcomes)
    dump(output / 'strict_threshold_cases.json', strict_outcomes)
    dump(output / 'boundary_sensitivity.json', boundary_changes)
    write_csv(output / 'threshold_cases.csv', [{k:v for k,v in row.items() if k != 'success'} | row['success'] for row in outcomes])

    summaries, strict_summaries, draw_records = [], [], {}
    for cohort, stream in [('original', 0), ('external', 1)]:
        days = sorted({r['day'] for r in rows if r['cohort'] == cohort})
        generator = np.random.default_rng(np.random.SeedSequence([SEED, stream, 7]))
        starts = generator.integers(0, len(days), size=(DRAWS, (len(days)+6)//7))
        draws = ((starts[:, :, None] + np.arange(7)) % len(days)).reshape(DRAWS, -1)[:, :len(days)]
        draw_records[cohort] = {'seed_sequence': [SEED, stream, 7], 'days': days, 'indices': draws.tolist()}
        for threshold in THRESHOLDS:
            panel = [r for r in outcomes if r['cohort'] == cohort and r['threshold'] == threshold]
            for meter in ['ALL'] + sorted({r['meter'] for r in panel}):
                selected = panel if meter == 'ALL' else [r for r in panel if r['meter'] == meter]
                for baseline in BASELINES:
                    summaries.append(paired_summary(selected, baseline, cohort, meter, threshold, draws, days))
                    strict_selected = [r for r in strict_outcomes if r['cohort']==cohort and r['threshold']==threshold and (meter=='ALL' or r['meter']==meter)]
                    strict_summaries.append(paired_summary(strict_selected, baseline, cohort, meter, threshold, draws, days))
    write_csv(output / 'threshold_summary.csv', summaries)
    dump(output / 'threshold_summary.json', summaries)
    write_csv(output / 'strict_threshold_summary.csv', strict_summaries)
    dump(output / 'strict_threshold_summary.json', strict_summaries)
    dump(output / 'bootstrap_draws.json', draw_records)

    table = [r'\begin{table}[htbp]', r'\centering\small', r'\begin{tabular}{llrrr}', r'\toprule',
        r'Panel & Target & Adaptive & Fixed & Greedy\\', r'\midrule']
    for cohort in ['original', 'external']:
        for threshold in THRESHOLDS:
            group = [r for r in summaries if r['cohort'] == cohort and r['meter'] == 'ALL' and r['threshold'] == threshold]
            by = {r['baseline']:r for r in group}
            values = [by['fixed']['adaptive_percent']] + [by[name]['baseline_percent'] for name in ['fixed','greedy']]
            table.append(('Original' if cohort == 'original' else 'External') + f" & {float(F(threshold)):.2f} & " + ' & '.join(f'{x:.2f}' for x in values) + r'\\')
    table += [r'\bottomrule', r'\end{tabular}',
        r'\caption{Exploratory recorded success (\%) as the joint-width target changes. We replay the unchanged policies on all 819 original and 279 external blocks with two shared counter readings. The exact-endpoint, uncapped, noiseless replays retain the original $10^{-8}$ width-comparison tolerance. The supplement includes randomized policies, paired uncertainty summaries, and zero-tolerance sensitivity. These are recorded outcomes, not new all-completions guarantees.}',
        r'\label{tab:joint_threshold_sensitivity}', r'\end{table}']
    (output / 'threshold_table.tex').write_text('\n'.join(table) + '\n', encoding='utf8')
    report = {'status': 'PASS', 'analysis_status': 'Exploratory review-stage sensitivity of frozen policies on previously analyzed blocks.',
              'blocks': 1098, 'thresholds': THRESHOLDS, 'outcome_rows': len(outcomes), 'summary_rows': len(summaries),
              'new_forecast_fits': 0, 'new_policy_optimizations': 0, 'new_network_calls': 0,
              'threshold_comparison': 'Primary retains original replay convention J <= threshold + 1e-8. Rational widths derived from binary64 coefficients are compared to this rational cutoff; strict zero-tolerance boundary sensitivity is saved separately. Original half-width target and policies are unchanged.',
              'boundary_sensitivity_changes': len(boundary_changes),
              'strict_outcome_rows': len(strict_outcomes), 'strict_summary_rows': len(strict_summaries),
              'gap_scope': 'Continuum optimum brackets at the original half-width target only; gaps are upper minus lower probability, not measured performance gaps.',
              'policy_scope': 'Adaptive and greedy continuations, deterministic batch, and both randomized mixtures are frozen. Half-precision challenger is designed for threshold 1/2 only; no new threshold-optimality claim.',
              'uncertainty': '2,000 percentile draws (linear 2.5/97.5% quantiles), synchronized seven-day circular calendar blocks within each source; SeedSequence([20261013, source_id, 7]), PCG64; source_id 0 original, 1 external. Descriptive pointwise intervals, not simultaneous bands or population-level inference.',
              'inputs': {'path': input_path.name, 'sha256': sha(input_path), **data['sources']},
              'source_sha256': sha(Path(__file__)), 'continuum_gaps': gaps,
              'full_panel_summaries': [r for r in summaries if r['meter'] == 'ALL']}
    dump(output / 'report.json', report)
    print(json.dumps({'status': 'PASS', 'blocks': len(rows), 'outcome_rows': len(outcomes), 'gap_summaries': flat_gaps,
                      'half_width_count_check': 'PASS'}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=HERE/'frozen_inputs.json')
    p.add_argument('--output-dir', type=Path, default=HERE/'results')
    args = p.parse_args()
    run(args.input, args.output_dir)
