"""Exact verification of the constructed shared-query joint-width example.

Uses Python's standard library and no numerical optimization solver.
"""
from fractions import Fraction as F
from itertools import combinations, product
from pathlib import Path
import argparse, hashlib, json
HERE=Path(__file__).resolve().parent
C=((F(1,2),F(0),F(1),F(1,2),F(1,2),F(0)),
   (F(2,3),F(2,3),F(1),F(1,3),F(0),F(1)))
N=6
QS=list(combinations(range(1,N),2))
STAR=(F(0),F(0),F(1,2),F(0),F(0),F(1,2))
PI={(1,2):F(1,6),(2,3):F(1,3),(3,5):F(1,2)}
DUAL=(F(1,3),F(0),F(1,6),F(1,6),F(1,3),F(0))
def ran(c,a,b):return max(c[a:b])-min(c[a:b])
def vectors(c,Q):
    cuts=(0,)+tuple(Q)+(N,);v=[]
    for a,b in zip(cuts,cuts[1:]):v.extend([ran(c,a,b)]*(b-a))
    return tuple(v)
def width(c,Q,z):return sum(a*b for a,b in zip(vectors(c,Q),z))
def joint(Q,z):return max(width(c,Q,z) for c in C)
def lines(k,j):
    result=[]
    for c in C:
        if j<k:L=max(ran(c,0,j),ran(c,j,k));R=ran(c,k,N)
        else:L=ran(c,0,k);R=max(ran(c,k,j),ran(c,j,N))
        result.append((L,R))
    return result
def conditional(k,j,t):return max(L*t+R*(1-t) for L,R in lines(k,j))
def candidates(k):
    rows=[(L-R,R) for j in range(1,N) if j!=k for L,R in lines(k,j)]
    pts={F(0),F(1)}
    for (s,b),(u,v) in combinations(rows,2):
        if s!=u:
            t=(v-b)/(s-u)
            if 0<=t<=1:pts.add(t)
    return sorted(pts)
def exact_planner():
    out=[]
    for k in range(1,N):
        vals=[]
        for t in candidates(k):
            val,j=min((conditional(k,j,t),j) for j in range(1,N) if j!=k)
            vals.append({'t':str(t),'best_second':j,'conditional_value':str(val)})
        value=max(F(v['conditional_value']) for v in vals)
        out.append({'first':k,'worst_joint_width':str(value),'candidate_values':vals})
    return out
def endpoint_width(c,Q,z):
    # Enumerate vertices of the actual fiber: each fixed segment mass is
    # assigned to one coordinate in that segment; no range formula is used.
    cuts=(0,)+tuple(Q)+(N,)
    segs=list(zip(cuts,cuts[1:]));masses=[sum(z[a:b]) for a,b in segs]
    vals=[]
    for locs in product(*(range(a,b) for a,b in segs)):
        vals.append(sum(c[i]*m for i,m in zip(locs,masses)))
    return max(vals)-min(vals)
def comps(total,n):
    if n==1:yield(total,);return
    for i in range(total+1):
        for tail in comps(total-i,n-1):yield(i,)+tail
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=HERE/'proof_verification.json')
    args=p.parse_args()
    assert all(max(c)-min(c)==1 for c in C)
    assert sum(PI.values())==sum(DUAL)==1
    basis=[tuple(F(int(i==h)) for i in range(N)) for h in range(N)]
    matrix={Q:tuple(joint(Q,z) for z in basis) for Q in QS}
    primal=tuple(sum(PI.get(Q,0)*matrix[Q][h] for Q in QS) for h in range(N))
    assert primal==(F(2,3),)*5+(F(1,2),)
    adverse={Q:sum(w*v for w,v in zip(DUAL,matrix[Q])) for Q in QS}
    assert min(adverse.values())==F(2,3)
    hard={Q:joint(Q,STAR) for Q in QS};assert min(hard.values())==F(1,2)
    assert lines(3,5)==[(F(1),F(0)),(F(1,3),F(1,3))]
    assert lines(3,2)==[(F(1,2),F(1,2)),(F(0),F(1))]
    # Upper maxima on both adaptive branches, including all affine crossings.
    branch_max=[]
    for j,lo,hi in [(5,F(0),F(1,2)),(2,F(1,2),F(1))]:
        pts={lo,hi}
        for (L,R),(U,V) in combinations(lines(3,j),2):
            if L-R!=U-V:
                t=(V-R)/((L-R)-(U-V))
                if lo<=t<=hi:pts.add(t)
        branch_max.append(max(conditional(3,j,t) for t in pts))
    assert branch_max==[F(1,2),F(1,2)]
    plans=exact_planner();assert min(F(r['worst_joint_width']) for r in plans)==F(1,2)
    midpoint=tuple((a+b)/2 for a,b in zip(basis[0],basis[3]))
    assert joint((2,3),midpoint)==F(1,2)<(joint((2,3),basis[0])+joint((2,3),basis[3]))/2==F(3,4)
    # Independent scalar endpoint enumeration on 126 rational records.
    grid=[tuple(F(x,4) for x in row) for row in comps(4,N)]
    allsets=[()]+[(k,) for k in range(1,N)]+QS
    interval_checks=0
    for z in grid:
        for Q in allsets:
            for c in C:
                assert endpoint_width(c,Q,z)==width(c,Q,z);interval_checks+=1
    # Conditional extrema: mass t in the prefix and 1-t in the suffix,
    # independently enumerate their possible concentration vertices.
    conditional_checks=0
    for k in range(1,N):
        for j in range(1,N):
            if k==j:continue
            Q=tuple(sorted((k,j)))
            for a in range(8):
                t=F(a,7);actual=[]
                for l in range(k):
                    for r in range(k,N):
                        z=[F(0)]*N;z[l]=t;z[r]=1-t
                        actual.append(max(endpoint_width(c,Q,z) for c in C))
                assert max(actual)==conditional(k,j,t);conditional_checks+=1
    result={'status':'PASS','artifact_provenance':'Exact checker for the explicitly specified mathematical construction',
        'coefficients':[[str(v) for v in c] for c in C],
        'initial_widths':['1','1'],'budget':2,'query_dictionary':'Internal prefixes 1,...,5',
        'optimal_randomized_batch_mean_joint_width':'2/3',
        'optimal_randomized_adaptive_mean_joint_width':'1/2',
        'primal_mixture':[{'Q':list(Q),'mass':str(w)} for Q,w in PI.items()],
        'primal_vertex_expected_widths':list(map(str,primal)),
        'dual_vertex_masses':list(map(str,DUAL)),
        'all_batches':[{'Q':list(Q),'vertex_joint_widths':list(map(str,matrix[Q])),
                        'adverse_expectation':str(adverse[Q]),'hard_record_width':str(hard[Q])} for Q in QS],
        'hard_record':list(map(str,STAR)),'adaptive_branch_maxima':list(map(str,branch_max)),
        'exact_deterministic_first_query_results':plans,
        'checks':{'rational_grid_records':len(grid),'scalar_fiber_endpoint_checks':interval_checks,
                  'conditional_joint_extremum_checks':conditional_checks},
        'continuum_arguments':['For each batch J is a maximum of linear functions on the simplex and is convex; the six vertex mixture bounds imply the upper bound everywhere.',
            'The adverse vertex distribution lower-bounds every randomized batch.',
            'The two conditional maxima bound both adaptive branches for every first answer.',
            'The single hard record bounds every final set and therefore every adaptive seed by transcript consistency.',
            'All affine line intersections partition the first-answer interval into fixed-order cells; each min-of-max envelope is affine inside each cell.'],
        'scope':'Constructed exact-total uncapped example and specialized deterministic two-query algorithm; no empirical forecast improvement, operational benefit or historical priority verified',
        'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'PASS','adaptive':'1/2','batch':'2/3','checks':result['checks'],
                      'first_query_values':[r['worst_joint_width'] for r in plans]}))
if __name__=='__main__':main()

