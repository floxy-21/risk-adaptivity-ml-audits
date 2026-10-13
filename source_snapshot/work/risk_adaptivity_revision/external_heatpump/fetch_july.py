"""Cache authorized frozen July source records; no fitting or outcome selection."""
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
START, END = 1751328000, 1754006400
CACHE = ROOT / 'hourly'
LOCK = ROOT.parent / 'external_validation' / 'operational' / 'protocol_lock.json'
lock = json.loads(LOCK.read_text(encoding='utf-8'))
assert lock['systems'] == [1, 2, 7]
assert lock['test_start'] == '2025-07-01T00:00:00Z'
assert lock['test_end_exclusive'] == '2025-08-01T00:00:00Z'
sources = []
for ident in (1, 2, 7):
    params = {'id': ident, 'feeds': 'heatpump_elec_kwh', 'start': START, 'end': END,
              'interval': 3600, 'average': 0, 'delta': 0, 'timeformat': 'unix'}
    url = 'https://heatpumpmonitor.org/timeseries/data?' + urllib.parse.urlencode(params)
    path = CACHE / f'system_{ident}_test_2025July.json'
    if not path.exists():
        time.sleep(2)
        started = dt.datetime.now(dt.timezone.utc).isoformat()
        tick = time.perf_counter()
        request = urllib.request.Request(url, headers={'User-Agent': 'Academic reproducibility check; Python urllib'})
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read()
            status, headers = response.status, dict(response.headers)
        elapsed = time.perf_counter() - tick
        json.loads(raw)
        path.write_bytes(raw)
        with (ROOT/'request_log.jsonl').open('a', encoding='utf-8') as out:
            out.write(json.dumps({'url': url, 'path': str(path.relative_to(ROOT)), 'started_utc': started,
                'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'status': status,
                'elapsed_seconds': elapsed, 'response_headers': headers,
                'purpose': 'authorized_frozen_July_replay_source_cache; no outcome selection'})+'\n')
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data['heatpump_elec_kwh']
    assert [int(t) for t, _ in rows] == list(range(START, END+1, 3600))
    sources.append({'system_id': ident, 'raw_path': str(path.relative_to(ROOT)), 'rows': len(rows),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

output = CACHE / 'train_test_hourly_counters.csv'
fields = ['system_id', 'timestamp_utc', 'requested_timestamp_utc', 'returned_timestamp_utc',
          'source_timestamp_utc', 'counter_kwh', 'valid', 'unit', 'timestamp_semantics',
          'raw_response_file', 'raw_row_index']
count = 0
boundary_agreements = []
with output.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for ident in (1, 2, 7):
        train_file = CACHE / f'system_{ident}_train_2025H1.json'
        test_file = CACHE / f'system_{ident}_test_2025July.json'
        train = json.loads(train_file.read_text(encoding='utf-8'))['heatpump_elec_kwh']
        test = json.loads(test_file.read_text(encoding='utf-8'))['heatpump_elec_kwh']
        # Preserve frozen training at the shared boundary; flag any provider revision.
        boundary_agreements.append({'system_id': ident, 'shared_boundary_identical': train[-1] == test[0]})
        assert train[-1] == test[0], 'Provider changed shared boundary: retain both raw files and review before export'
        for source, records, skipfirst in ((train_file, train, False), (test_file, test, True)):
            for index, (stamp, value) in enumerate(records):
                if skipfirst and index == 0:
                    continue
                utc = dt.datetime.fromtimestamp(stamp, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                valid = isinstance(value, (int, float)) and math.isfinite(value)
                writer.writerow({'system_id': ident, 'timestamp_utc': utc, 'requested_timestamp_utc': utc,
                    'returned_timestamp_utc': utc, 'source_timestamp_utc': '',
                    'counter_kwh': value if valid else '', 'valid': int(valid), 'unit': 'kWh',
                    'timestamp_semantics': 'returned API grid; native sample time unverified',
                    'raw_response_file': source.name, 'raw_row_index': index})
                count += 1
report = {'scope': 'Source caching only; no fitted models or policy outcomes inspected',
          'protocol_lock_sha256': hashlib.sha256(LOCK.read_bytes()).hexdigest(),
          'sources': sources, 'shared_boundary': boundary_agreements, 'path': str(output), 'rows': count,
          'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
(ROOT/'july_cache_manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print(json.dumps(report, indent=2))
