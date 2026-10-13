from pathlib import Path
import json
import numpy as np
from policy import candidate_scores as uniform_scores
from ridge_policy import candidate_scores,make_alpha

def main():
    rng=np.random.default_rng(5103);maximum=0.;cases=0;queries=0
    for repetition in range(100):
        a=rng.normal(size=12);b=rng.normal(size=12)
        truth=rng.gamma(2,1,size=12);totals=truth.reshape(2,6).sum(axis=1)
        observed=truth.copy();observed[rng.random(12)<.7]=np.nan
        reference=uniform_scores(a,b,observed,totals)
        current=candidate_scores(a,b,observed,totals,np.ones(12))
        assert len(reference)==len(current)
        for row,other in zip(reference,current):
            assert row['index']==other['index']
            maximum=max(maximum,abs(row['certificate_probability']-other['certificate_probability']));queries+=1
        cases+=1
    assert maximum<1e-12
    a=np.arange(6,dtype=float);b=a+1;visible=np.full(6,np.nan);alpha=np.ones(6)
    invalid=0
    for total in [np.nan,np.inf,-1.]:
        try:candidate_scores(a,b,visible,[total],alpha)
        except ValueError:invalid+=1
        else:raise AssertionError('Invalid total accepted')
    try:candidate_scores(a,b,np.ones(6),[7.],alpha)
    except ValueError:invalid+=1
    else:raise AssertionError('Inconsistent fully observed sum accepted')
    for kappa in [.5,1,2,4,8,16]:
        assert np.array_equal(make_alpha(np.zeros(6),kappa),np.full(6,kappa))
        values=make_alpha(np.array([0,0,0,0,0,1.]),kappa)
        assert (values>0).all() and abs(values.sum()-6*kappa)<1e-12
    result={'status':'passed','uniform_equivalence_cases':cases,'candidates':queries,'max_probability_difference':maximum,
            'invalid_input_rejections':invalid,'zero_forecast_uniform_fallback':'passed for six concentrations',
            'note':'Independent full generalized beta probability checker is in ../math.'}
    Path(__file__).with_name('check_ridge.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
