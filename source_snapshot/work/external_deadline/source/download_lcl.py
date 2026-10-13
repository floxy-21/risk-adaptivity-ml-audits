"""Download official public LCL archive with a hash and bounded streaming memory."""
import hashlib, json, time, urllib.request
from pathlib import Path
from datetime import datetime, timezone
root = Path(__file__).resolve().parent
url = 'https://data.london.gov.uk/download/vqm0d/3527bf39-d93e-4071-8451-df2ade1ea4f2/LCL-FullData.zip'
path = root / 'LCL-FullData.zip'
t = time.perf_counter(); n = 0; h = hashlib.sha256()
with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60) as r, path.with_suffix('.zip.part').open('wb') as f:
    while b := r.read(1024 * 1024):
        f.write(b); h.update(b); n += len(b)
        if n % (100 * 1024 * 1024) == 0:
            print(json.dumps({'bytes': n, 'seconds': time.perf_counter() - t}), flush=True)
    assert n == 801_674_949, n
    record = {'url': url, 'final_url': r.url, 'status': r.status, 'bytes': n, 'sha256': h.hexdigest(), 'seconds': time.perf_counter() - t, 'created_utc': datetime.now(timezone.utc).isoformat()}
path.with_suffix('.zip.part').replace(path)
(root / 'lcl_download_manifest.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record), flush=True)
