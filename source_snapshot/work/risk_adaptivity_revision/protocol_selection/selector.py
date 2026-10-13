"""Certificate-aware acquisition-interface selector and offline dispatcher.

No network calls, model fitting, new optimization or hidden-answer selection.
Logical acquisition callbacks are not equated with HTTP transactions.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from fractions import Fraction as F
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import time
import types

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
FALLBACK=BASE/'external_validation/stored_error_fallback'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_plan(value):
    """Keep JSON identifier types distinct when validating a saved plan."""
    try:
        return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (TypeError,ValueError) as exc:
        raise ValueError('Acquisition plans must contain finite JSON values') from exc


class Selector:
    def __init__(self):
        self.lock=json.loads((HERE/'protocol_lock.json').read_text())
        if digest(HERE/'PROTOCOL.txt')!=self.lock['protocol_sha256']:
            raise ValueError('Frozen selector protocol changed')
        self.source_bytes={}
        for path,sha in self.lock['inputs'].items():
            raw=(BASE/path).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=sha:
                raise ValueError('Frozen dependency changed: '+path)
            self.source_bytes[path]=raw
        prefix='external_validation/stored_error_fallback/'
        self.fixed={r['id']:r for r in json.loads(self.source_bytes[prefix+'fixed_batch_certificates.json'])['certificates']}
        self.branch={r['id']:r for r in json.loads(self.source_bytes[prefix+'branch_certificates.json'])['certificates']}
        self.prescriptions={r['id']:r for r in json.loads(self.source_bytes[prefix+'prescriptions.json'])}
        # Execute the bytes that were actually hashed; do not reopen a mutable
        # source path between validation and import. The helper is local code.
        self.policy=types.ModuleType('certified_fallback_policy')
        self.policy.__file__=str(FALLBACK/'policy.py')
        exec(compile(self.source_bytes[prefix+'policy.py'],self.policy.__file__,'exec'),self.policy.__dict__)
        if len(self.fixed)!=29 or len(self.branch)!=22:
            raise ValueError('Unexpected certificate panel')

    def scenario(self,scenario_id):
        return deepcopy(next(s for s in self.lock['scenarios'] if s['id']==scenario_id))

    def validate(self,interface):
        required={'measurement_model','maximum_optional_readings','maximum_information_rounds',
                  'permitted_boundaries','bulk_returns_boundaries','preference','point_transport',
                  'scalar_reading_unit','round_unit','id','scenario_kind','bulk_allowed',
                  'fixed_batch_allowed','adaptive_allowed','exclusion_of_bulk_reason'}
        if not isinstance(interface,dict) or not required<=interface.keys():
            raise ValueError('Complete acquisition-interface mapping required')
        for key in ['bulk_allowed','fixed_batch_allowed','adaptive_allowed']:
            if type(interface[key]) is not bool:
                raise ValueError('Acquisition permissions must be explicit booleans')
        for key in ['id','scenario_kind']:
            if not isinstance(interface[key],str) or not interface[key].strip():
                raise ValueError('Interface identity and scenario kind must be nonempty strings')
        if not interface['bulk_allowed'] and (
                not isinstance(interface['exclusion_of_bulk_reason'],str)
                or not interface['exclusion_of_bulk_reason'].strip()):
            raise ValueError('An excluded bulk interface requires an explicit reason')
        if interface['measurement_model']!=self.lock['measurement_model']:
            raise ValueError('No certificate is supplied for the requested measurement model or threshold')
        for key in ['maximum_optional_readings','maximum_information_rounds']:
            value=interface[key]
            if value is not None and (not isinstance(value,int) or isinstance(value,bool) or value<0):
                raise ValueError('Budgets must be nonnegative integers or None')
        for key in ['permitted_boundaries','bulk_returns_boundaries']:
            values=interface[key]
            if not isinstance(values,list) or any(type(k) is not int for k in values):
                raise ValueError('Query boundaries must be a list of integer identifiers')
            if len(set(values))!=len(values) or not set(values)<=set(range(1,6)):
                raise ValueError('Invalid or duplicated query boundary')
        allowed_metrics={'optional_readings','information_rounds','http_requests'}
        preference=interface['preference']
        if (not isinstance(preference,list) or not preference
                or any(not isinstance(metric,str) for metric in preference)
                or len(set(preference))!=len(preference) or not set(preference)<=allowed_metrics):
            raise ValueError('Explicit supported protocol preference required')
        if interface['point_transport'] not in ['unspecified','one_http_request_per_scalar','native_multipoint_request']:
            raise ValueError('Unsupported transport description')
        if interface['scalar_reading_unit']!='one_new_internal_prefix_value':
            raise ValueError('Reading budget must count scalar observations, not HTTP transactions')
        if interface['round_unit']!='one_group_of_queries_chosen_before_its_answers':
            raise ValueError('Information rounds must be distinguished from transport transactions')

    def provenance(self,path,case_id,kind):
        relative='external_validation/stored_error_fallback/'+path
        return {'path':relative,'sha256':self.lock['inputs'][relative],
                'case_id':case_id,'guarantee_kind':kind}

    def select(self,case_id,interface):
        self.validate(interface)
        if case_id not in self.fixed:raise KeyError('Unsupported case: '+case_id)
        fixed=self.fixed[case_id];branch=self.branch.get(case_id)
        base={'id':case_id,'system_id':fixed['system_id'],'scenario':interface['id'],
              'interface_manifest':deepcopy(interface),
              'measurement_model':deepcopy(interface['measurement_model']),
              'preference':list(interface['preference']),
              'budget_units':{'optional_readings':interface['scalar_reading_unit'],
                              'information_rounds':interface['round_unit'],
                              'http_requests':'transport transactions; unknown if not documented'},
              'maximum_optional_readings':interface['maximum_optional_readings'],
              'maximum_information_rounds':interface['maximum_information_rounds'],
              'point_transport':interface['point_transport'],
              'scenario_kind':interface['scenario_kind'],
              'uses_withheld_answers_for_selection':False}
        transport=interface['point_transport']
        fixed_http=None if transport=='unspecified' else 1 if transport=='native_multipoint_request' else len(fixed['query_boundaries'])
        adaptive_http=None if transport=='unspecified' else 2
        candidates=[
            {'protocol':'bulk_range','query_boundaries':list(interface['bulk_returns_boundaries']),
             'optional_readings':len(interface['bulk_returns_boundaries']),
             'information_rounds':1,'http_requests':1,
             'certified_upper_exact':fixed['certified_upper_exact'],
             'certificate':self.provenance('fixed_batch_certificates.json',case_id,'superset inclusion of certified fixed batch'),
             'included_certificate_boundaries':fixed['query_boundaries'],
             'exclusion_reasons':[]},
            {'protocol':'fixed_batch','query_boundaries':fixed['query_boundaries'],
             'optional_readings':len(fixed['query_boundaries']),
             'information_rounds':1,'http_requests':fixed_http,
             'certified_upper_exact':fixed['certified_upper_exact'],
             'certificate':self.provenance('fixed_batch_certificates.json',case_id,'exact fixed-batch dual upper bound'),
             'exclusion_reasons':[]},
            {'protocol':'adaptive','query_boundaries':None,
             'first_query':branch['first_query'] if branch else None,
             'successor_boundaries':[r['second_query'] for r in branch['lines']] if branch else [],
             'optional_readings':2,'information_rounds':2,'http_requests':adaptive_http,
             'certified_upper_exact':branch['certified_worst_branch_bound_exact'] if branch else None,
             'certificate':self.provenance('branch_certificates.json',case_id,'exact full-domain affine branching upper bound') if branch else None,
             'exclusion_reasons':[]}]
        def exclude(c,code,reason):c['exclusion_reasons'].append({'code':code,'reason':reason})
        for c in candidates:
            protocol=c['protocol']
            if protocol=='bulk_range':
                if not interface['bulk_allowed']:
                    exclude(c,'BULK_NOT_ADMISSIBLE',interface['exclusion_of_bulk_reason'])
                if not set(fixed['query_boundaries'])<=set(c['query_boundaries']):
                    exclude(c,'CERTIFICATE_SUBSET_NOT_RETURNED','Range response does not include this certified batch')
                required=set(c['query_boundaries'])
            elif protocol=='fixed_batch':
                if not interface['fixed_batch_allowed']:
                    exclude(c,'FIXED_BATCH_NOT_ADMISSIBLE','Interface disallows preselected grouped observations')
                required=set(c['query_boundaries'])
            else:
                if not interface['adaptive_allowed']:
                    exclude(c,'ADAPTATION_NOT_ADMISSIBLE','Interface does not allow answer-dependent selection')
                if branch is None:
                    exclude(c,'NO_TWO_QUERY_GUARANTEE','Existing exact lower witnesses exclude a deterministic two-query guarantee in this case')
                required={branch['first_query'],*[r['second_query'] for r in branch['lines']]} if branch else set()
            if not required<=set(interface['permitted_boundaries']):
                exclude(c,'QUERY_NOT_PERMITTED','Certified protocol requires a boundary outside the allowed dictionary')
            for cap,metric in [('maximum_optional_readings','optional_readings'),('maximum_information_rounds','information_rounds')]:
                if interface[cap] is not None and c[metric]>interface[cap]:
                    exclude(c,'EXCEEDS_'+metric.upper(),'Requires '+str(c[metric])+', declared maximum '+str(interface[cap]))
            if any(c[metric] is None for metric in interface['preference']):
                exclude(c,'MISSING_COST_METADATA','Requested preference cannot be evaluated from documented transport metadata')
            if c['certified_upper_exact'] is not None:
                if F(c['certified_upper_exact'])>F(1,2):
                    raise ValueError('Certificate exceeds requested threshold')
            c['admissible']=not c['exclusion_reasons']
        eligible=[c for c in candidates if c['admissible']]
        selected=min(eligible,key=lambda c:tuple(c[k] for k in interface['preference'])+(c['protocol'],)) if eligible else None
        return dict(base,status='CERTIFIED' if selected else 'ESCALATION_REQUIRED',
                    selected=deepcopy(selected),candidates=candidates,
                    scope='Choice among existing certified protocols; no empirical cost prediction or new optimizer')

    def execute(self,selection,*,read_point,read_batch):
        """Dispatch logical acquisition callbacks, with no network implementation.

        read_point(k) returns one normalized stored prefix; read_batch(indices,
        mode=...) returns a mapping. A fixed batch callback may internally use
        several HTTP transactions. Callback count is NOT measured HTTP count.
        """
        current=self.select(selection['id'],selection['interface_manifest'])
        if canonical_plan(selection)!=canonical_plan(current):
            raise ValueError('Selection differs from the validated interface and certificate plan')
        if selection['status']!='CERTIFIED':raise ValueError('Escalation required; no acquisition executed')
        choice=selection['selected'];case_id=selection['id']
        if choice['protocol']=='adaptive':
            # Use the already verified in-memory certificate rather than the
            # legacy helper's file-reopening path. No online LP is needed.
            cert=self.branch[case_id];answers={};sequence=[]
            def ask(k):
                if k in answers:raise ValueError('Duplicate adaptive query')
                answers[k]=self.policy.as_fraction(read_point(k));sequence.append(k)
                if not self.policy.transcript_is_feasible(answers):
                    raise ValueError('Observed transcript is outside the declared fixed-error model')
                return answers[k]
            t=ask(cert['first_query'])
            upper,second=min((F(line['intercept_exact'])+t*F(line['slope_exact']),line['second_query'])
                             for line in cert['lines'])
            if upper>F(1,2):raise ValueError('Conditional certificate does not reach precision')
            ask(second)
            return {'id':case_id,'policy_type':'existing_two_query_adaptive_support',
                    'query_boundaries':sequence,
                    'normalized_stored_answers_exact':{str(k):str(v) for k,v in answers.items()},
                    'hard_query_budget':2,'guaranteed_width_over_original_W0_upper_exact':str(upper),
                    'threshold_over_original_W0_exact':'1/2','transcript_feasible':True}
        boundaries=tuple(choice['query_boundaries'])
        received=read_batch(boundaries,mode=choice['protocol'])
        if not isinstance(received,dict) or any(type(k) is not int for k in received):
            raise ValueError('Batch callback must return a mapping with integer boundary identifiers')
        if set(received)!=set(boundaries):raise ValueError('Callback must return exactly the requested internal boundaries')
        values={k:self.policy.as_fraction(received[k]) for k in boundaries}
        if not self.policy.transcript_is_feasible(values):
            raise ValueError('Observed transcript is outside the declared fixed-error model')
        return {'id':case_id,'policy_type':choice['protocol'],'query_boundaries':list(boundaries),
                'normalized_stored_answers_exact':{str(k):str(v) for k,v in values.items()},
                'hard_query_budget':choice['optional_readings'],
                'guaranteed_width_over_original_W0_upper_exact':choice['certified_upper_exact'],
                'threshold_over_original_W0_exact':'1/2','transcript_feasible':True}


def measured_summary():
    folder=BASE/'external_validation/operational/http_benchmark_20261012'
    trials=json.loads((folder/'trials.json').read_text())
    records=json.loads((folder/'request_log.json').read_text())['records']
    by_policy={}
    for policy in sorted({t['policy'] for t in trials}):
        rows=[t for t in trials if t['policy']==policy]
        by_policy[policy]={'trials':len(rows),**{key:statistics.mean(float(r[key]) for r in rows)
            for key in ['requests','information_rounds','api_io_seconds','end_to_end_elapsed_seconds',
                        'body_bytes_received','relative_width','precision_success']}}
    return {'trials':len(trials),'total_requests':len(records),
            'trial_requests':sum(t['requests'] for t in trials),
            'initial_endpoint_setup_requests':sum(r['role']=='initial endpoint' for r in records),
            'cases':len({t['case'] for t in trials}),'repetitions_per_policy_case':2,
            'by_policy':by_policy,
            'scope':'Descriptive recorded microbenchmark on three fixed tasks; not timing evidence for the 29 sensitivity cases',
            'limits':['End-to-end time includes separately logged client throttle waits',
                      'Body bytes are not TLS wire bytes; full range includes two retained endpoints',
                      'Zero width is for stored API-grid targets, not a zero physical-error assertion',
                      'Selective setup endpoints are common and outside individual policy-trial timing']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=HERE/'results')
    args=parser.parse_args();start=time.perf_counter();selector=Selector()
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    ledger=[];summary={};execution_count=0;rejected=0;logical_callbacks=0
    for interface in selector.lock['scenarios']:
        rows=[]
        for case_id in sorted(selector.fixed):
            row=selector.select(case_id,interface);rows.append(row);ledger.append(row)
            called=[]
            def point(k):called.append(('point',k));return F(k,6)
            def batch(indices,*,mode):called.append((mode,list(indices)));return {k:F(k,6) for k in indices}
            if row['status']=='CERTIFIED':
                result=selector.execute(row,read_point=point,read_batch=batch)
                assert result['hard_query_budget']==row['selected']['optional_readings']
                assert F(result['guaranteed_width_over_original_W0_upper_exact'])<=F(1,2)
                assert len(called)==row['selected']['information_rounds']
                execution_count+=1;logical_callbacks+=len(called)
            else:
                try:selector.execute(row,read_point=point,read_batch=batch)
                except ValueError:rejected+=1
                else:raise AssertionError('Unavailable guarantee executed')
                assert not called
        chosen=[r['selected'] for r in rows if r['selected']]
        summary[interface['id']]={'cases':len(rows),'certified':len(chosen),'escalation_required':len(rows)-len(chosen),
             'protocol_counts':dict(Counter(c['protocol'] for c in chosen)),
             'reserved_scalar_readings':sum(c['optional_readings'] for c in chosen),
             'information_rounds_total':sum(c['information_rounds'] for c in chosen),
             'planned_http_requests_total':sum(c['http_requests'] for c in chosen) if all(c['http_requests'] is not None for c in chosen) else None}
    # A declared hypothetical service demonstrates why requests and readings
    # are distinct objectives. This is not an HPM capability assertion.
    case_id=sorted(selector.branch)[0]
    extra=selector.scenario('restricted_three_readings')
    extra.update(id='logical_native_multipoint',point_transport='native_multipoint_request',
                 preference=['http_requests','information_rounds','optional_readings'])
    request_choice=selector.select(case_id,extra)['selected'];assert request_choice['protocol']=='fixed_batch'
    extra['preference']=['optional_readings','information_rounds']
    reading_choice=selector.select(case_id,extra)['selected'];assert reading_choice['protocol']=='adaptive'
    invalid_rejected=0
    for changed in ['model','budget','unit']:
        invalid=selector.scenario('public_bulk')
        if changed=='model':invalid['measurement_model']['error_bound_exact']='1/50'
        if changed=='budget':invalid['maximum_optional_readings']=-1
        if changed=='unit':invalid['scalar_reading_unit']='one_http_request'
        try:selector.select(case_id,invalid)
        except ValueError:invalid_rejected+=1
        else:raise AssertionError('Unsupported assumptions were accepted')
    modified=deepcopy(ledger[0]);modified['selected']['optional_readings']=0
    try:selector.execute(modified,read_point=lambda k:None,read_batch=lambda *args,**kwargs:None)
    except ValueError:modified_plan_rejected=True
    else:raise AssertionError('Modified selection executed without revalidation')
    measured=measured_summary()
    assert (measured['trials'],measured['total_requests'],measured['trial_requests'],measured['initial_endpoint_setup_requests'])==(30,60,54,6)
    report={'status':'PASS','scenario_cases':len(ledger),'scenarios':summary,
            'constructed_callback_executions':execution_count,'blocked_dispatches':rejected,
            'logical_acquisition_callbacks':logical_callbacks,'unsupported_input_rejections':invalid_rejected,
            'modified_plan_rejected_before_acquisition':modified_plan_rejected,
            'logical_request_vs_reading_check':{'case':case_id,'hypothetical_native_multipoint':True,
               'fewest_requests_selects':request_choice['protocol'],'fewest_readings_selects':reading_choice['protocol']},
            'new_network_calls':0,'new_model_fits':0,'new_empirical_performance_claim':False,
            'protocol_lock_sha256':digest(HERE/'protocol_lock.json'),'selector_sha256':digest(Path(__file__)),
            'seconds':time.perf_counter()-start}
    for filename,data in [('case_ledger.json',ledger),('report.json',report),('recorded_http_summary.json',measured)]:
        (out/filename).write_text(json.dumps(data,indent=2)+'\n')
    flat=[]
    for row in ledger:
        c=row['selected'] or {}
        flat.append({'case':row['id'],'system':row['system_id'],'scenario':row['scenario'],'status':row['status'],
                     'protocol':c.get('protocol'),'scalar_readings':c.get('optional_readings'),
                     'information_rounds':c.get('information_rounds'),'planned_http_requests':c.get('http_requests'),
                     'upper_over_initial_width_exact':c.get('certified_upper_exact'),
                     'certificate_path':c.get('certificate',{}).get('path'),
                     'certificate_sha256':c.get('certificate',{}).get('sha256'),
                     'candidate_exclusions':json.dumps({x['protocol']:[r['code'] for r in x['exclusion_reasons']] for x in row['candidates']},sort_keys=True)})
    with (out/'case_ledger.csv').open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
