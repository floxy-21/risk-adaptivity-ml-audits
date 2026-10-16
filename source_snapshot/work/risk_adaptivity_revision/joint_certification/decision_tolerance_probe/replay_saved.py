"""Rebuild all decision outcomes from bundled derived pair endpoints (not raw data).

This standalone standard-library path does not import the analysis producer or
the endpoint helper. Full source binding is checked by check.py --chain-dir.
"""
from pathlib import Path
from fractions import Fraction as Q
from collections import defaultdict
import argparse, csv, hashlib, json, random, time

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def close(a,b):assert abs(float(a)-float(b))<=2e-11,(a,b)
def quantile(v,p):
    v=sorted(v);z=(len(v)-1)*p;i=int(z)
    return v[i]+(z-i)*(v[min(i+1,len(v)-1)]-v[i])
def csv_write(path,rows):
    with path.open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=HERE/'results')
    parser.add_argument('--out',type=Path,default=HERE/'saved_replay')
    args=parser.parse_args();t0=time.perf_counter();args.out.mkdir(exist_ok=True,parents=True)
    protocol=read(HERE/'protocol.json');report=read(args.results/'report.json')
    saved=read(args.results/'saved_endpoint_inputs.json')
    assert saved['protocol_sha256']==report['protocol_sha256']==sha(HERE/'protocol.json')
    assert report['saved_endpoint_inputs_sha256']==sha(args.results/'saved_endpoint_inputs.json')
    assert report['case_outcomes_sha256']==sha(args.results/'case_outcomes.csv')
    assert report['producer_sha256']==sha(HERE/'analyze.py')
    blocks=saved['blocks'];assert len(blocks)==1098
    supplied=list(csv.DictReader((args.results/'case_outcomes.csv').open(newline='')))
    supplied={(x['id'],x['factor'],x['policy']):x for x in supplied}
    assert len(supplied)==1098*7*5
    factors=list(map(Q,protocol['thresholds']['factor_grid']));policies=protocol['policies']
    rows=[];endpoint_checks=0;model_decision_checks=0
    for b in blocks:
        assert 'answers' not in b,'Source answer vector must not be bundled'
        models=b['models'];assert models==sorted(models) and len(models)==4
        pairs=b['pair_order'];assert len(pairs)==6 and len({tuple(sorted(p)) for p in pairs})==6
        m2=Q(b['training_M2']);assert m2>0
        actual={m:Q(z) for m,z in b['actual_regrets'].items()}
        assert set(actual)==set(models) and min(actual.values())==0
        regrets=[];strict=[]
        for index,endpoints in enumerate(b['bounds']):
            assert len(endpoints)==6
            directed={}
            for (a,c),(l,u) in zip(pairs,endpoints):
                lower,upper=Q(l),Q(u);assert lower<=upper
                directed[a,c]=upper;directed[c,a]=-lower;endpoint_checks+=1
            risk={m:max([Q(0)]+[directed[m,j] for j in models if j!=m]) for m in models}
            assert risk=={m:Q(v) for m,v in b['upper_regrets'][index].items()}
            regrets.append(risk)
            strict.append([m for m in models if all(directed[m,j]<0 for j in models if j!=m)])
        assert strict==b['strict_winner_names']
        for f in factors:
            epsilon=f*m2
            qualified=[[m for m in models if u[m]<=epsilon] for u in regrets]
            for names in qualified:
                for m in names:assert actual[m]<=epsilon;model_decision_checks+=1
            for policy in policies:
                weights=list(map(Q,b['batch_mixtures'][policy]))
                assert len(weights)==10 and min(weights)>=0 and sum(weights)==1
                if policy in b['policy_batch_indices']:
                    idx=b['policy_batch_indices'][policy]
                    assert weights==[Q(int(i==idx)) for i in range(10)]
                chosen=[x[0] if x else '' for x in qualified]
                upper=sum(w*min(x.values()) for w,x in zip(weights,regrets))
                r={k:b[k] for k in ['id','cohort','meter','day']}
                r.update(factor=str(f),epsilon=str(epsilon),policy=policy,
                  epsilon_certified=str(sum(w*bool(x) for w,x in zip(weights,qualified))),
                  strict_winner=str(sum(w*bool(x) for w,x in zip(weights,strict))),
                  minimum_upper_regret=str(upper),minimum_upper_regret_div_M2=str(upper/m2),
                  certified_selected_model=chosen[b['policy_batch_indices'][policy]] if policy in b['policy_batch_indices'] else 'mixture',
                  success_weighted_actual_regret=str(sum(w*actual[m] for w,m in zip(weights,chosen) if m)))
                assert r==supplied[b['id'],str(f),policy]
                rows.append(r)
    lookup={(r['id'],r['factor'],r['policy']):r for r in rows}
    groups=defaultdict(list)
    for b in blocks:groups[b['cohort']+'/'+b['meter']].append(b)
    summary_rows=[];paired_rows=[]
    def check_summary(bb,label,summary):
        assert summary['blocks']==len(bb)
        for f in factors:
            ff=str(f);given=summary['factors'][ff]
            for name in policies:
                rr=[lookup[b['id'],ff,name] for b in bb];ps=given['policies'][name]
                count=sum(Q(r['epsilon_certified']) for r in rr)
                strict_count=sum(Q(r['strict_winner']) for r in rr)
                assert Q(ps['certified_expected_count'])==count
                assert Q(ps['strict_expected_count'])==strict_count
                close(ps['success_fraction'],count/len(bb))
                ur=[float(Q(r['minimum_upper_regret_div_M2'])) for r in rr]
                close(ps['mean_min_upper_regret_div_M2'],sum(ur)/len(ur))
                close(ps['median_min_upper_regret_div_M2'],quantile(ur,.5))
                summary_rows.append({'group':label,'blocks':len(bb),'factor':ff,'policy':name,
                  'expected_certified_count':float(count),'success_percent':float(100*count/len(bb)),
                  'strict_winner_expected_count':float(strict_count),
                  'mean_min_upper_regret_div_M2':sum(ur)/len(ur),'median_min_upper_regret_div_M2':quantile(ur,.5)})
            for name in policies[1:]:
                aa=[Q(lookup[b['id'],ff,'adaptive']['epsilon_certified']) for b in bb]
                vv=[Q(lookup[b['id'],ff,name]['epsilon_certified']) for b in bb]
                cells=[sum(a*v for a,v in zip(aa,vv)),sum(a*(1-v) for a,v in zip(aa,vv)),
                       sum((1-a)*v for a,v in zip(aa,vv)),sum((1-a)*(1-v) for a,v in zip(aa,vv))]
                pp=given['paired'][name]
                assert cells==[Q(pp[k]) for k in ['both','adaptive_only','comparator_only','neither']]
                close(pp['difference_pp'],100*(cells[1]-cells[2])/len(bb))
                if name in ['greedy','deterministic_batch']:
                    indices=[i for i,b in enumerate(bb) if Q(b['precision_success']['adaptive'])==1 and Q(b['precision_success'][name])==0]
                    link=pp['on_adaptive_only_precision_success'];assert link['blocks']==len(indices)
                    assert Q(link['adaptive_decision_only'])==sum(aa[i]*(1-vv[i]) for i in indices)
                    assert Q(link['comparator_decision_only'])==sum((1-aa[i])*vv[i] for i in indices)
                paired_rows.append({'group':label,'blocks':len(bb),'factor':ff,'comparator':name,
                  **{k:float(v) for k,v in zip(['both','adaptive_only','comparator_only','neither'],cells)},
                  'adaptive_minus_comparator_pp':pp['difference_pp'],
                  'lower95_pp':pp.get('descriptive_percentile_95_pp',['',''])[0],
                  'upper95_pp':pp.get('descriptive_percentile_95_pp',['',''])[1]})
    for key,bb in groups.items():check_summary(bb,key,report['systems'][key])
    for ci,cohort in enumerate(['original','external']):
        bb=[b for b in blocks if b['cohort']==cohort];check_summary(bb,cohort,report['cohorts'][cohort])
        byday=defaultdict(list)
        for b in bb:byday[b['day']].append(b['id'])
        days=sorted(byday);rng=random.Random(protocol['uncertainty']['seed']+ci);samples=[]
        assert len({len(v) for v in byday.values()})==1
        for _ in range(2000):
            picks=[]
            while len(picks)<len(days):
                start=rng.randrange(len(days));picks.extend((start+j)%len(days) for j in range(7))
            cc=[0]*len(days)
            for i in picks[:len(days)]:cc[i]+=1
            samples.append(cc)
        for f in factors:
            ff=str(f)
            for name in policies[1:]:
                values=[sum(float(Q(lookup[i,ff,'adaptive']['epsilon_certified'])-Q(lookup[i,ff,name]['epsilon_certified'])) for i in byday[d])/len(byday[d]) for d in days]
                draws=[100*sum(n*v for n,v in zip(cc,values))/len(days) for cc in samples]
                ci95=report['cohorts'][cohort]['factors'][ff]['paired'][name]['descriptive_percentile_95_pp']
                close(ci95[0],quantile(draws,.025));close(ci95[1],quantile(draws,.975))
    csv_write(args.out/'case_outcomes.csv',rows)
    csv_write(args.out/'all_factors_and_systems.csv',summary_rows)
    csv_write(args.out/'paired_outcomes.csv',paired_rows)
    assert sha(args.out/'case_outcomes.csv')==sha(args.results/'case_outcomes.csv')
    result={'status':'PASS','mode':'bundled-derived-endpoint-replay','blocks':len(blocks),
      'case_policy_factor_rows':len(rows),'oriented_pair_batch_endpoints_checked':endpoint_checks,
      'saved_reference_decision_checks':model_decision_checks,'bootstrap_intervals_recomputed':56,
      'scope':'Recomputes directed bounds, epsilon decisions, strict winners, all source/system summaries and paired bootstrap intervals from saved derived endpoints. It does not verify source records, reconstruct original answers, refit models or reselect policies. Run analyze.py and check.py with --chain-dir for full pinned-source verification.',
      'protocol_sha256':sha(HERE/'protocol.json'),'input_sha256':sha(args.results/'saved_endpoint_inputs.json'),
      'producer_report_sha256':sha(args.results/'report.json'),'checker_sha256':sha(__file__),
      'case_outcomes_sha256':sha(args.out/'case_outcomes.csv'),'elapsed_seconds':time.perf_counter()-t0}
    (args.out/'report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
