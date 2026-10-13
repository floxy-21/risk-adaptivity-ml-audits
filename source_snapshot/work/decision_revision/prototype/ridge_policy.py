"""ML-guided Dirichlet probability policy; fixed prior, target-blind decisions.

This is a developmental extension of the uniform-simplex policy. Alpha values
are fixed once from the Ridge forecast for the WHOLE original block. Conditioning
on observed coordinates preserves remaining alpha values, never renormalizing
their concentration. The reference record is never a policy input.
"""
import math
import numpy as np
from scipy.special import betainc
from policy import state

def make_alpha(ridge,kappa,blocksize=6):
    ridge=np.asarray(ridge,float)
    if ridge.ndim!=1 or len(ridge)%blocksize or not np.isfinite(ridge).all() or not np.isfinite(kappa) or kappa<=0:
        raise ValueError('Finite forecast vector and positive concentration required')
    alpha=np.empty_like(ridge)
    for start in range(0,len(ridge),blocksize):
        positive=np.maximum(ridge[start:start+blocksize],0.)
        floor=1e-8*max(float(positive.mean()),1e-12)
        weight=np.maximum(positive,floor)
        alpha[start:start+blocksize]=kappa*blocksize*weight/float(weight.sum())
    return alpha

def negative_probability(intercept,slope,total,alpha,beta):
    end=intercept+slope*total
    if intercept<0 and end<0:return 1.
    if intercept>=0 and end>=0:return 0.
    if slope==0:return float(intercept<0)
    threshold=min(1.,max(0.,-intercept/(slope*total)))
    return float(betainc(alpha,beta,threshold)) if slope>0 else float(betainc(beta,alpha,1-threshold))

def candidate_scores(a,b,observed,totals,alpha,blocksize=6):
    totals=np.asarray(totals,float);observed=np.asarray(observed,float)
    if totals.ndim!=1 or not np.isfinite(totals).all() or np.any(totals<0):
        raise ValueError('Finite nonnegative aggregate totals required')
    if observed.ndim!=1 or len(observed)!=len(totals)*blocksize:
        raise ValueError('Observation and aggregate dimensions differ')
    for g,total in enumerate(totals):
        block=observed[g*blocksize:(g+1)*blocksize]
        if np.isfinite(block).all() and abs(math.fsum(float(v) for v in block)-total)>1e-10*max(1.,abs(total)):
            raise ValueError('Fully observed block inconsistent with its total')
    alpha=np.asarray(alpha,float)
    if alpha.shape!=np.shape(a) or not np.isfinite(alpha).all() or np.any(alpha<=0):
        raise ValueError('Positive finite fixed alpha vector required')
    c,constant,blocks,lower,upper=state(a,b,observed,totals,blocksize)
    scores=[]
    for indices,total,coef in blocks:
        if len(indices)<2 or total<=0 or np.ptp(coef)==0:continue
        otherlower=lower-total*float(coef.min());otherupper=upper-total*float(coef.max())
        for j,index in enumerate(indices):
            rest=np.delete(coef,j)
            other_indices=np.delete(indices,j)
            al=float(alpha[index]);be=math.fsum(float(x) for x in alpha[other_indices])
            lo=otherlower+total*float(rest.min());los=float(coef[j]-rest.min())
            hi=otherupper+total*float(rest.max());his=float(coef[j]-rest.max())
            probability=negative_probability(hi,his,total,al,be)+negative_probability(-lo,-los,total,al,be)
            if probability>1+1e-9 or probability<0:raise ArithmeticError('Invalid disjoint event probability')
            scores.append({'index':int(index),'certificate_probability':min(1.,max(0.,probability)),
                           'worst_remaining_width':otherupper-otherlower+total*float(np.ptp(rest)),
                           'alpha':al,'beta':be,'residual_total':total,
                           'lower_intercept':lo,'lower_slope':los,'upper_intercept':hi,'upper_slope':his})
    return scores

def select_one(a,b,observed,totals,alpha,blocksize=6):
    scores=candidate_scores(a,b,observed,totals,alpha,blocksize)
    if not scores:return {'query_indices':[],'scores':scores}
    chosen=min(scores,key=lambda row:(-row['certificate_probability'],row['worst_remaining_width'],row['index']))
    return {'query_indices':[chosen['index']],'chosen':chosen,'scores':scores}
