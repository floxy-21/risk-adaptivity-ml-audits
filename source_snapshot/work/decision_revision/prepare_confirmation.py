"""Prepare a previously unfitted LCL cohort using only frozen training eligibility.

No forecast fitting, loss evaluation or acquisition is performed here. Historical
source quality counts for the lowest 100 IDs were already available; this is not
a claim that their source records had never been parsed.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import time
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'work/external_deadline'
HERE = Path(__file__).resolve().parent


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    started = time.perf_counter()
    out = HERE / 'confirmation_source'
    out.mkdir(exist_ok=False)
    inventory_path = OLD / 'data/lcl/household_inventory.json'
    old_selection_path = OLD / 'data/lcl/selection.json'
    inventory = json.loads(inventory_path.read_text())
    excluded = set(json.loads(old_selection_path.read_text())['selected_ids'])
    selected = [r['household_id'] for r in inventory
                if r['complete_days_by_split'].get('training', 0) >= 90
                and r['household_id'] not in excluded][:20]
    assert len(selected) == 20 and selected == sorted(selected)
    parser_path = OLD / 'source/prepare_lcl.py'
    raw_path = OLD / 'source/lcl_raw/CC_LCL-FullData.csv'
    expected_raw = json.loads((OLD / 'data/lcl/manifest.json').read_text())['member']['sha256']
    frozen = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'rule': 'Next 20 training-eligible IDs after excluding the original 20, among the same lowest 100 source IDs; >=90 complete training days, no outcome filtering.',
              'selected_ids': selected, 'excluded_previously_fitted_ids': sorted(excluded),
              'inputs': {p.relative_to(ROOT).as_posix(): sha(p)
                         for p in (inventory_path, old_selection_path, parser_path, Path(__file__))},
              'expected_raw_sha256': expected_raw,
              'scope': 'Training-only cohort preparation. Original quality counts were known. These consumers have not been fitted or evaluated in this project.'}
    (out / 'selection_before_extract.json').write_text(json.dumps(frozen, indent=2)+'\n')
    assert sha(raw_path) == expected_raw, 'Raw source differs from verified archive'
    spec = importlib.util.spec_from_file_location('frozen_lcl_source_parser', parser_path)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    chunks, rows = [], 0
    for n, frame in enumerate(pd.read_csv(raw_path, dtype=str, keep_default_na=False, chunksize=500000)):
        rows += len(frame)
        keep = frame[frame.LCLid.isin(selected) & (frame.DateTime >= parser.START)
                     & (frame.DateTime < parser.END)]
        if len(keep):
            chunks.append(keep.copy())
        if n % 40 == 0:
            print(json.dumps({'source_rows': rows, 'seconds': time.perf_counter()-started}), flush=True)
    literal = pd.concat(chunks, ignore_index=True)
    literal.to_csv(out / 'selected_halfhour_source.csv.gz', index=False,
                   compression={'method': 'gzip', 'mtime': 0})
    hourly, counts = [], []
    for hh in selected:
        values, count = parser.hourly_reference(literal[literal.LCLid == hh].copy())
        values.insert(0, 'household_id', hh)
        hourly.append(values)
        counts.append({'household_id': hh, **count})
    pd.concat(hourly, ignore_index=True).to_csv(out / 'hourly.csv', index=False, float_format='%.17g')
    (out / 'quality_counts.json').write_text(json.dumps(counts, indent=2)+'\n')
    config = json.loads((OLD / 'fitted/frozen_config.json').read_text())
    config['household_ids'] = selected
    config['protocol_path'] = 'work/decision_revision/confirmation_protocol.json'
    (out / 'forecast_config.json').write_text(json.dumps(config, indent=2)+'\n')
    report = {'status': 'passed', 'selected_ids': selected, 'source_rows_scanned': rows,
              'source_literal_rows': len(literal), 'processing_seconds': time.perf_counter()-started,
              'raw_sha256': expected_raw, 'source_parser_sha256': sha(parser_path),
              'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()},
              'source_only_no_forecast_or_acquisition_evaluation': True}
    (out / 'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
