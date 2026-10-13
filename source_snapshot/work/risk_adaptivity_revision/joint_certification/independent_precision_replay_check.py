"""Independently check precision challenger replay with exact rational arithmetic.

No producer imports. The default rechecks the bundled external cohort. The
optional all-cohort mode additionally requires the documented original exports.
Policy selection and full-domain guarantees are verified in separate checkers;
this script checks recorded outcomes, including MSE decisions from forecasts.
"""
import argparse,csv,hashlib,itertools,json,time
from datetime import datetime,timedelta,timezone
from fractions import Fraction as F
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
Q=list(itertools.combinations(range(1,6),2))
FIELDS=['adaptive_J','precision_batch_expected_J','adaptive_success','precision_batch_success_probability',
        'adaptive_winner','precision_batch_winner_probability','adaptive_ranking','precision_batch_ranking_probability']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def resolve(s):return ROOT/Path(s.replace(chr(92),'/'))
def bounds(c,d,y,q):
    lo=hi=d;edges=(0,*q,6)
    for a,b in zip(edges,edges[1:]):
        e=sum(y[a:b]);lo+=e*min(c[a:b]);hi+=e*max(c[a:b])
    return lo,hi
def sign(lo,hi):return -1 if hi<0 else 1 if lo>0 else 0

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort',choices=['external','all'],default='external')
    ap.add_argument('--replay-dir',type=Path);ap.add_argument('--output',type=Path)
    ap.add_argument('--forecasts',type=Path,default=ROOT/'outputs/review_frozen_forecasts.csv')
    a=ap.parse_args();start_clock=time.perf_counter()
    directory=a.replay_dir or HERE/('empirical_precision_results' if a.cohort=='external' else 'empirical_precision_all_results')
    output=a.output or HERE/('independent_precision_replay_external.json' if a.cohort=='external' else 'independent_precision_replay_all.json')
    report=json.loads((directory/'report.json').read_text());assert report['cohort']==a.cohort
    paths={key:resolve(spec['path']) for key,spec in report['inputs'].items()}
    for key,path in paths.items():assert sha(path)==report['inputs'][key]['sha256']
    policy_doc=json.loads(paths['precision_plans'].read_text());assert policy_doc['fine_answers_loaded'] is False
    policy={p['id']:p for p in policy_doc['plans']}
    plans=json.loads(paths['shared_plans'].read_text())['plans']
    ledger={r['id']:r for r in csv.DictReader(paths['ledger'].open(newline=''))}
    saved={r['id']:r for r in json.loads((directory/'cases.json').read_text())}
    assert set(policy)==set(ledger)==set(saved)=={p['id'] for p in plans}
    assert len(plans)==(279 if a.cohort=='external' else 1098)
    cases={};original={};external={}
    for rel,h in report['data_source_hashes'].items():
        path=resolve(rel);assert sha(path)==h
        if path.name=='geometry.json':
            for r in json.loads(path.read_text())['cases']:cases[r['id']]=r
        elif path.name=='data_blem_hourly_endpoints.csv':
            assert a.cohort=='all'
            for r in csv.DictReader(path.open(newline='')):
                original[r['meter'],datetime.fromisoformat(r['interval_start_utc'])]=F(int(r['end_counter_integer'])-int(r['start_counter_integer']),10**10)
        elif path.name=='train_test_hourly_counters.csv':
            for r in csv.DictReader(path.open(newline='')):
                if r['valid']=='1':external['hpm_'+r['system_id'],datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'))]=F(r['counter_kwh'])
        else:raise AssertionError(('unknown source',rel))
    forecasts={}
    if a.cohort=='all':
        needed={(p['meter'],datetime.fromisoformat(p['day']).replace(hour=p['start_hour'],tzinfo=timezone.utc)+timedelta(hours=i)) for p in plans if p['cohort']=='original' for i in range(6)}
        for r in csv.DictReader(a.forecasts.open(newline='')):
            t=datetime.fromisoformat(r['timestamp']).replace(tzinfo=timezone.utc);key=(r['meter'],t)
            if key in needed:
                forecasts[key]={m:F(float(r[m])) for m in ['ridge','hist_gradient_boosting','mlp']}
                forecasts[key]['daily']=F(float(r['daily'])) if r['daily'] else F(float(original[r['meter'],t-timedelta(days=1)]))
        assert set(forecasts)==needed
    reconstructed=[];checks=0;max_difference=0.;max_normalized_source_rounding=0.
    for p in plans:
        t=datetime.fromisoformat(p['day']).replace(hour=p['start_hour'],tzinfo=timezone.utc)
        if p['cohort']=='original':y=[original[p['meter'],t+timedelta(hours=i)] for i in range(6)]
        else:
            counter=[external[p['meter'],t+timedelta(hours=i)] for i in range(7)];y=[v-u for u,v in zip(counter,counter[1:])]
        assert min(y)>=0 and sum(y)>0;x=[v/sum(y) for v in y]
        frozen=policy[p['id']];pi=list(map(F,frozen['batch_weights']));assert sum(pi)==1 and min(pi)>=0
        contrasts=[];C=[];models=set()
        for cid in p['pair_case_ids']:
            r=cases[cid];models.update((r['model_a'],r['model_b']))
            raw=list(map(F,r['c']));m,M=min(raw),max(raw);assert M>m;C.append([(v-m)/(M-m) for v in raw])
            if p['cohort']=='external':pa=list(map(F,r['forecast_a']));pb=list(map(F,r['forecast_b']))
            else:
                pa=[forecasts[p['meter'],t+timedelta(hours=i)][r['model_a']] for i in range(6)]
                pb=[forecasts[p['meter'],t+timedelta(hours=i)][r['model_b']] for i in range(6)]
            c=[(b-a)/3 for a,b in zip(pa,pb)];d=sum(a*a-b*b for a,b in zip(pa,pb))/6
            truth=sum((a-z)**2-(b-z)**2 for a,b,z in zip(pa,pb,y))/6
            assert d+sum(a*z for a,z in zip(c,y))==truth
            exact_normalized=[(v-min(c))/(max(c)-min(c)) for v in c]
            max_normalized_source_rounding=max(max_normalized_source_rounding,max(float(abs(u-v)) for u,v in zip(C[-1],exact_normalized)))
            contrasts.append((r,c,d,truth))
        assert [[str(v) for v in c] for c in C]==frozen['normalized_coefficients_exact']
        widths=[];decisions=[]
        for q in Q:
            widths.append(max(bounds(c,F(0),x,q)[1]-bounds(c,F(0),x,q)[0] for c in C))
            wins={m:set() for m in models};known=0
            for r,c,d,truth in contrasts:
                lo,hi=bounds(c,d,y,q);s=sign(lo,hi);assert lo<=truth<=hi
                assert s==sign(*bounds(list(map(F,r['c'])),F(r['d']),y,q));checks+=1
                if s:
                    assert truth<0 if s<0 else truth>0
                    winner,loser=(r['model_a'],r['model_b']) if s<0 else (r['model_b'],r['model_a'])
                    wins[winner].add(loser);known+=1
            winners=sum(len(v)==3 for v in wins.values());assert winners<=1
            decisions.append((winners,int(known==6)))
        successes=[int(w<=F(1,2)) for w in widths]
        old=ledger[p['id']];aq=tuple(sorted((int(old['adaptive_first']),int(old['adaptive_second']))));ai=Q.index(aq)
        values={'adaptive_J':float(widths[ai]),'precision_batch_expected_J':float(sum(w*v for w,v in zip(pi,widths))),
                'adaptive_success':successes[ai],'precision_batch_success_probability':float(sum(w*v for w,v in zip(pi,successes))),
                'adaptive_winner':decisions[ai][0],'precision_batch_winner_probability':float(sum(w*v[0] for w,v in zip(pi,decisions))),
                'adaptive_ranking':decisions[ai][1],'precision_batch_ranking_probability':float(sum(w*v[1] for w,v in zip(pi,decisions)))}
        observed=saved[p['id']]
        assert observed['batch_joint_widths_exact']==list(map(str,widths)) and observed['batch_successes']==successes
        assert observed['batch_weights_exact']==list(map(str,pi)) and observed['adaptive_queries']==list(aq)
        for key,value in values.items():
            discrepancy=abs(value-observed[key]);assert discrepancy<1e-12;max_difference=max(max_difference,discrepancy)
        assert observed['exact_vs_original_success_mismatch']==(successes[ai]!=int(float(old['adaptive_recorded_success'])))
        values.update({k:p[k] for k in ['cohort','meter']});reconstructed.append(values)
    for grouping,key in [('cohorts','cohort'),('by_meter','meter')]:
        for label,s in report[grouping].items():
            rows=[r for r in reconstructed if r[key]==label];assert len(rows)==s['blocks']
            for field in FIELDS:
                total=sum(r[field] for r in rows);mean=total/len(rows)
                assert abs(total-s['totals'][field])<1e-10 and abs(mean-s['means'][field])<1e-12
    final={'status':'PASS','cohort':a.cohort,'blocks':len(plans),'exact_pair_decision_checks':checks,'exact_batch_width_checks':10*len(plans),
           'maximum_replay_difference':max_difference,'maximum_normalized_source_rounding':max_normalized_source_rounding,
           'scope':'All ten recorded batch widths, half-width outcomes, and policy mixture summaries recomputed independently. MSE winner/ranking signs reconstructed directly from frozen forecasts with exact rational arithmetic. Plan optimality and the universal theorem require separate proofs/checks.',
           'source_sha256':sha(Path(__file__)),'replay_cases_sha256':sha(directory/'cases.json'),'precision_plans_sha256':sha(paths['precision_plans']),
           'original_forecasts_sha256':sha(a.forecasts) if a.cohort=='all' else None,
           'elapsed_seconds':time.perf_counter()-start_clock}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(final,indent=2)+'\n');print(json.dumps(final,indent=2))
if __name__=='__main__':main()
