"""Prespecified first unresolved Portugal MLP-versus-HGB operator example.

Selection uses no post-query outcome. This is a same-panel illustration, not
a new experiment or representative estimate. Retained Portugal totals are
constructed from the complete trace, as documented in the main study.
"""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from study_recovery import decision, optimal_queries, pair_interval, prepare_blocks, sha, worst_width


def attaining_witnesses(a,b,observed,totals):
    coefficients = 2*(b-a)/len(a)
    blocks = prepare_blocks(coefficients,observed,totals)
    low,high = np.nan_to_num(observed,nan=0.),np.nan_to_num(observed,nan=0.)
    for block in blocks:
        low[block.indices[int(np.argmin(block.coefficients))]] = block.energy
        high[block.indices[int(np.argmax(block.coefficients))]] = block.energy
    visible = np.isfinite(observed)
    expected = pair_interval(a,b,observed,totals)
    endpoint_values = []
    max_total_error = 0.
    for witness in [low,high]:
        assert np.all(witness >= 0.)
        np.testing.assert_array_equal(witness[visible],observed[visible])
        sums = witness.reshape(-1,6).sum(axis=1)
        np.testing.assert_allclose(sums,totals,rtol=1e-10,atol=1e-9)
        max_total_error = max(max_total_error,float(np.max(abs(sums-totals))))
        endpoint_values.append(math.fsum((((a-b)/len(a))*((a-witness)+(b-witness))).tolist()))
    np.testing.assert_allclose(endpoint_values,expected,rtol=1e-10,atol=1e-9)
    validation = {'nonnegative':True,'observed_coordinates_preserved':True,
        'maximum_block_total_absolute_error_kwh':max_total_error,
        'evaluated_mse_difference_endpoints':endpoint_values,'matches_reported_interval':True}
    return low,high,validation


def main():
    out = Path(__file__).resolve().parent
    summary_path = out / "study_summary.json"
    summary = json.loads(summary_path.read_text())
    if "mlp" not in summary["design"]["models"]:
        raise RuntimeError("Wait for the completed AI prediction archive")
    predictions_path = out / "study_predictions.csv"
    if sha(predictions_path) != summary["artifacts"]["study_predictions.csv"]["sha256"]:
        raise RuntimeError("Prediction archive is not the completed main-study version")
    data = pd.read_csv(predictions_path)
    data = data[data.cohort == "portugal"].copy()
    data["day"] = pd.to_datetime(data.timestamp.str.slice(0,10), format="%Y-%m-%d")
    for (day,meter), group in data.groupby(["day","meter"], sort=True):
        group = group.sort_values("timestamp")
        a = group.mlp.to_numpy()
        b = group.hist_gradient_boosting.to_numpy()
        truth = group.truth_kwh.to_numpy()
        totals = truth.reshape(-1,6).sum(axis=1)
        epochday = int(day.value // 86400000000000)
        rng = np.random.default_rng(np.random.SeedSequence([1103,epochday,1]))
        start = int(rng.integers(0,19))
        observed = truth.copy(); observed[start:start+6] = np.nan
        before = pair_interval(a,b,observed,totals)
        if decision(*before) != 0:
            continue
        # Selection ends here, before any queried target is exposed.
        coefficients = 2*(b-a)/24
        blocks = prepare_blocks(coefficients,observed,totals)
        queries = optimal_queries(blocks,2)
        recovered = observed.copy(); recovered[list(queries)] = truth[list(queries)]
        after = pair_interval(a,b,recovered,totals)
        before_low,before_high,before_validation = attaining_witnesses(a,b,observed,totals)
        after_low,after_high,after_validation = attaining_witnesses(a,b,recovered,totals)
        actual_gap = math.fsum(((a-b)*((a-truth)+(b-truth))).tolist())/24
        timestamps = group.timestamp.tolist()
        records = []
        for i in range(24):
            records.append({"timestamp":timestamps[i],"mlp_kwh":float(a[i]),"hgb_kwh":float(b[i]),
                "contrast_coefficient":float(coefficients[i]),"was_missing":bool(np.isnan(observed[i])),
                "visible_before_kwh":None if np.isnan(observed[i]) else float(observed[i]),
                "queried":i in queries,"recovered_value_kwh":float(truth[i]) if i in queries else None,
                "before_lower_witness_kwh":float(before_low[i]),"before_upper_witness_kwh":float(before_high[i]),
                "after_lower_witness_kwh":float(after_low[i]),"after_upper_witness_kwh":float(after_high[i]),
                "six_hour_block_total_kwh":float(totals[i//6]),
                "reference_truth_kwh_not_used_for_query_selection":float(truth[i])})
        pd.DataFrame(records).to_csv(out / "study_operator_example.csv",index=False)
        result = {"completed_utc":datetime.now(timezone.utc).isoformat(),"cohort":"portugal","meter":meter,
            "day":str(day.date()),"prediction_a":"mlp","prediction_b":"hist_gradient_boosting",
            "selection_rule":"First chronologically unresolved pre-recovery case; date then meter ID; no conditioning on post-query outcome",
            "mask_seed":1103,"gap_hours":6,"block_hours":6,"query_budget":2,
            "missing_indices":list(range(start,start+6)),"missing_timestamps":timestamps[start:start+6],
            "block_totals_kwh":totals.tolist(),"before_interval_mse_a_minus_b":list(before),
            "query_indices":list(queries),"queries":[{"timestamp":timestamps[i],"value_kwh":float(truth[i])} for i in queries],
            "query_count":len(queries),"after_interval_mse_a_minus_b":list(after),
            "after_decision":{-1:"MLP",0:"unresolved",1:"HGB"}[decision(*after)],
            "worst_case_width_before":worst_width(blocks,()),"worst_case_width_after":worst_width(blocks,queries),
            "reference_full_data_gap_for_verification_only":actual_gap,
            "witness_validation":{"before":before_validation,"after":after_validation},
            "source_semantics":"Same archived Portugal traces; controlled verification mask and simulated retrieval; supplied totals constructed from complete trace",
            "hashes":{"script":sha(__file__),"predictions":sha(predictions_path),"main_summary":sha(summary_path),
                      "recovery_source":sha(out/'study_recovery.py'),"protocol":sha(out.parent/'work'/'recovery_ai_protocol.txt'),
                      "table":sha(out/'study_operator_example.csv')}}
        (out/'study_operator_example.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
        print(json.dumps({k:result[k] for k in ['meter','day','before_interval_mse_a_minus_b','queries','after_interval_mse_a_minus_b','after_decision']},indent=2))
        return
    raise RuntimeError("No pre-recovery unresolved Portugal MLP-versus-HGB case exists under the fixed criterion")


if __name__ == "__main__":
    main()
