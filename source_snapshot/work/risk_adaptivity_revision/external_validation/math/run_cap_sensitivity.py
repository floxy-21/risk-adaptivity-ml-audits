"""Frozen-subset capped-counter sensitivity; no hidden replay answers loaded."""
from __future__ import annotations
import csv
import hashlib
import itertools
import json
from fractions import Fraction as F
from pathlib import Path
import time
from collections import Counter

import numpy as np
from scipy.optimize import linprog
from robust_two_query import Model, worst_batch, first_query_value
from counter_two_side import (two_side, full_uncapped, capped_batch_worst,
    capped_at_profile, capped_first, capped_adaptive)

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BATCHES=list(itertools.combinations(range(1,6),2))
TOL=2e-8


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capped_model(c,cap):
    n=len(c)
    return Model(np.array([np.ones(n),-np.ones(n)]),np.array([1.,-1.]),
        np.array(list(map(float,c))),np.array([[float(h<k) for h in range(n)] for k in range(1,n)]),
        [(0.,float(cap))]*n)


def feasible_profile(raw,cap):
    out=[F(float(np.clip(x,0.,float(cap)))).limit_denominator(1000000) for x in raw]
    residual=1-sum(out)
    if residual:
        choices=[i for i,v in enumerate(out) if 0<=v+residual<=cap]
        if not choices: return None
        out[choices[0]]+=residual
    assert sum(out)==1 and all(0<=v<=cap for v in out)
    return tuple(out)


def finite_game(widths,tau):
    M=[[int(w<=tau) for w in row] for row in widths]
    arr=np.asarray(M,dtype=float); p=len(M)
    solved=linprog(np.r_[np.zeros(p),1.],A_ub=np.c_[arr.T,-np.ones(10)],b_ub=np.zeros(10),
        A_eq=[np.r_[np.ones(p),0.]],b_eq=[1.],bounds=[(0.,None)]*p+[(None,None)],method='highs',
        options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    assert solved.success,solved.message
    adverse=[F(float(max(0,x))).limit_denominator(1000000) for x in solved.x[:p]]
    mass=sum(adverse); adverse=[x/mass for x in adverse]
    upper=max(sum(adverse[i]*M[i][j] for i in range(p)) for j in range(10))
    batch=[F(float(max(0,-x))).limit_denominator(1000000) for x in solved.ineqlin.marginals]
    mass=sum(batch); batch=[x/mass for x in batch]
    lower_finite=min(sum(batch[j]*M[i][j] for j in range(10)) for i in range(p))
    assert lower_finite==upper and abs(float(upper)-solved.fun)<1e-9
    return upper,adverse,batch


def sparse_cover(c,cap,first,tau):
    seconds=[j for j in range(1,6) if j!=first]
    for count in [1,2]:
        for subset in itertools.combinations(seconds,count):
            value,_=capped_first(c,first,cap,subset)
            if value<=tau: return list(subset),value
    raise AssertionError('Helly pair cover absent despite adaptive guarantee')


def validate_arbitrary_n():
    rng=np.random.default_rng(20261012)
    checked=lpchecked=0; maximum=0.
    for n in range(3,25):
        for draw in range(4):
            c=[F(int(z),7) for z in rng.integers(-12,13,n)]
            best,rows=two_side(c)
            for row in rows:
                assert row['value']==full_uncapped(c,row['first'])
            assert best['value']==min(row['value'] for row in rows)
            if n<=10 and draw<2:
                model=capped_model(c,F(1))
                for row in rows:
                    v=first_query_value(model,row['first']-1)['value']
                    maximum=max(maximum,abs(v-float(row['value'])))
                    assert abs(v-float(row['value']))<=TOL
                lpchecked+=1
            checked+=1
    for c in [[F(1)]*6,list(map(F,[0,0,1,1,0,1])),list(map(F,[0,1,0]))]:
        best,rows=two_side(c)
        assert all(row['value']==full_uncapped(c,row['first']) for row in rows)
        checked+=1
    return {'rational_instances':checked,'full_conditional_envelopes':'exact equality',
            'generic_LP_instances':lpchecked,'max_LP_discrepancy':maximum,'seed':20261012}


def main():
    started=time.perf_counter()
    manifest=json.loads((HERE/'cap_sensitivity_manifest.json').read_text())
    assert digest(HERE/'CAP_SENSITIVITY_PROTOCOL.txt')==manifest['protocol_sha256']
    for path,expected in manifest['input_sha256'].items(): assert digest(ROOT/path)==expected
    selected=set(manifest['case_ids']); cases=[]
    for path in manifest['input_sha256']:
        if path.endswith('geometry.json'):
            cases += [r for r in json.loads((ROOT/path).read_text())['cases'] if r['id'] in selected]
    cases=sorted(cases,key=lambda r:r['id'])
    assert len(cases)==290 and {r['id'] for r in cases}==selected
    arbitrary=validate_arbitrary_n()
    constructed=[]
    cc=list(map(F,[0,0,1,1,0,1]))
    for cap in [F(1),F(1,2),F(1,3)]:
        (aa,kk),_=capped_adaptive(cc,cap)
        dd=min(capped_batch_worst(cc,q,cap) for q in BATCHES)
        val=capped_batch_worst(cc,(2,4),cap)
        lp=worst_batch(capped_model(cc,cap),(1,3))[0]
        assert abs(lp-float(val))<=TOL
        if cap==F(1,2): assert dd<=F(1,2) and val<=F(1,2)
        constructed.append({'cap':str(cap),'A_exact':str(aa),'D_exact':str(dd),
            'batch_2_4_worst_exact':str(val),'independent_batch_LP':lp,
            'initial_width_exact':str(capped_batch_worst(cc,(),cap))})
    rows=[]; witnesses=[]; max_D=max_A=max_terminal=0.; threshold_flags=[]
    scenario_names={F(1):'uncapped',F(1,2):'E/2',F(1,3):'E/3'}
    for index,case in enumerate(cases):
        original=[F.from_float(float(v)) for v in case['c']]
        scale=max(original)-min(original); assert scale>0 and case['E']>0
        c=[v/scale for v in original]
        physical=float(scale)*case['E']
        for cap in [F(1),F(1,2),F(1,3)]:
            name=scenario_names[cap]
            initial=capped_batch_worst(c,(),cap)
            (A,first),firsts=capped_adaptive(c,cap)
            worsts=[capped_batch_worst(c,q,cap) for q in BATCHES]
            D=min(worsts); det_index=worsts.index(D)
            model=capped_model(c,cap)
            profiles=set()
            for full in itertools.combinations(range(6),int(1/cap)):
                profiles.add(tuple(cap if i in full else F(0) for i in range(6)))
            for qi,q in enumerate(BATCHES):
                ld,u,v=worst_batch(model,tuple(j-1 for j in q))
                max_D=max(max_D,abs(ld-float(worsts[qi])))
                assert abs(ld-float(worsts[qi]))<=TOL
                for endpoint in [u,v]:
                    reconstructed=feasible_profile(endpoint,cap)
                    if reconstructed is not None:
                        profiles.add(reconstructed)
            for val,k in firsts:
                la=first_query_value(model,k-1)['value']
                max_A=max(max_A,abs(la-float(val)))
                assert abs(la-float(val))<=TOL
            if cap==1:
                best,_=two_side(c)
                assert best['value']==A
                assert abs(float(A)-case['geometry']['A'])<=TOL
                assert abs(float(D)-case['geometry']['det_value'])<=TOL
            profiles=sorted(profiles)
            widths=[[capped_at_profile(c,q,p,cap) for q in BATCHES] for p in profiles]
            # The protocol's fixed LP spot check uses the first and last case
            # and every 29th case, all batches, at the first feasible profile.
            if index % 29==0 or index==len(cases)-1:
                p=profiles[0]
                for qi,q in enumerate(BATCHES):
                    w=worst_batch(model,tuple(j-1 for j in q),np.array(list(map(float,p))))[0]
                    max_terminal=max(max_terminal,abs(w-float(widths[0][qi])))
                    assert abs(w-float(widths[0][qi]))<=TOL
            for threshold_name,tau in [('fixed_old_absolute',F(1,2)),('half_new_initial',initial/2)]:
                upper,adverse,mixture=finite_game(widths,tau)
                category='batch_suffices' if D<=tau else ('feedback_required' if A<=tau else 'adaptive_not_guaranteed')
                lower=F(1) if D<=tau else (F(1,2) if A<=tau else F(0))
                support=[]
                if D<=tau:
                    assert upper==1; support=[list(BATCHES[det_index])]
                elif A<=tau:
                    second_actions,cover_value=sparse_cover(c,cap,first,tau)
                    support=[sorted((first,j)) for j in second_actions]
                    lower=F(1,len(support)); assert lower<=upper<1
                exact=str(upper) if lower==upper else 'not established'
                if abs(float(A-tau))<=TOL or abs(float(D-tau))<=TOL:
                    threshold_flags.append({'id':case['id'],'scenario':name,'threshold':threshold_name,
                        'A_minus_tau_exact':str(A-tau),'D_minus_tau_exact':str(D-tau),
                        'resolution':'exact rational comparison'})
                row={'id':case['id'],'meter':case['meter'],'pair':case['model_a']+'/'+case['model_b'],
                    'scenario':name,'threshold':threshold_name,'class':category,
                    'E':case['E'],'old_W0':physical,'new_W0':float(initial)*physical,
                    'new_W0_over_old_exact':str(initial),'tau_over_old_exact':str(tau),
                    'A_over_old_exact':str(A),'D_over_old_exact':str(D),
                    'A_over_old':float(A),'D_over_old':float(D),
                    'finite_upper_exact':str(upper),'continuum_lower_exact':str(lower),
                    'continuum_success_exact':exact,'zero_query_suffices':initial<=tau,
                    'adaptive_first':first,'det_batch':str(BATCHES[det_index]),
                    'finite_profiles':len(profiles)}
                rows.append(row)
                witnesses.append({'id':case['id'],'scenario':name,'threshold':threshold_name,
                    'tau_over_old_exact':str(tau),'profiles':[list(map(str,p)) for p in profiles],
                    'adverse_weights':list(map(str,adverse)),'finite_game_batch_weights':list(map(str,mixture)),
                    'continuum_cover_support':support,'continuum_cover_weights':
                        [str(F(1,len(support)))]*len(support) if support else [],
                    'finite_upper_exact':str(upper),'continuum_lower_exact':str(lower),
                    'continuum_success_exact':exact})
        if (index+1)%25==0: print(f'cap sensitivity {index+1}/290',flush=True)
    groups=[]
    for scenario in scenario_names.values():
        for threshold in ['fixed_old_absolute','half_new_initial']:
            subset=[r for r in rows if r['scenario']==scenario and r['threshold']==threshold]
            counts=Counter(r['class'] for r in subset)
            groups.append({'scenario':scenario,'threshold':threshold,'cases':len(subset),
                'counts':dict(counts),'exact_half':sum(r['continuum_success_exact']=='1/2' for r in subset),
                'zero_query_suffices':sum(r['zero_query_suffices'] for r in subset),
                'mean_new_W0_over_old':float(np.mean([float(F(r['new_W0_over_old_exact'])) for r in subset])),
                'mean_A_over_old':float(np.mean([r['A_over_old'] for r in subset])),
                'mean_D_over_old':float(np.mean([r['D_over_old'] for r in subset])),
                'by_meter':{meter:dict(Counter(r['class'] for r in subset if r['meter']==meter))
                            for meter in sorted({r['meter'] for r in subset})}})
    report={'status':'PASS','scope':'Post-analysis illustrative-cap sensitivity of all 290 originally feedback-essential cases; no physical-cap or new-source claim',
        'protocol_sha256':manifest['protocol_sha256'],'selected_cases':290,'scenarios':3,
        'thresholds':2,'rows':len(rows),'constructed_check':constructed,
        'arbitrary_n_verification':arbitrary,'maximum_errors':{'batch_LP':max_D,'adaptive_LP':max_A,'terminal_LP':max_terminal},
        'LP_tolerance':1e-9,'value_tolerance':TOL,'threshold_boundary_cases':len(threshold_flags),
        'boundary_resolution':'exact rational formulas','summaries':groups,
        'seconds':time.perf_counter()-started,'source_sha256':digest(__file__)}
    with (HERE/'cap_sensitivity_cases.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (HERE/'cap_sensitivity_witnesses.json').write_text(json.dumps(witnesses,indent=2)+'\n')
    (HERE/'cap_sensitivity_boundaries.json').write_text(json.dumps(threshold_flags,indent=2)+'\n')
    (HERE/'cap_sensitivity_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__': main()
