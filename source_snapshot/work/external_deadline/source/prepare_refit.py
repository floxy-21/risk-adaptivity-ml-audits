"""Source-only REFIT raw whole-house inventory. No forecasts or outcomes are read.

Usage: python prepare_refit.py --raw-dir DIRECTORY [--archive ARCHIVE]
Reads raw House*.csv under DIRECTORY and emits the frozen reference and inventory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'data'
START = int(pd.Timestamp('2014-06-23', tz='UTC').timestamp())
END = int(pd.Timestamp('2015-04-03', tz='UTC').timestamp())
EXPECTED_HOUSES = list(range(1, 14)) + list(range(15, 22))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def integrate(t, p, start=START, end=END):
    """Strict zero-order hold using integer seconds; quarantines duplicate/backward events."""
    assert t.ndim == p.ndim == 1 and len(t) == len(p)
    assert np.all(np.isfinite(t)) and np.all(t == np.floor(t))
    t = t.astype(np.int64)
    back = np.flatnonzero(np.diff(t) < 0)
    bad_times = np.unique(np.concatenate([t[back], t[back + 1]]))
    sorted_input = len(back) == 0
    if not sorted_input:
        order = np.argsort(t, kind='stable')
        t, p = t[order], p[order]
    duplicated = np.zeros(len(t), dtype=bool)
    duplicate_pairs = np.flatnonzero(np.diff(t) == 0)
    duplicated[duplicate_pairs] = True
    duplicated[duplicate_pairs + 1] = True
    quarantined = duplicated | np.isin(t, bad_times)
    dt = np.diff(t)
    good_power = np.isfinite(p[:-1]) & (p[:-1] >= 0)
    quarantine_interval = quarantined[:-1] | quarantined[1:]
    good = (dt > 0) & (dt <= 16) & good_power & ~quarantine_interval
    num_hours = (end - start) // 3600
    energy_ws = np.zeros(num_hours, dtype=np.float64)
    coverage = np.zeros(num_hours, dtype=np.int64)
    reasons = {k: np.zeros(num_hours, dtype=np.int64) for k in ['long_gap_seconds', 'invalid_power_seconds', 'quarantined_seconds']}
    largest_gap = np.zeros(num_hours, dtype=np.int64)

    # Good intervals cannot cross more than one hourly boundary.
    use = good & (t[:-1] < end) & (t[1:] > start)
    left = np.maximum(t[:-1][use], start)
    right = np.minimum(t[1:][use], end)
    values = p[:-1][use]
    hour = (left - start) // 3600
    mid = np.minimum(right, start + (hour + 1) * 3600)
    duration = mid - left
    np.add.at(coverage, hour, duration)
    np.add.at(energy_ws, hour, values * duration)
    cross = right > mid
    np.add.at(coverage, hour[cross] + 1, right[cross] - mid[cross])
    np.add.at(energy_ws, hour[cross] + 1, values[cross] * (right[cross] - mid[cross]))

    # Invalid intervals are sparse; record every affected hour, including full gap spans.
    bad = np.flatnonzero((~good) & (dt > 0) & (t[:-1] < end) & (t[1:] > start))
    for i in bad:
        left, right = max(t[i], start), min(t[i + 1], end)
        first, last = (left - start) // 3600, (right - 1 - start) // 3600
        for h in range(int(first), int(last) + 1):
            seconds = min(right, start + (h + 1) * 3600) - max(left, start + h * 3600)
            if dt[i] > 16:
                reasons['long_gap_seconds'][h] += seconds
                largest_gap[h] = max(largest_gap[h], dt[i])
            if not good_power[i]:
                reasons['invalid_power_seconds'][h] += seconds
            if quarantine_interval[i]:
                reasons['quarantined_seconds'][h] += seconds
    assert np.all((coverage >= 0) & (coverage <= 3600))
    eligible = coverage == 3600
    hourly = pd.DataFrame({
        'timestamp_utc': pd.to_datetime(np.arange(start, end, 3600), unit='s', utc=True).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'energy_kwh': np.where(eligible, energy_ws / 3_600_000.0, np.nan),
        'eligible': eligible.astype(int),
        'coverage_seconds': coverage,
        'largest_gap_seconds': largest_gap,
        **reasons,
    })
    stats = {
        'source_rows': len(t), 'first_unix': int(t[0]), 'last_unix': int(t[-1]),
        'backward_events': len(back), 'stable_sort_needed': not sorted_input,
        'duplicate_pairs': len(duplicate_pairs), 'duplicate_rows': int(duplicated.sum()),
        'quarantined_timestamps': int(quarantined.sum()),
        'nonfinite_aggregate_rows': int((~np.isfinite(p)).sum()),
        'negative_aggregate_rows': int((p < 0).sum()),
        'zero_aggregate_rows': int((p == 0).sum()),
        'source_interval_max_seconds': int(dt.max()),
        'source_interval_longer_than_16_seconds': int((dt > 16).sum()),
        'eligible_hours': int(eligible.sum()),
        'ineligible_hours': int((~eligible).sum()),
        'solar_generation_affected_documented': False,
    }
    return hourly, stats

def test_integration():
    t = np.arange(0, 7201, 8)
    p = np.full(len(t), 1000.)
    h, _ = integrate(t, p, 0, 7200)
    assert h.eligible.tolist() == [1, 1]
    assert h.energy_kwh.tolist() == [1., 1.]
    # Boundary-splitting integration must be exact for constant power.
    h, _ = integrate(t + 3, p, 8, 7208)
    assert h.iloc[0].coverage_seconds == 3600 and h.iloc[0].energy_kwh == 1
    q = np.delete(t, [100, 101])
    h, _ = integrate(q, np.full(len(q), 1000.), 0, 7200)
    assert h.eligible.tolist() == [0, 1] and h.iloc[0].long_gap_seconds == 24
    q = np.insert(t, 100, t[100])
    h, s = integrate(q, np.full(len(q), 1000.), 0, 7200)
    assert h.eligible.tolist() == [0, 1] and s['duplicate_rows'] == 2
    z = p.copy(); z[100] = np.nan
    h, _ = integrate(t, z, 0, 7200)
    assert h.eligible.tolist() == [0, 1] and h.iloc[0].invalid_power_seconds == 8
    q = t.copy(); q[100], q[101] = q[101], q[100]
    h, s = integrate(q, p, 0, 7200)
    assert h.eligible.tolist() == [0, 1] and s['backward_events'] == 1
    return {'status': 'passed', 'fixtures': 6}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw-dir', type=Path)
    ap.add_argument('--archive', type=Path)
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    tests = test_integration()
    if args.self_test:
        print(json.dumps(tests)); return
    if args.raw_dir is None:
        ap.error('--raw-dir is required for source processing')
    start_run = time.perf_counter()
    candidates = {}
    excluded_members = []
    for p in args.raw_dir.rglob('*.csv'):
        m = re.search(r'(?:RAW_)?House_?(\d+)_Part([12])\.csv$', p.name, re.I)
        if m:
            hh = int(m.group(1))
            if m.group(2) == '1':
                excluded_members.append({'household_id': hh, 'member_name': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p), 'reason': 'Part1 encodes unavailable sensors as zero'})
                continue
            if hh in candidates: raise ValueError(f'Duplicate source member for house {hh}')
            if p.name.upper().startswith('CLEAN'): raise ValueError('Cleaned data are forbidden')
            candidates[hh] = p
    if sorted(candidates) != EXPECTED_HOUSES:
        raise ValueError(f'Expected all 20 source house IDs {EXPECTED_HOUSES}, found {sorted(candidates)}')
    OUT.mkdir(exist_ok=True)
    hourly_path = OUT / 'hourly.csv'
    daily_all, records, members = [], [], []
    first = True
    for hh, path in sorted(candidates.items()):
        tick = time.perf_counter()
        columns = pd.read_csv(path, nrows=0).columns.tolist()
        if 'Unix' not in columns or 'Aggregate' not in columns:
            raise ValueError(f'Unrecognized raw columns for {path.name}: {columns}')
        chunks = list(pd.read_csv(path, usecols=['Unix', 'Aggregate'], dtype={'Unix': np.float64, 'Aggregate': np.float64}, chunksize=1_000_000))
        frame = pd.concat(chunks, ignore_index=True)
        del chunks
        hours, stats = integrate(frame.Unix.to_numpy(), frame.Aggregate.to_numpy())
        del frame
        hours.insert(0, 'household_id', hh)
        hours.to_csv(hourly_path, mode='w' if first else 'a', index=False, header=first, float_format='%.17g')
        first = False
        hours['date_utc'] = hours.timestamp_utc.str.slice(0, 10)
        daily = hours.groupby('date_utc', as_index=False).agg(eligible_hours=('eligible', 'sum'), coverage_seconds=('coverage_seconds', 'sum'), long_gap_seconds=('long_gap_seconds', 'sum'), invalid_power_seconds=('invalid_power_seconds', 'sum'), quarantined_seconds=('quarantined_seconds', 'sum'))
        daily.insert(0, 'household_id', hh)
        daily['complete'] = (daily.eligible_hours == 24).astype(int)
        daily['split'] = np.select([daily.date_utc.between('2014-07-01', '2014-12-31'), daily.date_utc.between('2015-01-01', '2015-01-31'), daily.date_utc.between('2015-02-01', '2015-03-31')], ['training', 'validation', 'test'], default='outside_split')
        counts = daily.groupby('split').complete.sum().to_dict()
        minima = {'training': 90, 'validation': 20, 'test': 20}
        reasons = [f'{k}_complete_days_below_{v}' for k, v in minima.items() if counts.get(k, 0) < v]
        stats.update({'household_id': hh, 'complete_days_by_split': counts, 'source_eligible': not reasons, 'exclusion_reasons': reasons, 'solar_generation_affected_documented': hh in [3, 11, 21]})
        daily_all.append(daily)
        records.append(stats)
        members.append({'household_id': hh, 'member_name': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path), 'columns': columns})
        print(json.dumps({'household_id': hh, 'seconds': time.perf_counter() - tick, 'complete_days': counts, 'eligible': not reasons}), flush=True)
    pd.concat(daily_all, ignore_index=True).to_csv(OUT / 'daily_quality.csv', index=False)
    (OUT / 'household_inventory.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    selected = [r['household_id'] for r in records if r['source_eligible']]
    manifest = {'status': 'passed', 'created_utc': datetime.now(timezone.utc).isoformat(), 'protocol_sha256': sha(HERE / 'source_protocol.txt'), 'protocol_amendment_sha256': sha(HERE / 'source_protocol_amendment.txt'), 'parser_sha256': sha(Path(__file__)), 'dataset_doi': '10.15129/31da3ece-f902-4e95-a093-e0a9536983c4', 'release': 'REFIT_RAW_081116', 'license': 'CC BY 4.0', 'archive': {'name': args.archive.name, 'bytes': args.archive.stat().st_size, 'sha256': sha(args.archive)} if args.archive else None, 'source_members': members, 'excluded_members': excluded_members, 'selected_households': selected, 'households_processed': len(records), 'reference': 'Zero-order hold integral of admissible raw-release aggregate power (including source event-change expansion), kWh; not exact physical energy.', 'interpolation': 'Our processing adds no gap filling and uses no cleaned values. The raw source already includes event-change expansion. Hold over raw intervals <=16 seconds is the explicit reference convention.', 'tests': tests, 'processing_seconds': time.perf_counter() - start_run, 'outputs': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in [hourly_path, OUT / 'daily_quality.csv', OUT / 'household_inventory.json']}}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'passed', 'selected_households': selected}), flush=True)

if __name__ == '__main__':
    main()
