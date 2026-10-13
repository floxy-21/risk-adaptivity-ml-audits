"""Read-only gate replay over the complete public exact-total endpoint grid.

Uses no training, new masks, queries, alternative denominator, or target tuning.
Endpoints are frozen historical outputs. Reference losses are consulted only
after all gate classifications have been fixed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

from certificate_gate import certificate_gate

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
KEYS = ["cohort", "meter", "model_a", "model_b", "gap_hours", "pattern", "seed",
        "block_hours", "total_tolerance", "regime"]
VISIBLE_METADATA = ["days", "full_target_denominator", "observed_target_denominator",
                    "normalization_scale", "originally_missing_coordinates",
                    "free_archive_coordinates", "aggregate_determined_coordinates", "fully_known_days"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(frame):
    n = len(frame)
    p = frame.paired_gate_action.value_counts().to_dict()
    s = frame.separate_gate_action.value_counts().to_dict()
    separate_hold = int(s.get("hold", 0))
    paired_hold = int(p.get("hold", 0))
    newly_allowed = int(((frame.paired_gate_action == "allow") &
                         (frame.separate_gate_action == "hold")).sum())
    return dict(comparisons=n, paired_allow=int(p.get("allow",0)),
        paired_hold=paired_hold, paired_contradict=int(p.get("contradict",0)),
        separate_allow=int(s.get("allow",0)), separate_hold=separate_hold,
        separate_contradict=int(s.get("contradict",0)),
        no_strict_donor_proposal=int(p.get("no_strict_proposal",0)),
        additional_allowed=newly_allowed,
        held_reduction_percent=100*(separate_hold-paired_hold)/separate_hold if separate_hold else None,
        paired_allow_percent=100*p.get("allow",0)/n,
        separate_allow_percent=100*s.get("allow",0)/n,
        held_with_opposite_completion=int(((frame.paired_gate_action == "hold") &
          frame.paired_opposite_completion_supported_by_sharp_endpoint).sum()),
        donor_wrong_reference_after_gate=int(frame.donor_wrong_reference_after_gate.sum()),
        paired_wrong_reference_after_gate=int(frame.paired_wrong_reference_after_gate.sum()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=HERE / "results")
    args = parser.parse_args()
    started = time.perf_counter()
    source = args.input_root / "outputs/study_period_archive_public_cases.csv"
    manifest_path = args.input_root / "outputs/study_period_archive_public_manifest.json"
    source_hash = sha(source)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert source_hash == manifest["public_files"][source.name]["sha256"]
    parse_start = time.perf_counter()
    data = pd.read_csv(source)
    parse_seconds = time.perf_counter()-parse_start
    exact = data[data.total_tolerance == 0].copy()
    paired = exact[exact.method == "paired_bounds"].set_index(KEYS).sort_index()
    separate = exact[exact.method == "individual_bounds"].set_index(KEYS).sort_index()
    donor = exact[exact.method == "historical_donor"].set_index(KEYS).sort_index()
    assert not paired.index.duplicated().any()
    assert paired.index.equals(separate.index) and paired.index.equals(donor.index)
    for field in VISIBLE_METADATA:
        np.testing.assert_array_equal(paired[field].to_numpy(), separate[field].to_numpy())
        np.testing.assert_array_equal(paired[field].to_numpy(), donor[field].to_numpy())
    assert len(paired) == 20088
    ledger = paired.reset_index()[KEYS+VISIBLE_METADATA].copy()
    ledger["donor_point_gap"] = donor.mean_lower_or_point.to_numpy()
    donor_margin = 1e-9 * np.maximum(1.0, np.abs(ledger.donor_point_gap.to_numpy()))
    donor_direction = np.where(ledger.donor_point_gap > donor_margin, 1,
                        np.where(ledger.donor_point_gap < -donor_margin, -1, 0))
    np.testing.assert_array_equal(donor_direction, donor.decision.to_numpy())
    ledger["donor_proposed_direction"] = donor_direction
    ledger["donor_proposed_winner"] = np.where(donor_direction > 0, ledger.model_b,
                                           np.where(donor_direction < 0, ledger.model_a, "tie"))
    # Gate phase deliberately has no reference-loss argument or reference lookup.
    gate_start = time.perf_counter()
    for name, frame in (("paired", paired), ("separate", separate)):
        lo, hi = frame.mean_lower_or_point.to_numpy(), frame.mean_upper_or_point.to_numpy()
        assert np.isfinite(np.r_[lo, hi]).all()
        ledger[name+"_lower"] = lo
        ledger[name+"_upper"] = hi
        records = [certificate_gate(float(l), float(u), int(direction))
                   for l, u, direction in zip(lo, hi, donor_direction)]
        gate = pd.DataFrame(records)
        np.testing.assert_array_equal(gate.certified_direction.to_numpy(), frame.decision.to_numpy())
        for column in gate:
            ledger[name+"_"+("gate_action" if column == "action" else column)] = gate[column].to_numpy()
    gate_seconds = time.perf_counter()-gate_start
    gate_fingerprint = hashlib.sha256(ledger.to_csv(index=False, lineterminator="\n").encode()).hexdigest()

    # Only after classification: check the historical reference and nested bounds.
    truth = paired.true_mean_gap.to_numpy()
    for frame in (separate, donor):
        np.testing.assert_array_equal(truth, frame.true_mean_gap.to_numpy())
    eps = 1e-8*np.maximum(1., np.abs(truth))
    assert np.all(ledger.paired_lower <= truth+eps)
    assert np.all(ledger.paired_upper >= truth-eps)
    nesting_eps = 1e-8*np.maximum(1., np.max(np.abs(ledger[["paired_lower", "paired_upper", "separate_lower", "separate_upper"]].to_numpy()), axis=1))
    assert np.all(ledger.separate_lower <= ledger.paired_lower+nesting_eps)
    assert np.all(ledger.separate_upper >= ledger.paired_upper-nesting_eps)
    ledger["reference_gap_after_gate"] = truth
    ledger["donor_wrong_reference_after_gate"] = (donor_direction != 0) & (donor_direction != np.sign(truth))
    ledger["paired_wrong_reference_after_gate"] = (ledger.paired_certified_direction != 0) & (ledger.paired_certified_direction != np.sign(truth))
    assert not ledger.paired_wrong_reference_after_gate.any()
    portugal = ledger[(ledger.cohort == "portugal") &
                      (ledger.regime == "saved_forecast_archive_closed")]
    primary = summarize(portugal)
    assert primary["comparisons"] == 9720
    assert primary["paired_allow"] == 7836 and primary["separate_allow"] == 2513
    assert primary["paired_hold"] == 1884 and primary["separate_hold"] == 7207
    assert primary["held_with_opposite_completion"] == 1884
    assert primary["paired_contradict"] == 0 and primary["donor_wrong_reference_after_gate"] == 0
    groups = []
    for (cohort, regime), part in ledger.groupby(["cohort", "regime"], sort=True):
        groups.append(dict(cohort=cohort, regime=regime, **summarize(part)))
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(out/"action_ledger.csv", index=False, lineterminator="\n")
    pd.DataFrame(groups).to_csv(out/"cohort_summary.csv", index=False, lineterminator="\n")
    assert sha(source) == source_hash
    report = dict(status="passed", source=str(source.relative_to(args.input_root)).replace("\\","/"),
        source_sha256=source_hash, manifest_sha256=sha(manifest_path),
        script_sha256=sha(__file__), gate_source_sha256=sha(HERE/"certificate_gate.py"),
        python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
        input_rows=len(data), exact_total_comparisons=len(ledger),
        gate_calls=2*len(ledger), primary_portugal_archive_exact=primary,
        groups=groups, gate_phase_fingerprint_before_reference=gate_fingerprint,
        seconds=dict(csv_parse=parse_seconds, gate_calls_and_ledger_columns=gate_seconds,
                     full_execution=time.perf_counter()-started),
        tolerance=dict(decision="1e-9*max(1,abs(lower),abs(upper))", enclosure="1e-8*max(1,abs(reference))"),
        output_sha256={name:sha(out/name) for name in ["action_ledger.csv", "cohort_summary.csv"]},
        interpretation="A post-review replay of a declared allow/hold gate over saved sharp endpoints. The count reduction is in unresolved certificates under identical information and zero queries; it is not measured money, latency, manual workload, predictive accuracy, or acquisition savings. Separate-loss bounds are the matched certificate baseline, not the strongest point-imputation baseline. All donor directions in the primary grid are correct on the observed reference; held directions have feasible opposite-sign completions supported by the sharp endpoint theorem. The ledger does not export those full completion vectors or regenerate bounds. Constructed risk separations are separate evidence.")
    (out/"verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status":"passed", "primary":primary, "seconds":report["seconds"]}, indent=2))


if __name__ == "__main__":
    main()
