"""Export transparent planning examples from the existing certified tasks.

One example per system: first task for system1, first fallback task for systems2
and7. This is a didactic choice, not a new sample or performance experiment.
"""
from fractions import Fraction as F
import json
from pathlib import Path
from bound_workflow import BoundWorkflow

HERE=Path(__file__).resolve().parent


def main():
    workflow=BoundWorkflow();rows=[]
    for system in [1,2,7]:
        ids=sorted(k for k,v in workflow.tasks.items() if v['task']['system_id']==system)
        if system in [2,7]:ids=[k for k in ids if k not in workflow.selector.branch]
        task=workflow.task(ids[0]);c=list(map(F,task['contrast_coefficients_exact']))
        width0=F(task['total_kwh_exact'])*(max(c)-min(c))
        plans={name:workflow.plan(task,workflow.selector.scenario(name))['selection']
               for name in ['public_bulk','restricted_three_readings','restricted_two_readings']}
        rows.append({'task':task,'task_sha256':workflow.tasks[task['case_id']]['task_sha256'],
                     'coefficient_display_approximate':list(map(float,c)),
                     'initial_width_exact':str(width0),'precision_target_exact':str(width0/2),
                     'plans':plans,'selection_reason':'Pedagogical example; no representative-frequency claim'})
    output={'scope':'Saved real task geometry; no response execution, new API trial or empirical performance result',
            'examples':rows}
    (HERE/'workflow_examples.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps([{'case':r['task']['case_id'],'E_kwh':float(F(r['task']['total_kwh_exact'])),
                       'coefficients':r['coefficient_display_approximate'],
                       'restricted_plan':r['plans']['restricted_three_readings']['selected']['protocol'],
                       'boundaries':r['plans']['restricted_three_readings']['selected']['query_boundaries'],
                       'first':r['plans']['restricted_three_readings']['selected'].get('first_query'),
                       'seconds':r['plans']['restricted_three_readings']['selected'].get('successor_boundaries')}
                      for r in rows],indent=2))


if __name__=='__main__':main()
