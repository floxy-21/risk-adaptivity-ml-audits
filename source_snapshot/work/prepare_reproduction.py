"""Remove only archived, post-main derived CSVs before a fresh main-study run.

The main runner records hashes for study_*.csv. These two independently generated
extensions must therefore be regenerated after, rather than during, a fresh main
run. Source data, source code and all four main-study CSVs are untouched here.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ("study_matched_coverage.csv", "study_recovery.csv", "study_recovery_neural.csv",
           "study_operator_example.csv")
DERIVED += ("study_recovery_pair_seed.csv", "study_recovery_cases.csv",
            "study_daily_matched.csv", "study_daily_curves.csv", "study_daily_pairs.csv",
            "study_daily_margin_strata.csv")
DERIVED += ("study_archive_access_cohorts.csv", "study_archive_access_meters.csv",
            "study_archive_access_pair_seed.csv", "study_holdout_consumers_predictions.csv",
            "study_holdout_consumers_pair_seed.csv", "study_holdout_consumers_meters.csv",
            "study_holdout_consumers_cohorts.csv", "study_holdout_consumers_named_pairs.csv",
            "study_holdout_consumers_forecast_metrics.csv")


if __name__ == "__main__":
    for name in DERIVED:
        path = ROOT / "outputs" / name
        if path.exists():
            path.unlink()
            print(f"Removed archived derived result outputs/{name}; regenerate after main study")
