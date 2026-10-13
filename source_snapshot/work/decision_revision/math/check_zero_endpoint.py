"""Degenerate zero-endpoint strict-ranking check; no external data."""
import importlib.util,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'work/decision_revision/prototype'))
from ridge_policy import candidate_scores
from check_decision_probability import exact_myopic_probability
# c=(0,0,1) with d=0: querying either zero coefficient never proves a
# strict sign; querying coefficient1 makes D=x>0 almost surely.
c=np.array([0.,0.,1.]);a=np.ones(6);b=np.ones(6);a[:3]=1-c/4;b[:3]=1+c/4
# Missing fixed constant =-sum(c)=-1. Known a=1,b=0 adds+1.
a[3]=1.;b[3]=0.;a[4:]=b[4:]=0.
obs=np.array([np.nan,np.nan,np.nan,0.,0.,0.])
rows=candidate_scores(a,b,obs,[1.],np.ones(6))
probs=[row['certificate_probability'] for row in rows]
assert np.allclose(probs,[0.,0.,1.],rtol=0,atol=1e-14),probs
reference=[exact_myopic_probability(c,1.,0.,0.,i) for i in range(3)]
assert np.allclose(reference,probs,rtol=0,atol=1e-14)
print(json.dumps({'status':'passed','zero_endpoint_strict_ranking_probabilities':probs,'reference':reference}))
