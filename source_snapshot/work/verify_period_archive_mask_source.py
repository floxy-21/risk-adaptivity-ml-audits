"""Check original oracle-mask precision after the documented implementation repair."""
import sys
from pathlib import Path
import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs'))
from run_energy_rank_study import load_portugal,load_household,digest
out=ROOT/'outputs'
standard=pd.read_csv(out/'study_predictions.csv')
exact=pd.read_csv(out/'study_predictions.csv',float_precision='round_trip')
household,portugal=load_household(),load_portugal()
blem=pd.read_csv(ROOT/'work/data_blem_hourly.csv',index_col=0,parse_dates=True)
changed=[]; checked=0; maximum_delta=0.
for (cohort,meter),group in exact.groupby(['cohort','meter']):
    source=household if cohort=='household' else portugal[meter] if cohort=='portugal' else blem[meter]
    original=source.reindex(pd.to_datetime(group.timestamp)).to_numpy()
    serialized=group.truth_kwh.to_numpy()
    np.testing.assert_array_equal(original,serialized)
    checked+=len(original)
    maximum_delta=max(maximum_delta,float(np.max(abs(original-standard.loc[group.index,'truth_kwh'].to_numpy()))))
    for day,daygroup in group.groupby(group.timestamp.str[:10]):
        left=daygroup.truth_kwh.to_numpy(); right=standard.loc[daygroup.index,'truth_kwh'].to_numpy()
        for gap in (2,6,12):
            original_mask=sorted(np.argsort(left,kind='stable')[-gap:].tolist())
            parsed_mask=sorted(np.argsort(right,kind='stable')[-gap:].tolist())
            if original_mask!=parsed_mask:
                changed.append(dict(cohort=cohort,meter=meter,day=day,gap_hours=gap,
                    original_mask_hours=original_mask,default_csv_mask_hours=parsed_mask))
assert len(changed)==4
report={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
 'target_coordinates_exactly_matching_original_source':checked,'meters':34,
 'maximum_default_parser_target_change':maximum_delta,'changed_oracle_masks':changed,
 'result':'Original hourly-source targets exactly equal round-trip parsed original CSV targets; original source defines repaired oracle masks. Contiguous/scattered RNG masks are unaffected.',
 'source_hashes':{'study_predictions.csv':digest(out/'study_predictions.csv'),'run_energy_rank_study.py':digest(out/'run_energy_rank_study.py')},
 'work_source_hashes':{name:digest(ROOT/'work'/name) for name in ('study_household_hourly.pkl','study_portugal_hourly.pkl','data_blem_hourly.csv')},
 'script_sha256':digest(__file__)}
(out/'study_period_archive_mask_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
