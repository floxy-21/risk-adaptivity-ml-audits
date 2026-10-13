"""Independent next-cohort selection, raw extraction and Decimal hourly audit.

No forecast, acquisition, or loss outcomes are loaded. Does not import either
preparation implementation. Raw mode scans the full original source independently.
"""
import argparse,csv,gzip,hashlib,json,math,time
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from decimal import Decimal,InvalidOperation
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'work/external_deadline/data/lcl'
NEW=ROOT/'work/decision_revision/confirmation_source'
OUT=Path(__file__).parent


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
    return h.hexdigest()


def canonical_row(values):
    return (json.dumps(values,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')


def scan_raw(path,selected):
    raw_hash=hashlib.sha256();selected_hash=hashlib.sha256();ids={x.encode('ascii') for x in selected}
    rows=chosen=0;carry=b'';header=None;started=time.perf_counter()
    with path.open('rb') as f:
        while chunk:=f.read(16<<20):
            raw_hash.update(chunk);lines=(carry+chunk).split(b'\n');carry=lines.pop()
            for line in lines:
                if header is None:
                    header=next(csv.reader([line.decode('utf-8-sig').rstrip('\r')]))
                    assert header==['LCLid','stdorToU','DateTime','KWH/hh (per half hour) ']
                    continue
                rows+=1
                if line[:9] not in ids:continue
                assert line[9:10]==b','
                fields=next(csv.reader([line.decode('utf-8').rstrip('\r')]))
                assert len(fields)==4 and fields[0] in selected
                if '2012-12-24'<=fields[2]<'2014-03-03':
                    selected_hash.update(canonical_row(fields));chosen+=1
            if rows%20000000<400000:print(json.dumps({'raw_rows_checked':rows,'seconds':time.perf_counter()-started}),flush=True)
    assert not carry,'Unexpected unterminated raw final line'
    return {'raw_sha256':raw_hash.hexdigest(),'all_source_rows_scanned':rows,
            'selected_literal_rows':chosen,'selected_row_stream_sha256':selected_hash.hexdigest(),
            'independent_raw_scan_seconds':time.perf_counter()-started}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--raw',action='store_true');args=ap.parse_args()
    started=time.perf_counter()
    manifest=json.loads((NEW/'manifest.json').read_text());assert manifest['status']=='passed'
    for name,digest in manifest['files'].items():assert sha(NEW/name)==digest,name
    old_manifest=json.loads((OLD/'manifest.json').read_text())
    selection=json.loads((NEW/'selection_before_extract.json').read_text())
    for name,digest in selection['inputs'].items():assert sha(ROOT/name)==digest,name
    original=json.loads((OLD/'selection.json').read_text())['selected_ids']
    inventory=json.loads((OLD/'household_inventory.json').read_text())
    ids=[r['household_id'] for r in inventory];assert ids==sorted(ids) and len(ids)==100
    # Independently reconstruct training counts from original daily records.
    training=Counter();old_days={}
    with (OLD/'daily_quality.csv').open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            assert int(row['complete'])==int(int(row['eligible_hours'])==24)
            old_days[(row['household_id'],row['date_benchmark'])]=int(row['eligible_hours'])
            if row['split']=='training' and int(row['complete']):training[row['household_id']]+=1
    for row in inventory:assert training[row['household_id']]==row['complete_days_by_split'].get('training',0)
    selected=[hh for hh in ids if training[hh]>=90 and hh not in original][:20]
    assert len(selected)==20 and selected==selection['selected_ids']==manifest['selected_ids']
    assert not set(selected)&set(original)
    assert selection['excluded_previously_fitted_ids']==sorted(original)
    quality={r['household_id']:r for r in json.loads((NEW/'quality_counts.json').read_text())}
    assert set(quality)==set(selected)
    records=defaultdict(list);literal_hash=hashlib.sha256();literal_count=Counter();tariffs=defaultdict(set)
    invalid_count=Counter();negative_count=Counter();zero_count=Counter();offgrid_count=Counter();timestamps=Counter()
    with gzip.open(NEW/'selected_halfhour_source.csv.gz','rt',newline='',encoding='utf-8') as f:
        reader=csv.DictReader(f);names=reader.fieldnames
        for row in reader:
            literal_hash.update(canonical_row([row[k] for k in names]))
            hh=row['LCLid'];assert hh in selected
            text=row['DateTime'];assert '2012-12-24'<=text<'2014-03-03'
            t=datetime.fromisoformat(text);fraction=text.split('.',1)[1] if '.' in text else ''
            offgrid=t.minute not in (0,30) or t.second!=0 or any(c!='0' for c in fraction)
            try:
                value=Decimal(row['KWH/hh (per half hour) '].strip())
                finite=value.is_finite();nonnegative=finite and value>=0
            except InvalidOperation:value=Decimal(0);finite=False;nonnegative=False
            hour=t.strftime('%Y-%m-%dT%H:00:00')
            records[(hh,hour)].append((t.isoformat(),value,nonnegative,offgrid))
            literal_count[hh]+=1;tariffs[hh].add(row['stdorToU']);invalid_count[hh]+=not finite
            negative_count[hh]+=finite and value<0;zero_count[hh]+=finite and value==0
            offgrid_count[hh]+=offgrid;timestamps[(hh,t.isoformat())]+=1
    rows=sum(literal_count.values());assert rows==manifest['source_literal_rows']
    raw_result=None
    if args.raw:
        raw_result=scan_raw(ROOT/'work/external_deadline/source/lcl_raw/CC_LCL-FullData.csv',selected)
        assert raw_result['raw_sha256']==manifest['raw_sha256']==selection['expected_raw_sha256']==old_manifest['member']['sha256']
        assert raw_result['selected_literal_rows']==rows
        assert raw_result['selected_row_stream_sha256']==literal_hash.hexdigest()
        assert raw_result['all_source_rows_scanned']==manifest['source_rows_scanned']
    dup_count=Counter()
    for (hh,t),count in timestamps.items():
        if count>1:dup_count[hh]+=count
    eligible_count=Counter();day_count=Counter();hours_count=Counter();seen=set();max_error=0.
    with (NEW/'hourly.csv').open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            hh,hour=row['household_id'],row['timestamp_benchmark'];assert hh in selected
            key=(hh,hour);assert key not in seen;seen.add(key);hours_count[hh]+=1
            assert row['timestamp_utc']==hour+'Z'
            t=datetime.fromisoformat(hour);assert t.minute==0 and t.second==0
            assert datetime(2012,12,24)<=t<datetime(2014,3,3)
            source=records.get(key,[]);stamps=[r[0] for r in source]
            duplicate=len(stamps)!=len(set(stamps));dst=hour[:10] in ['2013-03-31','2013-10-27']
            good=len(source)==2 and not duplicate and not dst and all(v[2] and not v[3] for v in source)
            assert int(row['eligible'])==int(good),(key,'eligible')
            assert int(row['source_readings'])==len(source)
            assert int(row['invalid_readings'])==sum(not v[2] for v in source)
            assert int(row['offgrid_readings'])==sum(v[3] for v in source)
            assert int(row['dst_excluded'])==int(dst)
            if good:
                expected=float(sum((v[1] for v in source),Decimal(0)));actual=float(row['energy_kwh'])
                error=abs(expected-actual);max_error=max(max_error,error)
                assert error<=2e-14*max(1.,abs(expected)),(key,expected,actual)
                eligible_count[hh]+=1;day_count[(hh,hour[:10])]+=1
            else:assert row['energy_kwh']==''
    expected_hours=int((datetime(2014,3,3)-datetime(2012,12,24)).total_seconds()/3600)
    for hh in selected:
        assert hours_count[hh]==expected_hours
        q=quality[hh]
        for name,count in [('source_rows_in_prepared_window',literal_count[hh]),('null_nonfinite_rows',invalid_count[hh]),
                           ('negative_rows',negative_count[hh]),('zero_rows',zero_count[hh]),('duplicate_rows',dup_count[hh]),
                           ('offgrid_rows',offgrid_count[hh]),('eligible_hours',eligible_count[hh])]:assert q[name]==count,(hh,name,q[name],count)
        assert q['tariff_values']==sorted(tariffs[hh])
        t=datetime(2012,12,24)
        while t<datetime(2014,3,3):
            day=t.strftime('%Y-%m-%d');assert day_count[(hh,day)]==old_days[(hh,day)],(hh,day)
            t+=timedelta(days=1)
    report={'status':'passed','scope':'Source and training-only cohort selection audit; no forecast, model loss, or acquisition results inspected.',
            'selected_ids':selected,'selected_training_complete_days':{hh:training[hh] for hh in selected},
            'selected_source_rows_checked':rows,'hourly_rows_checked':len(seen),'eligible_hours_checked':sum(eligible_count.values()),
            'max_absolute_decimal_difference_kwh':max_error,'complete_hour_grids_checked':20,
            'all_daily_quality_counts_agree_with_prior_inventory':True,'raw_reextraction':raw_result,
            'literal_row_stream_sha256':literal_hash.hexdigest(),'wall_seconds':time.perf_counter()-started,
            'checker_sha256':sha(Path(__file__)),'manifest_sha256':sha(NEW/'manifest.json'),
            'selected_literal_file_sha256':sha(NEW/'selected_halfhour_source.csv.gz'),'hourly_sha256':sha(NEW/'hourly.csv'),
            'limitation':'Benchmark timestamps preserve provider labels; this does not verify physical timezone or actual meter arrival times.'}
    (OUT/'confirmation_source_check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

