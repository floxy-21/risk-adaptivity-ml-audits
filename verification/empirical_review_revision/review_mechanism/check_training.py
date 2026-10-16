"""Recalculate training moments from retained source counter differences.

For BLEM this uses integer endpoint records, independent of the producer's
hourly-energy CSV. It never accesses held-out fine-resolution answers.
"""
import argparse
from collections import defaultdict
import csv
from datetime import datetime,timedelta,timezone
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1]
ROOT=BASE.parents[1]
def stamp(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--chain-dir',type=Path);p.add_argument('--results',required=True,type=Path);a=p.parse_args()
    given=read(a.results/'training_scales.json')['systems'];values=defaultdict(dict)
    endpoint=a.chain_dir/'original_raw/prepared/data_blem_hourly_endpoints.csv' if a.chain_dir else None
    if endpoint is not None:
        with endpoint.open(newline='',encoding='utf-8') as f:
            for r in csv.DictReader(f):
                t=stamp(r['interval_start_utc'])
                if datetime(2017,1,1,tzinfo=timezone.utc)<=t<datetime(2017,10,1,tzinfo=timezone.utc):
                    x=int(r['end_counter_integer'])-int(r['start_counter_integer'])
                    if x>=0:values['original/'+r['meter']][t]=F(x,10**10)
    external=BASE/'external_heatpump/hourly/train_test_hourly_counters.csv';points=defaultdict(dict)
    with external.open(newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            t=stamp(r['timestamp_utc'])
            if t<=datetime(2025,7,1,tzinfo=timezone.utc) and r['valid']=='1':
                points['external/hpm_'+r['system_id']][t]=F(r['counter_kwh'])
    for name,counter in points.items():
        for t in sorted(counter):
            next_=t+timedelta(hours=1)
            if next_ in counter and counter[next_]>=counter[t]:values[name][t]=counter[next_]-counter[t]
    result={}
    for name,g in given.items():
        original=name.startswith('original/')
        if original and endpoint is None:
            # Full raw BLEM sources have a separate regeneration route. The
            # default verifies the pinned source-linked moment declarations.
            metadata=[x.get('meta',x) for x in read(ROOT/'outputs/study_meter_results.json')]
            meta=next(x for x in metadata if x['cohort']=='blem_counters' and x['meter']==name.split('/')[1])
            assert g['training_days_count']==meta['train_days']==266
            assert abs(float(F(g['mean_exact']))-meta['training_mean_kwh'])<1e-12
            assert F(g['second_moment_exact'])>=F(g['mean_exact'])**2
            result[name]={'eligible_days':g['training_days_count'],'hourly_values':g['hour_count'],
              'mean_exact':g['mean_exact'],'second_moment_exact':g['second_moment_exact'],
              'raw_training_reconstructed':False,'scope':'Pinned declaration, frozen mean and count checked; use --chain-dir for independent integer-counter reconstruction.'}
            continue
        first=datetime(2017,1,1,tzinfo=timezone.utc) if original else datetime(2025,1,1,tzinfo=timezone.utc)
        last=datetime(2017,10,1,tzinfo=timezone.utc) if original else datetime(2025,7,1,tzinfo=timezone.utc)
        day=first;days=[];numbers=[]
        while day<last:
            valid=True
            for lag in [0,1,2,7]:
                for h in range(24):
                    t=day-timedelta(days=lag)+timedelta(hours=h)
                    if t not in values[name] or values[name][t]<0:valid=False
            if valid:
                days.append(day.date().isoformat());numbers.extend(values[name][day+timedelta(hours=h)] for h in range(24))
            day+=timedelta(days=1)
        assert days==g['training_days'] and len(days)==g['training_days_count']
        m=sum(numbers,F(0))/len(numbers);m2=sum((n*n for n in numbers),F(0))/len(numbers)
        assert m==F(g['mean_exact']) and m2==F(g['second_moment_exact'])
        assert m2>m*m and abs(float(m)-g['frozen_mean'])<1e-12
        assert hashlib.sha256(json.dumps(list(map(str,numbers)),separators=(',',':')).encode()).hexdigest()==g['value_sequence_sha256']
        result[name]={'eligible_days':len(days),'hourly_values':len(numbers),'mean_exact':str(m),'second_moment_exact':str(m2),'second_moment_kwh_squared':float(m2),'raw_training_reconstructed':True}
    out={'status':'PASS','systems':result,'training_scale_sha256':sha(a.results/'training_scales.json'),
      'checker_sha256':sha(__file__),'source_sha256':{'original_integer_endpoints':sha(endpoint) if endpoint else None,'external_decimal_counters':sha(external)},
      'original_training_reconstructed_in_this_run':endpoint is not None,
      'scope':'Training-only source differences with complete current/lag1/2/7 calendar checks for available source panels. Default uses source-linked declarations for original BLEM moments; --chain-dir additionally reconstructs those from integer counters.'}
    (a.results/'training_independent_check.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','systems':{k:v['eligible_days'] for k,v in result.items()}},indent=2))

if __name__=='__main__':main()
