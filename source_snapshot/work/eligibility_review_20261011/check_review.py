"""Replay the query-eligibility review without replacing archived reports.

Run at the extracted supplement root. This checks existing functions and
traces; it does not refit models, tune a policy or create new effectiveness data.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    started = time.perf_counter()
    jobs = [('eligibility/check_zero_coefficient.py', 'eligibility/report.json'),
            ('batch/check_saved_batches.py', 'batch/saved_batch_accounting.json'),
            ('batch/check_api_fixtures.py', 'batch/batch_api_fixtures.json')]
    archived = {report: (HERE / report).read_bytes() for _, report in jobs if (HERE / report).exists()}
    inputs = {str((HERE / script).relative_to(ROOT)).replace('\\', '/'): sha(HERE / script)
              for script, _ in jobs}
    for name in ['work/external_deadline/validation/trajectories.jsonl',
                 'work/external_deadline/test/trajectories.jsonl',
                 'work/external_deadline/acquisition/acquisition.py',
                 'work/decision_revision/prototype/ridge_policy.py',
                 'work/decision_revision/oracle/confirmation_oracle.py']:
        inputs[name] = sha(ROOT / name)
    output = ROOT / 'outputs'
    output.mkdir(exist_ok=True)
    checks, timings = {}, {}
    try:
        with (output / 'query_eligibility_review_replay.log').open('w', encoding='utf-8') as log:
            for script, report in jobs:
                before = time.perf_counter()
                result = subprocess.run([sys.executable, str(HERE / script)], cwd=ROOT,
                                        stdout=log, stderr=subprocess.STDOUT)
                assert result.returncode == 0, script
                checks[script] = json.loads((HERE / report).read_text())
                assert checks[script]['status'] == 'passed', script
                timings[script] = time.perf_counter() - before
    finally:
        # Retain fresh results below; restore published report bytes for exact
        # manuscript reconstruction and immutable package verification.
        for report, content in archived.items():
            (HERE / report).write_bytes(content)
    assert all(sha(ROOT / name) == expected for name, expected in inputs.items())
    report = {'status': 'passed', 'completed_utc': datetime.now(timezone.utc).isoformat(),
              'seconds': time.perf_counter()-started, 'inputs': inputs,
              'checks': checks, 'step_seconds': timings,
              'scope': 'Fresh regression and saved-batch accounting; no model fit, policy tuning or new effectiveness experiment.',
              'archived_report_bytes_preserved': True}
    (output / 'query_eligibility_review_replay.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'status': 'passed', 'seconds': report['seconds'], 'checks': list(checks)}))


if __name__ == '__main__':
    main()
