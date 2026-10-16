"""Independent source, vertex, orientation and summary checks; imports no replay producer."""
from pathlib import Path
from fractions import Fraction as Q
from datetime import datetime,timedelta,timezone
from collections import defaultdict
from itertools import combinations,product
import argparse,csv,hashlib,json,random,time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OUT=HERE/'results'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ts(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def close(a,b):assert abs(float(a)-float(b))<=2e-11,(a,b)
def quantile(v,p):
    v=sorted(v);a=(len(v)-1)*p;i=int(a)
    return v[i]+(a-i)*(v[min(i+1,len(v)-1)]-v[i])
def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chain-dir',type=Path,required=True,help='Full-chain replay root containing shared/ and original_raw/.')
    parser.add_argument('--results',type=Path,default=OUT)
    cli=parser.parse_args();OUT=cli.results
    t0=time.perf_counter();protocol=read(HERE/'protocol.json');report=read(OUT/'report.json')
    assert report['protocol_sha256']==sha(HERE/'protocol.json')
    assert report['producer_sha256']==sha(HERE/'analyze.py')
    def resolve(name):
        prefix='work/final_chain_20261014T031901Z/run/'
        return cli.chain_dir/name[len(prefix):] if name.startswith(prefix) else ROOT/name
    for name,h in protocol['inputs'].items():assert sha(resolve(name))==h,('hash',name)
    def locate(s):return resolve(next(k for k in protocol['inputs'] if k.endswith(s)))
    plans={x['id']:x for x in read(locate('shared/empirical_plans.json'))['plans']}
    ledger={x['id']:x for x in csv.DictReader(locate('shared/empirical_cases.csv').open(newline=''))}
    geometries={}
    for ending in ['original_raw/results/geometry.json','external_validation/replay/geometry.json']:
        for x in read(locate(ending))['cases']:assert x['id'] not in geometries;geometries[x['id']]=x
    training=read(locate('review_mechanism/executed/training_scales.json'))['systems']
    energy={};counter={}
    with locate('original_raw/prepared/data_blem_hourly_endpoints.csv').open(newline='') as h:
        for x in csv.DictReader(h):
            energy[x['meter'],ts(x['interval_start_utc'])]=Q(int(x['end_counter_integer'])-int(x['start_counter_integer']),10**10)
    with locate('external_heatpump/hourly/train_test_hourly_counters.csv').open(newline='') as h:
        for x in csv.DictReader(h):
            if x['valid']=='1':counter['hpm_'+x['system_id'],ts(x['timestamp_utc'])]=Q(x['counter_kwh'])
    records=read(OUT/'block_certificates.json')['blocks'];assert len(records)==1098
    rows=list(csv.DictReader((OUT/'case_outcomes.csv').open(newline='')))
    lookup={(r['id'],r['factor'],r['policy']):r for r in rows}
    assert len(lookup)==len(rows)==1098*7*5
    factors=list(map(Q,protocol['thresholds']['factor_grid']));policies=protocol['policies']
    batches=list(combinations(range(1,6),2))
    groups=defaultdict(list)
    for b in records:groups[b['cohort']+'/'+b['meter']].append(b)
    sample=set()
    for vv in groups.values():
        vv=sorted(vv,key=lambda b:b['id'])
        sample.update(vv[i]['id'] for i in (0,len(vv)//2,len(vv)-1))
    endpoint_pairs=0;vertex_objectives=0;certified_model_checks=0;branch_checks=0
    for b in records:
        plan=plans[b['id']];old=ledger[b['id']]
        assert b['pair_case_ids']==plan['pair_case_ids']
        dt=ts(b['day']).replace(hour=b['start_hour'],tzinfo=timezone.utc)
        if b['cohort']=='original':y=[energy[b['meter'],dt+timedelta(hours=j)] for j in range(6)]
        else:y=[counter[b['meter'],dt+timedelta(hours=j+1)]-counter[b['meter'],dt+timedelta(hours=j)] for j in range(6)]
        assert y==list(map(Q,b['answers'])) and min(y)>=0
        m2=Q(training[b['cohort']+'/'+b['meter']]['second_moment_exact'])
        assert m2==Q(b['training_M2'])
        pairs=[geometries[x] for x in b['pair_case_ids']]
        assert b['pair_order']==[[x['model_a'],x['model_b']] for x in pairs]
        models=sorted({z[k] for z in pairs for k in ['model_a','model_b']})
        assert models==b['models'] and len(models)==4
        for k in ['id','cohort','meter','day','start_hour']:assert b[k]==plan[k]
        g=plan['geometry']
        for name,first_key in [('adaptive','first_query'),('greedy','greedy_first_query')]:
            first=g[first_key];s=float(sum(y[:first])/sum(y))
            scores=[max(a*s+d for a,d in line) for line in g['conditional_lines'][first-1]]
            chosen=next(i for i,z in enumerate(scores) if z<=min(scores)+1e-12)
            second=g['second_query_dictionaries'][first-1][chosen]
            assert (first,second)==(int(old[name+'_first']),int(old[name+'_second']))
            assert b['policy_batch_indices'][name]==batches.index(tuple(sorted((first,second))))
            branch_checks+=1
        assert b['policy_batch_indices']['deterministic_batch']==g['best_deterministic_batch_index']
        raw=list(map(Q,g['randomized_batch_weights']));mass=sum(max(z,Q(0)) for z in raw)
        mixture=[max(z,Q(0))/mass for z in raw]
        assert list(map(Q,b['batch_mixtures']['randomized_mean_batch']))==mixture
        assert list(map(Q,b['batch_mixtures']['uniform_batch']))==[Q(1,10)]*10
        for name,index in b['policy_batch_indices'].items():
            assert list(map(Q,b['batch_mixtures'][name]))==[Q(int(i==index)) for i in range(10)]
        true_directed={}
        for pair in pairs:
            aa,bb=pair['model_a'],pair['model_b'];truth=Q(pair['d'])+sum(Q(c)*v for c,v in zip(pair['c'],y))
            true_directed[aa,bb]=truth;true_directed[bb,aa]=-truth
        actual={m:max([Q(0)]+[true_directed[m,j] for j in models if j!=m]) for m in models}
        assert actual=={k:Q(v) for k,v in b['actual_regrets'].items()}
        recomputed=[];strict=[]
        for qi,q in enumerate(batches):
            cuts=(0,*q,6);segments=[list(range(a,z)) for a,z in zip(cuts,cuts[1:])]
            masses=[sum(y[j] for j in seg) for seg in segments];directed={}
            for ri,pair in enumerate(pairs):
                coefficients=list(map(Q,pair['c']));constant=Q(pair['d'])
                # Exact feasible extremizers and coefficient-wise dual bounds.
                low_witness=[Q(0)]*6;high_witness=[Q(0)]*6
                for seg,amount in zip(segments,masses):
                    ilo=min(seg,key=lambda j:coefficients[j]);ihi=max(seg,key=lambda j:coefficients[j])
                    low_witness[ilo]=amount;high_witness[ihi]=amount
                    assert all(coefficients[ilo]<=coefficients[j]<=coefficients[ihi] for j in seg)
                lo=constant+sum(a*v for a,v in zip(coefficients,low_witness))
                hi=constant+sum(a*v for a,v in zip(coefficients,high_witness))
                assert [lo,hi]==list(map(Q,b['bounds'][qi][ri]))
                assert lo<=true_directed[pair['model_a'],pair['model_b']]<=hi
                endpoint_pairs+=1
                if b['id'] in sample:
                    values=[]
                    for indices in product(*segments):
                        vertex=[Q(0)]*6
                        for at,amount in zip(indices,masses):vertex[at]=amount
                        values.append(constant+sum(a*v for a,v in zip(coefficients,vertex)))
                    assert min(values)==lo and max(values)==hi
                    vertex_objectives+=len(values)
                directed[pair['model_a'],pair['model_b']]=hi
                directed[pair['model_b'],pair['model_a']]=-lo
            regrets={m:max([Q(0)]+[directed[m,j] for j in models if j!=m]) for m in models}
            recomputed.append(regrets)
            assert regrets=={k:Q(v) for k,v in b['upper_regrets'][qi].items()}
            strict.append([m for m in models if all(directed[m,j]<0 for j in models if j!=m)])
        assert strict==b['strict_winner_names']
        for f in factors:
            ff=str(f);eps=f*m2
            selected=[[m for m in models if rr[m]<=eps] for rr in recomputed]
            for names in selected:
                for m in names:assert actual[m]<=eps;certified_model_checks+=1
            for name in policies:
                mix=list(map(Q,b['batch_mixtures'][name]));r=lookup[b['id'],ff,name]
                assert Q(r['epsilon'])==eps
                assert Q(r['epsilon_certified'])==sum(w*bool(x) for w,x in zip(mix,selected))
                assert Q(r['strict_winner'])==sum(w*bool(x) for w,x in zip(mix,strict))
                target=sum(w*min(x.values()) for w,x in zip(mix,recomputed))
                assert Q(r['minimum_upper_regret'])==target
                assert Q(r['minimum_upper_regret_div_M2'])==target/m2
                assert Q(r['success_weighted_actual_regret'])==sum(w*actual[x[0]] for w,x in zip(mix,selected) if x)
                if name in b['policy_batch_indices']:
                    names=selected[b['policy_batch_indices'][name]]
                    assert r['certified_selected_model']==(names[0] if names else '')
    def summary_check(bb,summary):
        assert summary['blocks']==len(bb)
        for f in factors:
            ff=str(f);given=summary['factors'][ff]
            for name in policies:
                rr=[lookup[b['id'],ff,name] for b in bb];ps=given['policies'][name]
                assert Q(ps['certified_expected_count'])==sum(Q(r['epsilon_certified']) for r in rr)
                assert Q(ps['strict_expected_count'])==sum(Q(r['strict_winner']) for r in rr)
                close(ps['success_fraction'],Q(ps['certified_expected_count'])/len(bb))
                ur=[float(Q(r['minimum_upper_regret_div_M2'])) for r in rr]
                close(ps['mean_min_upper_regret_div_M2'],sum(ur)/len(ur))
                close(ps['median_min_upper_regret_div_M2'],quantile(ur,.5))
            for name in policies[1:]:
                a=[Q(lookup[b['id'],ff,'adaptive']['epsilon_certified']) for b in bb]
                v=[Q(lookup[b['id'],ff,name]['epsilon_certified']) for b in bb]
                cells=[sum(x*y for x,y in zip(a,v)),sum(x*(1-y) for x,y in zip(a,v)),
                       sum((1-x)*y for x,y in zip(a,v)),sum((1-x)*(1-y) for x,y in zip(a,v))]
                givenp=given['paired'][name]
                assert cells==[Q(givenp[k]) for k in ['both','adaptive_only','comparator_only','neither']]
                close(givenp['difference_pp'],100*(cells[1]-cells[2])/len(bb))
                if name in ['greedy','deterministic_batch']:
                    ids=[i for i,b in enumerate(bb) if Q(b['precision_success']['adaptive'])==1 and Q(b['precision_success'][name])==0]
                    link=givenp['on_adaptive_only_precision_success']
                    assert link['blocks']==len(ids)
                    assert Q(link['adaptive_decision_only'])==sum(a[i]*(1-v[i]) for i in ids)
                    assert Q(link['comparator_decision_only'])==sum((1-a[i])*v[i] for i in ids)
    for k,v in groups.items():summary_check(v,report['systems'][k])
    for ci,cohort in enumerate(['original','external']):
        bb=[b for b in records if b['cohort']==cohort];summary_check(bb,report['cohorts'][cohort])
        byday=defaultdict(list)
        for b in bb:byday[b['day']].append(b['id'])
        days=sorted(byday);rng=random.Random(protocol['uncertainty']['seed']+ci)
        counts=[]
        for _ in range(2000):
            picks=[]
            while len(picks)<len(days):
                start=rng.randrange(len(days));picks.extend((start+j)%len(days) for j in range(7))
            c=[0]*len(days)
            for i in picks[:len(days)]:c[i]+=1
            counts.append(c)
        for f in factors:
            ff=str(f)
            for name in policies[1:]:
                values=[sum(float(Q(lookup[i,ff,'adaptive']['epsilon_certified'])-Q(lookup[i,ff,name]['epsilon_certified'])) for i in byday[d])/len(byday[d]) for d in days]
                boot=[100*sum(n*v for n,v in zip(cc,values))/len(days) for cc in counts]
                got=report['cohorts'][cohort]['factors'][ff]['paired'][name]['descriptive_percentile_95_pp']
                close(got[0],quantile(boot,.025));close(got[1],quantile(boot,.975))
    known={'original':{'adaptive':123,'greedy':118,'deterministic_batch':122},
           'external':{'adaptive':207,'greedy':208,'deterministic_batch':201}}
    for c,ps in known.items():
        for p,n in ps.items():assert Q(report['cohorts'][c]['factors']['0']['policies'][p]['strict_expected_count'])==n
    result={'status':'PASS','source_bound_blocks':len(records),'case_policy_factor_rows':len(rows),
      'all_pair_batch_endpoint_intervals_checked':endpoint_pairs,'source_branch_decisions_checked':branch_checks,
      'representative_vertex_blocks':sorted(sample),'independent_vertex_objectives':vertex_objectives,
      'source_truth_certificate_checks':certified_model_checks,'bootstrap_intervals_recomputed':2*7*4,
      'scope':'Independent within-study implementation; no producer or replay helper imports. Full exact source-bound endpoint certificates plus exhaustive vertices on 18 fixed representative blocks. Not an external replication.',
      'protocol_sha256':sha(HERE/'protocol.json'),'producer_report_sha256':sha(OUT/'report.json'),
      'checker_sha256':sha(__file__),'elapsed_seconds':time.perf_counter()-t0}
    (OUT/'independent_check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

