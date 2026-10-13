"""Separate scalar/Decimal check of selected LCL source rows and hourly outputs.

This checker does not import the source preparation implementation. It is a
same-study implementation check, not independent acquisition of the original data.
"""
import csv, gzip, hashlib, json, math
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / 'data' / 'lcl'

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        while b := f.read(8 * 1024 * 1024): h.update(b)
    return h.hexdigest()

def main():
    manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['status'] == 'passed'
    for name, record in manifest['outputs'].items():
        assert sha(DATA / name) == record['sha256'], name
    selection = json.loads((DATA / 'selection.json').read_text(encoding='utf-8'))
    inventory = json.loads((DATA / 'household_inventory.json').read_text(encoding='utf-8'))
    candidate_ids = [r['household_id'] for r in inventory]
    assert candidate_ids == sorted(candidate_ids) and len(candidate_ids) == 100
    assert selection['candidate_ids'] == candidate_ids
    train_days, complete_days, day_hour_counts = Counter(), Counter(), Counter()
    with (DATA / 'daily_quality.csv').open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            assert int(row['complete']) == int(int(row['eligible_hours']) == 24)
            if row['split'] == 'training' and int(row['complete']):
                train_days[row['household_id']] += 1
            if int(row['complete']): complete_days[(row['household_id'], row['split'])] += 1
    expected_selected = [hh for hh in candidate_ids if train_days[hh] >= 90][:20]
    assert selection['selected_ids'] == manifest['selected_ids'] == expected_selected
    for record in inventory:
        for split, count in record['complete_days_by_split'].items():
            assert complete_days[(record['household_id'], split)] == count

    records = defaultdict(list)
    rows = 0
    with gzip.open(DATA / 'selected_halfhour_source.csv.gz', 'rt', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            hh = row['LCLid']; assert hh in expected_selected
            original = row['DateTime']
            t = datetime.fromisoformat(original)
            # Source has fractional seconds; check the original suffix as well.
            fraction = original.split('.', 1)[1] if '.' in original else ''
            offgrid = t.minute not in [0, 30] or t.second != 0 or any(c != '0' for c in fraction)
            try:
                value = Decimal(row['KWH/hh (per half hour) '].strip())
                good = value.is_finite() and value >= 0
            except InvalidOperation:
                value, good = Decimal(0), False
            hour = t.strftime('%Y-%m-%dT%H:00:00')
            records[(hh, hour)].append((t.isoformat(), value, good, offgrid))
            rows += 1
    checked, eligible, max_error = 0, 0, 0.
    with (DATA / 'hourly.csv').open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            hh, hour = row['household_id'], row['timestamp_benchmark']
            assert row['timestamp_utc'] == hour + 'Z'
            source = records.get((hh, hour), [])
            stamps = [r[0] for r in source]
            dup = len(stamps) != len(set(stamps))
            dst = hour[:10] in ['2013-03-31', '2013-10-27']
            good = len(source) == 2 and not dup and not dst and all(r[2] and not r[3] for r in source)
            assert int(row['eligible']) == int(good), (hh, hour, 'eligibility')
            assert int(row['source_readings']) == len(source)
            assert int(row['invalid_readings']) == sum(not r[2] for r in source)
            assert int(row['offgrid_readings']) == sum(r[3] for r in source)
            assert int(row['dst_excluded']) == int(dst)
            if good:
                expected = float(sum((r[1] for r in source), Decimal(0)))
                actual = float(row['energy_kwh'])
                err = abs(expected - actual); max_error = max(max_error, err)
                assert err <= 2e-14 * max(1., abs(expected)), (hh, hour, expected, actual)
                day_hour_counts[(hh, hour[:10])] += 1
                eligible += 1
            else:
                assert row['energy_kwh'] == ''
            checked += 1
    with (DATA / 'daily_quality.csv').open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['household_id'] in expected_selected:
                assert int(row['eligible_hours']) == day_hour_counts[(row['household_id'], row['date_benchmark'])]
    out = {'status': 'passed', 'checker_sha256': sha(Path(__file__)), 'input_manifest_sha256': sha(DATA / 'manifest.json'), 'selected_source_rows_checked': rows, 'hourly_rows_checked': checked, 'eligible_hours_checked': eligible, 'max_absolute_decimal_sum_difference_kwh': max_error, 'selection': 'Reconstructed from all100candidate daily training-only quality counts.', 'scope': 'Scalar reference checking against bundled literal selected source rows, source output integrity, day counts and selection logic. Does not independently re-extract source rows from the8.54GB original or verify physical timezones/arrival metadata.', 'selected_ids': expected_selected}
    (HERE / 'lcl_reference_verification.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps(out))

if __name__ == '__main__': main()
