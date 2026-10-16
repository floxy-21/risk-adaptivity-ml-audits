"""Check six-system tolerance context and generate its supplementary table.

Default: reproduce the table from pinned system aggregates and independently
recompute external metrics from bundled public API responses. With --chain-dir,
also recompute all original metrics from the pinned original raw-source chain.
No original fine-answer arrays or per-block original losses are exported.
"""
from pathlib import Path
from fractions import Fraction as F
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from decimal import Decimal
import argparse, csv, hashlib, itertools, json

HERE = Path(__file__).resolve().parent
SUMMARY_PIN = 'a8e27b093a4b6dab24e1dff9bc323c7c8b4c4a9dbacd77c065358093b6d60a34'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def median(values):
    ordered = sorted(values); k = len(ordered)//2
    return ordered[k] if len(ordered)%2 else (ordered[k-1]+ordered[k])/2


def when(c):
    return datetime.fromisoformat(c['day']).replace(tzinfo=timezone.utc)+timedelta(hours=c['start_hour'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chain-dir', type=Path, help='Optional pinned original-source chain.')
    ap.add_argument('--out', type=Path, default=HERE/'results/tolerance_scale')
    args = ap.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    summary_path = HERE/'inputs/tolerance_scale_summary.json'
    assert sha(summary_path) == SUMMARY_PIN, 'System aggregate version mismatch'
    summary = json.loads(summary_path.read_text()); pins = summary['source_sha256']
    assert summary['builder_sha256'] == sha(HERE/'build_tolerance_scale.py')
    for name, pin in pins.items():
        if not name.startswith('original_raw/'):
            assert sha(HERE/name) == pin, name
    data = json.loads((HERE/'inputs/public_decision_inputs_coherent.json').read_text())['cases']
    groups = defaultdict(list)
    for c in data:
        groups[c['cohort'],c['meter']].append(c)
    saved = {(s['cohort'],s['meter']):s for s in summary['systems']}
    assert set(saved)==set(groups) and len(saved)==6
    for key, cases in groups.items():
        s = saved[key]; n = len(cases)
        assert s['blocks']==n and s['models_per_block']==4 and s['pairs_per_block']==6
        assert n == (273 if key[0]=='original' else 93)
        eps = {F(c['epsilon']) for c in cases}; assert len(eps)==1
        assert all(F(c['epsilon'])==F(c['training_M2'])/100 for c in cases)
        assert F(s['exact']['epsilon_kwh2']) == eps.pop()
        assert all(F(v)>=0 and float(F(v))==s['decimal'][k] for k,v in s['exact'].items())
        assert 0<=s['all_four_models_within_epsilon_blocks']<=s['at_least_two_models_within_epsilon_blocks']<=n
    # Reconstruct external reference increments from public cumulative samples.
    plans = json.loads((HERE/'http_probe/request_plan.json').read_text())['requests']
    logs = json.loads((HERE/'http_probe/http_log.json').read_text())['records']
    counters = {}
    for request, log in zip(plans, logs):
        if request['role']!='whole_hourly':
            continue
        response = HERE/'http_probe'/f"response_{log['sequence']:02d}.json"
        assert sha(response)==log['response_sha256']
        rows = json.loads(response.read_text(),parse_float=Decimal)['heatpump_elec_kwh']
        counters[request['meter']] = {datetime.fromtimestamp(int(t),timezone.utc): F(v) for t,v in rows}
    raw_counters = {}
    if args.chain_dir:
        raw = args.chain_dir/'original_raw/prepared/data_blem_hourly_endpoints.csv'
        assert sha(raw)==pins['original_raw/prepared/data_blem_hourly_endpoints.csv']
        needed = {(c['meter'],when(c)+timedelta(hours=h)) for c in data if c['cohort']=='original' for h in range(7)}
        with raw.open(newline='') as f:
            for r in csv.DictReader(f):
                t = datetime.fromisoformat(r['interval_start_utc'].replace('Z','+00:00')).astimezone(timezone.utc)
                for delta, column in [(0,'start_counter_integer'),(1,'end_counter_integer')]:
                    key = r['meter'],t+timedelta(hours=delta)
                    if key in needed:
                        value = F(int(r[column]),10**10)
                        assert key not in raw_counters or raw_counters[key]==value
                        raw_counters[key] = value
        assert set(raw_counters)==needed
    checked_groups = []; evaluated = 0
    for (cohort,meter), cases in groups.items():
        if cohort=='original' and not args.chain_dir:
            continue
        all_losses = []; per_model = defaultdict(list)
        eps = F(cases[0]['epsilon'])
        for c in cases:
            t = when(c)
            cc = [raw_counters[meter,t+timedelta(hours=h)] if cohort=='original'
                  else counters[meter][t+timedelta(hours=h)] for h in range(7)]
            targets = [cc[h+1]-cc[h] for h in range(6)]
            assert min(targets)>=0 and sum(targets)==F(c['E'])
            squared_target_sum = sum(y*y for y in targets)
            losses = {}
            for m, raw_predictions in c['forecast_vectors'].items():
                predictions = list(map(F,raw_predictions))
                # Independent expanded quadratic rather than builder residuals.
                loss = (sum(p*p for p in predictions)+squared_target_sum-
                        2*sum(p*y for p,y in zip(predictions,targets)))/6
                assert loss>=0; losses[m]=loss; per_model[m].append(loss)
            all_losses.append(losses); evaluated+=1
        best = [min(r.values()) for r in all_losses]
        spreads = [max(r.values())-min(r.values()) for r in all_losses]
        exact = {
            'epsilon_kwh2':eps,
            'median_block_best_mse_kwh2':median(best),
            'median_block_model_mse_spread_kwh2':median(spreads),
            'median_pooled_model_mse_kwh2':median([v for r in all_losses for v in r.values()]),
            'median_pooled_absolute_pair_gap_kwh2':median([abs(a-b) for r in all_losses for a,b in itertools.combinations(r.values(),2)]),
        }
        s = saved[cohort,meter]
        assert exact=={k:F(v) for k,v in s['exact'].items()},(cohort,meter)
        assert {m:median(v) for m,v in per_model.items()}=={m:F(v) for m,v in s['median_each_model_mse_kwh2'].items()}
        assert sum(v<=eps for v in spreads)==s['all_four_models_within_epsilon_blocks']
        assert sum(sum(v-min(r.values())<=eps for v in r.values())>=2 for r in all_losses)==s['at_least_two_models_within_epsilon_blocks']
        checked_groups.append(cohort+'/'+meter)
    # All figures are descriptive; no new significance test or decision rule.
    def fmt(v):
        text = f'{float(F(v)):.4g}'
        if 'e' in text:
            mantissa,power = text.split('e')
            return '$'+mantissa+r'\times10^{'+str(int(power))+'}$'
        return text
    lines = [r'\begin{table}[htbp]\centering\small',
             r'\caption{Absolute tolerance and realized loss scales on the same blocks. All loss columns are in kWh$^2$. Med. MSE pools the four fixed models across blocks; best and spread are blockwise minimum and maximum-minus-minimum MSE, respectively, before taking medians. All four counts blocks whose realized spread is at most $\epsilon$; it is not a certificate count.}',
             r'\label{tab:retrieval-tolerance-scale}',r'\begin{tabular}{lrrrrr}\toprule',
             r'System & $\epsilon$ & Med. MSE & Med. best & Med. spread & All four\\\midrule']
    for s in summary['systems']:
        label = ('BLEM '+str(int(s['meter'].split('_')[-1]))) if s['cohort']=='original' else 'HPM '+s['meter'].split('_')[-1]
        values = [s['exact'][k] for k in ['epsilon_kwh2','median_pooled_model_mse_kwh2','median_block_best_mse_kwh2','median_block_model_mse_spread_kwh2']]
        lines.append(label+' & '+' & '.join(fmt(v) for v in values)+' & '+str(s['all_four_models_within_epsilon_blocks'])+'/'+str(s['blocks'])+r'\\')
    lines += [r'\bottomrule\end{tabular}\end{table}',
              r'The tolerance has different implications across systems. HPM~7 has all four models within tolerance on 44 of 93 blocks, while HPM~1 has none and has a near-zero median best-model error alongside a much larger model spread. The blockwise best MSE is a hindsight reference, not the performance of one deployable model. These summaries interpret the unchanged tolerance rather than calibrating it to an operational loss.']
    fragment='\n'.join(lines)+'\n'
    (args.out/'tolerance_scale_fragment.tex').write_text(fragment)
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    report = {
        'status':'PASS','scope':__doc__,'systems':6,'cases':1098,
        'independently_recomputed_systems':sorted(checked_groups),
        'independently_recomputed_blocks':evaluated,
        'original_system_aggregates_only':True,
        'original_raw_regeneration_performed':bool(args.chain_dir),
        'summary_sha256':sha(summary_path),'checker_sha256':sha(Path(__file__)),
        'input_sha256':sha(HERE/'inputs/public_decision_inputs_coherent.json'),
        'fragment_sha256':sha(args.out/'tolerance_scale_fragment.tex'),
        'limitations':'Default original rows replay pinned system aggregates; optional --chain-dir independently recomputes original reference losses. No new fitting, policy, threshold or inference.'}
    (args.out/'independent_check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
