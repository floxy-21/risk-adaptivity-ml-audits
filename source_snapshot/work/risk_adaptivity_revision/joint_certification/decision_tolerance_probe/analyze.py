"""Retrospective epsilon-decision replay of frozen two-reading precision policies."""
from pathlib import Path
from fractions import Fraction as F
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from types import SimpleNamespace
import argparse, csv, hashlib, importlib.util, itertools, json, random, time

HERE=Path(__file__).resolve().parent
JOINT=HERE.parent
BASE=JOINT.parent
ROOT=BASE.parents[1]
BATCHES=list(itertools.combinations(range(1,6),2))
POLICIES=['adaptive','greedy','deterministic_batch','randomized_mean_batch','uniform_batch']

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,F):return str(v)
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    return v
def dump(p,v):Path(p).write_text(json.dumps(clean(v),indent=2,allow_nan=False)+'\n',encoding='utf-8')
def csv_write(p,rows):
    with Path(p).open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows([clean(r) for r in rows])
def percentile(v,p):
    v=sorted(v);z=(len(v)-1)*p;i=int(z);f=z-i
    return v[i]*(1-f)+v[min(i+1,len(v)-1)]*f
def choice(geometry,first,y):
    t=float(sum(y[:first])/sum(y))
    lines=geometry['conditional_lines'][first-1]
    values=[max(slope*t+intercept for slope,intercept in row) for row in lines]
    best=min(values)
    index=next(i for i,x in enumerate(values) if x<=best+1e-12)
    return geometry['second_query_dictionaries'][first-1][index]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chain-dir',type=Path,required=True,help='Full-chain replay root containing shared/ and original_raw/. Exact frozen hashes are required.')
    parser.add_argument('--out',type=Path,default=HERE/'results')
    cli=parser.parse_args()
    start=time.perf_counter()
    p=read(HERE/'protocol.json')
    assert p['status']=='FROZEN'
    def resolve(name):
        prefix='work/final_chain_20261014T031901Z/run/'
        return cli.chain_dir/name[len(prefix):] if name.startswith(prefix) else ROOT/name
    for name,h in p['inputs'].items():assert sha(resolve(name))==h,('Input mismatch',name)
    def find(suffix):return resolve(next(k for k in p['inputs'] if k.endswith(suffix)))
    plans_path=find('shared/empirical_plans.json');ledger_path=find('shared/empirical_cases.csv')
    spec=importlib.util.spec_from_file_location('frozen_decision_helper',find('joint_certification/decision_replay.py'))
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    args=SimpleNamespace(cohort='all',
       original_geometry=[find('original_raw/results/geometry.json')],
       external_geometry=find('external_validation/replay/geometry.json'),
       original_answers=find('original_raw/prepared/data_blem_hourly_endpoints.csv'),
       external_answers=find('external_heatpump/hourly/train_test_hourly_counters.csv'))
    case_map,original,external,input_hashes=helper.load_data(args)
    plans=read(plans_path)['plans'];assert len(plans)==1098
    saved={r['id']:r for r in csv.DictReader(ledger_path.open(newline=''))}
    training=read(find('review_mechanism/executed/training_scales.json'))['systems']
    factors=list(map(F,p['thresholds']['factor_grid']))
    out=cli.out;out.mkdir(exist_ok=True,parents=True)
    blocks=[];rows=[];max_weight_correction=0.;clipped_weight_count=0
    for plan in plans:
        day=datetime.fromisoformat(plan['day']).replace(hour=plan['start_hour'],tzinfo=timezone.utc)
        if plan['cohort']=='original':
            y=[original[plan['meter'],day+timedelta(hours=h)] for h in range(6)]
        else:
            q=[external[plan['meter'],day+timedelta(hours=h)] for h in range(7)]
            y=[b-a for a,b in zip(q,q[1:])]
        assert min(y)>=0 and abs(float(sum(y))-plan['total_energy'])<1e-10
        pairs=[case_map[k] for k in plan['pair_case_ids']]
        models=sorted({pair[k] for pair in pairs for k in ['model_a','model_b']})
        assert len(models)==4 and len(pairs)==6
        m2=F(training[plan['cohort']+'/'+plan['meter']]['second_moment_exact'])
        g=plan['geometry'];old=saved[plan['id']]
        first=g['first_query'];second=choice(g,first,y)
        gfirst=g['greedy_first_query'];gsecond=choice(g,gfirst,y)
        assert (first,second)==(int(old['adaptive_first']),int(old['adaptive_second']))
        assert (gfirst,gsecond)==(int(old['greedy_first']),int(old['greedy_second']))
        indices={'adaptive':BATCHES.index(tuple(sorted((first,second)))),
                 'greedy':BATCHES.index(tuple(sorted((gfirst,gsecond)))),
                 'deterministic_batch':g['best_deterministic_batch_index']}
        raw=list(map(F,g['randomized_batch_weights']))
        assert min(raw)>=F('-1e-12') and abs(float(sum(raw))-1)<1e-8
        clipped_weight_count+=sum(x<0 for x in raw)
        weights=[max(F(0),x) for x in raw];total=sum(weights);weights=[x/total for x in weights]
        max_weight_correction=max(max_weight_correction,max(abs(float(a-b)) for a,b in zip(raw,weights)))
        mixes={k:[F(int(i==v)) for i in range(10)] for k,v in indices.items()}
        mixes['randomized_mean_batch']=weights;mixes['uniform_batch']=[F(1,10)]*10
        all_bounds=[helper.endpoints(pairs,y,q) for q in BATCHES]
        upper=[];strict=[];truth={}
        for pair,(_,_,actual) in zip(pairs,all_bounds[0]):
            truth[pair['model_a'],pair['model_b']]=actual
            truth[pair['model_b'],pair['model_a']]=-actual
        actual_regret={m:max([F(0)]+[truth[m,j] for j in models if j!=m]) for m in models}
        for bounds in all_bounds:
            directed={}
            for pair,(lo,hi,actual) in zip(pairs,bounds):
                a,b=pair['model_a'],pair['model_b']
                assert lo<=actual<=hi
                directed[a,b]=hi;directed[b,a]=-lo
            upper.append({m:max([F(0)]+[directed[m,j] for j in models if j!=m]) for m in models})
            strict.append([m for m in models if all(directed[m,j]<0 for j in models if j!=m)])
            assert len(strict[-1])<=1
        block={k:plan[k] for k in ['id','cohort','meter','day','start_hour']}
        block.update({'models':models,'pair_case_ids':plan['pair_case_ids'],
          'pair_order':[[x['model_a'],x['model_b']] for x in pairs], 'answers':y,'training_M2':m2,
          'policy_batch_indices':indices,'batch_mixtures':mixes,'batches':BATCHES,
          'bounds':[[[lo,hi] for lo,hi,_ in rr] for rr in all_bounds],
          'upper_regrets':upper,'actual_regrets':actual_regret,
          'strict_winner_names':strict,
          'precision_success':{'adaptive':F(old['adaptive_recorded_success']),
             'greedy':F(old['greedy_recorded_success']),'deterministic_batch':F(old['det_batch_recorded_success']),
             'randomized_mean_batch':F(old['randomized_batch_recorded_success_probability']),
             'uniform_batch':F(old['uniform_batch_recorded_success_probability'])}})
        for factor in factors:
            epsilon=factor*m2
            qualified=[[m for m in models if up[m]<=epsilon] for up in upper]
            for q in qualified:
                for m in q:assert actual_regret[m]<=epsilon
            for policy,mix in mixes.items():
                success=sum(w*bool(q) for w,q in zip(mix,qualified))
                strict_success=sum(w*bool(q) for w,q in zip(mix,strict))
                chosen=[q[0] if q else '' for q in qualified]
                expected_upper=sum(w*min(up.values()) for w,up in zip(mix,upper))
                chosen_regret=sum(w*actual_regret[m] for w,m in zip(mix,chosen) if m)
                row={k:block[k] for k in ['id','cohort','meter','day']}
                row.update({'factor':str(factor),'epsilon':epsilon,'policy':policy,
                    'epsilon_certified':success,'strict_winner':strict_success,
                    'minimum_upper_regret':expected_upper,'minimum_upper_regret_div_M2':expected_upper/m2,
                    'certified_selected_model':chosen[indices[policy]] if policy in indices else 'mixture',
                    'success_weighted_actual_regret':chosen_regret})
                rows.append(row)
        blocks.append(block)
    csv_write(out/'case_outcomes.csv',rows)
    dump(out/'block_certificates.json',{'blocks':blocks})
    saved_blocks=[{k:v for k,v in b.items() if k!='answers'} for b in blocks]
    dump(out/'saved_endpoint_inputs.json',{'scope':'Derived endpoint-to-decision replay only. No source readings are bundled here. Full source regeneration requires the pinned source records and --chain-dir.',
         'protocol_sha256':sha(HERE/'protocol.json'),'blocks':saved_blocks})
    lookup={(r['id'],r['factor'],r['policy']):r for r in rows}
    def summarize(bb):
        result={}
        for f in factors:
            ff=str(f);policy_summary={};paired={}
            for policy in POLICIES:
                rr=[lookup[b['id'],ff,policy] for b in bb]
                ss=sum(r['epsilon_certified'] for r in rr)
                ur=[r['minimum_upper_regret_div_M2'] for r in rr]
                policy_summary[policy]={'certified_expected_count':ss,'success_fraction':float(ss/len(bb)),
                    'strict_expected_count':sum(r['strict_winner'] for r in rr),
                    'mean_min_upper_regret_div_M2':float(sum(ur)/len(ur)),
                    'median_min_upper_regret_div_M2':percentile(list(map(float,ur)),.5)}
            for policy in POLICIES[1:]:
                cells=[F(0)]*4;delta=[]
                link={'blocks':0,'adaptive_decision_only':F(0),'comparator_decision_only':F(0)}
                for b in bb:
                    a=lookup[b['id'],ff,'adaptive']['epsilon_certified'];v=lookup[b['id'],ff,policy]['epsilon_certified']
                    for i,x in enumerate((a*v,a*(1-v),(1-a)*v,(1-a)*(1-v))):cells[i]+=x
                    delta.append(a-v)
                    if policy in ('greedy','deterministic_batch') and b['precision_success']['adaptive']==1 and b['precision_success'][policy]==0:
                        link['blocks']+=1;link['adaptive_decision_only']+=a*(1-v);link['comparator_decision_only']+=(1-a)*v
                paired[policy]={'both':cells[0],'adaptive_only':cells[1],'comparator_only':cells[2],
                    'neither':cells[3],'difference_pp':float(sum(delta)*100/len(bb)),
                    'on_adaptive_only_precision_success':link}
            result[ff]={'policies':policy_summary,'paired':paired}
        return {'blocks':len(bb),'factors':result}
    cohorts={k:summarize([b for b in blocks if b['cohort']==k]) for k in ['original','external']}
    systems={key:summarize([b for b in blocks if b['cohort']+'/'+b['meter']==key])
             for key in sorted({b['cohort']+'/'+b['meter'] for b in blocks})}
    for ci,cohort in enumerate(['original','external']):
        bb=[b for b in blocks if b['cohort']==cohort];days=sorted({b['day'] for b in bb})
        day_blocks={d:[b for b in bb if b['day']==d] for d in days};assert len({len(v) for v in day_blocks.values()})==1
        rng=random.Random(p['uncertainty']['seed']+ci);samples=[]
        for _ in range(2000):
            indices=[]
            while len(indices)<len(days):
                start_i=rng.randrange(len(days));indices.extend((start_i+k)%len(days) for k in range(7))
            samples.append(indices[:len(days)])
        for f in factors:
            ff=str(f)
            for policy in POLICIES[1:]:
                vals=[sum(float(lookup[b['id'],ff,'adaptive']['epsilon_certified']-lookup[b['id'],ff,policy]['epsilon_certified'])
                          for b in day_blocks[d])/len(day_blocks[d]) for d in days]
                draws=[100*sum(vals[j] for j in sample)/len(days) for sample in samples]
                cohorts[cohort]['factors'][ff]['paired'][policy]['descriptive_percentile_95_pp']=[percentile(draws,.025),percentile(draws,.975)]
    expected={'original':{'adaptive':123,'greedy':118,'deterministic_batch':122},
              'external':{'adaptive':207,'greedy':208,'deterministic_batch':201}}
    strict_checks={}
    for cohort,ps in expected.items():
        for policy,value in ps.items():
            got=cohorts[cohort]['factors']['0']['policies'][policy]['strict_expected_count']
            assert got==value,(cohort,policy,got,value)
            strict_checks[cohort+'/'+policy]=got
    report={'status':'PASS','scope':p['scope'],'cases':1098,'case_policy_factor_rows':len(rows),
      'factor_grid':list(map(str,factors)),'primary_factor':'1/100','cohorts':cohorts,'systems':systems,
      'strict_winner_reconciliation':strict_checks,
      'weight_normalization':{'max_absolute_correction':max_weight_correction,'negative_roundoff_weights_clipped':clipped_weight_count},
      'exact_definition':'For each model, upper regret=max(0, all directed pair upper bounds); certified iff upper regret<=epsilon. Strict winner checked separately with all directed bounds<0.',
      'bootstrap':p['uncertainty'],'protocol_sha256':sha(HERE/'protocol.json'),'producer_sha256':sha(__file__),
      'inputs':p['inputs'],'source_mode':'full-source --chain-dir, exact frozen input hashes',
      'saved_endpoint_inputs_sha256':sha(out/'saved_endpoint_inputs.json'),
      'case_outcomes_sha256':sha(out/'case_outcomes.csv'),'elapsed_seconds':time.perf_counter()-start}
    dump(out/'report.json',report)
    print(json.dumps({'status':'PASS','rows':len(rows),'primary_counts':{c:{name:float(v['factors']['1/100']['policies'][name]['certified_expected_count']) for name in POLICIES} for c,v in cohorts.items()}},indent=2))
if __name__=='__main__':main()

