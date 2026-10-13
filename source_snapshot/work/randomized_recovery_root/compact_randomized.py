"""Independent compact mixed-batch LP; research implementation, not manuscript."""
from itertools import combinations, product
from pathlib import Path
import hashlib, json, math, time
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

HERE = Path(__file__).resolve().parent

def sparse(rows, n):
    rr, cc, vv = [], [], []
    for r, row in enumerate(rows):
        for c, v in row.items():
            if v:
                rr.append(r); cc.append(c); vv.append(v)
    return coo_matrix((vv, (rr, cc)), shape=(len(rows), n)).tocsr()

def solve_compact(coefficients, energies, budget, *, return_metadata=False):
    start = time.perf_counter()
    original = [np.asarray(c, dtype=float) for c in coefficients]
    index_maps = [np.argsort(c, kind='stable') for c in original]
    cs = [c[order] for c,order in zip(original,index_maps)]
    energies = np.asarray(energies, dtype=float)
    assert all(len(c) >= 2 and np.isfinite(c).all() for c in cs)
    assert (energies > 0).all() and len(energies) == len(cs)
    assert isinstance(budget, int) and budget >= 0
    caps = [len(c)-1 for c in cs]
    q = min(budget, sum(caps))
    nvars = len(cs)  # t_g: maximum expected coefficient in each block
    objective = list(energies)
    eq, eqrhs, ub, ubrhs = [], [], [], []
    flow = {}
    scenario = [[{g: -1.} for _ in c] for g, c in enumerate(cs)]
    options = []
    interiors = {}
    def var():
        nonlocal nvars
        idx = nvars; nvars += 1; objective.append(0.)
        return idx
    def add(row, col, value):
        row[col] = row.get(col, 0.) + value
    for g, c in enumerate(cs):
        m = len(c)
        prefix_cap, suffix_cap = sum(caps[:g]), sum(caps[g+1:])
        for b in range(min(q, prefix_cap)+1):
            for k in range(min(caps[g], q-b)+1):
                if b+k+suffix_cap < q:
                    continue
                r = m-k
                endpoints = [(0, 0)] if r == 1 else [(l,u) for l in range(m) for u in range(l+r-1,m)]
                for l,u in endpoints:
                    x = var()
                    add(flow.setdefault((g,b), {}), x, 1.)
                    add(flow.setdefault((g+1,b+k), {}), x, -1.)
                    options.append((g,b,k,l,u,x))
                    interiors[x] = []
                    width = float(c[u]-c[l])
                    if r == 1:
                        continue
                    add(scenario[g][l], x, width)
                    add(scenario[g][u], x, width)
                    interior_eq = {x: -(r-2.)}
                    if r > 2:
                        for i in range(l+1,u):
                            z = var()
                            interiors[x].append((i,z))
                            interior_eq[z] = 1.
                            ub.append({z: 1., x: -1.}); ubrhs.append(0.)
                            add(scenario[g][i], z, width)
                        eq.append(interior_eq); eqrhs.append(0.)
    for node, row in sorted(flow.items()):
        eq.append(row)
        eqrhs.append(1. if node == (0,0) else -1. if node == (len(cs),q) else 0.)
    for block in scenario:
        for row in block:
            ub.append(row); ubrhs.append(0.)
    ae, au = sparse(eq,nvars), sparse(ub,nvars)
    be, bu = np.array(eqrhs), np.array(ubrhs)
    res = linprog(objective, A_ub=au, b_ub=bu, A_eq=ae, b_eq=be, bounds=(0,None), method='highs')
    assert res.success, res.message
    feasibility = max(float(np.max(np.abs(ae@res.x-be))), float(np.max(au@res.x-bu)), float(-np.min(res.x)), 0.)
    assert feasibility <= 1e-7
    result = {'value':float(res.fun), 'variables':nvars, 'equalities':len(eq), 'inequalities':len(ub),
            'feasibility_max':feasibility, 'seconds':time.perf_counter()-start,
            'positive_edge_options':int(sum(res.x[x]>1e-9 for _,_,_,_,_,x in options))}
    if return_metadata:
        result['metadata'] = {
            'query_count':q,
            'sorted_coefficients':[c.tolist() for c in cs],
            'original_index_maps':[order.tolist() for order in index_maps],
            'block_epigraphs':res.x[:len(cs)].tolist(),
            'edges':[{'group':g,'spent':b,'queries':k,'lower':l,'upper':u,
                      'flow':float(res.x[x]),
                      'interior_masses':[(i,float(res.x[z])) for i,z in interiors[x]]}
                     for g,b,k,l,u,x in options]}
    return result

def solve_enumerated(coefficients, energies, budget):
    start = time.perf_counter()
    cs = [np.asarray(c,dtype=float) for c in coefficients]
    q = min(budget, sum(len(c)-1 for c in cs))
    opts=[]
    for c in cs:
        block=[]
        for k in range(min(q,len(c)-1)+1):
            for queried in combinations(range(len(c)),k):
                retained=[i for i in range(len(c)) if i not in queried]
                v=np.zeros(len(c)); v[retained]=np.ptp(c[retained])
                block.append((k,v))
        opts.append(block)
    columns=[]
    deterministic=[]
    for items in product(*opts):
        if sum(k for k,v in items) != q:
            continue
        columns.append(np.concatenate([v for k,v in items]))
        deterministic.append(sum(e*float(v.max()) for e,(k,v) in zip(energies,items)))
    a=np.array(columns).T; n=a.shape[1]; groups=len(cs)
    constraints=np.zeros((a.shape[0],n+groups)); constraints[:,:n]=a
    offset=0
    for g,c in enumerate(cs):
        constraints[offset:offset+len(c),n+g]=-1.; offset+=len(c)
    eq=np.zeros((1,n+groups));eq[0,:n]=1.
    res=linprog(np.r_[np.zeros(n),energies],A_ub=constraints,b_ub=np.zeros(a.shape[0]),A_eq=eq,b_eq=[1.],bounds=(0,None),method='highs')
    assert res.success,res.message
    return {'value':float(res.fun),'deterministic':min(deterministic),'batches':n,
            'support':int((res.x[:n]>1e-9).sum()),'seconds':time.perf_counter()-start}

def main():
    protocol_hash=hashlib.sha256((HERE/'protocol.txt').read_bytes()).hexdigest()
    rng=np.random.default_rng(20261010); cases=[]
    for m in range(3,9):
        for rep in range(4):
            cases.append(([rng.integers(-5,9,m).tolist()],[int(rng.integers(1,6))],(m+rep)%(m-1)))
    for index in range(12):
        sizes=[3+index%3,3+(index//3)%3]
        cases.append(([rng.integers(-5,9,m).tolist() for m in sizes],rng.integers(1,6,2).tolist(),index%5))
    for index in range(6):
        cases.append(([rng.integers(-5,9,3).tolist() for _ in range(3)],rng.integers(1,6,3).tolist(),index%5))
    results=[]
    for i,(cs,es,b) in enumerate(cases):
        compact=solve_compact(cs,es,b); full=solve_enumerated(cs,es,b)
        error=abs(compact['value']-full['value'])
        assert error<=1e-7+1e-7*abs(full['value']),(i,compact,full)
        assert compact['value']<=full['deterministic']+1e-7
        results.append({'case':i,'coefficients':cs,'energies':es,'budget':b,'compact':compact,'enumerated':full,'error':error})
    sharp=[]
    for m,r in [(4,2),(6,2),(9,3),(12,2)]:
        c=np.concatenate([10*j+np.linspace(0,1,r) for j in range(m//r)])
        compact=solve_compact([c],[1],m-r); full=solve_enumerated([c],[1],m-r)
        assert abs(compact['value']-r/m)<=1e-7
        assert abs(full['deterministic']-1.)<=1e-7
        sharp.append({'m':m,'retained':r,'budget':m-r,'compact':compact,'enumerated':full,'sharp_ratio':m/r})
    scale=[]
    for m,b in [(60,4),(120,6)]:
        c=np.linspace(-3,4,m)
        scale.append({'m':m,'budget':b,'number_of_fixed_size_batches':math.comb(m,b),'compact':solve_compact([c],[1],b)})
    result={'status':'passed','protocol_sha256':protocol_hash,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'random_cases':len(results),'max_objective_discrepancy':max(r['error'] for r in results),
            'cases':results,'sharp_examples':sharp,'scalability':scale,
            'scope':'Ordinary floating-point solver checks. Synthetic algorithm validation, not measured field impact or a novelty claim.'}
    (HERE/'compact_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','random_cases','max_objective_discrepancy','sharp_examples','scalability']},indent=2))

if __name__=='__main__':main()
