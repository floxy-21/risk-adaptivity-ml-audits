"""Record the pre-outcome operational protocol and source-selection hashes."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    output=HERE/"protocol_lock.json"
    if output.exists():raise FileExistsError("Protocol already frozen; preserve it and document an amendment")
    selected=ROOT/"work/risk_adaptivity_revision/external_heatpump/selected_systems.json"
    source_protocol=selected.with_name("source_selection_protocol.json")
    assert [r["id"] for r in json.loads(selected.read_text())]==[1,2,7]
    record={
        "status":"fixed_before_external_forecast_or_treatment_outcomes",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "protocol_sha256":sha(HERE/"PROTOCOL.txt"),
        "selected_systems_sha256":sha(selected),"source_selection_protocol_sha256":sha(source_protocol),
        "original_forecast_program_sha256":sha(ROOT/"outputs/run_energy_rank_study.py"),
        "implementation_sha256":{name:sha(HERE/name) for name in ["measurement.py","train_external.py","test_measurement.py"]},
        "systems":[1,2,7],"train_start":"2025-01-01T00:00:00Z","test_start":"2025-07-01T00:00:00Z","test_end_exclusive":"2025-08-01T00:00:00Z",
        "only_training_values_inspected":True,"provider_benchmark_requests_made":0,
        "no_paper_modified_or_submitted":True,"no_outreach":True,
        "implementation_status":"Transport offline unit tests only; explicit-split forecast adapter not yet executed; interface benchmark awaits canonical July adapter and runner.",
        "interface_limits":"Stored hourly API-grid cumulative samples; no verified native timestamp or direct-register provenance; full hourly-range recovery is mandatory comparator."
    }
    output.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(record,indent=2))

if __name__=="__main__":main()
