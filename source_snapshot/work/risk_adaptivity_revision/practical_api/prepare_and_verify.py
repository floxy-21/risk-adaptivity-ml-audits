"""Freeze two availability-selected public-data examples and verify the API.

Selection is independent of model errors or certificate outcomes: the first
Portugal six-hour/contiguous/1103/exact-six-hour-total archived snapshot with
copies, and the first without copies, in the existing saved row ordering.
"""
from __future__ import annotations

import csv
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import numpy as np
import scipy
from scipy.optimize import linprog

from audit_api import ROOT, REFERENCE_API, audit_snapshot

HERE = Path(__file__).resolve().parent
MODELS = ("daily", "ridge", "hist_gradient_boosting", "mlp")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_links():
    chosen = {}
    with gzip.open(ROOT / "outputs/study_period_archive_public_links.csv.gz", "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            if (row["cohort"] == "portugal" and row["gap_hours"] == "6" and row["pattern"] == "contiguous"
                    and row["seed"] == "1103" and row["block_hours"] == "6" and float(row["total_tolerance"]) == 0
                    and row["regime"] == "saved_forecast_archive_closed"):
                kind = "copies_available" if int(row["archive_copy_mask"]) else "copies_absent"
                chosen.setdefault(kind, row)
                if len(chosen) == 2:
                    return chosen
    raise RuntimeError("Both declared availability examples were not found")


def prepare():
    chosen = select_links()
    needed = {row["aggregate_snapshot_id"] for row in chosen.values()}
    aggregates = {}
    with gzip.open(ROOT / "outputs/study_period_archive_public_aggregates.csv.gz", "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["aggregate_snapshot_id"] in needed:
                aggregates[row["aggregate_snapshot_id"]] = row
                if len(aggregates) == len(needed):
                    break
    meters = {(r["cohort"], r["meter"]) for r in chosen.values()}
    rows = []
    with (ROOT / "outputs/review_frozen_forecasts.csv").open(newline="") as stream:
        for source_row, row in enumerate(csv.DictReader(stream)):
            if (row["cohort"], row["meter"]) in meters:
                rows.append({**row, "source_row": source_row})
    snapshots, references = {}, {}
    for kind, link in chosen.items():
        meter_rows = [r for r in rows if r["cohort"] == link["cohort"] and r["meter"] == link["meter"]]
        day_rows = sorted([r for r in meter_rows if r["timestamp"][:10] == link["day"]], key=lambda r: r["timestamp"])
        assert len(day_rows) == 24
        mask = int(link["initial_missing_mask"])
        observed = [None if mask & (1 << i) else float(r["truth_kwh"]) for i, r in enumerate(day_rows)]
        aggregate = aggregates[link["aggregate_snapshot_id"]]
        totals = json.loads(aggregate["central_totals"])
        snapshots[kind] = {"schema": "exact_total_archive_audit_v1", "cohort": link["cohort"],
            "meter": link["meter"], "day": link["day"], "timestamps": [r["timestamp"] for r in day_rows],
            "predictions": {m: [float(r[m]) for r in day_rows] for m in MODELS}, "observed": observed,
            "totals": [{"indices": list(range(6*g, 6*g+6)), "total": total,
                "source_snapshot_id": link["aggregate_snapshot_id"], "source_block_index": g} for g, total in enumerate(totals)],
            "archive_persistence_rows": [{"source_row": r["source_row"],
                "forecast_target_timestamp": r["timestamp"], "daily": float(r["daily"])} for r in meter_rows],
            "access_rule": "All saved test-period daily-persistence forecast rows for this meter are permitted. "
                "Direct day-lag24 copies and exact aggregate deductions are applied before bounding. "
                "This is the existing retrospective benchmark archive; no production arrival timestamps are asserted.",
            "provenance": {"selection": "First matching availability class in the saved link file, independent of model errors or resulting bounds.",
                "aggregate_kind": "Existing benchmark total manufactured from complete historical public targets, not a naturally observed surviving physical counter.",
                "forecast_source": "outputs/review_frozen_forecasts.csv", "forecast_source_rows": [r["source_row"] for r in day_rows],
                "mask_source": "outputs/study_period_archive_public_links.csv.gz", "original_link": link,
                "totals_source": "outputs/study_period_archive_public_aggregates.csv.gz"}}
        references[kind] = {"truth": [float(r["truth_kwh"]) for r in day_rows], "original_link": link}
    return snapshots, references


def validate(snapshot, result, reference):
    truth = reference["truth"]
    errors = {"maximum_known_coordinate_error": 0.0, "maximum_total_error": 0.0,
              "maximum_endpoint_objective_error": 0.0, "maximum_independent_lp_error": 0.0,
              "maximum_reference_enclosure_error": 0.0, "wrong_certificates": 0}
    n = len(truth)
    eq = []
    rhs = []
    for block in snapshot["totals"]:
        row = np.zeros(n)
        row[block["indices"]] = 1
        eq.append(row)
        rhs.append(block["total"])
    for i, y in enumerate(result["closed_observed"]):
        if y is not None:
            row = np.zeros(n)
            row[i] = 1
            eq.append(row)
            rhs.append(y)
    lp_count = 0
    for pair in result["pairwise_decisions"]:
        a = np.array(snapshot["predictions"][pair["model_a"]])
        b = np.array(snapshot["predictions"][pair["model_b"]])
        coefficient = 2*(b-a)/n
        constant = math.fsum((float(x)-float(z))*(float(x)+float(z))/n for x, z in zip(a,b))
        for endpoint, value in (("lower_completion", "lower"), ("upper_completion", "upper")):
            witness = pair[endpoint]
            assert len(witness) == n and min(witness) >= -1e-12
            errors["maximum_known_coordinate_error"] = max(errors["maximum_known_coordinate_error"],
                max((abs(witness[i]-y) for i,y in enumerate(result["closed_observed"]) if y is not None), default=0))
            errors["maximum_total_error"] = max(errors["maximum_total_error"],
                max(abs(math.fsum(witness[i] for i in block["indices"])-block["total"]) for block in snapshot["totals"]))
            objective = math.fsum((float(x)-float(z))*((float(x)-y)+(float(z)-y))/n for x,z,y in zip(a,b,witness))
            errors["maximum_endpoint_objective_error"] = max(errors["maximum_endpoint_objective_error"], abs(objective-pair[value]))
            sign = 1 if value == "lower" else -1
            lp = linprog(sign*coefficient, A_eq=np.asarray(eq), b_eq=np.asarray(rhs), bounds=(0,None), method="highs",
                         options={"primal_feasibility_tolerance":1e-9,"dual_feasibility_tolerance":1e-9})
            assert lp.success, lp.message
            independent = constant + sign*float(lp.fun)
            errors["maximum_independent_lp_error"] = max(errors["maximum_independent_lp_error"], abs(independent-pair[value]))
            lp_count += 1
        actual = math.fsum((float(x)-float(z))*((float(x)-y)+(float(z)-y))/n for x,z,y in zip(a,b,truth))
        errors["maximum_reference_enclosure_error"] = max(errors["maximum_reference_enclosure_error"], pair["lower"]-actual, actual-pair["upper"], 0)
        if pair["certified_lower_loss_model"]:
            expected = pair["model_a"] if actual < 0 else pair["model_b"] if actual > 0 else None
            errors["wrong_certificates"] += int(pair["certified_lower_loss_model"] != expected)
    for entry in result["free_copy_trace"]:
        assert entry["value"] == truth[entry["target_index"]]
    link = reference["original_link"]
    assert sum(1 << entry["target_index"] for entry in result["free_copy_trace"]) == int(link["archive_copy_mask"])
    assert sum(1 << entry["target_index"] for entry in result["aggregate_deductions"]) == int(link["aggregate_deduced_mask"])
    scale = max(1.0, *(abs(v) for pair in result["pairwise_decisions"] for v in (pair["lower"],pair["upper"])), *(b["total"] for b in snapshot["totals"]))
    assert max(errors.values()) <= 2e-8*scale, errors
    leaked = dict(snapshot, hidden_truth=truth)
    try:
        audit_snapshot(leaked)
    except ValueError:
        pass
    else:
        raise AssertionError("API accepted a hidden-reference field")
    return {**errors, "independent_endpoint_LPs": lp_count, "hidden_truth_field_rejected": True,
        "absolute_acceptance_tolerance": 2e-8*scale}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    snapshots, references = prepare()
    outputs = []
    for kind, snapshot in snapshots.items():
        input_path = out / (kind + "_input.json")
        input_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        result = audit_snapshot(json.loads(input_path.read_text()))
        checked = validate(snapshot, result, references[kind])
        output_path = out / (kind + "_output.json")
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        outputs.append({"example": kind, "meter": result["meter"], "day": result["day"],
            "input_sha256": sha(input_path), "output_sha256": sha(output_path),
            "free_copy_count": result["free_copy_count"], "remaining_missing_count": result["remaining_missing_count"],
            "allowed_rankings": sum(r["action"] == "ALLOW_RANKING" for r in result["pairwise_decisions"]),
            "held_rankings": sum(r["action"] == "HOLD_RANKING" for r in result["pairwise_decisions"]),
            "certified_best_model": result["certified_best_model"], "paid_queries": result["paid_queries"],
            "bound_and_validation_seconds": result["bound_and_validation_seconds"], "checks": checked})
    deps = [Path(__file__), HERE/"audit_api.py", HERE/"run_example.py", REFERENCE_API,
        ROOT/"outputs/review_frozen_forecasts.csv", ROOT/"outputs/study_period_archive_public_links.csv.gz",
        ROOT/"outputs/study_period_archive_public_aggregates.csv.gz"]
    report = {"status":"PASS", "examples": outputs, "python":platform.python_version(),
        "numpy":np.__version__, "scipy":scipy.__version__, "elapsed_seconds":time.perf_counter()-started,
        "source_sha256":{p.relative_to(ROOT).as_posix():sha(p) for p in deps},
        "scope":"Two availability-selected executable historical daily examples, not a new empirical performance estimate. "
            "No forecasting model refit, hidden-target input to the evaluator, paid retrieval, or production cost measurement."}
    (out/"verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
