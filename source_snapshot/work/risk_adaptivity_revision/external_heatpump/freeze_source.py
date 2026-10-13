"""Freeze an external public-source selection without fitting or test scoring.

Standard-library only. Run once; existing raw responses are reused, never replaced.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'metadata'
RAW.mkdir(exist_ok=True)
STAMP = dt.datetime.now(dt.timezone.utc).isoformat()
TRAIN_START = int(dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).timestamp())
TEST_START = int(dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc).timestamp())
TEST_END = int(dt.datetime(2025, 8, 1, tzinfo=dt.timezone.utc).timestamp())
last_request = 0.0

def write_once(path, obj):
    if not path.exists():
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

protocol = {
    'protocol_version': 'external-source-selection-v1',
    'frozen_utc': STAMP,
    'status_at_freeze': 'No hourly response requested and no forecast outcomes calculated for this source.',
    'purpose': 'External source and actual retrieval-interface validation; no promised effect size.',
    'source': 'HeatpumpMonitor.org / OpenEnergyMonitor community installations',
    'training_utc': ['2025-01-01T00:00:00Z', '2025-07-01T00:00:00Z'],
    'test_utc': ['2025-07-01T00:00:00Z', '2025-08-01T00:00:00Z'],
    'selection': [
        'Sort the public system list by numeric id ascending.',
        'Require MID metadata true and nonempty electrical-meter description explicitly identifying class 1.',
        'Require a heatpump_elec_kwh feed with metadata start <= 2025-01-01 and end >= 2025-08-01 UTC.',
        'Lock the first three qualifying IDs. Do not replace by observed performance or test completeness.',
        'Preserve all exclusions and metadata evidence. Metadata endpoint coverage does not assert no interior gaps.',
        'No further completeness exclusion is used for source selection. Downstream training/test availability handling must be declared separately before test scoring.'
    ],
    'retrieval': {
        'feed': 'heatpump_elec_kwh', 'units': 'stored cumulative kWh',
        'hourly_request': 'interval=3600, average=0, delta=0; timestamped values; UTC epoch parameters',
        'no_client_interpolation': True,
        'native_history_interpolation_status': 'unverified; public feed metadata does not expose processing chain',
        'native_meter_register_provenance': 'unverified; cumulative feed naming is insufficient proof',
        'bulk_baseline': 'One range request for the same seven hourly endpoints of a six-hour block is allowed and must be measured.',
        'tariff': 'No per-reading tariff established; hosting price per feed/year is not query billing.',
        'throttle': 'Sequential metadata/data GETs with at least 2 seconds between request starts; cache responses.'
    },
    'limitations': [
        'This is an external public data source, not independent execution or human specialist validation.',
        'MID class designation is not an unconditional deterministic relative-error bound or per-device calibration certificate.',
        'Stored-feed precision, physical accuracy, timestamp rounding and potential prior interpolation are distinct.',
        'A physical uncertainty study needs justified constraints and fresh analysis; exact-read guarantees cannot automatically be transferred.'
    ]
}
write_once(ROOT / 'source_selection_protocol.json', protocol)

def get_json(url, name):
    global last_request
    path = RAW / name
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    delay = max(0.0, 2.0 - (time.monotonic() - last_request))
    if delay:
        time.sleep(delay)
    last_request = time.monotonic()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    request = urllib.request.Request(url, headers={'User-Agent': 'Academic reproducibility metadata check; Python urllib'})
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read()
        headers = dict(response.headers)
        status = response.status
    parsed = json.loads(raw)
    path.write_bytes(raw)
    with (ROOT / 'request_log.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'url': url, 'path': str(path.relative_to(ROOT)), 'started_utc': started,
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'status': status,
            'response_headers': headers}) + '\n')
    return parsed

systems = get_json('https://heatpumpmonitor.org/system/list/public.json', 'public_systems.json')
if isinstance(systems, dict):
    systems = list(systems.values())
systems = sorted(systems, key=lambda x: int(x['id']))
ledger = []
selected = []
for system in systems:
    ident = int(system['id'])
    meter = str(system.get('electric_meter', ''))
    row = {'id': ident, 'mid_metering': system.get('mid_metering'), 'electric_meter': meter}
    if str(system.get('mid_metering', '')).lower() not in ('1', 'true'):
        row['decision'] = 'exclude_not_mid'
    elif 'class 1' not in meter.lower():
        row['decision'] = 'exclude_missing_explicit_class_1_description'
    else:
        feeds = get_json(f'https://heatpumpmonitor.org/timeseries/available?id={ident}', f'system_{ident}_feeds.json')
        feed = feeds.get('feeds', feeds).get('heatpump_elec_kwh')
        if feed is None:
            row['decision'] = 'exclude_missing_cumulative_feed'
        else:
            row['feed'] = feed
            if int(feed['start_time']) > TRAIN_START or int(feed['end_time']) < TEST_END:
                row['decision'] = 'exclude_metadata_does_not_cover_frozen_calendar'
            else:
                row['decision'] = 'selected'
                meta = get_json(f'https://heatpumpmonitor.org/system/get.json?id={ident}', f'system_{ident}_metadata.json')
                selected.append({'id': ident, 'location': system.get('location'), 'electric_meter': meter,
                    'heat_meter': system.get('heat_meter'), 'mid_metering': system.get('mid_metering'),
                    'feed_key': 'heatpump_elec_kwh', 'feed': feed,
                    'units': 'stored cumulative kWh', 'direct_register_provenance': 'not verified',
                    'historical_interpolation_status': 'not exposed in public feed metadata'})
    ledger.append(row)
    if len(selected) == 3:
        break
write_once(ROOT / 'selection_ledger.json', ledger)
write_once(ROOT / 'selected_systems.json', selected)
print(json.dumps({'selected': selected, 'considered': len(ledger), 'protocol_sha256': hashlib.sha256((ROOT/'source_selection_protocol.json').read_bytes()).hexdigest()}, indent=2))
