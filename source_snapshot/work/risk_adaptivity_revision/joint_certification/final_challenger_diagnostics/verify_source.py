"""Bind diagnostic inputs to the previously regenerated both-source catalogs.

This checks joins and input identity. check.py --precision-plans separately
reconstructs every coefficient inequality. Neither command refits a model.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--shared-plans',required=True,type=Path)
    p.add_argument('--precision-plans',required=True,type=Path)
    p.add_argument('--replay-inputs',type=Path,default=HERE.parent/'review_sensitivity/frozen_inputs.json')
    p.add_argument('--input',type=Path,default=HERE/'frozen_inputs.json')
    p.add_argument('--output',type=Path,default=HERE/'source_verification.json')
    a=p.parse_args();data=json.loads(a.input.read_text())
    shared={r['id']:r for r in json.loads(a.shared_plans.read_text())['plans']}
    precision={r['id']:r for r in json.loads(a.precision_plans.read_text())['plans']}
    replay={r['id']:r for r in json.loads(a.replay_inputs.read_text())['cases']}
    assert set(shared)==set(precision)==set(replay)=={r['id'] for r in data['cases']}
    for r in data['cases']:
        key=r['id'];g=shared[key]['geometry'];p=precision[key];v=replay[key]
        for field,value in v.items():assert r[field]==value,(key,field)
        C=p['normalized_coefficients_exact']
        assert hashlib.sha256(json.dumps(C,separators=(',',':')).encode()).hexdigest()==r['coefficient_digest']
        if r['cohort']=='external':assert C==r['normalized_coefficients_exact']
        else:assert 'normalized_coefficients_exact' not in r
        assert r['adaptive_first']==g['first_query'] and r['greedy_first']==g['greedy_first_query']
        assert r['saved_first_guarantees_binary64']==g['first_query_guarantees']
        assert r['saved_deterministic_guarantee_binary64']==g['deterministic_batch_guarantee']
        assert r['lower']==p['precision_lower_exact'] and r['upper']==p['precision_upper_exact']
        assert r['randomized_half_precision_weights']==p['batch_weights']
    report={'status':'PASS','blocks':len(data['cases']),'coefficient_rows_joined':6*len(data['cases']),
        'original_coefficients_bundled':False,
        'scope':'Both-panel diagnostic joins to regenerated shared and precision catalogs and the existing verified derived-width replay. Coefficient inequalities checked separately in full_source_independent_check.json. Source timestamps, source bytes, frozen forecasts and coefficient derivation are verified by provenance_chain; this is not a fresh fit.',
        'inputs':{'shared_plans':sha(a.shared_plans),'precision_plans':sha(a.precision_plans),'replay_inputs':sha(a.replay_inputs),'diagnostic_inputs':sha(a.input)},
        'source_sha256':sha(Path(__file__)),'new_network_calls':0,'new_forecast_fits':0}
    a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
