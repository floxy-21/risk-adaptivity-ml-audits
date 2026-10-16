#!/usr/bin/env python3
"""Independent resource check by shortest-path segmentation and endpoints.

Does not import reading_budget.py or any policy optimizer. The existing
source-binding module is used only to validate input hashes and normalize
the frozen contrasts. All new mathematical checks are implemented here.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
SOURCE = BASE / "joint_certification/assurance_feasibility/verify_assurance.py"
spec = importlib.util.spec_from_file_location("input_binding_only", SOURCE)
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def extremal_pair(c, query, left_mass=None, first=None):
    """Enumerate mass on single segment, or one segment on each prefix side."""
    boundaries = (0, *query, 6)
    segments = [(a, b) for a, b in zip(boundaries, boundaries[1:])]
    if first is None:
        combinations = [((seg, F(1)),) for seg in segments]
    else:
        left = [seg for seg in segments if seg[1] <= first]
        right = [seg for seg in segments if seg[0] >= first]
        combinations = [((a, left_mass), (b, 1-left_mass)) for a in left for b in right]
    maximum = F(0)
    checks = 0
    for assignment in combinations:
        high, low = [F(0)] * 6, [F(0)] * 6
        for (a, b), mass in assignment:
            high[max(range(a, b), key=lambda i: c[i])] += mass
            low[min(range(a, b), key=lambda i: c[i])] += mass
        assert sum(high) == sum(low) == 1 and min(high + low) >= 0
        for k in query:
            assert sum(high[:k]) == sum(low[:k])
        if first is not None:
            assert sum(high[:first]) == sum(low[:first]) == left_mass
        width = sum(x * (h-l) for x, h, l in zip(c, high, low))
        assert width >= 0
        maximum = max(maximum, width)
        checks += 1
    return maximum, checks


def shortest_segmentation(c):
    # A segment edge is legal exactly when all six target ranges fit the
    # precision threshold. The DAG distance minus one is the query budget.
    d, paths = [0] + [100] * 6, [()] + [None] * 6
    for right in range(1, 7):
        for left in range(right):
            good = all(max(row[left:right]) - min(row[left:right]) <= F(1, 2) for row in c)
            if good and d[left] + 1 < d[right]:
                d[right] = d[left] + 1
                paths[right] = paths[left] + (() if right == 6 else (right,))
    assert d[6] <= 6
    return d[6] - 1, paths[6]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chain-dir", type=Path)
    p.add_argument("--results", type=Path, required=True)
    a = p.parse_args()
    started = time.perf_counter()
    inputs, provenance = binding.source_inputs(a.chain_dir)
    given = read(a.results / "ledger.json")["rows"]
    report = read(a.results / "report.json")
    assert report["ledger_sha256"] == sha(a.results / "ledger.json")
    assert len(given) == len(inputs)
    counts, budgets = Counter(), {}
    for row, inp in zip(given, inputs):
        assert row["id"] == inp["id"] and row["coefficient_digest"] == inp["coefficient_digest"]
        c = inp["coefficients"]
        optimal, independent_batch = shortest_segmentation(c)
        assert optimal == row["fixed_minimum_readings"]
        counts["independent_shortest_path_minima"] += 1
        assert len(row["all_fixed_batches"]) == 32
        seen = set()
        for b in row["all_fixed_batches"]:
            q = tuple(b["query"])
            assert q == tuple(sorted(set(q))) and set(q) <= set(range(1, 6)) and q not in seen
            seen.add(q)
            maximum = F(0)
            for contrast in c:
                width, checks = extremal_pair(contrast, q)
                maximum = max(maximum, width)
                counts["feasible_fixed_endpoint_pairs"] += checks
            assert maximum == F(b["worst_normalized_width"])
            counts["independent_all_batch_widths"] += 1
            if len(q) < optimal:
                assert maximum > F(1, 2)
                counts["strict_insufficient_batch_checks"] += 1
        minimum_given = tuple(row["fixed_lexicographic_batch"])
        assert len(minimum_given) == optimal
        scan_batch = tuple(row["fixed_linear_scan_batch"])
        assert len(scan_batch) == optimal
        assert max(extremal_pair(contrast, scan_batch)[0] for contrast in c) <= F(1, 2)
        counts["linear_scan_vs_independent_shortest_path"] += 1
        if row["adaptive_minimum_readings"] == 2:
            assert optimal >= 2
            first = row["adaptive_two_first_query"]
            intervals = row["adaptive_two_cover"]
            frontier = F(0)
            for item in sorted(intervals, key=lambda x: (F(x["lower"]), F(x["upper"]), x["second"])):
                lower, upper = F(item["lower"]), F(item["upper"])
                assert 0 <= lower <= upper <= 1
                assert lower <= frontier
                frontier = max(frontier, upper)
                q = tuple(sorted((first, item["second"])))
                for t in (lower, upper):
                    for contrast in c:
                        width, checks = extremal_pair(contrast, q, t, first)
                        assert width <= F(1, 2)
                        counts["adaptive_conditional_endpoint_pairs"] += checks
            assert frontier == 1
            counts["adaptive_closed_interval_covers"] += 1
        elif row["adaptive_minimum_readings"] is not None:
            assert row["adaptive_minimum_readings"] == optimal <= 1
        cohort = inp["cohort"]
        budgets.setdefault(cohort, Counter())[str(optimal)] += 1
    for cohort, histogram in budgets.items():
        assert dict(histogram) == report["summaries"][cohort]["minimum_fixed_budget_histogram"]
    output = {"status": "PASS", "method": "Independent DAG shortest-path minima plus exact extremal endpoint and interval-cover inequalities; producer not imported.",
              "checks": counts, "fixed_budget_histograms": budgets,
              "results_ledger_sha256": sha(a.results / "ledger.json"),
              "producer_report_sha256": sha(a.results / "report.json"),
              "checker_sha256": sha(__file__), "source_binding_sha256": sha(SOURCE),
              "source_input_hashes": provenance, "elapsed_seconds": time.perf_counter() - started,
              "recorded_answers_or_replay_outcomes_used": False,
              "scope": "All fixed cardinalities exact; adaptive minimum only for certificates using at most two. Input-binding code shared; mathematical verification separately implemented."}
    (a.results / "independent_check.json").write_text(json.dumps(binding.clean(output), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(binding.clean({k: output[k] for k in ("status", "checks", "fixed_budget_histograms", "elapsed_seconds")}), indent=2))


if __name__ == "__main__":
    main()
