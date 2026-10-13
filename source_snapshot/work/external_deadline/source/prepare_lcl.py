"""Build quality-filtered paired-label hourly references from official LCL data.
No forecasting, ranking, acquisition or test-outcome optimization occurs here.
"""
from __future__ import annotations
import argparse, hashlib, json, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'data' / 'lcl'
START = '2012-12-24'
END = '2014-03-03'
DST_DAYS = ['2013-03-31', '2013-10-27']
ENERGY = 'KWH/hh (per half hour) '

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def hourly_reference(frame, start=START, end=END):
    t = pd.to_datetime(frame.DateTime, format='ISO8601', errors='raise')
    y = pd.to_numeric(frame[ENERGY].str.strip(), errors='coerce')
    dup = t.duplicated(keep=False)
    offgrid = (t.dt.minute % 30 != 0) | (t.dt.second != 0) | (t.dt.microsecond != 0) | (t.dt.nanosecond != 0)
    valid = np.isfinite(y) & (y >= 0)
    x = pd.DataFrame({'hour': t.dt.floor('h'), 'energy': y, 'valid': valid.astype(int), 'duplicate': dup.astype(int), 'offgrid': offgrid.astype(int)})
    group = x.groupby('hour').agg(energy_kwh=('energy', 'sum'), source_readings=('energy', 'size'), valid_readings=('valid', 'sum'), duplicate_readings=('duplicate', 'sum'), offgrid_readings=('offgrid', 'sum'))
    index = pd.date_range(start, end, inclusive='left', freq='h')
    group = group.reindex(index)
    for c in ['source_readings', 'valid_readings', 'duplicate_readings', 'offgrid_readings']:
        group[c] = group[c].fillna(0).astype(int)
    group['invalid_readings'] = group.source_readings - group.valid_readings
    group['dst_excluded'] = group.index.strftime('%Y-%m-%d').isin(DST_DAYS).astype(int)
    good = (group.source_readings == 2) & (group.valid_readings == 2) & (group.duplicate_readings == 0) & (group.offgrid_readings == 0) & (group.dst_excluded == 0)
    group['eligible'] = good.astype(int)
    group.loc[~good, 'energy_kwh'] = np.nan
    group.insert(0, 'timestamp_benchmark', group.index.strftime('%Y-%m-%dT%H:%M:%S'))
    group.insert(1, 'timestamp_utc', group.timestamp_benchmark + 'Z')
    group = group.reset_index(drop=True)
    counts = {'source_rows_in_prepared_window': len(frame), 'null_nonfinite_rows': int((~np.isfinite(y)).sum()), 'negative_rows': int((y < 0).sum()), 'zero_rows': int((y == 0).sum()), 'duplicate_rows': int(dup.sum()), 'offgrid_rows': int(offgrid.sum()), 'tariff_values': sorted(frame.stdorToU.unique().tolist()), 'eligible_hours': int(good.sum())}
    return group, counts

def self_test():
    base = pd.DataFrame({'DateTime': ['2013-01-01 00:00:00', '2013-01-01 00:30:00'], ENERGY: ['0', '0.5'], 'stdorToU': ['Std', 'Std']})
    h, _ = hourly_reference(base, '2013-01-01', '2013-01-02')
    assert h.iloc[0].eligible == 1 and h.iloc[0].energy_kwh == .5
    h, _ = hourly_reference(pd.concat([base, base.iloc[[0]]]), '2013-01-01', '2013-01-02')
    assert h.iloc[0].eligible == 0 and h.iloc[0].duplicate_readings == 2
    for value in ['Null', 'nan', '-1']:
        f = base.copy(); f.loc[0, ENERGY] = value
        h, _ = hourly_reference(f, '2013-01-01', '2013-01-02')
        assert h.iloc[0].eligible == 0 and h.iloc[0].invalid_readings == 1
    f = base.copy(); f.loc[0, 'DateTime'] = '2013-01-01 00:01:00'
    h, _ = hourly_reference(f, '2013-01-01', '2013-01-02')
    assert h.iloc[0].eligible == 0 and h.iloc[0].offgrid_readings == 1
    f = base.copy(); f.DateTime = f.DateTime.str.replace('2013-01-01', '2013-03-31')
    h, _ = hourly_reference(f, '2013-03-31', '2013-04-01')
    assert h.iloc[0].eligible == 0 and h.iloc[0].dst_excluded == 1
    return {'status': 'passed', 'fixtures': 7}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', type=Path, default=HERE / 'lcl_raw' / 'CC_LCL-FullData.csv')
    ap.add_argument('--archive', type=Path, default=HERE / 'LCL-FullData.zip')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    tests = self_test()
    if args.self_test: print(json.dumps(tests)); return
    OUT.mkdir(parents=True, exist_ok=True)
    tick = time.perf_counter(); ids = set(); kept = []; rows = 0
    input_code_hash = sha(__file__)
    protocol_hashes = {p.name: sha(p) for p in [HERE / 'lcl_protocol.txt', HERE / 'lcl_clock_amendment.txt']}
    # Dynamic top100 is valid even if source rows are not household-sorted.
    # Every row belonging to an eventual top100 ID is retained when seen.
    for n, chunk in enumerate(pd.read_csv(args.csv, dtype=str, keep_default_na=False, chunksize=500_000)):
        assert chunk.columns.tolist() == ['LCLid', 'stdorToU', 'DateTime', ENERGY]
        rows += len(chunk)
        ids.update(chunk.LCLid.unique().tolist())
        candidates = sorted(ids)[:100]
        q = chunk[chunk.LCLid.isin(candidates) & (chunk.DateTime >= START) & (chunk.DateTime < END)]
        if len(q): kept.append(q.copy())
        if n % 20 == 0:
            print(json.dumps({'rows_scanned': rows, 'distinct_ids': len(ids), 'kept_rows_so_far': sum(map(len, kept)), 'seconds': time.perf_counter() - tick}), flush=True)
    candidates = sorted(ids)[:100]
    raw = pd.concat(kept, ignore_index=True)
    raw = raw[raw.LCLid.isin(candidates)].copy()
    del kept
    # Source quality for every prescribed candidate. Selection uses only training counts.
    hourly, inventory, days = {}, [], []
    for hh in candidates:
        frame = raw[raw.LCLid == hh].copy()
        hours, counts = hourly_reference(frame)
        hours.insert(0, 'household_id', hh)
        date = hours.timestamp_benchmark.str[:10]
        daily = hours.assign(date_benchmark=date).groupby('date_benchmark', as_index=False).agg(eligible_hours=('eligible', 'sum'), source_readings=('source_readings', 'sum'), invalid_readings=('invalid_readings', 'sum'), duplicate_readings=('duplicate_readings', 'sum'), offgrid_readings=('offgrid_readings', 'sum'), dst_excluded_hours=('dst_excluded', 'sum'))
        daily.insert(0, 'household_id', hh)
        daily['complete'] = (daily.eligible_hours == 24).astype(int)
        daily['split'] = np.select([daily.date_benchmark.between('2013-01-01', '2013-09-30'), daily.date_benchmark.between('2013-10-01', '2013-12-31'), daily.date_benchmark.between('2014-01-01', '2014-02-28')], ['training', 'validation', 'test'], default='outside_split')
        per_split = daily.groupby('split').complete.sum().to_dict()
        counts.update({'household_id': hh, 'complete_days_by_split': per_split, 'training_eligible': per_split.get('training', 0) >= 90})
        hourly[hh] = hours; inventory.append(counts); days.append(daily)
    selected = [r['household_id'] for r in inventory if r['training_eligible']][:20]
    for r in inventory:
        r['selected'] = r['household_id'] in selected
        r['exclusion_reason'] = None if r['selected'] else ('fewer_than_90_complete_training_days' if not r['training_eligible'] else 'beyond_predeclared_lowest_20_eligible_ids')
    pd.concat([hourly[hh] for hh in selected], ignore_index=True).to_csv(OUT / 'hourly.csv', index=False, float_format='%.17g')
    pd.concat(days, ignore_index=True).to_csv(OUT / 'daily_quality.csv', index=False)
    (OUT / 'household_inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    # Original row labels and literal values for all selected-household source-window rows.
    raw[raw.LCLid.isin(selected)].to_csv(OUT / 'selected_halfhour_source.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    (OUT / 'selection.json').write_text(json.dumps({'rule': 'First20 training-eligible IDs among lowest100 observed source IDs; no validation/test selection.', 'candidate_ids': candidates, 'selected_ids': selected, 'minimum_complete_training_days': 90, 'selected_before_model_fitting': True, 'protocol_hashes': protocol_hashes}, indent=2), encoding='utf-8')
    outputs = {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(OUT.iterdir()) if p.is_file() and p.name != 'manifest.json'}
    manifest = {'status': 'passed', 'created_utc': datetime.now(timezone.utc).isoformat(), 'source': 'UK Power Networks Low Carbon London, official London Datastore full archive', 'license': 'CC BY4.0', 'archive': {'name': args.archive.name, 'bytes': args.archive.stat().st_size, 'sha256': sha(args.archive)}, 'member': {'name': args.csv.name, 'bytes': args.csv.stat().st_size, 'sha256': sha(args.csv)}, 'parser_sha256': input_code_hash, 'protocol_hashes': protocol_hashes, 'source_rows_scanned': rows, 'source_distinct_households': len(ids), 'candidate_count': len(candidates), 'selected_ids': selected, 'clock': 'Providerlabels treated as assigned benchmark clock. timestamp_utc is timestamp_benchmark suffixed Z for software coordinates; physical UTC and interval-start orientation are not verified.', 'reference': 'Sum of the two source kWh readings labeled :00 and :30, with no missing-value imputation.', 'source_quality_flags': 'The original CSV has only ID, tariff, DateTime and kWh; there is no actual/estimated flag. Our validity rule cannot establish absence of every source-level estimate.', 'tests': tests, 'processing_seconds': time.perf_counter() - tick, 'outputs': outputs}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'passed', 'selected_ids': selected, 'seconds': time.perf_counter() - tick}), flush=True)

if __name__ == '__main__': main()
