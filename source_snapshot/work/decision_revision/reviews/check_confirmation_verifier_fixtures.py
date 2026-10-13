"""Exercise independent replay guards and finite randomized LP checks."""
from pathlib import Path
import copy
import json
import sys
import numpy as np
from verify_decision_confirmation import endpoints, status, candidates, verify_selection, verify_randomized, alpha_vector

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'work/external_deadline/acquisition'))
from acquisition import select_batch


def main():
    rng=np.random.default_rng(826410)
    errors=[];rejections=0
    for repetition in range(80):
        a=rng.uniform(0,2,24);b=rng.uniform(0,2,24);truth=rng.uniform(.01,2,24)
        totals=truth.reshape(4,6).sum(axis=1)
        observed=truth.copy()
        start=repetition%19;observed[start:start+6]=np.nan
        # Public selection only; the independent verifier never imports it.
        chosen=select_batch('randomized',a,b,observed,totals,1,rng=rng)
        record=verify_randomized(a,b,observed,totals,chosen['query_indices'][0],chosen['diagnostics'])
        errors.append(record)
        if repetition<4:
            corrupt=copy.deepcopy(chosen['diagnostics'])
            corrupt['robust_expected_width']+=.1
            try:verify_randomized(a,b,observed,totals,chosen['query_indices'][0],corrupt)
            except AssertionError:rejections+=1
            else:raise AssertionError('Corrupted randomized objective accepted')
        scores=candidates(a,b,observed,totals,alpha_vector(np.ones(24),2.))
        best=min(scores,key=lambda x:(-x['probability'],x['worst_width'],x['index']))
        verify_selection('ml_decision',{'kind':'ridge_dirichlet','kappa':2.},best['index'],best['probability'],a,b,observed,totals,np.ones(24),1.,'fixture',0,{'selected_kappa':2.})
        if repetition<4:
            try:verify_selection('ml_decision',{'kind':'ridge_dirichlet','kappa':2.},best['index'],best['probability']+.1,a,b,observed,totals,np.ones(24),1.,'fixture',0,{'selected_kappa':2.})
            except AssertionError:rejections+=1
            else:raise AssertionError('Corrupted acquisition probability accepted')
    report={'status':'passed','synthetic_randomized_states':len(errors),'corruptions_rejected':rejections,
            'maximum_finite_primary_discrepancy':max(x['primary_error'] for x in errors),
            'maximum_finite_secondary_discrepancy':max(x['secondary_error'] for x in errors),
            'scope':'Fixtures call production to obtain synthetic diagnostics; the independent verifier itself imports no production policy or evaluator.'}
    Path(__file__).with_name('confirmation_verifier_fixtures.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

