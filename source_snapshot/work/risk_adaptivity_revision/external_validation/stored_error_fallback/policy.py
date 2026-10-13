"""Executable, solver-free certified two-or-three-reading acquisition policy.

Call execute(case_id, read_boundary). The callback receives a one-based internal
boundary in 1..5 and returns the stored cumulative readout relative to the
known starting counter, divided by the exact retained total E.  Use Fraction or
a decimal string when exact decimal normalization is intended.  Binary64
answers are represented as their exact stored binary rationals.

The guarantee is conditional on the declared nonnegative-increment model,
exact outer counters, and a fixed internal stored-readout error <= .01 E.
It is not a calibrated assertion about a physical meter.  No network, forecast
training, hidden fine-resolution answers, or numerical optimizer is used here.
"""
from collections import Counter
from fractions import Fraction as F
import argparse
import json
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent
DELTA=F(1,100)
TAU=F(1,2)


def as_fraction(value):
    return F.from_float(value) if isinstance(value,float) else F(value)


def plan(case_id):
    """Return a certificate-selected plan without accessing any observations."""
    prescriptions=json.loads((HERE/'prescriptions.json').read_text())
    matches=[p for p in prescriptions if p['id']==case_id]
    if len(matches)!=1: raise KeyError(case_id)
    return matches[0]


def transcript_is_feasible(answers):
    """Exact feasibility of observed noisy prefixes with nonnegative increments."""
    prefix=F(0)
    for boundary,value in sorted(answers.items()):
        if boundary not in range(1,6): return False
        lower=max(F(0),value-DELTA)
        upper=min(F(1),value+DELTA)
        prefix=max(prefix,lower)
        if prefix>upper: return False
    return prefix<=1


def execute(case_id, read_boundary):
    """Acquire exactly the certified budget through the supplied callback.

    For a two-reading case, the first answer selects the second boundary by
    comparing certified affine upper bounds with exact rational arithmetic.
    For a fallback case, all three boundaries are chosen before any answer.
    Out-of-model transcripts raise ValueError and are never certified.
    """
    p=plan(case_id)
    acquired={}; sequence=[]
    def ask(boundary):
        assert boundary not in acquired
        answer=as_fraction(read_boundary(boundary))
        acquired[boundary]=answer; sequence.append(boundary)
        if not transcript_is_feasible(acquired):
            raise ValueError('Observed transcript is infeasible under the declared error model')
        return answer
    if p['policy_type']=='fixed_batch_fallback':
        fixed=tuple(p['query_boundaries'])
        for boundary in fixed: ask(boundary)
        upper=F(p['batch_certified_upper_exact'])
    else:
        records=json.loads((HERE/'branch_certificates.json').read_text())['certificates']
        cert=next(r for r in records if r['id']==case_id)
        assert cert['first_query']==p['first_query']
        t=ask(p['first_query'])
        options=[(F(r['intercept_exact'])+F(r['slope_exact'])*t,r['second_query']) for r in cert['lines']]
        upper,second=min(options)
        # The exact full-domain envelope certificate ensures this assertion for
        # every feasible first answer. No conditional solver is called.
        assert upper<=TAU
        ask(second)
    assert len(sequence)==p['hard_query_budget'] and upper<=TAU
    return {'id':case_id,'policy_type':p['policy_type'],
            'query_boundaries':sequence,
            'normalized_stored_answers_exact':{str(k):str(v) for k,v in acquired.items()},
            'hard_query_budget':p['hard_query_budget'],
            'guaranteed_width_over_original_W0_upper_exact':str(upper),
            'threshold_over_original_W0_exact':str(TAU),
            'transcript_feasible':True}


def self_test(output):
    """Constructed execution tests, not additional recorded-data evidence.

    The fixed test set comprises all six simplex vertices and the uniform
    profile crossed with errors all0, all+delta, all-delta, and both alternating
    signs. It covers feasible first-answer endpoints and both certified branches.
    """
    started=time.perf_counter()
    prescriptions=json.loads((HERE/'prescriptions.json').read_text())
    profiles=[[F(int(i==j)) for i in range(6)] for j in range(6)]+[[F(1,6)]*6]
    errors=[[F(0)]*5,[DELTA]*5,[-DELTA]*5,
            [DELTA*(-1)**j for j in range(5)],[-DELTA*(-1)**j for j in range(5)]]
    executions=0; calls=0; branches={}; by_budget=Counter(); all_trace=[]
    for p in prescriptions:
        branches[p['id']]=Counter()
        for pi,x in enumerate(profiles):
            for ei,e in enumerate(errors):
                observed=[]
                def reader(k):
                    observed.append(k)
                    return sum(x[:k])+e[k-1]
                result=execute(p['id'],reader)
                assert observed==result['query_boundaries']
                assert len(set(observed))==len(observed)==p['hard_query_budget']
                if p['policy_type']=='existing_two_query_adaptive_support':
                    branches[p['id']][str(observed[1])]+=1
                elif p['policy_type']=='fixed_batch_fallback':
                    assert observed==p['query_boundaries']
                executions+=1;calls+=len(observed);by_budget[len(observed)]+=1
                all_trace.append({'id':p['id'],'profile':pi,'error_pattern':ei,
                                  'queries':observed,'upper_exact':result['guaranteed_width_over_original_W0_upper_exact']})
    invalid_rejections=0
    for p in prescriptions:
        try: execute(p['id'],lambda k:F(2))
        except ValueError: invalid_rejections+=1
        else: raise AssertionError('Out-of-model answer was certified')
    report={'status':'PASS','cases':len(prescriptions),'constructed_executions':executions,
            'callback_readings':calls,'executions_by_budget':dict(by_budget),
            'out_of_model_cases_rejected':invalid_rejections,
            'observed_second_branches':{k:dict(v) for k,v in branches.items() if v},
            'online_optimization_calls':0,'network_calls':0,
            'scope':'Implementation tests on fixed constructed feasible profiles; not new empirical performance results',
            'seconds':time.perf_counter()-started}
    output.write_text(json.dumps(report,indent=2)+'\n')
    (output.parent/'execution_test_traces.json').write_text(json.dumps(all_trace,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='observed_second_branches'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--output',type=Path,default=HERE/'execution_checks.json')
    args=parser.parse_args()
    if not args.self_test: parser.error('Use --self-test, or import execute(case_id, read_boundary)')
    self_test(args.output)
