"""Independently check the cached HPM selection and internal freeze chronology.

Standard library only: no network, model fitting, forecasting or policy replay.
The recorded chronology is an internal audit trail, not external preregistration.
"""
from __future__ import annotations
import argparse
import datetime as dt
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / "external_heatpump"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(value):
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert result.tzinfo is not None and result.utcoffset() == dt.timedelta(0)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "source_qualification_check.json")
    args = parser.parse_args()
    started = time.perf_counter()
    source_protocol = json.loads((SOURCE / "source_selection_protocol.json").read_text())
    lock = json.loads((HERE / "protocol_lock.json").read_text())
    assert digest(SOURCE / "source_selection_protocol.json") == lock["source_selection_protocol_sha256"]
    assert digest(SOURCE / "selected_systems.json") == lock["selected_systems_sha256"]
    assert digest(HERE / "PROTOCOL.txt") == lock["protocol_sha256"]
    train_begin = int(stamp(source_protocol["training_utc"][0]).timestamp())
    train_end = int(stamp(source_protocol["training_utc"][1]).timestamp())
    test_end = int(stamp(source_protocol["test_utc"][1]).timestamp())
    assert (train_begin, train_end, test_end) == (1735689600, 1751328000, 1754006400)
    assert source_protocol["test_utc"][0] == source_protocol["training_utc"][1]

    # Derive the stopping-prefix decisions from the raw cached metadata rather
    # than trusting the saved selection decisions or running its producer.
    systems = json.loads((SOURCE / "metadata/public_systems.json").read_text())
    if isinstance(systems, dict):
        systems = list(systems.values())
    systems.sort(key=lambda record: int(record["id"]))
    assert len({int(record["id"]) for record in systems}) == len(systems)
    derived = []
    chosen = []
    for system in systems:
        ident = int(system["id"])
        meter = str(system.get("electric_meter", ""))
        row = {"id": ident, "mid_metering": system.get("mid_metering"), "electric_meter": meter}
        if str(system.get("mid_metering", "")).lower() not in ("1", "true"):
            row["decision"] = "exclude_not_mid"
        elif "class 1" not in meter.lower():
            row["decision"] = "exclude_missing_explicit_class_1_description"
        else:
            feeds = json.loads((SOURCE / f"metadata/system_{ident}_feeds.json").read_text())
            feed = feeds.get("feeds", feeds).get("heatpump_elec_kwh")
            if feed is None:
                row["decision"] = "exclude_missing_cumulative_feed"
            else:
                row["feed"] = feed
                if int(feed["start_time"]) > train_begin or int(feed["end_time"]) < test_end:
                    row["decision"] = "exclude_metadata_does_not_cover_frozen_calendar"
                else:
                    row["decision"] = "selected"
                    chosen.append(ident)
        derived.append(row)
        if len(chosen) == 3:
            break
    expected = json.loads((SOURCE / "selection_ledger.json").read_text())
    assert derived == expected, "Cached metadata does not reproduce selection ledger"
    assert chosen == [1, 2, 7] == lock["systems"]
    saved_selection = json.loads((SOURCE / "selected_systems.json").read_text())
    assert [record["id"] for record in saved_selection] == chosen
    by_id = {record["id"]: record for record in derived}
    for selected in saved_selection:
        for key in ("mid_metering", "electric_meter", "feed"):
            assert selected[key] == by_id[selected["id"]][key]

    # Check every cached response, including metadata accidentally fetched by
    # the documented early envelope-parser error. No request is issued here.
    logs = [json.loads(line) for line in (SOURCE / "request_log.jsonl").read_text().splitlines()]
    for row in logs:
        relative = Path(row["path"].replace("\\", "/"))
        assert not relative.is_absolute() and ".." not in relative.parts
        body = SOURCE / relative
        assert digest(body) == row["sha256"], str(relative)
        assert body.stat().st_size == row["bytes"], str(relative)
        assert row["status"] == 200
    recorded_times = [stamp(row["started_utc"]) for row in logs]
    assert recorded_times == sorted(recorded_times)
    train_log = [row for row in logs if "_train_2025H1.json" in row["path"]]
    july_log = [row for row in logs if "_test_2025July.json" in row["path"]]
    assert len(train_log) == len(july_log) == 3
    assert {Path(row["path"].replace("\\", "/")).name for row in train_log} == {
        f"system_{ident}_train_2025H1.json" for ident in chosen}
    assert {Path(row["path"].replace("\\", "/")).name for row in july_log} == {
        f"system_{ident}_test_2025July.json" for ident in chosen}
    hourly = [row for row in logs if row["path"].replace("\\", "/").startswith("hourly/")]
    assert len(hourly) == 6, "Unexpected hourly request outside selected six cached ranges"
    selection_freeze = stamp(source_protocol["frozen_utc"])
    operational_freeze = stamp(lock["created_utc"])
    first_training = min(stamp(row["started_utc"]) for row in train_log)
    last_training = max(stamp(row["started_utc"]) for row in train_log)
    first_july = min(stamp(row["started_utc"]) for row in july_log)
    assert selection_freeze <= recorded_times[0] < first_training
    assert last_training < operational_freeze < first_july
    assert lock["only_training_values_inspected"] is True
    assert lock["provider_benchmark_requests_made"] == 0

    # Independently reconstruct raw availability and the lag-complete training
    # gate. Exact decimal differences avoid importing the forecast producer.
    availability = {row["id"]: row for row in json.loads((SOURCE / "training_availability.json").read_text())}
    fits = {row["system_id"]: row for row in json.loads((HERE / "fresh_fits_20261012/training_report.json").read_text())["systems"]}
    training_results = []
    endpoint_grid = list(range(train_begin, train_end + 1, 3600))
    for ident in chosen:
        path = SOURCE / f"hourly/system_{ident}_train_2025H1.json"
        raw = json.loads(path.read_text(), parse_float=Decimal, parse_int=Decimal)
        samples = raw["heatpump_elec_kwh"]
        assert [int(row[0]) for row in samples] == endpoint_grid
        values = [row[1] for row in samples]
        def valid(value):
            return isinstance(value, Decimal) and value.is_finite()
        intervals = [valid(left) and valid(right) and right >= left
                     for left, right in zip(values[:-1], values[1:])]
        days = [all(intervals[start:start+24]) for start in range(0, len(intervals), 24)]
        feature_eligible = [index for index in range(7, len(days))
                            if all(days[index-lag] for lag in (0, 1, 2, 7))]
        count = sum(intervals)
        fraction = count / len(intervals)
        saved = availability[ident]
        assert digest(path) == saved["sha256"]
        assert len(samples) == saved["response_rows"] == saved["expected_endpoint_count"]
        assert count == saved["valid_hourly_intervals"]
        assert len(intervals) == saved["total_training_intervals"]
        assert sum(days) == saved["complete_days"]
        assert abs(fraction-saved["valid_fraction"]) <= 1e-15
        assert len(feature_eligible) == fits[ident]["train_days"]
        assert abs(fraction-fits[ident]["training_hourly_valid_fraction"]) <= 1e-15
        assert count * 100 >= 95 * len(intervals) and len(feature_eligible) >= 90
        training_results.append({"system_id": ident, "valid_intervals": count,
            "total_intervals": len(intervals), "valid_fraction": fraction,
            "complete_raw_days": sum(days), "feature_eligible_training_days": len(feature_eligible),
            "eligible": True, "training_response_sha256": digest(path)})

    report = {"status": "PASS", "scope": "Independent offline cached-metadata qualification and internal chronology check; no network or refit",
        "public_systems": len(systems), "screened_stopping_prefix": [row["id"] for row in derived],
        "selected_systems": chosen, "decision_ledger": derived,
        "verified_cached_response_hashes": len(logs), "training": training_results,
        "chronology_utc": {"source_rule_frozen": selection_freeze.isoformat(),
            "first_training_request": first_training.isoformat(), "last_training_request": last_training.isoformat(),
            "detailed_operational_rule_frozen": operational_freeze.isoformat(), "first_July_request": first_july.isoformat()},
        "chronology_interpretation": "Source rule precedes all hourly data; detailed operational/training gates were locked after training-only inspection and before July retrieval. Internal timestamps are not external preregistration.",
        "source_sha256": {"source_selection_protocol.json": digest(SOURCE / "source_selection_protocol.json"),
            "selected_systems.json": digest(SOURCE / "selected_systems.json"),
            "selection_ledger.json": digest(SOURCE / "selection_ledger.json"),
            "request_log.jsonl": digest(SOURCE / "request_log.jsonl"),
            "protocol_lock.json": digest(HERE / "protocol_lock.json")},
        "script_sha256": digest(Path(__file__)), "seconds": time.perf_counter()-started}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "public_systems", "selected_systems", "verified_cached_response_hashes", "training", "chronology_utc", "seconds")}, indent=2))


if __name__ == "__main__":
    main()
