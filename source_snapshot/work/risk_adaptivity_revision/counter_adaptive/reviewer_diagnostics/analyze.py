"""Post-review comparator/outcome audit. No policy or threshold is retuned.

The precision-optimal support is the pre-existing coefficient-only half-cover
rule. Original five-policy outputs are read unchanged. Integer source
registers independently determine the added mixture's interval locations.
"""
from pathlib import Path
from fractions import Fraction as F
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from itertools import combinations
import argparse, csv, hashlib, json, math, sys

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(STUDY/'math_review'))
from check_half_cover import make_cover, RAW_HASHES
from check_counter_adaptive import conditional_coefficients

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def interval(c,d,y,Q):
    cuts=(0,)+tuple(Q)+(6,)
    lo=hi=d
    for a,b in zip(cuts[:-1],cuts[1:]):
        mass=sum(y[a:b]);lo+=mass*min(c[a:b]);hi+=mass*max(c[a:b])
    return lo,hi

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directories',nargs='+',type=Path,default=[STUDY/'pilot',STUDY/'continuation'])
    p.add_argument('--data-dir',type=Path,default=ROOT/'work')
    p.add_argument('--output-dir',type=Path,default=HERE)
    args=p.parse_args(); cases={};replays={}; hashes={}
    for directory in args.directories:
        for name in ['geometry.json','replay_cases.csv']:
            hashes[str(directory/name)]=sha(directory/name)
        for row in json.loads((directory/'geometry.json').read_text())['cases']:
            assert row['id'] not in cases;cases[row['id']]=row
        with (directory/'replay_cases.csv').open(newline='') as f:
            for row in csv.DictReader(f):
                key=(row['id'],row['policy']);assert key not in replays;replays[key]=row
    assert len(cases)==4914 and len(replays)==24570
    half=json.loads((STUDY/'math_review/half_cover_verification.json').read_text())
    witnesses={r['id']:r for r in half['cover_witnesses']}
    assert len(witnesses)==290
    # Confirm all added policies from coefficients only, before opening replies.
    policies={}
    for key,w in witnesses.items():
        row=cases[key];c=list(map(F.from_float,row['c'])); span=max(c)-min(c)
        cn=[(v-min(c))/span for v in c]
        _,chosen=make_cover(cn,row['geometry']['first'],F(1,2))
        Qs=[tuple(sorted((row['geometry']['first'],z['j']))) for z in chosen]
        assert Qs==[tuple(q) for q in w['batches']]
        policies[key]=Qs
    raw={}
    for meter in sorted({r['meter'] for r in cases.values()}):
        src=args.data_dir/f"data_blem_{meter.replace('_','-')}.csv"
        assert sha(src)==RAW_HASHES[meter]
        hashes[str(src)]=sha(src)
        with src.open(newline='') as f:
            raw[meter]={int(r['time']):int(r['energy']) for r in csv.DictReader(f)}
    added=[]; witness_case=None
    for key,Qs in policies.items():
        row=cases[key];w=witnesses[key]
        t0=datetime.fromisoformat(row['day']).replace(tzinfo=timezone.utc)+timedelta(hours=row['start_hour'])
        cv=[raw[row['meter']][int((t0+timedelta(hours=h)).timestamp())*1000] for h in range(7)]
        y=[F(cv[h+1]-cv[h],10**10) for h in range(6)]
        c=list(map(F.from_float,row['c']));d=F.from_float(row['d']);E=sum(y);span=max(c)-min(c)
        endpoints=[interval(c,d,y,Q) for Q in Qs]
        success=sum(F(int(hi-lo<=E*span/2),2) for lo,hi in endpoints)
        relative=sum((hi-lo)/(2*E*span) for lo,hi in endpoints)
        assert success==F(w['recorded_success_exact'])
        assert relative==F(w['recorded_relative_width_exact'])
        winner=sum(.5*int(float(hi)<-1e-9*max(1,abs(float(lo)),abs(float(hi))) or float(lo)>1e-9*max(1,abs(float(lo)),abs(float(hi)))) for lo,hi in endpoints)
        added.append({'id':key,'meter':row['meter'],'phase':row['phase'],'policy':'precision_optimal_cover','success':float(success),'relative_width':float(relative),'winner':winner})
        if key==half['representative_witnesses'][0]['id']:
            cn=[(v-min(c))/span for v in c];M=math.lcm(*(v.denominator for v in cn));nums=[int(v*M) for v in cn]
            batch=[]
            weights=list(map(F,w['adverse_weights_exact']))
            for Q in combinations(range(1,6),2):
                cuts=(0,)+Q+(6,);v=[None]*6
                for a,b in zip(cuts[:-1],cuts[1:]):
                    for h in range(a,b):v[h]=max(cn[a:b])-min(cn[a:b])
                upper=sum(weights[h]*int(v[h]<=F(1,2)) for h in range(6))
                assert upper<=F(1,2)
                batch.append({'Q':Q,'range_numerators':[int(x*M) for x in v],'adverse_success':str(upper)})
            witness_case={'id':key,'total_kWh_exact':str(E),'original_c_binary64':row['c'],'normalized_coefficient_numerators':nums,'denominator':M,'batches':batch,'cover':w,'interpretation':'z=y/E and q=(c-min(c))/(max(c)-min(c)); displayed widths normalized by W0. Exact rationals encode the original binary64 coefficient vector.'}
    assert witness_case
    summaries=[]
    for subset,ids in [('all',list(cases)),('separation',list(witnesses))]:
        for policy in ['adaptive','det_batch','mean_batch','uniform_batch','greedy_adaptive']:
            rr=[replays[i,policy] for i in ids]
            summaries.append({'subset':subset,'policy':policy,'n':len(ids),'success':sum(float(r['success_0.5']) for r in rr)/len(rr),'relative_width':sum(float(r['relative_width']) for r in rr)/len(rr),'winner':sum(float(r['winner_probability']) for r in rr)/len(rr)})
    summaries.append({'subset':'separation','policy':'precision_optimal_cover','n':290,**{key:sum(r[key] for r in added)/290 for key in ['success','relative_width','winner']}})
    paired=[]
    for subset,ids in [('all',list(cases)),('separation',list(witnesses))]:
        for label,field in [('precision','success_0.5'),('ordering','winner_probability')]:
            counts=defaultdict(int)
            for key in ids:
                a=float(replays[key,'adaptive'][field]);b=float(replays[key,'det_batch'][field]);assert a in (0,1) and b in (0,1)
                counts[{(1,1):'both',(1,0):'adaptive_only',(0,1):'batch_only',(0,0):'neither'}[a,b]]+=1
            paired.append({'subset':subset,'outcome':label,'n':len(ids),**{key:counts[key] for key in ['both','adaptive_only','batch_only','neither']}})
    groups=[]
    for field in ['meter','phase']:
        for group in sorted({r[field] for r in cases.values()}):
            ids=[key for key,r in cases.items() if r[field]==group]
            out={'grouping':field,'group':group,'n':len(ids),'separation':len(set(ids)&set(witnesses))}
            for policy in ['adaptive','det_batch']:
                for metric,col in [('precision','success_0.5'),('ordering','winner_probability')]:
                    out[f'{policy}_{metric}']=sum(float(replays[key,policy][col]) for key in ids)/len(ids)
            groups.append(out)
    report={'status':'PASS','scope':'Post-review descriptive diagnostics, original cases/policies/threshold unchanged; no new independent cohort','input_sha256':hashes,'counts':{'cases':4914,'original_policy_rows':24570,'precision_optimal_rows':290},'mixture_selection':'Existing coefficient-only half-cover: lowest-index full-cover action if any; otherwise widest prefix and earliest suffix coverage with smallest-index ties, equal probabilities. No replay answers enter selection.','ordering_margin':'1e-9 * max(1,abs(lower),abs(upper)), same as original replay','summaries':summaries,'paired':paired,'groups':groups,'fully_specified_witness':witness_case}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    with (args.output_dir/'outcome_ledger.csv').open('w',newline='') as f:
        fields=['id','meter','phase','separation','adaptive_precision','batch_precision','adaptive_ordering','batch_ordering']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for key,row in cases.items():
            rr={'id':key,'meter':row['meter'],'phase':row['phase'],'separation':int(key in witnesses)}
            for label,policy in [('adaptive','adaptive'),('batch','det_batch')]:
                rr[label+'_precision']=int(float(replays[key,policy]['success_0.5']))
                rr[label+'_ordering']=int(float(replays[key,policy]['winner_probability']))
            writer.writerow(rr)
    with (args.output_dir/'precision_cover_ledger.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(added[0]));writer.writeheader();writer.writerows(added)
    (args.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    # No raw fine-resolution replies are redistributed.
    print(json.dumps({key:report[key] for key in ['status','counts','summaries','paired','groups']},indent=2))

if __name__=='__main__':main()
