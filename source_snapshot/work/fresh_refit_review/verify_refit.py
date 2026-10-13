"""Independent arithmetic comparison of a fresh same-trainer replay.

This checker never fits an estimator or imports the refit driver. Full mode
checks all 64 series; --public checks the 61 redistributable UCI series.
"""
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
import argparse
import ast
import calendar
import hashlib
import itertools
import json
import math
import traceback
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'outputs'
MODELS=['daily','ridge','hist_gradient_boosting','mlp']
KEYS=['cohort','meter','timestamp']
TRUTH_TOL=(1e-12,1e-12)
FIT_TOL=(1e-8,1e-8)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def differences(fresh,frozen,tol):
    a,b=np.asarray(fresh,dtype=float),np.asarray(frozen,dtype=float)
    assert a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all()
    error=np.abs(a-b);limit=tol[0]+tol[1]*np.abs(b)
    return {'values':int(a.size),'exact_numeric_matches':int((a==b).sum()),
            'max_absolute_error':float(error.max(initial=0.)),
            'max_error_over_declared_tolerance':float((error/limit).max(initial=0.)),
            'outside_tolerance':int((error>limit).sum())}

def require_close(a,b,tol=FIT_TOL):
    d=differences(a,b,tol)
    assert d['outside_tolerance']==0,d
    return d

def independent_dst(days):
    excluded=set()
    for year in set(days.year):
        for month in [3,10]:
            day=date(int(year),month,calendar.monthrange(int(year),month)[1])
            while day.weekday()!=6:day-=timedelta(days=1)
            excluded.update(day+timedelta(days=lag) for lag in [0,1,2,7])
    return np.asarray([t.date() in excluded for t in days])

def independent_design(series):
    # Define dependencies by timestamp lookup, rather than shifting day matrices.
    first=series.index.min().ceil('D');last=series.index.max().floor('D')
    days=pd.date_range(first,last,freq='D')
    hours=pd.DatetimeIndex([day+pd.Timedelta(hours=h) for day in days for h in range(24)])
    y=series.reindex(hours).to_numpy(dtype=float).reshape(-1,24)
    columns=[]
    for lag in [1,2,7]:
        columns.append(series.reindex(hours-pd.Timedelta(days=lag)).to_numpy(dtype=float).reshape(-1,24))
    previous=series.reindex(hours-pd.Timedelta(days=1)).to_numpy(dtype=float).reshape(-1,24).mean(axis=1)
    columns.append(np.repeat(previous[:,None],24,axis=1))
    columns.extend([np.tile([math.sin(2*math.pi*h/24) for h in range(24)],(len(days),1)),
                    np.tile([math.cos(2*math.pi*h/24) for h in range(24)],(len(days),1))])
    for period,values in [(7,days.dayofweek),(12,days.month-1)]:
        for function in [math.sin,math.cos]:
            columns.append(np.repeat(np.asarray([function(2*math.pi*int(v)/period) for v in values])[:,None],24,axis=1))
    x=np.stack(columns,axis=2)
    good=np.isfinite(y).all(axis=1)&(y>=0).all(axis=1)&np.isfinite(x).all(axis=(1,2))
    return days,x,y,good

def extract_design_functions(source):
    tree=ast.parse(source)
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['daily_design','local_dst_affected']]
    assert len(selected)==2
    namespace={'np':np,'pd':pd}
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<frozen design functions>','exec'),namespace)
    return namespace['daily_design'],namespace['local_dst_affected']

def fixture_checks(source):
    original,dst=extract_design_functions(source)
    cases=0;feature_values=0
    for start,tz in [('2014-03-01',None),('2014-10-01',None),('2017-09-01','UTC')]:
        index=pd.date_range(start,periods=60*24,freq='h',tz=tz)
        series=pd.Series(1+np.arange(len(index),dtype=float)/37,index=index)
        series.iloc[9*24+2]=np.nan;series.iloc[12*24+7]=-1.
        days,x,y,good=original(series)
        od,ox,oy,og=independent_design(series)
        assert days.equals(od);np.testing.assert_allclose(y,oy,atol=0,rtol=0,equal_nan=True)
        # The original lag construction starts at its first full day; fixtures
        # have no earlier partial day, so every represented dependency agrees.
        np.testing.assert_allclose(x,ox,atol=2e-15,rtol=2e-15,equal_nan=True)
        np.testing.assert_array_equal(good,og);np.testing.assert_array_equal(dst(days),independent_dst(days))
        target=days[35];changed=series.copy();changed.loc[target:target+pd.Timedelta(hours=23)]+=1000
        _,mutated,_,_=original(changed)
        np.testing.assert_array_equal(x[35],mutated[35])
        assert all(target-pd.Timedelta(days=lag)+pd.Timedelta(hours=23)<target for lag in [1,2,7])
        cases+=1;feature_values+=x.size
    return {'synthetic_series':cases,'feature_scalar_checks':feature_values,
            'same_day_target_perturbation_checks':cases,'dst_definition_checks':cases,
            'scope':'Independent timestamp lookup and scalar trigonometry compared with two AST-extracted frozen design helpers; no fitter executed.'}

def strict_sign(value,scale):
    return 1 if value>1e-9*max(1.,scale) else -1 if value < -1e-9*max(1.,scale) else 0

def run(public):
    started=datetime.now(timezone.utc)
    sources={}
    def read(relative):
        path=ROOT/relative;sources[relative]=sha(path)
        return json.loads(path.read_text(encoding='utf-8'))
    summary=read('outputs/study_summary.json')
    holdout=read('outputs/study_holdout_consumers.json')
    fresh=read('work/fresh_refit_review/fresh_result.json')
    prepared=read('work/fresh_refit_review/prepared.json')
    selection=read('work/fresh_refit_review/selection.json')
    fresh_metadata=read('work/fresh_refit_review/fit_metadata.json')
    sources['work/fresh_refit_review/comparison_protocol.txt']=sha(HERE/'comparison_protocol.txt')
    sources['work/fresh_refit_review/protocol.txt']=sha(HERE/'protocol.txt')
    sources['work/fresh_refit_review/refit.py']=sha(HERE/'refit.py')
    sources['work/fresh_refit_review/verify_refit.py']=sha(Path(__file__))
    trainer=OUT/'run_energy_rank_study.py';source=trainer.read_text()
    sources['outputs/run_energy_rank_study.py']=sha(trainer)
    assert sha(trainer)==summary['script_sha256']==prepared['source_hashes']['outputs/run_energy_rank_study.py']
    assert fresh['status']=='PASS' and not fresh['failures']
    assert fresh['series_completed']==64 and fresh['trained_estimators_completed']==192
    assert fresh['prediction_rows']==166536
    assert fresh['comparison_protocol_sha256']==prepared['comparison_protocol_sha256']==sha(HERE/'comparison_protocol.txt')
    assert fresh['protocol_sha256']==prepared['protocol_sha256']==sha(HERE/'protocol.txt')
    assert fresh['driver_sha256']==prepared['driver_sha256']==sha(HERE/'refit.py')
    assert fresh['source_hashes']==prepared['source_hashes']
    for relative,expected in fresh['source_hashes'].items():
        if public and relative=='outputs/study_predictions.csv':continue
        assert sha(ROOT/relative)==expected,relative
        sources[relative]=expected
    assert datetime.fromisoformat(prepared['completed_utc'])<datetime.fromisoformat(fresh['completed_utc'])
    assert fresh['config']==prepared['config'] and fresh['versions']==prepared['versions']==summary['versions']==holdout['versions']
    for name in ['cache_existed_before_preparation','old_hourly_cache_reads','model_state_reads']:
        assert fresh[name] is prepared[name] is False
    for name,h in fresh['output_hashes'].items():
        if public and name=='fresh_predictions.csv':continue
        assert sha(HERE/name)==h,name
    config=fresh['config']
    assert config['models']==MODELS and config['mlp']==summary['design']['fixed_hyperparameters']['mlp']
    assert config['ridge_alpha']==1. and config['numerical_threads']==2 and config['workers']==1
    tree=ast.parse(source)
    hgb=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='HistGradientBoostingRegressor')
    assert {kw.arg:ast.literal_eval(kw.value) for kw in hgb.keywords}==config['hgb']
    ridge=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Ridge')
    assert {kw.arg:ast.literal_eval(kw.value) for kw in ridge.keywords}=={'alpha':config['ridge_alpha']}
    mlp_assign=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MLP_PARAMETERS' for t in n.targets))
    assert json.loads(json.dumps({kw.arg:ast.literal_eval(kw.value) for kw in mlp_assign.keywords}))==config['mlp']
    original_ids=[m['meter'] for m in summary['meters'] if m['cohort']=='portugal']
    extra_ids=holdout['selection']['selected_ids']
    assert selection['original_selected_ids']==config['original_selected_ids']==original_ids
    assert selection['holdout_selected_ids']==config['holdout_selected_ids']==extra_ids
    screening=selection['screening']
    assert [r['meter'] for r in screening]==[f'MT_{i:03d}' for i in range(1,371)]
    eligible=[r['meter'] for r in screening if r['training_nonmissing_fraction']>=.99 and r['training_positive_fraction']>.95]
    assert [n for n in eligible if int(n[3:])<=80][:30]==original_ids
    assert [n for n in eligible if int(n[3:])>=81][:30]==extra_ids
    assert not set(original_ids)&set(extra_ids)
    refmeta={(m['cohort'],m['meter']):m for m in [*summary['meters'],*holdout['fit_metadata']]}
    newmeta={(m['cohort'],m['meter']):m for m in fresh_metadata}
    assert len(newmeta)==len(refmeta)==64 and set(newmeta)==set(refmeta)
    meta_checks=[]
    for key,r in refmeta.items():
        n=newmeta[key]
        assert n['status']=='passed' and n['fit_cohort']==('portugal' if key[0]=='portugal_new_consumers' else key[0])
        for field in ['train_days','test_days','train_start','train_end','test_start','test_end']:assert n[field]==r[field],(key,field)
        require_close(n['training_mean_kwh'],r['training_mean_kwh'],TRUTH_TOL)
        for field in ['epochs','warnings']:assert n['mlp_training'][field]==r['mlp_training'][field],(key,field)
        assert not n['mlp_training']['warnings'] and n['additional_warnings']==r.get('additional_warnings',[])==[]
        assert n['mlp_training']['epochs']<=config['mlp']['max_iter']
        require_close(n['mlp_training']['training_objective_loss'],r['mlp_training']['training_objective_loss'])
        require_close(n['mlp_training']['target_scale_training_mean_kwh'],r['mlp_training']['target_scale_training_mean_kwh'],TRUTH_TOL)
        for model in MODELS:require_close(n['mse'][model],r['mse'][model])
        assert pd.Timestamp(n['train_end'])<pd.Timestamp(n['test_start'])
        meta_checks.append({'cohort':key[0],'meter':key[1],'epochs':n['mlp_training']['epochs'],'train_days':n['train_days'],'test_days':n['test_days'],'warnings':[]})
    if public:
        fresh_path=HERE/'fresh_predictions_public.csv';original_path=OUT/'review_frozen_forecasts.csv'
        omission=read('work/fresh_refit_review/omission_manifest.json')
        assert omission['status']=='PASS' and omission['public_rows']==159984 and omission['public_series']==61
        assert omission['omitted_rows']==6552 and omission['omitted_series']==3 and omission['omitted_cohort']=='blem_counters'
        assert omission['public_sha256']==sha(fresh_path)
        assert omission['local_full_sha256']==fresh['output_hashes']['fresh_predictions.csv']
        public_reference=read('outputs/review_frozen_forecasts.json')
        assert public_reference['output_sha256']==sha(original_path)
        assert public_reference['original_predictions_sha256']==fresh['source_hashes']['outputs/study_predictions.csv']
    else:
        fresh_path=HERE/'fresh_predictions.csv';original_path=OUT/'study_predictions.csv'
    fresh_frame=pd.read_csv(fresh_path);original_frame=pd.read_csv(original_path)
    if public:original_frame=original_frame[original_frame.cohort!='blem_counters']
    ref=pd.concat([original_frame,pd.read_csv(OUT/'study_holdout_consumers_predictions.csv')],ignore_index=True)
    for path in [fresh_path,original_path,OUT/'study_holdout_consumers_predictions.csv']:
        sources[str(path.relative_to(ROOT)).replace('\\','/')]=sha(path)
    assert fresh_frame.columns.tolist()==ref.columns.tolist()==[*KEYS,'truth_kwh',*MODELS]
    assert not fresh_frame.duplicated(KEYS).any() and not ref.duplicated(KEYS).any()
    nf=fresh_frame.set_index(KEYS).sort_index();rf=ref.set_index(KEYS).sort_index()
    assert nf.index.equals(rf.index)
    expected_series=61 if public else 64;expected_rows=159984 if public else 166536
    assert len(nf)==expected_rows and len(nf.groupby(level=['cohort','meter']))==expected_series
    assert np.isfinite(nf.to_numpy(dtype=float)).all() and (nf.to_numpy(dtype=float)>=0).all()
    discrepancy={field:require_close(nf[field],rf[field],TRUTH_TOL if field in ['truth_kwh','daily'] else FIT_TOL) for field in nf}
    metrics=[];ranking_changes=[];metric_differences=[];rowgroups={}
    for key,n in nf.groupby(level=['cohort','meter']):
        r=rf.loc[key];n=n.droplevel(['cohort','meter']);rowgroups[key]=n
        assert len(n)==24*newmeta[key]['test_days']
        stamps=pd.DatetimeIndex(n.index)
        assert stamps[0].date().isoformat()==newmeta[key]['test_start'] and stamps[-1].date().isoformat()==newmeta[key]['test_end']
        unique_days=stamps.normalize().unique()
        assert len(unique_days)==newmeta[key]['test_days']
        assert all(len(n.loc[[s.isoformat() for s in pd.date_range(d,periods=24,freq='h')]])==24 for d in unique_days)
        if key[0] in ['portugal','portugal_new_consumers']:
            assert all(d.year==2014 and d.month in [1,4,7,10] and d.day<=28 for d in unique_days)
        elif key[0]=='household':assert all(d.year==2010 for d in unique_days)
        else:assert all(d>=pd.Timestamp('2017-10-01',tz='UTC') for d in unique_days)
        if key[0]!='blem_counters':assert not independent_dst(unique_days).any()
        n_scores=[];r_scores=[]
        for model in MODELS:
            ne=n[model].to_numpy()-n.truth_kwh.to_numpy();re=r[model].to_numpy()-r.truth_kwh.to_numpy()
            vals={'mse':(float(np.mean(ne**2)),float(np.mean(re**2))),
                  'rmse':(float(np.sqrt(np.mean(ne**2))),float(np.sqrt(np.mean(re**2)))),
                  'mae':(float(np.mean(np.abs(ne))),float(np.mean(np.abs(re))))}
            row={'cohort':key[0],'meter':key[1],'model':model,'targets':len(n)}
            for metric,(nv,rv) in vals.items():
                require_close(nv,rv);row['fresh_'+metric]=nv;row['frozen_'+metric]=rv
            row['fresh_normalized_mse']=vals['mse'][0]/newmeta[key]['training_mean_kwh']**2
            row['frozen_normalized_mse']=vals['mse'][1]/refmeta[key]['training_mean_kwh']**2
            require_close(row['fresh_normalized_mse'],row['frozen_normalized_mse'])
            require_close(vals['mse'][0],newmeta[key]['mse'][model]);require_close(vals['mse'][1],refmeta[key]['mse'][model])
            n_scores.append(vals['mse'][0]);r_scores.append(vals['mse'][1]);metrics.append(row)
        for a,b in itertools.combinations(range(4),2):
            nd=n_scores[a]-n_scores[b];rd=r_scores[a]-r_scores[b]
            ns=strict_sign(nd,abs(nd));rs=strict_sign(rd,abs(rd))
            if ns!=rs:ranking_changes.append({'cohort':key[0],'meter':key[1],'model_a':MODELS[a],'model_b':MODELS[b],'fresh_sign':ns,'frozen_sign':rs})
    fixtures=fixture_checks(source)
    actual_design=[]
    if not public:
        for relative,h in fresh['raw_source_hashes'].items():assert sha(ROOT/relative)==h
        for relative,h in prepared['hourly_files'].items():assert sha(HERE/relative)==h
        helpers,_=extract_design_functions(source);cache={}
        for job in prepared['jobs']:
            path=HERE/job['hourly_file']
            if str(path) not in cache:cache[str(path)]=pd.read_pickle(path)
            series=cache[str(path)]
            if isinstance(series,pd.DataFrame):series=series[job['meter']]
            days,x,y,good=independent_design(series)
            hdays,hx,hy,hgood=helpers(series)
            assert days.equals(hdays)
            # Independently looked-up early partial histories can exist before
            # the source helper's first full day. Neither is training eligible;
            # compare causal features from the first complete seven-day history.
            np.testing.assert_allclose(x[7:],hx[7:],atol=2e-12,rtol=2e-12,equal_nan=True)
            np.testing.assert_allclose(y,hy,atol=0,rtol=0,equal_nan=True)
            good[:7]=False;assert np.array_equal(good,hgood)
            if job['fit_cohort'] in ['portugal','household']:good &= ~independent_dst(days)
            if job['fit_cohort']=='portugal':
                tr=(days.year==2013)&good;te=(days.year==2014)&np.isin(days.month,[1,4,7,10])&(days.day<=28)&good
            elif job['fit_cohort']=='household':tr=np.isin(days.year,[2008,2009])&good;te=(days.year==2010)&good
            else:tr=(days<pd.Timestamp('2017-10-01',tz=days.tz))&good;te=(days>=pd.Timestamp('2017-10-01',tz=days.tz))&good
            key=(job['cohort'],job['meter']);meta=newmeta[key]
            assert int(tr.sum())==meta['train_days'] and int(te.sum())==meta['test_days']
            assert str(days[tr][0].date())==meta['train_start'] and str(days[tr][-1].date())==meta['train_end']
            n=rowgroups[key];expected_index=[(d+pd.Timedelta(hours=h)).isoformat() for d in days[te] for h in range(24)]
            assert list(n.index)==expected_index
            require_close(n.truth_kwh,y[te].reshape(-1),TRUTH_TOL)
            require_close(n.daily,x[te,:,0].reshape(-1),TRUTH_TOL)
            require_close(float(y[tr].mean()),meta['training_mean_kwh'],TRUTH_TOL)
            if job['fit_cohort']=='portugal':
                training=series.loc['2013'];screen=next(s for s in screening if s['meter']==job['meter'])
                assert len(training)==screen['training_hour_count']
                require_close(float(training.notna().mean()),screen['training_nonmissing_fraction'],TRUTH_TOL)
                require_close(float((training>0).mean()),screen['training_positive_fraction'],TRUTH_TOL)
            actual_design.append({'cohort':key[0],'meter':key[1],'feature_values_compared':int(hx[7:].size),
                                  'train_days':int(tr.sum()),'test_days':int(te.sum()),'target_rows':len(n)})
    scope='public' if public else 'full'
    metric_path=HERE/('independent_metrics_'+scope+'.csv')
    metric_frame=pd.DataFrame(metrics);metric_frame.to_csv(metric_path,index=False)
    cohort_metrics=[]
    metric_fields=[c for c in metric_frame if c.startswith(('fresh_','frozen_'))]
    for (cohort,model),frame in metric_frame.groupby(['cohort','model']):
        row={'cohort':cohort,'model':model,'meters':len(frame),**{c:float(frame[c].mean()) for c in metric_fields}}
        if cohort=='portugal_new_consumers':
            for metric,field in [('mse','mse_kwh2'),('rmse','rmse_kwh'),('mae','mae_kwh')]:
                require_close(row['frozen_'+metric],holdout['forecast_metrics_macro'][model][field])
        cohort_metrics.append(row)
    report={'status':'passed' if not ranking_changes else 'numerical_tolerances_passed_but_rankings_changed',
            'completed_utc':datetime.now(timezone.utc).isoformat(),'mode':scope,
            'fresh_trainer_reused':True,'independent_training_reimplementation':False,
            'rows_compared':len(nf),'series_compared':expected_series,'forecast_values_compared':len(nf)*4,
            'per_model_discrepancies':discrepancy,'fit_metadata_checked':len(meta_checks),
            'complete_reference_metrics_checked':len(metrics)*3,'complete_period_pair_rankings_checked':expected_series*6,
            'normalized_mse_checks':len(metrics),'cohort_macro_metrics':cohort_metrics,
            'ranking_changes':ranking_changes,'all_fresh_training_warnings':[],
            'synthetic_feature_fixtures':fixtures,'actual_rebuilt_hourly_designs_checked':len(actual_design),
            'actual_design_checks':actual_design,'metadata_checks':meta_checks,
            'source_hashes':sources,'raw_source_hashes_verified':fresh['raw_source_hashes'] if not public else {},
            'hourly_source_hashes_verified':prepared['hourly_files'] if not public else {},
            'metrics_file':metric_path.name,'metrics_sha256':sha(metric_path),'script_sha256':sha(Path(__file__)),
            'comparison_protocol_sha256':sha(HERE/'comparison_protocol.txt'),
            'seconds':(datetime.now(timezone.utc)-started).total_seconds(),
            'scope':'Fresh same-trainer execution compared by independent row arithmetic, metadata/configuration checks and feature/chronology fixtures. No optimizer fit or full mask grid is run by this checker. '+('Public replay checks 61 UCI series; the archived all-64 check requires local BLEM raw/forecast values and newly rebuilt hourly inputs.' if public else 'Full replay covers all 64 series and independently checks features, chronology and targets against newly rebuilt hourly inputs; raw parsing/training routines themselves are reused or separately source-reviewed, not independent estimators.')}
    for relative,h in sources.items():assert sha(ROOT/relative)==h
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--public',action='store_true');args=parser.parse_args()
    output=HERE/('independent_verification_public.json' if args.public else 'independent_verification.json')
    try:report=run(args.public)
    except Exception as error:
        report={'status':'failed','completed_utc':datetime.now(timezone.utc).isoformat(),'error':repr(error),'traceback':traceback.format_exc(),'script_sha256':sha(Path(__file__))}
        output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');raise
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['actual_design_checks','metadata_checks','source_hashes','raw_source_hashes_verified','hourly_source_hashes_verified']},indent=2))
