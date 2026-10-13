"""Independent sample re-evaluation of both replication bound comparators.

No production study bounds, archive closure, or replication functions are
imported. Paired bounds use the separate standard-library reference API.
Individual-loss minima use independently coded scalar water filling; maxima
enumerate simplex vertices at both allowed endpoint masses.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta
import hashlib
import itertools
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd

from audit_api import ROOT, REFERENCE_API, reference

HERE = Path(__file__).resolve().parent
MODELS = ("daily", "ridge", "hist_gradient_boosting", "mlp")
PAIRS = tuple(itertools.combinations(range(4), 2))
SCENARIOS = ((6, "contiguous", 1103, 6, 0.0), (12, "scattered", 3301, 24, .05))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def closure(initial, totals, blocksize, tau):
    visible = list(initial)
    residual_blocks = []
    for g, total in enumerate(totals):
        ids = list(range(g*blocksize, (g+1)*blocksize))
        missing = [i for i in ids if visible[i] is None]
        mass = float(total) - math.fsum(visible[i] for i in ids if visible[i] is not None)
        assert mass >= -1e-9*max(1.0, abs(float(total)))
        mass = max(0.0, mass)
        lower, upper = max(0.0, mass-tau*float(total)), mass+tau*float(total)
        if missing and (upper == 0 or (tau == 0 and len(missing) == 1)):
            for i in missing:
                visible[i] = 0.0 if upper == 0 else mass
        elif missing:
            residual_blocks.append((missing, lower, upper))
    return visible, residual_blocks


def single_loss_bounds(prediction, visible, blocks):
    minimum = maximum = math.fsum((float(p)-y)**2 for p,y in zip(prediction,visible) if y is not None)
    for ids, lower, upper in blocks:
        p = [float(prediction[i]) for i in ids]
        unconstrained = [max(0.0, value) for value in p]
        mass = math.fsum(unconstrained)
        target = min(upper, max(lower, mass))
        if lower <= mass <= upper:
            best = unconstrained
        elif target == 0:
            best = [0.0]*len(p)
        else:
            left, right = min(p)-target-1.0, max(p)+1.0
            for _ in range(100):
                multiplier = (left+right)/2
                if math.fsum(max(0.0, value-multiplier) for value in p) > target:
                    left = multiplier
                else:
                    right = multiplier
            best = [max(0.0, value-(left+right)/2) for value in p]
            assert abs(math.fsum(best)-target) <= 1e-9*max(1.0,target)
        minimum += math.fsum((value-y)**2 for value,y in zip(p,best))
        candidates = []
        for total in (lower,upper):
            for at in range(len(p)):
                candidates.append(math.fsum((value-(total if j==at else 0.0))**2 for j,value in enumerate(p)))
        maximum += max(candidates)
    return minimum/len(prediction), maximum/len(prediction)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE/"replication_independent_verification.json")
    parser.add_argument("--replication-dir", type=Path, default=ROOT/"work/risk_adaptivity_revision/practical/replication")
    args = parser.parse_args()
    args.replication_dir = args.replication_dir.resolve()
    args.output = args.output.resolve()
    started = time.perf_counter()
    prediction_path = ROOT/"outputs/study_holdout_consumers_predictions.csv"
    selection_path = ROOT/"outputs/study_holdout_consumers_selection.json"
    ledger_path = args.replication_dir/"period_cases.csv"
    report_path = args.replication_dir/"verification.json"
    original = json.loads(report_path.read_text())
    for path, expected in original["input_sha256"].items():
        assert sha(ROOT/path) == expected, path
    for filename, expected in original["output_sha256"].items():
        assert sha(args.replication_dir/filename) == expected, filename
    frame = pd.read_csv(prediction_path)
    selected = json.loads(selection_path.read_text())["selected_ids"]
    ledger = pd.read_csv(ledger_path)
    assert len(frame)==77040 and len(selected)==30 and len(ledger)==19440
    source_hashes = {str(p.relative_to(ROOT)).replace("\\","/"):sha(p) for p in
        (Path(__file__), HERE/"audit_api.py", REFERENCE_API, prediction_path, selection_path, ledger_path, report_path)}
    full_summaries = []
    for tau, expected in zip((0.0,.05), ((7753,2527),(7424,2010))):
        part = ledger[ledger.total_tolerance==tau]
        assert len(part)==9720
        for name, lower, upper in (("paired", "paired_lower", "paired_upper"), ("separate","separate_lower","separate_upper")):
            margin = 1e-9*np.maximum(1.0,np.maximum(np.abs(part[lower]),np.abs(part[upper])))
            decisions = np.where(part[lower]>margin,1,np.where(part[upper]<-margin,-1,0))
            np.testing.assert_array_equal(decisions,part[name+"_decision"])
            assert not np.any((decisions!=0)&(decisions!=np.sign(part.reference_gap)))
        p, s = part.paired_decision.to_numpy()!=0,part.separate_decision.to_numpy()!=0
        assert (int(p.sum()),int(s.sum()))==expected
        assert not np.any(s&~p)
        full_summaries.append({"total_tolerance":tau,"comparisons":len(part),"paired_certified":int(p.sum()),
            "separate_certified":int(s.sum()),"separate_only":int((s&~p).sum())})

    max_pair_abs = max_pair_norm = max_sep_abs = max_sep_norm = 0.0
    checked = []
    daily_count = copied_count = api_calls = individual_calls = 0
    for meter in selected:
        part = frame[frame.meter==meter].sort_values("timestamp")
        # Independently construct archive lookup from timestamp/daily only.
        archive = {datetime.fromisoformat(row.timestamp):float(row.daily) for row in part.itertuples()}
        for gap,pattern,seed,bs,tau in SCENARIOS:
            sums = np.zeros((4,6))
            days = 0
            for day, group in part.groupby(part.timestamp.str[:10],sort=True):
                group=group.sort_values("timestamp")
                assert len(group)==24
                days+=1
                daily_count+=1
                truth = group.truth_kwh.to_numpy()
                predictions = group[list(MODELS)].to_numpy().T
                gi=(2,6,12).index(gap)
                day_number = (datetime.fromisoformat(day)-datetime(1970,1,1)).days
                rng=np.random.default_rng(np.random.SeedSequence([seed,day_number,gi]))
                missing = np.zeros(24,dtype=bool)
                if pattern=="contiguous":
                    first=int(rng.integers(0,25-gap));missing[first:first+gap]=True
                else:
                    missing[rng.choice(24,gap,replace=False)]=True
                visible=[None if missing[i] else float(y) for i,y in enumerate(truth)]
                for i,timestamp in enumerate(group.timestamp):
                    source=datetime.fromisoformat(timestamp)+timedelta(days=1)
                    if visible[i] is None and source in archive:
                        visible[i]=archive[source]
                        copied_count+=1
                # Totals are the declared manufactured benchmark inputs, as in protocol.
                totals=truth.reshape(-1,bs).sum(axis=1)
                visible, residual=closure(visible,totals,bs,tau)
                if not any(v is None for v in visible):
                    losses=[math.fsum((float(p)-y)**2 for p,y in zip(pred,visible))/24 for pred in predictions]
                    values=np.array([losses[a]-losses[b] for a,b in PAIRS])
                    sums+=values[None,:]
                    continue
                blocks=[reference.EnergyBlock(ids,lower,upper) for ids,lower,upper in residual]
                individual=[single_loss_bounds(p,visible,residual) for p in predictions]
                individual_calls+=4
                for k,(a,b) in enumerate(PAIRS):
                    pair=reference.bound_pairwise_mse(predictions[a],predictions[b],visible,blocks)
                    sums[:,k] += (pair.lower,pair.upper,individual[a][0]-individual[b][1],individual[a][1]-individual[b][0])
                    api_calls+=1
            assert days==107
            averages=sums/days
            for k,(a,b) in enumerate(PAIRS):
                row=ledger[(ledger.meter==meter)&(ledger.gap_hours==gap)&(ledger.pattern==pattern)&(ledger.seed==seed)
                    &(ledger.block_hours==bs)&(ledger.total_tolerance==tau)&(ledger.model_a==MODELS[a])&(ledger.model_b==MODELS[b])]
                assert len(row)==1
                target=row.iloc[0]
                expected=np.array([target.paired_lower,target.paired_upper,target.separate_lower,target.separate_upper])
                difference=np.abs(averages[:,k]-expected)
                scale=np.maximum(1.0,np.abs(expected))
                assert np.all(difference<=2e-8*scale),(meter,SCENARIOS,MODELS[a],MODELS[b],difference)
                max_pair_abs=max(max_pair_abs,float(max(difference[:2])))
                max_pair_norm=max(max_pair_norm,float(max((difference/scale)[:2])))
                max_sep_abs=max(max_sep_abs,float(max(difference[2:])))
                max_sep_norm=max(max_sep_norm,float(max((difference/scale)[2:])))
                checked.append({"meter":meter,"gap_hours":gap,"pattern":pattern,"seed":seed,"block_hours":bs,
                    "total_tolerance":tau,"model_a":MODELS[a],"model_b":MODELS[b],
                    "independent_bounds":averages[:,k].tolist(),"reported_bounds":expected.tolist()})
    assert len(checked)==360
    result={"status":"PASS","whole_ledger_comparisons_checked":len(ledger),"ledger_summaries":full_summaries,
        "consumers_independently_recomputed":len(selected),"fixed_scenarios":SCENARIOS,
        "daily_snapshots_recomputed":daily_count,"period_comparisons_independently_recomputed":len(checked),
        "reference_API_calls":api_calls,"independent_individual_loss_calls":individual_calls,
        "direct_copy_occurrences":copied_count,"max_paired_absolute_discrepancy":max_pair_abs,
        "max_paired_normalized_discrepancy":max_pair_norm,"max_separate_absolute_discrepancy":max_sep_abs,
        "max_separate_normalized_discrepancy":max_sep_norm,"tolerance":"2e-8*max(1,abs(reported endpoint))",
        "elapsed_seconds":time.perf_counter()-started,"source_sha256":source_hashes,"checked_cases":checked,
        "scope":"Independent sampled recomputation of paired and separate-loss endpoints for all30consumers on two fixed scenarios. "
            "No production bound or closure function imported; common frozen predictions and declared masks/totals retained. "
            "All19440ledger decisions and counts checked. This does not independently recompute every scenario, train forecasts, "
            "or establish an untouched population or production cost benefit."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("checked_cases","source_sha256")},indent=2))


if __name__=="__main__":main()
