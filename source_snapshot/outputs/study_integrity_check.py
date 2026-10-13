"""Verify final source/protocol/data-output hashes and cross-file study counts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = Path(__file__).resolve().parent
    work = out.parent / "work"
    summary = json.loads((out / "study_summary.json").read_text())
    checked = {}
    for path, expected in [(out / "run_energy_rank_study.py", summary["script_sha256"]),
                           (work / "study_protocol.txt", summary["protocol_sha256"]),
                           *[(work / name, value) for name, value in summary["protocol_supplements"].items()],
                           *[(out / name, record["sha256"]) for name, record in summary["artifacts"].items()]]:
        actual = sha(path)
        assert actual == expected, f"Hash mismatch: {path.name}"
        checked[path.name] = actual
    pred = pd.read_csv(out / "study_predictions.csv")
    comp = pd.read_csv(out / "study_comparisons.csv")
    selection = pd.read_csv(out / "study_selections.csv")
    period = pd.read_csv(out / "study_period_comparisons.csv")
    expected_days = sum(x["test_days"] for x in summary["meters"])
    assert len(pred) == 24 * expected_days
    assert not pred.duplicated(["cohort", "meter", "timestamp"]).any()
    assert np.isfinite(pred[["truth_kwh", *summary["design"]["models"]]]).all().all()
    assert (pred[["truth_kwh", *summary["design"]["models"]]] >= 0).all().all()
    for cohort, info in summary["cohorts"].items():
        for tau, methods in info["comparison"].items():
            for method, record in methods.items():
                rows = comp[(comp.cohort == cohort) & (comp.total_tolerance == float(tau)) & (comp.method == method)]
                assert int(rows.trials.sum()) == record["n"]
                assert int(rows.decisions.sum()) == record["decisions"]
                assert int(rows.wrong_decisions.sum()) == record["wrong"]
                per_meter = rows.groupby("meter")[["trials", "decisions", "wrong_decisions"]].sum()
                rate = (per_meter.decisions / per_meter.trials).mean()
                np.testing.assert_allclose(rate, record["resolved_fraction"], rtol=1e-12, atol=1e-12)
                error = (per_meter.wrong_decisions / per_meter.decisions.replace(0, np.nan)).mean()
                if record["error_among_decisions"] is not None:
                    np.testing.assert_allclose(error, record["error_among_decisions"], rtol=1e-12, atol=1e-12)
        for tau, methods in info["period_comparison"].items():
            for method, record in methods.items():
                rows = period[(period.cohort == cohort) & (period.total_tolerance == float(tau)) & (period.method == method)]
                assert len(rows) == record["n"]
                assert int((rows.decision != 0).sum()) == record["decisions"]
                assert int(rows.wrong_decision.sum()) == record["wrong"]
    direct = comp[comp.method == "paired_bounds"]
    direct_period = period[period.method == "paired_bounds"]
    assert (direct.enclosed_truth == direct.trials).all()
    assert direct.wrong_decisions.sum() == 0
    assert direct_period.wrong_decision.sum() == 0
    assert (selection.regret_bound_coverage == 1).all()
    masks_per_day = (len(summary["design"]["gaps"]) * len(summary["design"]["patterns"])
                     * len(summary["design"]["seeds"]) * len(summary["design"]["block_hours"])
                     * len(summary["design"]["total_tolerances"]))
    scenarios = expected_days * masks_per_day
    assert direct.trials.sum() == scenarios * 6
    result = {
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "hashes_verified": checked,
        "meters": len(summary["meters"]),
        "heldout_meter_days": expected_days,
        "dependent_verification_scenarios": scenarios,
        "dependent_pairwise_comparisons": int(direct.trials.sum()),
        "daily_paired_decisions": int(direct.decisions.sum()),
        "daily_paired_wrong_decisions": int(direct.wrong_decisions.sum()),
        "period_paired_decisions": int((direct_period.decision != 0).sum()),
        "period_paired_wrong_decisions": int(direct_period.wrong_decision.sum()),
        "paired_reference_enclosure_fraction": 1.0,
        "minimum_selection_regret_bound_coverage": float(selection.regret_bound_coverage.min()),
        "row_counts": {"predictions": len(pred), "comparisons": len(comp), "selections": len(selection), "period_comparisons": len(period)},
        "interpretation": "Cross-file accounting and recorded-input integrity checks, not evidence that scenarios are independent or that future rankings are guaranteed.",
    }
    destination = out / "study_integrity_check.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "hashes_verified"}, indent=2))


if __name__ == "__main__":
    main()
