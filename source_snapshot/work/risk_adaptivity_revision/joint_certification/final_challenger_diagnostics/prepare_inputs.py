"""Freeze derived inputs for the final challenger diagnostics; no raw traces.

Run only after the existing both-source provenance route has produced plans.
The output contains coefficients, stored policy choices, and derived widths.
"""
import argparse
import hashlib
import json
from pathlib import Path
from analyze import exact_geometry

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--shared-plans', required=True, type=Path)
    p.add_argument('--precision-plans', required=True, type=Path)
    p.add_argument('--replay-inputs', type=Path, default=HERE.parent/'review_sensitivity/frozen_inputs.json')
    p.add_argument('--output', type=Path, default=HERE/'frozen_inputs.json')
    a = p.parse_args()
    shared = {r['id']:r for r in json.loads(a.shared_plans.read_text())['plans']}
    precision = {r['id']:r for r in json.loads(a.precision_plans.read_text())['plans']}
    replay = json.loads(a.replay_inputs.read_text())
    assert set(shared) == set(precision) == {r['id'] for r in replay['cases']}
    result = []
    for r in replay['cases']:
        g = shared[r['id']]['geometry']; q = precision[r['id']]
        assert r['lower'] == q['precision_lower_exact'] and r['upper'] == q['precision_upper_exact']
        assert r['randomized_half_precision_weights'] == q['batch_weights']
        record=r | {
            'normalized_coefficients_exact':q['normalized_coefficients_exact'],
            'adaptive_first':g['first_query'], 'greedy_first':g['greedy_first_query'],
            'saved_first_guarantees_binary64':g['first_query_guarantees'],
            'saved_deterministic_guarantee_binary64':g['deterministic_batch_guarantee'],
        }
        record['coefficient_digest']=hashlib.sha256(json.dumps(record['normalized_coefficients_exact'],separators=(',',':')).encode()).hexdigest()
        if record['cohort']=='original':
            record['saved_regime_certificate']=exact_geometry(record)
            del record['normalized_coefficients_exact']
        result.append(record)
    sources = {name:{'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        for name,path in [('shared_plans',a.shared_plans),('precision_plans',a.precision_plans),('replay_inputs',a.replay_inputs)]}
    data = {'scope':'Original panel: derived interval certificates, frozen choices and widths, with coefficient digests but no coefficients or raw values. External panel: exact normalized coefficients included. No new fitted forecasts.',
            'sources':sources, 'cases':result}
    a.output.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':'PASS','cases':len(result),'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}))


if __name__ == '__main__': main()
