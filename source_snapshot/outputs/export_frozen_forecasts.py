"""Export frozen fitted forecasts, excluding targets and copied BLEM persistence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pandas as pd

OUT=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    summary_path=OUT/'study_summary.json'
    source=OUT/'study_predictions.csv'
    summary=json.loads(summary_path.read_text())
    assert sha(source)==summary['artifacts'][source.name]['sha256']
    models=summary['design']['models']
    raw=pd.read_csv(source,usecols=['cohort','meter','timestamp','truth_kwh',*models])
    numeric_ranges={name:{'min':float(raw[name].min()),'max':float(raw[name].max())}
                    for name in ['truth_kwh',*models]}
    frame=raw.drop(columns=['truth_kwh'])
    assert models==['daily','ridge','hist_gradient_boosting','mlp']
    metadata={(m['cohort'],m['meter']):m for m in summary['meters']}
    frame['training_mean_kwh']=[metadata[(c,m)]['training_mean_kwh'] for c,m in zip(frame.cohort,frame.meter)]
    frame['model_training_end_date']=[metadata[(c,m)]['train_end'] for c,m in zip(frame.cohort,frame.meter)]
    frame['simulated_issue_timestamp']=[s[:10]+'T00:00:00'+('+00:00' if s.endswith('+00:00') else '') for s in frame.timestamp]
    frame.rename(columns={'timestamp':'target_interval_start'},inplace=True)
    counter=frame.cohort=='blem_counters'
    frame['daily_omitted']=counter
    # Persistence copies past target observations exactly, so it must not be
    # treated as a newly derived fitted forecast for this omission decision.
    frame.loc[counter,'daily']=float('nan')
    assert frame.loc[counter,'daily'].isna().all()
    assert 'truth_kwh' not in frame.columns
    destination=OUT/'frozen_forecasts.csv'
    frame.to_csv(destination,index=False)
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'rows':len(frame),'meters':len(metadata),
        'models':models,'predicted_unit':'hourly kWh','raw_targets_included':False,
        'numeric_ranges':numeric_ranges,
        'blem_daily_persistence_omitted':True,'omitted_daily_rows':int(counter.sum()),
        'issue_time_semantics':'Simulated historical day-start feature cutoff, not an originally logged vendor issue time',
        'timezone_semantics':'BLEM UTC; Portugal and household retain provider-local naive clocks and documented DST exclusions',
        'omission_reason':'Daily persistence would copy the previous day of BLEM measurements. Omit that column for BLEM rather than directly redistribute observations. This does not establish broader dataset licensing rights.',
        'regeneration':'Download original sources and run run_energy_rank_study.py, then export_frozen_forecasts.py',
        'script_sha256':sha(__file__),
        'source_hashes':{'study_summary.json':sha(summary_path),'study_predictions.csv':sha(source)},
        'output_sha256':sha(destination)}
    (OUT/'frozen_forecasts.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
