"""Independent mathematical audit; no hidden or external study outcomes used."""
from pathlib import Path
from fractions import Fraction
import json
import numpy as np
from scipy.special import betainc


def exact_myopic_probability(c, energy, other_lower, other_upper, i, alpha=None):
    c=np.asarray(c,float); m=len(c)
    if m<2 or energy<=0: raise ValueError('At least two unknowns and positive residual total')
    if alpha is None: alpha=np.ones(m)
    alpha=np.asarray(alpha,float)
    if len(alpha)!=m or np.any(alpha<=0):raise ValueError('Positive Dirichlet shape parameters required')
    rem=np.delete(c,i); lower=float(rem.min());upper=float(rem.max())
    # Normalize x=energy*z. The event is lower(z)<0<upper(z).
    lower0=other_lower+energy*lower; lower1=energy*(c[i]-lower)
    upper0=other_upper+energy*upper; upper1=energy*(c[i]-upper)
    if upper0==lower0 and upper1==lower1:
        return 1.0 # D is known; its possible zero is an exact tie, not ambiguity.
    left,right=0.,1.
    for intercept,slope in ((-lower0,-lower1),(upper0,upper1)):
        if slope==0:
            if intercept<0:return 1.0
        elif slope>0:left=max(left,-intercept/slope)
        else:right=min(right,-intercept/slope)
    if left>=right:return 1.0
    beta=float(alpha.sum()-alpha[i])
    unresolved=betainc(float(alpha[i]),beta,right)-betainc(float(alpha[i]),beta,left)
    return float(np.clip(1.-unresolved,0.,1.))


def main():
    rng=np.random.default_rng(910117)
    fixtures=100; n=100000; errors=[]
    # Monte Carlo direct completion plus independently recomputed residual bounds.
    # No sample is used to construct acquisition probabilities.
    for case in range(fixtures):
        m=int(rng.integers(2,9)); c=rng.integers(-5,6,size=m).astype(float)
        energy=float(rng.uniform(.1,6));alpha=rng.uniform(.2,3,size=m)
        i=int(rng.integers(m)); center=float(rng.normal());span=float(rng.uniform(0,6))
        if case%5==0:span=0.
        other_lower=center-span;other_upper=center+span
        probability=exact_myopic_probability(c,energy,other_lower,other_upper,i,alpha)
        completion=energy*rng.dirichlet(alpha,size=n)
        x=completion[:,i]; residual=energy-x
        rem=np.delete(c,i)
        low=other_lower+c[i]*x+residual*rem.min()
        high=other_upper+c[i]*x+residual*rem.max()
        certified=(low>=0)|(high<=0)|((high-low)==0)
        empirical=float(certified.mean());error=abs(empirical-probability);errors.append(error)
        assert error<.011, (case,probability,empirical,error)
    c=(-4.,-3.,0.,2.)
    p=[exact_myopic_probability(c,1.,0.,0.,i) for i in range(4)]
    expected=[Fraction(8,27),Fraction(27,125),Fraction(0),Fraction(1,27)]
    assert np.allclose(p,list(map(float,expected)),rtol=0,atol=1e-14)
    widths=[float(np.ptp(np.delete(c,i))) for i in range(4)]
    # Interior zero-contrast record used in lower bound and all subset check.
    # For c=(-4,-3,0,2), y=(.1,.1,.45,.35) yields contrast=0.
    y=np.array([.1,.1,.45,.35]);assert abs(np.dot(c,y))<1e-15
    from itertools import combinations
    lower_bound_subset_checks=0
    for k in range(3):
        for q in combinations(range(4),k):
            un=[j for j in range(4) if j not in q]
            fixed=sum(c[j]*y[j] for j in q); e=sum(y[j] for j in un)
            lo=fixed+e*min(c[j] for j in un);hi=fixed+e*max(c[j] for j in un)
            assert lo<0<hi,(q,lo,hi)
            lower_bound_subset_checks+=1
    result={'status':'passed','scope':'Synthetic mathematical validation only; not empirical study replication',
            'dirichlet_cases':fixtures,'monte_carlo_completions_per_case':n,'total_completions':fixtures*n,
            'largest_absolute_probability_difference':max(errors),'absolute_error_threshold':.011,
            'counterexample':{'coefficients':c,'residual_total':1,'fixed_offset':0,'one_query_certification_probabilities':p,
               'exact_rational_probabilities':[str(x) for x in expected],'worst_residual_widths':widths,
               'width_optimal_query_index':int(np.argmin(widths)),'decision_optimal_query_index':int(np.argmax(p)),
               'probability_advantage':p[0]-p[3]},
            'interior_tie_record':y.tolist(),'lower_bound_all_subset_checks':lower_bound_subset_checks}
    out=Path(__file__).with_name('mathematical_checks.json');out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

