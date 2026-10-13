"""Freeze the integration scenarios and hashes before ledger generation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
MODEL={'latent_target':'nonnegative_six_increment_affine_contrast',
       'retained_total':'exact_normalized_one',
       'query_semantics':'stored_internal_prefix_plus_fixed_hidden_error',
       'error_bound_exact':'1/100',
       'precision_over_initial_width_exact':'1/2',
       'calibration':'declared_allowance_not_physical_calibration'}


def main():
    common={'measurement_model':MODEL,'permitted_boundaries':[1,2,3,4,5],
            'bulk_returns_boundaries':[1,2,3,4,5],
            'fixed_batch_allowed':True,'adaptive_allowed':True,
            'scalar_reading_unit':'one_new_internal_prefix_value',
            'round_unit':'one_group_of_queries_chosen_before_its_answers'}
    scenarios=[]
    p=dict(common,id='public_bulk',bulk_allowed=True,maximum_optional_readings=None,
           maximum_information_rounds=None,point_transport='one_http_request_per_scalar',
           preference=['http_requests','information_rounds','optional_readings'],
           scenario_kind='documented_public_capabilities_with_declared_uncertainty_model',
           source='Existing HPM range/point API documentation and frozen public microbenchmark',
           exclusion_of_bulk_reason=None)
    scenarios.append(p)
    for sid,budget,rounds in [('restricted_three_readings',3,2),
                             ('restricted_two_readings',2,2),
                             ('restricted_one_round',3,1)]:
        scenarios.append(dict(common,id=sid,bulk_allowed=False,
            maximum_optional_readings=budget,maximum_information_rounds=rounds,
            point_transport='unspecified',
            preference=['optional_readings','information_rounds'],
            scenario_kind='declared_benchmark_interface_not_observed_provider_service',
            source='Mathematical individual-prefix query dictionary',
            exclusion_of_bulk_reason='This declared benchmark admits individually selected prefix observations only'))
    input_names=[
        'external_validation/stored_error_fallback/prescriptions.json',
        'external_validation/stored_error_fallback/fixed_batch_certificates.json',
        'external_validation/stored_error_fallback/branch_certificates.json',
        'external_validation/stored_error_fallback/policy.py',
        'external_validation/stored_error_fallback/INDEPENDENT_CERTIFICATE_CHECKS.json',
        'external_validation/stored_error_fallback/INDEPENDENT_BRANCH_CHECKS.json',
        'external_validation/stored_error_sensitivity/failure_diagnostics/witnesses.json',
        'external_validation/operational/http_benchmark_20261012/trials.json',
        'external_validation/operational/http_benchmark_20261012/request_log.json',
        'external_validation/operational/http_benchmark_20261012/benchmark_plan.json']
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    content={'schema':'acquisition-interface-selector-v1',
             'frozen_utc':datetime.now(timezone.utc).isoformat(),
             'protocol_sha256':sha(HERE/'PROTOCOL.txt'),
             'measurement_model':MODEL,'scenarios':scenarios,
             'inputs':{p:sha(BASE/p) for p in input_names},
             'logical_extra_check':'One hypothetical native multipoint interface with request priority; no provider claim',
             'execution_test':'All29cases x4scenarios, fixed uniform increments and zero errors',
             'source_data_or_models_changed':False}
    out=HERE/'protocol_lock.json'
    if out.exists(): raise RuntimeError('Protocol is already frozen; do not overwrite it')
    out.write_text(json.dumps(content,indent=2)+'\n')
    print(json.dumps({'status':'FROZEN','scenarios':4,'input_files':len(input_names),
                      'sha256':sha(out),'frozen_utc':content['frozen_utc']},indent=2))


if __name__=='__main__':main()
