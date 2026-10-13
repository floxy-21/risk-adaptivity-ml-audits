"""Check source-to-frozen-forecast-to-coefficient lineage, without fitting models.

External mode is offline and uses bundled attributed source responses. All mode
additionally requires the original pinned BLEM cache and freshly regenerated
geometry/endpoints. Reports contain identifiers and hashes, not raw BLEM data.
No policy-producer module is imported. Certificate/replay checks are separate.
"""
import argparse, csv, hashlib, io, json, tempfile, time
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
JC = HERE.parent
BASE = JC.parent
ROOT = BASE.parents[1]
MODELS = ('daily', 'ridge', 'hist_gradient_boosting', 'mlp')
PINNED = {
    'data_blem_consumer-00000001.csv': '9228795c6369ce144fbb929f9d413397545f86e3a95d2f9a0f27c92f1d55ad8d',
    'data_blem_consumer-00000002.csv': '93d142217c74ab2c12a98035b3ea178ead234fec0b71942e8e90db5b7e6a2ef3',
    'data_blem_consumer-00000003.csv': 'db69719d2262ebeb6df39abafffca2805c8a03b1b4777f86eb8aa78acf578b6c',
}
ORIGINAL_FORECAST = 'fc7a7f6097e4b65b34ec297ee6e73b02420a0481d82636c984bb0155b38123e0'
ORIGINAL_RESTORED = 'c1f6d2663d228aeeb8073226488ea8f2fca6b14b308e4a4f62ce38482c93f8e6'
EXTERNAL_FORECAST = '04dc64193fbcf00879e4f7ba5224d5626def79a8caad474fb3242d3d8d69b12f'
EXTERNAL_COUNTERS = 'b66ed33d2b1b00ac680bf564c3329231317b8176b7e88ac318ee0714494077da'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require_hash(p, expected):
    actual = sha(p)
    if actual != expected:
        raise ValueError(f'Pinned source mismatch: {p}; expected {expected}; got {actual}')
    return actual


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)


def original_inputs(a, hashes):
    raw = {}
    for name, expected in PINNED.items():
        path = a.raw_dir / name
        hashes[str(path)] = require_hash(path, expected)
        meter = name.removeprefix('data_blem_').removesuffix('.csv').replace('-', '_')
        with path.open(newline='', encoding='utf-8-sig') as handle:
            records = [(int(r['time']), int(r['energy'])) for r in csv.DictReader(handle)]
        assert records == sorted(records) and len({t for t, _ in records}) == len(records)
        raw[meter] = dict(records)
    hashes[str(a.original_endpoints)] = sha(a.original_endpoints)
    hourly = {}
    with a.original_endpoints.open(newline='') as handle:
        for r in csv.DictReader(handle):
            start = stamp(r['interval_start_utc']); end = stamp(r['interval_end_utc'])
            assert end - start == timedelta(hours=1)
            assert stamp(r['actual_start_snapshot_utc']) == start
            assert stamp(r['actual_end_snapshot_utc']) == end
            assert float(r['start_lag_seconds']) == float(r['end_lag_seconds']) == 0
            t0, t1 = int(start.timestamp()*1000), int(end.timestamp()*1000)
            values = [raw[r['meter']][t] for t in range(t0, t1+1, 180000)]
            assert len(values) == 21 and min(b-a for a,b in zip(values,values[1:])) >= 0
            assert values[0] == int(r['start_counter_integer'])
            assert values[-1] == int(r['end_counter_integer'])
            value = F(values[-1]-values[0], 10**10)
            assert abs(float(value)-float(r['energy_kwh'])) < 1e-14
            hourly[r['meter'], start] = value
    path = ROOT/'outputs/review_frozen_forecasts.csv'
    hashes[str(path)] = require_hash(path, ORIGINAL_FORECAST)
    manifest = json.loads((ROOT/'outputs/review_frozen_forecasts.json').read_text())
    assert manifest['output_sha256'] == ORIGINAL_FORECAST
    assert manifest['original_predictions_sha256'] == ORIGINAL_RESTORED
    forecasts = {}; restored_rows = []; changed = 0
    # This parser reproduces the historical CSV conversion, not a new fit.
    import pandas as pd
    hourly_csv = a.original_endpoints.with_name('data_blem_hourly.csv')
    historical = pd.read_csv(hourly_csv, index_col=0, parse_dates=True)
    hashes[str(hourly_csv)] = sha(hourly_csv)
    with path.open(newline='') as handle:
        reader = csv.reader(handle); header = next(reader)
        assert header == ['cohort','meter','timestamp','truth_kwh',*MODELS]
        for row in reader:
            if row[0] == 'blem_counters':
                meter, t = row[1], stamp(row[2]); assert row[3] == row[4] == ''
                target, lag = hourly[meter,t], hourly[meter,t-timedelta(days=1)]
                original_t = pd.Timestamp(row[2])
                row[3] = str(float(historical[meter].loc[original_t]))
                row[4] = str(float(historical[meter].loc[original_t-pd.Timedelta(days=1)]))
                assert abs(float(row[3])-float(target)) < 1e-14
                assert abs(float(row[4])-float(lag)) < 1e-14
                forecasts[meter,t] = dict(zip(MODELS, map(float,row[4:])))
                changed += 1
            restored_rows.append(row)
    stream = io.StringIO(newline=''); writer = csv.writer(stream)
    writer.writerow(header); writer.writerows(restored_rows)
    restored_sha = hashlib.sha256(stream.getvalue().encode()).hexdigest()
    assert restored_sha == ORIGINAL_RESTORED and changed == 6552 and len(restored_rows) == 89496
    return forecasts, hourly, {'verified_hourly_endpoints':len(hourly), 'restored_blem_rows':changed,
        'restored_mixed_archive_rows':len(restored_rows), 'restored_archive_sha256':restored_sha,
        'restoration_scope':'Rebuild BLEM targets/persistence from pinned counters; preserve all other frozen CSV fields. UCI raw targets are not rechecked by this focused original-counter chain.'}


def external_inputs(hashes):
    folder = BASE/'external_heatpump/hourly'
    csv_path = folder/'train_test_hourly_counters.csv'
    hashes[str(csv_path)] = require_hash(csv_path, EXTERNAL_COUNTERS)
    with csv_path.open(newline='') as handle:
        exported = {(int(r['system_id']),stamp(r['timestamp_utc'])):
                    F(r['counter_kwh']) if r['valid']=='1' else None for r in csv.DictReader(handle)}
    source = {}; n = 0
    july_manifest = json.loads((BASE/'external_heatpump/july_cache_manifest.json').read_text())
    for r in july_manifest['sources']:
        path = BASE/'external_heatpump'/r['raw_path'].replace('\\','/')
        require_hash(path, r['sha256'])
    for ident in (1,2,7):
        for suffix in ('train_2025H1', 'test_2025July'):
            path = folder/f'system_{ident}_{suffix}.json'; hashes[str(path)] = sha(path)
            records = json.loads(path.read_text(), parse_float=Decimal)['heatpump_elec_kwh']
            for t, value in records:
                key = (ident, datetime.fromtimestamp(int(t), timezone.utc))
                exact = F(value) if value is not None else None
                assert exported[key] == exact
                if key in source: assert source[key] == exact
                source[key] = exact; n += 1
    assert set(source) == set(exported)
    path = BASE/'external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv'
    hashes[str(path)] = require_hash(path, EXTERNAL_FORECAST)
    training_path = path.with_name('training_report.json'); hashes[str(training_path)] = sha(training_path)
    training = json.loads(training_path.read_text())
    assert training['status'] == 'PASS' and training['forecast_sha256'] == EXTERNAL_FORECAST
    assert set(training['source_hashes'].values()) == {EXTERNAL_COUNTERS}
    forecasts = {}; lag_checks = 0
    with path.open(newline='') as handle:
        for r in csv.DictReader(handle):
            ident = int(r['system_id']); t, issue = stamp(r['timestamp_utc']), stamp(r['issue_utc'])
            assert issue == t.replace(hour=0) and t >= issue
            lag = t-timedelta(days=1); assert lag+timedelta(hours=1) <= issue
            actual = source[ident,lag+timedelta(hours=1)]-source[ident,lag]
            assert abs(float(r['daily'])-float(actual)) < 1e-12
            forecasts[f'hpm_{ident}',t] = {m:float(r[m]) for m in MODELS}; lag_checks += 1
    assert lag_checks == 2232
    return forecasts, source, {'provider_decimal_tokens_verified':n, 'unique_hourly_records':len(source),
                               'frozen_forecast_rows':len(forecasts),'causal_persistence_checks':lag_checks}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort',choices=('external','all'),default='external')
    ap.add_argument('--raw-dir',type=Path)
    ap.add_argument('--original-geometry',type=Path,nargs='+')
    ap.add_argument('--original-endpoints',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    a = ap.parse_args(); start=time.perf_counter(); hashes={}; sources=[]; metrics={}
    ef, er, metrics['external'] = external_inputs(hashes)
    sources.append(('external',BASE/'external_validation/replay/geometry.json'))
    of, oh = {},{}
    if a.cohort=='all':
        assert a.raw_dir and a.original_geometry and a.original_endpoints
        of, oh, metrics['original'] = original_inputs(a,hashes)
        sources += [('original',p) for p in a.original_geometry]
    counts=Counter(); blocks={}; errors={'coefficient':0.,'constant':0.,'total':0.}; row_checks=0
    for cohort,path in sources:
        hashes[str(path)]=sha(path); doc=json.loads(path.read_text())
        for r in doc['cases']:
            meter=r['meter']; t=stamp(r['day']).replace(hour=r['start_hour']); forecasts=ef if cohort=='external' else of
            av=[forecasts[meter,t+timedelta(hours=h)][r['model_a']] for h in range(6)]
            bv=[forecasts[meter,t+timedelta(hours=h)][r['model_b']] for h in range(6)]
            c=[2*(b-aa)/6 for aa,b in zip(av,bv)]; d=sum(aa*aa-b*b for aa,b in zip(av,bv))/6
            if cohort=='original':
                E=sum(oh[meter,t+timedelta(hours=h)] for h in range(6))
            else:
                ident=int(meter.removeprefix('hpm_')); E=er[ident,t+timedelta(hours=6)]-er[ident,t]
                assert F(r['E_exact'])==E
            diffs={'coefficient':max(abs(u-v) for u,v in zip(c,r['c'])), 'constant':abs(d-r['d']), 'total':abs(float(E)-r['E'])}
            for key,value in diffs.items():
                errors[key]=max(errors[key],value)
                scale=max(1.,abs(d)) if key=='constant' else max(1.,*map(abs,c)) if key=='coefficient' else max(1.,float(E))
                assert value <= 1e-12*scale, (r['id'],key,value)
            assert stamp(r['forecast_issue_utc'])==t.replace(hour=0)
            assert stamp(r['cutoff_utc'])==t+timedelta(hours=6)
            assert abs(r['W0']-float(E)*(max(r['c'])-min(r['c']))) < 1e-12*max(1.,r['W0'])
            key=f'{cohort}/{meter}/{r["day"]}/{r["start_hour"]:02d}'
            blocks.setdefault(key,[]).append(r['id']); counts[cohort]+=1; row_checks+=6
    expected={'external':1674}; expected_blocks={'external':279}
    if a.cohort=='all': expected['original']=4914; expected_blocks['original']=819
    assert dict(counts)==expected and all(len(v)==6 and len(set(v))==6 for v in blocks.values())
    assert dict(Counter(k.split('/')[0] for k in blocks))==expected_blocks
    # An explicit local corruption guard demonstrates fail-closed identity checks.
    with tempfile.TemporaryDirectory(prefix='source_identity_guard_') as tmp:
        probe=Path(tmp)/'source'; probe.write_bytes(b'known source')
        expected_digest=sha(probe); require_hash(probe,expected_digest)
        probe.write_bytes(b'changed source'); rejected=False
        try: require_hash(probe,expected_digest)
        except ValueError: rejected=True
        assert rejected
    report={'status':'PASS','cohort':a.cohort,'source_metrics':metrics,'coefficient_cases':dict(counts),
        'physical_blocks':expected_blocks,'six_hour_forecast_row_checks':row_checks,'maximum_float_differences':errors,
        'coefficient_tolerance':'1e-12 times max(1, magnitude), allowing historical CSV/binary64 conversion only',
        'units':{'original':'Integer counter subtraction first, divided by 10^10 to kWh; exact hourly boundaries with 21 nondecreasing three-minute snapshots.',
                 'external':'Exact decimal differences of stored API-grid cumulative kWh values; no native hardware/calibration claim.'},
        'training_scope':'Frozen forecast assets and their source linkage; no model refit, independent training validation or untouched evaluation.',
        'changed_source_guard_rejected':rejected,
        'source_sha256':sha(Path(__file__)),'input_sha256':hashes,'case_ids_by_block':blocks,
        'elapsed_seconds':time.perf_counter()-start}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','coefficient_cases','physical_blocks','maximum_float_differences','elapsed_seconds')},indent=2))


if __name__=='__main__': main()
