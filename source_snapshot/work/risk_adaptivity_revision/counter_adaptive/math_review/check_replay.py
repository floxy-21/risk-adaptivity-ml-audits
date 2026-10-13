"""Independent raw-counter replay and selected sharp-endpoint LP checks.

No study.py code is imported. Exact integer-register differences and original
serialized coefficient Fractions define the checked targets and policy rule.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import time
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from check_counter_adaptive import conditional_coefficients

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BATCHES = list(itertools.combinations(range(1,6),2))
FRACTIONS = [.25,.4,.5,.6,.75]
TOL = 2e-8


def exact_terminal(c,d,y,Q):
    cuts = (0,)+tuple(Q)+(6,)
    lo=hi=d
    for a,b in zip(cuts[:-1],cuts[1:]):
        mass=sum(y[a:b]); lo+=mass*min(c[a:b]); hi+=mass*max(c[a:b])
    return lo,hi


def choose_second(c,first,prefix_mass,E):
    values=[]
    for j in range(1,6):
        if j==first:
            continue
        a,b=conditional_coefficients(c,first,j)
        values.append((a*prefix_mass+b*(E-prefix_mass),j))
    return min(values)[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path,help="Contains geometry.json, replay_cases.csv and query_trace.json")
    p.add_argument("--data-dir",type=Path,default=ROOT/"work")
    p.add_argument("--lp-cases",type=int,default=12)
    p.add_argument("--output",type=Path,default=HERE/"replay_verification.json")
    args=p.parse_args(); start=time.perf_counter()
    geom_path=args.directory/"geometry.json"; replay_path=args.directory/"replay_cases.csv"; trace_path=args.directory/"query_trace.json"
    cases=json.loads(geom_path.read_text(encoding="utf-8"))["cases"]
    traces={r["id"]:r for r in json.loads(trace_path.read_text(encoding="utf-8"))}
    with replay_path.open(newline="",encoding="utf-8") as h:
        replay={(r["id"],r["policy"]):r for r in csv.DictReader(h)}
    assert len(replay)==5*len(cases) and len(traces)==len(cases)
    raw={}; raw_hashes={}
    for meter in sorted({c["meter"] for c in cases}):
        src=args.data_dir/f"data_blem_{meter.replace('_','-')}.csv"
        with src.open(newline="",encoding="utf-8-sig") as h:
            raw[meter]={int(r["time"]):int(r["energy"]) for r in csv.DictReader(h)}
        raw_hashes[meter]=hashlib.sha256(src.read_bytes()).hexdigest()
    sample=set(np.linspace(0,len(cases)-1,min(args.lp_cases,len(cases)),dtype=int).tolist())
    counts={"cases":0,"policy_rows":0,"sharp_batch_intervals":0,"independent_endpoint_lps":0,
            "exact_policy_matches":0,"all_batch_reference_containment":0}
    errors={"outer_total":0.,"width":0.,"relative_width":0.,"scaled_width":0.,
            "winner_probability":0.,"success_probability":0.,"endpoint_lp":0.,"lp_primal_residual":0.}
    for idx,row in enumerate(cases):
        t0=datetime.fromisoformat(row["day"]).replace(tzinfo=timezone.utc)+timedelta(hours=row["start_hour"])
        stamps=[int((t0+timedelta(hours=h)).timestamp())*1000 for h in range(7)]
        registers=[raw[row["meter"]][s] for s in stamps]
        y=[F(registers[h+1]-registers[h],10**10) for h in range(6)]
        assert min(y)>=0
        E=sum(y); c=[F.from_float(float(v)) for v in row["c"]]; d=F.from_float(float(row["d"]))
        errors["outer_total"]=max(errors["outer_total"],abs(float(E)-row["E"]))
        assert abs(float(E)-row["E"])<=1e-10*max(1.,row["E"])
        g=row["geometry"]; first=g["first"]; greedy_first=g["greedy_first"]
        second=choose_second(c,first,sum(y[:first]),E)
        greedy_second=choose_second(c,greedy_first,sum(y[:greedy_first]),E)
        aq=tuple(sorted((first,second))); gq=tuple(sorted((greedy_first,greedy_second)))
        trace=traces[row["id"]]
        assert trace["first"]==first and trace["second"]==second
        assert trace["first_timestamp_ms"]==stamps[first] and trace["second_timestamp_ms"]==stamps[second]
        assert tuple(trace["chosen_final_cuts"])==aq
        counts["exact_policy_matches"]+=1
        actual=d+sum(v*z for v,z in zip(c,y))
        endpoints={}
        for Q in BATCHES:
            lo,hi=exact_terminal(c,d,y,Q)
            assert lo<=actual<=hi
            endpoints[Q]=(lo,hi)
            counts["all_batch_reference_containment"]+=1
            counts["sharp_batch_intervals"]+=1
            if idx in sample:
                M=np.array([[int(i<k) for i in range(6)] for k in (*Q,6)],dtype=float)
                rhs=M@np.asarray(y,dtype=float)
                for sign,expected in [(1,lo),(-1,hi)]:
                    result=linprog(sign*np.asarray(c,dtype=float),A_eq=M,b_eq=rhs,bounds=(0,None),method="highs")
                    assert result.success
                    recovered=float(d)+sign*result.fun
                    discrepancy=abs(recovered-float(expected))
                    residual=max(float(np.max(np.abs(M@result.x-rhs))),float(max(0.,-np.min(result.x))))
                    errors["endpoint_lp"]=max(errors["endpoint_lp"],discrepancy)
                    errors["lp_primal_residual"]=max(errors["lp_primal_residual"],residual)
                    assert discrepancy<=TOL*max(1.,abs(float(expected)))
                    counts["independent_endpoint_lps"]+=1
        policies={"adaptive":[(aq,1.)],"greedy_adaptive":[(gq,1.)],
                  "det_batch":[(BATCHES[g["det_batch_index"]],1.)],
                  "mean_batch":list(zip(BATCHES,g["mean_weights"])),
                  "uniform_batch":[(Q,.1) for Q in BATCHES]}
        for name,choices in policies.items():
            saved=replay[row["id"],name]
            width=sum(float(endpoints[Q][1]-endpoints[Q][0])*prob for Q,prob in choices)
            relative=width/row["W0"] if row["W0"]>0 else 0.
            scaled=width/row["normalization_scale"]
            expected_winner=0.
            for Q,prob in choices:
                lo,hi=map(float,endpoints[Q]); margin=1e-9*max(1.,abs(lo),abs(hi))
                expected_winner+=prob*int(hi < -margin or lo > margin)
            for key,val in [("mean_width",width),("relative_width",relative),("scaled_width",scaled),("winner_probability",expected_winner)]:
                error_key="width" if key=="mean_width" else key
                error=abs(float(saved[key])-val); errors[error_key]=max(errors[error_key],error)
                assert error<=TOL*max(1.,abs(val)),(row["id"],name,key,error)
            for frac in FRACTIONS:
                cutoff=F.from_float(frac*row["W0"]+1e-9*max(row["W0"],1e-15))
                expected=sum(prob for Q,prob in choices if endpoints[Q][1]-endpoints[Q][0]<=cutoff)
                error=abs(float(saved["success_"+str(frac)])-expected)
                errors["success_probability"]=max(errors["success_probability"],error)
                assert error<=TOL,(row["id"],name,frac,error)
            assert int(saved["requests"])==(2 if row["W0"]>0 else 0)
            counts["policy_rows"]+=1
        counts["cases"]+=1
        if (idx+1)%500==0:
            print(f"independent raw replay {idx+1}/{len(cases)}",flush=True)
    report={"status":"PASS","scope":"Original integer counter replay, exact rational terminal bounds and policy choices; all saved policy metrics; independently assembled endpoint LP sample",
            "directory":str(args.directory),"geometry_sha256":hashlib.sha256(geom_path.read_bytes()).hexdigest(),
            "replay_sha256":hashlib.sha256(replay_path.read_bytes()).hexdigest(),"trace_sha256":hashlib.sha256(trace_path.read_bytes()).hexdigest(),
            "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"raw_source_sha256":raw_hashes,
            "counts":counts,"maximum_errors":errors,"comparison_tolerance":TOL,"lp_case_indices":sorted(sample),
            "runtime_seconds":time.perf_counter()-start}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
