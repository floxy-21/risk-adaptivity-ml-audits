"""At most twelve preselected public GETs; actual wire-body/range validation.

This validates the adapter and archive, not a deployed gated audit service.
"""
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path
import hashlib, importlib.util, json, random, sys
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
HELPER=ROOT/'work/risk_adaptivity_revision/external_validation/operational/measurement.py'
spec=importlib.util.spec_from_file_location('cost_measurement',HELPER)
measurement=importlib.util.module_from_spec(spec);sys.modules[spec.name]=measurement;spec.loader.exec_module(measurement)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def main():
    out=HERE/'http_probe';out.mkdir(exist_ok=True)
    # A new invocation may not accidentally repeat the public trial.
    assert not (out/'request_plan.json').exists(), 'Public trial already planned; replay saved responses instead.'
    src=HERE.parent/'public_decision_inputs_coherent.json'
    assert sha(src)=='4dab6420e1a365feb9bd08d21ebb936f347c21b445848a49b898086dd8029230'
    inputs=json.loads(src.read_text())['cases']
    rows=json.loads((HERE/'case_gate.json').read_text())
    fronts=json.loads((HERE/'range_frontiers.json').read_text())['external']['gated_fine']
    plan=[]
    for system in [1,2,7]:
        meter=f'hpm_{system}';rr=[r for r in rows if r['meter']==meter]
        start=min(r['utc_hour'] for r in rr)*3600;end=max(r['utc_hour']+6 for r in rr)*3600
        needs=fronts['required'][meter]
        spans=[('whole_hourly',start,end,3600),('whole_coarse',start,end,21600),
               ('gated_coalesced',min(needs)*3600,max(needs)*3600,3600),
               ('first_needed_point',min(needs)*3600,min(needs)*3600+1,3600)]
        for role,a,b,step in spans:
            plan.append(dict(system=system,meter=meter,role=role,start=a,end=b,interval=step,
                expected_timestamps=list(range(a,b+1,step)),
                url=measurement.hpm_range_url(system,'heatpump_elec_kwh',a,b,step)+'&timeformat=unix'))
    random.Random(20261016).shuffle(plan)
    metadata=dict(frozen_at=datetime.now(timezone.utc).isoformat(),input_sha256=sha(src),
        protocol_sha256=sha(HERE/'PROTOCOL.txt'),producer_sha256=sha(__file__),
        gate_sha256=sha(HERE/'case_gate.json'),measurement_sha256=sha(HELPER),
        requests=plan,maximum_requests=12,automatic_retries=0,seed=20261016)
    save(out/'request_plan.json',metadata)
    recorder=measurement.HTTPRecorder({'heatpumpmonitor.org'},maximum_requests=12,min_start_interval=1.0,timeout=40.0)
    observed={};exception=None
    try:
        for n,req in enumerate(plan,1):
            received=recorder.get(req['url'],trial_id=f"system{req['system']}-{req['role']}",policy=req['role'],role='adapter-validation',information_round=1)
            (out/f"response_{n:02d}.json").write_bytes(received.payload)
            assert received.status==200, f"HTTP {received.status}"
            raw=json.loads(received.payload.decode('utf-8'),parse_float=Decimal)['heatpump_elec_kwh']
            parsed={int(t):F(str(v)) if v is not None else None for t,v in raw}
            assert len(raw)==len(parsed) and list(parsed)==req['expected_timestamps'], 'Timestamp contract mismatch'
            assert all(v is not None for v in parsed.values()), 'Null counter value'
            for (sysid,role),values in observed.items():
                if sysid==req['system']:
                    assert all(values[t]==parsed[t] for t in values.keys()&parsed.keys()), 'Overlapping responses disagree'
            observed[req['system'],req['role']]=parsed
            received.observation['returned_rows']=len(parsed)
            print(f"{n}/12 system={req['system']} {req['role']} rows={len(parsed)} bytes={len(received.payload)}",flush=True)
    except Exception as exc:
        exception=f'{type(exc).__name__}: {exc}'
    finally:
        recorder.close()
        recorder.write(out/'http_log.json',scope=__doc__,metadata=dict(plan_sha256=sha(out/'request_plan.json'),error=exception))
    report=dict(status='FAIL' if exception else 'PASS',error=exception,requests_attempted=len(recorder.records),
        plan_sha256=sha(out/'request_plan.json'),log_sha256=sha(out/'http_log.json'),systems={},
        limits=['Twelve serial requests do not establish a population latency effect.',
                'Whole-range reads validate the counterfactual gate; they were not avoided during this validation experiment.',
                'Body bytes exclude headers and TLS traffic. Cached future forecasts can remove retrieval entirely.',
                'The source API does not enforce a two-reading restriction or a paid per-reading service.'])
    if not exception:
        cases={c['id']:c for c in inputs};gates={r['id']:r for r in rows}
        for system in [1,2,7]:
            meter=f'hpm_{system}';whole=observed[system,'whole_hourly']
            rr=[r for r in rows if r['meter']==meter]
            discrepancies=[];certified_checks=[]
            for r in rr:
                c=cases[r['id']];t=r['utc_hour']*3600
                targets=[whole[t+3600*(j+1)]-whole[t+3600*j] for j in range(6)]
                assert min(targets)>=0, 'Nonmonotone source counter'
                discrepancy=sum(targets)-F(c['E']);discrepancies.append(discrepancy)
                assert abs(discrepancy)<=F(1,10**9), 'Live endpoint total differs from frozen model'
                if not r['fetch']:
                    losses={m:sum((F(a)-y)**2 for a,y in zip(v,targets))/6 for m,v in c['forecast_vectors'].items()}
                    regret=losses[r['selected_model']]-min(losses.values())
                    assert regret<=F(c['epsilon']), 'Certified decision fails live-record replay'
                    certified_checks.append(dict(id=r['id'],model=r['selected_model'],actual_excess_mse=str(regret),epsilon=c['epsilon']))
            logs={r['policy']:r for r in recorder.records if r['trial_id'].startswith(f'system{system}-')}
            costs={role:{k:r[k] for k in ['returned_rows','response_body_bytes','api_io_seconds']} for role,r in logs.items()}
            report['systems'][meter]=dict(blocks=len(rr),gate_skips=len(certified_checks),
                max_absolute_frozen_total_discrepancy=str(max(map(abs,discrepancies))),
                overlap_checks='exact decimal-rational equality',costs=costs,
                actual_certified_decision_checks=certified_checks)
    save(out/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='systems'},indent=2))
    if exception:raise RuntimeError(exception)

if __name__=='__main__':main()
