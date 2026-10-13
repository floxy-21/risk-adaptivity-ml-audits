"""Check policy INPUTS only against raw counters and frozen original forecasts.

Does not inspect the geometry's objective values, policy choices or success
results. Requires the original mixed archive locally, or its exact reconstruction.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import numpy as np
import pandas as pd
from audit_counter_interface import ROOT,HERE,EXPECTED_RAW,HOUR,DAY,MODELS,load_counter,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry',type=Path,nargs='+',required=True)
    parser.add_argument('--original-archive',type=Path,default=ROOT/'outputs/study_predictions.csv')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'work')
    parser.add_argument('--output',type=Path,default=HERE/'policy_input_verification.json')
    args=parser.parse_args()
    pub=ROOT/'outputs/review_frozen_forecasts.csv'
    man=json.loads((ROOT/'outputs/review_frozen_forecasts.json').read_text())
    assert sha(pub)==man['output_sha256']
    if not args.original_archive.exists():
        raise FileNotFoundError('Reconstruct with python work/reproduce_review_revision.py --raw --reconstruct-only, then pass --original-archive <printed-stage>/outputs/study_predictions.csv')
    assert sha(args.original_archive)==man['original_predictions_sha256']
    original=pd.read_csv(args.original_archive)
    original=original[original.cohort=='blem_counters'].copy()
    exported=pd.read_csv(pub)
    exported=exported[exported.cohort=='blem_counters'].copy()
    assert set(original.meter)==set(EXPECTED_RAW) and set(exported.meter)==set(EXPECTED_RAW)
    assert len(original)==len(exported)==6552
    for frame in (original,exported):
        frame['timestamp']=pd.to_datetime(frame.timestamp,utc=True)
        assert not frame.duplicated(['meter','timestamp']).any()
    original=original.set_index(['meter','timestamp']).sort_index()
    exported=exported.set_index(['meter','timestamp']).sort_index()
    assert original.index.equals(exported.index)
    learned_diff=float(np.max(np.abs(original[list(MODELS[1:])].to_numpy()-exported[list(MODELS[1:])].to_numpy())))
    assert learned_diff==0
    assert exported.daily.isna().all() and exported.truth_kwh.isna().all()
    summary=json.loads((ROOT/'outputs/study_summary.json').read_text())
    means={r['meter']:r['training_mean_kwh'] for r in summary['meters'] if r['cohort']=='blem_counters'}
    counters={};raw_hashes={};dates={};daily_diff=0.;daily_changed=0
    for meter in EXPECTED_RAW:
        path,_,rows,counter=load_counter(meter,args.data_dir)
        counters[meter]=counter;raw_hashes[meter]=sha(path)
        mf=original.loc[meter]
        days=sorted(set(mf.index.normalize()))
        required=list(pd.date_range('2017-10-01','2017-12-30',tz='UTC',freq='D'))
        assert days==required and len(days)==91
        assert all(len(mf.loc[d:d+pd.Timedelta(hours=23)])==24 for d in days)
        dates[meter]=[d.strftime('%Y-%m-%d') for d in days]
        for stamp,row in mf.iterrows():
            previous=int(stamp.timestamp()*1000)-DAY
            reconstructed=(counter[previous+HOUR]-counter[previous])/10**10
            difference=abs(reconstructed-float(row.daily))
            daily_diff=max(daily_diff,difference);daily_changed+=difference!=0
            assert difference <= 2e-14*max(1,abs(reconstructed),abs(float(row.daily)))
    max_errors=Counter();total=0;seen=set();by_panel=Counter();files=[]
    for path in args.geometry:
        obj=json.loads(path.read_text()); cases=obj['cases']
        declared=obj['manifest']['phase']
        expected_ids=set()
        for meter in EXPECTED_RAW:
            for index,day in enumerate(dates[meter]):
                phase='pilot' if index<20 else 'continuation'
                if declared!='all' and phase!=declared:continue
                for h in (0,6,12):
                    for ai,a in enumerate(MODELS):
                        for b in MODELS[ai+1:]:expected_ids.add(f'{meter}/{day}/{h:02d}/{a}/{b}')
        ids=[c['id'] for c in cases]
        assert len(ids)==len(set(ids)) and set(ids)==expected_ids
        assert not seen.intersection(ids),'Overlapping phase geometry supplied'
        seen.update(ids)
        for case in cases:
            meter=case['meter'];h=case['start_hour'];day=pd.Timestamp(case['day'],tz='UTC')
            stamps=[day+pd.Timedelta(hours=h+i) for i in range(6)]
            a,b=case['model_a'],case['model_b']
            rec={};old={}
            for model in (a,b):
                old[model]=np.array([original.loc[(meter,t),model] for t in stamps],float)
                if model=='daily':
                    previous=[int(t.timestamp()*1000)-DAY for t in stamps]
                    rec[model]=np.array([(counters[meter][t+HOUR]-counters[meter][t])/10**10 for t in previous])
                else:rec[model]=np.array([exported.loc[(meter,t),model] for t in stamps],float)
            coef=2*(rec[b]-rec[a])/6;oldcoef=2*(old[b]-old[a])/6
            cr=float(np.ptp(coef)); cn=(coef-coef.min())/cr if cr>0 else np.zeros(6)
            start=int(stamps[0].timestamp()*1000)
            energy=(counters[meter][start+6*HOUR]-counters[meter][start])/10**10
            expected={'E':energy,'W0':energy*cr,'d':float(np.mean(rec[a]**2-rec[b]**2)),
                      'normalization_scale':means[meter]**2}
            for field,value in expected.items():
                err=abs(float(case[field])-value);max_errors[field]=max(max_errors[field],err)
                assert err<=1e-12*max(1,abs(value)),(case['id'],field,err)
            for field,value in [('c',coef),('c_normalized',cn)]:
                err=float(np.max(np.abs(np.array(case[field])-value)));max_errors[field]=max(max_errors[field],err)
                assert err<=1e-12*max(1,float(np.max(np.abs(value)))),(case['id'],field,err)
            max_errors['c_vs_original_frozen_daily']=max(max_errors['c_vs_original_frozen_daily'],float(np.max(np.abs(coef-oldcoef))))
            max_errors['d_vs_original_frozen_daily']=max(max_errors['d_vs_original_frozen_daily'],abs(float(np.mean(rec[a]**2-rec[b]**2))-float(np.mean(old[a]**2-old[b]**2))))
            assert pd.Timestamp(case['forecast_issue_utc'])==day
            assert pd.Timestamp(case['cutoff_utc'])==day+pd.Timedelta(hours=h+6)
            assert case['day_index']==dates[meter].index(case['day'])
            assert case['phase']==('pilot' if case['day_index']<20 else 'continuation')
            total+=1;by_panel[case['phase']]+=1
        files.append({'path':str(path),'sha256':sha(path),'declared_phase':declared,'input_cases':len(cases)})
    report={'status':'passed','scope':'Source and policy-input verification only; no policy objective, choice, replay result, advantage or case selection inspected.',
        'geometry_inputs':files,'policy_input_cases_checked':total,'cases_by_panel':dict(by_panel),
        'exact_source_meters':list(EXPECTED_RAW),'days_per_meter':91,'frozen_hourly_rows':6552,
        'original_archive_sha256':sha(args.original_archive),'public_export_sha256':sha(pub),'raw_sha256':raw_hashes,
        'learned_forecast_max_absolute_difference':learned_diff,
        'daily_persistence_reconstructed_rows':6552,'daily_persistence_rows_with_nonzero_float_difference':int(daily_changed),
        'daily_persistence_max_absolute_difference_kwh':daily_diff,
        'maximum_policy_input_absolute_discrepancies':dict(max_errors),
        'policy_input_tolerance':'1e-12*max(1,abs(expected scalar) or maximum absolute vector element)',
        'original_persistence_check_tolerance':'2e-14*max(1,abs(old),abs(regenerated))',
        'persistence_interpretation':'Direct integer-difference division can differ by final floating parsing bits from the original hourly-CSV-parsed persistence. This is quantified, not described as byte-identical.',
        'script_sha256':sha(__file__),'data_audit_script_sha256':sha(HERE/'audit_counter_interface.py')}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
