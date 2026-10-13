"""Read-only provenance/eligibility audit; does not evaluate acquisition policies.

Writes metadata only. No raw counter vectors, hourly targets, or daily
persistence copies are exported by this program. All cases are retained.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
COMMIT = "756b2c1265f964b70f72625a95d98413cdfb78bd"
EXPECTED_RAW = {
    "consumer_00000001": "9228795c6369ce144fbb929f9d413397545f86e3a95d2f9a0f27c92f1d55ad8d",
    "consumer_00000002": "93d142217c74ab2c12a98035b3ea178ead234fec0b71942e8e90db5b7e6a2ef3",
    "consumer_00000003": "db69719d2262ebeb6df39abafffca2805c8a03b1b4777f86eb8aa78acf578b6c",
}
HOUR = 3_600_000
STEP = 180_000
DAY = 24*HOUR
MODELS = ("daily", "ridge", "hist_gradient_boosting", "mlp")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def iso(ms):
    return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat()


def millis(text):
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("A BLEM timestamp must carry its UTC timezone")
    assert dt.utcoffset() == timedelta(0)
    return int(dt.timestamp()*1000)


def load_counter(meter, data_dir):
    """Reference-side raw access. Never hand this entire object to a policy."""
    name = meter.replace("_", "-")
    path = data_dir/f"data_blem_{name}.csv"
    assert sha(path) == EXPECTED_RAW[meter], path
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        values = [(int(r["time"]), int(r["energy"])) for r in reader]
    assert len(values) == 175201
    assert all(b[0]-a[0] == STEP for a,b in zip(values, values[1:]))
    assert all(b[1] >= a[1] for a,b in zip(values, values[1:]))
    return path, columns, values, dict(values)


def block_snapshot(meter, day, cutoff_hour, counters, forecasts, training_mean):
    """Evaluator-visible payload only, before any historical snapshot queries.

    This declared benchmark retains block-start/cutoff counters and withholds all
    interior snapshots. It does not infer actual record arrival or retrieval
    availability from the raw timestamps. The caller keeps counters private.
    """
    assert cutoff_hour in (6,12,18)
    start_hour = cutoff_hour-6
    start = day + start_hour*HOUR
    stop = day + cutoff_hour*HOUR
    total_units = counters[stop]-counters[start]
    assert total_units >= 0
    return {
        "meter": meter,
        "target_start_utc": iso(start), "target_end_utc": iso(stop),
        "audit_cutoff_utc": iso(stop), "forecast_issue_utc": iso(day),
        "horizon_hours": 6,
        "counter_unit_kwh": "1e-10",
        "start_counter_integer": counters[start],
        "cutoff_counter_integer": counters[stop],
        "retained_total_integer_units": total_units,
        "retained_total_kwh": total_units/10**10,
        "forecast_models": list(MODELS),
        "predictions_kwh": {m: forecasts[m][start_hour:cutoff_hour] for m in MODELS},
        "training_mean_kwh": training_mean,
        "loss_normalization_scale": max(training_mean**2, 1e-12),
        "eligible_cumulative_query_utc": [iso(start+h*HOUR) for h in range(1,6)],
        "query_measurement": "C(q)-C(start), in integer counter units; exact linear prefix sum",
        "arrival_semantics": "declared retrospective timestamp cutoff, no actual arrival log",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT/"work")
    parser.add_argument("--forecast-file", type=Path, default=ROOT/"outputs/review_frozen_forecasts.csv")
    parser.add_argument("--output", type=Path, default=HERE/"interface_verification.json")
    args = parser.parse_args()
    summary_path = ROOT/"outputs/study_summary.json"
    public_manifest = ROOT/"outputs/review_frozen_forecasts.json"
    summary = json.loads(summary_path.read_text())
    manifest = json.loads(public_manifest.read_text())
    assert sha(args.forecast_file) == manifest["output_sha256"]
    metadata = {r["meter"]:r for r in summary["meters"] if r["cohort"] == "blem_counters"}
    assert set(metadata) == set(EXPECTED_RAW)
    frozen = {m:{} for m in metadata}
    with args.forecast_file.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["cohort"] != "blem_counters":
                continue
            assert row["truth_kwh"] == "" and row["daily"] == ""
            stamp = millis(row["timestamp"])
            assert stamp % HOUR == 0 and stamp not in frozen[row["meter"]]
            frozen[row["meter"]][stamp] = {m:float(row[m]) for m in MODELS[1:]}
            assert all(math.isfinite(v) and v >= 0 for v in frozen[row["meter"]][stamp].values())
    reports = []
    snapshots_checked = 0
    for meter,meta in sorted(metadata.items()):
        path,columns,raw,counters = load_counter(meter,args.data_dir)
        first,last = raw[0][0],raw[-1][0]
        assert iso(first)=="2016-12-31T23:00:00+00:00"
        assert iso(last)=="2017-12-31T23:00:00+00:00"
        valid_hourly = {}
        for start in range(((first+HOUR-1)//HOUR)*HOUR,last,HOUR):
            vv = [counters.get(t) for t in range(start,start+HOUR+1,STEP)]
            if any(v is None for v in vv) or any(b<a for a,b in zip(vv,vv[1:])):
                continue
            valid_hourly[start] = (vv[-1]-vv[0])/10**10
        assert len(valid_hourly)==8760
        # Rebuild the old complete-day and lag eligibility, without fitting or
        # looking at forecast accuracy/certification/acquisition outcomes.
        day_start = ((min(valid_hourly)+DAY-1)//DAY)*DAY
        last_day = (max(valid_hourly)//DAY)*DAY
        complete = {}
        for day in range(day_start,last_day+1,DAY):
            if all(day+h*HOUR in valid_hourly for h in range(24)):
                complete[day] = [valid_hourly[day+h*HOUR] for h in range(24)]
        eligible = [d for d in sorted(complete) if all(d-k*DAY in complete for k in (1,2,7))]
        split = millis("2017-10-01T00:00:00+00:00")
        train = [d for d in eligible if d<split]
        test = [d for d in eligible if d>=split]
        assert len(train)==266 and len(test)==91
        assert len(frozen[meter])==2184
        assert set(frozen[meter]) == {d+h*HOUR for d in test for h in range(24)}
        train_mean = math.fsum(v for d in train for v in complete[d])/(24*len(train))
        assert abs(train_mean-meta["training_mean_kwh"]) <= 1e-12
        tel_error=0.
        for day in test:
            predictions = {m:[] for m in MODELS}
            for h in range(24):
                predictions["daily"].append(valid_hourly[day-DAY+h*HOUR])
                for model in MODELS[1:]:
                    predictions[model].append(frozen[meter][day+h*HOUR][model])
            for cutoff in (6,12,18):
                payload = block_snapshot(meter,day,cutoff,counters,predictions,meta["training_mean_kwh"])
                assert len(payload["eligible_cumulative_query_utc"]) == 5
                assert all(millis(t)<day+cutoff*HOUR for t in payload["eligible_cumulative_query_utc"])
                assert sum(counters[day+(h+1)*HOUR]-counters[day+h*HOUR] for h in range(cutoff-6,cutoff)) == payload["retained_total_integer_units"]
                tel_error=max(tel_error,abs(math.fsum(complete[day][cutoff-6:cutoff])-payload["retained_total_kwh"]))
                snapshots_checked+=1
        reports.append({
            "meter":meter,"raw_path":path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
            "raw_sha256":sha(path),"raw_columns":columns,"raw_rows":len(raw),
            "source_url":f"https://raw.githubusercontent.com/QuantLet/BLEM/{COMMIT}/data/consumer/{meter.replace('_','-')}.csv",
            "first_utc":iso(first),"last_utc":iso(last),"valid_hourly_intervals":len(valid_hourly),
            "duplicate_times":0,"missing_three_minute_steps":0,"counter_decreases":0,
            "complete_utc_days":len(complete),"eligible_training_days":len(train),"eligible_test_days":len(test),
            "training_start":iso(train[0]),"training_end":iso(train[-1]),
            "test_start":iso(test[0]),"test_end":iso(test[-1]),"frozen_forecast_rows":len(frozen[meter]),
            "training_mean_kwh":meta["training_mean_kwh"],"independent_training_mean_kwh":train_mean,
            "training_scale_absolute_discrepancy":abs(train_mean-meta["training_mean_kwh"]),
            "loss_normalization_scale":max(meta["training_mean_kwh"]**2,1e-12),
            "cutoffs_checked": [6,12,18],"block_total_integer_telescoping_exact":True,
            "maximum_float_block_total_difference_kwh":tel_error,
        })
    result={"status":"passed","scope":"Provenance, calendar, eligibility, scale, timestamp and counter interface only; no policy or advantage evaluation.",
        "source_commit":COMMIT,"meters":reports,"meter_days":273,"hourly_targets":6552,
        "declared_six_hour_snapshots_checked":snapshots_checked,
        "predictions_refit":False,"target_or_counter_rows_exported":False,
        "source_sha256":{str(p.relative_to(ROOT)):sha(p) for p in [summary_path,public_manifest,args.forecast_file,ROOT/"work/data_prepare_blem.py",ROOT/"work/study_protocol_blem.txt",Path(__file__)]},
        "access_rule":"Same-day 00:00-issued forecasts; six-hour blocks [00,06), [06,12), [12,18); visible block-start/end counters; five internal hourly counter queries. Next-day forecast copies and future endpoints excluded.",
        "timing_limitation":"Raw timestamps are measurement times, not measured arrival/retrieval times; outage and access remain imposed benchmark assumptions."}
    assert snapshots_checked==819
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("meters","source_sha256")},indent=2))


if __name__ == "__main__":
    main()
