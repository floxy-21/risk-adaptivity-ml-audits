"""Cache only the frozen training calendar, then report availability (no fitting)."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'hourly'
CACHE.mkdir(exist_ok=True)
START = 1735689600  # 2025-01-01T00:00:00Z
END = 1751328000  # 2025-07-01T00:00:00Z, training endpoint
ledger = []
for system in json.loads((ROOT/'selected_systems.json').read_text(encoding='utf-8')):
    ident = system['id']
    params = {'id': ident, 'feeds': 'heatpump_elec_kwh', 'start': START, 'end': END,
              'interval': 3600, 'average': 0, 'delta': 0, 'timeformat': 'unix'}
    url = 'https://heatpumpmonitor.org/timeseries/data?' + urllib.parse.urlencode(params)
    path = CACHE / f'system_{ident}_train_2025H1.json'
    if not path.exists():
        time.sleep(2)
        started = dt.datetime.now(dt.timezone.utc).isoformat()
        tick = time.perf_counter()
        req = urllib.request.Request(url, headers={'User-Agent': 'Academic reproducibility check; Python urllib'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            status, headers = resp.status, dict(resp.headers)
        elapsed = time.perf_counter() - tick
        json.loads(raw)  # require a readable body before caching
        path.write_bytes(raw)
        with (ROOT/'request_log.jsonl').open('a', encoding='utf-8') as out:
            out.write(json.dumps({'url': url, 'path': str(path.relative_to(ROOT)), 'started_utc': started,
                'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'status': status,
                'elapsed_seconds': elapsed, 'response_headers': headers, 'purpose': 'training_only_availability'})+'\n')
    data = json.loads(path.read_text(encoding='utf-8'))
    if 'heatpump_elec_kwh' not in data:
        raise ValueError(f'Unexpected response for {ident}: {str(data)[:250]}')
    records = data['heatpump_elec_kwh']
    mapped = {int(t): value for t, value in records}
    expected = list(range(START, END + 1, 3600))
    def good(v):
        return isinstance(v, (int, float)) and math.isfinite(v)
    valid = []
    negative = 0
    for t in expected[:-1]:
        left, right = mapped.get(t), mapped.get(t+3600)
        if good(left) and good(right) and right < left:
            negative += 1
        valid.append(good(left) and good(right) and right >= left)
    complete_days = sum(all(valid[d:d+24]) for d in range(0, len(valid), 24))
    row = {'id': ident, 'response_rows': len(records), 'expected_endpoint_count': len(expected),
           'timestamps_match_expected_exactly': [int(t) for t, _ in records] == expected,
           'valid_hourly_intervals': sum(valid), 'total_training_intervals': len(valid),
           'valid_fraction': sum(valid)/len(valid), 'complete_days': complete_days,
           'negative_differences': negative, 'training_eligible': sum(valid)/len(valid) >= .95 and complete_days >= 90,
           'criteria': 'Frozen operational protocol: >=95% valid hourly intervals and >=90 complete days. No interpolation, clipping, or replacement.',
           'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    ledger.append(row)
outpath = ROOT/'training_availability.json'
if not outpath.exists():
    outpath.write_text(json.dumps(ledger, indent=2)+'\n', encoding='utf-8')
print(json.dumps(ledger, indent=2))
