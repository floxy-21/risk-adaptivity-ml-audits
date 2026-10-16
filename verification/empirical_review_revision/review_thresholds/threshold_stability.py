"""Exact threshold intervals for the existing 222 matched-half certificates.

All policies and adverse distributions are frozen. No recorded fine answers,
new fits, optimization solver, or replay outcomes enter this calculation.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
from itertools import combinations
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ROOT = BASE.parents[1]
TARGETS = [F(s) for s in (".45", ".475", ".49", ".50", ".51", ".525", ".55")]


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p, obj):
    Path(p).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def vectors(C, query):
    cuts = (0, *query, 6)
    return [[z for l, u in zip(cuts, cuts[1:])
             for z in [max(c[l:u])-min(c[l:u])] * (u-l)] for c in C]


def tighten(a, b):
    """Minimize max_h(lambda*a_h+(1-lambda)*b_h) exactly on [0,1]."""
    candidates = {F(0), F(1)}
    for i, j in combinations(range(6), 2):
        slope = (a[i]-b[i])-(a[j]-b[j])
        if slope:
            t = (b[j]-b[i])/slope
            if 0 <= t <= 1:
                candidates.add(t)
    return min((max(t*x+(1-t)*y for x, y in zip(a, b)), t) for t in candidates)


def describe(vals):
    v = sorted(vals)
    # Inverse empirical CDF / nearest-rank quantiles; no interpolation.
    def quantile(n, d):
        return v[max(0, (len(v)*n+d-1)//d-1)]
    return {"n": len(v), "min_exact": str(v[0]), "q25_exact": str(quantile(1, 4)),
            "median_exact": str(quantile(1, 2)), "q75_exact": str(quantile(3, 4)),
            "max_exact": str(v[-1]),
            "approx": {"min": float(v[0]), "q25": float(quantile(1, 4)),
                       "median": float(quantile(1, 2)), "q75": float(quantile(3, 4)),
                       "max": float(v[-1])}}


def summarize(rows):
    retained = {str(t): sum(F(r["lower_closed"]) <= t < F(r["upper_open"]) for r in rows)
                for t in TARGETS}
    return {"cases": len(rows), "certified_at_threshold": retained,
            "inconclusive_at_threshold": {t: len(rows)-n for t, n in retained.items()},
            "saved_multiplier_lower": describe([F(r["saved_lower_closed"]) for r in rows]),
            "tightened_multiplier_lower": describe([F(r["lower_closed"]) for r in rows]),
            "adverse_upper_open": describe([F(r["upper_open"]) for r in rows]),
            "adaptive_bound": describe([F(r["adaptive_upper"]) for r in rows]),
            "strictly_below_half_lower": sum(F(r["lower_closed"]) < F(1, 2) for r in rows),
            "lower_equal_half": sum(F(r["lower_closed"]) == F(1, 2) for r in rows),
            "upper_strictly_above_half": sum(F(r["upper_open"]) > F(1, 2) for r in rows),
            "lower_margin_from_half": describe([F(1, 2)-F(r["lower_closed"]) for r in rows]),
            "upper_margin_from_half": describe([F(r["upper_open"])-F(1, 2) for r in rows]),
            "entire_closed_symmetric_band": {str(e): sum(F(r["lower_closed"]) <= F(1, 2)-e
                                                          and F(r["upper_open"]) > F(1, 2)+e
                                                          for r in rows)
                                              for e in (F(1, 100), F(1, 40), F(1, 20))},
            "symmetric_margin_about_half": describe([min(F(1, 2)-F(r["lower_closed"]),
                                                       F(r["upper_open"])-F(1, 2)) for r in rows])}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--chain-dir", type=Path, help="Verify and regenerate from a full source-chain run")
    mode.add_argument("--certificate-inputs", type=Path, help="Replay bundled rational certificate inputs only")
    ap.add_argument("--output-dir", type=Path, default=HERE/"replayed")
    args = ap.parse_args()
    started = time.perf_counter()
    embedded = None
    actual, source_hashes = {}, {}
    if args.chain_dir:
        chain = args.chain_dir.resolve()
        precision_path = chain/"precision/plans.json"
        adaptive_path = chain/"precision/adaptive_half_check.json"
        shared_path = chain/"shared/empirical_plans.json"
        source_check = chain/"source_chain.json"
        source_run = chain/"chain_execution.json"
        plans, adaptive = read(precision_path), read(adaptive_path)
        run, provenance = read(source_run), read(source_check)
        assert run["status"] == provenance["status"] == plans["status"] == adaptive["status"] == "PASS"
        assert run["cohort"] == provenance["cohort"] == "all"
        assert sha(source_check) == run["source_chain_sha256"]
        assert sha(precision_path) == adaptive["precision_plans_sha256"]
        assert sha(shared_path) == adaptive["base_plans_sha256"] == plans["input_plan_sha256"]
        for p, h in provenance["input_sha256"].items():
            assert sha(p) == h
        for relative, h in plans["source_hashes"].items():
            path = (BASE/relative).resolve()
            assert sha(path) == h
            source_hashes[relative] = h
            for r in read(path)["cases"]:
                actual[r["id"]] = r["c"]
    else:
        embedded = read(args.certificate_inputs or HERE/"executed/inputs.json")
        source_hashes = embedded["source_hashes"]
        plans = {"query_batches": embedded["query_batches"], "profiles": embedded["profiles"], "plans": []}
        adaptive = {"cases": [r["adaptive"] for r in embedded["cases"]]}
        for row in embedded["cases"]:
            for key, c in zip(row["pair_case_ids"], row["raw_coefficients_binary64"]):
                if key in actual:
                    assert actual[key] == c
                actual[key] = c
            plans["plans"].append({**row, "precision_lower_exact": "1/2", "precision_upper_exact": "1/2",
                                   "policy_kind": "certified_uniform_pair", "original_c_binary64": row["raw_coefficients_binary64"],
                                   "selected_batches": [plans["query_batches"][i] for i in row["selected_indices"]],
                                   "pair_cover_multipliers": row["saved_cover"]})
    Q = plans["query_batches"]
    assert Q == [list(q) for q in combinations(range(1, 6), 2)]
    profiles = [list(map(F, x)) for x in plans["profiles"]]
    assert all(len(x) == 6 and min(x) >= 0 and sum(x) == 1 for x in profiles)
    byid = {r["id"]: r for r in plans["plans"]}
    inputs, output = [], []
    for index, branch in enumerate(adaptive["cases"], 1):
        r = byid[branch["id"]]
        assert r["precision_lower_exact"] == r["precision_upper_exact"] == "1/2"
        assert r["policy_kind"] == "certified_uniform_pair"
        raw = [actual[key] for key in r["pair_case_ids"]]
        assert raw == r["original_c_binary64"]
        C = []
        for cc in raw:
            c = list(map(F.from_float, cc)); lo, hi = min(c), max(c)
            assert hi > lo
            C.append([(x-lo)/(hi-lo) for x in c])
        assert [[str(x) for x in c] for c in C] == r["normalized_coefficients_exact"]
        V = [vectors(C, q) for q in Q]
        first = branch["first_query"]
        cursor, A = F(0), F(0)
        for b in branch["branches"]:
            lo, hi = F(b["lo"]), F(b["hi"])
            assert lo == cursor < hi <= 1
            q = sorted((first, b["second"]))
            vv = vectors(C, q)
            lines = [(max(v[:first])-max(v[first:]), max(v[first:])) for v in vv]
            assert [[str(m), str(a)] for m, a in lines] == b["lines"]
            bound = max(m*t+a for m, a in lines for t in (lo, hi))
            assert bound == F(b["upper_exact"])
            A = max(A, bound); cursor = hi
        assert cursor == 1 and A == F(branch["upper_exact"]) <= F(1, 2)
        i, j = r["selected_indices"]
        assert r["selected_batches"] == [Q[i], Q[j]]
        assert all(F(w) == (F(1, 2) if n in (i, j) else 0)
                   for n, w in enumerate(r["batch_weights"]))
        saved_lower, pair_lower, covers = F(0), F(0), []
        assert len(r["pair_cover_multipliers"]) == 36
        for cv in r["pair_cover_multipliers"]:
            rr, ss = cv["first_contrast"], cv["second_contrast"]
            a, b, lam = V[i][rr], V[j][ss], F(cv["lambda"])
            assert 0 <= lam <= 1
            old_bound = max(lam*x+(1-lam)*y for x, y in zip(a, b))
            bound, tighter = tighten(a, b)
            assert bound <= old_bound <= F(1, 2)
            saved_lower = max(saved_lower, old_bound)
            pair_lower = max(pair_lower, bound)
            covers.append({"r": rr, "s": ss, "lambda": str(tighter), "upper": str(bound),
                           "saved_lambda": str(lam), "saved_upper": str(old_bound)})
        mu = list(map(F, r["adverse_profile_weights"]))
        assert len(mu) == len(profiles) and min(mu) >= 0 and sum(mu) == 1
        values = [[max(sum(a*x for a, x in zip(v, profile)) for v in batch)
                   for batch in V] for profile in profiles]
        crossovers = []
        for batch in range(10):
            events = sorted({values[p][batch] for p in range(len(profiles)) if mu[p]})
            for tau in events:
                at = sum(mu[p] for p in range(len(profiles)) if values[p][batch] <= tau)
                below = sum(mu[p] for p in range(len(profiles)) if values[p][batch] < tau)
                if at > F(1, 2):
                    assert below <= F(1, 2)
                    crossovers.append({"batch_index": batch, "threshold": str(tau),
                                       "success_strictly_below": str(below), "success_at": str(at)})
                    break
        assert len(crossovers) == 10
        L = max(A, pair_lower)
        Lsaved = max(A, saved_lower)
        U = min(F(e["threshold"]) for e in crossovers)
        assert L <= Lsaved <= F(1, 2) < U
        inputs.append({"id": r["id"], "cohort": r["cohort"], "meter": r["meter"],
                       "pair_case_ids": r["pair_case_ids"], "raw_coefficients_binary64": raw,
                       "normalized_coefficients_exact": r["normalized_coefficients_exact"],
                       "adaptive": branch, "selected_indices": r["selected_indices"],
                       "batch_weights": r["batch_weights"], "saved_cover": r["pair_cover_multipliers"],
                       "adverse_profile_weights": r["adverse_profile_weights"]})
        output.append({"id": r["id"], "cohort": r["cohort"], "meter": r["meter"],
                       "pair_labels": [s.split("/")[-2:] for s in r["pair_case_ids"]],
                       "lower_closed": str(L), "upper_open": str(U),
                       "saved_lower_closed": str(Lsaved), "adaptive_upper": str(A),
                       "pair_cover_lower": str(pair_lower), "saved_pair_cover_lower": str(saved_lower),
                       "cover_witnesses": covers, "adverse_crossovers": crossovers,
                       "adverse_profile_widths": [[str(x) for x in row] for row in values],
                       "certified_targets": [str(t) for t in TARGETS if L <= t < U]})
        if index % 50 == 0:
            print(json.dumps({"processed": index, "seconds": time.perf_counter()-started}), flush=True)
    assert Counter(r["cohort"] for r in output) == {"original": 165, "external": 57}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    input_data = embedded if embedded is not None else {"source_hashes": source_hashes, "precision_plans_sha256": sha(precision_path),
                  "adaptive_check_sha256": sha(adaptive_path), "shared_plans_sha256": sha(shared_path),
                  "source_chain_sha256": sha(source_check), "chain_execution_sha256": sha(source_run),
                  "profiles": plans["profiles"], "query_batches": Q, "cases": inputs}
    dump(args.output_dir/"inputs.json", input_data)
    dump(args.output_dir/"intervals.json", {"cases": output, "inputs_sha256": sha(args.output_dir/"inputs.json")})
    groups = {"all": output}
    for cohort in ("original", "external"):
        groups[cohort] = [r for r in output if r["cohort"] == cohort]
        for meter in sorted({r["meter"] for r in groups[cohort]}):
            groups[cohort+"/"+meter] = [r for r in groups[cohort] if r["meter"] == meter]
    report = {"status": "PASS", "case_count": len(output), "summary": {k: summarize(v) for k, v in groups.items()},
              "execution_mode": "full_source_chain" if args.chain_dir else "bundled_certificate_replay",
              "source_records_verified_in_this_run": bool(args.chain_dir),
              "interval_convention": "[lower_closed, upper_open): success is J <= threshold; upper endpoint excluded",
              "certificate_scope": "Sufficient ranges for the same saved adaptive branches, uniform batch mixture, and adverse weights. Pair-cover multipliers tightened algebraically; no policy retuning. Not a maximal range over all adaptive or randomized batch policies.",
              "outside_interval": "Inconclusive about whether exact adaptive-1/batch-half separation holds, not a proof of its failure.",
              "model_pair_scope": "Every case jointly covers all six model pairs; pair-wise counts are not independent cases.",
              "quantile_method": "Inverse empirical CDF / nearest rank, exact rationals; no interpolation",
              "inputs_sha256": sha(args.output_dir/"inputs.json"), "intervals_sha256": sha(args.output_dir/"intervals.json"),
              "producer_sha256": sha(__file__), "elapsed_seconds": time.perf_counter()-started,
              "fine_answers_used": False, "new_model_fits": 0, "new_solver_calls": 0}
    dump(args.output_dir/"report.json", report)
    print(json.dumps({"status": report["status"], "case_count": len(output),
                      "summary": {k: report["summary"][k] for k in ("all", "original", "external")},
                      "elapsed_seconds": report["elapsed_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
