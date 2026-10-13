"""Frozen five-policy public HTTP benchmark, capped at 60 actual requests.

Default is plan-only. --execute performs the read-only public requests.
Uses actual API-grid values, no server emulation or artificial per-query prices.
"""
from __future__ import annotations
import argparse
import csv
from decimal import Decimal
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import time
import numpy as np
import pandas as pd
from measurement import HTTPRecorder,hpm_range_url,summarize_trial
from train_external import read_counters

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
SPEC=importlib.util.spec_from_file_location("original_counter",ROOT/"work/risk_adaptivity_revision/counter_adaptive/study.py")
STUDY=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(STUDY)
POLICIES=["det_batch","mean_batch","greedy_adaptive","adaptive","full_hourly_range"]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False),encoding="utf-8")

def choose_cases(forecasts,counters):
    frame=pd.read_csv(forecasts);frame["timestamp_utc"]=pd.to_datetime(frame.timestamp_utc,utc=True)
    cases=[];skipped=[]
    for system in [1,2,7]:
        rows=frame[frame.system_id==system].sort_values("timestamp_utc")
        selected=None
        for day in sorted(rows.timestamp_utc.dt.normalize().unique()):
            for hour in [0,6,12]:
                start=pd.Timestamp(day)+pd.Timedelta(hours=hour)
                part=rows[(rows.timestamp_utc>=start)&(rows.timestamp_utc<start+pd.Timedelta(hours=6))]
                C0=counters.get((system,start));C6=counters.get((system,start+pd.Timedelta(hours=6)))
                if len(part)!=6 or C0 is None or C6 is None or C6<C0:
                    skipped.append({"system":system,"start":start.isoformat(),"reason":"missing forecast/outer endpoint"});continue
                a=part.daily.to_numpy();b=part.mlp.to_numpy();c=2*(b-a)/6;E=float(C6-C0);width=E*float(np.ptp(c))
                if width<=0:
                    skipped.append({"system":system,"start":start.isoformat(),"reason":"zero initial width"});continue
                selected={"id":f"hpm_{system}/{start.isoformat()}/daily/mlp","system_id":system,
                          "start_unix":int(start.timestamp()),"start_utc":start.isoformat(),
                          "C0":str(C0),"C6":str(C6),"E":E,"W0":width,"c":c.tolist(),
                          "d":float(np.mean(a*a-b*b)),"models":["daily","mlp"]}
                break
            if selected:break
        if selected is None:raise RuntimeError(f"No pre-answer eligible benchmark case for locked system {system}")
        cases.append(selected)
    return cases,skipped

def plan_policy(case,policy,rng):
    c=np.array(case["c"]);c=(c-c.min())/np.ptp(c)
    if policy=="full_hourly_range":return {"cuts":list(range(1,6))}
    V=np.stack([STUDY.vertex_widths(c,q) for q in STUDY.BATCHES],axis=1)
    if policy=="det_batch":
        index=STUDY.min_tie(V.max(axis=0),V.mean(axis=0));return {"cuts":list(STUDY.BATCHES[index])}
    if policy=="mean_batch":
        primary=STUDY.solve(np.r_[np.zeros(10),1.],A_ub=np.c_[V,-np.ones(6)],b_ub=np.zeros(6),A_eq=[np.r_[np.ones(10),0.]],b_eq=[1.],bounds=[(0,None)]*11)
        second=STUDY.solve(V.mean(axis=0),A_ub=V,b_ub=np.full(6,primary.fun+1e-10),A_eq=[np.ones(10)],b_eq=[1.],bounds=[(0,None)]*10)
        weights=np.maximum(second.x,0);weights/=weights.sum()
        index=rng.choices(range(10),weights=weights.tolist(),k=1)[0]
        return {"cuts":list(STUDY.BATCHES[index]),"mixture_weights":weights.tolist(),"sampled_batch":index}
    envelopes=[STUDY.envelope(STUDY.lines(c,k))[0] for k in range(1,6)]
    if policy=="adaptive":first=STUDY.min_tie(envelopes)+1
    else:first=STUDY.min_tie([max(STUDY.span(c,0,k),STUDY.span(c,k,6)) for k in range(1,6)],envelopes)+1
    return {"first":first}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecasts",type=Path,required=True)
    parser.add_argument("--counter-csv",nargs="+",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    lock=json.loads((HERE/"protocol_lock.json").read_text());assert sha(HERE/"PROTOCOL.txt")==lock["protocol_sha256"]
    if args.output_dir.exists():raise FileExistsError("Use a new benchmark directory")
    args.output_dir.mkdir(parents=True)
    counters,_=read_counters(args.counter_csv);cases,skipped=choose_cases(args.forecasts,counters)
    order_rng=random.Random(1729);orders=[]
    for case in cases:
        order=order_rng.sample(POLICIES,len(POLICIES))
        orders.extend([{"case":case["id"],"repetition":0,"order":order},{"case":case["id"],"repetition":1,"order":list(reversed(order))}])
    manifest={"status":"frozen_before_timed_responses","protocol_sha256":lock["protocol_sha256"],
              "source_forecast_sha256":sha(args.forecasts),"counter_source_hashes":{str(p):sha(p) for p in args.counter_csv},
              "code_sha256":sha(Path(__file__)),"cases":cases,"skipped":skipped,"orders":orders,
              "point_semantics":"start=t,end=t+1,interval3600,average0,delta0,timeformatunix",
              "full_semantics":"start=t0,end=t6,interval3600,average0,delta0,timeformatunix; seven values, including retained endpoints",
              "random_seed":1729,"maximum_requests":60,"no_optional_internal_answer_used_for_case_selection":True}
    dump(args.output_dir/"benchmark_plan.json",manifest)
    if not args.execute:
        print("Plan written; no network requests made.");return
    recorder=HTTPRecorder(["heatpumpmonitor.org"],maximum_requests=60,min_start_interval=1.,timeout=30.)
    trials=[];setup={};rng=random.Random(1729)
    def request(case,first,last,trial,policy,role,round_index):
        t0=case["start_unix"];start=t0+3600*first;end=t0+3600*last if last!=first else start+1
        url=hpm_range_url(case["system_id"],"heatpump_elec_kwh",start,end,3600)+"&timeformat=unix"
        received=recorder.get(url,trial_id=trial,policy=policy,role=role,information_round=round_index)
        if received.status!=200:raise RuntimeError(f"HTTP {received.status}")
        values=json.loads(received.payload.decode(),parse_float=Decimal)["heatpump_elec_kwh"]
        parsed={int(t):Decimal(str(v)) if v is not None else None for t,v in values}
        expected=[t0+3600*i for i in range(first,last+1)]
        if list(parsed)!=expected:raise RuntimeError("Actual API timestamps differ from the fixed point/range contract")
        if any(v is None or not v.is_finite() for v in parsed.values()):raise RuntimeError("Requested API sample unavailable; no replacement case")
        received.observation["returned_timestamp_count"]=len(parsed)
        received.observation["returned_timestamps_unix"]=list(parsed)
        return {int((t-t0)/3600):v for t,v in parsed.items()}
    try:
        # Same-grid point/range validation uses the six actual setup requests.
        for case in cases:
            before=len(recorder.records);values={}
            for cut in [0,6]:values.update(request(case,cut,cut,case["id"]+"/setup","common","initial endpoint",0))
            if values[0]!=Decimal(case["C0"]) or values[6]!=Decimal(case["C6"]):raise RuntimeError("Live point and frozen range endpoints disagree; stop rather than changing the target")
            setup[case["id"]]=list(recorder.records[before:])
        case_map={c["id"]:c for c in cases}
        for order in orders:
            case=case_map[order["case"]]
            for policy in order["order"]:
                recorder.close()  # Identical fresh connection for every policy trial.
                trial=case["id"]+f"/{order['repetition']}/{policy}";before=len(recorder.records)
                t0=time.perf_counter();p0=time.perf_counter();plan=plan_policy(case,policy,rng);planning=time.perf_counter()-p0
                known={0:Decimal(case["C0"]),6:Decimal(case["C6"])};requested=[]
                if policy=="full_hourly_range":
                    known.update(request(case,0,6,trial,policy,"full recovery",1));requested=list(range(7))
                elif "cuts" in plan:
                    for cut in plan["cuts"]:
                        known.update(request(case,cut,cut,trial,policy,"preselected point",1));requested.append(cut)
                else:
                    first=plan["first"];known.update(request(case,first,first,trial,policy,"first adaptive point",1));requested.append(first)
                    fraction=Fraction(known[first]-known[0])/Fraction(known[6]-known[0])
                    a0=time.perf_counter();second=STUDY.second(case,first,fraction);planning+=time.perf_counter()-a0
                    known.update(request(case,second,second,trial,policy,"second adaptive point",2));requested.append(second);plan["second"]=second
                v0=time.perf_counter();lo=hi=case["d"];coeff=case["c"]
                for left,right in zip(sorted(known),sorted(known)[1:]):
                    energy=float(known[right]-known[left])
                    if energy<0:raise RuntimeError("Live API cumulative samples are nonmonotone")
                    lo+=energy*min(coeff[left:right]);hi+=energy*max(coeff[left:right])
                width=hi-lo;eps=1e-9*max(case["W0"],1e-15)
                success=width<=.5*case["W0"]+eps;validation=time.perf_counter()-v0;elapsed=time.perf_counter()-t0
                records=recorder.records[before:]
                metrics=summarize_trial(records,elapsed_seconds=elapsed,planning_seconds=planning,validation_seconds=validation,
                                        requested_timestamps=[case["start_unix"]+3600*k for k in requested],
                                        returned_timestamps=[t for r in records for t in r.get("returned_timestamps_unix",[])],precision_success=success)
                trials.append({"case":case["id"],"system_id":case["system_id"],"repetition":order["repetition"],"policy":policy,"plan":plan,
                               "relative_width":width/case["W0"],"interval":[lo,hi],"winner_certified":lo>eps or hi<-eps,**metrics})
                dump(args.output_dir/"trials.json",trials)
        status="PASS"
    except Exception as exc:
        status="FAILED";dump(args.output_dir/"failure.json",{"error":f"{type(exc).__name__}: {exc}","completed_trials":len(trials),"requests_attempted":len(recorder.records)})
        raise
    finally:
        recorder.close();recorder.write(args.output_dir/"request_log.json",scope="Actual public HPM API retrieval microbenchmark; no prototype service",metadata={"status":locals().get("status","INTERRUPTED"),"protocol_sha256":lock["protocol_sha256"]})
        dump(args.output_dir/"setup_requests.json",setup)
    report={"status":status,"trials":len(trials),"requests":len(recorder.records),"systems":3,"repetitions_per_case":2,
            "scope":"Actual public-interface microbenchmark; only three selected tasks, not a population latency estimate or deployment cost saving.",
            "full_baseline":"Seven hourly API-grid samples in one range request. In the retained-endpoint scenario a five-interior-point response could be smaller; no gain is attributed to its two redundant endpoint bytes.",
            "end_to_end_setup":"For selective end-to-end acquisition add the two common endpoint requests. Full-range recovery includes the endpoints in its one request.",
            "limitations":["Provider caches uncontrolled; connections reset consistently per policy trial.","API I/O excludes logged client 1/sec throttle waits; full completion includes them.","Response-body bytes are not TLS wire bytes.","Stored API-grid targets, not verified native physical hourly energy."]}
    dump(args.output_dir/"report.json",report);print(json.dumps(report,indent=2))

if __name__=="__main__":main()
