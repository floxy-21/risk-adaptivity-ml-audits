"""Reproduce decision-audit evidence in a new isolated copy of the supplement.

Run from an extracted research_supplement.zip with pinned requirements installed.
Default: bundled source check, complete confirmation replay, exhaustive oracle,
query-eligibility/batch review, complete public certificate grid, and exact
current manuscript reconstruction.
It does not refit models.
--development additionally replays every developmental concentration and baseline.
--legacy additionally runs the previous external replay using its archived TeX.
--refit creates fresh confirmation fits and acquisition outputs, not new paper claims.
--small runs mathematical checks without parsing empirical traces; all hashes are checked.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, shutil, subprocess, sys, time

ROOT = Path(__file__).resolve().parents[1]
DR = Path('work/decision_revision')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--small', action='store_true')
    ap.add_argument('--development', action='store_true')
    ap.add_argument('--legacy', action='store_true')
    ap.add_argument('--refit', action='store_true')
    args = ap.parse_args()
    assert not (args.small and (args.development or args.legacy or args.refit))
    started = time.perf_counter()
    manifest = ROOT / 'MANIFEST.sha256'
    if not manifest.exists():
        raise SystemExit('Extract research_supplement.zip and run this command at its root; MANIFEST.sha256 is required.')
    stage = ROOT / 'work' / ('dreplay_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    stage.mkdir(parents=True, exist_ok=False)
    pins = {}
    for line in manifest.read_text().splitlines():
        expected, name = line.split('  ', 1)
        source = (ROOT / name).resolve()
        assert source.is_relative_to(ROOT.resolve()) and source.is_file(), name
        assert sha(source) == expected, 'Package input mismatch: '+name
        pins[name] = expected
        if args.small and not (source.suffix == '.py' or name == 'outputs/requirements-study.txt'):
            continue
        dest = stage / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    (stage / 'outputs').mkdir(exist_ok=True)
    logs, checks = [], {}

    def run(script, *arguments):
        log = stage / 'outputs' / f'decision_step_{len(logs)+1:02d}_{Path(script).stem}.log'
        before = time.perf_counter()
        bootstrap = ('import runpy,sys;from pathlib import Path;'
                     'p=sys.argv[1];sys.argv=sys.argv[1:];'
                     'sys.path.insert(0,str(Path(p).parent));runpy.run_path(p,run_name="__main__")')
        print('Running:', script, *map(str, arguments), flush=True)
        with log.open('w', encoding='utf-8') as output:
            result = subprocess.run([sys.executable, '-c', bootstrap, str(stage / script), *map(str, arguments)],
                                    cwd=stage, stdout=output, stderr=subprocess.STDOUT, text=True)
        logs.append(dict(script=str(script), arguments=list(map(str, arguments)),
                         returncode=result.returncode, seconds=time.perf_counter()-before,
                         log=log.relative_to(stage).as_posix()))
        if result.returncode:
            print('\n'.join(log.read_text(encoding='utf-8', errors='replace').splitlines()[-35:]), flush=True)
            raise RuntimeError('Reproduction failed; original inputs preserved: '+str(log))

    # Mathematical checks overwrite only staged reports, which are retained
    # separately before restoring the archived report bytes used by the builder.
    for script, report in [('prototype/check.py', 'prototype/check.json'),
                           ('prototype/check_ridge.py', 'prototype/check_ridge.json'),
                           ('math/check_ridge_independent.py', 'math/ridge_independent_check.json')]:
        run(DR / script)
        p = stage / DR / report
        if p.exists():
            checks[script] = read(p)
    if not args.small:
        run(DR / 'math/verify_confirmation_source.py')
        checks['bundled_source'] = read(stage / DR / 'math/confirmation_source_check.json')
        assert checks['bundled_source']['status'] == 'passed'
        # Retain newly executed reports in this wrapper record, then restore
        # shipped proof/check report bytes pinned before fitting and composition.
        allowed_reports = {str(DR / name).replace('\\', '/') for name in (
            'prototype/check.json', 'prototype/check_ridge.json',
            'math/ridge_independent_check.json', 'math/confirmation_source_check.json')}
        restored = []
        for name, expected in pins.items():
            target = stage / name
            if target.exists() and sha(target) != expected:
                assert name in allowed_reports, 'Unexpected staged input modification: '+name
                shutil.copy2(ROOT / name, target)
                restored.append(name)
        checks['restored_archived_reports_after_fresh_checks'] = restored
        if args.refit:
            for name in ('confirmation_fitted', 'confirmation'):
                source = (stage / DR / name).resolve()
                target = (stage / DR / ('distributed_'+name)).resolve()
                assert source.is_relative_to(stage.resolve()) and target.is_relative_to(stage.resolve())
                source.rename(target)
            run('work/external_deadline/forecast/forecast.py', 'prepare', '--hourly', DR / 'confirmation_source/hourly.csv',
                '--config', DR / 'confirmation_source/forecast_config.json', '--output-dir', DR / 'confirmation_fitted')
            run('work/external_deadline/forecast/forecast.py', 'fit', '--prepared', DR / 'confirmation_fitted')
            run(DR / 'confirmation.py', 'run')
            checks['fresh_fit'] = read(stage / DR / 'confirmation_fitted/fit_metadata.json')
        run(DR / 'oracle/confirmation_oracle.py', '--run-dir', DR / 'confirmation',
            '--reference', DR / 'confirmation_fitted/reference_targets.csv', '--reference-period', 'test',
            '--output-dir', DR / 'replayed_oracle')
        checks['oracle'] = read(stage / DR / 'replayed_oracle/summary.json')
        if not args.refit:
            assert checks['oracle']['summaries'] == read(stage / DR / 'confirmation_oracle/summary.json')['summaries']
        run(DR / 'reviews/verify_decision_confirmation.py', '--run-dir', DR / 'confirmation',
            '--source-cases', DR / 'confirmation/source_cases.jsonl',
            '--reference', DR / 'confirmation_fitted/reference_targets.csv', '--reference-period', 'test',
            '--forecast-dir', DR / 'confirmation_fitted', '--primary-policy', 'ml_decision',
            '--comparators', 'width_one', 'hara_one', '--oracle-dir', DR / 'replayed_oracle',
            '--output', 'outputs/decision_confirmation_replay.json')
        checks['confirmation'] = read(stage / 'outputs/decision_confirmation_replay.json')
        assert checks['confirmation']['status'] == 'passed'
        run('work/eligibility_review_20261011/check_review.py')
        checks['query_eligibility_review'] = read(stage / 'outputs/query_eligibility_review_replay.json')
        assert checks['query_eligibility_review']['status'] == 'passed'
        assert checks['query_eligibility_review']['archived_report_bytes_preserved'] is True
        for relative in ('eligibility/report.json', 'batch/saved_batch_accounting.json',
                         'batch/batch_api_fixtures.json'):
            name = 'work/eligibility_review_20261011/' + relative
            assert sha(stage / name) == pins[name], 'Review did not restore archived report: '+name
        certificate_base = stage / 'work/certificate_grid_review'
        run('work/certificate_grid_review/summarize_certificates.py', '--source', 'public',
            '--output-dir', 'outputs/certificate_grid_replay')
        fresh_certificate = read(stage / 'outputs/certificate_grid_replay/verification.json')
        archived_certificate = read(certificate_base / 'results_public/verification.json')
        assert fresh_certificate['status'] == 'passed' and fresh_certificate['scope'] == 'public'
        assert fresh_certificate['output_sha256'] == archived_certificate['output_sha256']
        assert fresh_certificate['cross_tab'] == archived_certificate['cross_tab']
        assert fresh_certificate == archived_certificate, 'Public certificate grid report differs from archived report'
        archived_full_certificate = read(certificate_base / 'results_full/verification.json')
        assert archived_full_certificate['status'] == 'passed' and archived_full_certificate['scope'] == 'full'
        assert archived_full_certificate['script_sha256'] == sha(certificate_base / 'summarize_certificates.py')
        checks['certificate_grid'] = dict(public_replay=fresh_certificate,
            full_archived_comparisons=archived_full_certificate['paired_comparisons'],
            full_archived_cross_tab=archived_full_certificate['cross_tab'],
            full_scope_reexecuted=False,
            scope='Public endpoint grid reexecuted; full BLEM-dependent archived table is hash-checked, not reexecuted.')
        if args.development:
            for name in ('full', 'ridge_grid'):
                run(DR / 'reviews/verify_decision.py', '--run-dir', DR / 'prototype' / name,
                    '--source-cases', 'work/external_deadline/validation/trajectories.jsonl',
                    '--reference', 'work/external_deadline/fitted/reference_targets.csv',
                    '--reference-period', 'validation', '--output', f'outputs/development_{name}_replay.json')
                checks['development_'+name] = read(stage / f'outputs/development_{name}_replay.json')
                assert checks['development_'+name]['status'] == 'passed'
        if args.legacy:
            current_tex = (stage / 'outputs/revised_manuscript.tex').read_bytes()
            shutil.copy2(stage / DR / 'prior_release/revised_manuscript.tex', stage / 'outputs/revised_manuscript.tex')
            run('work/reproduce_external_revision.py')
            (stage / 'outputs/revised_manuscript.tex').write_bytes(current_tex)
            checks['legacy_external_replay'] = 'Passed; fresh nested report/log retained in staged work directory.'
        if not args.refit:
            run('work/build_decision_manuscript.py')
            expected = pins['outputs/revised_manuscript.tex']
            assert sha(stage / 'outputs/revised_manuscript.tex') == expected
            checks['exact_manuscript_sha256'] = expected
    for name, expected in pins.items():
        assert sha(ROOT / name) == expected, 'Original package member modified: '+name
    report = dict(status='passed', finished_utc=datetime.now(timezone.utc).isoformat(), stage=str(stage),
                  seconds=time.perf_counter()-started, steps=logs, checks=checks,
                  original_members_unchanged=True, package_members_checked=len(pins),
                  fresh_refit=args.refit, development_replayed=args.development, legacy_replayed=args.legacy,
                  exact_manuscript_rebuilt=not args.small and not args.refit,
                  scope='Fresh steps are listed; carried historical checks are not represented as reexecuted. Uses the installed pinned environment; no dependency installation is performed.')
    target = stage / 'outputs/decision_revision_reproduction.json'
    target.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'report': str(target), 'seconds': report['seconds']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
