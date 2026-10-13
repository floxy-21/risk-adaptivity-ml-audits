"""Frozen NOAA natural coarsening / GEFS source feasibility panel. No paid queries."""
from pathlib import Path
import sys, csv, json, hashlib, re, calendar, time, threading
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'python_deps'))
import eccodes
import numpy as np

CACHE = HERE / 'gefs_cache'
CACHE.mkdir(exist_ok=True)
STATION = 'USC00010140'
MEMBERS = ['c00', 'p01', 'p02', 'p03', 'p04']
DECODE_LOCK = threading.Lock()
DATES = ['2008-12-05','2008-12-10','2008-12-11','2008-12-17','2008-12-28','2008-12-29','2009-06-05','2009-06-14','2009-06-24']
SHA = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def dump(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

def request(url, headers=None):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers or {}), timeout=90) as r:
                return r.read(), r.status, dict(r.headers)
        except Exception:
            if attempt == 2: raise
            time.sleep(attempt+1)

def observations():
    source = HERE/(STATION+'.csv')
    assert SHA(source) == 'acc9ae944c00b783061613c6fd2cb50ec3d547ef7b013df8383dca259ec85cb8'
    rows = {r['DATE']:r for r in csv.DictReader(source.open(newline=''))}
    panel=[]; excluded=[]
    for year, month in [(2008,12),(2009,6)]:
        for d in range(1,calendar.monthrange(year,month)[1]+1):
            day=f'{year:04}-{month:02}-{d:02}'
            r=rows.get(day)
            if r is None:
                excluded.append(dict(date=day,reason='no station daily row')); continue
            v=[int(r[f'HR{h:02}Val']) for h in range(24)]
            mf=[r[f'HR{h:02}MF'].strip() for h in range(24)]
            qf=[r[f'HR{h:02}QF'].strip() for h in range(24)]
            if day in DATES:
                assert mf == ['a']+['.']*22+['A'] and all(x==-9999 for x in v[:23]) and v[23]>=0
                assert qf[-1]=='A'
                case=dict(date=day,kind='natural_accumulation',total_mm=v[23]*.254,truth_3h_mm=None)
            elif all(x>=0 for x in v) and all(not x for x in qf) and not any(x in ['a','.','A'] for x in mf):
                truth=[sum(v[h:h+3])*.254 for h in range(0,24,3)]
                case=dict(date=day,kind='complete_control',total_mm=sum(truth),truth_3h_mm=truth)
            else:
                excluded.append(dict(date=day,reason='incomplete/flagged or multi-day accumulation outside fixed one-day panel'));continue
            case.update(hourly_source_record=r, utc_start=day+'T06:00:00Z', lead_hours=list(range(6,31,3)))
            panel.append(case)
    assert len(panel)==52 and len(excluded)==9
    dump('observation_panel.json',dict(protocol_sha256=SHA(HERE/'protocol.txt'),source_sha256=SHA(source),cases=panel,excluded=excluded))
    return panel

def forecast(day,member):
    stamp=day.replace('-','')+'00'
    base=f'https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast/{stamp[:4]}/{stamp}/{member}/Days:1-10/apcp_sfc_{stamp}_{member}.grib2'
    tag=f'{stamp}_{member}'
    idx=CACHE/(tag+'.idx'); grib=CACHE/(tag+'.grib2'); meta=CACHE/(tag+'.json')
    if not idx.exists(): idx.write_bytes(request(base+'.idx')[0])
    entries=[]
    for line in idx.read_text().splitlines():
        fields=line.split(':'); match=re.search(r':(\d+)-(\d+) hour acc fcst:',line)
        if match: entries.append((int(fields[1]),int(match[1]),int(match[2])))
    selected=[i for i,e in enumerate(entries) if 9<=e[2]<=30]
    assert len(selected)==8 and selected==list(range(selected[0],selected[0]+8))
    start=entries[selected[0]][0];end=entries[selected[-1]+1][0]-1
    if not grib.exists() or not meta.exists():
        data,status,headers=request(base,{'Range':f'bytes={start}-{end}'})
        assert status==206 and len(data)==end-start+1
        assert headers.get('Content-Range','').startswith(f'bytes {start}-{end}/')
        grib.write_bytes(data)
        meta.write_text(json.dumps(dict(url=base,index_url=base+'.idx',download_utc=datetime.now(timezone.utc).isoformat(),status=status,headers=headers,range_start=start,range_end=end,index_sha256=SHA(idx),range_sha256=SHA(grib)),indent=2)+'\n')
    provenance=json.loads(meta.read_text())
    assert provenance['index_sha256']==SHA(idx) and provenance['range_sha256']==SHA(grib)
    values=[];messages=[]
    with DECODE_LOCK, grib.open('rb') as f:
        while (gid:=eccodes.codes_grib_new_from_file(f)) is not None:
            try:
                m={k:eccodes.codes_get(gid,k) for k in ['dataDate','dataTime','validityDate','validityTime','startStep','endStep','units','shortName','perturbationNumber','binaryScaleFactor','decimalScaleFactor','packingType']}
                assert m['dataDate']==int(stamp[:8]) and m['dataTime']==0
                assert m['shortName']=='tp' and m['units']=='kg m**-2' and m['perturbationNumber']==int(member[1:])
                valid=datetime.strptime(stamp,'%Y%m%d%H')+timedelta(hours=m['endStep'])
                assert m['validityDate']==int(valid.strftime('%Y%m%d')) and m['validityTime']==int(valid.strftime('%H%M'))
                near=eccodes.codes_grib_find_nearest(gid,32.2322,272.5896,npoints=1)[0]
                assert near['lat']==32.25 and near['lon']==272.5
                m.update(dict(near)); messages.append(m); values.append(float(near['value']))
            finally: eccodes.codes_release(gid)
    assert [(m['startStep'],m['endStep']) for m in messages]==[(6,9),(6,12),(12,15),(12,18),(18,21),(18,24),(24,27),(24,30)]
    signed=[values[i] if i%2==0 else values[i]-values[i-1] for i in range(8)]
    bins=[];repairs=[]
    for i in range(0,8,2):
        first,total=values[i:i+2]
        assert first>=0 and total>=0
        error_bound=.5*sum(2**messages[j]['binaryScaleFactor']/10**messages[j]['decimalScaleFactor'] for j in [i,i+1])
        assert first-total<=error_bound+1e-8,(day,member,first,total,error_bound)
        repaired=min(first,total)
        bins.extend([repaired,total-repaired])
        if first>total:repairs.append(dict(first_bin=i,raw_first=first,raw_second=total-first,retained_six_hour_total=total,packing_error_bound=error_bound))
    return dict(date=day,member=member,forecast_3h_mm=bins,signed_raw_3h_mm=signed,packing_repairs=repairs,messages=messages,provenance=provenance)

def bounds(a,b,total):
    a=np.array(a);b=np.array(b)
    c=2*(b-a)/8; constant=float(np.mean(a*a-b*b))
    lo=constant+total*float(min(c));hi=constant+total*float(max(c))
    uniform=constant+total*float(np.mean(c))
    # All8 simplex vertices independently evaluate the original quadratic contrast.
    ys=np.eye(8)*total
    direct=np.mean((ys-a)**2-(ys-b)**2,axis=1)
    assert np.allclose([lo,hi],[direct.min(),direct.max()],atol=1e-8,rtol=1e-9)
    # Individual squared-loss minimum is simplex projection; maximum is a vertex.
    intervals=[]
    for pred in [a,b]:
        ordered=np.sort(pred)[::-1]; cumulative=np.cumsum(ordered)-total
        rho=np.nonzero(ordered-cumulative/np.arange(1,9)>0)[0]
        theta=cumulative[rho[-1]]/(rho[-1]+1) if len(rho) else float(max(pred))
        projected=np.maximum(pred-theta,0)
        if total==0: projected=np.zeros(8)
        assert abs(sum(projected)-total)<1e-8
        intervals.append([float(np.mean((projected-pred)**2)),float(np.max(np.mean((ys-pred)**2,axis=1)))])
    independent=[intervals[0][0]-intervals[1][1],intervals[0][1]-intervals[1][0]]
    assert independent[0]<=lo+1e-8 and independent[1]>=hi-1e-8
    return dict(lower=lo,upper=hi,width=hi-lo,uniform_point=uniform,individual_a=intervals[0],individual_b=intervals[1],independent_contrast=independent)

def main():
    # Prime ecCodes definitions on the main thread; decoder calls are serialized.
    primer=eccodes.codes_grib_new_from_samples('regular_ll_sfc_grib2')
    eccodes.codes_release(primer)
    start=time.monotonic();panel=observations();results={};failures=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures={pool.submit(forecast,c['date'],m):(c['date'],m) for c in panel for m in MEMBERS}
        for i,f in enumerate(as_completed(futures),1):
            key=futures[f]
            try: results[key]=f.result()
            except Exception as e: failures.append(dict(date=key[0],member=key[1],error=repr(e)))
            if i%20==0: print(f'forecasts {i}/{len(futures)}, failures={len(failures)}, seconds={time.monotonic()-start:.1f}',flush=True)
    forecasts=[results[k] for k in sorted(results)]
    dump('forecast_panel.json',dict(script_sha256=SHA(__file__),protocol_sha256=SHA(HERE/'protocol.txt'),records=forecasts,failures=failures))
    cases=[]
    for c in panel:
        day=c['date']
        if not all((day,m) in results for m in MEMBERS):continue
        a=np.array(results[day,'c00']['forecast_3h_mm']);b=np.mean([results[day,m]['forecast_3h_mm'] for m in MEMBERS],axis=0)
        out=dict(date=day,kind=c['kind'],total_mm=c['total_mm'],control_3h_mm=a.tolist(),ensemble_3h_mm=b.tolist(),**bounds(a,b,c['total_mm']))
        raw_a=results[day,'c00']['signed_raw_3h_mm'];raw_b=np.mean([results[day,m]['signed_raw_3h_mm'] for m in MEMBERS],axis=0)
        out['signed_unrepaired_sensitivity']=bounds(raw_a,raw_b,c['total_mm'])
        out['strict_decision']='control' if out['upper'] < -1e-10 else 'ensemble' if out['lower'] >1e-10 else 'unresolved'
        out['record_total_bias_control']=float(sum(a)-c['total_mm']);out['record_total_bias_ensemble']=float(sum(b)-c['total_mm'])
        if c['truth_3h_mm'] is not None:
            truth=np.array(c['truth_3h_mm']);out['observed_mse_control']=float(np.mean((truth-a)**2));out['observed_mse_ensemble']=float(np.mean((truth-b)**2))
            out['observed_gap']=out['observed_mse_control']-out['observed_mse_ensemble']
            assert out['lower']-1e-8<=out['observed_gap']<=out['upper']+1e-8
        cases.append(out)
    summaries={}
    for kind in ['natural_accumulation','complete_control']:
        group=[c for c in cases if c['kind']==kind]
        summaries[kind]=dict(days=len(group),strict_control=sum(c['strict_decision']=='control' for c in group),strict_ensemble=sum(c['strict_decision']=='ensemble' for c in group),unresolved=sum(c['strict_decision']=='unresolved' for c in group),mean_lower=float(np.mean([c['lower'] for c in group])),mean_upper=float(np.mean([c['upper'] for c in group])))
    result=dict(status='passed' if not failures else 'incomplete_with_failures',script_sha256=SHA(__file__),protocol_sha256=SHA(HERE/'protocol.txt'),elapsed_seconds=time.monotonic()-start,forecast_records=len(forecasts),failures=failures,cases=cases,summary=summaries,scope='Natural recorded-total feasible sets; no natural hidden-hour ground truth or paid recovery claim. Complete-control coarsening is artificial diagnostic only. Public alternate-source audit is separately recorded.')
    dump('panel_result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))

if __name__=='__main__':main()
