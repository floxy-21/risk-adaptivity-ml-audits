"""Derive distributable contrasts and dimensionless cap ledger from raw-route outputs."""
import csv
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
manifest = json.loads((HERE / 'cap_sensitivity_manifest.json').read_text())
selected = set(manifest['case_ids'])
cases = []
for relative, expected in manifest['input_sha256'].items():
    path = ROOT / relative
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    if relative.endswith('geometry.json'):
        cases.extend(row for row in json.loads(path.read_text())['cases'] if row['id'] in selected)
cases.sort(key=lambda row: row['id'])
assert len(cases) == 290 and {row['id'] for row in cases} == selected
exported = []
for row in cases:
    coefficients = [F.from_float(float(v)) for v in row['c']]
    exported.append({'id': row['id'], 'meter': row['meter'],
                     'pair': row['model_a'] + '/' + row['model_b'],
                     'c_exact': list(map(str, coefficients)),
                     'range_exact': str(max(coefficients) - min(coefficients))})
output = {'scope': 'Derived frozen forecast-contrast coefficients only; no raw register values or totals. Relative caps and widths cancel every positive E.',
          'source_protocol_sha256': manifest['protocol_sha256'], 'cases': exported}
(HERE / 'cap_sensitivity_coefficients.json').write_text(json.dumps(output, indent=2) + '\n')
with (HERE / 'cap_sensitivity_cases.csv').open(newline='', encoding='utf-8') as stream:
    ledger = list(csv.DictReader(stream))
fields = [name for name in ledger[0] if name not in {'E', 'old_W0', 'new_W0'}]
with (HERE / 'cap_sensitivity_bundled_cases.csv').open('w', newline='', encoding='utf-8') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(ledger)
print('PASS: 290 forecast contrasts and 1,740 dimensionless rows exported; raw totals omitted.')
