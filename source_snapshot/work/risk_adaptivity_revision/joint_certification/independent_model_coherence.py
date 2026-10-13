"""Check that all six contrast vectors arise from the same four model vectors."""
import argparse,hashlib,json,itertools
from collections import defaultdict
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cohort',choices=['external','all'],default='external')
parser.add_argument('--results-dir',type=Path)
parser.add_argument('--output',type=Path)
args=parser.parse_args()
results=args.results_dir or HERE/('empirical_external_results' if args.cohort=='external' else 'empirical_results')
report=json.loads((results/'empirical_report.json').read_text())
groups=defaultdict(list)
for name,item in report['inputs'].items():
    if name in ('original_endpoints','external_counters'):continue
    for r in json.loads((ROOT/Path(item['path'].replace(chr(92),'/'))).read_text())['cases']:
        groups[(r['meter'],r['day'],r['start_hour'])].append(r)
maximum_error=0.;forecast_error=0.;minimum_width=float('inf');maximum_width=0.;external_pairs=0
for key,rows in groups.items():
    names=sorted(set(r['model_a'] for r in rows)|set(r['model_b'] for r in rows));base=names[0]
    assert len(names)==4 and len(rows)==6
    assert {frozenset((r['model_a'],r['model_b'])) for r in rows}=={frozenset(q) for q in itertools.combinations(names,2)}
    relative={base:[0.]*6}
    for r in rows:
        if r['model_a']==base:relative[r['model_b']]=r['c']
        elif r['model_b']==base:relative[r['model_a']]=[-v for v in r['c']]
    for r in rows:
        maximum_error=max(maximum_error,max(abs(v-(b-a)) for v,a,b in zip(r['c'],relative[r['model_a']],relative[r['model_b']])))
        if 'forecast_a' in r:
            external_pairs+=1
            forecast_error=max(forecast_error,max(abs(v-(b-a)/3) for v,a,b in zip(r['c'],r['forecast_a'],r['forecast_b'])))
        minimum_width=min(minimum_width,r['W0']);maximum_width=max(maximum_width,r['W0'])
assert len(groups)==(279 if args.cohort=='external' else 1098) and maximum_error<1e-12 and forecast_error<1e-12
output={'status':'PASS','blocks':len(groups),'six_pair_cases':6*len(groups),'external_forecast_pairs_checked':external_pairs,
        'max_six_pair_affine_coherence_error':maximum_error,'external_saved_forecast_coefficient_error':forecast_error,
        'minimum_initial_width':minimum_width,'maximum_initial_width':maximum_width,'tolerance':1e-12,
        'scope':'Checks six-pair consistency; independently recomputes external c=(forecast_b-forecast_a)/3 from the already frozen geometry export. Does not refit or independently regenerate the original saved forecasts.',
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output_path=args.output or HERE/('independent_model_coherence_external.json' if args.cohort=='external' else 'independent_model_coherence_all.json')
output_path.parent.mkdir(parents=True,exist_ok=True)
output_path.write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
