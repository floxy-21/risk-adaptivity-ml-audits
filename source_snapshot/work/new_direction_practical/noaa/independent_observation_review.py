"""Independent stdlib observation/closure review; does not import build_panel."""
import csv, json, hashlib, calendar
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
HERE=Path(__file__).resolve().parent
EVENTS=['2008-12-05','2008-12-10','2008-12-11','2008-12-17','2008-12-28','2008-12-29','2009-06-05','2009-06-14','2009-06-24']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    source=HERE/'USC00010140.csv';quarter=HERE/'USC00010140.15m.csv'
    hourly={r['DATE']:r for r in csv.DictReader(source.open(newline=''))}
    finer={r['DATE']:r for r in csv.DictReader(quarter.open(newline=''))}
    proposed=json.loads((HERE/'observation_panel.json').read_text())
    planned={r['date']:r for r in proposed['cases']}
    inventory=[r for r in csv.DictReader((HERE/'station_inventory.csv').open()) if r['StnID']=='USC00010140'][0]
    assert float(inventory['UTC_Offset'])==-6 and float(inventory['Lat'])==32.2322 and float(inventory['Lon'])==-87.4104
    observations=[];excluded=[];mfcount=Counter();positive_controls=[]
    for year,month in [(2008,12),(2009,6)]:
      for d in range(1,calendar.monthrange(year,month)[1]+1):
        day=f'{year:04}-{month:02}-{d:02}';r=hourly.get(day)
        if r is None:excluded.append({'date':day,'reason':'absent daily row'});continue
        values=[int(r[f'HR{h:02}Val']) for h in range(24)]
        quality=[r[f'HR{h:02}QF'].strip() for h in range(24)]
        measurement=[r[f'HR{h:02}MF'].strip() for h in range(24)]
        if day in EVENTS:
            assert measurement==['a']+['.']*22+['A'] and quality==['M']*23+['A']
            assert values[:23]==[-9999]*23 and values[23]>0
            assert int(r['DlySum'])==-9999
            assert all(r[f'HR{h:02}S1'].strip()=='4' for h in range(24))
            assert planned[day]['kind']=='natural_accumulation' and planned[day]['truth_3h_mm'] is None
            assert abs(planned[day]['total_mm']-values[23]*.254)<1e-12
            alt=finer.get(day);alttrace={'row_present':alt is not None,'source_day':day}
            if alt:
                prefixes=[f'{h:02}{q:02}' for h in range(24) for q in [0,15,30,45]]
                known=[p for p in prefixes if int(alt[p+'Val'])>=0 and not alt[p+'QF'].strip() and alt[p+'MF'].strip() not in ['a','.','A']]
                assert known==['0000','0015','0030'] and all(int(alt[p+'Val'])==0 for p in known)
                assert alt['0045MF']=='a' and all(alt[p+'MF']=='.' for p in prefixes[4:-1]) and alt['2345MF']=='A'
                assert int(alt['2345Val'])==values[23] and alt['2345QF']=='A'
                unknown_by_bin=[sum(p not in known for p in prefixes[12*b:12*(b+1)]) for b in range(8)]
                assert all(x>0 for x in unknown_by_bin)
                alttrace.update(known_zero_quarters=known,unknown_quarters_per_three_hour_bin=unknown_by_bin,
                  accumulated_start='00:45 LST',accumulated_end='24:00 LST',accumulated_total_raw=int(alt['2345Val']),
                  all_three_hour_targets_still_unresolved=True,projection_onto_three_hour_targets_unchanged=True)
            else:alttrace.update(all_three_hour_targets_still_unresolved=True,projection_onto_three_hour_targets_unchanged=True)
            observations.append({'date':day,'kind':'natural_accumulation','record_total_raw':values[23],
                                 'record_total_mm':values[23]*.254,'dlysum_used':False,'alternate_15m':alttrace})
        elif all(v>=0 for v in values) and not any(quality) and not any(m in ['a','.','A'] for m in measurement):
            targets=[sum(values[i:i+3])*.254 for i in range(0,24,3)]
            assert planned[day]['kind']=='complete_control' and planned[day]['truth_3h_mm']==targets
            mfcount.update(measurement)
            if sum(values):positive_controls.append({'date':day,'total_raw':sum(values)})
            observations.append({'date':day,'kind':'complete_control','total_raw':sum(values),'source_zero_hours':sum(m=='Z' for m in measurement)})
        else:excluded.append({'date':day,'reason':'present but incomplete or flagged'})
    assert len(observations)==52 and len(excluded)==9
    assert set(planned)=={r['date'] for r in observations}
    assert {r['date'] for r in proposed['excluded']}=={r['date'] for r in excluded}
    for case in proposed['cases']:
        assert case['utc_start']==case['date']+'T06:00:00Z' and case['lead_hours']==list(range(6,31,3))
    raw=[]
    for month in ['200812','200906']:
        path=HERE/f'hpd_{month}.csv'
        rows=list(csv.reader(path.open()));matches=[r for r in rows if r and r[0].strip()=='010140']
        assert not matches
        raw.append({'file':path.name,'sha256':sha(path),'rows':len(rows),'station010140_rows':0})
    filenames=['protocol.txt','observation_panel.json','USC00010140.csv','USC00010140.15m.csv',
               'station_inventory.csv','readme.csv.txt','readme.15min.txt','public_source_search.json']
    report={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),'independent_of_builder_import':True,
      'source_hashes':{f:sha(HERE/f) for f in filenames},'station':inventory,'natural_days':9,'complete_controls':43,
      'all_calendar_dates':61,'exclusions':excluded,'control_measurement_flags':dict(mfcount),'positive_controls':positive_controls,
      'natural_cases':[o for o in observations if o['kind']=='natural_accumulation'],'raw_monthly_sources':raw,
      'closure_reason':'Every three-hour bin still has at least one unconstrained nonnegative quarter-hour component. Any nonnegative three-hour allocation summing to the recorded total extends to the observed initial zeros and the finer accumulation, so projection remains the same simplex.',
      'scope':'Closure covers the explicitly inspected NOAA hourly, parallel 15-minute and available monthly raw digital sources. It does not prove no other archive exists. Recorded-total allocation is not a deterministic physical-rain measurement guarantee.'}
    (HERE/'independent_observation_review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['natural_cases','station']},indent=2))
if __name__=='__main__':main()
