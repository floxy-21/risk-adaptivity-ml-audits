#!/usr/bin/env python3
"""Seeded exact cross-check of the general minimum-prefix partition scan."""
import argparse
from fractions import Fraction as F
import hashlib
import importlib.util
from itertools import combinations
import json
from pathlib import Path
import random
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tested_reading_budget", HERE / "reading_budget.py")
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


def exhaustive(c, threshold):
    n = len(c[0])
    tested = 0
    first_budget = None
    for size in range(n):
        for q in combinations(range(1, n), size):
            boundaries = (0, *q, n)
            good = all(max(row[a:b]) - min(row[a:b]) <= threshold
                       for row in c for a, b in zip(boundaries, boundaries[1:]))
            tested += 1
            if good and first_budget is None:
                first_budget = size
    assert first_budget is not None
    return first_budget, tested


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    started = time.perf_counter()
    rng = random.Random(20261014)
    records = []
    tests = 0
    for n in range(2, 11):
        for r in range(1, 6):
            for threshold in (F(0), F(1, 4), F(1, 2), F(1)):
                c = [[F(rng.randrange(-5, 6), rng.randrange(1, 10)) for _ in range(n)] for _ in range(r)]
                # Ties and constant rows are deliberate, not filtered out.
                if r > 1 and n % 2 == 0:
                    c[-1] = [F(1, 3)] * n
                minimum, checked = exhaustive(c, threshold)
                q = producer.minimum_fixed_prefix_batch(c, threshold)
                assert len(q) == minimum
                records.append({"hours": n, "targets": r, "threshold": str(threshold),
                                "minimum_fixed_queries": minimum, "scan_batch": q,
                                "coefficients": [[str(x) for x in row] for row in c]})
                tests += checked
    out = {"status": "PASS", "seed": 20261014, "instances": len(records),
           "enumerated_batches": tests, "recorded_meter_values_used": False,
           "scope": "Constructed exact-rational checks of the general O(R*n) scan against full batch enumeration, including zero threshold, ties and constant targets.",
           "producer_sha256": hashlib.sha256((HERE / "reading_budget.py").read_bytes()).hexdigest(),
           "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "elapsed_seconds": time.perf_counter() - started, "instances_checked": records}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("status", "seed", "instances", "enumerated_batches", "elapsed_seconds")}, indent=2))


if __name__ == "__main__":
    main()
