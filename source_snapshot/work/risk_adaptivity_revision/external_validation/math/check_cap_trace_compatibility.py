"""Post-geometry check of illustrative caps against recorded traces.

All 290 fixed cases remain in the cap sensitivity. This diagnostic does not
select cases or assert that a cap is physically valid. Raw increments are
read for this check only, not supplied to the acquisition optimization.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPECTED_RAW = {
    'consumer_00000001': '9228795c6369ce144fbb929f9d413397545f86e3a95d2f9a0f27c92f1d55ad8d',
    'consumer_00000002': '93d142217c74ab2c12a98035b3ea178ead234fec0b71942e8e90db5b7e6a2ef3',
    'consumer_00000003': 'db69719d2262ebeb6df39abafffca2805c8a03b1b4777f86eb8aa78acf578b6c',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'work')
    args = parser.parse_args()
    started = time.perf_counter()
    manifest = json.loads((HERE / 'cap_sensitivity_manifest.json').read_text())
    # Establish that the geometry and all cap decisions predate this raw check.
    assert json.loads((HERE / 'cap_sensitivity_report.json').read_text())['status'] == 'PASS'
    rows = []
    raw = {}
    for meter, expected in EXPECTED_RAW.items():
        path = args.data_dir / f"data_blem_{meter.replace('_', '-')}.csv"
        assert digest(path) == expected
        with path.open(newline='', encoding='utf-8-sig') as stream:
            raw[meter] = {int(row['time']): int(row['energy']) for row in csv.DictReader(stream)}
    for case_id in manifest['case_ids']:
        meter, day, hour, model_a, model_b = case_id.split('/')
        t0 = datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(hours=int(hour))
        readings = [raw[meter][int((t0 + timedelta(hours=h)).timestamp()) * 1000] for h in range(7)]
        increments = [b - a for a, b in zip(readings, readings[1:])]
        total = sum(increments)
        assert total > 0 and min(increments) >= 0
        for cap in [F(1, 2), F(1, 3)]:
            violations = [v > cap * total for v in increments]
            rows.append({'id': case_id, 'meter': meter, 'block': '/'.join([meter, day, hour]),
                         'cap': str(cap), 'trace_violates_cap': any(violations),
                         'violating_coordinates': sum(violations)})
    summaries = []
    for cap in ['1/2', '1/3']:
        subset = [row for row in rows if row['cap'] == cap]
        blocks = {row['block']: row['trace_violates_cap'] for row in subset}
        summaries.append({'cap': cap, 'cases': len(subset),
                          'violating_cases': sum(row['trace_violates_cap'] for row in subset),
                          'unique_blocks': len(blocks), 'violating_unique_blocks': sum(blocks.values()),
                          'by_meter': {meter: {
                              'cases': sum(row['meter'] == meter for row in subset),
                              'violating_cases': sum(row['trace_violates_cap'] for row in subset if row['meter'] == meter),
                              'unique_blocks': len({row['block'] for row in subset if row['meter'] == meter}),
                              'violating_unique_blocks': len({row['block'] for row in subset if row['meter'] == meter and row['trace_violates_cap']})
                          } for meter in EXPECTED_RAW}})
    with (HERE / 'cap_trace_compatibility_cases.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    output = {'status': 'PASS', 'scope': 'Post-geometry recorded-trace compatibility; no cap validation and no case exclusions',
              'cases_retained': 290, 'comparisons': 'Exact integer-register increments against rational fraction of observed block total',
              'summaries': summaries, 'source_sha256': digest(__file__),
              'raw_sha256': EXPECTED_RAW,
              'frozen_cap_report_sha256': digest(HERE / 'cap_sensitivity_report.json'),
              'protocol_sha256': manifest['protocol_sha256'], 'seconds': time.perf_counter() - started}
    (HERE / 'cap_trace_compatibility.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2), flush=True)


if __name__ == '__main__':
    main()
