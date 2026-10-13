"""Export unchanged training responses with explicit grid/native-time distinction."""
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
path = ROOT/'hourly'/'training_hourly_counters.csv'
with path.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=['system_id', 'timestamp_utc', 'requested_timestamp_utc',
        'returned_timestamp_utc', 'source_timestamp_utc', 'counter_kwh', 'valid', 'unit',
        'timestamp_semantics', 'raw_response_file', 'raw_row_index'])
    writer.writeheader()
    for ident in (1, 2, 7):
        source = ROOT/'hourly'/f'system_{ident}_train_2025H1.json'
        rows = json.loads(source.read_text(encoding='utf-8'))['heatpump_elec_kwh']
        for index, (stamp, value) in enumerate(rows):
            utc = dt.datetime.fromtimestamp(stamp, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            requested = dt.datetime.fromtimestamp(1735689600+3600*index, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            valid = isinstance(value, (int,float)) and math.isfinite(value)
            writer.writerow({'system_id': ident, 'timestamp_utc': utc,
                'requested_timestamp_utc': requested, 'returned_timestamp_utc': utc,
                'source_timestamp_utc': '', 'counter_kwh': value if valid else '',
                'valid': int(valid), 'unit': 'kWh',
                'timestamp_semantics': 'returned API grid; native sample time unverified',
                'raw_response_file': source.name, 'raw_row_index': index})
print(json.dumps({'path': str(path), 'rows': 3*4345, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
