"""Exact decision gate and honest request/row accounting; no hidden targets.

The contract is epsilon-optimal MODEL CHOICE, not joint half-width precision.
Returned rows are coordinate values, not bytes, energy, dollars or latency.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction as F
import argparse, csv, hashlib, json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'inputs/public_decision_inputs_coherent.json'
PIN = '4dab6420e1a365feb9bd08d21ebb936f347c21b445848a49b898086dd8029230'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True)+'\n', encoding='utf-8')

def hour(c):
    return int(datetime.strptime(c['day'], '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())//3600 + c['start_hour']

def decide(c):
    """Exact all-completion candidate bound, independently checked by vertices."""
    e, eps = F(c['E']), F(c['epsilon'])
    assert e >= 0 and eps == F(c['training_M2'])/100
    vectors = {m:list(map(F, a)) for m,a in c['forecast_vectors'].items()}
    models = sorted(vectors)
    assert len(models) == 4 and all(len(a)==6 for a in vectors.values())
    uppers = {}
    checks = 0
    for p in c['pairs']:
        a,b = p['model_a'], p['model_b']
        coeff = [2*(bv-av)/6 for av,bv in zip(vectors[a],vectors[b])]
        constant = sum(av*av-bv*bv for av,bv in zip(vectors[a],vectors[b]))/6
        assert coeff == list(map(F,p['c'])) and constant == F(p['d'])
        values=[]
        for h in range(6):
            target = [e if j==h else F(0) for j in range(6)]
            actual = (sum((v-y)**2 for v,y in zip(vectors[a],target))-
                      sum((v-y)**2 for v,y in zip(vectors[b],target)))/6
            assert actual == constant + coeff[h]*e
            values.append(actual); checks += 1
        uppers[a,b] = constant + e*max(coeff)
        uppers[b,a] = -constant - e*min(coeff)
        assert uppers[a,b] == max(values) and uppers[b,a] == -min(values)
    bounds = {m:max([F(0)] + [uppers[m,j] for j in models if j!=m]) for m in models}
    qualified = [m for m in models if bounds[m] <= eps]
    return dict(id=c['id'], cohort=c['cohort'], meter=c['meter'], day=c['day'],
        start_hour=c['start_hour'], utc_hour=hour(c), epsilon=str(eps),
        qualified=qualified, selected_model=qualified[0] if qualified else None,
        upper_regrets={m:str(v) for m,v in bounds.items()}, fetch=not bool(qualified),
        independent_vertex_checks=checks)

def archive_decide(c, later):
    """Conservative binary64-rounding envelopes, never exact copy assumptions.

    Pinned original daily forecasts are constructed by int-difference/10**10;
    external daily forecasts copy float(Decimal difference) with round-trip CSV
    parsing. One neighboring binary64 spacing on either side is conservative.
    These are benchmark forecast records, not observed production log arrivals.
    """
    if later is None:
        return dict(qualified=[],source_case=None,copied_targets=0)
    z=list(map(F,later['forecast_vectors']['daily']));lo=[];hi=[]
    for v in z:
        f=float(v);assert F.from_float(f)==v and math.isfinite(f) and f>=0
        lower=F.from_float(math.nextafter(f,-math.inf));upper=F.from_float(math.nextafter(f,math.inf))
        lo.append(max(F(0),lower));hi.append(upper)
    assert sum(lo)<=F(c['E'])<=sum(hi), 'Archive rounding box excludes retained total'
    directed={}
    for p in c['pairs']:
        cc=list(map(F,p['c']));d=F(p['d']);a,b=p['model_a'],p['model_b']
        directed[a,b]=d+sum(v*(h if v>=0 else l) for v,l,h in zip(cc,lo,hi))
        directed[b,a]=-d+sum(-v*(h if v<=0 else l) for v,l,h in zip(cc,lo,hi))
    models=sorted(c['forecast_vectors'])
    bounds={m:max([F(0)]+[directed[m,j] for j in models if j!=m]) for m in models}
    qualified=[m for m in models if bounds[m]<=F(c['epsilon'])]
    return dict(source_case=later['id'],copied_targets=6,qualified=qualified,
        rounding_lower=list(map(str,lo)),rounding_upper=list(map(str,hi)),
        selected_model=qualified[0] if qualified else None,
        upper_regrets={m:str(v) for m,v in bounds.items()},
        copied_total_discrepancy=str(sum(z)-F(c['E'])),
        information_rule='Later benchmark persistence vector; original daily vectors generated from permitted prior-day input, external vectors saved with round-trip parsing.')

def frontier(required):
    """Exact all-frontier for hourly inclusive ranges with fixed request count.

    Join all needed timestamps per meter. Cutting a gap of d hours saves d-1
    rows for one extra request. Sort positive gaps. Different gaps contribute
    independently, so selecting the largest savings is exact.
    """
    required = {m:sorted(set(ts)) for m,ts in required.items() if ts}
    base = sum(ts[-1]-ts[0]+1 for ts in required.values())
    gaps = sorted([(b-a-1,m,a,b) for m,ts in required.items() for a,b in zip(ts,ts[1:]) if b-a>1],
                  key=lambda x:(-x[0],x[1],x[2]))
    points=[dict(requests=len(required), returned_rows=base)]
    for i,(saving,_,_,_) in enumerate(gaps,1):
        base -= saving
        points.append(dict(requests=len(required)+i, returned_rows=base))
    return dict(required_rows=sum(map(len,required.values())), frontier=points,
                cuts=[dict(saved_rows=s,meter=m,left=a,right=b) for s,m,a,b in gaps],
                required={m:ts for m,ts in required.items()})

def ranges_at(f, requests):
    req=f['required']; k=max(0,min(requests-len(req),len(f['cuts'])))
    cuts={(r['meter'],r['left'],r['right']) for r in f['cuts'][:k]}
    ranges=[]
    for meter,ts in sorted(req.items()):
        first=ts[0]
        for a,b in zip(ts,ts[1:]):
            if (meter,a,b) in cuts:
                ranges.append(dict(meter=meter,start_hour=first,end_hour=a,rows=a-first+1)); first=b
        ranges.append(dict(meter=meter,start_hour=first,end_hour=ts[-1],rows=ts[-1]-first+1))
    assert len(ranges)==len(req)+k
    assert sum(r['rows'] for r in ranges)==f['frontier'][k]['returned_rows']
    returned=defaultdict(set)
    for r in ranges: returned[r['meter']].update(range(r['start_hour'],r['end_hour']+1))
    assert all(set(ts)<=returned[m] for m,ts in req.items())
    return ranges

def immediate(rows, gated, cold):
    cache=set(); requests=[]; decisions=[]
    endpoint_rows=internal_rows=hits=0
    for r in sorted(rows,key=lambda r:(r['utc_hour'],r['meter'])):
        m,t=r['meter'],r['utc_hour']; endpoints={(m,t),(m,t+6)}
        internal={(m,t+h) for h in range(1,6)}
        if not cold:
            cache.update(endpoints)
        if cold and gated:
            missing=endpoints-cache
            if missing:
                got=sorted(h for mm,h in missing)
                requests.append(dict(case=r['id'],role='coarse',meter=m,start_hour=got[0],end_hour=got[-1],interval_hours=6,rows=len(got)))
                cache.update(missing); endpoint_rows+=len(got)
        if gated and not r['fetch']:
            assert endpoints<=cache
            decisions.append(dict(id=r['id'],action='certificate',selected_model=r['selected_model']))
            continue
        need=internal if not cold or gated else internal|endpoints
        hits+=len(need & cache)
        missing=need-cache
        if missing:
            hs=sorted(h for mm,h in missing)
            got={(m,h) for h in range(hs[0],hs[-1]+1)}
            requests.append(dict(case=r['id'],role='fine',meter=m,start_hour=hs[0],end_hour=hs[-1],interval_hours=1,rows=len(got)))
            endpoint_rows+=len(got&endpoints);internal_rows+=len(got-endpoints)
            cache.update(got)
        assert internal|endpoints<=cache
        decisions.append(dict(id=r['id'],action='retrieve',models_sharing_fetch=4,pairs_sharing_fetch=6))
    # A second identical audit uses either its saved certificate or cached full trace.
    for r in rows:
        m,t=r['meter'],r['utc_hour']
        assert {(m,t),(m,t+6)}<=cache
        if not gated or r['fetch']: assert {(m,t+h) for h in range(1,6)}<=cache
    return dict(blocks=len(rows),requests=len(requests),returned_rows=sum(r['rows'] for r in requests),
        endpoint_rows_returned=endpoint_rows,other_rows_returned=internal_rows,
        cached_hits_during_first_pass=hits,repeat_audit_additional_requests=0,
        policy=('gated' if gated else 'always_bulk')+('_cold' if cold else '_warm'),
        request_plan=requests,case_actions=decisions)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=HERE/'results')
    args=parser.parse_args(); out=args.out;out.mkdir(parents=True,exist_ok=True)
    assert digest(SOURCE)==PIN, 'Input version mismatch'
    source=json.loads(SOURCE.read_text(encoding='utf-8'))
    rows=[decide(c) for c in source['cases']]
    assert len(rows)==1098 and len({r['id'] for r in rows})==1098
    summaries={}; plans={}; all_frontiers={}; archive=[]
    index={(c['cohort'],c['meter'],hour(c)):c for c in source['cases']}
    for r in rows:
        c=index[r['cohort'],r['meter'],r['utc_hour']]
        later=index.get((r['cohort'],r['meter'],r['utc_hour']+24))
        copied = archive_decide(c,later)
        archive.append(dict(id=r['id'],cohort=r['cohort'],meter=r['meter'],
            **copied,retrieval_needed=bool(r['fetch'] and not copied['qualified'])))
    for cohort in ['original','external']:
        rr=[r for r in rows if r['cohort']==cohort]; meters=sorted({r['meter'] for r in rr})
        nzero=sum(not r['fetch'] for r in rr)
        assert nzero=={'original':8,'external':198}[cohort]
        warm=immediate(rr,False,False); gated=immediate(rr,True,False)
        cold=immediate(rr,False,True); coldgate=immediate(rr,True,True)
        plans[cohort]={p['policy']:p for p in [warm,gated,cold,coldgate]}
        required_all=defaultdict(list);required_gate=defaultdict(list);required_archive=defaultdict(list)
        archiveids={r['id'] for r in archive if r['retrieval_needed']}
        endpoints=defaultdict(set)
        for r in rr:
            m,t=r['meter'],r['utc_hour']; endpoints[m].update([t,t+6])
            required_all[m].extend(range(t+1,t+6))
            if r['fetch']: required_gate[m].extend(range(t+1,t+6))
            if r['id'] in archiveids: required_archive[m].extend(range(t+1,t+6))
        ff={name:frontier(req) for name,req in [('all_fine',required_all),('gated_fine',required_gate),('archive_first_fine',required_archive)]}
        for name,f in ff.items():
            choices=sorted({len(f['required']),len(f['frontier'])+len(f['required'])-1,3,6,9,12,30,81,100,279,819})
            f['example_plans']={str(k):ranges_at(f,k) for k in choices if len(f['required'])<=k<=len(f['frontier'])+len(f['required'])-1}
        all_frontiers[cohort]=ff
        whole_rows=sum(max(ts)-min(ts)+1 for ts in endpoints.values())
        coarse_rows=sum((max(ts)-min(ts))//6+1 for ts in endpoints.values())
        assert coarse_rows==sum(map(len,endpoints.values()))
        archive_rr=[a for a in archive if a['cohort']==cohort]
        summaries[cohort]=dict(blocks=len(rr),system_count=len(meters),zero_query_certificates=nzero,
            required_fine_fetch_blocks=len(rr)-nzero,
            immediate={p['policy']:{k:v for k,v in p.items() if k not in ['request_plan','case_actions']} for p in [warm,gated,cold,coldgate]},
            systems={m:dict(blocks=sum(r['meter']==m for r in rr),zero_query_certificates=sum(r['meter']==m and not r['fetch'] for r in rr)) for m in meters},
            retrospective=dict(cold_whole_period_bulk=dict(requests=len(meters),returned_rows=whole_rows),
                cold_coarse_inputs=dict(requests=len(meters),returned_rows=coarse_rows),
                warm_gated_minimum_requests=ff['gated_fine']['frontier'][0],
                warm_gated_minimum_rows=ff['gated_fine']['frontier'][-1],
                warm_ungated_minimum_requests=ff['all_fine']['frontier'][0],
                saved_next_day_target_copy_blocks=sum(a['source_case'] is not None for a in archive_rr),
                archive_rounding_box_certified_blocks=sum(bool(a['qualified']) for a in archive_rr),
                archive_after_gate_remaining_blocks=sum(a['retrieval_needed'] for a in archive_rr),
                archive_first_fine_frontier=ff['archive_first_fine']['frontier']),
            interpretation='Counts are conditional access accounting for epsilon-model choice; no measured price, deployment delay or joint-precision saving.')
    report=dict(status='PASS',scope=__doc__,input_sha256=digest(SOURCE),source_sha256=digest(__file__),
        reconstruction_source_sha256=digest(HERE/'source_reference/reconstruct_coherent_inputs.py'),
        archive_original_parser_sha256=digest(HERE/'source_reference/study.py'),
        archive_external_training_sha256=digest(HERE/'source_reference/train_external.py'),
        protocol_sha256=digest(HERE/'PROTOCOL.txt'),blocks=len(rows),exact_vertex_mse_checks=sum(r['independent_vertex_checks'] for r in rows),
        models_per_shared_audit=4,pairs_per_shared_audit=6,epsilon_training_m2_factor='1/100',cohorts=summaries,
        limits=['The endpoint-rich immediate schedule is a specified access replay, not a deployed service.',
                'The cold and retrospective frontiers retain stronger bulk and free-archive alternatives.',
                'A zero-query certificate gives epsilon-optimality, not exact best-model identity.',
                'This is a separate decision objective from joint half-width certification.'])
    write(out/'case_gate.json',rows);write(out/'request_plans.json',plans)
    write(out/'range_frontiers.json',all_frontiers);write(out/'archive_copy_trace.json',archive)
    write(out/'report.json',report)
    routing=dict(scope='Request-oriented guard for the evaluated interfaces, not a globally optimal acquisition theorem.',
        retained_endpoints=dict(action='exact epsilon gate then bulk for unresolved blocks',cohorts={k:v['immediate']['gated_warm'] for k,v in summaries.items()}),
        cold_immediate_request_objective=dict(action='bulk directly; do not spend a separate request learning the endpoints first',cohorts={k:v['immediate']['always_bulk_cold'] for k,v in summaries.items()}),
        retrospective=dict(action='use all permitted later forecast records with rounding envelopes, then coalesce unresolved fine ranges',cohorts={k:v['retrospective']['archive_first_fine_frontier'][0] for k,v in summaries.items()}),
        complete_cache=dict(action='return cached certificate or evaluate cached complete trace',additional_requests=0))
    write(out/'routing_decisions.json',routing)
    with (out/'cost_frontier.csv').open('w',newline='',encoding='utf-8') as h:
        writer=csv.DictWriter(h,fieldnames=['cohort','policy','requests','returned_rows','required_rows']);writer.writeheader()
        for cohort,fs in all_frontiers.items():
            for name,f in fs.items():
                for point in f['frontier']:writer.writerow(dict(cohort=cohort,policy=name,required_rows=f['required_rows'],**point))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
