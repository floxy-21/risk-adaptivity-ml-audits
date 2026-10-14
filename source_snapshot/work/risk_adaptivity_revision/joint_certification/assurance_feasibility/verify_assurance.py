#!/usr/bin/env python3
"""Exact finite-witness certificates ruling out two-query adaptive certainty.

Standard library only. Default: bundled external coefficients. --chain-dir:
both cohorts from a completed source-verified run_chain.py output. No existing
scientific producer is imported or modified. No recorded answers are used.
The exported records are synthetic normalized simplex points, not meter data.
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
JC = HERE.parent
BASE = JC.parent
ROOT = BASE.parents[1]
HALF = F(1, 2)
BATCHES = tuple(combinations(range(1, 6), 2))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def clean(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, str):
        return value.replace(str(ROOT), "<WORKSPACE>").replace(ROOT.as_posix(), "<WORKSPACE>")
    if isinstance(value, dict):
        return {clean(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def dump(path, value):
    path.write_text(json.dumps(clean(value), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), F(0))


def source_inputs(chain_dir):
    """Bind coefficients to independently source-checked geometry and forecasts."""
    if chain_dir:
        chain_dir = chain_dir.resolve()
        chain = read(chain_dir / "chain_execution.json")
        source = read(chain_dir / "source_chain.json")
        assert chain["status"] == source["status"] == "PASS"
        assert chain["cohort"] == source["cohort"] == "all"
        assert chain["original_raw_report"]["reused_completed_run"] is False
        assert chain["reused_generated_paths"] == {"shared": None, "precision": None}
        assert sha(chain_dir / "source_chain.json") == chain["source_chain_sha256"]
        assert sha(JC / "provenance_chain/run_chain.py") == chain["runner_sha256"]
        assert sha(JC / "provenance_chain/check_source_chain.py") == source["source_sha256"]
        for path, expected in source["input_sha256"].items():
            assert sha(path) == expected, path
        plans_path = chain_dir / "precision/plans.json"
        shared_path = chain_dir / "shared/empirical_plans.json"
        assert sha(plans_path) == read(chain_dir / "precision/independent_check.json")["plan_sha256"]
        provenance = {"mode": "fresh_both_source_chain", "chain_execution_sha256": sha(chain_dir / "chain_execution.json"),
                      "source_chain_sha256": sha(chain_dir / "source_chain.json"),
                      "source_input_sha256": source["input_sha256"],
                      "source_physical_blocks": source["physical_blocks"],
                      "source_coefficient_cases": source["coefficient_cases"],
                      "source_maximum_differences": source["maximum_float_differences"],
                      "source_chain_runtime_seconds": chain["elapsed_seconds"]}
    else:
        plans_path = JC / "precision_external_results/plans.json"
        shared_path = JC / "empirical_external_results/empirical_plans.json"
        evidence_path = JC / "provenance_chain/executed/fresh_both_panel_replay_20261014.json"
        evidence = read(evidence_path)
        assert evidence["status"] == "PASS" and evidence["scientific_scripts_unchanged"] is True
        provenance = {"mode": "bundled_external_only", "source_execution_evidence_sha256": sha(evidence_path),
                      "source_physical_blocks": {"external": 279},
                      "original_coefficients_verified_in_this_run": False}
    plans = read(plans_path)
    assert plans["status"] == "PASS" and plans["fine_answers_loaded"] is False
    assert sha(shared_path) == plans["input_plan_sha256"]
    raw_coefficients = {}
    geometries = {}
    for relative, expected in plans["source_hashes"].items():
        path = (BASE / relative).resolve()
        assert sha(path) == expected
        geometries[relative] = expected
        for row in read(path)["cases"]:
            # Deliberately read only the identifier and affine coefficients.
            # The retained total, observed increments and replay fields are unused.
            raw_coefficients[row["id"]] = row["c"]
    if not chain_dir:
        bound = evidence["all_source_input_sha256"]
        external_geometry_hash = geometries["external_validation/replay/geometry.json"]
        assert any(key.replace("\\", "/").endswith("external_validation/replay/geometry.json")
                   and value == external_geometry_hash for key, value in bound.items())
    provenance.update(plans_sha256=sha(plans_path), shared_plans_sha256=sha(shared_path),
                      geometry_sha256=geometries, precision_producer_sha256=plans["source_sha256"])
    rows = []
    normalization_checks = 0
    for row in plans["plans"]:
        if not chain_dir:
            assert row["cohort"] == "external"
        coefficients = []
        assert len(row["pair_case_ids"]) == 6
        for case_id in row["pair_case_ids"]:
            values = [F.from_float(value) for value in raw_coefficients[case_id]]
            low, high = min(values), max(values)
            assert high > low
            coefficients.append([(value - low) / (high - low) for value in values])
            normalization_checks += 1
        serialized = [[str(value) for value in c] for c in coefficients]
        assert serialized == row["normalized_coefficients_exact"]
        assert len(coefficients) == 6 and all(len(c) == 6 for c in coefficients)
        rows.append({"id": row["id"], "cohort": row["cohort"], "coefficients": coefficients,
                     "coefficient_digest": digest(serialized)})
    provenance["exact_coefficient_normalization_checks"] = normalization_checks
    provenance["maximum_exact_normalization_difference"] = "0"
    return rows, provenance


def segment_vectors(coefficients, query):
    cuts = (0, *query, 6)
    result = []
    for c in coefficients:
        row = []
        for lo, hi in zip(cuts, cuts[1:]):
            row.extend([max(c[lo:hi]) - min(c[lo:hi])] * (hi - lo))
        result.append(row)
    return result


def first_answer_witness(coefficients, first):
    """Find a rational gap in the exact continuation-success intervals."""
    intervals = []
    for second in range(1, 6):
        if second == first:
            continue
        vectors = segment_vectors(coefficients, tuple(sorted((first, second))))
        lower, upper, empty = F(0), F(1), False
        for row in vectors:
            left, right = max(row[:first]), max(row[first:])
            slope = left - right
            if slope > 0:
                upper = min(upper, (HALF - right) / slope)
            elif slope < 0:
                lower = max(lower, (HALF - right) / slope)
            elif right > HALF:
                empty = True
        if not empty and lower <= upper:
            intervals.append((lower, upper))
    # Check closed endpoints as well as open gaps. Equality is success.
    breaks = sorted({F(0), F(1)} | {x for interval in intervals for x in interval})
    probes = sorted(set(breaks + [(a + b) / 2 for a, b in zip(breaks, breaks[1:])]))
    for t in probes:
        if not any(lo <= t <= hi for lo, hi in intervals):
            return t
    return None


def construct_endpoints(coefficients, first, second, answer):
    """Put side masses in segments attaining a conditional failing range."""
    query = tuple(sorted((first, second)))
    cuts = (0, *query, 6)
    segments = tuple(zip(cuts, cuts[1:]))
    candidates = []
    for contrast, c in enumerate(coefficients):
        upper, lower = [F(0)] * 6, [F(0)] * 6
        for lo_limit, hi_limit, mass in ((0, first, answer), (first, 6, 1 - answer)):
            available = [(lo, hi) for lo, hi in segments if lo_limit <= lo < hi <= hi_limit]
            lo, hi = max(available, key=lambda bounds: max(c[bounds[0]:bounds[1]]) - min(c[bounds[0]:bounds[1]]))
            high_index = max(range(lo, hi), key=lambda index: c[index])
            low_index = min(range(lo, hi), key=lambda index: c[index])
            upper[high_index] += mass
            lower[low_index] += mass
        difference = dot(c, [u - v for u, v in zip(upper, lower)])
        candidates.append((difference, contrast, upper, lower))
    difference, contrast, upper, lower = max(candidates, key=lambda item: item[0])
    assert difference > HALF
    return {"second": second, "contrast_index": contrast,
            "upper_endpoint": upper, "lower_endpoint_and_adverse_record": lower,
            "normalized_width_lower_bound": difference, "strict_failure_margin": difference - HALF}


def verify_certificate(certificate, coefficients, counts):
    """Independent direct endpoint check: no conditional-width formula is used."""
    assert certificate["success_upper_bound"] == "19/20"
    assert certificate["adverse_mass_per_ordered_witness"] == "1/20"
    assert len(certificate["first_answers"]) == 5
    minimum_margin = None
    for first, branch in zip(range(1, 6), certificate["first_answers"]):
        assert branch["first"] == first
        answer = F(branch["answer"])
        assert 0 <= answer <= 1
        assert [w["second"] for w in branch["witnesses"]] == [j for j in range(1, 6) if j != first]
        counts["common_first_answer_checks"] += 1
        for witness in branch["witnesses"]:
            second = witness["second"]
            upper = list(map(F, witness["upper_endpoint"]))
            lower = list(map(F, witness["lower_endpoint_and_adverse_record"]))
            for endpoint in (upper, lower):
                assert len(endpoint) == 6 and min(endpoint) >= 0 and sum(endpoint) == 1
                assert sum(endpoint[:first]) == answer
                counts["simplex_endpoint_checks"] += 1
            for query in (first, second):
                assert sum(upper[:query]) == sum(lower[:query])
                counts["shared_query_answer_checks"] += 1
            contrast = witness["contrast_index"]
            difference = dot(coefficients[contrast], [u - v for u, v in zip(upper, lower)])
            assert difference == F(witness["normalized_width_lower_bound"]) > HALF
            margin = difference - HALF
            assert margin == F(witness["strict_failure_margin"]) > 0
            minimum_margin = margin if minimum_margin is None else min(minimum_margin, margin)
            counts["strict_failing_fiber_checks"] += 1
    assert 20 * F(certificate["adverse_mass_per_ordered_witness"]) == 1
    counts["seed_independent_adverse_distributions"] += 1
    return minimum_margin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chain-dir", type=Path, help="A completed fresh both-source run_chain.py output")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    rows, provenance = source_inputs(args.chain_dir)
    counts = Counter()
    regimes = {}
    certificates = []
    margin_by_cohort = {}
    for row in rows:
        cohort, coefficients = row["cohort"], row["coefficients"]
        regimes.setdefault(cohort, Counter())
        fixed = min(max(max(c) for c in segment_vectors(coefficients, q)) for q in BATCHES) <= HALF
        answers = [first_answer_witness(coefficients, k) for k in range(1, 6)]
        adaptive = any(answer is None for answer in answers)
        assert not fixed or adaptive
        regime = "fixed_guarantee" if fixed else "adaptive_only_guarantee" if adaptive else "no_deterministic_adaptive_guarantee"
        regimes[cohort][regime] += 1
        counts["coefficient_instances_classified"] += 1
        counts["first_query_interval_covers_checked"] += 5
        if adaptive:
            continue
        certificate = {"id": row["id"], "cohort": cohort,
                       "coefficient_digest": row["coefficient_digest"],
                       "success_upper_bound": "19/20", "adverse_mass_per_ordered_witness": "1/20",
                       "first_answers": []}
        for first, answer in zip(range(1, 6), answers):
            certificate["first_answers"].append({"first": first, "answer": answer,
                "witnesses": [construct_endpoints(coefficients, first, second, answer)
                              for second in range(1, 6) if second != first]})
        certificate = clean(certificate)
        margin = verify_certificate(certificate, coefficients, counts)
        margin_by_cohort[cohort] = min(margin_by_cohort.get(cohort, margin), margin)
        certificates.append(certificate)
    expected = {"external": {"fixed_guarantee": 128, "adaptive_only_guarantee": 57,
                             "no_deterministic_adaptive_guarantee": 94}}
    if args.chain_dir:
        expected["original"] = {"fixed_guarantee": 162, "adaptive_only_guarantee": 168,
                                "no_deterministic_adaptive_guarantee": 489}
    assert {key: dict(value) for key, value in regimes.items()} == expected
    args.output_dir.mkdir(parents=True, exist_ok=True)
    witness_path = args.output_dir / "synthetic_witnesses.json"
    dump(witness_path, {"scope": "Constructed normalized simplex points, not recorded meter values; original coefficient vectors are not exported.",
                        "threshold": "1/2", "proof": "Uniform mass on twenty ordered first/second-action witness records is drawn independently of the policy seed.",
                        "certificates": certificates})
    report = {"status": "PASS", "scope": "Exact source-bound impossibility of randomized adaptive certainty under the existing two-prefix-reading contract.",
              "checked_cohorts": sorted(regimes), "regimes": regimes,
              "randomized_adaptive_success_upper_bound_on_no_guarantee_cases": "19/20",
              "bound_is_not_claimed_optimal": True, "actual_check_counts": counts,
              "minimum_strict_failure_margin_by_cohort": margin_by_cohort,
              "minimum_strict_failure_margin_float_by_cohort": {k: float(v) for k, v in margin_by_cohort.items()},
              "provenance": provenance, "source_sha256": sha(__file__),
              "synthetic_witnesses_sha256": sha(witness_path), "elapsed_seconds": time.perf_counter() - started,
              "input_fields_used": ["case identifier", "cohort", "paired case identifiers", "affine coefficients", "source hashes"],
              "recorded_answers_or_replay_outcomes_used": False, "original_coefficients_exported": False,
              "new_forecast_fits": 0, "new_network_calls": 0,
              "limitations": "Elementary finite-action consequence, not a claimed novel theorem or optimized randomized-adaptive success value. Exact serialized-coefficient, uncapped, exact-total/noiseless prefix model. No winner-selection, hardware-calibration, privacy/compliance or deployment-saving claim."}
    dump(args.output_dir / "report.json", report)
    print(json.dumps(clean({key: report[key] for key in ("status", "checked_cohorts", "regimes", "actual_check_counts", "minimum_strict_failure_margin_float_by_cohort", "elapsed_seconds")}), indent=2))


if __name__ == "__main__":
    main()
