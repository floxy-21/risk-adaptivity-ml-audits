from pathlib import Path
import json
import importlib.util
from importlib.machinery import SourceFileLoader
import numpy as np
from scipy.optimize import linprog as real_linprog
HERE=Path(__file__).resolve().parent
loader=SourceFileLoader('_saved_face_checker',str(HERE/'verify_decision_confirmation_before_face_fix.py.txt'))
spec=importlib.util.spec_from_loader(loader.name,loader)
checker=importlib.util.module_from_spec(spec);loader.exec_module(checker)
fixture=json.loads((HERE/'randomized_failure.json').read_text())
arguments=[np.asarray(fixture[k],float) for k in ['a','b','observed','totals']]
reports=[]
for label,tolerance,remove_slack in [('original',None,False),('tight9_exact',1e-9,True),('tight10_exact',1e-10,True),('tight10_slack',1e-10,False)]:
    calls=[]
    def solve(*args,**kwargs):
        if tolerance:
            kwargs['method']='highs-ds'
            kwargs['options']={'primal_feasibility_tolerance':tolerance,'dual_feasibility_tolerance':tolerance}
        if len(calls)==1 and remove_slack:
            kwargs['b_ub']=kwargs['b_ub']-1e-9
        result=real_linprog(*args,**kwargs)
        calls.append({'objective':np.asarray(args[0]).tolist(),'A_ub':np.asarray(kwargs.get('A_ub')).tolist(),
                      'b_ub':np.asarray(kwargs.get('b_ub')).tolist(),'A_eq':np.asarray(kwargs.get('A_eq')).tolist(),
                      'b_eq':np.asarray(kwargs.get('b_eq')).tolist(),'success':result.success,
                      'x':result.x.tolist() if result.success else None,'fun':float(result.fun) if result.success else None})
        return result
    checker.linprog=solve
    try:
        outcome=checker.verify_randomized(*arguments,fixture['chosen'],fixture['diagnostics'])
        status='passed'
    except AssertionError as error:
        outcome=str(error);status='failed'
    reports.append({'label':label,'status':status,'result':outcome,'solves':calls})
result={'case_id':fixture['case_id'],'stage':fixture['stage'],
        'recorded':fixture['diagnostics'],'modes':reports}
(HERE/'randomized_failure_probe.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'case_id':fixture['case_id'],'stage':fixture['stage'],
                  'modes':[{'label':r['label'],'status':r['status'],'result':r['result'],'objectives':[s['fun'] for s in r['solves']]} for r in reports]},indent=2))
