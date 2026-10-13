"""Verify manuscript reconstruction in an isolated work directory.

The open manuscript is read only. No PDF is compiled or tab opened. A temporary
source tree is retained under work/ for inspection; its TeX is not a deliverable.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from revision_extension_inputs import extension_paths, validate_extension_inputs

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = ROOT / "outputs/revised_manuscript.tex"
    if not target.exists():
        raise FileNotFoundError("Reconstruct the manuscript with work/build_final_manuscript.py first")
    original_hash = digest(target)
    validate_extension_inputs(ROOT)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stage = (ROOT / "work" / f"data_reconstruction_check_{stamp}").resolve()
    if not stage.is_relative_to((ROOT / "work").resolve()):
        raise ValueError("Invalid reconstruction workspace")
    (stage / "work").mkdir(parents=True, exist_ok=False)
    (stage / "outputs").mkdir()
    # The composer consumes final result JSONs and checks three source CSV hashes.
    # Copy all completed study JSONs/CSVs so later additive analyses remain usable.
    omitted_names={'study_predictions.csv','study_recovery_cases.csv'}
    public_manifest=json.loads((ROOT/'outputs/study_period_archive_public_manifest.json').read_text())
    omitted_names.update(public_manifest['omitted_files'])
    inputs = sorted((ROOT / "outputs").glob("study_*.json"))
    inputs += [p for p in sorted((ROOT / "outputs").glob("study_*.csv"))
               if p.name not in omitted_names]
    inputs += [p for p in sorted((ROOT/'outputs').glob('study_period_archive_*.csv.gz'))
               if p.name not in omitted_names]
    inputs += [ROOT / "outputs/manuscript_result_tables.json"]
    inputs += [ROOT / "outputs/test_recovery_adaptivity.json"]
    inputs += [ROOT / "outputs/ai_recovery_analysis.json"]
    inputs += [ROOT / "outputs/recovery_diagnostics.json"]
    inputs += [ROOT / "outputs/frozen_forecasts.json"]
    inputs += [ROOT / "outputs/frozen_forecasts.csv"]
    inputs += [ROOT / "outputs/study_archive_access.py"]
    inputs += [ROOT / "outputs/review_raw_reconstruction.json"]
    inputs += [ROOT / "outputs/review_frozen_forecasts.json"]
    inputs += [ROOT / "outputs/review_frozen_forecasts.csv"]
    inputs += [ROOT / "outputs/study_holdout_consumers.py"]
    holdout = json.loads((ROOT / 'outputs/study_holdout_consumers.json').read_text(encoding='utf-8'))
    inputs += [ROOT / 'outputs' / name for name in holdout['selection']['helper_hashes']
               if ROOT / 'outputs' / name not in inputs]
    # Review extensions verify their dependency hashes during composition,
    # including source scripts as well as aggregate numerical files.
    for report_path in list(inputs):
        if report_path.suffix != ".json":
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            continue
        for name in report.get("source_hashes", {}):
            if name not in omitted_names:
                dependency = ROOT / "outputs" / name
                if dependency not in inputs:
                    inputs.append(dependency)
    for source in inputs:
        shutil.copy2(source, stage / "outputs" / source.name)
    for name in ["compose_final_sections.py", "build_final_manuscript.py", "final_sections.json",
                 "prediction_archive_omission.json", "compose_review_sections.py",
                 "compose_archive_sections.py", "archive_access_protocol.txt",
                 "compose_interval_sections.py", "compose_holdout_sections.py",
                 "holdout_consumers_protocol.txt", "verify_holdout_replication.py",
                 "compose_period_archive_sections.py", "period_archive_protocol.txt",
                 "period_archive_bugfix_amendment.txt", "verify_period_archive_mask_source.py",
                 "verify_period_archive.py", "compose_interval_trace_sections.py",
                 "interval_trace_protocol.txt", "verify_interval_trace.py", "data_prepare_blem.py"]:
        shutil.copy2(ROOT / "work" / name, stage / "work" / name)
    extension_inputs=extension_paths(ROOT)
    for relative in extension_inputs:
        destination=stage/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,destination)
    builder = stage / "work/build_final_manuscript.py"
    composer = stage / "work/compose_final_sections.py"
    subprocess.run([sys.executable, str(builder)], check=True, cwd=stage, capture_output=True, text=True)
    reconstructed = stage / "outputs/revised_manuscript.tex"
    saved_sections_hash = digest(stage / "work/final_sections.json")
    archived_reconstruction_hash = digest(reconstructed)
    if archived_reconstruction_hash != original_hash:
        raise AssertionError("Archived sections/template do not reconstruct the current manuscript exactly")
    composition = subprocess.run([sys.executable, str(composer)], check=False, cwd=stage, capture_output=True, text=True)
    if composition.returncode:
        print(composition.stdout, composition.stderr)
        composition.check_returncode()
    fresh_sections_hash = digest(stage / "work/final_sections.json")
    if fresh_sections_hash != saved_sections_hash:
        raise AssertionError("Fresh composition differs from archived final_sections.json")
    subprocess.run([sys.executable, str(builder)], check=True, cwd=stage, capture_output=True, text=True)
    fresh_reconstruction_hash = digest(reconstructed)
    if fresh_reconstruction_hash != original_hash:
        raise AssertionError("Freshly composed sections do not reconstruct the manuscript exactly")
    if digest(target) != original_hash:
        raise AssertionError("Open manuscript changed during reconstruction audit")
    hashes = {"outputs/revised_manuscript.tex": original_hash,
              "work/final_sections.json": saved_sections_hash,
              "work/compose_final_sections.py": digest(ROOT / "work/compose_final_sections.py"),
              "work/build_final_manuscript.py": digest(ROOT / "work/build_final_manuscript.py"),
              "work/check_manuscript_reconstruction.py": digest(Path(__file__))}
    hashes["work/prediction_archive_omission.json"] = digest(ROOT / "work/prediction_archive_omission.json")
    hashes["work/compose_review_sections.py"] = digest(ROOT / "work/compose_review_sections.py")
    hashes["work/compose_archive_sections.py"] = digest(ROOT / "work/compose_archive_sections.py")
    hashes["work/archive_access_protocol.txt"] = digest(ROOT / "work/archive_access_protocol.txt")
    hashes["work/compose_interval_sections.py"] = digest(ROOT / "work/compose_interval_sections.py")
    hashes["work/compose_holdout_sections.py"] = digest(ROOT / "work/compose_holdout_sections.py")
    hashes["work/holdout_consumers_protocol.txt"] = digest(ROOT / "work/holdout_consumers_protocol.txt")
    hashes["work/verify_holdout_replication.py"] = digest(ROOT / "work/verify_holdout_replication.py")
    for name in ['compose_period_archive_sections.py','period_archive_protocol.txt','verify_period_archive.py',
                 'period_archive_bugfix_amendment.txt','verify_period_archive_mask_source.py',
                 'compose_interval_trace_sections.py','interval_trace_protocol.txt','verify_interval_trace.py']:
        hashes['work/'+name]=digest(ROOT/'work'/name)
    for relative in extension_inputs:
        hashes[relative]=digest(ROOT/relative)
    record = {"status": "passed", "completed_utc": datetime.now(timezone.utc).isoformat(),
              "archived_sections_exact_bytes": True, "fresh_sections_exact_bytes": True,
              "fresh_manuscript_exact_bytes": True, "open_manuscript_unchanged": True,
              "source_hashes": hashes, "source_result_hashes": {p.name: digest(p) for p in inputs},
              "temporary_directory": stage.relative_to(ROOT).as_posix(),
              "compiler_used": False, "composer_stdout": composition.stdout.strip()}
    (ROOT / "outputs/manuscript_reconstruction_check.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "manuscript_sha256": original_hash,
                      "checks": "archived and freshly composed exact byte reconstruction; source unchanged"}, indent=2))


if __name__ == "__main__":
    main()
