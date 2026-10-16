"""Rebuild system-level tolerance context from existing frozen forecasts/targets.

This exploratory descriptive table changes no model, threshold, cohort or
policy. Only system aggregates are exported, never original fine-answer arrays.
The original source needs the separately documented pinned raw-source chain.
"""
from pathlib import Path
from fractions import Fraction as F
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import argparse, csv, hashlib, itertools, json, statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUT_PIN = '4dab6420e1a365feb9bd08d21ebb936f347c21b445848a49b898086dd8029230'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00')).astimezone(timezone.utc)


def start(case):
    return datetime.fromisoformat(case['day']).replace(tzinfo=timezone.utc) + timedelta(hours=case['start_hour'])


def summarize(records):
    groups = defaultdict(list)
    for r in records:
        groups[r['cohort'], r['meter']].append(r)
    output = []
    for (cohort, meter), rows in sorted(groups.items(), key=lambda x: (x[0][0] != 'original', x[0][1])):
        assert len({r['epsilon'] for r in rows}) == 1
        epsilon = rows[0]['epsilon']
        best = [min(r['losses'].values()) for r in rows]
        spread = [max(r['losses'].values()) - min(r['losses'].values()) for r in rows]
        pair_gap = [abs(a-b) for r in rows for a, b in itertools.combinations(r['losses'].values(), 2)]
        pooled = [value for r in rows for value in r['losses'].values()]
        metrics = {
            'epsilon_kwh2': epsilon,
            'median_block_best_mse_kwh2': statistics.median(best),
            'median_block_model_mse_spread_kwh2': statistics.median(spread),
            'median_pooled_model_mse_kwh2': statistics.median(pooled),
            'median_pooled_absolute_pair_gap_kwh2': statistics.median(pair_gap),
        }
        output.append({
            'cohort': cohort, 'meter': meter, 'blocks': len(rows),
            'models_per_block': 4, 'pairs_per_block': 6,
            'all_four_models_within_epsilon_blocks': sum(v <= epsilon for v in spread),
            'at_least_two_models_within_epsilon_blocks': sum(
                sum(v - min(r['losses'].values()) <= epsilon for v in r['losses'].values()) >= 2
                for r in rows),
            'exact': {k: str(v) for k, v in metrics.items()},
            'decimal': {k: float(v) for k, v in metrics.items()},
            'median_each_model_mse_kwh2': {
                m: str(statistics.median([r['losses'][m] for r in rows]))
                for m in sorted(rows[0]['losses'])},
        })
    return output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chain-dir', type=Path, required=True,
                    help='Completed pinned source chain, containing original_raw/prepared/.')
    ap.add_argument('--out', type=Path, default=HERE/'inputs/tolerance_scale_summary.json')
    args = ap.parse_args()
    source = HERE/'inputs/public_decision_inputs_coherent.json'
    assert sha(source) == INPUT_PIN
    data = json.loads(source.read_text()); cases = data['cases']
    raw = args.chain_dir/'original_raw/prepared/data_blem_hourly_endpoints.csv'
    expected = next(v for k, v in data['source_sha256'].items()
                    if k.replace('\\', '/').endswith('original_raw/prepared/data_blem_hourly_endpoints.csv'))
    assert sha(raw) == expected, 'Original source differs from pinned chain'
    original = {}
    needed_original = {(c['meter'], start(c)+timedelta(hours=h))
                       for c in cases if c['cohort']=='original' for h in range(6)}
    with raw.open(newline='') as f:
        for r in csv.DictReader(f):
            key = r['meter'], stamp(r['interval_start_utc'])
            if key not in needed_original:
                continue
            value = F(int(r['end_counter_integer']) - int(r['start_counter_integer']), 10**10)
            assert value >= 0
            assert key not in original
            original[key] = value
    assert set(original) == needed_original
    plan = json.loads((HERE/'http_probe/request_plan.json').read_text())
    log = json.loads((HERE/'http_probe/http_log.json').read_text())
    public = {}; response_pins = {}
    for request, entry in zip(plan['requests'], log['records']):
        if request['role'] != 'whole_hourly':
            continue
        path = HERE/'http_probe'/f"response_{entry['sequence']:02d}.json"
        assert sha(path) == entry['response_sha256'] and request['url'] == entry['url']
        readings = json.loads(path.read_text(), parse_float=F)['heatpump_elec_kwh']
        public[request['meter']] = {int(t): F(v) for t, v in readings}
        response_pins[path.relative_to(HERE).as_posix()] = sha(path)
    records = []; checks = 0
    for c in cases:
        t = start(c)
        if c['cohort'] == 'original':
            y = [original[c['meter'], t + timedelta(hours=h)] for h in range(6)]
        else:
            ts = int(t.timestamp()); counter = public[c['meter']]
            y = [counter[ts+(h+1)*3600] - counter[ts+h*3600] for h in range(6)]
        assert min(y) >= 0 and sum(y) == F(c['E'])
        epsilon = F(c['training_M2'])/100
        assert epsilon == F(c['epsilon'])
        losses = {m: sum((F(v)-target)**2 for v, target in zip(vectors, y))/6
                  for m, vectors in c['forecast_vectors'].items()}
        assert len(losses) == 4
        for p in c['pairs']:
            contrast = F(p['d']) + sum(F(v)*target for v, target in zip(p['c'], y))
            assert contrast == losses[p['model_a']] - losses[p['model_b']]
            checks += 1
        records.append({'id': c['id'], 'cohort': c['cohort'], 'meter': c['meter'],
                        'epsilon': epsilon, 'losses': losses})
    assert len(records) == 1098 and checks == 6588
    result = {
        'status': 'PASS', 'scope': __doc__, 'cases': len(records),
        'model_losses_evaluated': len(records)*4,
        'exact_paired_loss_checks': checks,
        'selection': 'All 819 original and 279 external existing blocks; no replacements.',
        'tolerance_factor': '1/100', 'units': 'kWh squared',
        'definitions': {
            'median_block_best_mse_kwh2': 'Median across blocks of the smallest of four realized block MSEs; descriptive hindsight reference, not one deployable model.',
            'median_block_model_mse_spread_kwh2': 'Median across blocks of maximum minus minimum realized MSE among the same four fixed models.',
            'median_pooled_model_mse_kwh2': 'Median of all four realized model MSEs pooled across blocks within one system.',
            'median_pooled_absolute_pair_gap_kwh2': 'Median absolute MSE difference over all six model pairs pooled across blocks within one system.',
            'all_four_models_within_epsilon_blocks': 'Number of blocks where maximum minus minimum realized model MSE is at most epsilon. This uses reference targets and is not a no-query certificate count.',
        },
        'systems': summarize(records),
        'source_sha256': {
            'inputs/public_decision_inputs_coherent.json': sha(source),
            'original_raw/prepared/data_blem_hourly_endpoints.csv': sha(raw),
            'http_probe/request_plan.json': sha(HERE/'http_probe/request_plan.json'),
            'http_probe/http_log.json': sha(HERE/'http_probe/http_log.json'),
            **response_pins,
        },
        'builder_sha256': sha(Path(__file__)),
        'privacy': 'Only six system-level aggregate rows are exported. No original fine-answer arrays or per-block original losses are exported.',
    }
    assert sha(raw) == expected and sha(source) == INPUT_PIN
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': 'PASS', 'cases': len(records), 'systems': result['systems']}, indent=2))


if __name__ == '__main__':
    main()
