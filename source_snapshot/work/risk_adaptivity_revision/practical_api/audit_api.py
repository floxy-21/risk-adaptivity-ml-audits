"""A zero-query gate for archived forecast comparisons, with endpoint witnesses.

The evaluator receives predictions, surviving targets, declared exact totals,
and permitted saved day-lag persistence rows. Hidden reference truth is not an
input. Numerical outputs use the existing standard-library reference API.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import importlib.util
import itertools
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
REFERENCE_API = ROOT / "outputs/energy_rank_bounds.py"
spec = importlib.util.spec_from_file_location("practical_energy_rank_bounds", REFERENCE_API)
reference = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reference
spec.loader.exec_module(reference)


def audit_snapshot(snapshot):
    allowed = {"schema", "cohort", "meter", "day", "timestamps", "predictions", "observed",
               "totals", "archive_persistence_rows", "access_rule", "provenance"}
    if set(snapshot) != allowed or snapshot["schema"] != "exact_total_archive_audit_v1":
        raise ValueError("Expected evaluator-only snapshot schema; reference truth is not accepted")
    started = time.perf_counter()
    timestamps = [datetime.fromisoformat(t) for t in snapshot["timestamps"]]
    observed = [None if v is None else float(v) for v in snapshot["observed"]]
    n = len(observed)
    if not n or len(timestamps) != n or len(set(timestamps)) != n:
        raise ValueError("Expected one unique timestamp per target")
    if any(v is not None and (not math.isfinite(v) or v < 0) for v in observed):
        raise ValueError("Surviving targets must be finite and nonnegative")
    if len(snapshot["predictions"]) < 2:
        raise ValueError("At least two saved prediction vectors are required")
    for pred in snapshot["predictions"].values():
        if len(pred) != n or any(not math.isfinite(float(v)) for v in pred):
            raise ValueError("Forecast vectors must be finite and match scheduled targets")

    lookup = {}
    for row in snapshot["archive_persistence_rows"]:
        if set(row) != {"source_row", "forecast_target_timestamp", "daily"}:
            raise ValueError("Persistence rows accept source identity, timestamp and daily forecast only")
        timestamp = datetime.fromisoformat(row["forecast_target_timestamp"])
        if timestamp in lookup or not math.isfinite(row["daily"]) or row["daily"] < 0:
            raise ValueError("Invalid or duplicate saved persistence row")
        lookup[timestamp] = row
    copied = []
    for i, timestamp in enumerate(timestamps):
        if observed[i] is None and timestamp + timedelta(days=1) in lookup:
            source = lookup[timestamp + timedelta(days=1)]
            observed[i] = float(source["daily"])
            copied.append({"target_index": i, "target_timestamp": snapshot["timestamps"][i],
                           "source_row": source["source_row"],
                           "source_forecast_target_timestamp": source["forecast_target_timestamp"],
                           "source_column": "daily", "value": observed[i],
                           "identity": "saved_daily_prediction[t+24h] == target[t]"})

    blocks = []
    covered = set()
    deductions = []
    arithmetic = []
    for block in snapshot["totals"]:
        if set(block) != {"indices", "total", "source_snapshot_id", "source_block_index"}:
            raise ValueError("Exact total block schema mismatch")
        ids = block["indices"]
        if not ids or any(type(i) is not int or not 0 <= i < n for i in ids) or len(ids) != len(set(ids)) or covered.intersection(ids):
            raise ValueError("Total blocks must have valid distinct nonoverlapping indices")
        covered.update(ids)
        total = float(block["total"])
        if not math.isfinite(total) or total < 0:
            raise ValueError("Invalid exact total")
        missing = [i for i in ids if observed[i] is None]
        known_sum = math.fsum(observed[i] for i in ids if observed[i] is not None)
        residual = total - known_sum
        tolerance = 1e-10 * max(1.0, total, abs(known_sum))
        if residual < -tolerance or (not missing and abs(residual) > tolerance):
            raise ValueError("Declared aggregate conflicts with observed or reconstructed readings")
        arithmetic.append({"source_block_index": block["source_block_index"],
                           "known_sum": known_sum, "supplied_total": total,
                           "raw_residual": residual, "numerical_tolerance": tolerance})
        if missing:
            if residual < 0:
                # Only a recorded arithmetic-scale negative is removed, never a material inconsistency.
                residual = 0.0
            if len(missing) == 1 or residual == 0:
                for i in missing:
                    observed[i] = residual if len(missing) == 1 else 0.0
                    deductions.append({"target_index": i, "value": observed[i],
                        "source_snapshot_id": block["source_snapshot_id"],
                        "source_block_index": block["source_block_index"],
                        "reason": "exact singleton residual" if len(missing) == 1 else "nonnegative zero residual"})
            else:
                # Removing fixed contributions is algebraically equivalent to the original exact total.
                blocks.append(reference.EnergyBlock(missing, residual))
    if any(v is None and i not in covered for i, v in enumerate(observed)):
        raise ValueError("Every unresolved target requires a declared aggregate")

    pairs = []
    for name_a, name_b in itertools.combinations(snapshot["predictions"], 2):
        result = reference.bound_pairwise_mse(snapshot["predictions"][name_a], snapshot["predictions"][name_b],
            observed, blocks, numerical_tolerance=1e-9)
        winner = name_a if result.winner == "A" else name_b if result.winner == "B" else None
        pairs.append({"model_a": name_a, "model_b": name_b, "lower": result.lower, "upper": result.upper,
            "numerical_margin": result.numerical_margin, "action": "ALLOW_RANKING" if winner else "HOLD_RANKING",
            "certified_lower_loss_model": winner, "lower_completion": list(result.lower_completion),
            "upper_completion": list(result.upper_completion)})
    winners = [model for model in snapshot["predictions"] if all(
        pair["certified_lower_loss_model"] == model for pair in pairs if model in (pair["model_a"], pair["model_b"]))]
    return {"schema": "exact_total_archive_audit_output_v1", "cohort": snapshot["cohort"],
        "meter": snapshot["meter"], "day": snapshot["day"], "scheduled_target_denominator": n,
        "paid_queries": 0, "initial_missing_count": sum(v is None for v in snapshot["observed"]),
        "free_copy_count": len(copied), "aggregate_deduction_count": len(deductions),
        "remaining_missing_count": sum(v is None for v in observed), "closed_observed": observed,
        "free_copy_trace": copied, "aggregate_deductions": deductions, "residual_arithmetic": arithmetic,
        "pairwise_decisions": pairs, "certified_best_model": winners[0] if len(winners) == 1 else None,
        "bound_and_validation_seconds": time.perf_counter() - started,
        "scope": "A finite-record numerical audit gate. ALLOW_RANKING certifies the displayed pair under the declared constraints; "
            "HOLD_RANKING withholds a guarantee. Neither is a production deployment decision or a future-accuracy guarantee."}
