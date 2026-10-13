"""List bounded source-reproduction artifacts; exclude raw archives and tool binaries."""
import hashlib, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
names = [
    'source/source_protocol.txt', 'source/source_protocol_amendment.txt',
    'source/source_dates_amendment.txt', 'source/RAW_READ_ME_081116.txt',
    'source/download_refit.py', 'source/prepare_refit.py', 'source/README.txt',
    'source/download_manifest.json', 'source/archive_inventory.txt',
    'data/manifest.json', 'data/household_inventory.json', 'data/source_feasibility.json',
    'data/daily_quality.csv', 'data/hourly.csv',
    'source/lcl_protocol.txt', 'source/lcl_clock_amendment.txt',
    'source/download_lcl.py', 'source/prepare_lcl.py', 'source/verify_lcl_reference.py',
    'source/LCL_README.txt', 'source/lcl_download_manifest.json',
    'source/lcl_archive_inventory.json', 'source/lcl_reference_verification.json',
    'source/lcl_landing.html', 'source/make_source_package_manifest.py',
    'data/lcl/hourly.csv', 'data/lcl/daily_quality.csv',
    'data/lcl/household_inventory.json', 'data/lcl/selected_halfhour_source.csv.gz',
    'data/lcl/selection.json', 'data/lcl/manifest.json',
]
files = []
for name in names:
    p = ROOT / name
    files.append({'path': 'work/external_deadline/' + name, 'bytes': p.stat().st_size,
                  'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
result = {'status': 'passed', 'files': files, 'count': len(files),
          'excluded': ['source/*raw/ full CSV directories', 'source/*.7z and source/*.zip original downloads',
                       'source/7zr.exe and source/7zip/ extraction tools', 'source/article* full source-paper copies',
                       'source/*preparation.log runtime logs', 'source/__pycache__/'],
          'note': 'The listed files plus this manifest form the bounded source package. Original downloads are regenerated from official URLs with pinned hashes. Root protocol/amendment and forecast/audit files must be added by their owning pipeline.'}
(HERE / 'source_package_manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'status': 'passed', 'files': len(files), 'total_bytes': sum(r['bytes'] for r in files)}))
