"""Development diagnostic: independent quadrature and vertex checks."""
from pathlib import Path
import json
import numpy as np
from policy import candidate_scores

def main():
    rng=np.random.default_rng(993702)
    quadrature_errors=[];vertex_errors=[];instances=0;queries=0
    for m in range(2,7):
      for repetition in range(40):
        a=rng.normal(size=m);b=rng.normal(size=m);total=float(rng.uniform(.1,5))
        observed=np.full(m,np.nan)
        rows=candidate_scores(a,b,observed,[total],m)
        # Uniform quantiles of the exact marginal. No policy analytic helper used.
        u=(np.arange(50000)+.5)/50000
        x=total*(1-(1-u)**(1/(m-1)))
        for row in rows:
            i=row['index'];others=np.delete(np.arange(m),i)
            # Reference post-query endpoints from all simplex vertices.
            vals=[]
            for j in others:
                y=np.zeros((len(x),m));y[:,i]=x;y[:,j]=total-x
                vals.append(np.mean((a-y)**2-(b-y)**2,axis=1))
            vals=np.asarray(vals);lo=vals.min(axis=0);hi=vals.max(axis=0)
            empirical=float(np.mean((lo>0)|(hi<0)))
            quadrature_errors.append(abs(empirical-row['certificate_probability']))
            vertex_errors.extend([float(np.max(np.abs(lo-(row['lower_intercept']+row['lower_slope']*x)))),
                                  float(np.max(np.abs(hi-(row['upper_intercept']+row['upper_slope']*x))))])
            queries+=1
        instances+=1
    assert max(quadrature_errors)<=2e-5+1e-12
    assert max(vertex_errors)<1e-12
    report={'status':'passed','instances':instances,'queries':queries,'quadrature_points_per_query':50000,
            'max_quadrature_probability_error':max(quadrature_errors),'max_vertex_endpoint_error':max(vertex_errors),
            'scope':'Synthetic numerical validation of exact one-step probability only; no stopping optimality claim.'}
    Path(__file__).with_name('check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
