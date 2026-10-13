"""Exact rational uncapped two-best-side and capped marginal-slope oracles."""
from fractions import Fraction as F
import itertools


def ranges(c):
    n = len(c); out = {}
    for a in range(n):
        lo = hi = c[a]
        for b in range(a+1, n+1):
            lo = min(lo, c[b-1]); hi = max(hi, c[b-1])
            out[a, b] = hi-lo
    return out


def two_side(c):
    n = len(c); r = ranges(c); values = []
    assert n >= 3
    for k in range(1, n):
        ell, rr = r[0, k], r[k, n]
        left = [(max(r[0,j],r[j,k]),j) for j in range(1,k)]
        right = [(max(r[k,j],r[j,n]),j) for j in range(k+1,n)]
        alpha, jl = min(left) if left else (None,None)
        beta, jr = min(right) if right else (None,None)
        switch = None
        if not left:
            val = beta
        elif not right:
            val = alpha
        else:
            delta = ell+rr-alpha-beta
            if delta:
                switch = (rr-beta)/delta
                assert 0 <= switch <= 1
                val = max(alpha,beta,(ell*rr-alpha*beta)/delta)
            else:
                val = max(ell,rr)
        values.append({'first':k,'value':val,'left':jl,'right':jr,'switch':switch})
    return min(values,key=lambda v:(v['value'],v['first'])), values


def full_uncapped(c, k):
    n = len(c); r = ranges(c); lines = []
    for j in range(1,n):
        if j == k: continue
        a,b = (max(r[0,j],r[j,k]),r[k,n]) if j<k else (r[0,k],max(r[k,j],r[j,n]))
        lines.append((a,b))
    points = {F(0),F(1)}
    for (a,b),(aa,bb) in itertools.combinations(lines,2):
        denom=(a-b)-(aa-bb)
        if denom:
            t=(bb-b)/denom
            if 0 <= t <= 1: points.add(t)
    return max(min(a*t+b*(1-t) for a,b in lines) for t in points)


def segments(n, batch):
    cuts=[0,*sorted(batch),n]
    return list(zip(cuts,cuts[1:]))


def slopes(c, groups):
    ans=[]
    for a,b in groups:
        ordered=sorted(c[a:b])
        ans += [hi-lo for hi,lo in zip(reversed(ordered),ordered)]
    return sorted(ans,reverse=True)


def integral(ordered_slopes, mass, cap):
    assert mass >= 0 and mass <= len(ordered_slopes)*cap
    ans=F(0)
    for slope in ordered_slopes:
        take=min(mass,cap)
        ans += take*slope; mass -= take
        if mass == 0: break
    assert mass == 0
    return ans


def capped_batch_worst(c, batch, cap):
    return integral(slopes(c,segments(len(c),batch)),F(1),cap)


def capped_at_profile(c, batch, profile, cap):
    return sum((integral(slopes(c,[(a,b)]),sum(profile[a:b]),cap)
                for a,b in segments(len(c),batch)),F(0))


def capped_first(c, k, cap, seconds=None):
    n=len(c)
    seconds=list(seconds) if seconds is not None else [j for j in range(1,n) if j != k]
    lo=max(F(0),1-(n-k)*cap); hi=min(F(1),k*cap)
    grid={lo,hi}
    for m in range(n+1):
        for point in [m*cap,1-m*cap]:
            if lo <= point <= hi: grid.add(point)
    grid=sorted(grid)
    pieces={}
    for j in seconds:
        ss=segments(n,(k,j))
        pieces[j]=(slopes(c,[(a,b) for a,b in ss if b<=k]),
                   slopes(c,[(a,b) for a,b in ss if a>=k]))
    def g(j,t):
        l,r=pieces[j]
        return integral(l,t,cap)+integral(r,1-t,cap)
    best=F(-1); adverse=None
    if lo == hi:
        return min(g(j,lo) for j in seconds),lo
    for a,b in zip(grid,grid[1:]):
        equations=[]
        for j in seconds:
            ga,gb=g(j,a),g(j,b)
            slope=(gb-ga)/(b-a); intercept=ga-slope*a
            equations.append((slope,intercept))
        candidates={a,b}
        for (s,d),(ss,dd) in itertools.combinations(equations,2):
            if s!=ss:
                t=(dd-d)/(s-ss)
                if a<=t<=b: candidates.add(t)
        for t in candidates:
            value=min(s*t+d for s,d in equations)
            if value>best: best,adverse=value,t
    return best,adverse


def capped_adaptive(c,cap):
    values=[(capped_first(c,k,cap)[0],k) for k in range(1,len(c))]
    return min(values),values
