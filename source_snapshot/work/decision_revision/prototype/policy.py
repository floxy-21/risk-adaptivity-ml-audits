"""Development-only, target-blind, myopic decision-directed query policy.

Independent uniform simplex priors over each residual nonnegative-total block.
For a single queried coordinate, the marginal scaled Beta(1,m-1) distribution
and affine post-query bounds give exact (up to floating point) sign-certificate
probability. This is a surrogate objective, not an optimal stopping policy.
"""
import math
import numpy as np


def state(a,b,observed,totals,blocksize=6):
    a,b,observed=(np.asarray(x,float) for x in (a,b,observed))
    if a.ndim!=1 or a.shape!=b.shape or a.shape!=observed.shape or len(a)!=len(totals)*blocksize:
        raise ValueError('Incompatible dimensions')
    if not np.isfinite(a).all() or not np.isfinite(b).all() or np.isinf(observed).any():
        raise ValueError('Nonfinite model outputs or infinite observed values')
    if np.any(observed[np.isfinite(observed)] < 0): raise ValueError('Negative energy')
    c=2*(b-a)/len(a)
    constant=math.fsum(float(x*x-y*y) for x,y in zip(a,b))/len(a)
    constant+=math.fsum(float(c[i]*observed[i]) for i in np.flatnonzero(np.isfinite(observed)))
    blocks=[]
    for g,total in enumerate(totals):
        indices=np.arange(g*blocksize,(g+1)*blocksize)
        unknown=indices[np.isnan(observed[indices])]
        residual=float(total)-math.fsum(float(v) for v in observed[indices] if math.isfinite(v))
        if residual < -1e-10*max(1.,abs(total)): raise ValueError('Negative residual')
        residual=max(0.,residual)
        if len(unknown): blocks.append((unknown,residual,c[unknown]))
    lower=constant+math.fsum(s*float(v.min()) for _,s,v in blocks)
    upper=constant+math.fsum(s*float(v.max()) for _,s,v in blocks)
    return c,constant,blocks,lower,upper


def affine_negative_probability(intercept,slope,total,m):
    """P(intercept + slope*X < 0), X/total~Beta(1,m-1)."""
    if m < 2 or total<=0: raise ValueError('Nondegenerate marginal required')
    at_zero=intercept;at_total=intercept+slope*total
    if at_zero<0 and at_total<0:return 1.
    if at_zero>=0 and at_total>=0:return 0.
    if slope==0:return float(intercept<0)
    fraction=min(1.,max(0.,-intercept/(slope*total)))
    survival=(1-fraction)**(m-1)
    return 1-survival if slope>0 else survival


def candidate_scores(a,b,observed,totals,blocksize=6):
    c,constant,blocks,lower,upper=state(a,b,observed,totals,blocksize)
    rows=[]
    for indices,total,coef in blocks:
        m=len(indices)
        if m<2 or total<=0 or float(np.ptp(coef))==0:continue
        otherlower=lower-total*float(coef.min())
        otherupper=upper-total*float(coef.max())
        for j,index in enumerate(indices):
            rest=np.delete(coef,j)
            lo0=otherlower+total*float(rest.min());loslope=float(coef[j]-rest.min())
            hi0=otherupper+total*float(rest.max());hislope=float(coef[j]-rest.max())
            pa=affine_negative_probability(hi0,hislope,total,m)
            pb=affine_negative_probability(-lo0,-loslope,total,m)
            if pa+pb>1+1e-10:raise ArithmeticError('Disjoint sign event probabilities exceed one')
            rows.append({'index':int(index),'certificate_probability':min(1.,max(0.,pa+pb)),
                         'worst_remaining_width':otherupper-otherlower+total*float(np.ptp(rest)),
                         'expected_remaining_width':otherupper-otherlower+total*(m-1)/m*float(np.ptp(rest)),
                         'lower_intercept':lo0,'lower_slope':loslope,'upper_intercept':hi0,'upper_slope':hislope,
                         'total':total,'unknown_count':m})
    return rows


def select_one(a,b,observed,totals,*,objective='decision_probability',blocksize=6):
    rows=candidate_scores(a,b,observed,totals,blocksize)
    if not rows:return {'query_indices':[],'scores':rows}
    if objective=='decision_probability':
        chosen=min(rows,key=lambda r:(-r['certificate_probability'],r['worst_remaining_width'],r['index']))
    elif objective in ('exact_width_one','greedy_width_one'):
        chosen=min(rows,key=lambda r:(r['worst_remaining_width'],r['index']))
    else:raise ValueError('Unknown deterministic objective')
    return {'query_indices':[chosen['index']],'scores':rows,'chosen':chosen}
