"""Optional independent source, exact-loss and outer-total audit.

Does not import the coherent-input builder, planner or retrieval gate. Replays
the documented CSV parsing, checks the saved model vectors, and evaluates
squared loss directly at every simplex vertex. No withheld within-block
counter increments or realized model-ranking outcomes enter this check.
Original daily benchmark forecasts are generated from their permitted prior-day
counter inputs; they are not claimed to be a preserved production forecast log.
The default cached replay does not invoke this raw-source path. Supply a full
workspace with the pinned forecast and source files; --chain-dir can redirect
the original raw-source regeneration output. This does not refit any models.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter,defaultdict
import argparse,csv,hashlib,json,time
import pandas as pd

HERE=Path(__file__).resolve().parent
MODELS=['daily','ridge','hist_gradient_boosting','mlp']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=HERE.parents[2],help='Full source workspace, not the smaller saved-response replay directory.')
    parser.add_argument('--chain-dir',type=Path,help='Optional full-chain run root containing original_raw/prepared/data_blem_hourly_endpoints.csv.')
    parser.add_argument('--out',type=Path,default=HERE/'source_check_results',help='Directory for this optional check only.')
    args=parser.parse_args();ROOT=args.workspace.resolve()
    SOURCE=HERE/'inputs/public_decision_inputs_coherent.json'
    ORIGINAL=ROOT/'outputs/review_frozen_forecasts.csv'
    EXTERNAL=ROOT/'work/risk_adaptivity_revision/external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv'
    chain=args.chain_dir or ROOT/'work/final_chain_20261014T031901Z/run'
    OCOUNTERS=chain/'original_raw/prepared/data_blem_hourly_endpoints.csv'
    ECOUNTERS=ROOT/'work/risk_adaptivity_revision/external_heatpump/hourly/train_test_hourly_counters.csv'
    TRAINING=ROOT/'work/risk_adaptivity_revision/joint_certification/review_mechanism/executed/training_scales.json'
    PROTOCOL=ROOT/'work/risk_adaptivity_revision/joint_certification/decision_tolerance_probe/protocol.json'
    needed_files=[SOURCE,ORIGINAL,EXTERNAL,OCOUNTERS,ECOUNTERS,TRAINING,PROTOCOL,ROOT/'outputs/review_frozen_forecasts.json']
    absent=[str(p) for p in needed_files if not p.is_file()]
    if absent:raise FileNotFoundError('Optional raw-source audit needs these pinned files; use --workspace/--chain-dir: '+', '.join(absent))
    args.out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();data=json.loads(SOURCE.read_text());cases=data['cases']
    expected_sources={name.replace('\\','/'):digest for name,digest in data['source_sha256'].items()}
    for path,suffix in [(ORIGINAL,'outputs/review_frozen_forecasts.csv'),(EXTERNAL,'external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv'),(OCOUNTERS,'original_raw/prepared/data_blem_hourly_endpoints.csv')]:
        expected=next(digest for name,digest in expected_sources.items() if name.endswith(suffix))
        assert sha(path)==expected,('Pinned source changed',str(path))
    assert sha(ORIGINAL)==json.loads((ROOT/'outputs/review_frozen_forecasts.json').read_text())['output_sha256']
    assert sha(EXTERNAL)=='04dc64193fbcf00879e4f7ba5224d5626def79a8caad474fb3242d3d8d69b12f'
    assert sha(ECOUNTERS)=='b66ed33d2b1b00ac680bf564c3329231317b8176b7e88ac318ee0714494077da'
    training_pin=next(v for k,v in json.loads(PROTOCOL.read_text())['inputs'].items() if k.endswith('review_mechanism/executed/training_scales.json'))
    assert sha(TRAINING)==training_pin
    training=json.loads(TRAINING.read_text())['systems']
    orig=pd.read_csv(ORIGINAL,usecols=['cohort','meter','timestamp',*MODELS])
    orig=orig[orig.cohort=='blem_counters'].copy();orig['time']=pd.to_datetime(orig.timestamp,utc=True)
    missing={(r.meter,r.time-pd.Timedelta(days=1)) for r in orig[orig.daily.isna()].itertuples()}
    needed={cohort:set() for cohort in ['original','external']}
    for c in cases:
        t=pd.Timestamp(c['day'],tz='UTC')+pd.Timedelta(hours=c['start_hour'])
        needed[c['cohort']].update([(c['meter'],t),(c['meter'],t+pd.Timedelta(hours=6))])
    coarse=defaultdict(dict);prior={}
    with OCOUNTERS.open(newline='') as f:
        for r in csv.DictReader(f):
            t=pd.Timestamp(r['interval_start_utc']);meter=r['meter'];key=(meter,t)
            if key in missing:prior[key]=(int(r['end_counter_integer'])-int(r['start_counter_integer']))/10**10
            if key in needed['original']:
                v=F(int(r['start_counter_integer']),10**10)
                if key in coarse['original']:assert coarse['original'][key]==v
                coarse['original'][key]=v
            key=(meter,t+pd.Timedelta(hours=1))
            if key in needed['original']:
                v=F(int(r['end_counter_integer']),10**10)
                if key in coarse['original']:assert coarse['original'][key]==v
                coarse['original'][key]=v
    assert set(prior)==missing
    for idx,r in orig[orig.daily.isna()].iterrows():orig.at[idx,'daily']=prior[r.meter,r.time-pd.Timedelta(days=1)]
    ext=pd.read_csv(EXTERNAL,usecols=['meter','timestamp_utc',*MODELS],float_precision='round_trip')
    ext['time']=pd.to_datetime(ext.timestamp_utc,utc=True)
    with ECOUNTERS.open(newline='') as f:
        for r in csv.DictReader(f):
            key=('hpm_'+r['system_id'],pd.Timestamp(r['timestamp_utc']))
            if key in needed['external']:
                assert r['valid']=='1';coarse['external'][key]=F(r['counter_kwh'])
    assert all(set(coarse[c])==needed[c] for c in needed)
    vectors={}
    for cohort,frame in [('original',orig),('external',ext)]:
        for r in frame.itertuples():
            key=(cohort,r.meter,r.time);assert key not in vectors
            vectors[key]={m:F.from_float(float(getattr(r,m))) for m in MODELS}
    output=[];pairchecks=vertexchecks=vectorchecks=0;qualified_count=Counter();systems=Counter()
    for case in cases:
        ident=case['id'];cohort=case['cohort'];meter=case['meter'];n=6
        t=pd.Timestamp(case['day'],tz='UTC')+pd.Timedelta(hours=case['start_hour'])
        E=coarse[cohort][meter,t+pd.Timedelta(hours=6)]-coarse[cohort][meter,t]
        assert E==F(case['E']) and E>0
        M2=F(training[cohort+'/'+meter]['second_moment_exact']);assert M2==F(case['training_M2'])
        eps=M2/100;assert eps==F(case['epsilon'])
        vv={m:[vectors[cohort,meter,t+pd.Timedelta(hours=h)][m] for h in range(n)] for m in MODELS}
        for m in MODELS:
            assert vv[m]==list(map(F,case['forecast_vectors'][m]));vectorchecks+=n
        # Direct squared losses at all six allowed vertices; no affine-bound
        # implementation reused here. Common E^2 terms cancel in comparisons.
        losses={m:[sum((p-(E if h==vertex else 0))**2 for h,p in enumerate(vv[m]))/n
                   for vertex in range(n)] for m in MODELS}
        directed={}
        for p in case['pairs']:
            a,b=p['model_a'],p['model_b'];coeff=list(map(F,p['c']));offset=F(p['d'])
            assert coeff==[(vv[b][h]-vv[a][h])/3 for h in range(n)]
            assert offset==sum(x*x-y*y for x,y in zip(vv[a],vv[b]))/n;pairchecks+=1
            differences=[x-y for x,y in zip(losses[a],losses[b])]
            assert differences==[offset+E*c for c in coeff];vertexchecks+=n
            directed[a,b]=max(differences);directed[b,a]=-min(differences)
        risks={m:max([F(0)]+[directed[m,q] for q in MODELS if q!=m]) for m in MODELS}
        qualified=sorted(m for m in MODELS if risks[m]<=eps);gate=bool(qualified)
        qualified_count[cohort]+=gate;systems[cohort+'/'+meter]+=gate
        output.append({'id':ident,'cohort':cohort,'meter':meter,'zero_retrieval':gate,
                       'qualified_models':'|'.join(qualified),'minimum_upper_regret':str(min(risks.values())),
                       'epsilon':str(eps),'total':str(E)})
    with (args.out/'independent_gate_cases.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    counts={cohort:{'cases':sum(c['cohort']==cohort for c in cases),'zero_retrieval':qualified_count[cohort],
                    'retrieval_required':sum(c['cohort']==cohort for c in cases)-qualified_count[cohort]}
            for cohort in sorted(qualified_count)}
    report={'status':'PASS','scope':__doc__,'cohorts':counts,'per_system_zero_retrieval':dict(systems),
            'forecast_coordinates_checked':vectorchecks,'pair_formulas_checked':pairchecks,
            'direct_vertex_loss_differences_checked':vertexchecks,'outer_totals_checked':len(cases),
            'persistence_previous_day_fills':len(missing),'seconds':time.perf_counter()-started,
            'pins':{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):sha(p) for p in [SOURCE,ORIGINAL,EXTERNAL,OCOUNTERS,ECOUNTERS,TRAINING,PROTOCOL,Path(__file__)]}}
    (args.out/'independent_gate_math_check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='pins'},indent=2))
if __name__=='__main__':main()
