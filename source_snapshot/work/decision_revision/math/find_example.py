from itertools import combinations
import numpy as np

def unresolved_probability(c,d,i):
    m=len(c); rem=np.delete(c,i); lo=float(rem.min());hi=float(rem.max())
    # lower=d+lo+(c_i-lo)x <0, upper=d+hi+(c_i-hi)x >0
    left,right=0.,1.
    for intercept,slope in ((-d-lo,-c[i]+lo),(d+hi,c[i]-hi)):
        # intercept+slope*x>0
        if abs(slope)<1e-14:
            if intercept<=0:return 0.
        elif slope>0:left=max(left,-intercept/slope)
        else:right=min(right,-intercept/slope)
    if left>=right:return 0.
    return (1-left)**(m-1)-(1-right)**(m-1)
for c in combinations(range(-4,6),4):
    for d in np.arange(-2,3,.25):
        if d+min(c)>=0 or d+max(c)<=0:continue
        probs=np.array([1-unresolved_probability(np.array(c),d,i) for i in range(4)])
        widths=np.array([np.ptp(np.delete(c,i)) for i in range(4)])
        widthset=np.flatnonzero(widths==min(widths))
        if probs.max()-probs[widthset].max()>.25:
            print(c,d,'cert probabilities',probs,'widths',widths,'best-cert',int(probs.argmax()))
            raise SystemExit
