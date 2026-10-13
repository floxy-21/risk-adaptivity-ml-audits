"""Targeted integration checks for saved-task binding, no new data or LPs."""
from copy import deepcopy
from fractions import Fraction as F
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
from bound_workflow import BoundWorkflow, canonical
from selector import Selector, FALLBACK

HERE=Path(__file__).resolve().parent


def synthetic_response(request):
    """Fixed constructed uniform profile with zero error, never a real replay."""
    task=request['task'];start=F(task['start_counter_kwh_exact']);total=F(task['total_kwh_exact'])
    return [{'task_sha256':request['task_sha256'],'system_id':task['system_id'],
             'feed_key':task['feed_key'],'boundary':k,
             'timestamp_utc':task['query_timestamps_utc'][str(k)],
             'reading_unit':task['reading_unit'],'counter_kwh_exact':str(start+total*F(k,6))}
            for k in request['boundaries']]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=HERE/'binding_checks')
    parser.add_argument('--optimized-child',action='store_true')
    args=parser.parse_args();started=time.perf_counter()
    original=Path.read_bytes
    def bad_bytes(path):
        raw=original(path)
        return raw+b' ' if path==FALLBACK/'fixed_batch_certificates.json' else raw
    with patch.object(Path,'read_bytes',bad_bytes):
        try:Selector()
        except ValueError:hash_rejected=True
        else:raise RuntimeError('Altered source accepted')
    if args.optimized_child:
        print(json.dumps({'status':'PASS','hash_rejection_with_assertions_disabled':hash_rejected}));return
    workflow=BoundWorkflow();executed=blocked=0
    for case_id in workflow.tasks:
        for interface in workflow.selector.lock['scenarios']:
            plan=workflow.plan(workflow.task(case_id),interface);calls=[]
            def point(request):calls.append(request);return synthetic_response(request)[0]
            def batch(request):calls.append(request);return synthetic_response(request)
            if plan['selection']['status']=='CERTIFIED':
                result=workflow.execute(plan,read_point=point,read_batch=batch)
                if result['task_sha256']!=plan['task_sha256']:raise RuntimeError('Output binding lost')
                if F(result['guaranteed_width_over_original_W0_upper_exact'])>F(1,2):raise RuntimeError('Bound failed')
                executed+=1
            else:
                try:workflow.execute(plan,read_point=point,read_batch=batch)
                except ValueError:blocked+=1
                else:raise RuntimeError('Escalation dispatched')
                if calls:raise RuntimeError('Escalation used responses')
    case_id=sorted(workflow.selector.branch)[0];task=workflow.task(case_id)
    interface=workflow.selector.scenario('public_bulk')
    task_mutations=[]
    for field,value in [('system_id',True),('system_id',1.0),('system_id',999),('start_utc','2025-01-01T00:00:00Z'),
                        ('total_kwh_exact','1'),('models',['wrong','models']),
                        ('error_bound_over_total_exact','1/50')]:
        changed=deepcopy(task);changed[field]=value;task_mutations.append(changed)
    changed=deepcopy(task);changed['contrast_coefficients_exact'][0]='99';task_mutations.append(changed)
    for changed in task_mutations:
        try:workflow.plan(changed,interface)
        except ValueError:pass
        else:raise RuntimeError('Mismatched task accepted')
    plan=workflow.plan(task,interface);response_rejections=0
    mutations=[('task_sha256','0'*64),('system_id',999),('feed_key','wrong'),
               ('timestamp_utc','2025-01-01T00:00:00Z'),('reading_unit','Wh'),
               ('boundary',5),('counter_kwh_exact',1.23),('counter_kwh_exact','NaN')]
    for field,value in mutations:
        def bad_batch(request):
            response=synthetic_response(request);response[0][field]=value;return response
        try:workflow.execute(plan,read_point=lambda r:None,read_batch=bad_batch)
        except ValueError:response_rejections+=1
        else:raise RuntimeError('Mismatched response accepted')
    # Verified bytes remain the data used: a changed disk path after loading
    # cannot silently replace the in-memory adaptive branch certificate.
    adaptive=workflow.plan(task,workflow.selector.scenario('restricted_three_readings'))
    original_text=Path.read_text
    def reject_branch_reopen(path,*args,**kwargs):
        if path==FALLBACK/'branch_certificates.json':raise RuntimeError('Unverified runtime reopen')
        return original_text(path,*args,**kwargs)
    with patch.object(Path,'read_text',reject_branch_reopen):
        workflow.execute(adaptive,read_point=lambda r:synthetic_response(r)[0],read_batch=synthetic_response)
    child=subprocess.run([sys.executable,'-O',str(Path(__file__)), '--optimized-child'],capture_output=True,text=True,check=True)
    optimized=json.loads(child.stdout)
    if optimized['status']!='PASS':raise RuntimeError('Optimized hash guard failed')
    report={'status':'PASS','bound_tasks':len(workflow.tasks),'constructed_bound_executions':executed,
            'escalations_without_callbacks':blocked,'changed_task_rejections':len(task_mutations),
            'bad_response_rejections':response_rejections,'source_hash_guard_with_python_O':True,
            'verified_branch_bytes_not_reopened':True,'new_network_calls':0,'new_model_fits':0,
            'scope':'Metadata/source binding and constructed dispatch checks; not new empirical benefit or data-origin authentication',
            'task_manifest_sha256':workflow.manifest_sha256,
            'bound_workflow_sha256':hashlib.sha256((HERE/'bound_workflow.py').read_bytes()).hexdigest(),
            'seconds':time.perf_counter()-started}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
