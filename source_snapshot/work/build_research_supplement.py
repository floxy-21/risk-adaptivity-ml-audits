"""Package only final study artefacts, with reproducibility and hash validation.

No full raw archives, PDFs, caches, pilots or main TeX are included. Only the
explicit reusable theory/application TeX fragments are allowed. Dry-run is the
default; --build writes outputs/research_supplement.zip once final results exist.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from revision_extension_inputs import EXTENSION_PATHS, ALLOWED_FRAGMENT_TEX, validate_extension_inputs

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "outputs/REPRODUCE.txt",
    "outputs/requirements-study.txt",
    "outputs/energy_rank_bounds.py",
    "outputs/run_energy_rank_study.py",
    "outputs/test_energy_rank_bounds.py",
    "outputs/study_verification_tests.py",
    "outputs/test_main_ai_revision.py",
    "outputs/study_training_preflight.py",
    "outputs/study_training_preflight.json",
    "outputs/test_recovery_adaptivity.py",
    "outputs/test_recovery_adaptivity.json",
    "outputs/study_independent_audit.py",
    "outputs/study_independent_audit.json",
    "outputs/study_matched_coverage.py",
    "outputs/study_matched_coverage.csv",
    "outputs/study_matched_coverage.json",
    "outputs/study_predictions.csv",
    "outputs/export_frozen_forecasts.py",
    "outputs/frozen_forecasts.csv",
    "outputs/frozen_forecasts.json",
    "outputs/export_review_frozen_forecasts.py",
    "outputs/review_frozen_forecasts.csv",
    "outputs/review_frozen_forecasts.json",
    "outputs/review_raw_reconstruction.json",
    "outputs/study_comparisons.csv",
    "outputs/study_selections.csv",
    "outputs/study_period_comparisons.csv",
    "outputs/study_meter_results.json",
    "outputs/study_summary.json",
    "outputs/study_environment.json",
    "outputs/study_runtime_benchmark.py",
    "outputs/study_runtime_benchmark.json",
    "outputs/study_integrity_check.py",
    "outputs/study_integrity_check.json",
    "outputs/study_recovery.py",
    "outputs/test_study_recovery.py",
    "outputs/study_recovery.csv",
    "outputs/study_recovery.json",
    "outputs/study_recovery_neural.csv",
    "outputs/study_recovery_regression_fixtures.json",
    "outputs/study_operator_example.py",
    "outputs/study_operator_example.json",
    "outputs/study_operator_example.csv",
    "outputs/study_recovery_pair_seed.csv",
    "outputs/study_recovery_cases.csv",
    "outputs/export_recovery_cases_public.py",
    "outputs/study_recovery_cases_public.csv",
    "outputs/study_recovery_cases_public_manifest.json",
    "outputs/study_daily_evaluation.py",
    "outputs/study_daily_evaluation.json",
    "outputs/study_daily_matched.csv",
    "outputs/study_daily_curves.csv",
    "outputs/study_daily_pairs.csv",
    "outputs/study_daily_margin_strata.csv",
    "outputs/study_archive_access.py",
    "outputs/study_archive_access.json",
    "outputs/study_archive_access_cohorts.csv",
    "outputs/study_archive_access_meters.csv",
    "outputs/study_archive_access_pair_seed.csv",
    "outputs/study_holdout_consumers.py",
    "outputs/study_holdout_consumers.json",
    "outputs/study_holdout_consumers_selection.json",
    "outputs/study_holdout_consumers_predictions.csv",
    "outputs/study_holdout_consumers_pair_seed.csv",
    "outputs/study_holdout_consumers_meters.csv",
    "outputs/study_holdout_consumers_cohorts.csv",
    "outputs/study_holdout_consumers_named_pairs.csv",
    "outputs/study_holdout_consumers_forecast_metrics.csv",
    "outputs/study_holdout_independent_audit.json",
    "outputs/study_period_archive.py",
    "outputs/study_period_archive.json",
    "outputs/study_period_archive_manifest.json",
    "outputs/study_period_archive_mask_audit.json",
    "outputs/study_period_archive_audit.json",
    "outputs/study_period_archive_cases.csv",
    "outputs/study_period_archive_scenarios.csv",
    "outputs/study_period_archive_cohorts.csv",
    "outputs/study_period_archive_pairs.csv",
    "outputs/study_period_archive_matched.csv",
    "outputs/study_period_archive_sources.csv",
    "outputs/study_period_archive_states.csv.gz",
    "outputs/study_period_archive_links.csv.gz",
    "outputs/study_period_archive_aggregates.csv.gz",
    "outputs/study_period_archive_public_cases.csv",
    "outputs/study_period_archive_public_sources.csv",
    "outputs/study_period_archive_public_states.csv.gz",
    "outputs/study_period_archive_public_links.csv.gz",
    "outputs/study_period_archive_public_aggregates.csv.gz",
    "outputs/study_period_archive_public_manifest.json",
    "outputs/study_interval_trace_recovery.py",
    "outputs/study_interval_trace_recovery.json",
    "outputs/study_interval_trace_recovery.csv",
    "outputs/study_interval_trace_recovery_pair_seed.csv",
    "outputs/study_interval_trace_recovery_cohorts.csv",
    "outputs/study_interval_trace_recovery_gaps.csv",
    "outputs/study_interval_trace_audit.json",
    "outputs/study_greedy_boundary.py",
    "outputs/study_greedy_boundary.json",
    "outputs/interval_total_recovery.py",
    "outputs/study_interval_total_recovery.py",
    "outputs/study_interval_total_recovery.json",
    "outputs/study_recovery_runtime.py",
    "outputs/study_recovery_runtime.json",
    "outputs/manuscript_result_tables.json",
    "outputs/analyze_ai_recovery.py",
    "outputs/ai_recovery_analysis.json",
    "outputs/analyze_recovery_diagnostics.py",
    "outputs/recovery_diagnostics.json",
    "outputs/manuscript_reconstruction_check.json",
    "work/study_protocol.txt",
    "work/study_protocol_blem.txt",
    "work/study_protocol_amendment.txt",
    "work/study_protocol_recovery.txt",
    "work/study_protocol_ai_revision.txt",
    "work/study_protocol_training_convergence.txt",
    "work/study_training_preflight_log.txt",
    "work/recovery_ai_protocol.txt",
    "work/recovery_exploratory_amendment.txt",
    "work/recovery_cache_amendment.txt",
    "work/solver_validation_amendment.txt",
    "work/daily_evaluation_protocol.txt",
    "work/archive_access_protocol.txt",
    "work/holdout_consumers_protocol.txt",
    "work/verify_holdout_replication.py",
    "work/period_archive_protocol.txt",
    "work/period_archive_bugfix_amendment.txt",
    "work/verify_period_archive_mask_source.py",
    "work/export_period_archive_public.py",
    "work/verify_period_archive.py",
    "work/interval_trace_protocol.txt",
    "work/verify_interval_trace.py",
    "work/reproduce_review_revision.py",
    "work/study_daily_evaluation_log.txt",
    "work/prediction_archive_omission.json",
    "work/study_run_log.txt",
    "work/study_recovery_log.txt",
    "work/download_study_data.py",
    "work/data_prepare_blem.py",
    "work/build_research_supplement.py",
    "work/verify_research_supplement.py",
    "work/validate_submission_archive.py",
    "work/prepare_reproduction.py",
    "work/analyze_final_results.py",
    "work/build_final_manuscript.py",
    "work/compose_final_sections.py",
    "work/compose_review_sections.py",
    "work/compose_archive_sections.py",
    "work/compose_interval_sections.py",
    "work/compose_holdout_sections.py",
    "work/compose_period_archive_sections.py",
    "work/compose_interval_trace_sections.py",
    "work/check_manuscript_reconstruction.py",
    "work/final_sections.json",
    "work/data_uci_provenance.json",
    "work/data_electricity_provenance.json",
    "work/data_blem_provenance.json",
    "work/data_blem_source_notes.json",
    "work/data_blem_audit.json",
]
REQUIRED.extend(EXTENSION_PATHS)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validated_content(root):
    validate_extension_inputs(root)
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise RuntimeError("Final package files missing: " + ", ".join(missing))
    content = {name: (root / name).read_bytes() for name in REQUIRED}
    empty = [name for name, blob in content.items() if not blob]
    if empty:
        raise RuntimeError("Incomplete/empty files: " + ", ".join(empty))
    summary = json.loads(content["outputs/study_summary.json"])
    lossless=json.loads(content['outputs/review_frozen_forecasts.json'])
    if digest(content['outputs/review_frozen_forecasts.csv'])!=lossless['output_sha256']:
        raise RuntimeError('Lossless review export mismatch')
    if digest(content['outputs/export_review_frozen_forecasts.py'])!=lossless['script_sha256']:
        raise RuntimeError('Lossless review export script mismatch')
    restored=json.loads(content['outputs/review_raw_reconstruction.json'])
    if restored['status']!='passed' or not restored['exact_original_bytes']:
        raise RuntimeError('Original evaluation archive was not exactly reconstructed')
    if restored['reconstructed_predictions_sha256']!=lossless['original_predictions_sha256']:
        raise RuntimeError('Reconstructed frozen archive differs from source')
    if digest(content['work/reproduce_review_revision.py'])!=restored['runner_sha256']:
        raise RuntimeError('Raw reconstruction runner changed after its recorded check')
    holdout = json.loads(content['outputs/study_holdout_consumers.json'])
    if holdout['status'] != 'passed' or holdout['failures']:
        raise RuntimeError('Frozen new-consumer replication has not passed')
    selection = holdout['selection']
    if json.loads(content['outputs/study_holdout_consumers_selection.json']) != selection:
        raise RuntimeError('Frozen new-consumer selection changed')
    for name, expected in {**selection['original_artifact_hashes'], **selection['helper_hashes'],
                           **holdout['output_hashes'],
                           'study_holdout_consumers.py': selection['script_sha256']}.items():
        if digest(content['outputs/' + name]) != expected:
            raise RuntimeError('Frozen new-consumer source or output mismatch: ' + name)
    if digest(content['work/holdout_consumers_protocol.txt']) != selection['protocol_sha256']:
        raise RuntimeError('Frozen new-consumer protocol mismatch')
    holdout_audit = json.loads(content['outputs/study_holdout_independent_audit.json'])
    if holdout_audit['status'] != 'passed':
        raise RuntimeError('Independent new-consumer audit has not passed')
    if digest(content['work/verify_holdout_replication.py']) != holdout_audit['script_sha256']:
        raise RuntimeError('Independent new-consumer checker changed')
    for name, expected in holdout_audit['source_hashes'].items():
        if digest(content['outputs/' + name]) != expected:
            raise RuntimeError('Independent new-consumer audit source mismatch: ' + name)
    archive_access = json.loads(content["outputs/study_archive_access.json"])
    if archive_access['status'] != 'passed' or archive_access['checks']['wrong_certificates'] != 0:
        raise RuntimeError('Archive-access sensitivity has not passed')
    for name, expected in {**archive_access['source_hashes'], **archive_access['output_hashes'],
                           'study_archive_access.py': archive_access['script_sha256']}.items():
        if digest(content['outputs/' + name]) != expected:
            raise RuntimeError('Archive-access source or output mismatch: ' + name)
    if digest(content['work/archive_access_protocol.txt']) != archive_access['protocol_sha256']:
        raise RuntimeError('Archive-access protocol mismatch')
    boundary = json.loads(content['outputs/study_greedy_boundary.json'])
    if not boundary['all_passed'] or boundary['tests_run'] != 3:
        raise RuntimeError('Greedy boundary checks have not passed')
    for name, expected in boundary['source_hashes'].items():
        if digest(content['outputs/' + name]) != expected:
            raise RuntimeError('Greedy boundary source mismatch: ' + name)
    interval = json.loads(content['outputs/study_interval_total_recovery.json'])
    if not interval['all_passed']:
        raise RuntimeError('Interval-total batch verification did not pass')
    for name, expected in interval['source_hashes'].items():
        if digest(content['outputs/' + name]) != expected:
            raise RuntimeError('Interval-total source mismatch: ' + name)
    for stem, protocol_name in [('study_period_archive','period_archive_protocol.txt'),
                                ('study_interval_trace_recovery','interval_trace_protocol.txt')]:
        extension=json.loads(content['outputs/'+stem+'.json'])
        if extension['status']!='passed':
            raise RuntimeError('Unpassed new revision: '+stem)
        for name,expected in {**extension['source_hashes'], **extension['output_hashes']}.items():
            if digest(content['outputs/'+name])!=expected:
                raise RuntimeError('Revision hash mismatch: '+name)
        if digest(content['work/'+protocol_name])!=extension['protocol_sha256']:
            raise RuntimeError('Revision protocol mismatch: '+stem)
    period=json.loads(content['outputs/study_period_archive.json'])
    if digest(content['outputs/study_period_archive.py'])!=period['script_sha256']:
        raise RuntimeError('Period script mismatch')
    if digest(content['outputs/study_period_archive_manifest.json'])!=period['manifest_sha256']:
        raise RuntimeError('Period manifest mismatch')
    period_manifest=json.loads(content['outputs/study_period_archive_manifest.json'])
    correction=period_manifest['implementation_correction']
    if digest(content[correction['amendment_file']])!=correction['amendment_sha256']:
        raise RuntimeError('Period mask correction amendment mismatch')
    mask_audit=json.loads(content['outputs/study_period_archive_mask_audit.json'])
    if mask_audit['status']!='passed' or digest(content['work/verify_period_archive_mask_source.py'])!=mask_audit['script_sha256']:
        raise RuntimeError('Original-source mask audit mismatch')
    for name,checker in [('study_period_archive_audit.json','verify_period_archive.py'),
                         ('study_interval_trace_audit.json','verify_interval_trace.py')]:
        checked=json.loads(content['outputs/'+name])
        if checked['status']!='passed':
            raise RuntimeError('Revision checker did not pass: '+name)
        if digest(content['work/'+checker])!=checked['script_sha256']:
            raise RuntimeError('Revision checker changed: '+checker)
        for source_name,expected in checked['source_hashes'].items():
            if digest(content['outputs/'+source_name])!=expected:
                raise RuntimeError('Revision check used a different input: '+source_name)
    omitted = json.loads(content["work/prediction_archive_omission.json"])
    predictions = content["outputs/study_predictions.csv"]
    if omitted["filename"] != "study_predictions.csv" or omitted["sha256"] != digest(predictions) or omitted["bytes"] != len(predictions):
        raise RuntimeError("Prediction omission marker does not match the verified local predictions")
    exported=json.loads(content['outputs/frozen_forecasts.json'])
    if digest(content['outputs/export_frozen_forecasts.py'])!=exported['script_sha256'] or digest(content['outputs/frozen_forecasts.csv'])!=exported['output_sha256']:
        raise RuntimeError('Frozen forecast export provenance mismatch')
    for name,expected in exported['source_hashes'].items():
        if digest(content['outputs/'+name])!=expected:
            raise RuntimeError(f'Frozen forecast export source mismatch: {name}')
    if exported['raw_targets_included'] or not exported['blem_daily_persistence_omitted']:
        raise RuntimeError('Frozen forecast export includes prohibited target copies')
    if not summary.get("completed_utc") or summary.get("reference_crosschecks_passed", 0) < 1000:
        raise RuntimeError("Final summary does not confirm completed study and numerical checks")
    preflight=json.loads(content["outputs/study_training_preflight.json"])
    if preflight["status"] != "passed" or preflight["warning_count"] != 0 or len(preflight["meters"]) != 34:
        raise RuntimeError("Training-only convergence preflight did not pass for all 34 meters")
    if preflight["main_script_sha256"] != summary["script_sha256"] or digest(content["outputs/study_training_preflight.py"]) != preflight["script_sha256"] or digest(content["work/study_protocol_training_convergence.txt"]) != preflight["protocol_sha256"]:
        raise RuntimeError("Training-only preflight source or protocol mismatch")
    if preflight["parameters"] != summary["design"]["fixed_hyperparameters"]["mlp"]:
        raise RuntimeError("Final MLP configuration differs from the convergent preflight")
    for meter in summary["meters"]:
        training=meter["mlp_training"]
        if training["warnings"] or training["epochs"] >= preflight["parameters"]["max_iter"]:
            raise RuntimeError(f"Final neural training did not stop cleanly for {meter['meter']}")
    if digest(content["outputs/run_energy_rank_study.py"]) != summary["script_sha256"]:
        raise RuntimeError("Study script differs from the version used to produce final results")
    if digest(content["work/study_protocol.txt"]) != summary["protocol_sha256"]:
        raise RuntimeError("Main protocol differs from the recorded analysis protocol")
    audit = json.loads(content["outputs/study_independent_audit.json"])
    if digest(content["outputs/study_independent_audit.py"]) != audit["audit_script_sha256"]:
        raise RuntimeError("Independent audit script differs from recorded version")
    if summary["script_sha256"] != audit["study_script_sha256"]:
        raise RuntimeError("Independent audit did not validate the final study script")
    if digest(content["outputs/energy_rank_bounds.py"]) != audit["generic_solver_sha256"]:
        raise RuntimeError("Independent audit did not validate the final generic solver")
    adaptivity = json.loads(content["outputs/test_recovery_adaptivity.json"])
    if adaptivity["status"] != "passed" or digest(content["outputs/test_recovery_adaptivity.py"]) != adaptivity["script_sha256"]:
        raise RuntimeError("Adaptive recovery audit does not validate the final test script")
    matched = json.loads(content["outputs/study_matched_coverage.json"])
    for field, name in [("script_sha256", "study_matched_coverage.py"),
                        ("source_summary_sha256", "study_summary.json"),
                        ("source_period_sha256", "study_period_comparisons.csv")]:
        if digest(content["outputs/" + name]) != matched[field]:
            raise RuntimeError(f"Matched-coverage provenance mismatch: {field}")
    tables = json.loads(content["outputs/manuscript_result_tables.json"])
    for name, expected in tables["source_hashes"].items():
        if digest(content["outputs/" + name]) != expected:
            raise RuntimeError(f"Manuscript table source hash mismatch: {name}")
    ai_analysis = json.loads(content["outputs/ai_recovery_analysis.json"])
    if digest(content["outputs/analyze_ai_recovery.py"]) != ai_analysis["analysis_script_sha256"]:
        raise RuntimeError("AI recovery postanalysis script hash mismatch")
    for name, expected in ai_analysis["source_hashes"].items():
        if digest(content["outputs/" + name]) != expected:
            raise RuntimeError(f"AI recovery postanalysis source hash mismatch: {name}")
    recovery_diagnostics=json.loads(content['outputs/recovery_diagnostics.json'])
    if digest(content['outputs/analyze_recovery_diagnostics.py'])!=recovery_diagnostics['analysis_script_sha256']:
        raise RuntimeError('Exploratory recovery diagnostic script mismatch')
    for name,expected in recovery_diagnostics['source_hashes'].items():
        if digest(content['outputs/'+name])!=expected:
            raise RuntimeError(f'Exploratory recovery diagnostic source mismatch: {name}')
    integrity = json.loads(content["outputs/study_integrity_check.json"])
    if integrity["status"] != "passed":
        raise RuntimeError("Final cross-file integrity check did not pass")
    for name, expected in integrity["hashes_verified"].items():
        prefix = "work/" if name.startswith("study_protocol") else "outputs/"
        if digest(content[prefix + name]) != expected:
            raise RuntimeError(f"Final integrity report source mismatch: {name}")
    recovery = json.loads(content["outputs/study_recovery.json"])
    recovery_paths = {"script": "outputs/study_recovery.py",
                      "protocol": "work/" + recovery.get("protocol_filename", "study_protocol_recovery.txt"),
                      "study_predictions.csv": "outputs/study_predictions.csv",
                      "study_summary.json": "outputs/study_summary.json",
                      "study_recovery.csv": "outputs/study_recovery.csv",
                      "study_recovery_neural.csv": "outputs/study_recovery_neural.csv",
                      "study_recovery_regression_fixtures.json": "outputs/study_recovery_regression_fixtures.json"}
    recovery_paths.update({name:"outputs/"+name for name in ['study_recovery_pair_seed.csv','study_recovery_cases.csv']})
    recovery_paths['exploratory_protocol']='work/'+recovery['exploratory_diagnostics']['protocol_filename']
    recovery_paths['implementation_protocol']='work/'+recovery['implementation_amendment_filename']
    for key, name in recovery_paths.items():
        if digest(content[name]) != recovery["hashes"][key]:
            raise RuntimeError(f"Recovery experiment provenance mismatch: {key}")
    if recovery["main_study_script_sha256"] != summary["script_sha256"] or recovery["meters"] != 34:
        raise RuntimeError("Recovery extension is incomplete or uses another main study")
    example=json.loads(content["outputs/study_operator_example.json"])
    example_paths={"script":"outputs/study_operator_example.py",
                   "predictions":"outputs/study_predictions.csv",
                   "main_summary":"outputs/study_summary.json",
                   "recovery_source":"outputs/study_recovery.py",
                   "protocol":"work/recovery_ai_protocol.txt",
                   "table":"outputs/study_operator_example.csv"}
    for key,name in example_paths.items():
        if digest(content[name]) != example["hashes"][key]:
            raise RuntimeError(f"Operator example provenance mismatch: {key}")
    daily=json.loads(content['outputs/study_daily_evaluation.json'])
    if daily['status']!='passed' or digest(content['outputs/study_daily_evaluation.py'])!=daily['script_sha256']:
        raise RuntimeError('Daily evaluation source does not match completed analysis')
    if digest(content['work/daily_evaluation_protocol.txt'])!=daily['protocol_sha256']:
        raise RuntimeError('Daily evaluation protocol hash mismatch')
    for name,expected in (daily['source_hashes']|daily['output_hashes']).items():
        if digest(content['outputs/'+name])!=expected:
            raise RuntimeError(f'Daily evaluation provenance mismatch: {name}')
    recovery_runtime = json.loads(content["outputs/study_recovery_runtime.json"])
    bound_runtime = json.loads(content["outputs/study_runtime_benchmark.json"])
    if digest(content["outputs/study_runtime_benchmark.py"]) != bound_runtime["script_sha256"] or digest(content["outputs/energy_rank_bounds.py"]) != bound_runtime["reference_source_sha256"]:
        raise RuntimeError("Bound runtime benchmark does not match the final reference implementation")
    if digest(content["outputs/study_recovery_runtime.py"]) != recovery_runtime["script_sha256"]:
        raise RuntimeError("Recovery timing script hash mismatch")
    if digest(content["outputs/study_recovery.py"]) != recovery_runtime["recovery_source_sha256"]:
        raise RuntimeError("Recovery timing used a different recovery implementation")
    reconstruction = json.loads(content["outputs/manuscript_reconstruction_check.json"])
    if reconstruction["status"] != "passed" or not reconstruction["open_manuscript_unchanged"]:
        raise RuntimeError("Manuscript reconstruction did not pass")
    for name, expected in reconstruction["source_hashes"].items():
        if name == "outputs/revised_manuscript.tex":
            if (root / name).exists() and digest((root / name).read_bytes()) != expected:
                raise RuntimeError("Manuscript changed after reconstruction audit")
        elif name not in content or digest(content[name]) != expected:
            raise RuntimeError(f"Manuscript reconstruction source mismatch: {name}")
    for name, expected in reconstruction["source_result_hashes"].items():
        if "outputs/" + name not in content or digest(content["outputs/" + name]) != expected:
            raise RuntimeError(f"Manuscript reconstruction result mismatch: {name}")
    for name, expected in summary.get("protocol_supplements", {}).items():
        if digest(content["work/" + name]) != expected:
            raise RuntimeError(f"Protocol supplement hash mismatch: {name}")
    for name, expected in summary["artifacts"].items():
        blob = content.get("outputs/" + name)
        if blob is None or digest(blob) != expected["sha256"] or len(blob) != expected["bytes"]:
            raise RuntimeError(f"Final result hash/length mismatch: {name}")
    if set(summary.get("cohorts", {})) != {"household", "portugal", "blem_counters"}:
        raise RuntimeError("Expected all three study cohorts in final summary")
    if summary["cohorts"]["portugal"]["meters"] != 30 or summary["cohorts"]["blem_counters"]["meters"] != 3:
        raise RuntimeError("Expected thirty Portugal and three BLEM meters")
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if not args.build:
        for name in REQUIRED:
            path = ROOT / name
            print(f"{'present' if path.is_file() else 'MISSING'} {name}")
        print("Dry run only. Final completion signal is required before --build.")
        return
    content = validated_content(ROOT)
    # Validate the locally retained prediction/target records above, then omit
    # their bytes from the submission archive because dataset redistribution
    # terms for the derived BLEM hourly observations have not been established.
    del content["outputs/study_predictions.csv"]
    # Validate the full local results above; distribute only the explicit public
    # trace exports where detailed loss rows could reproduce omitted readings.
    for marker_name in ['study_period_archive_public_manifest.json','study_recovery_cases_public_manifest.json']:
        marker=json.loads(content['outputs/'+marker_name])
        for name,record in marker['public_files'].items():
            if digest(content['outputs/'+name])!=record['sha256']:
                raise RuntimeError('Public trace hash mismatch: '+name)
        for name,record in marker['omitted_files'].items():
            if digest(content['outputs/'+name])!=record['sha256']:
                raise RuntimeError('Omitted trace hash mismatch: '+name)
            del content['outputs/'+name]
    readme = ("Online Resource 1: Reproducibility Package\n"
              "Article: Auditing Machine-Learning Forecasts with Aggregate Targets: Exact Deterministic and Randomized Recovery\n"
              "Journal: Applied Intelligence\n"
              "Author: Jishan Kapoor, Independent Researcher, Toronto M4Y 1C9, Canada\n"
              "Corresponding email: kapoorjishan19@gmail.com\n"
              "Description: Source code, aggregate results, mathematical validation, protocols, and provenance for deterministic/randomized recovery and the natural precipitation audit.\n\n"
              "Start with outputs/REPRODUCE.txt. Preserve the outputs/ and work/\n"
              "directory structure. Raw source records, the complete hourly prediction/target\n"
              "archive, and the main TeX/PDF documents are excluded. Only explicit\n"
              "work/ theory and application fragments needed for reconstruction remain.\n"
              "CC BY 4.0 UCI worked-example\n"
              "original-review and new-consumer hourly targets/predictions are included with\n"
              "source attribution in REPRODUCE.txt. BLEM persistence, detailed loss\n"
              "traces and per-case recovery rows are omitted; cohort summaries remain.\n"
              "Public trace manifests identify every omitted file and its replacement.\n"
              "The default work/reproduce_final_revision.py command verifies the\n"
              "original period/interval results, every randomized energy case, the\n"
              "hard-budget policy sampler, the NOAA decoded-record excerpts,\n"
              "independent target-blind tie/holdout-policy consistency, and archived scaling\n"
              "records and independently checks the fresh-refit UCI forecast rows.\n"
              "The earlier review runner retains optional --rerun-scaling. The final\n"
              "runner offers --fresh-refit for isolated raw restoration and refitting. It\n"
              "then reconstructs the exact manuscript in isolation. Generated checks\n"
              "use separate copies and preserve archived generation reports.\n"
              "NOAA full GRIB caches and dependency directories are excluded; raw\n"
              "re-decoding is distinct from the supplied offline arithmetic replay.\n"
              "Regenerate complete targets with the supplied scripts.\n"
              "Verify every listed file against MANIFEST.sha256 before reproduction.\n")
    content["README.txt"] = readme.encode("utf-8")
    content["requirements.txt"] = content["outputs/requirements-study.txt"]
    prohibited=[name for name in content if name.endswith(('.pdf','.pkl')) or
                (name.endswith('.tex') and name not in ALLOWED_FRAGMENT_TEX)]
    if prohibited: raise RuntimeError('Prohibited package artifacts: '+', '.join(prohibited))
    manifest = "".join(f"{digest(blob)}  {name}\n" for name, blob in sorted(content.items()))
    content["MANIFEST.sha256"] = manifest.encode("utf-8")
    output = ROOT / "outputs/research_supplement.zip"
    temporary = output.with_suffix(".zip.building")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, blob in sorted(content.items()):
            archive.writestr(name, blob)
    # Reopen and verify actual archive bytes before exposing the final filename.
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
        for name, blob in content.items():
            if digest(archive.read(name)) != digest(blob):
                raise RuntimeError(f"Packaged byte mismatch: {name}")
    if temporary.stat().st_size > 500_000_000:
        raise RuntimeError("Supplement exceeds the chosen 500 MB packaging ceiling; retain traces in a separately named archive")
    temporary.replace(output)
    record = {"archive": output.name, "bytes": output.stat().st_size,
              "sha256": digest(output.read_bytes()), "files": len(content),
              "manifest": [{"path": name, "sha256": digest(blob), "bytes": len(blob)}
                           for name, blob in sorted(content.items())]}
    report = ROOT / "outputs/research_supplement_manifest.json"
    report.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({k: record[k] for k in ["archive", "bytes", "sha256", "files"]}, indent=2))


if __name__ == "__main__":
    main()
