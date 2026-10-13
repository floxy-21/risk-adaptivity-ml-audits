"""Secondary recorded model-choice outcomes of frozen shared precision policies.

Does not select queries using winner outcomes. Exact rational interval endpoints
use source binary64 contrasts and exact counter increments. This does not solve
minimum-query model selection; all selective policies retain two readings.
"""
from pathlib import Path
from fractions import Fraction as F
from datetime import datetime,timedelta,timezone
import argparse,csv,hashlib,itertools,json

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[1]
BATCHES=list(itertools.combinations(range(1,6),2))

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def load_data(args):
    paths=[args.external_geometry]
    if args.cohort=='all':paths=[*args.original_geometry,*paths]
    case_map={}
    for p in paths:
        for c in json.loads(p.read_text())['cases']:case_map[c['id']]=c
    original={}
    p1=args.original_answers
    if args.cohort=='all':
        with p1.open(newline='') as f:
            for row in csv.DictReader(f):
                original[row['meter'],datetime.fromisoformat(row['interval_start_utc'])]=F(int(row['end_counter_integer'])-int(row['start_counter_integer']),10**10)
    external={}
    p2=args.external_answers
    with p2.open(newline='') as f:
        for row in csv.DictReader(f):
            if row['valid']=='1':external['hpm_'+row['system_id'],datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))]=F(row['counter_kwh'])
    inputs=[*paths,p2]+([p1] if args.cohort=='all' else [])
    return case_map,original,external,{str(p.resolve().relative_to(ROOT)) if p.resolve().is_relative_to(ROOT) else str(p.resolve()):sha(p) for p in inputs}

def endpoints(pairs,y,Q):
    cuts=(0,*Q,6)
    bounds=[]
    for pair in pairs:
        c=list(map(F,pair['c']));d=F(pair['d'])
        lo=hi=d
        for left,right in zip(cuts,cuts[1:]):
            mass=sum(y[left:right]);lo+=mass*min(c[left:right]);hi+=mass*max(c[left:right])
        truth=d+sum(a*b for a,b in zip(c,y))
        assert lo<=truth<=hi
        bounds.append((lo,hi,truth))
    return bounds

def decision(pairs,y,Q):
    bounds=endpoints(pairs,y,Q)
    models={p[k] for p in pairs for k in ['model_a','model_b']}
    wins={m:set() for m in models};known=0
    for pair,(lo,hi,truth) in zip(pairs,bounds):
        a,b=pair['model_a'],pair['model_b']
        if hi<0:
            assert truth<0;wins[a].add(b);known+=1
        elif lo>0:
            assert truth>0;wins[b].add(a);known+=1
    selected=[m for m in models if len(wins[m])==3]
    assert len(selected)<=1
    return {'winner':int(bool(selected)),'ranking':int(known==6),'pairs':known,'winner_name':selected[0] if selected else ''}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort',choices=['external','all'],default='external')
    ap.add_argument('--plans',type=Path)
    ap.add_argument('--ledger',type=Path)
    ap.add_argument('--output-dir',type=Path)
    ap.add_argument('--original-geometry',type=Path,nargs='+',default=[BASE/'counter_adaptive/pilot/geometry.json',BASE/'counter_adaptive/continuation/geometry.json'])
    ap.add_argument('--external-geometry',type=Path,default=BASE/'external_validation/replay/geometry.json')
    ap.add_argument('--original-answers',type=Path,default=ROOT/'work/data_blem_hourly_endpoints.csv')
    ap.add_argument('--external-answers',type=Path,default=BASE/'external_heatpump/hourly/train_test_hourly_counters.csv')
    a=ap.parse_args()
    source_dir=HERE/('empirical_external_results' if a.cohort=='external' else 'empirical_results')
    a.plans=a.plans or source_dir/'empirical_plans.json'
    a.ledger=a.ledger or source_dir/'empirical_cases.csv'
    a.output_dir=a.output_dir or HERE/('decision_external_results' if a.cohort=='external' else 'decision_results')
    a.output_dir.mkdir(exist_ok=True,parents=True)
    plans=json.loads(a.plans.read_text())['plans']
    saved={r['id']:r for r in csv.DictReader(a.ledger.open(newline=''))}
    assert len(plans)==(279 if a.cohort=='external' else 1098)
    assert {p['cohort'] for p in plans}==({'external'} if a.cohort=='external' else {'original','external'})
    case_map,original,external,inputs=load_data(a)
    rows=[]
    for p in plans:
        start=datetime.fromisoformat(p['day']).replace(hour=p['start_hour'],tzinfo=timezone.utc)
        if p['cohort']=='original':y=[original[p['meter'],start+timedelta(hours=i)] for i in range(6)]
        else:
            counters=[external[p['meter'],start+timedelta(hours=i)] for i in range(7)]
            y=[v-u for u,v in zip(counters,counters[1:])]
        assert min(y)>=0 and abs(float(sum(y))-p['total_energy'])<1e-10
        pairs=[case_map[k] for k in p['pair_case_ids']]
        decisions=[decision(pairs,y,q) for q in BATCHES]
        r=saved[p['id']];g=p['geometry']
        indices={'adaptive':BATCHES.index(tuple(sorted([int(r['adaptive_first']),int(r['adaptive_second'])]))),
                 'greedy':BATCHES.index(tuple(sorted([int(r['greedy_first']),int(r['greedy_second'])]))),
                 'deterministic_batch':g['best_deterministic_batch_index']}
        row={k:p[k] for k in ['id','cohort','meter']}
        for name,index in indices.items():
            for key in ['winner','ranking','pairs']:row[name+'_'+key]=decisions[index][key]
        for key in ['winner','ranking','pairs']:
            row['randomized_batch_'+key]=sum(w*d[key] for w,d in zip(g['randomized_batch_weights'],decisions))
            row['uniform_batch_'+key]=sum(d[key] for d in decisions)/10
            row['zero_query_'+key]=decision(pairs,y,())[key]
            row['bulk_'+key]=decision(pairs,y,tuple(range(1,6)))[key]
        rows.append(row)
    keys=[k for k in rows[0] if k not in ['id','cohort','meter']]
    def aggregate(rr):return {'blocks':len(rr),'totals':{k:sum(r[k] for r in rr) for k in keys},'means':{k:sum(r[k] for r in rr)/len(rr) for k in keys}}
    report={'status':'PASS','cases':len(rows),'cohort':a.cohort,'scope':__doc__,
        'strict_sign_rule':'Exact rational endpoints and zero threshold; no numerical winner tolerance; all reported decisions checked against true contrast.',
        'cohorts':{k:aggregate([r for r in rows if r['cohort']==k]) for k in sorted({r['cohort'] for r in rows})},
        'by_meter':{k:aggregate([r for r in rows if r['meter']==k]) for k in sorted({r['meter'] for r in rows})},
        'source_sha256':sha(Path(__file__)),'plan_sha256':sha(a.plans),'ledger_sha256':sha(a.ledger),'inputs':inputs}
    (a.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.output_dir/'cases.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(report['cohorts'],indent=2))

if __name__=='__main__':main()
