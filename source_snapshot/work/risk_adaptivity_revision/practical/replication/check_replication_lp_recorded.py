"""Independent whole-period paired-bound LP checks; no production imports.

Select first and last declared consumers, every gap/pattern/block/tolerance,
and the first seed. Include all six model pairs and all 107 days. Archive
values enter through the saved persistence column. Complete targets create
benchmark masks/totals; they do not enter the LP as hidden observations.
"""
from __future__ import annotations
import hashlib
import itertools
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
import scipy
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MODELS = ["daily", "ridge", "hist_gradient_boosting", "mlp"]
DAY_NS = 86400000000000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    started = time.perf_counter()
    source = ROOT / "outputs/study_holdout_consumers_predictions.csv"
    old_run = json.loads((ROOT/"outputs/study_holdout_consumers.json").read_text())
    assert sha(source) == old_run["output_hashes"][source.name]
    selected = json.loads((ROOT/"outputs/study_holdout_consumers_selection.json").read_text())["selected_ids"]
    data = pd.read_csv(source)
    case_path = HERE/"replication/period_cases.csv"
    cases = pd.read_csv(case_path)
    meters = [selected[0], selected[-1]]
    cases = cases[cases.meter.isin(meters) & (cases.seed == 1103)]
    # Explicit model spelling is checked against the serialized artifact.
    available = [x for x in MODELS if x in data.columns]
    if len(available) != 4:
        raise ValueError(f"Expected frozen model columns {MODELS}; got {list(data.columns)}")
    records = []
    discrepancy = 0.
    normalized_discrepancy = 0.
    feasibility = 0.
    for meter in meters:
        frame = data[data.meter == meter].sort_values("timestamp").copy()
        frame["day"] = pd.to_datetime(frame.timestamp).dt.floor("D")
        archive = {pd.Timestamp(t).value-DAY_NS: float(v)
                   for t, v in frame[["timestamp", "daily"]].itertuples(index=False, name=None)}
        group_keys = ["gap_hours", "pattern", "block_hours", "total_tolerance"]
        for (gap, pattern, block, tau), expected in cases[cases.meter == meter].groupby(group_keys):
            all_pred, all_obs = [], []
            group_constraints = []
            global_index = 0
            for day, group in frame.groupby("day", sort=True):
                group = group.sort_values("timestamp")
                truth = group.truth_kwh.to_numpy()
                pred = group[MODELS].to_numpy().T
                gi = (2,6,12).index(int(gap))
                rng = np.random.default_rng(np.random.SeedSequence([1103, int(pd.Timestamp(day).value//DAY_NS), gi]))
                mask = np.zeros(24, dtype=bool)
                if pattern == "contiguous":
                    first = int(rng.integers(0,25-gap)); mask[first:first+gap] = True
                elif pattern == "scattered":
                    mask[rng.choice(24,gap,replace=False)] = True
                else:
                    mask[np.argsort(truth,kind="stable")[-gap:]] = True
                obs = truth.copy(); obs[mask] = np.nan
                for i, stamp in enumerate(group.timestamp):
                    if np.isnan(obs[i]) and pd.Timestamp(stamp).value in archive:
                        obs[i] = archive[pd.Timestamp(stamp).value]
                for first in range(0,24,block):
                    indices = np.arange(first,first+block)
                    total = float(truth[indices].sum())
                    known_sum = float(np.nansum(obs[indices]))
                    unknown = indices[np.isnan(obs[indices])]+global_index
                    lower = max(0., (1-tau)*total-known_sum)
                    upper = max(0., (1+tau)*total-known_sum)
                    if len(unknown):
                        group_constraints.append((unknown,lower,upper))
                    else:
                        assert lower <= 1e-8*max(1.,total)
                all_pred.append(pred); all_obs.append(obs)
                global_index += 24
            pred = np.concatenate(all_pred,axis=1)
            obs = np.concatenate(all_obs)
            unknown = np.flatnonzero(np.isnan(obs))
            position = {int(x):i for i,x in enumerate(unknown)}
            A, b = [], []
            for indices, lower, upper in group_constraints:
                row = np.zeros(len(unknown))
                row[[position[int(i)] for i in indices]] = 1.
                A.extend([row,-row]); b.extend([upper,-lower])
            A,b = np.asarray(A),np.asarray(b)
            for row in expected.itertuples(index=False):
                ia,ib = MODELS.index(row.model_a),MODELS.index(row.model_b)
                delta = pred[ia]-pred[ib]
                known = np.isfinite(obs)
                constant = float(np.sum(delta[known]*((pred[ia,known]-obs[known])+(pred[ib,known]-obs[known]))))
                constant += float(np.sum(delta[unknown]*(pred[ia,unknown]+pred[ib,unknown])))
                c = -2*delta[unknown]
                if len(unknown):
                    lo = linprog(c,A_ub=A,b_ub=b,bounds=(0,None),method="highs",
                                 options={"primal_feasibility_tolerance":1e-9,"dual_feasibility_tolerance":1e-9})
                    hi = linprog(-c,A_ub=A,b_ub=b,bounds=(0,None),method="highs",
                                 options={"primal_feasibility_tolerance":1e-9,"dual_feasibility_tolerance":1e-9})
                    assert lo.success and hi.success
                    ends = np.array([constant+lo.fun,constant-hi.fun])/global_index
                    feasibility = max(feasibility,float(np.max(A@lo.x-b)),float(np.max(A@hi.x-b)),
                                      float(np.max(-lo.x)),float(np.max(-hi.x)))
                else:
                    ends = np.repeat(constant/global_index,2)
                expected_ends = np.array([row.paired_lower,row.paired_upper])
                diff = float(np.max(np.abs(ends-expected_ends)))
                scale = max(1.,float(np.max(np.abs(expected_ends))))
                discrepancy = max(discrepancy,diff)
                normalized_discrepancy = max(normalized_discrepancy,diff/scale)
                assert diff <= 1e-8*scale
                records.append(dict(meter=meter,gap_hours=gap,pattern=pattern,block_hours=block,
                    total_tolerance=tau,model_a=row.model_a,model_b=row.model_b,
                    unknown_coordinates=len(unknown),lp_lower=ends[0],lp_upper=ends[1],
                    production_lower=row.paired_lower,production_upper=row.paired_upper,
                    absolute_difference=diff,normalized_difference=diff/scale))
    assert len(records) == 432
    pd.DataFrame(records).to_csv(HERE/"replication/independent_lp_cases.csv",index=False,lineterminator="\n")
    result = dict(status="passed",source_sha256=sha(source),period_cases_sha256=sha(case_path),
        script_sha256=sha(__file__),consumers=meters,period_comparisons=len(records),
        linear_programs=2*len(records),seed=1103,all_gaps_patterns_blocks_tolerances=True,
        max_absolute_endpoint_difference=discrepancy,max_normalized_endpoint_difference=normalized_discrepancy,
        max_absolute_constraint_violation=feasibility,checking_tolerance="1e-8*max(1,abs(production endpoints))",
        highs_primal_dual_feasibility_tolerance=1e-9,scipy=scipy.__version__,
        elapsed_seconds=time.perf_counter()-started,
        scope="Independent whole-period linear-program representation checks paired endpoints only; no production imports. The separate-loss quadratic extrema and model training are not independently rerun by this checker.")
    (HERE/"replication/independent_lp_verification.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__": main()
