"""Training-only convergence diagnostic; never predicts or scores held-out data."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time
import warnings
import numpy as np
import pandas as pd
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from run_energy_rank_study import (ROOT, WORK, OUT, MLP_PARAMETERS,
    daily_design, local_dst_affected, load_household, load_portugal)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    started=time.perf_counter()
    jobs=[('household','household_1',load_household())]
    portugal=load_portugal()
    jobs.extend(('portugal',c,portugal[c]) for c in portugal.columns)
    blem=pd.read_csv(WORK/'data_blem_hourly.csv',index_col=0,parse_dates=True)
    jobs.extend(('blem_counters',c,blem[c]) for c in blem.columns)
    assert len(jobs)==34
    result={'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Training-only convergence; no held-out predictions or scores computed',
        'parameters':MLP_PARAMETERS,'main_script_sha256':digest(OUT/'run_energy_rank_study.py'),
        'script_sha256':digest(Path(__file__)),
        'protocol_sha256':digest(WORK/'study_protocol_training_convergence.txt'),
        'versions':{'python':platform.python_version(),'numpy':np.__version__,
                    'pandas':pd.__version__,'sklearn':sklearn.__version__},'meters':[]}
    with threadpool_limits(limits=2):
        for cohort,meter,series in jobs:
            days,x,y,eligible=daily_design(series)
            if cohort in ('portugal','household'):
                eligible &= ~local_dst_affected(days)
            if cohort=='portugal':
                train=(days.year==2013)&eligible
            elif cohort=='household':
                train=np.isin(days.year,[2008,2009])&eligible
            else:
                train=(days<pd.Timestamp('2017-10-01',tz=days.tz))&eligible
            train_x=x[train].reshape(-1,10)
            train_y=y[train].reshape(-1)
            scale=float(train_y.mean())
            assert train.sum()>=30 and np.isfinite(scale) and scale>0
            estimator=make_pipeline(StandardScaler(),MLPRegressor(**MLP_PARAMETERS))
            before=time.perf_counter()
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                estimator.fit(train_x,train_y/scale)
            model=estimator.named_steps['mlpregressor']
            convergence_warnings=[str(w.message) for w in caught if issubclass(w.category,ConvergenceWarning)]
            record={'cohort':cohort,'meter':meter,'train_days':int(train.sum()),
                'epochs':int(model.n_iter_),'training_objective_loss':float(model.loss_),
                'loss_curve_tail':list(map(float,model.loss_curve_[-20:])),
                'target_scale_training_mean_kwh':scale,
                'convergence_warnings':convergence_warnings,
                'all_warnings':[str(w.message) for w in caught],
                'stopped_without_cap_warning':not convergence_warnings and model.n_iter_<MLP_PARAMETERS['max_iter'],
                'fit_seconds':time.perf_counter()-before}
            result['meters'].append(record)
            print(datetime.now(timezone.utc).isoformat(timespec='seconds'),cohort,meter,
                  'epochs',record['epochs'],'converged',record['stopped_without_cap_warning'],flush=True)
            (OUT/'study_training_preflight.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    result['status']='passed' if all(m['stopped_without_cap_warning'] for m in result['meters']) else 'requires_review'
    result['completed_utc']=datetime.now(timezone.utc).isoformat()
    result['wall_seconds']=time.perf_counter()-started
    result['warning_count']=sum(len(m['convergence_warnings']) for m in result['meters'])
    result['epoch_range']=[min(m['epochs'] for m in result['meters']),max(m['epochs'] for m in result['meters'])]
    (OUT/'study_training_preflight.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('COMPLETE',result['status'],'warning_count',result['warning_count'],flush=True)
    if result['status']!='passed':
        raise RuntimeError('At least one training-only fit requires convergence review')


if __name__=='__main__':
    main()
