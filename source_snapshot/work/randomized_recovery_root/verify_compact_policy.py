"""Independent atom-enumeration and index/budget checks of compact policy API."""
from pathlib import Path
from itertools import product
from fractions import Fraction
import hashlib
import json
import math
import time
import numpy as np
from compact_policy import solve_policy
from compact_randomized import solve_enumerated

HERE = Path(__file__).resolve().parent


def subset_atoms(cumulative, k):
    """Enumerate uniform-offset sampling intervals without calling sampler."""
    if k == 0:
        return [(1., ())]
    assert cumulative[-1] == k
    breaks = sorted(set([Fraction(0),Fraction(1)] + [x-math.floor(x) for x in cumulative]))
    atoms = []
    for lo,hi in zip(breaks,breaks[1:]):
        if hi <= lo:
            continue
        offset = (lo+hi)/2
        selected = []
        for j in range(k):
            point = offset+j
            matches = [i for i, upper in enumerate(cumulative) if point < upper]
            if not matches:
                raise AssertionError('No atom interval contains the sampling point')
            selected.append(matches[0])
        assert len(set(selected)) == k
        atoms.append((float(hi-lo),tuple(selected)))
    return atoms


def policy_atoms(policy):
    states = [(1.,0,[() for _ in policy.coefficients])]
    for g,original_group in enumerate(policy.active_groups):
        next_states=[]
        for prob,spent,batch in states:
            for edge in policy.edges_by_node[(g,spent)]:
                m=len(policy.index_maps[g]); r=m-edge['queries']
                interiors=subset_atoms(edge['systematic_cumulative'],max(0,r-2))
                for atom_mass, subset in interiors:
                    retained={0} if r == 1 else {edge['lower'],edge['upper']}
                    retained.update(edge['interior_indices'][i] for i in subset)
                    queried=tuple(sorted(int(policy.index_maps[g][i]) for i in range(m) if i not in retained))
                    newbatch=list(batch);newbatch[original_group]=queried
                    next_states.append((prob*edge['conditional_probability']*atom_mass,
                                        spent+len(queried),newbatch))
        states=next_states
    return states


def check_batch(policy,batch):
    count=sum(len(q) for q in batch)
    assert count == policy.query_count and count <= policy.budget
    for g,(c,q) in enumerate(zip(policy.coefficients,batch)):
        assert len(q) == len(set(q)) and all(0<=i<len(c) for i in q)
        if g not in policy.active_groups:
            assert not q


def main():
    started=time.perf_counter()
    original=json.loads((HERE/'compact_verification.json').read_text())
    cases=[(x['coefficients'],x['energies'],x['budget']) for x in original['cases']]
    cases += [([[3.,0.,4.,1.]],[1.],0), ([[3.,0.,4.,1.]],[1.],99),
              ([[3.,0.,4.,1.],[5.],[2.,2.],[4.,7.],[]],[1.,8.,9.,0.,0.],2),
              ([[2.,2.],[5.],[]],[7.,4.,0.],10),
              ([[3.,0.,4.,1.],[9.,5.,2.]],[1.,4.],2),
              ([],[],0)]
    rng=np.random.default_rng(2026101007)
    reports=[];draws=0;max_coef=0.;max_value=0.
    for index,(cs,es,budget) in enumerate(cases):
        policy=solve_policy(cs,es,budget)
        atoms=policy_atoms(policy)
        assert abs(sum(p for p,_,_ in atoms)-1.)<=1e-10
        expected=[np.zeros(len(c)) for c in cs]
        for probability,spent,batch in atoms:
            check_batch(policy,batch)
            assert spent==policy.query_count
            for g,(c,queried) in enumerate(zip(cs,batch)):
                retained=[i for i in range(len(c)) if i not in queried]
                span=float(np.ptp(np.asarray(c)[retained])) if len(retained)>1 and es[g]>0 else 0.
                expected[g][retained]+=probability*span
        error=max((float(np.max(np.abs(a-b),initial=0.)) for a,b in zip(expected,policy.expected_coefficients)),default=0.)
        assert error<=1e-7
        value=sum(e*float(a.max(initial=0.)) for e,a in zip(es,expected))
        active=policy.active_groups
        oracle=solve_enumerated([cs[g] for g in active],[es[g] for g in active],budget)['value'] if active else 0.
        value_error=abs(value-oracle)
        assert value_error<=1e-7*(1.+abs(oracle))
        max_coef=max(max_coef,error);max_value=max(max_value,value_error)
        y=[]
        for c,e in zip(cs,es):
            if len(c):
                v=rng.dirichlet(np.ones(len(c)))*e
                y.append(v)
            else:
                y.append([])
        assert policy.expected_width_at(y)<=policy.worst_expected_width+1e-7
        for _ in range(100):
            check_batch(policy,policy.sample(rng));draws+=1
        reports.append({'case':index,'atoms':len(atoms),'coefficient_error':error,
                        'objective_error':value_error,'query_count':policy.query_count,
                        'diagnostics':policy.diagnostics})
    c=np.linspace(-3,4,120)[::-1]
    large=solve_policy([c],[1.],6)
    for _ in range(1000):
        batch=large.sample(rng);check_batch(large,batch);draws+=1
    invalid=[([[1.,2.]],[float('inf')],1), ([[1.,float('nan')]],[1.],1),
             ([[]],[1.],0), ([[1.]],[1.],-1), ([[1.]],[1.],True),
             ([[1.]],[1.],.5), ([[1.]],[1.,2.],0), ([[1.]],[float('nan')],0)]
    rejected=0
    for args in invalid:
        try:
            solve_policy(*args)
        except ValueError:
            rejected+=1
        else:
            raise AssertionError('Invalid input accepted')
    result={'status':'passed','cases':len(cases),'seeded_draws':draws,'invalid_inputs_rejected':rejected,
            'max_atom_coefficient_error':max_coef,'max_enumerated_objective_error':max_value,
            'reports':reports,'large_case':{'m':120,'budget':6,'value':large.worst_expected_width,
                                          'diagnostics':large.diagnostics},
            'source_hashes':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in
                             ('compact_randomized.py','compact_policy.py','verify_compact_policy.py','policy_protocol.txt')},
            'source_value_report_sha256':hashlib.sha256((HERE/'compact_verification.json').read_bytes()).hexdigest(),
            'seconds':time.perf_counter()-started,
            'scope':'Exact mixture atom reconstruction on small cases; ordinary floating-point LP tolerance. No empirical outcomes changed.'}
    (HERE/'policy_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','cases','seeded_draws','invalid_inputs_rejected','max_atom_coefficient_error','max_enumerated_objective_error','seconds']},indent=2))


if __name__=='__main__':
    main()
