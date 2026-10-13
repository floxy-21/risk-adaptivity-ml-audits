"""Check secondary decisions directly from frozen forecasts with rational MSE.

No producer imports. External default uses bundled forecasts in geometry;
--cohort all additionally needs the original frozen forecast/target exports.
The policy choices remain those already recorded in the shared-query ledger.
"""
import argparse,csv,hashlib,itertools,json
from datetime import datetime,timedelta,timezone
from fractions import Fraction as F
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
Q=list(itertools.combinations(range(1,6),2))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bounds(c,d,y,q):
    edges=(0,*q,6);lo=d;hi=d
    for a,b in zip(edges,edges[1:]):
        energy=sum(y[a:b]);lo+=energy*min(c[a:b]);hi+=energy*max(c[a:b])
    return lo,hi
def direction(lo,hi):return -1 if hi<0 else 1 if lo>0 else 0

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort',choices=['external','all'],default='external')
    ap.add_argument('--results-dir',type=Path);ap.add_argument('--decision-dir',type=Path)
    ap.add_argument('--forecasts',type=Path,default=ROOT/'outputs/review_frozen_forecasts.csv')
    ap.add_argument('--output',type=Path);a=ap.parse_args()
    results=a.results_dir or HERE/('empirical_external_results' if a.cohort=='external' else 'empirical_results')
    decisions=a.decision_dir or HERE/('decision_external_results' if a.cohort=='external' else 'decision_results')
    output=a.output or HERE/('independent_decision_external.json' if a.cohort=='external' else 'independent_decision_all.json')
    report=json.loads((results/'empirical_report.json').read_text())
    plans=json.loads((results/'empirical_plans.json').read_text())['plans']
    ledger={r['id']:r for r in csv.DictReader((results/'empirical_cases.csv').open(newline=''))}
    saved={r['id']:r for r in csv.DictReader((decisions/'cases.csv').open(newline=''))}
    cases={}
    for name,spec in report['inputs'].items():
        if name in ['original_endpoints','external_counters']:continue
        for r in json.loads((ROOT/Path(spec['path'].replace(chr(92),'/'))).read_text())['cases']:cases[r['id']]=r
    original={};external={};forecasts={}
    if a.cohort=='all':
        for r in csv.DictReader((ROOT/Path(report['inputs']['original_endpoints']['path'].replace(chr(92),'/'))).open(newline='')):
            original[r['meter'],datetime.fromisoformat(r['interval_start_utc'])]=F(int(r['end_counter_integer'])-int(r['start_counter_integer']),10**10)
        meters={p['meter'] for p in plans if p['cohort']=='original'}
        needed={(p['meter'],datetime.fromisoformat(p['day']).replace(hour=p['start_hour'],tzinfo=timezone.utc)+timedelta(hours=i)) for p in plans if p['cohort']=='original' for i in range(6)}
        for r in csv.DictReader(a.forecasts.open(newline='')):
            if r['meter'] in meters:
                t=datetime.fromisoformat(r['timestamp']).replace(tzinfo=timezone.utc)
                if (r['meter'],t) in needed:
                    forecasts[r['meter'],t]={m:F(float(r[m])) for m in ['ridge','hist_gradient_boosting','mlp']}
                    forecasts[r['meter'],t]['daily']=F(float(r['daily'])) if r['daily'] else F(float(original[r['meter'],t-timedelta(days=1)]))
        assert set(forecasts)==needed
    for r in csv.DictReader((ROOT/Path(report['inputs']['external_counters']['path'].replace(chr(92),'/'))).open(newline='')):
        if r['valid']=='1':external['hpm_'+r['system_id'],datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'))]=F(r['counter_kwh'])
    sign_checks=0;maximum_coefficient_discrepancy=0.;maximum_constant_discrepancy=0.;minimum_certified_margin=None;max_replay_difference=0.
    for p in plans:
        start=datetime.fromisoformat(p['day']).replace(hour=p['start_hour'],tzinfo=timezone.utc)
        if p['cohort']=='original':y=[original[p['meter'],start+timedelta(hours=i)] for i in range(6)]
        else:
            counter=[external[p['meter'],start+timedelta(hours=i)] for i in range(7)]
            y=[b-a for a,b in zip(counter,counter[1:])]
        contrasts=[];models=set()
        for cid in p['pair_case_ids']:
            r=cases[cid];models.update((r['model_a'],r['model_b']))
            if p['cohort']=='external':pa=list(map(F,r['forecast_a']));pb=list(map(F,r['forecast_b']))
            else:
                pa=[forecasts[p['meter'],start+timedelta(hours=i)][r['model_a']] for i in range(6)]
                pb=[forecasts[p['meter'],start+timedelta(hours=i)][r['model_b']] for i in range(6)]
            c=[(b-a)/3 for a,b in zip(pa,pb)];d=sum(a*a-b*b for a,b in zip(pa,pb))/6
            truth=sum((a-z)**2-(b-z)**2 for a,b,z in zip(pa,pb,y))/6
            assert truth==d+sum(a*z for a,z in zip(c,y))
            maximum_coefficient_discrepancy=max(maximum_coefficient_discrepancy,max(float(abs(cc-F(v))) for cc,v in zip(c,r['c'])))
            maximum_constant_discrepancy=max(maximum_constant_discrepancy,float(abs(d-F(r['d']))))
            contrasts.append((r,c,d,truth))
        all_decisions=[]
        for q in [*Q,(),tuple(range(1,6))]:
            wins={m:set() for m in models};known=0
            for r,c,d,truth in contrasts:
                lo,hi=bounds(c,d,y,q);oldlo,oldhi=bounds(list(map(F,r['c'])),F(r['d']),y,q)
                sign=direction(lo,hi);assert sign==direction(oldlo,oldhi),(p['id'],r['id'],q,'rounding changes certification')
                assert lo<=truth<=hi;sign_checks+=1
                if sign:
                    margin=-hi if sign<0 else lo
                    minimum_certified_margin=margin if minimum_certified_margin is None else min(minimum_certified_margin,margin)
                    assert (truth<0 if sign<0 else truth>0)
                    winner,loser=(r['model_a'],r['model_b']) if sign<0 else (r['model_b'],r['model_a'])
                    wins[winner].add(loser);known+=1
            winner_count=sum(len(v)==3 for v in wins.values());assert winner_count<=1
            all_decisions.append({'winner':winner_count,'ranking':int(known==6),'pairs':known})
        row=ledger[p['id']];g=p['geometry'];observed=saved[p['id']]
        indices={'adaptive':Q.index(tuple(sorted((int(row['adaptive_first']),int(row['adaptive_second']))))),
                 'greedy':Q.index(tuple(sorted((int(row['greedy_first']),int(row['greedy_second']))))),
                 'deterministic_batch':g['best_deterministic_batch_index'],'zero_query':10,'bulk':11}
        for name,index in indices.items():
            for k in ['winner','ranking','pairs']:assert float(observed[name+'_'+k])==all_decisions[index][k]
        for k in ['winner','ranking','pairs']:
            for name,value in [('randomized_batch',sum(w*d[k] for w,d in zip(g['randomized_batch_weights'],all_decisions))),('uniform_batch',sum(d[k] for d in all_decisions[:10])/10)]:
                difference=abs(value-float(observed[name+'_'+k]));assert difference<1e-12;max_replay_difference=max(max_replay_difference,difference)
    final={'status':'PASS','cohort':a.cohort,'blocks':len(plans),'exact_pair_sign_checks':sign_checks,
        'scope':'Each of ten batches plus zero-query and bulk rechecked using exact rational squared-loss contrasts reconstructed from frozen forecasts; original-source omitted persistence predictions use the documented prior-day raw increment. Every sign and decision in the saved ledger agrees; source-affine rounding does not change any reported certificate. This verifies these finite records, not the universal adaptivity theorem.',
        'maximum_source_coefficient_discrepancy':maximum_coefficient_discrepancy,'maximum_source_constant_discrepancy':maximum_constant_discrepancy,
        'minimum_strict_certificate_margin':float(minimum_certified_margin),'maximum_recorded_mixture_difference':max_replay_difference,
        'source_sha256':sha(Path(__file__)),'decision_cases_sha256':sha(decisions/'cases.csv'),'plans_sha256':sha(results/'empirical_plans.json')}
    output.parent.mkdir(exist_ok=True,parents=True);output.write_text(json.dumps(final,indent=2)+'\n');print(json.dumps(final,indent=2))

if __name__=='__main__':main()
