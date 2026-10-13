"""Bind the existing 29 certificates to their frozen audit tasks.

Reads only saved forecasts/geometry and retained endpoint values. No internal
response is used to choose a policy, and no source file is modified.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;BASE=HERE.parent


def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
def stamp(t):return t.isoformat().replace('+00:00','Z')


def main():
    geometry_path=BASE/'external_validation/replay/geometry.json'
    fallback=BASE/'external_validation/stored_error_fallback'
    old_lock=json.loads((fallback/'protocol_lock.json').read_text())
    geometry_raw=geometry_path.read_bytes()
    expected=next(v['sha256'] for v in old_lock['inputs'].values() if v['path'].replace('\\','/').endswith('replay/geometry.json'))
    if sha(geometry_raw)!=expected:raise ValueError('Frozen geometry hash mismatch')
    geometry=json.loads(geometry_raw);cases={r['id']:r for r in geometry['cases']}
    cert_raw=(fallback/'fixed_batch_certificates.json').read_bytes()
    certificates=json.loads(cert_raw)['certificates']
    source_manifest=BASE/'external_heatpump/july_cache_manifest.json'
    cache=json.loads(source_manifest.read_text());values={};inputs={
        'external_validation/replay/geometry.json':sha(geometry_raw),
        'external_validation/stored_error_fallback/fixed_batch_certificates.json':sha(cert_raw),
        'external_heatpump/july_cache_manifest.json':sha(source_manifest.read_bytes())}
    for relative,key in [
        ('external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv','forecast_sha256'),
        ('external_heatpump/hourly/train_test_hourly_counters.csv','counter_sha256')]:
        actual=sha((BASE/relative).read_bytes())
        if actual!=geometry['manifest'][key]:raise ValueError('Task source artifact mismatch: '+relative)
        inputs[relative]=actual
    for source in cache['sources']:
        relative='external_heatpump/'+source['raw_path'].replace('\\','/')
        raw=(BASE/relative).read_bytes()
        if sha(raw)!=source['sha256']:raise ValueError('Public cache hash mismatch')
        values[source['system_id']]=dict(json.loads(raw,parse_float=Decimal)['heatpump_elec_kwh'])
        inputs[relative]=sha(raw)
    tasks=[]
    for cert in sorted(certificates,key=lambda r:r['id']):
        case=cases[cert['id']]
        start=datetime.fromisoformat(case['day']).replace(hour=case['start_hour'],tzinfo=timezone.utc)
        end=start+timedelta(hours=6)
        c0=F(values[case['system_id']][int(start.timestamp())]);c6=F(values[case['system_id']][int(end.timestamp())])
        total=c6-c0
        if total<=0 or total!=F(case['E_exact']):raise ValueError('Retained total mismatch')
        coefficients=[str(F.from_float(float(c))) for c in case['c']]
        if coefficients!=cert['original_coefficients_exact']:raise ValueError('Certificate coefficient mismatch')
        task={'case_id':case['id'],'system_id':case['system_id'],'source':'HeatpumpMonitor public cached API',
              'feed_key':'heatpump_elec_kwh','start_utc':stamp(start),'end_utc':stamp(end),
              'query_timestamps_utc':{str(k):stamp(start+timedelta(hours=k)) for k in range(1,6)},
              'timestamp_semantics':'requested API grid; native measurement and arrival timestamps unknown',
              'forecast_issue_utc':case['forecast_issue_utc'],'forecast_issue_semantics':'declared retrospective schedule',
              'models':[case['model_a'],case['model_b']],
              'contrast_coefficients_exact':coefficients,'contrast_constant_exact':str(F.from_float(float(case['d']))),
              'contrast_semantics':'saved paired MSE affine contrast, exact binary64 coefficient representation',
              'start_counter_kwh_exact':str(c0),'end_counter_kwh_exact':str(c6),'total_kwh_exact':str(total),
              'reading_unit':'kWh cumulative stored readout',
              'normalization':'(stored counter - exact retained start counter) / exact retained total',
              'error_bound_over_total_exact':'1/100','precision_over_initial_width_exact':'1/2',
              'forecast_artifact_sha256':geometry['manifest']['forecast_sha256'],
              'counter_artifact_sha256':geometry['manifest']['counter_sha256'],
              'certificate_artifact_sha256':sha(cert_raw),
              'scope':'This saved task only; metadata binding is not origin authentication or sensor calibration'}
        tasks.append({'task':task,'task_sha256':sha(canonical(task))})
    manifest={'schema':'saved-audit-task-binding-v1','inputs':inputs,'tasks':tasks,
              'scope':'Existing29 task bindings; no outcome experiment or change to certificates'}
    output=HERE/'task_manifest.json';output.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'status':'PASS','tasks':len(tasks),'retained_endpoints_checked':2*len(tasks),
                      'manifest_sha256':sha(output.read_bytes())},indent=2))


if __name__=='__main__':main()
