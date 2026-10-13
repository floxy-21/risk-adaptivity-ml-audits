"""Fresh full archive certification grid on the existing additional consumers."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "outputs"))
from run_energy_rank_study import bounds, MODELS, P0, P1
from study_period_archive import close_observations
from study_archive_access import persistence_lookup, reveal_from_archive, DAY_NS

GAPS=(2,6,12)
PATTERNS=("contiguous","scattered","high_demand")
SEEDS=(1103,2207,3301)
BLOCKS=(6,24)
TAUS=(0.,.05)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE/"replication")
    args=parser.parse_args()
    out=args.output_dir
    out.mkdir(parents=True,exist_ok=True)
    inputs=[ROOT/"outputs/study_holdout_consumers_predictions.csv",
            ROOT/"outputs/study_holdout_consumers_selection.json",
            ROOT/"outputs/study_holdout_consumers.json",
            ROOT/"outputs/run_energy_rank_study.py",
            ROOT/"outputs/study_period_archive.py",
            ROOT/"outputs/study_archive_access.py",
            HERE/"replication_protocol.txt",Path(__file__)]
    hashes={str(p.relative_to(ROOT)).replace("\\","/"):sha(p) for p in inputs}
    run_manifest=dict(started_utc=datetime.now(timezone.utc).isoformat(),input_sha256=hashes,
        protocol_mtime_utc=datetime.fromtimestamp((HERE/"replication_protocol.txt").stat().st_mtime,timezone.utc).isoformat(),
        grid=dict(gaps=GAPS,patterns=PATTERNS,seeds=SEEDS,blocks=BLOCKS,tolerances=TAUS),
        status="running")
    (out/"run_manifest.json").write_text(json.dumps(run_manifest,indent=2)+"\n")
    start=time.perf_counter()
    frame=pd.read_csv(inputs[0])
    selected=json.loads(inputs[1].read_text())["selected_ids"]
    assert sorted(frame.meter.unique())==sorted(selected) and len(selected)==30
    assert len(frame)==77040
    frame["day"]=pd.to_datetime(frame.timestamp).dt.floor("D")
    scenarios=[(gi,gap,pattern,seed,bs,tau) for gi,gap in enumerate(GAPS)
               for pattern in PATTERNS for seed in SEEDS for bs in BLOCKS for tau in TAUS]
    rows=[]
    counts=dict(meter_days=0, day_scenarios=0, fully_archived_days=0, bound_calls=0,
                source_copy_checks=0, reference_enclosures=0, interval_nesting=0)
    max_enclosure=0.
    max_nesting=0.
    meter_timings=[]
    for meter in selected:
        meter_start=time.perf_counter()
        part=frame[frame.meter==meter].sort_values("timestamp")
        lookup=persistence_lookup(part[["timestamp","daily"]])
        sums=np.zeros((len(scenarios),4,6))
        reference=np.zeros(6)
        ndays=0
        for day, group in part.groupby("day",sort=True):
            group=group.sort_values("timestamp")
            assert len(group)==24
            ndays+=1
            counts["meter_days"]+=1
            pred=group[MODELS].to_numpy().T
            truth=group.truth_kwh.to_numpy()
            timestamps=group.timestamp.tolist()
            losses=np.mean((pred-truth)**2,axis=1)
            ref=losses[P0]-losses[P1]
            reference+=ref
            copies, found=reveal_from_archive(timestamps, np.full(24,np.nan),lookup)
            if found:
                np.testing.assert_array_equal(copies[list(found)],truth[list(found)])
                counts["source_copy_checks"]+=len(found)
            # Every target already has a direct source row: both intervals are
            # points under every mask/total tolerance. No hidden value supplies it.
            if len(found)==24:
                counts["fully_archived_days"]+=1
                copy_loss=np.mean((pred-copies)**2,axis=1)
                value=copy_loss[P0]-copy_loss[P1]
                sums+=value[None,None,:]
                counts["day_scenarios"]+=len(scenarios)
                continue
            totals={bs:truth.reshape(-1,bs).sum(axis=1) for bs in BLOCKS}
            masks={}
            for gi,gap in enumerate(GAPS):
                for pattern in PATTERNS:
                    for seed in SEEDS:
                        rng=np.random.default_rng(np.random.SeedSequence([seed,int(pd.Timestamp(day).value//DAY_NS),gi]))
                        missing=np.zeros(24,dtype=bool)
                        if pattern=="contiguous":
                            first=int(rng.integers(0,25-gap)); missing[first:first+gap]=True
                        elif pattern=="scattered": missing[rng.choice(24,gap,replace=False)]=True
                        else: missing[np.argsort(truth,kind="stable")[-gap:]]=True
                        observed=truth.copy(); observed[missing]=np.nan
                        augmented,_=reveal_from_archive(timestamps,observed,lookup)
                        masks[(gi,pattern,seed)]=augmented
            for ix,(gi,gap,pattern,seed,bs,tau) in enumerate(scenarios):
                observed,_,_,_=close_observations(masks[(gi,pattern,seed)],totals[bs],bs,tau)
                # Production evaluator receives no complete target vector.
                result=np.asarray(bounds(pred,observed,totals[bs],bs,tau))
                counts["bound_calls"]+=1
                lo,hi,ilo,ihi=result
                scale=np.maximum(1.,np.abs(ref))
                enclosure=max(float(np.max(lo-ref)),float(np.max(ref-hi)),
                              float(np.max(ilo-ref)),float(np.max(ref-ihi)))
                max_enclosure=max(max_enclosure,enclosure)
                assert np.all(lo<=ref+1e-8*scale) and np.all(hi>=ref-1e-8*scale)
                assert np.all(ilo<=ref+1e-8*scale) and np.all(ihi>=ref-1e-8*scale)
                nesting_scale=np.maximum(1.,np.max(np.abs(result),axis=0))
                assert np.all(ilo<=lo+1e-8*nesting_scale) and np.all(ihi>=hi-1e-8*nesting_scale)
                max_nesting=max(max_nesting,float(np.max(ilo-lo)),float(np.max(hi-ihi)))
                counts["reference_enclosures"]+=12
                counts["interval_nesting"]+=6
                sums[ix]+=result
                counts["day_scenarios"]+=1
        assert ndays==107
        means=sums/ndays
        reference/=ndays
        for ix,(_,gap,pattern,seed,bs,tau) in enumerate(scenarios):
            for pair in range(6):
                lo,hi,ilo,ihi=means[ix,:,pair]
                pdirection=1 if lo>1e-9*max(1.,abs(lo),abs(hi)) else -1 if hi < -1e-9*max(1.,abs(lo),abs(hi)) else 0
                sdirection=1 if ilo>1e-9*max(1.,abs(ilo),abs(ihi)) else -1 if ihi < -1e-9*max(1.,abs(ilo),abs(ihi)) else 0
                wrong_p=bool(pdirection and pdirection!=np.sign(reference[pair]))
                wrong_s=bool(sdirection and sdirection!=np.sign(reference[pair]))
                assert not wrong_p and not wrong_s
                assert sdirection==0 or sdirection==pdirection
                rows.append(dict(cohort="portugal_additional_existing",meter=meter,
                    model_a=MODELS[P0[pair]],model_b=MODELS[P1[pair]],gap_hours=gap,
                    pattern=pattern,seed=seed,block_hours=bs,total_tolerance=tau,
                    days=ndays,full_target_denominator=24*ndays,
                    paired_lower=lo,paired_upper=hi,separate_lower=ilo,separate_upper=ihi,
                    reference_gap=reference[pair],paired_decision=pdirection,
                    separate_decision=sdirection,paired_wrong=int(wrong_p),separate_wrong=int(wrong_s)))
        elapsed=time.perf_counter()-meter_start
        meter_timings.append(dict(meter=meter,seconds=elapsed))
        print(json.dumps(dict(meter=meter,finished=len(meter_timings),seconds=elapsed)),flush=True)
    result=pd.DataFrame(rows)
    assert len(result)==19440
    result.to_csv(out/"period_cases.csv",index=False,lineterminator="\n")
    summaries=[]
    for tau, part in result.groupby("total_tolerance",sort=True):
        p=part.paired_decision.to_numpy()!=0
        s=part.separate_decision.to_numpy()!=0
        n=len(part)
        summaries.append(dict(total_tolerance=float(tau),comparisons=n,
            paired_certified=int(p.sum()),separate_certified=int(s.sum()),
            paired_unresolved=int((~p).sum()),separate_unresolved=int((~s).sum()),
            paired_only=int((p&~s).sum()),separate_only=int((s&~p).sum()),
            paired_coverage_percent=100*p.mean(),separate_coverage_percent=100*s.mean(),
            unresolved_reduction_percent=100*(p.sum()-s.sum())/(~s).sum(),
            paired_wrong=int(part.paired_wrong.sum()),separate_wrong=int(part.separate_wrong.sum()),
            paired_mean_width=float((part.paired_upper-part.paired_lower).mean()),
            separate_mean_width=float((part.separate_upper-part.separate_lower).mean())))
    pd.DataFrame(summaries).to_csv(out/"summary.csv",index=False,lineterminator="\n")
    for path in inputs: assert sha(path)==hashes[str(path.relative_to(ROOT)).replace("\\","/")]
    report=dict(status="passed",completed_utc=datetime.now(timezone.utc).isoformat(),
        input_sha256=hashes,counts=counts,consumers=30,hourly_targets=77040,
        comparisons=len(result),summaries=summaries,meter_timings=meter_timings,
        elapsed_seconds=time.perf_counter()-start,max_absolute_enclosure_violation=max_enclosure,
        max_absolute_nesting_violation=max_nesting,
        decision_margin="1e-9*max(1,abs(lower),abs(upper))",
        checking_tolerance="1e-8 times corresponding reference/nesting scale",
        output_sha256={name:sha(out/name) for name in ["period_cases.csv","summary.csv"]},
        interpretation="Fresh extended comparison-grid execution using frozen forecasts from30existing additional Portugal consumers. Same source/calendar; earlier primary recovery outcomes were already inspected. No untouched-source or blind validation claim, model refit, additional queries, deployment savings, or predicted accuracy improvement. High-demand masks use serialized targets under this newly fixed grid protocol; repeated seed-labelled deterministic masks are dependent.")
    (out/"verification.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(dict(status="passed",summaries=summaries,elapsed_seconds=report["elapsed_seconds"]),indent=2))


if __name__=="__main__":main()
