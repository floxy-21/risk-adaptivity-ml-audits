"""Explicit-calendar forecasting adapter for the locked external HPM cohort.

No downloads. Requires canonical source CSV(s) and a stage-A protocol lock.
Importing or --help does not fit models. July targets do not affect training
or prediction-day eligibility; only past lag inputs may gate an issued forecast.
"""
from __future__ import annotations
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import warnings

for key in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"]:
    os.environ.setdefault(key,"2")
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/"outputs"))
from run_energy_rank_study import daily_design,MLP_PARAMETERS,MODELS


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_counters(paths):
    counters={};source_rows=[]
    for path in paths:
        with path.open(newline="",encoding="utf-8") as file:
            for row in csv.DictReader(file):
                system=int(row["system_id"])
                assert system in [1,2,7]
                stamp=pd.Timestamp(row["timestamp_utc"])
                assert stamp.tzinfo is not None and stamp.utcoffset().total_seconds()==0
                assert stamp.minute==stamp.second==stamp.microsecond==0
                valid=str(row["valid"]).lower() in ("true","1") and row["counter_kwh"] not in ("","null","None","nan")
                value=Decimal(row["counter_kwh"]) if valid else None
                if value is not None and not value.is_finite():value=None
                key=system,stamp
                if key in counters:
                    assert counters[key]==value,(key,"duplicate source disagreement")
                counters[key]=value
                source_rows.append({"system":system,"time":stamp.isoformat(),"valid":value is not None})
    return counters,source_rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counter-csv",nargs="+",type=Path,required=True)
    parser.add_argument("--protocol-lock",type=Path,default=HERE/"protocol_lock.json")
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    lock=json.loads(args.protocol_lock.read_text())
    assert lock["status"]=="fixed_before_external_forecast_or_treatment_outcomes"
    assert sha(HERE/"PROTOCOL.txt")==lock["protocol_sha256"]
    assert sha(ROOT/"outputs/run_energy_rank_study.py")==lock["original_forecast_program_sha256"]
    if args.output_dir.exists():raise FileExistsError("Use a new output directory; no forecasts are overwritten")
    counters,source_rows=read_counters(args.counter_csv)
    assert {system for system,t in counters}=={1,2,7}
    start=pd.Timestamp("2025-01-01",tz="UTC")
    split=pd.Timestamp("2025-07-01",tz="UTC")
    stop=pd.Timestamp("2025-08-01",tz="UTC")
    grid=pd.date_range(start,stop-pd.Timedelta(hours=1),freq="h")
    output=[];ledgers=[];metadata=[];began=time.perf_counter()
    for system in [1,2,7]:
        values=[]
        for t in grid:
            x=counters.get((system,t));y=counters.get((system,t+pd.Timedelta(hours=1)))
            values.append(float(y-x) if x is not None and y is not None and y>=x else np.nan)
        series=pd.Series(values,index=grid)
        days,x,y,eligible=daily_design(series)
        training=(days<split)&eligible
        train_fraction=float(np.isfinite(series.loc[series.index<split]).mean())
        assert training.sum()>=90 and train_fraction>=.95,(system,"training eligibility failed; do not substitute a system")
        # Unlike the old BLEM wrapper, test-day eligibility does not inspect y.
        feature_ok=np.isfinite(x).all(axis=(1,2))
        testing=(days>=split)&(days<stop)&feature_ok
        assert ((days[training]>=start)&(days[training]<split)).all()
        assert len(days[(days>=split)&(days<stop)])==31
        tx=x[training].reshape(-1,10);ty=y[training].reshape(-1)
        scale=float(ty.mean());assert np.isfinite(scale) and scale>0
        design=x[testing].reshape(-1,10)
        estimators={
            "ridge":make_pipeline(StandardScaler(),Ridge(alpha=1.0)),
            "hist_gradient_boosting":HistGradientBoostingRegressor(max_iter=100,learning_rate=.08,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1,max_bins=127,random_state=1729,early_stopping=False),
            "mlp":make_pipeline(StandardScaler(),MLPRegressor(**MLP_PARAMETERS)),
        }
        predictions={"daily":x[testing,:,0]};fit_records={}
        with threadpool_limits(limits=2):
            for name,estimator in estimators.items():
                t0=time.perf_counter()
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter("always",ConvergenceWarning)
                    estimator.fit(tx,ty/scale if name=="mlp" else ty)
                prediction=estimator.predict(design).reshape(-1,24)
                if name=="mlp":prediction*=scale
                predictions[name]=np.maximum(prediction,0)
                fit_records[name]={"seconds":time.perf_counter()-t0,"warnings":[str(w.message) for w in captured]}
                if name=="mlp":fit_records[name]["epochs"]=int(estimator.named_steps["mlpregressor"].n_iter_)
        for n,day in enumerate(days[testing]):
            for hour in range(24):
                output.append({"cohort":"external_hpm","meter":f"hpm_{system}","system_id":system,
                               "timestamp_utc":(day+pd.Timedelta(hours=hour)).isoformat(),"issue_utc":day.isoformat(),
                               **{model:float(predictions[model][n,hour]) for model in MODELS}})
        for i,day in enumerate(days):
            if split<=day<stop:
                ledgers.append({"system_id":system,"day_utc":day.isoformat(),"forecast_issued":bool(feature_ok[i]),
                                "forecast_eligibility_reason":"available past lag inputs" if feature_ok[i] else "missing past lag input",
                                "reference_target_complete":bool(np.isfinite(y[i]).all()),
                                "reference_availability_did_not_gate_forecast":True})
        metadata.append({"system_id":system,"train_days":int(training.sum()),"training_hourly_valid_fraction":train_fraction,
                         "test_calendar_days":31,"forecast_issue_days":int(testing.sum()),"training_mean_kwh":scale,
                         "first_train_day":days[training][0].isoformat(),"last_train_day":days[training][-1].isoformat(),
                         "fit":fit_records,"source_target":"difference of consecutive hourly API-grid stored cumulative kWh samples",
                         "measurement_time_not_claimed":"Native acquisition times/physical hourly interval boundaries are not inferred from API-grid labels."})
    args.output_dir.mkdir(parents=True)
    for name,rows in [("frozen_forecasts.csv",output),("calendar_ledger.csv",ledgers)]:
        with (args.output_dir/name).open("w",newline="",encoding="utf-8") as file:
            writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report={"status":"PASS","scope":"Fresh fits with unchanged model specifications and explicit external split; no acquisition or acceptance outcomes computed.",
            "systems":metadata,"source_hashes":{str(path):sha(path) for path in args.counter_csv},
            "protocol_lock_sha256":sha(args.protocol_lock),"adapter_sha256":sha(Path(__file__)),
            "forecast_sha256":sha(args.output_dir/"frozen_forecasts.csv"),"forecast_rows":len(output),
            "no_retuning_retries_replacement":True,"seconds":time.perf_counter()-began}
    (args.output_dir/"training_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ["status","forecast_rows","seconds","forecast_sha256"]}))


if __name__=="__main__":main()
