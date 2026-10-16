"""Network-free independent accounting and saved-response replay.

Does not import analyze.py or issue requests. Does not read private answers.
"""
from collections import defaultdict
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path
import argparse, hashlib, itertools, json

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=HERE/'results')
    args=parser.parse_args(); out=args.results
    data=load(HERE/'inputs/public_decision_inputs_coherent.json')['cases']
    cases={c['id']:c for c in data};gates=load(out/'case_gate.json')
    plans=load(out/'request_plans.json');frontiers=load(out/'range_frontiers.json')
    report=load(out/'report.json');accounted=0
    assert report['input_sha256']==sha(HERE/'inputs/public_decision_inputs_coherent.json')
    assert report['source_sha256']==sha(HERE/'analyze.py')
    assert len(gates)==len(cases)==1098 and len({g['id'] for g in gates})==1098
    gate_vertex_checks=0
    for g in gates:
        c=cases[g['id']];E=F(c['E']);eps=F(c['training_M2'])/100
        assert eps==F(c['epsilon'])==F(g['epsilon'])
        models=sorted(c['forecast_vectors'])
        # Compute squared losses directly, rather than use the affine max
        # formula in analyze.py. Their difference is affine, so its maximum
        # on the nonnegative exact-total simplex occurs at one of these vertices.
        losses={m:[sum((F(a)-(E if h==v else 0))**2 for h,a in enumerate(c['forecast_vectors'][m]))/6
                   for v in range(6)] for m in models}
        upper={}
        for a,b in itertools.combinations(models,2):
            differences=[x-y for x,y in zip(losses[a],losses[b])]
            upper[a,b]=max(differences);upper[b,a]=-min(differences);gate_vertex_checks+=6
        bounds={m:max([F(0)]+[upper[m,j] for j in models if j!=m]) for m in models}
        qualified=[m for m in models if bounds[m]<=eps]
        assert qualified==g['qualified'] and bool(qualified)==(not g['fetch'])
        assert (qualified[0] if qualified else None)==g['selected_model']
        assert bounds=={m:F(v) for m,v in g['upper_regrets'].items()}
    for cohort,policies in plans.items():
        gg=sorted([g for g in gates if g['cohort']==cohort],key=lambda r:(r['utc_hour'],r['meter']))
        for policy,p in policies.items():
            req=defaultdict(list)
            for r in p['request_plan']:req[r['case']].append(r)
            cache=set();returned=0;endpointrows=0
            for g in gg:
                meter,t=g['meter'],g['utc_hour'];ends={(meter,t),(meter,t+6)}
                allcoords={(meter,t+h) for h in range(7)}
                if policy.endswith('warm'):cache|=ends
                for r in req[g['id']]:
                    coords={(meter,h) for h in range(r['start_hour'],r['end_hour']+1,r['interval_hours'])}
                    assert len(coords)==r['rows'] and coords<=allcoords
                    if r['role']=='coarse':assert coords<=ends
                    assert coords-cache, 'A request with no new coordinate is wasteful'
                    returned+=len(coords);endpointrows+=len(coords&ends);cache|=coords
                assert ends<=cache
                if policy.startswith('always') or g['fetch']:assert allcoords<=cache
                accounted+=1
            assert len(p['request_plan'])==p['requests'] and returned==p['returned_rows']
            assert endpointrows==p['endpoint_rows_returned']
            assert p['repeat_audit_additional_requests']==0
            assert all(not g['fetch'] or {(g['meter'],g['utc_hour']+h) for h in range(7)}<=cache for g in gg)
    # Exhaustive independent partition oracle for samples of every system/list.
    partition_checks=0;frontier_checks=0
    for cohort,policies in frontiers.items():
        for policy,f in policies.items():
            needed=f['required'];base=sum(ts[-1]-ts[0]+1 for ts in needed.values())
            savings=sorted((b-a-1 for ts in needed.values() for a,b in zip(ts,ts[1:]) if b-a>1),reverse=True)
            assert f['required_rows']==sum(map(len,needed.values()))
            assert f['frontier']==[dict(requests=len(needed)+k,returned_rows=base-sum(savings[:k])) for k in range(len(savings)+1)]
            for requested,rr in f['example_plans'].items():
                assert len(rr)==int(requested)
                covered=defaultdict(set)
                for r in rr:
                    assert r['rows']==r['end_hour']-r['start_hour']+1
                    covered[r['meter']].update(range(r['start_hour'],r['end_hour']+1))
                assert all(set(ts)<=covered[m] for m,ts in needed.items())
                frontier_checks+=1
            for meter,ts in needed.items():
                for offset in [0,len(ts)//2,max(0,len(ts)-8)]:
                    small=ts[offset:offset+8];best={}
                    for mask in range(1<<max(0,len(small)-1)):
                        starts=[0]+[j+1 for j in range(len(small)-1) if mask>>j&1]
                        ends=[j for j in range(len(small)-1) if mask>>j&1]+[len(small)-1]
                        rows=sum(small[b]-small[a]+1 for a,b in zip(starts,ends))
                        k=len(starts);best[k]=min(best.get(k,10**9),rows)
                    gains=sorted((b-a-1 for a,b in zip(small,small[1:])),reverse=True)
                    for k,cost in best.items():assert cost==small[-1]-small[0]+1-sum(gains[:k-1])
                    partition_checks+=len(best)
    http=HERE/'http_probe';plan=load(http/'request_plan.json');log=load(http/'http_log.json')
    assert len(plan['requests'])==len(log['records'])==12 and log['requests_attempted']==12
    assert plan['input_sha256']==report['input_sha256'] and plan['gate_sha256']==sha(out/'case_gate.json')
    bysystem=defaultdict(dict);overlap=0;rowschecked=0
    for n,(p,r) in enumerate(zip(plan['requests'],log['records']),1):
        raw=(http/f'response_{n:02d}.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['decoded_payload_sha256']
        assert r['status']==200 and r['url']==p['url'] and r['automatic_retries']==0
        values=json.loads(raw,parse_float=Decimal)['heatpump_elec_kwh']
        stamps=[int(t) for t,v in values]
        assert stamps==list(range(p['start'],p['end']+1,p['interval']))==p['expected_timestamps']
        parsed={int(t):F(str(v)) for t,v in values};assert len(parsed)==len(values)==r['returned_rows']
        for prior in bysystem[p['system']].values():
            for t in prior.keys()&parsed.keys():assert prior[t]==parsed[t];overlap+=1
        bysystem[p['system']][p['role']]=parsed;rowschecked+=len(parsed)
    decisions=0;queried=0;totalchecks=0
    for g in gates:
        if g['cohort']!='external':continue
        system=int(g['meter'].split('_')[1]);c=cases[g['id']];t=g['utc_hour']*3600
        values=bysystem[system]['whole_hourly']
        y=[values[t+(h+1)*3600]-values[t+h*3600] for h in range(6)]
        assert min(y)>=0 and sum(y)==F(c['E']);totalchecks+=1
        losses={m:sum((F(v)-target)**2 for v,target in zip(a,y))/6 for m,a in c['forecast_vectors'].items()}
        if g['fetch']:
            selected=min(losses,key=lambda m:(losses[m],m));queried+=1
        else:
            selected=g['selected_model'];decisions+=1
        assert losses[selected]-min(losses.values())<=F(c['epsilon'])
    result=dict(status='PASS',scope=__doc__,source_sha256=sha(__file__),
        analyzed_report_sha256=sha(out/'report.json'),input_sha256=report['input_sha256'],
        direct_vertex_loss_checks=gate_vertex_checks,exact_gates_checked=len(gates),
        case_policy_cache_checks=accounted,exhaustive_small_partition_budget_checks=partition_checks,
        frontier_plan_coverage_checks=frontier_checks,saved_HTTP_requests_checked=12,
        saved_HTTP_rows_checked=rowschecked,exact_overlap_checks=overlap,exact_live_total_checks=totalchecks,
        external_zero_query_decisions_validated=decisions,external_bulk_selected_decisions_validated=queried,
        network_requests_issued_by_checker=0)
    (out/'independent_check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
