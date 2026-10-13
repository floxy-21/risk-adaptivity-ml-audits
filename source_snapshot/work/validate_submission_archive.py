"""Verify a fresh extraction without original raw-source downloads.

The distributed UCI-only new-consumer excerpt is used by its separate checker.
The original mixed-source 34-series prediction/target archive stays omitted.
"""
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from revision_extension_inputs import ALLOWED_FRAGMENT_TEX

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile_daily(root):
    totals = {}
    with (root/'outputs/study_recovery_pair_seed.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            budget = int(row['budget'])
            if row['policy'] != 'optimal_minimax_width' or int(row['gap_hours']) != 6 or budget not in (0, 2):
                continue
            for pair in ('all_pairs', row['model_a']+'__'+row['model_b']):
                key = (row['cohort'], budget, pair)
                values = totals.setdefault(key, [0, 0, 0])
                for index, name in enumerate(('pair_trials', 'decisions', 'wrong_decisions')):
                    values[index] += int(row[name])
    checked = 0
    with (root/'outputs/study_daily_pairs.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            key = (row['cohort'], int(row['budget']), row['pair'])
            expected = [int(row[name]) for name in ('comparisons', 'certificate_decisions', 'certificate_wrong')]
            assert totals[key] == expected, (key, totals[key], expected)
            checked += 1
    assert checked == 42
    return checked


def main():
    archive_path=ROOT/'outputs/research_supplement.zip'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    stage=(ROOT/'work'/f'data_supplement_verify_{stamp}').resolve()
    assert stage.is_relative_to((ROOT/'work').resolve())
    stage.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        names=archive.namelist()
        assert 'outputs/study_predictions.csv' not in names
        assert not any(name.endswith(('.pdf','.pkl')) for name in names)
        assert {name for name in names if name.endswith('.tex')}==set(ALLOWED_FRAGMENT_TEX)
        assert 'outputs/JOURNAL_ALIGNMENT.txt' not in names
        for name in names:
            assert (stage/name).resolve().is_relative_to(stage)
        archive.extractall(stage)
    subprocess.run([sys.executable,'work/verify_research_supplement.py'],cwd=stage,check=True,capture_output=True,text=True)
    revision_run=subprocess.run([sys.executable,'work/reproduce_final_revision.py'],cwd=stage,check=False,capture_output=True,text=True)
    if revision_run.returncode:
        print(revision_run.stdout,revision_run.stderr)
        revision_run.check_returncode()
    entry_result=json.loads(revision_run.stdout[revision_run.stdout.rfind('\n{')+1:])
    revision_report_path=Path(entry_result['report']).resolve()
    assert revision_report_path.is_relative_to(stage)
    final_report=json.loads(revision_report_path.read_text())
    assert final_report['status']=='passed' and final_report['exact_manuscript_bytes']
    assert final_report['refit_public_check']['rows_compared']==159984
    revision_report=final_report['baseline_replay']
    revision_report_path=Path(revision_report['stage'])/'outputs/review_revision_reproduction.json'
    assert revision_report_path.is_relative_to(stage)
    assert revision_report['status']=='passed' and revision_report['exact_manuscript_bytes']
    period_audit=json.loads((revision_report_path.parent/'study_period_archive_audit.json').read_text())
    interval_trace_audit=json.loads((revision_report_path.parent/'study_interval_trace_audit.json').read_text())
    assert period_audit['status']==interval_trace_audit['status']=='passed'
    extension_checks=revision_report['extension_checks']
    assert extension_checks['status']=='passed' and extension_checks['archived_generation_inputs_unchanged']
    assert extension_checks['reports']['randomized']['cases']==20736
    assert extension_checks['reports']['randomized']['compact_versus_finite_game_checks']==1074
    assert extension_checks['reports']['compact_policy']['cases']==48
    assert extension_checks['reports']['noaa']['raw_and_preprocessed_direct_vertex_checks']==832
    assert extension_checks['reports']['tie_policies']['status']=='passed'
    assert extension_checks['reports']['tie_policies']['secondary_optimality_checks']==2148
    assert extension_checks['reports']['randomized_holdout']['status']=='PASS'
    assert extension_checks['reports']['randomized_holdout']['cases']==19260
    assert extension_checks['reports']['randomized_holdout']['positive_probability_batches']==3958
    assert extension_checks['reports']['scaling']['status']=='PASS'
    assert extension_checks['reports']['scaling']['compact_cases']==28
    assert extension_checks['reports']['scaling']['finite_comparisons']==12
    reconciled_daily_rows = reconcile_daily(stage)
    code="""
import sys,unittest,json
from pathlib import Path
sys.path.insert(0,'outputs')
if not Path('outputs/study_recovery_cases.csv').exists():
    import test_study_recovery
    cls=test_study_recovery.RecoveryTests
    name='test_exploratory_diagnostics_reconcile_without_changing_primary'
    setattr(cls,name,unittest.skip('Full historical per-day recovery cases withheld; UCI public subset and unchanged-source hash supplied; full check passed locally')(getattr(cls,name)))
suite=unittest.TestLoader().loadTestsFromNames(['test_energy_rank_bounds','study_verification_tests','test_main_ai_revision','test_study_recovery','study_greedy_boundary'])
r=unittest.TextTestRunner(verbosity=2).run(suite)
print('TEST_RESULT:'+json.dumps({'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':[(str(t),reason) for t,reason in r.skipped]}))
sys.exit(0 if r.wasSuccessful() else 1)
"""
    checks=subprocess.run([sys.executable,'-c',code],cwd=stage,check=False,capture_output=True,text=True)
    if checks.returncode:
        print(checks.stdout, checks.stderr)
        checks.check_returncode()
    counts=json.loads(next(line.split(':',1)[1] for line in checks.stdout.splitlines() if line.startswith('TEST_RESULT:')))
    adaptive=subprocess.run([sys.executable,'outputs/test_recovery_adaptivity.py'],cwd=stage,check=True,capture_output=True,text=True)
    adaptive_report=json.loads((stage/'outputs/test_recovery_adaptivity.json').read_text())
    assert adaptive_report['status']=='passed'
    interval_run=subprocess.run([sys.executable,'outputs/study_interval_total_recovery.py'],cwd=stage,check=True,capture_output=True,text=True)
    interval_report=json.loads((stage/'outputs/study_interval_total_recovery.json').read_text())
    assert interval_report['all_passed']
    holdout_run=subprocess.run([sys.executable,'work/verify_holdout_replication.py'],cwd=stage,check=True,capture_output=True,text=True)
    holdout_audit=json.loads((stage/'outputs/study_holdout_independent_audit.json').read_text())
    assert holdout_audit['status']=='passed'
    table_hash=sha(stage/'outputs/manuscript_result_tables.json')
    subprocess.run([sys.executable,'work/analyze_final_results.py'],cwd=stage,check=True,capture_output=True,text=True)
    assert sha(stage/'outputs/manuscript_result_tables.json')==table_hash
    sections_hash=sha(stage/'work/final_sections.json')
    subprocess.run([sys.executable,'work/compose_final_sections.py'],cwd=stage,check=True,capture_output=True,text=True)
    assert sha(stage/'work/final_sections.json')==sections_hash
    subprocess.run([sys.executable,'work/build_final_manuscript.py'],cwd=stage,check=True,capture_output=True,text=True)
    expected=json.loads((stage/'outputs/manuscript_reconstruction_check.json').read_text())['source_hashes']['outputs/revised_manuscript.tex']
    assert sha(stage/'outputs/revised_manuscript.tex')==expected
    report={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
        'archive':archive_path.name,'archive_bytes':archive_path.stat().st_size,
        'archive_sha256':sha(archive_path),'archive_files':len(names),
        'manifest_content_files':len((stage/'MANIFEST.sha256').read_text().splitlines()),
        'fresh_extract_directory':stage.relative_to(ROOT).as_posix(),
        'fresh_extract_tests_run':counts['run'],'test_failures':counts['failures'],
        'test_errors':counts['errors'],'tests_skipped':counts['skipped'],
        'adaptive_cases_passed':adaptive_report['cases'],
        'interval_total_verification':interval_report['counts'],
        'interval_total_maximum_absolute_errors':interval_report['maximum_absolute_errors'],
        'holdout_independent_aggregation_checks':holdout_audit['aggregation_checks'],
        'holdout_independent_numerical_checks':holdout_audit['independent_numerical_checks'],
        'holdout_independent_maximum_absolute_discrepancies':holdout_audit['maximum_absolute_discrepancies'],
        'review_revision_entrypoint_passed':True,
        'review_revision_reproduction':revision_report,
        'fresh_refit_public_check':final_report['refit_public_check'],
        'period_independent_audit':period_audit,
        'interval_trace_audit':interval_trace_audit,
        'randomized_and_natural_extension_checks':extension_checks,
        'daily_recovery_rows_reconciled':reconciled_daily_rows,
        'zip_crc_passed':True,'manifest_sha256_verification_passed':True,
        'original_aggregate_tables_rebuilt_without_full_prediction_archive':True,
        'manuscript_exactly_rebuilt_without_original_34_series_prediction_archive':True,
        'excluded_artifacts':['original 34-series complete hourly predictions/targets including BLEM',
                             'original raw-source archives','main TeX/PDF documents','source caches','private journal planning'],
        'included_tex_fragments':sorted(ALLOWED_FRAGMENT_TEX),
        'included_target_excerpt':'UCI worked/replication/review records with CC BY 4.0 attribution and NOAA selected observation/decoded-forecast records; no BLEM raw targets or persistence'}
    (ROOT/'outputs/supplement_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (ROOT/'work/final_archive_test_log.txt').write_text(revision_run.stdout+revision_run.stderr+'\n'+checks.stdout+checks.stderr+'\n'+adaptive.stdout+adaptive.stderr+'\n'+interval_run.stdout+interval_run.stderr+'\n'+holdout_run.stdout+holdout_run.stderr,encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
