"""Post-analysis exact two-batch covering certificate and separate raw replay.

Every policy is selected from coefficient geometry alone, before the raw
register file is opened. No original study or prespecified output is edited.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
from pathlib import Path

from check_counter_adaptive import conditional_coefficients, exact_envelope, width

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
ROOT=HERE.parents[3]
RAW_HASHES={
    "consumer_00000001":"9228795c6369ce144fbb929f9d413397545f86e3a95d2f9a0f27c92f1d55ad8d",
    "consumer_00000002":"93d142217c74ab2c12a98035b3ea178ead234fec0b71942e8e90db5b7e6a2ef3",
    "consumer_00000003":"db69719d2262ebeb6df39abafffca2805c8a03b1b4777f86eb8aa78acf578b6c",
}


def make_cover(c,k,tau):
    """Exact good intervals for conditional worst widths, deterministic ties."""
    intervals=[]
    for j in range(1,6):
        if j==k:
            continue
        a,b=conditional_coefficients(c,k,j)
        slope=a-b
        lo,hi=F(0),F(1)
        if slope==0:
            if b>tau:
                continue
        elif slope>0:
            hi=min(hi,(tau-b)/slope)
        else:
            lo=max(lo,(tau-b)/slope)
        if lo>hi:
            continue
        intervals.append({"j":j,"a":a,"b":b,"lo":lo,"hi":hi})
    full=[z for z in intervals if z["lo"]==0 and z["hi"]==1]
    if full:
        chosen=[min(full,key=lambda z:z["j"])]
    else:
        prefix=min((z for z in intervals if z["lo"]==0),key=lambda z:(-z["hi"],z["j"]))
        suffix=min((z for z in intervals if z["hi"]==1),key=lambda z:(z["lo"],z["j"]))
        assert prefix["hi"]>=suffix["lo"]
        chosen=[prefix,suffix]
        assert len({z["j"] for z in chosen})==2
    for z in chosen:
        assert z["a"]*z["lo"]+z["b"]*(1-z["lo"])<=tau
        assert z["a"]*z["hi"]+z["b"]*(1-z["hi"])<=tau
    return intervals,chosen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry",type=Path,nargs="+",default=[STUDY/"pilot"/"geometry.json",STUDY/"continuation"/"geometry.json"])
    parser.add_argument("--data-dir",type=Path,default=ROOT/"work")
    parser.add_argument("--output",type=Path,default=HERE/"half_cover_verification.json")
    args=parser.parse_args()
    started=time.perf_counter(); rows=[]; all_guaranteed=0; covers_one=0
    source_hashes={}; seen=set()
    # Policy construction stage: forecasts and geometry only, no raw replies.
    for p in args.geometry:
        p=p.resolve()
        source=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
        source_hashes[source]=hashlib.sha256(p.read_bytes()).hexdigest()
        for case in json.loads(p.read_text(encoding="utf-8"))["cases"]:
            assert case["id"] not in seen
            seen.add(case["id"])
            phase=case["phase"]
            entry=next(z for z in case["geometry"]["precision"] if z["fraction"]==.5)
            if not entry["adaptive_guarantee"]:
                continue
            all_guaranteed+=1
            orig=[F.from_float(float(x)) for x in case["c"]]
            cr=max(orig)-min(orig)
            assert cr>0
            c=[(z-min(orig))/cr for z in orig]
            k=case["geometry"]["first"]
            assert exact_envelope(c,k)[0]<=F(1,2)
            intervals,chosen=make_cover(c,k,F(1,2))
            covers_one+=len(chosen)==1
            if not entry["separation_le_70"]:
                continue
            probs=[F(1,len(chosen))]*len(chosen)
            Qs=[tuple(sorted((k,z["j"]))) for z in chosen]
            # Independently reconstruct the exact adverse upper bound.
            w=[F.from_float(max(0.,float(x))) for x in entry["weights"]]
            w=[x/sum(w) for x in w]
            import itertools
            allQ=list(itertools.combinations(range(1,6),2))
            U=max(sum(w[h]*int(width(c,[F(i==h) for i in range(6)],Q)<=F(1,2)) for h in range(6)) for Q in allQ)
            assert U==F(1,2)
            assert len(chosen)==2
            rows.append({"id":case["id"],"meter":case["meter"],"day":case["day"],
                         "phase":phase,"start_hour":case["start_hour"],
                         "source_geometry":source,
                         "model_a":case["model_a"],"model_b":case["model_b"],
                         "first":k,"batches":[list(Q) for Q in Qs],
                         "probabilities":[str(z) for z in probs],
                         "cover_intervals":[{"second":z["j"],"left":str(z["lo"]),"right":str(z["hi"]),
                                             "alpha":str(z["a"]),"beta":str(z["b"])} for z in chosen],
                         "overlap_length":str(chosen[0]["hi"]-chosen[1]["lo"]),
                         "adaptive_guarantee_exact":str(exact_envelope(c,k)[0]),
                         "batch_optimum_exact":str(U),
                         "adverse_weights_exact":[str(z) for z in w],
                         "_coefficients":c})
    assert len(seen)==4914 and all_guaranteed==4661 and len(rows)==290
    # Select examples only by source ordering, before opening raw replies.
    earliest_three={meter:sorted([r for r in rows if r["meter"]==meter],
                                key=lambda r:(r["day"],r["start_hour"],r["model_a"],r["model_b"]))[:3]
                    for meter in sorted({r["meter"] for r in rows})}
    representative=[]; earliest_nine=[]
    for meter,selected in earliest_three.items():
        for pos,r in enumerate(selected):
            prefix,suffix=r["cover_intervals"]
            left=F(suffix["left"]); right=F(prefix["right"])
            nice=next((x for x in [F(1,4),F(1,2),F(3,4)] if left<=x<=right),(left+right)/2)
            assert left<=nice<=right
            pa,pb=F(prefix["alpha"]),F(prefix["beta"])
            sa,sb=F(suffix["alpha"]),F(suffix["beta"])
            branch_bound=max(pb,pa*nice+pb*(1-nice),sa*nice+sb*(1-nice),sa)
            assert branch_bound<=F(1,2)
            witness={k:r[k] for k in ["id","meter","day","phase","start_hour","model_a","model_b","first","batches","probabilities","source_geometry","cover_intervals","batch_optimum_exact"]}
            witness.update(switch_fraction=str(nice),normalized_first_answer="t=prefix_mass/E",
                           second_if_t_le_switch=prefix["second"],second_otherwise=suffix["second"],
                           two_branch_guarantee_exact=str(branch_bound),
                           scope="Sufficient two-branch precision witness, not necessarily the full conditional-width-minimizing policy")
            earliest_nine.append(witness)
            if pos==0:
                representative.append(witness)
    assert [z["switch_fraction"] for z in representative]==["1/4","1/2","3/4"]
    # Raw replay begins only after all two-batch mixtures have been selected.
    raw={}; raw_hashes={}
    for meter in sorted({r["meter"] for r in rows}):
        p=args.data_dir/f"data_blem_{meter.replace('_','-')}.csv"
        assert hashlib.sha256(p.read_bytes()).hexdigest()==RAW_HASHES[meter],f"Unexpected raw source hash: {p}"
        with p.open(newline="",encoding="utf-8-sig") as h:
            raw[meter]={int(z["time"]):int(z["energy"]) for z in csv.DictReader(h)}
        raw_hashes[meter]=hashlib.sha256(p.read_bytes()).hexdigest()
    groups={"overall":defaultdict(list),"meter":defaultdict(list),"phase":defaultdict(list),"pair":defaultdict(list)}
    for r in rows:
        t0=datetime.fromisoformat(r["day"]).replace(tzinfo=timezone.utc)+timedelta(hours=r["start_hour"])
        cv=[raw[r["meter"]][int((t0+timedelta(hours=h)).timestamp())*1000] for h in range(7)]
        y=[F(cv[h+1]-cv[h],cv[6]-cv[0]) for h in range(6)]
        assert min(y)>=0 and sum(y)==1
        c=r.pop("_coefficients")
        ws=[width(c,y,tuple(Q)) for Q in r["batches"]]
        exact_success=sum(F(p)*int(w<=F(1,2)) for p,w in zip(r["probabilities"],ws))
        mean_width=sum(F(p)*w for p,w in zip(r["probabilities"],ws))
        assert exact_success>=F(1,2)
        r["recorded_success_exact"]=str(exact_success)
        r["recorded_relative_width_exact"]=str(mean_width)
        for name,key in [("overall","all"),("meter",r["meter"]),("phase",r["phase"]),("pair",r["model_a"]+" / "+r["model_b"])]:
            groups[name][key].append((exact_success,mean_width))
    summaries={name:[{"group":key,"cases":len(vals),
                       "mean_recorded_success_exact":str(sum(z[0] for z in vals)/len(vals)),
                       "mean_recorded_success":float(sum(z[0] for z in vals)/len(vals)),
                       "mean_recorded_relative_width":float(sum(z[1] for z in vals)/len(vals)),
                       "records_success_one":sum(z[0]==1 for z in vals),
                       "records_success_half":sum(z[0]==F(1,2) for z in vals)}
                      for key,vals in entries.items()] for name,entries in groups.items()}
    report={"status":"PASS","scope":"Post-analysis structural half-success certificate and descriptive raw replay; original prespecified baselines unchanged",
            "geometry_hashes":source_hashes,"source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "raw_source_hashes":raw_hashes,"all_primary_guarantees_checked":all_guaranteed,
            "one_batch_covers_among_all_guarantees":covers_one,"strong_cases":len(rows),
            "distribution":{"minimum":"1/2","q1":"1/2","median":"1/2","q3":"1/2","maximum":"1/2",
                            "exactly_half":len(rows),"below_point4":0,"below_point3":0},
            "representative_witnesses":representative,
            "earliest_three_per_meter":earliest_nine,
            "summaries":summaries,"runtime_seconds":time.perf_counter()-started,
            "cover_witnesses":rows}
    out=args.output
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    names={"daily":"Pers.","ridge":"Ridge","hist_gradient_boosting":"HGB","mlp":"MLP"}
    table=["% t is the queried prefix mass divided by E. Sufficient two-branch witnesses.",
           "% Selected by earliest date, block start, and lexicographic model pair per meter.",
           "% Meter & Date/start UTC & Pair & First k & Switch r & Second if t<=r / otherwise & equal batch support & bound W/W0"]
    for z in representative:
        pair=names[z["model_a"]]+"/"+names[z["model_b"]]
        batches=" / ".join("$\\{"+",".join(map(str,Q))+"\\}$" for Q in z["batches"])
        table.append(f"{int(z['meter'][-1])} & {z['day']}/{z['start_hour']:02d} & {pair} & {z['first']} & ${z['switch_fraction']}$ & {z['second_if_t_le_switch']} / {z['second_otherwise']} & {batches} & {float(F(z['two_branch_guarantee_exact'])):.4f} \\\\")
    out.with_name("half_cover_witness_table_rows.tex").write_text("\n".join(table)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in {"cover_witnesses","earliest_three_per_meter","representative_witnesses"}},indent=2))


if __name__=="__main__":
    main()
