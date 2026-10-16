"""Replay the current paper's checks in a fresh, hash-verified package copy.

Run from an extracted research_supplement.zip. No network or model fitting is
used. Timing-bearing reports are retained separately, then frozen composition
inputs are restored before the exact manuscript reconstruction.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, csv, hashlib, json, math, os, shutil, subprocess, sys, time

ROOT = Path(__file__).resolve().parents[2]

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''): h.update(b)
    return h.hexdigest()

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path)
    parser.add_argument('--small', action='store_true', help='Omit empirical endpoint and tie-policy replay; all package hashes still checked.')
    args = parser.parse_args()
    started = time.perf_counter()
    manifest = ROOT / 'MANIFEST.sha256'
    if not manifest.is_file(): raise SystemExit('Extract the supplement; MANIFEST.sha256 is required.')
    # A provenance checker must see the frozen archive, before a regeneration
    # job rewrites a declared mutable report. Check this dependency up front.
    replay_jobs = read(ROOT / 'work/risk_adaptivity_revision/replay_jobs.json')
    rewritten = set()
    for job in replay_jobs:
        conflicts = rewritten.intersection(job.get('requires_frozen_inputs', []))
        if conflicts:
            raise RuntimeError('Frozen-input check scheduled after regeneration: '
                               + job['name'] + ': ' + ', '.join(sorted(conflicts)))
        rewritten.update(job.get('mutable_reports', []))
    stage = (args.stage or ROOT / 'work' / ('rr_' + datetime.now(timezone.utc).strftime('%H%M%S%f'))).resolve()
    stage.mkdir(parents=True, exist_ok=False)
    pins = {}
    for line in manifest.read_text().splitlines():
        expected, name = line.split('  ', 1)
        p = (ROOT / name).resolve()
        assert p.is_relative_to(ROOT.resolve()) and p.is_file(), name
        assert sha(p) == expected, 'Package hash mismatch: ' + name
        pins[name] = expected
        dest = stage / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    logs, checks = [], {}
    (stage / 'outputs').mkdir(exist_ok=True)

    def run(script, *arguments):
        number = len(logs) + 1
        log = stage / 'outputs' / f'risk_step_{number:02d}.log'
        bootstrap = ('import runpy,sys\nfrom pathlib import Path\n'
                     'def no_network(event, arguments):\n'
                     '    if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:\n'
                     '        raise RuntimeError("Network access is disabled during default package replay")\n'
                     'sys.addaudithook(no_network)\n'
                     'p=sys.argv[1];sys.argv=sys.argv[1:]\n'
                     'sys.path.insert(0,str(Path(p).parent));runpy.run_path(p,run_name="__main__")')
        print('Running:', script, *map(str, arguments), flush=True)
        start = time.perf_counter()
        environment = dict(os.environ)
        environment.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
        with log.open('w', encoding='utf-8') as f:
            result = subprocess.run([sys.executable, '-c', bootstrap, str(stage / script), *map(str, arguments)],
                                    cwd=stage, env=environment, stdout=f, stderr=subprocess.STDOUT, text=True)
        logs.append({'script': script, 'arguments': list(map(str, arguments)), 'returncode': result.returncode,
                     'seconds': time.perf_counter()-start, 'log': log.relative_to(stage).as_posix()})
        if result.returncode:
            # Preserve process diagnostics even when its traceback is incomplete.
            # A failed step stops this run; no retry can conceal its first result.
            failure = {'status': 'failed', 'failure_kind': 'nonzero_subprocess_returncode',
                       'completed_steps': len(logs)-1, 'failed_step_number': number,
                       'failed_step': logs[-1], 'steps': logs,
                       'package_root': str(ROOT.resolve()), 'stage': str(stage),
                       'manifest_sha256': sha(manifest),
                       'script_sha256': sha(stage / script), 'log_sha256': sha(log),
                       'elapsed_seconds': time.perf_counter()-started}
            failure_text = json.dumps(failure, indent=2) + '\n'
            failure_path = stage / 'outputs/risk_clean_replay_failure.json'
            failure_path.write_text(failure_text, encoding='utf-8')
            (ROOT / 'outputs/risk_clean_replay_failure.json').write_text(failure_text, encoding='utf-8')
            print('\n'.join(log.read_text(encoding='utf-8', errors='replace').splitlines()[-30:]), flush=True)
            raise RuntimeError(f'Reproduction failed at step {number}, returncode {result.returncode}: '
                               + str(log) + '; diagnostics: ' + str(failure_path))

    rd = 'work/risk_adaptivity_revision/'
    run(rd + 'math/check_classification.py')
    checks['classification'] = read(stage / rd / 'math/classification_verification.json')
    run(rd + 'general/check_general_lp.py', '--output', 'outputs/risk_general_replay.json')
    checks['general'] = read(stage / 'outputs/risk_general_replay.json')
    run(rd + 'dual/verify_dual.py', '--output-dir', 'outputs/risk_dual_replay')
    checks['dual'] = read(stage / 'outputs/risk_dual_replay/verification.json')
    run(rd + 'dual/summarize_solver_comparison.py', '--output-dir', 'outputs/risk_solver_replay')
    checks['solver_comparison'] = read(stage / 'outputs/risk_solver_replay/verification.json')
    if not args.small:
        run('work/certificate_grid_review/summarize_certificates.py', '--source', 'public', '--output-dir', 'outputs/risk_grid_replay')
        checks['public_grid'] = read(stage / 'outputs/risk_grid_replay/verification.json')
        run('work/randomized_tie_review/verify_ties.py')
        checks['historical_ties'] = read(stage / 'work/randomized_tie_review/independent_verification.json')
    # New practical extensions are listed explicitly after their verification.
    jobs = read(stage / rd / 'replay_jobs.json')
    if not args.small:
        for job in jobs:
            run(job['script'], *job.get('args', []))
            checks[job['name']] = read(stage / job['report'])
            assert checks[job['name']]['status'].lower() in {'pass','passed'}, job['name']
            for dotted, maximum in job.get('maximum_report_values', {}).items():
                value = checks[job['name']]
                for part in dotted.split('.'): value = value[part]
                assert math.isfinite(value) and 0 <= value <= maximum, (job['name'], dotted, value)
        # Match fresh scientific ledgers, not timing-bearing report byte hashes.
        matches = []
        pairs = [
            (rd+'practical/results/action_ledger.csv','outputs/risk_gate_replay/action_ledger.csv'),
            (rd+'practical_multi/results_public/case_ledger.csv','outputs/risk_selection_replay/case_ledger.csv'),
            (rd+'practical/replication/period_cases.csv','outputs/risk_replication_replay/period_cases.csv')]
        pairs += [(path, path) for job in jobs for path in job.get('scientific_csv', [])]
        for original, fresh in pairs:
            # A fixed-path replay overwrites the stage copy; compare it with
            # the frozen package root, before restoring mutable inputs.
            original_root = ROOT if original == fresh else stage
            with (original_root/original).open(newline='',encoding='utf-8') as a, (stage/fresh).open(newline='',encoding='utf-8') as b:
                left,right=csv.reader(a),csv.reader(b)
                assert next(left)==next(right), original
                count=0
                from itertools import zip_longest
                for row1,row2 in zip_longest(left,right):
                    assert row1 is not None and row2 is not None and len(row1)==len(row2), original
                    for x,y in zip(row1,row2):
                        if x==y: continue
                        try: nx,ny=float(x),float(y)
                        except ValueError: raise AssertionError((original,count,x,y))
                        assert math.isclose(nx,ny,rel_tol=1e-8,abs_tol=1e-10), (original,count,x,y)
                    count+=1
                matches.append({'archived':original,'fresh':fresh,'rows':count,'numeric_relative_tolerance':1e-8,'numeric_absolute_tolerance':1e-10})
        checks['practical_ledger_matches']=matches
        for job in jobs:
            for relative, keys in job.get('scientific_json', {}).items():
                frozen, fresh = read(ROOT/relative), read(stage/relative)
                for key in keys:
                    assert frozen[key] == fresh[key], (job['name'], relative, key)
    # Persist newly measured results before restoring only declared mutable reports.
    allowed = {'work/risk_adaptivity_revision/math/classification_verification.json',
               'work/randomized_tie_review/independent_verification.json'}
    allowed.update(p for job in jobs for p in job.get('mutable_reports', []))
    restored = []
    for name, expected in pins.items():
        p = stage / name
        if sha(p) != expected:
            assert name in allowed, 'Unexpected input modification: ' + name
            shutil.copy2(ROOT / name, p)
            restored.append(name)
    run(rd + 'build_manuscript.py')
    assert sha(stage / 'outputs/revised_manuscript.tex') == read(ROOT / 'outputs/risk_release_manifest.json')['output_sha256']
    assert all(sha(stage / name) == expected for name, expected in pins.items())
    report = {'status': 'passed', 'completed_utc': datetime.now(timezone.utc).isoformat(),
              'package_members_verified': len(pins), 'stage': str(stage), 'small': args.small,
              'steps': logs, 'checks': checks, 'restored_frozen_reports': restored,
              'manuscript_reproduced_sha256': sha(stage / 'outputs/revised_manuscript.tex'),
              'elapsed_seconds': time.perf_counter()-started,
              'scope': 'Fresh isolated executable replay from bundled inputs with network disabled; includes cached new-source counter replay and archived HTTP-trace checks, but no model fitting, private BLEM raw regeneration, new HTTP measurements, repeated scaling measurements, or external independent replication.'}
    (ROOT / 'outputs/risk_clean_replay.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in {'checks','steps'}}, indent=2), flush=True)

if __name__ == '__main__': main()
