"""Read-only, full-grid cross-tab of the two saved whole-period certificates.

No forecast fitting, new masking, policy selection, or endpoint regeneration.
Run from any working directory: python work/certificate_grid_review/summarize_certificates.py
Use --source public for the redistributable Portugal/household endpoint files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
KEYS = ["cohort", "meter", "model_a", "model_b", "gap_hours", "pattern", "seed",
        "block_hours", "total_tolerance", "regime"]
GRID = ["cohort", "regime", "gap_hours", "pattern", "block_hours", "total_tolerance"]
MATCHED = ["days", "full_target_denominator", "observed_target_denominator", "true_mean_gap",
           "normalization_scale", "originally_missing_coordinates", "free_archive_coordinates",
           "aggregate_determined_coordinates", "fully_known_days"]
CATEGORIES = ["both", "paired_only", "neither", "separate_only"]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def summarize(frame, groups):
    result = frame.groupby(groups, as_index=False, sort=True).agg(
        comparisons=("both", "size"), both=("both", "sum"), paired_only=("paired_only", "sum"),
        neither=("neither", "sum"), separate_only=("separate_only", "sum"),
        paired_wrong=("paired_wrong", "sum"), separate_wrong=("separate_wrong", "sum"),
        paired_mean_normalized_width=("paired_width", "mean"),
        separate_mean_normalized_width=("separate_width", "mean"))
    result["paired_certified"] = result.both + result.paired_only
    result["separate_certified"] = result.both + result.separate_only
    result["paired_coverage_percent"] = 100 * result.paired_certified / result.comparisons
    result["separate_coverage_percent"] = 100 * result.separate_certified / result.comparisons
    result["paired_only_percentage_points"] = 100 * result.paired_only / result.comparisons
    assert (result[CATEGORIES].sum(axis=1) == result.comparisons).all()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["auto", "full", "public"], default="public")
    parser.add_argument("--input-root", type=Path, default=ROOT,
                        help="Root containing saved outputs/ and work/ (e.g. the raw-regeneration stage)")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    input_root = args.input_root.resolve()
    scope = args.source
    if scope == "auto":
        scope = "full" if (input_root / "outputs/study_period_archive_cases.csv").exists() else "public"
    name = "study_period_archive_cases.csv" if scope == "full" else "study_period_archive_public_cases.csv"
    source = input_root / "outputs" / name
    out = args.output_dir or HERE / ("replay_" + scope)
    out.mkdir(parents=True, exist_ok=True)
    provenance = [source, input_root / "outputs/study_period_archive.py", input_root / "work/period_archive_protocol.txt",
                  input_root / "outputs/study_period_archive_manifest.json",
                  input_root / "outputs/study_period_archive_public_manifest.json"]
    hashes = {str(p.relative_to(input_root)).replace("\\", "/"): digest(p) for p in provenance}
    public_manifest = json.loads(provenance[-1].read_text(encoding="utf-8"))
    expected_hash = (public_manifest["omitted_files"][name]["sha256"] if scope == "full"
                     else public_manifest["public_files"][name]["sha256"])
    assert digest(source) == expected_hash, "Saved endpoint file differs from its original export manifest"
    data = pd.read_csv(source)
    endpoints = data[data.method.isin(["paired_bounds", "individual_bounds"])].copy()
    assert not endpoints.duplicated(KEYS + ["method"]).any()
    paired = endpoints[endpoints.method == "paired_bounds"].set_index(KEYS).sort_index()
    separate = endpoints[endpoints.method == "individual_bounds"].set_index(KEYS).sort_index()
    assert paired.index.equals(separate.index), "Not a one-to-one matched scenario comparison"
    for field in MATCHED:
        np.testing.assert_array_equal(paired[field].to_numpy(), separate[field].to_numpy(), err_msg=field)
    expected_meters = {"household": 1, "portugal": 30}
    if scope == "full":
        expected_meters["blem_counters"] = 3
    assert paired.reset_index().groupby("cohort").meter.nunique().to_dict() == expected_meters
    assert len(paired) == sum(expected_meters.values()) * 6 * 3 * 3 * 3 * 2 * 3 * 2
    matched = paired.reset_index()[KEYS + ["true_mean_gap"]].copy()
    allowed = {"gap_hours": {2, 6, 12}, "pattern": {"contiguous", "scattered", "high_demand"},
               "seed": {1103, 2207, 3301}, "block_hours": {6, 24},
               "total_tolerance": {0.0, 0.01, 0.05},
               "regime": {"restricted_daily_product_closed", "saved_forecast_archive_closed"}}
    for key, choices in allowed.items():
        assert set(matched[key]) == choices
    models = {"daily", "ridge", "hist_gradient_boosting", "mlp"}
    assert set(matched.model_a) | set(matched.model_b) == models
    model_pairs = matched[["model_a", "model_b"]].drop_duplicates()
    assert len(model_pairs) == 6
    assert len({frozenset(pair) for pair in model_pairs.itertuples(index=False, name=None)}) == 6
    assert (model_pairs.model_a != model_pairs.model_b).all()
    # Distinct keys, allowed factor levels and the exact Cartesian-product count
    # for EVERY meter/pair together establish complete inclusion, not just a total.
    cells_per_meter_pair = 3 * 3 * 3 * 2 * 3 * 2
    assert (matched.groupby(["cohort", "meter", "model_a", "model_b"]).size() == cells_per_meter_pair).all()
    assert (matched.groupby(["cohort", "meter"]).size() == 6 * cells_per_meter_pair).all()
    values = {}
    for label, frame in [("paired", paired), ("separate", separate)]:
        lo = frame.mean_lower_or_point.to_numpy()
        hi = frame.mean_upper_or_point.to_numpy()
        truth = frame.true_mean_gap.to_numpy()
        assert np.isfinite(np.concatenate([lo, hi, truth])).all()
        # The exact original decision rule, including its endpoint-scaled margin.
        margin = 1e-9 * np.maximum(1.0, np.maximum(np.abs(lo), np.abs(hi)))
        decision = np.where(lo > margin, 1, np.where(hi < -margin, -1, 0))
        np.testing.assert_array_equal(decision, frame.decision.to_numpy())
        enclosure_tolerance = 1e-8 * np.maximum(1.0, np.abs(truth))
        assert np.all(lo <= hi + enclosure_tolerance)
        assert np.all(lo <= truth + enclosure_tolerance)
        assert np.all(hi >= truth - enclosure_tolerance)
        wrong = (decision != 0) & (decision != np.sign(truth))
        assert not wrong.any()
        matched[label + "_wrong"] = wrong.astype(int)
        matched[label + "_width"] = frame.normalized_width.to_numpy()
        values[label] = (lo, hi, decision)
    plo, phi, pdec = values["paired"]
    slo, shi, sdec = values["separate"]
    containment_tol = 1e-8 * np.maximum(1.0, np.max(np.abs(np.vstack([plo, phi, slo, shi])), axis=0))
    assert np.all(slo <= plo + containment_tol), "Separate lower endpoint excludes paired interval"
    assert np.all(shi >= phi - containment_tol), "Separate upper endpoint excludes paired interval"
    assert np.all((sdec == 0) | (sdec == pdec)), "Separate-only/opposite certificate requires investigation"
    for category, mask in {
        "both": (pdec != 0) & (sdec != 0), "paired_only": (pdec != 0) & (sdec == 0),
        "neither": (pdec == 0) & (sdec == 0), "separate_only": (pdec == 0) & (sdec != 0),
    }.items():
        matched[category] = mask.astype(int)
    tables = {
        "grid_counts.csv": summarize(matched, GRID),
        "grid_seed_counts.csv": summarize(matched, GRID + ["seed"]),
        "cohort_counts.csv": summarize(matched, ["cohort", "regime", "total_tolerance"]),
    }
    for filename, frame in tables.items():
        frame.to_csv(out / filename, index=False, lineterminator="\n")
    grid = tables["grid_counts.csv"]
    example = grid[(grid.cohort == "portugal") & (grid.regime == "saved_forecast_archive_closed")
                   & (grid.gap_hours == 6) & (grid.pattern == "contiguous") & (grid.block_hours == 6)
                   & (grid.total_tolerance == 0)]
    assert len(example) == 1
    row = example.iloc[0]
    assert (row.comparisons, row.both, row.paired_only, row.neither, row.separate_only) == (540, 64, 414, 62, 0)
    rows = []
    cohorts = {"portugal": "Portugal", "household": "Household", "blem_counters": "Counters"}
    for r in tables["cohort_counts.csv"].itertuples(index=False):
        access = "Archive" if r.regime == "saved_forecast_archive_closed" else "Restricted"
        rows.append(f"{cohorts[r.cohort]} & {access} & {100*r.total_tolerance:g}\\% & {r.comparisons:,} & {r.both:,} & {r.paired_only:,} & {r.neither:,} & {r.separate_only:,} \\\\")
    (out / "table_rows.tex").write_text("\n".join(rows) + "\n", encoding="utf-8")
    summary = {
        "status": "passed", "scope": scope, "source_sha256": hashes,
        "script_sha256": digest(__file__), "input_method_rows": len(data),
        "paired_comparisons": len(paired), "matching_separate_comparisons": len(separate),
        "scenario_cells": len(grid), "seed_scenario_cells": len(tables["grid_seed_counts.csv"]),
        "cohort_meters": expected_meters,
        "cross_tab": {category: int(matched[category].sum()) for category in CATEGORIES},
        "checks": {"unique_one_to_one_scenario_keys": True, "matched_observation_and_aggregate_metadata": True,
                   "saved_decisions_reproduced": True, "paired_interval_within_separate_interval": True,
                   "reference_inside_every_paired_and_separate_interval": True, "zero_wrong_certificates": True,
                   "zero_separate_only_certificates": True, "complete_declared_grid": True,
                   "original_portugal_540_example_reproduced": True},
        "tolerances": {"decision": "1e-9 * max(1,abs(lower),abs(upper)); original method-specific rule",
                       "reference_enclosure": "1e-8 * max(1,abs(reference))",
                       "interval_nesting": "1e-8 * max(1,abs(all four endpoints))"},
        "portugal_example": json.loads(example.to_json(orient="records"))[0],
        "interpretation": "Post-review descriptive cross-tab over the entire existing retrospective scenario grid. Repeated masks/seeds, model pairs and total tolerances are not independent trials. No new forecasts, missingness scenarios, tuning or acquisition. Separate bounds are a matched-information certificate comparator, not the strongest point-imputation or acquisition baseline. Full scope includes three BLEM series whose endpoints require raw-source regeneration; public scope replays Portugal and household only.",
        "output_sha256": {name: digest(out / name) for name in [*tables, "table_rows.tex"]},
    }
    for path in provenance:
        assert digest(path) == hashes[str(path.relative_to(input_root)).replace("\\", "/")]
    (out / "verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "scope": scope, "comparisons": len(paired),
                      "grid_cells": len(grid), "cross_tab": summary["cross_tab"], "output_dir": str(out)}))


if __name__ == "__main__":
    main()
