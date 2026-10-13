"""Fresh same-trainer model fitting from rebuilt raw series; isolated outputs only."""
from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,hashlib,time,csv,traceback,warnings,platform
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[n]='2'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent;WORK=ROOT/'work';OUT=ROOT/'outputs'
sys.path.insert(0,str(OUT));sys.path.insert(0,str(WORK))
import numpy as np,pandas as pd,scipy,sklearn
import run_energy_rank_study as trainer
import data_prepare_blem
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(8*1024*1024):h.update(chunk)
    return h.hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
def save(name,doc):(HERE/name).write_text(json.dumps(doc,indent=2,allow_nan=False),encoding='utf-8')
def versions():return dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__)
def prepare():
    assert not (HERE/'prepared.json').exists(),'Refuse to overwrite preparation'
    assert (HERE/'protocol.txt').exists() and (HERE/'comparison_protocol.txt').exists()
    started=time.perf_counter();hourly=HERE/'hourly';hourly.mkdir(exist_ok=False)
    rawexpected=json.loads((OUT/'review_raw_reconstruction.json').read_text())['raw_source_hashes']
    rawhashes={}
    for name,h in rawexpected.items():
        actual=sha(WORK/name);assert actual==h,name;rawhashes['work/'+name]=actual
    sourcepaths=['outputs/run_energy_rank_study.py','outputs/energy_rank_bounds.py','outputs/study_holdout_consumers.py','work/data_prepare_blem.py','outputs/study_summary.json','outputs/study_holdout_consumers.json','outputs/study_predictions.csv','outputs/study_holdout_consumers_predictions.csv','outputs/review_raw_reconstruction.json']
    sources={name:sha(ROOT/name) for name in sourcepaths}
    print('Raw sources verified; rebuilding household hourly series',flush=True)
    frame=pd.read_csv(WORK/'data_uci_household_power.txt',sep=';',usecols=['Date','Time','Global_active_power'],na_values=['?'],dtype={'Global_active_power':'float64'})
    index=pd.to_datetime(frame['Date']+' '+frame['Time'],format='%d/%m/%Y %H:%M:%S');power=pd.Series(frame.Global_active_power.to_numpy(),index=index)
    household=power.resample('h').sum(min_count=60)/60;household[power.resample('h').count()!=60]=np.nan
    household.to_pickle(hourly/'household.pkl');del frame,power
    print('Rebuilding all Portugal candidate series from raw quarter-hour text',flush=True)
    names=pd.read_csv(WORK/'data_electricity.txt',sep=';',nrows=0).columns.tolist();columns=[names[0]]+[f'MT_{i:03d}' for i in range(1,371)]
    frame=pd.read_csv(WORK/'data_electricity.txt',sep=';',decimal=',',usecols=columns,dtype={n:'float64' for n in columns[1:]})
    index=pd.to_datetime(frame.iloc[:,0],format='%Y-%m-%d %H:%M:%S')-pd.Timedelta(minutes=15);frame=frame.iloc[:,1:];frame.index=pd.DatetimeIndex(index)
    portugal=frame.resample('h').sum(min_count=4)/4;del frame
    train=portugal.loc['2013'];screen=[dict(meter=n,training_hour_count=len(train),training_nonmissing_fraction=float(train[n].notna().mean()),training_positive_fraction=float((train[n]>0).mean())) for n in portugal]
    eligible=[r['meter'] for r in screen if r['training_nonmissing_fraction']>=.99 and r['training_positive_fraction']>.95]
    original=[n for n in eligible if int(n[3:])<=80][:30];holdout=[n for n in eligible if int(n[3:])>=81][:30]
    summary=json.loads((OUT/'study_summary.json').read_text());held=json.loads((OUT/'study_holdout_consumers.json').read_text())
    assert original==[m['meter'] for m in summary['meters'] if m['cohort']=='portugal']
    assert holdout==held['selection']['selected_ids'] and not set(original)&set(holdout)
    portugal[original].to_pickle(hourly/'portugal_original.pkl');portugal[holdout].to_pickle(hourly/'portugal_holdout.pkl');del portugal,train
    print('Rebuilding three BLEM series from integer counters',flush=True)
    data_prepare_blem.prepare(WORK,hourly,download=False)
    blem=pd.read_csv(hourly/'data_blem_hourly.csv',index_col=0,parse_dates=True);blem.to_pickle(hourly/'blem.pkl')
    jobs=[dict(cohort='household',meter='household_1',fit_cohort='household',hourly_file='hourly/household.pkl')]
    jobs += [dict(cohort='portugal',meter=n,fit_cohort='portugal',hourly_file='hourly/portugal_original.pkl') for n in original]
    jobs += [dict(cohort='blem_counters',meter=n,fit_cohort='blem_counters',hourly_file='hourly/blem.pkl') for n in blem]
    jobs += [dict(cohort='portugal_new_consumers',meter=n,fit_cohort='portugal',hourly_file='hourly/portugal_holdout.pkl') for n in holdout]
    assert len(jobs)==64
    config=dict(models=trainer.MODELS,mlp=trainer.MLP_PARAMETERS,ridge_alpha=1.0,hgb=dict(max_iter=100,learning_rate=.08,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1,max_bins=127,random_state=1729,early_stopping=False),numerical_threads=2,workers=1,original_selected_ids=original,holdout_selected_ids=holdout)
    save('selection.json',dict(status='PASS',screening=screen,original_selected_ids=original,holdout_selected_ids=holdout))
    save('prepared.json',dict(status='PASS',completed_utc=stamp(),seconds=time.perf_counter()-started,raw_source_hashes=rawhashes,source_hashes=sources,protocol_sha256=sha(HERE/'protocol.txt'),comparison_protocol_sha256=sha(HERE/'comparison_protocol.txt'),driver_sha256=sha(__file__),config=config,versions=versions(),jobs=jobs,hourly_files={str(p.relative_to(HERE)).replace('\\','/'):sha(p) for p in hourly.iterdir()},cache_existed_before_preparation=False,old_hourly_cache_reads=False,model_state_reads=False,scope='Fresh raw parsing and integer-counter reconstruction; no fits or prediction comparisons in preparation.'))
    print('Preparation frozen for64series',flush=True)
def fit():
    assert not (HERE/'fresh_predictions.csv').exists(),'Refuse to overwrite fresh forecasts'
    p=json.loads((HERE/'prepared.json').read_text());assert p['status']=='PASS'
    assert sha(HERE/'comparison_protocol.txt')==p['comparison_protocol_sha256'];assert sha(__file__)==p['driver_sha256']
    for name,h in p['source_hashes'].items():assert sha(ROOT/name)==h,name
    for name,h in p['hourly_files'].items():assert sha(HERE/name)==h,name
    assert versions()==p['versions'];started=time.perf_counter();metadata=[];failures=[];rows=0
    with (HERE/'fresh_predictions.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['cohort','meter','timestamp','truth_kwh',*trainer.MODELS])
        for number,job in enumerate(p['jobs'],1):
            cohort,meter=job['cohort'],job['meter'];series=pd.read_pickle(HERE/job['hourly_file'])
            if isinstance(series,pd.DataFrame):series=series[meter]
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always');days,truth,pred,profiles,donors,meta=trainer.fit_forecasts(job['fit_cohort'],meter,series)
                assert np.isfinite(truth).all() and np.isfinite(pred).all() and (pred>=0).all()
                meta.update(cohort=cohort,status='passed',additional_warnings=[str(w.message) for w in caught],fit_cohort=job['fit_cohort'])
                for di,day in enumerate(days):
                    for hour in range(24):writer.writerow([cohort,meter,(day+pd.Timedelta(hours=hour)).isoformat(),truth[di,hour],*pred[di,:,hour]]);rows+=1
                f.flush();metadata.append(meta)
                print(f'Completed fresh fit {number}/64 {cohort}/{meter}',flush=True)
            except BaseException as exc:
                failure=dict(cohort=cohort,meter=meter,status='failed',error=repr(exc),traceback=traceback.format_exc());metadata.append(failure);failures.append(failure);print('FAILED',cohort,meter,repr(exc),flush=True)
            save('fit_metadata.json',metadata)
    unchanged={name:sha(ROOT/name)==h for name,h in p['source_hashes'].items()};assert all(unchanged.values())
    raw_unchanged={name:sha(ROOT/name)==h for name,h in p['raw_source_hashes'].items()};assert all(raw_unchanged.values())
    result=dict(status='PASS' if not failures else 'FAILED',completed_utc=stamp(),wall_seconds=time.perf_counter()-started,series_planned=64,series_completed=len(metadata)-len(failures),trained_estimators_completed=3*(len(metadata)-len(failures)),prediction_rows=rows,failures=failures,source_hashes=p['source_hashes'],raw_source_hashes=p['raw_source_hashes'],source_files_unchanged=unchanged,raw_files_unchanged=raw_unchanged,protocol_sha256=p['protocol_sha256'],comparison_protocol_sha256=p['comparison_protocol_sha256'],driver_sha256=sha(__file__),config=p['config'],versions=versions(),hourly_files=p['hourly_files'],jobs=p['jobs'],cache_existed_before_preparation=False,old_hourly_cache_reads=False,model_state_reads=False,scope='Fresh execution of unchanged declared trainer from newly rebuilt pinned raw series, before independent comparison. No saved model or old forecast supplies training/predictions. No mask-grid rerun.',output_hashes={n:sha(HERE/n) for n in ['fresh_predictions.csv','fit_metadata.json','prepared.json','selection.json']})
    save('fresh_result.json',result);print(json.dumps({k:result[k] for k in ('status','wall_seconds','series_completed','trained_estimators_completed','prediction_rows','failures')},indent=2),flush=True)
if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='fit':fit()
    else:raise ValueError(sys.argv[1])
