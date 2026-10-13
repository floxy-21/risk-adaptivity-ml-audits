"""Reproduce exact hourly energy targets from published BLEM meter counters.

Python standard library only. Downloads are optional and use the pinned original
authors' public repository. Output timestamps denote UTC interval START. This
script never interpolates counters and never uses observed maxima as capacities.

Usage:
  python data_prepare_blem.py --data-dir work --output-dir work/data_reproduced
  python data_prepare_blem.py --download --data-dir work --output-dir work/data_reproduced
"""
import argparse
import csv
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

COMMIT = "756b2c1265f964b70f72625a95d98413cdfb78bd"
SHA256 = {
    "consumer-00000001": "9228795c6369ce144fbb929f9d413397545f86e3a95d2f9a0f27c92f1d55ad8d",
    "consumer-00000002": "93d142217c74ab2c12a98035b3ea178ead234fec0b71942e8e90db5b7e6a2ef3",
    "consumer-00000003": "db69719d2262ebeb6df39abafffca2805c8a03b1b4777f86eb8aa78acf578b6c",
}
HOUR_MS = 3_600_000
STEP_MS = 180_000
KWH_PER_COUNTER_UNIT = 1e-10


def utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def prepare(data_dir, output_dir, download=False):
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    hourly_by_meter = {}
    endpoints = []
    audit = {}
    for meter, expected_sha in SHA256.items():
        path = data_dir / f"data_blem_{meter}.csv"
        source = (f"https://raw.githubusercontent.com/QuantLet/BLEM/{COMMIT}"
                  f"/data/consumer/{meter}.csv")
        if not path.exists():
            if not download:
                raise FileNotFoundError(f"{path}; use --download to obtain original data")
            with urllib.request.urlopen(source, timeout=90) as response:
                path.write_bytes(response.read())
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(f"Checksum mismatch for {path}")
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = [(int(r["time"]), int(r["energy"])) for r in csv.DictReader(f)]
        times = [r[0] for r in rows]
        if times != sorted(times) or len(set(times)) != len(times):
            raise ValueError(f"Unsorted/duplicate timestamps in {meter}")
        by_time = dict(rows)
        series = {}
        # Each eligible target uses two exact hour-boundary counter snapshots.
        # The additional fine-grid checks eliminate missing/reset interior data.
        first = ((times[0] + HOUR_MS - 1) // HOUR_MS) * HOUR_MS
        for start in range(first, times[-1], HOUR_MS):
            end = start + HOUR_MS
            stamps = range(start, end + 1, STEP_MS)
            values = [by_time.get(t) for t in stamps]
            if any(v is None for v in values):
                continue
            if any(b < a for a, b in zip(values, values[1:])):
                continue
            # Integer subtraction is essential, and precedes floating conversion.
            energy = (values[-1] - values[0]) / 10**10
            series[start] = energy
            endpoints.append([meter.replace("-", "_"), utc(start), utc(end),
                              utc(start), utc(end), 0, 0,
                              values[0], values[-1], energy])
        hourly_by_meter[meter] = series
        audit[meter] = {
            "source": source, "sha256": actual_sha, "raw_rows": len(rows),
            "first_utc": utc(times[0]), "last_utc": utc(times[-1]),
            "valid_hourly_intervals": len(series),
            "non_3min_steps": sum(b-a != STEP_MS for a,b in zip(times,times[1:])),
            "negative_counter_steps": sum(b[1] < a[1] for a,b in zip(rows,rows[1:])),
        }
    all_times = sorted(set().union(*(set(v) for v in hourly_by_meter.values())))
    with (output_dir / "data_blem_hourly.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp"] + [m.replace("-", "_") for m in SHA256])
        for stamp in all_times:
            writer.writerow([utc(stamp)] + [hourly_by_meter[m].get(stamp, "") for m in SHA256])
    with (output_dir / "data_blem_hourly_endpoints.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["meter", "interval_start_utc", "interval_end_utc",
                         "actual_start_snapshot_utc", "actual_end_snapshot_utc",
                         "start_lag_seconds", "end_lag_seconds",
                         "start_counter_integer", "end_counter_integer", "energy_kwh"])
        writer.writerows(endpoints)
    (output_dir / "data_blem_preparation_audit.json").write_text(
        json.dumps({"commit": COMMIT, "article": "https://doi.org/10.3390/en12142718",
                    "conversion_source": "BLEMdescStatEnergyData/FUN_getData.R",
                    "counter_unit_to_kwh": KWH_PER_COUNTER_UNIT,
                    "endpoint_interpolation": False, "stats": audit}, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("work"))
    parser.add_argument("--output-dir", type=Path, default=Path("work/data_reproduced"))
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(args.data_dir, args.output_dir, args.download), indent=2))
