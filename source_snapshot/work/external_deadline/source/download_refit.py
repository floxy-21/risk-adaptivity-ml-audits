"""Retrieve the openly licensed official REFIT raw archive with ordinary HTTP."""
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
BASE = 'https://pure.strath.ac.uk/ws/portalfiles/portal/'
FILES = [(62090176, 'RAW_READ_ME_081116.txt'), (62090177, 'REFIT_RAW_081116.7z')]
records = []
for identifier, name in FILES:
    url = f'{BASE}{identifier}/{name}'
    path = ROOT / name
    tick = time.perf_counter()
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=60) as response, path.with_suffix(path.suffix + '.part').open('wb') as output:
        n, digest = 0, hashlib.sha256()
        while chunk := response.read(1024 * 1024):
            output.write(chunk); digest.update(chunk); n += len(chunk)
            if n % (20 * 1024 * 1024) == 0:
                print(json.dumps({'file': name, 'bytes': n, 'seconds': time.perf_counter() - tick}), flush=True)
        expected = response.headers.get('Content-Length')
        if expected is not None:
            assert n == int(expected), (n, expected)
        records.append({'url': url, 'final_url': response.url, 'status': response.status, 'content_length': expected, 'bytes': n, 'sha256': digest.hexdigest(), 'seconds': time.perf_counter() - tick})
    path.with_suffix(path.suffix + '.part').replace(path)
    print(json.dumps({'file': name, 'status': 'complete', 'bytes': n}), flush=True)
(ROOT / 'download_manifest.json').write_text(json.dumps({'created_utc': datetime.now(timezone.utc).isoformat(), 'records': records}, indent=2), encoding='utf-8')
