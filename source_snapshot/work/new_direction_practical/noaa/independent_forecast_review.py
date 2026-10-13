"""Independent raw-GRIB and numerical audit. Does not import the builder."""
from pathlib import Path
import sys,json,hashlib,math,re,time
from datetime import datetime,timedelta,timezone
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'python_deps'))
import eccodes
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def near(a,b):assert math.isclose(a,b,abs_tol=1e-9,rel_tol=1e-10),(a,b)
def interval(a,b,total):
    # Independent evaluation of all extreme allocations in the original loss.
    vals=[]
    for j in range(8):
        y=[total if i==j else 0. for i in range(8)]
        vals.append(math.fsum((y[i]-a[i])**2-(y[i]-b[i])**2 for i in range(8))/8)
    return min(vals),max(vals)
def main():
    start=time.perf_counter();fp=HERE/'forecast_panel.json';pp=HERE/'panel_result.json'
    fdata=json.loads(fp.read_text());panel=json.loads(pp.read_text());obs=json.loads((HERE/'observation_panel.json').read_text())
    assert len(fdata['records'])==260 and not fdata['failures'] and panel['status']=='passed'
    assert len(panel['cases'])==52
    records={(r['date'],r['member']):r for r in fdata['records']}
    assert len(records)==260 and {d for d,m in records}=={c['date'] for c in obs['cases']}
    headers=[];negative=[];independent_values={};max_value_error=0.;max_projection_error=0.
    for (date,member),record in sorted(records.items()):
        stamp=date.replace('-','')+'00';tag=stamp+'_'+member
        path=HERE/'gefs_cache'/(tag+'.grib2');idx=path.with_suffix('.idx')
        provenance=record['provenance'];assert sha(path)==provenance['range_sha256'] and sha(idx)==provenance['index_sha256']
        assert path.stat().st_size==provenance['range_end']-provenance['range_start']+1
        assert provenance['status']==206
        assert provenance['headers']['Content-Range'].startswith(f"bytes {provenance['range_start']}-{provenance['range_end']}/")
        entries=[]
        for line in idx.read_text().splitlines():
            found=re.search(r':(\d+)-(\d+) hour acc fcst:',line)
            if found:entries.append((int(line.split(':')[1]),int(found[1]),int(found[2])))
        selected=[i for i,e in enumerate(entries) if e[2] in [9,12,15,18,21,24,27,30]]
        assert len(selected)==8 and provenance['range_start']==entries[selected[0]][0] and provenance['range_end']==entries[selected[-1]+1][0]-1
        decoded=[];steps=[];file_headers=[]
        with path.open('rb') as stream:
            while (handle:=eccodes.codes_grib_new_from_file(stream)) is not None:
                try:
                    keys=['dataDate','dataTime','validityDate','validityTime','startStep','endStep','stepUnits','forecastTime',
                          'units','shortName','perturbationNumber','packingType','referenceValue','bitsPerValue','binaryScaleFactor','decimalScaleFactor',
                          'Ni','Nj','latitudeOfFirstGridPointInDegrees','longitudeOfFirstGridPointInDegrees','iScansNegatively','jScansPositively','jPointsAreConsecutive']
                    h={k:eccodes.codes_get(handle,k) for k in keys}
                    assert h['dataDate']==int(stamp[:8]) and h['dataTime']==0 and h['stepUnits']==1
                    valid=datetime.strptime(stamp,'%Y%m%d%H')+timedelta(hours=h['endStep'])
                    assert h['validityDate']==int(valid.strftime('%Y%m%d')) and h['validityTime']==int(valid.strftime('%H%M'))
                    assert h['units']=='kg m**-2' and h['shortName']=='tp' and h['perturbationNumber']==int(member[1:])
                    assert [h['Ni'],h['Nj'],h['latitudeOfFirstGridPointInDegrees'],h['longitudeOfFirstGridPointInDegrees'],h['iScansNegatively'],h['jScansPositively'],h['jPointsAreConsecutive']]==[1440,721,90.,0.,0,0,0]
                    # Compute the nearest rectilinear-grid index independently;
                    # do not call the builder's nearest-point routine.
                    row=round((90.-32.2322)/.25);col=round((360.-87.4104)/.25)
                    index=row*1440+col;assert index==333730
                    value=float(eccodes.codes_get_elements(handle,'values',[index])[0])
                    stored=record['messages'][len(decoded)]
                    max_value_error=max(max_value_error,abs(value-stored['value']));near(value,stored['value'])
                    assert stored['lat']==90.-row*.25 and stored['lon']==col*.25
                    for key in ['dataDate','dataTime','validityDate','validityTime','startStep','endStep','units','shortName','perturbationNumber','binaryScaleFactor','decimalScaleFactor','packingType']:assert h[key]==stored[key]
                    decoded.append(value);steps.append((h['startStep'],h['endStep']))
                    h.update(date=date,member=member,message=len(decoded)-1,grid_index=index,grid_value=value,source_range_sha256=provenance['range_sha256'])
                    headers.append(h);file_headers.append(h)
                finally:eccodes.codes_release(handle)
        assert steps==[(6,9),(6,12),(12,15),(12,18),(18,21),(18,24),(24,27),(24,30)]
        signed=[];projected=[]
        for j in range(0,8,2):
            first,total=decoded[j:j+2]
            signed.extend([first,total-first]);assert min(first,total)>=0
            step3=2**file_headers[j]['binaryScaleFactor']*10**(-file_headers[j]['decimalScaleFactor'])
            step6=2**file_headers[j+1]['binaryScaleFactor']*10**(-file_headers[j+1]['decimalScaleFactor'])
            envelope=(step3+step6)/2
            if first>total:
                assert first-total<=envelope+1e-8
                negative.append({'date':date,'member':member,'first_bin':j,'signed_difference_mm':total-first,
                    'packing_step_first':step3,'packing_step_total':step6,'half_step_sum':envelope})
            point=max(0.,min(total,first));projected.extend([point,total-point])
            near(sum(projected[-2:]),total)
        for a,b in zip(signed,record['signed_raw_3h_mm']):near(a,b)
        for a,b in zip(projected,record['forecast_3h_mm']):max_projection_error=max(max_projection_error,abs(a-b));near(a,b)
        independent_values[date,member]=(projected,signed)
    observed={c['date']:c for c in obs['cases']};decisions={};raw_decision_changes=[];max_endpoint_error=0.;control_checks=0
    for case in panel['cases']:
        day=case['date'];total=observed[day]['total_mm'];near(case['total_mm'],total)
        a=independent_values[day,'c00'][0];b=[math.fsum(independent_values[day,m][0][j] for m in ['c00','p01','p02','p03','p04'])/5 for j in range(8)]
        for x,y in zip(a,case['control_3h_mm']):near(x,y)
        for x,y in zip(b,case['ensemble_3h_mm']):near(x,y)
        lo,hi=interval(a,b,total)
        max_endpoint_error=max(max_endpoint_error,abs(lo-case['lower']),abs(hi-case['upper']))
        near(lo,case['lower']);near(hi,case['upper'])
        dec='control' if hi < -1e-10 else 'ensemble' if lo>1e-10 else 'unresolved'
        assert dec==case['strict_decision'];decisions.setdefault(case['kind'],[]).append(dec)
        raw_a=independent_values[day,'c00'][1];raw_b=[math.fsum(independent_values[day,m][1][j] for m in ['c00','p01','p02','p03','p04'])/5 for j in range(8)]
        rl,rh=interval(raw_a,raw_b,total);near(rl,case['signed_unrepaired_sensitivity']['lower']);near(rh,case['signed_unrepaired_sensitivity']['upper'])
        rd='control' if rh < -1e-10 else 'ensemble' if rl>1e-10 else 'unresolved'
        if rd!=dec:raw_decision_changes.append({'date':day,'raw':rd,'projected':dec})
        if observed[day]['truth_3h_mm'] is not None:
            y=observed[day]['truth_3h_mm'];msea=math.fsum((u-v)**2 for u,v in zip(y,a))/8;mseb=math.fsum((u-v)**2 for u,v in zip(y,b))/8
            near(msea,case['observed_mse_control']);near(mseb,case['observed_mse_ensemble']);assert lo-1e-8<=msea-mseb<=hi+1e-8
            assert sum(y)==0;control_checks+=1
    for kind,decs in decisions.items():
        s=panel['summary'][kind];assert s['days']==len(decs) and s['strict_control']==decs.count('control') and s['strict_ensemble']==decs.count('ensemble') and s['unresolved']==decs.count('unresolved')
    with (HERE/'independent_grib_headers.jsonl').open('w') as stream:
        for h in headers:stream.write(json.dumps(h)+'\n')
    result={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.perf_counter()-start,
      'builder_imported':False,'forecast_records':len(records),'raw_grib_messages_redecoded':len(headers),
      'independent_grid_values_redecoded':len(headers),'station_grid_index':333730,'grid_value_max_difference':max_value_error,
      'nonnegative_projection_max_difference':max_projection_error,'endpoint_max_difference':max_endpoint_error,
      'negative_derived_bins':negative,'negative_member_days':len({(x['date'],x['member']) for x in negative}),
      'raw_vs_projected_decision_changes':raw_decision_changes,'complete_controls_checked':control_checks,'all_controls_zero':True,
      'source_hashes':{f:sha(HERE/f) for f in ['build_panel.py','protocol.txt','implementation_note.txt','forecast_panel.json','panel_result.json','observation_panel.json']},
      'headers_sha256':sha(HERE/'independent_grib_headers.jsonl'),
      'scope':'Full local raw-GRIB re-decoding, independently computed nearest rectilinear-grid index, fixed observed-source panel, byte-range hashes, all numerical endpoints. A distributed metadata-only reproducer cannot itself repeat raw-GRIB decoding without downloading pinned ranges.',
      'timing_interpretation':'Published Guan2022 section3b describes physical03UTC initialization and corrections to initial00-03/00-06 fields. Raw header validity confirms the audited06UTC to next06UTC window; nominal00-based leads do not receive an extra3h shift.',
      'packing_interpretation':'All negative nested differences lie within the stated half-step-sum envelope. This is consistent with differential quantization; the projection is explicitly forecast preprocessing, not proof of original unrounded model values or physical rainfall accuracy.'}
    (HERE/'independent_forecast_review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='negative_derived_bins'},indent=2))
if __name__=='__main__':main()
