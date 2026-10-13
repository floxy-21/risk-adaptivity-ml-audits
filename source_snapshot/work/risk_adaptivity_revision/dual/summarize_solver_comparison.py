"""Compare the existing paired scaling measurements without rerunning them."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=HERE / "solver_comparison")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / "work/randomized_scaling_review/results.csv"
    manifest_path = ROOT / "work/randomized_scaling_review/instances.json"
    raw_path = ROOT / "work/randomized_scaling_review/results.json"
    manifest = json.loads(manifest_path.read_text())
    raw = json.loads(raw_path.read_text())
    with source.open(newline="", encoding="utf-8") as stream:
        input_rows = list(csv.DictReader(stream))
    by_key = {(r["case"], r["method"]): r for r in input_rows}
    raw_by_key = {(r["case"], r["method"]): r for r in raw["rows"]}
    paired = []
    for case in manifest["cases"]:
        if not case["enumerated_eligible"]:
            continue
        c, f = [by_key[(case["case"], method)] for method in ("compact", "enumerated")]
        assert c["status"] == f["status"] == "success"
        # Check that the CSV values agree with the unflattened saved reports.
        for method, row in (("compact", c), ("enumerated", f)):
            unflattened = raw_by_key[(case["case"], method)]
            for key in ("value", "method_seconds"):
                assert float(row[key]) == float(unflattened[key]), (case["case"], method, key)
            peak = max(unflattened.get("peak_working_set_bytes", 0), unflattened.get("parent_observed_peak_bytes", 0)) / 2**20
            assert float(row["peak_working_set_mib"]) == peak
            assert int(row["variables"]) == int(unflattened["lp_checks"][0]["variables"])
        ctime, ftime = float(c["method_seconds"]), float(f["method_seconds"])
        paired.append({"case": case["case"], "blocks": case["blocks"],
            "coordinates_per_block": case["coordinates_per_block"], "budget": case["budget"],
            "profile": case["profile"], "enumerated_batches": case["batches"],
            "compact_variables": int(c["variables"]), "finite_variables": int(f["variables"]),
            "compact_method_seconds": ctime, "finite_method_seconds": ftime,
            "finite_over_compact_method_time": ftime / ctime,
            "compact_solver_seconds": float(c["solver_seconds"]), "finite_solver_seconds": float(f["solver_seconds"]),
            "compact_peak_process_mib": float(c["peak_working_set_mib"]), "finite_peak_process_mib": float(f["peak_working_set_mib"]),
            "compact_objective": float(c["value"]), "finite_objective": float(f["value"]),
            "normalized_objective_gap": float(c["finite_objective_discrepancy_normalized"]),
            "faster_recorded_method": "compact" if ctime < ftime else "finite" if ftime < ctime else "equal"})
    assert len(paired) == 12
    csv_path = out / "paired_solver_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(paired[0]))
        writer.writeheader()
        writer.writerows(paired)
    lines = [r"\begin{table}[htbp]", r"\centering\small",
        r"\caption{Paired saved solver measurements on all 12 instances eligible for finite enumeration. Within each C/F cell, C is compact and F is finite-game enumeration. $(G,m,B)$ gives blocks, coordinates per block, and budget; D and T denote distinct and tied coefficient profiles. Method times include construction and solving; compact also compiles its executable policy. Peak memory is absolute process working-set memory, including the runtime. Each entry is one archived measurement, not a repeated-run timing estimate.}",
        r"\label{tab:risk_paired_solvers}", r"\begin{tabular}{llrrr}", r"\toprule",
        r"Case & $(G,m,B)$/profile & LP variables C/F & Time C/F (ms) & Memory C/F (MiB)\\", r"\midrule"]
    for row in paired:
        profile = "D" if row["profile"].startswith("distinct") else "T"
        lines.append(f"{row['case']} & $({row['blocks']},{row['coordinates_per_block']},{row['budget']})$/{profile} & "
            f"{row['compact_variables']}/{row['finite_variables']} & "
            f"{1000*row['compact_method_seconds']:.2f}/{1000*row['finite_method_seconds']:.2f} & "
            f"{row['compact_peak_process_mib']:.2f}/{row['finite_peak_process_mib']:.2f} " + r"\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    tex_path = out / "paired_solver_table.tex"
    tex_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {"status": "PASS", "pairs": len(paired),
        "compact_faster_count": sum(r["faster_recorded_method"] == "compact" for r in paired),
        "finite_faster_count": sum(r["faster_recorded_method"] == "finite" for r in paired),
        "compact_fewer_variables_count": sum(r["compact_variables"] < r["finite_variables"] for r in paired),
        "compact_lower_peak_process_memory_count": sum(r["compact_peak_process_mib"] < r["finite_peak_process_mib"] for r in paired),
        "median_finite_over_compact_method_time": statistics.median(r["finite_over_compact_method_time"] for r in paired),
        "maximum_objective_discrepancy_normalized": max(r["normalized_objective_gap"] for r in paired),
        "measurement_scope": "Existing single-run measurements, no new timing run. Method implementations perform different post-solve work: compact compiles an executable sampling policy. Absolute peak process working set includes Python and dependencies; not incremental solver memory.",
        "source_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in [Path(__file__), source, manifest_path, raw_path]},
        "output_sha256": {p.name: sha(p) for p in [csv_path, tex_path]}}
    (out / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
