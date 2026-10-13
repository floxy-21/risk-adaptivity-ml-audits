"""Additive UCI-only public export; preserve full local analysis artifacts.

BLEM hourly loss traces can be inverted with saved forecasts. Archive period
endpoints can also isolate the final day lacking future copies. Omit detailed
BLEM states, mappings, aggregate traces, copy pointers and period case rows.
Keep published cohort/scenario/pair summaries and optional raw regeneration.
"""
from datetime import datetime, timezone
from pathlib import Path
import csv
import gzip
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs"
NAMES=("cases.csv","sources.csv","states.csv.gz","links.csv.gz","aggregates.csv.gz")


def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def main():
    report=json.loads((OUT/"study_period_archive.json").read_text())
    assert report["status"]=="passed"
    mapping={}; original_hashes={}; public_hashes={}; counts={}
    for suffix in NAMES:
        full="study_period_archive_"+suffix
        public="study_period_archive_public_"+suffix
        assert sha(OUT/full)==report["output_hashes"][full]
        opener=gzip.open if suffix.endswith(".gz") else open
        total=kept=0
        with opener(OUT/full,"rt",newline="",encoding="utf-8") as source, opener(OUT/public,"wt",newline="",encoding="utf-8") as destination:
            reader=csv.DictReader(source)
            writer=csv.DictWriter(destination,fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                total+=1
                if row["cohort"]=="blem_counters": continue
                assert row["cohort"] in ("portugal","household")
                writer.writerow(row);kept+=1
        mapping[public]=full
        original_hashes[full]=sha(OUT/full)
        assert original_hashes[full]==report["output_hashes"][full]
        public_hashes[public]=sha(OUT/public)
        counts[full]={"full_rows":total,"public_rows":kept,"omitted_blem_rows":total-kept}
    result={"status":"passed","created_utc":datetime.now(timezone.utc).isoformat(),
        "script_sha256":sha(Path(__file__)),"full_analysis_sha256":sha(OUT/"study_period_archive.json"),
        "public_to_full":mapping,
        "omitted_files":{name:{"sha256":digest,"bytes":(OUT/name).stat().st_size,**counts[name]} for name,digest in original_hashes.items()},
        "public_files":{name:{"sha256":digest,"bytes":(OUT/name).stat().st_size,"full_file":mapping[name],"rows":counts[mapping[name]]["public_rows"]} for name,digest in public_hashes.items()},
        "row_counts":counts,
        "omitted_cohort":"blem_counters",
        "reason":"Detailed loss traces plus saved forecasts can reveal individual targets; archive period endpoints can isolate the final day without future copies. Omitting explicit observation columns alone is insufficient.",
        "public_scope":"UCI-only daily scalar traces and method-specific period cases. BLEM cohort/scenario/pair/matched aggregates remain, without public daily-state or per-case reproduction.",
        "full_scope":"Full34-meter local analysis and independent scalar-trace verification are preserved. The optional raw-data reproduction path recreates the omitted BLEM detailed artifacts for all34 checks.",
        "source_hashes":{"study_period_archive.json":sha(OUT/"study_period_archive.json")}}
    (OUT/"study_period_archive_public_manifest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"status":"passed","row_counts":counts}),flush=True)


if __name__=="__main__": main()
