"""Small measured recovery-policy API benchmark with prepared feasible blocks."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import numpy as np
from study_recovery import optimal_queries, prepare_blocks, sha, worst_width


def main():
    rng = np.random.default_rng(861403)
    results = {}
    for gap in [6, 12]:
        cases = []
        for _ in range(30):
            a, b, truth = rng.uniform(0.01, 5., (3, 24))
            start = int(rng.integers(0, 25 - gap))
            observed = truth.copy()
            observed[start:start + gap] = np.nan
            totals = truth.reshape(-1, 6).sum(axis=1)
            cases.append(prepare_blocks(2 * (b-a) / 24, observed, totals))
        for blocks in cases[:5]:
            optimal_queries(blocks, 2)
        samples = []
        for _ in range(3):
            for index in rng.permutation(30):
                blocks = cases[int(index)]
                before = time.perf_counter_ns()
                selected = optimal_queries(blocks, 2)
                elapsed = (time.perf_counter_ns() - before) / 1e6
                samples.append(elapsed)
                assert len(selected) <= 2
                assert worst_width(blocks, selected) <= worst_width(blocks, ()) + 1e-12
        results[str(gap)] = {"n": 24, "missing_coordinates": gap, "query_budget": 2,
            "block_hours": 6, "calls": len(samples), "median_ms": float(np.median(samples)),
            "p95_ms": float(np.quantile(samples, .95)), "mean_ms": float(np.mean(samples)), "samples_ms": samples}
    out = Path(__file__).resolve().parent
    result = {"completed_utc": datetime.now(timezone.utc).isoformat(), "seed": 861403,
        "description": "Optimal pair-specific batch query selection on30preparedfeasible24-coordinate cases per gap;5warmups and3repeats percase",
        "timing_scope": "Only optimal_queries API; excludes parsing, prediction fitting, prepared-block construction, record retrieval, and updated bounds",
        "limitations": "One shared CPU host; concurrent activity uncontrolled; not network retrieval latency or a hardware benchmark",
        "script_sha256": sha(__file__), "recovery_source_sha256": sha(out / "study_recovery.py"), "results": results}
    (out / "study_recovery_runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for gap, values in results.items():
        print(gap, "median_ms", values["median_ms"], "p95_ms", values["p95_ms"])


if __name__ == "__main__":
    main()
