"""Replay hardest-completion checks on the existing synthetic instance archive."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import platform
import time

import numpy as np
import scipy

from dual_certificate import ROOT, SOLVER_PATH, ORACLE_PATH, sha, solve_with_dual_completion, width_at

HERE = Path(__file__).resolve().parent
TOLERANCE = 1e-8


def instances():
    archive = json.loads((ROOT / "work/randomized_recovery_root/compact_verification.json").read_text())
    cases = []
    for record in archive["cases"]:
        cases.append({"case": "V%02d" % record["case"], "source": "archived_42_small_cases",
            "coefficients": record["coefficients"], "energies": record["energies"],
            "budget": record["budget"], "enumerate": True, "archived_value": record["compact"]["value"]})
    # Recreate the archived sharp-example coefficients using the exact original expression.
    for record in archive["sharp_examples"]:
        m, r = record["m"], record["retained"]
        c = np.concatenate([10 * j + np.linspace(0, 1, r) for j in range(m // r)])
        cases.append({"case": f"S{m}_{r}", "source": "archived_sharp_examples",
            "coefficients": [c.tolist()], "energies": [1.0], "budget": m - r,
            "enumerate": True, "archived_value": record["compact"]["value"]})
    scale = json.loads((ROOT / "work/randomized_scaling_review/instances.json").read_text())
    for record in scale["cases"]:
        cases.append({"case": record["case"], "source": "archived_28_scaling_cases",
            "coefficients": record["coefficients"], "energies": record["energies"],
            "budget": record["budget"], "enumerate": record["enumerated_eligible"]})
    additional = [
        ("E01", [[0, 1, 3, 4]], [1], 2),
        ("E02", [[-3, 2, 7]], [2], 0),
        ("E03", [[0, 1, 3, 4]], [1], 3),
        ("E04", [[2, 2, 2]], [3], 2),
        ("E05", [[0, 1, 3, 4], [7, 7], [3]], [1, 2, 4], 2),
        ("E06", [[], [0, 4], [5]], [0, 0, 2], 9),
    ]
    for name, cs, energies, budget in additional:
        cases.append({"case": name, "source": "declared_edge_cases",
            "coefficients": cs, "energies": energies, "budget": budget, "enumerate": True})
    return cases


def enumerate_all(coefficients, completion, budget):
    """Independent brute-force final sets, including redundant complete blocks.

    Unlike the compact program and historical pricing oracle, this check imposes
    no m_g-1 cap, and includes every cardinality from zero through the hard budget.
    It therefore also checks shorter terminal sets relevant to adaptive stopping.
    """
    n = sum(map(len, coefficients))
    best, argbest, count = math.inf, None, 0
    for k in range(min(n, budget) + 1):
        for q in itertools.combinations(range(n), k):
            value = width_at(coefficients, completion, q)
            count += 1
            if value < best:
                best, argbest = value, q
    return {"minimum": best, "minimizing_query": list(argbest), "sets_checked": count,
        "scope": "All coordinate subsets with cardinality <= hard budget, including redundant full-block queries."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=HERE / "results")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source_paths = [Path(__file__), HERE / "dual_certificate.py", SOLVER_PATH, ORACLE_PATH,
        ROOT / "work/randomized_recovery_root/compact_verification.json",
        ROOT / "work/randomized_scaling_review/instances.json"]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths}
    started = time.perf_counter()
    rows, records = [], []
    for case in instances():
        start = time.perf_counter()
        result = solve_with_dual_completion(case["coefficients"], case["energies"], case["budget"], TOLERANCE)
        if "archived_value" in case:
            gap = abs(result["primal_value"] - case["archived_value"])
            assert gap <= TOLERANCE * result["objective_scale"]
            result["archived_primal_absolute_gap"] = gap
        if case["enumerate"]:
            enumeration = enumerate_all(case["coefficients"], result["dual_completion"], case["budget"])
            gap = abs(enumeration["minimum"] - result["primal_value"])
            assert gap <= TOLERANCE * result["objective_scale"], (case["case"], gap)
            assert abs(enumeration["minimum"] - result["pricing_minimum"]) <= TOLERANCE * result["objective_scale"]
            result["enumeration"] = enumeration
            result["enumeration_primal_normalized_gap"] = gap / result["objective_scale"]
        result["total_verification_seconds"] = time.perf_counter() - start
        records.append({**case, "verification": result})
        row = {"case": case["case"], "source": case["source"], "blocks": len(case["coefficients"]),
            "coordinates": sum(map(len, case["coefficients"])), "budget": case["budget"],
            "primal": result["primal_value"], "pricing_minimum": result["pricing_minimum"],
            "pricing_absolute_gap": result["primal_pricing_absolute_gap"],
            "pricing_normalized_gap": result["primal_pricing_normalized_gap"],
            "enumerated_sets": result.get("enumeration", {}).get("sets_checked", 0),
            "enumeration_normalized_gap": result.get("enumeration_primal_normalized_gap", ""),
            "max_block_sum_error": max((abs(r["completed_sum"] - r["required_total"]) for r in result["mass_completion"]), default=0),
            "max_negative_clip_l1": max((r["negative_clip_l1"] for r in result["mass_completion"]), default=0),
            "max_roundoff_excess_removed": max((r["roundoff_excess_removed"] for r in result["mass_completion"]), default=0),
            "total_verification_seconds": result["total_verification_seconds"]}
        rows.append(row)
        print(f"{case['case']}: primal={row['primal']:.12g}, pricing={row['pricing_minimum']:.12g}, "
              f"gap={row['pricing_normalized_gap']:.3g}, enumerated={row['enumerated_sets']}", flush=True)
    for relative, expected in hashes.items():
        assert sha(ROOT / relative) == expected, "Source changed during verification: " + relative
    result_path = out / "dual_completions.json"
    result_path.write_text(json.dumps({"cases": records}, indent=2), encoding="utf-8")
    csv_path = out / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {"status": "PASS", "completed_utc": datetime.now(timezone.utc).isoformat(),
        "cases": len(records), "scaling_cases": sum(r["source"] == "archived_28_scaling_cases" for r in records),
        "enumerated_cases": sum(r["enumerate"] for r in records),
        "enumerated_final_sets": sum(r["enumerated_sets"] for r in rows),
        "scaling_cases_independently_enumerated": sum(r["source"] == "archived_28_scaling_cases" and r["enumerate"] for r in records),
        "max_primal_pricing_absolute_gap": max(r["pricing_absolute_gap"] for r in rows),
        "max_primal_pricing_normalized_gap": max(r["pricing_normalized_gap"] for r in rows),
        "max_enumeration_primal_normalized_gap": max(r["enumeration_normalized_gap"] for r in rows if r["enumeration_normalized_gap"] != ""),
        "max_completed_block_sum_absolute_error": max(r["max_block_sum_error"] for r in rows),
        "max_negative_clip_l1": max(r["max_negative_clip_l1"] for r in rows),
        "max_roundoff_excess_removed": max(r["max_roundoff_excess_removed"] for r in rows),
        "maximum_stationarity_absolute": max(r["verification"]["lp_diagnostics"]["stationarity_absolute"] for r in records),
        "maximum_primal_dual_absolute_gap": max(r["verification"]["primal_dual_absolute_gap"] for r in records),
        "tolerance": {"solver_primal_and_dual_feasibility": 1e-9,
            "validation": TOLERANCE, "objective_normalization": "max(1, initial worst-case width)",
            "block_mass_normalization": "max(1, residual block total)"},
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "platform": platform.platform()},
        "elapsed_seconds": time.perf_counter() - started, "source_sha256": hashes,
        "output_sha256": {p.name: sha(p) for p in [result_path, csv_path]},
        "scope": "Numerical optimality and hardest-record checks on existing synthetic instances plus declared edge cases. "
            "Not new empirical forecast results, formal interval arithmetic, or runtime scaling claims."}
    (out / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
