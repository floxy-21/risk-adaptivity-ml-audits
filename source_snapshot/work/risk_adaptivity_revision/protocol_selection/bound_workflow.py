"""Task-bound wrapper for the saved-case reference acquisition selector.

Adapters must return readout envelopes, not unlabeled normalized numbers.
No network adapter is implemented. Metadata checking prevents accidental case
mixups; it does not authenticate a provider or calibrate physical readouts.
"""
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
from selector import Selector, canonical_plan

HERE=Path(__file__).resolve().parent;BASE=HERE.parent


def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()


class BoundWorkflow:
    def __init__(self):
        self.selector=Selector()
        raw=(HERE/'task_manifest.json').read_bytes()
        manifest=json.loads(raw)
        if manifest['schema']!='saved-audit-task-binding-v1':raise ValueError('Unsupported task-binding schema')
        for path,expected in manifest['inputs'].items():
            if digest((BASE/path).read_bytes())!=expected:raise ValueError('Task source changed: '+path)
        self.tasks={}
        for record in manifest['tasks']:
            task=record['task'];case_id=task['case_id']
            if digest(canonical(task))!=record['task_sha256']:raise ValueError('Task descriptor hash mismatch')
            proof=self.selector.fixed.get(case_id)
            if proof is None or task['contrast_coefficients_exact']!=proof['original_coefficients_exact']:
                raise ValueError('Task coefficients do not match the supplied certificate')
            if task['system_id']!=proof['system_id']:raise ValueError('Task meter does not match certificate')
            if case_id in self.tasks:raise ValueError('Duplicated task descriptor')
            self.tasks[case_id]=deepcopy(record)
        if set(self.tasks)!=set(self.selector.fixed):raise ValueError('Bound task panel differs from certified panel')
        self.manifest_sha256=digest(raw)

    def task(self,case_id):
        """Return the exact saved descriptor; new targets need new certificates."""
        return deepcopy(self.tasks[case_id]['task'])

    def plan(self,task,interface):
        if not isinstance(task,dict) or not isinstance(task.get('case_id'),str):
            raise ValueError('Saved task descriptor must be a mapping')
        expected=self.tasks.get(task.get('case_id'))
        if expected is None or task!=expected['task']:
            raise ValueError('Task metadata/coefficients/endpoints differ from the saved certified task')
        # Python equality aliases True with 1 and 1.0 with 1. The canonical
        # descriptor hash preserves the serialized identifier types as well.
        if digest(canonical(task))!=expected['task_sha256']:
            raise ValueError('Task descriptor types differ from the saved certified task')
        return {'task':deepcopy(task),'task_sha256':expected['task_sha256'],
                'task_manifest_sha256':self.manifest_sha256,
                'selection':self.selector.select(task['case_id'],interface)}

    def execute(self,plan,*,read_point,read_batch):
        """Callbacks receive requests containing the complete task binding.

        read_point(request) -> one envelope.
        read_batch(request) -> list of envelopes, one per requested boundary.
        Each envelope has task_sha256, system_id, feed_key, boundary,
        timestamp_utc, reading_unit and counter_kwh_exact (rational/decimal).
        """
        current=self.plan(plan['task'],plan['selection']['interface_manifest'])
        if canonical_plan(plan)!=canonical_plan(current):raise ValueError('Bound plan changed before execution')
        task=plan['task'];c0=F(task['start_counter_kwh_exact']);total=F(task['total_kwh_exact'])
        def request(boundaries,mode):
            return {'task_sha256':plan['task_sha256'],'task':deepcopy(task),
                    'boundaries':list(boundaries),'mode':mode}
        def unpack(envelope,boundary):
            if not isinstance(envelope,dict):raise ValueError('Malformed readout envelope')
            if (type(boundary) is not int or boundary not in range(1,6)
                    or type(envelope.get('system_id')) is not int
                    or type(envelope.get('boundary')) is not int):
                raise ValueError('Meter and boundary identifiers must be integers')
            expected={'task_sha256':plan['task_sha256'],'system_id':task['system_id'],
                      'feed_key':task['feed_key'],'boundary':boundary,
                      'timestamp_utc':task['query_timestamps_utc'][str(boundary)],
                      'reading_unit':task['reading_unit']}
            if any(envelope.get(k)!=v for k,v in expected.items()):
                raise ValueError('Readout envelope does not match requested task, boundary, timestamp or unit')
            value=envelope.get('counter_kwh_exact')
            if not isinstance(value,(str,int,F)) or isinstance(value,bool):
                raise ValueError('Use an exact rational/decimal readout token, not a rounded binary float')
            try:counter=F(value)
            except (ValueError,ZeroDivisionError,TypeError) as exc:raise ValueError('Invalid exact counter token') from exc
            return (counter-c0)/total
        def point(k):return unpack(read_point(request([k],'adaptive_point')),k)
        def batch(indices,*,mode):
            response=read_batch(request(indices,mode))
            if not isinstance(response,list) or len(response)!=len(indices):
                raise ValueError('Batch adapter must return one envelope per requested boundary')
            values={}
            for envelope in response:
                if not isinstance(envelope,dict):raise ValueError('Malformed readout envelope')
                k=envelope.get('boundary')
                if type(k) is not int:raise ValueError('Boundary identifiers must be integers')
                if k not in indices or k in values:raise ValueError('Missing, duplicated or unrequested boundary')
                values[k]=unpack(envelope,k)
            return values
        result=self.selector.execute(plan['selection'],read_point=point,read_batch=batch)
        result.update(task_sha256=plan['task_sha256'],task_manifest_sha256=self.manifest_sha256,
                      scope='Declared-model certificate for bound saved task; not source authentication or calibrated physical truth')
        return result
