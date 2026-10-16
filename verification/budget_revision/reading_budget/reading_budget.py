#!/usr/bin/env python3
"""Exact minimum fixed readout authorization, using no hidden query answers.

Default checks bundled external inputs. --chain-dir consumes an existing
completed source-verified both-panel chain. The half-width target and exact,
uncapped six-hour model are unchanged. This is a post-analysis resource
diagnostic, not new training, a new independent panel, or measured savings.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
import importlib.util
from itertools import combinations
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
SOURCE = BASE / "joint_certification/assurance_feasibility/verify_assurance.py"
spec = importlib.util.spec_from_file_location("verified_input_binding", SOURCE)
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)
HALF = F(1, 2)
SETS = tuple(q for b in range(6) for q in combinations(range(1, 6), b))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(binding.clean(data), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fixed_width(c, query):
    cuts = (0, *query, 6)
    # All unknown mass may lie in one segment of one contrast.
    return max(max(row[l:r]) - min(row[l:r]) for row in c for l, r in zip(cuts, cuts[1:]))


def minimum_fixed_prefix_batch(coefficients, threshold):
    """Longest admissible segment scan; O(number of contrasts * hours).

    Rows may be any real/rational affine coefficients whose ranges have
    already been normalized to the requested per-target precision scale.
    Each optional observation is a prefix of the same nonnegative total.
    """
    assert coefficients and threshold >= 0
    n = len(coefficients[0])
    assert n and all(len(row) == n for row in coefficients)
    lows = [row[0] for row in coefficients]
    highs = lows[:]
    query = []
    for i in range(1, n):
        proposed_low = [min(v, row[i]) for v, row in zip(lows, coefficients)]
        proposed_high = [max(v, row[i]) for v, row in zip(highs, coefficients)]
        if any(hi-lo > threshold for lo, hi in zip(proposed_low, proposed_high)):
            query.append(i)
            lows = [row[i] for row in coefficients]
            highs = lows[:]
        else:
            lows, highs = proposed_low, proposed_high
    return tuple(query)


def adaptive_two(c):
    """Closed first-answer covers; the tie convention is lexicographic."""
    rules = []
    for first in range(1, 6):
        intervals = []
        for second in range(1, 6):
            if second == first:
                continue
            q = tuple(sorted((first, second)))
            cuts = (0, *q, 6)
            segments = tuple(zip(cuts, cuts[1:]))
            lo, hi, possible = F(0), F(1), True
            for row in c:
                left = max(max(row[l:r]) - min(row[l:r]) for l, r in segments if r <= first)
                right = max(max(row[l:r]) - min(row[l:r]) for l, r in segments if l >= first)
                slope = left - right
                if slope > 0:
                    hi = min(hi, (HALF - right) / slope)
                elif slope < 0:
                    lo = max(lo, (HALF - right) / slope)
                elif right > HALF:
                    possible = False
            if possible and lo <= hi:
                intervals.append({"second": second, "lower": lo, "upper": hi})
        covered = F(0)
        found_start = False
        for interval in sorted(intervals, key=lambda v: (v["lower"], v["upper"], v["second"])):
            if interval["lower"] > covered:
                break
            found_start = True
            covered = max(covered, interval["upper"])
        if found_start and covered == 1:
            rules.append({"first": first, "second_answer_intervals": intervals})
    return rules


def summarize(rows):
    out = {}
    for key in sorted({r["cohort"] for r in rows} | {r["cohort"] + "/" + r["system"] for r in rows}):
        group = [r for r in rows if r["cohort"] == key or r["cohort"] + "/" + r["system"] == key]
        known = [r for r in group if r["adaptive_minimum_readings"] is not None]
        saved = [r for r in known if r["fixed_minimum_readings"] > r["adaptive_minimum_readings"]]
        out[key] = {
            "blocks": len(group),
            "minimum_fixed_budget_histogram": dict(sorted(Counter(r["fixed_minimum_readings"] for r in group).items())),
            "minimum_adaptive_budget_identified_at_most_two": len(known),
            "adaptive_two_vs_minimum_fixed_histogram": dict(sorted(Counter(r["fixed_minimum_readings"] for r in saved).items())),
            "strict_readout_saving_cases": len(saved),
            "fixed_readings_on_saving_subset": sum(r["fixed_minimum_readings"] for r in saved),
            "adaptive_readings_on_saving_subset": sum(r["adaptive_minimum_readings"] for r in saved),
            "fixed_total_readings_all_blocks": sum(r["fixed_minimum_readings"] for r in group),
            "adaptive_where_certified_otherwise_minimum_fixed_total": sum(min(r["fixed_minimum_readings"], r["adaptive_minimum_readings"] or r["fixed_minimum_readings"]) for r in group),
            "minimum_adaptive_budget_above_two_not_solved": len(group) - len(known),
        }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chain-dir", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    start = time.perf_counter()
    inputs, provenance = binding.source_inputs(args.chain_dir)
    ledger = []
    for row in inputs:
        c = row["coefficients"]
        values = [(q, fixed_width(c, q)) for q in SETS]
        good = [(q, w) for q, w in values if w <= HALF]
        q, w = min(good, key=lambda qw: (len(qw[0]), qw[0]))
        greedy_batch = minimum_fixed_prefix_batch(c, HALF)
        assert len(greedy_batch) == len(q) and fixed_width(c, greedy_batch) <= HALF
        rules = adaptive_two(c)
        amin = len(q) if len(q) <= 1 else 2 if rules else None
        assert (bool(rules)) == any(binding.first_answer_witness(c, k) is None for k in range(1, 6))
        assert len(q) > 2 or rules
        ledger.append({
            "id": row["id"], "cohort": row["cohort"], "system": row["id"].split("/")[1],
            "coefficient_digest": row["coefficient_digest"],
            "fixed_minimum_readings": len(q), "fixed_lexicographic_batch": q,
            "fixed_linear_scan_batch": greedy_batch,
            "fixed_batch_worst_normalized_width": w,
            "adaptive_minimum_readings": amin,
            "adaptive_two_first_query": rules[0]["first"] if rules else None,
            "adaptive_two_cover": rules[0]["second_answer_intervals"] if rules else [],
            "all_fixed_batches": [{"query": query, "worst_normalized_width": width} for query, width in values],
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write(args.output_dir / "ledger.json", {"status": "PASS", "rows": ledger})
    report = {"status": "PASS", "analysis": "Post-analysis exact least sufficient fixed readout authorization under unchanged noiseless uncapped half-width model.",
              "summaries": summarize(ledger), "subset_checks": 32 * len(ledger),
              "linear_scan_vs_enumeration_checks": len(ledger),
              "recorded_answers_or_replay_outcomes_used": False, "forecast_training_runs": 0,
              "fixed_optimum_includes_randomized_sure_policies": True,
              "adaptive_minimum_identified_only_when_at_most_two": True,
              "provenance": provenance, "source_sha256": sha(__file__), "binding_sha256": sha(SOURCE),
              "ledger_sha256": sha(args.output_dir / "ledger.json"), "elapsed_seconds": time.perf_counter() - start,
              "limitations": "Readouts, not HTTP requests, actual latency, dollars, calibrated sensor error, or a source-enforced contract. The API permits bulk. No claim that adaptive budgets above two are optimized."}
    write(args.output_dir / "report.json", report)
    print(json.dumps(binding.clean({k: report[k] for k in ("status", "summaries", "subset_checks", "elapsed_seconds")}), indent=2))


if __name__ == "__main__":
    main()
