"""Check actual HTTP traces against independently cached public July samples.

No network calls. Reconstructs expected JSON bodies from original source tokens,
checks SHA256 for every response, reference-loss containment and all budget logs.
"""
import argparse
import csv
from decimal import Decimal
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import statistics
from urllib.parse import urlsplit,parse_qs

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-dir",type=Path,required=True)
    parser.add_argument("--source-dir",type=Path,default=ROOT/"work/risk_adaptivity_revision/external_heatpump/hourly")
    args=parser.parse_args();base=args.benchmark_dir
    manifest=json.loads((base/"benchmark_plan.json").read_text())
    cases={c["id"]:c for c in manifest["cases"]}
    trials=json.loads((base/"trials.json").read_text())
    records=json.loads((base/"request_log.json").read_text())["records"]
    assert len(trials)==30 and len(records)==60
    source={s:dict(json.loads((args.source_dir/f"system_{s}_test_2025July.json").read_text(),parse_float=Decimal)["heatpump_elec_kwh"]) for s in [1,2,7]}
    matched=0;different=[]
    for record in records:
        assert record["status"]==200 and record["error"] is None
        query=parse_qs(urlsplit(record["url"]).query);system=int(query["id"][0])
        assert query["interval"]==["3600"] and query["average"]==["0"] and query["delta"]==["0"]
        stamps=record["returned_timestamps_unix"]
        expected='{"heatpump_elec_kwh":['+','.join('['+str(t)+','+str(source[system][t])+']' for t in stamps)+']}'
        payload=expected.encode()
        if hashlib.sha256(payload).hexdigest()==record["decoded_payload_sha256"]:
            matched+=1
            assert len(payload)==record["decoded_payload_bytes"]
        else:
            different.append({"request":record["sequence"],"expected_length":len(payload),"actual_length":record["decoded_payload_bytes"]})
    assert not different,("Source reconstruction differs from response hash; do not infer equality from timestamps alone",different)
    max_containment=0.0;adaptive_decisions=0
    for trial in trials:
        case=cases[trial["case"]];raw=source[case["system_id"]];start=case["start_unix"]
        counter=[raw[start+3600*h] for h in range(7)]
        truth=[float(counter[i+1]-counter[i]) for i in range(6)]
        reference=case["d"]+sum(c*y for c,y in zip(case["c"],truth))
        lo,hi=trial["interval"]
        max_containment=max(max_containment,lo-reference,reference-hi)
        assert lo<=reference+1e-9*max(1,abs(reference)) and hi>=reference-1e-9*max(1,abs(reference))
        if trial["policy"]=="full_hourly_range":
            assert trial["requests"]==1 and trial["distinct_returned_samples"]==7
            assert abs(hi-lo)<1e-12 and trial["precision_success"]
        else:
            assert trial["requests"]==2 and trial["distinct_returned_samples"]==2
        if "first" in trial["plan"]:
            k=trial["plan"]["first"];t=F(counter[k]-counter[0])/F(counter[6]-counter[0]);c=list(map(F.from_float,case["c"]))
            def span(a,b):return max(c[a:b])-min(c[a:b])
            choices=[]
            for j in range(1,6):
                if j==k:continue
                aa,bb=(max(span(0,j),span(j,k)),span(k,6)) if j<k else (span(0,k),max(span(k,j),span(j,6)))
                choices.append((aa*t+bb*(1-t),j))
            assert trial["plan"]["second"]==min(choices)[1]
            adaptive_decisions+=1
    metrics=["requests","information_rounds","body_bytes_received","api_io_seconds","throttle_wait_seconds","end_to_end_elapsed_seconds","planning_seconds","client_cpu_seconds","relative_width","precision_success","winner_certified"]
    summaries=[]
    for policy in sorted({r["policy"] for r in trials}):
        rows=[r for r in trials if r["policy"]==policy]
        for metric in metrics:
            values=[float(r[metric]) for r in rows]
            summaries.append({"policy":policy,"metric":metric,"runs":len(values),"mean":statistics.mean(values),"median":statistics.median(values),"min":min(values),"max":max(values)})
    with (base/"measurement_summary.csv").open("w",newline="",encoding="utf-8") as file:
        writer=csv.DictWriter(file,fieldnames=list(summaries[0]));writer.writeheader();writer.writerows(summaries)
    paired=[]
    for case_id in cases:
        rows=[r for r in trials if r["case"]==case_id]
        full=[r for r in rows if r["policy"]=="full_hourly_range"]
        for policy in sorted({r["policy"] for r in rows}):
            selected=[r for r in rows if r["policy"]==policy]
            paired.append({"case":case_id,"policy":policy,"repetitions":2,
                           "api_io_median_seconds":statistics.median(r["api_io_seconds"] for r in selected),
                           "api_io_min_seconds":min(r["api_io_seconds"] for r in selected),
                           "api_io_max_seconds":max(r["api_io_seconds"] for r in selected),
                           "mean_body_bytes":statistics.mean(r["body_bytes_received"] for r in selected),
                           "mean_paired_api_io_difference_vs_full_seconds":statistics.mean(r["api_io_seconds"]-next(f["api_io_seconds"] for f in full if f["repetition"]==r["repetition"]) for r in selected),
                           "precision_successes":sum(r["precision_success"] for r in selected)})
    with (base/"per_case_measurements.csv").open("w",newline="",encoding="utf-8") as file:
        writer=csv.DictWriter(file,fieldnames=list(paired[0]));writer.writeheader();writer.writerows(paired)
    result={"status":"PASS","responses_matching_original_source_payload_sha256":matched,"requests":len(records),
            "completed_trials":len(trials),"adaptive_second_choices_checked":adaptive_decisions,
            "maximum_reference_containment_error":max_containment,
            "scope":"Source-token reconstruction matches every received payload hash; timestamp/budget/interval checks and independent adaptive second decisions. Timing summaries are descriptive for three fixed cases.",
            "measurement_limitations":["client_cpu_seconds covers measured request processing, not total optimizer CPU; planning wall time is separately measured.",
                "Full hourly-range response includes two initially known endpoints; a five-interior-point response could reduce its payload further.",
                "Client one-request-per-second waiting is separately logged and is not provider latency.",
                "No provider server CPU, packets/TLS wire bytes, or population latency confidence interval is measured."]}
    (base/"verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
