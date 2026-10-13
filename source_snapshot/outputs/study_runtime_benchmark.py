"""Measured API latency for two sharp extrema; not an end-to-end speed claim.

Run after the main study. Inputs and LP matrices are prepared before timing.
Both methods return the lower and upper pairwise MSE difference. Reference
timing includes public-API validation and completion construction; HiGHS timing
includes two solver invocations on prepared matrices. Neither includes model
fitting, input-file parsing, nor output serialization. CPU activity from other
processes is uncontrolled, and this is not a hardware performance study.
"""
from datetime import datetime, timezone
import json
import hashlib
import math
from pathlib import Path
import platform
import time

import numpy as np
import scipy
from scipy.optimize import linprog

from energy_rank_bounds import EnergyBlock, bound_pairwise_mse


def make_case(n, rng):
    truth = rng.uniform(0.05, 5.0, n)
    a = rng.uniform(0.0, 5.0, n)
    b = rng.uniform(0.0, 5.0, n)
    missing = np.sort(rng.choice(n, n // 4, replace=False))
    mask = np.zeros(n, bool)
    mask[missing] = True
    observed = [None if mask[i] else float(truth[i]) for i in range(n)]
    blocks = [EnergyBlock(list(range(start, start + 6)), math.fsum(truth[start:start + 6]))
              for start in range(0, n, 6)]
    coefficient = 2.0 * (b - a) / n
    constant = float(np.sum(a * a - b * b) / n + coefficient[~mask] @ truth[~mask])
    matrix, rhs = [], []
    for start in range(0, n, 6):
        row = (missing >= start) & (missing < start + 6)
        if row.any():
            matrix.append(row.astype(float))
            rhs.append(float(truth[missing[row]].sum()))
    return a.tolist(), b.tolist(), observed, blocks, coefficient[mask], np.array(matrix), np.array(rhs), constant


def reference(case):
    result = bound_pairwise_mse(*case[:4])
    return result.lower, result.upper


def highs(case):
    c, aeq, beq, constant = case[4:]
    lower = linprog(c, A_eq=aeq, b_eq=beq, bounds=(0, None), method="highs")
    upper = linprog(-c, A_eq=aeq, b_eq=beq, bounds=(0, None), method="highs")
    if not lower.success or not upper.success:
        raise AssertionError("HiGHS failed on a feasible benchmark case")
    return constant + lower.fun, constant - upper.fun


def main():
    seed, cases_per_length, repeats = 937143, 30, 3
    rng = np.random.default_rng(seed)
    result = {
        "completed_utc": None,
        "description": "Time for BOTH pairwise MSE-difference extrema, exact disjoint six-hour energy totals, nonnegative missing values, no capacity caps",
        "seed": seed,
        "cases_per_length": cases_per_length,
        "repeats_per_case": repeats,
        "missing_fraction": 0.25,
        "warmup_cases_per_length": 5,
        "timing_scope": "Prepared inputs. Reference public API includes validation and extremal completions; HiGHS includes two solver calls on prepared matrices. Excludes fitting, file parsing, and serialization.",
        "limitations": "Single machine; concurrent process activity is uncontrolled; latencies include solver invocation overhead. No end-to-end training or optimized-vectorized-study speedup claim.",
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "lengths": {},
    }
    for n in [24, 168]:
        cases = [make_case(n, rng) for _ in range(cases_per_length)]
        for case in cases[:5]:
            reference(case)
            highs(case)
        samples = {"reference": [], "highs_two_solves": []}
        max_error = 0.0
        for repeat in range(repeats):
            for index in rng.permutation(cases_per_length):
                case = cases[index]
                outputs = {}
                methods = [("reference", reference), ("highs_two_solves", highs)]
                if (repeat + index) % 2:
                    methods.reverse()
                for name, method in methods:
                    before = time.perf_counter_ns()
                    outputs[name] = method(case)
                    samples[name].append((time.perf_counter_ns() - before) / 1e6)
                difference = float(np.max(np.abs(np.array(outputs["reference"]) - outputs["highs_two_solves"])))
                max_error = max(max_error, difference)
                np.testing.assert_allclose(outputs["reference"], outputs["highs_two_solves"], atol=1e-9, rtol=1e-9)
        result["lengths"][str(n)] = {
            "missing_coordinates": n // 4,
            "maximum_absolute_bound_discrepancy": max_error,
            "methods": {name: {"calls": len(values), "median_ms": float(np.median(values)),
                               "mean_ms": float(np.mean(values)), "p95_ms": float(np.quantile(values, .95)),
                               "samples_ms": values}
                        for name, values in samples.items()},
        }
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    result["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["reference_source_sha256"] = hashlib.sha256((Path(__file__).parent / "energy_rank_bounds.py").read_bytes()).hexdigest()
    output = Path(__file__).with_suffix(".json")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for n, values in result["lengths"].items():
        print(n, {name: round(data["median_ms"], 6) for name, data in values["methods"].items()},
              "max_error", values["maximum_absolute_bound_discrepancy"])


if __name__ == "__main__":
    main()
