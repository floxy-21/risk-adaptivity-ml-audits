"""Source-bound scalar/joint mechanism and training-scale floor diagnostics.

No fitting; policy calculations use no withheld evaluation answers. Training targets and
initially retained outer endpoints supply the declared absolute loss scale.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
import hashlib
import importlib.util
from itertools import combinations
import json
from pathlib import Path
import time
from input_binding import frozen

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ROOT = BASE.parents[1]
spec = importlib.util.spec_from_file_location('reading_budget', HERE.parent/'reading_budget/reading_budget.py')
rb = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
SETS = rb.SETS

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(s): return datetime.fromisoformat(s.replace('Z', '+00:00'))
def write(p,d): Path(p).write_text(json.dumps(rb.binding.clean(d),indent=2,allow_nan=False)+'\n',encoding='utf-8')

def training_scales(chain):
    """Rebuild eligibility from calendar-complete days and lag 1,2,7 days."""
    original = chain/'original_raw/prepared/data_blem_hourly.csv'
    external = BASE/'external_heatpump/hourly/train_test_hourly_counters.csv'
    oldmeta = ROOT/'outputs/study_meter_results.json'
    newmeta = BASE/'external_validation/operational/fresh_fits_20261012/training_report.json'
    training = {}; ledgers = {}; hashes = {str(p):sha(p) for p in [original,external,oldmeta,newmeta,ROOT/'outputs/run_energy_rank_study.py']}
    cutoff = datetime(2017,10,1,tzinfo=timezone.utc)
    with original.open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t=stamp(row['timestamp'])
            if not datetime(2017,1,1,tzinfo=timezone.utc)<=t<cutoff: continue
            for name,text in row.items():
                if name=='timestamp':continue
                if text and text.lower()!='nan':training.setdefault('original/'+name,{})[t]=F(text)
    counters={}
    cutoff = datetime(2025,7,1,tzinfo=timezone.utc)
    with external.open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t=stamp(row['timestamp_utc'])
            if t>cutoff:continue
            if row['valid']=='1' and row['counter_kwh']:
                counters.setdefault('external/hpm_'+row['system_id'],{})[t]=F(row['counter_kwh'])
    for name,points in counters.items():
        hourly={}
        for t,value in points.items():
            nxt=points.get(t+timedelta(hours=1))
            if t<cutoff and nxt is not None and nxt>=value:hourly[t]=nxt-value
        training[name]=hourly
    ref={}
    for r in read(oldmeta):
        m=r.get('meta',r)
        if m['cohort']=='blem_counters':ref['original/'+m['meter']]=m
    for m in read(newmeta)['systems']:ref['external/hpm_'+str(m['system_id'])]=m
    for name,hourly in sorted(training.items()):
        complete={}
        for day in sorted({t.replace(hour=0) for t in hourly}):
            values=[hourly.get(day+timedelta(hours=h)) for h in range(24)]
            if all(v is not None and v>=0 for v in values):complete[day]=values
        eligible=[d for d in complete if all(d-timedelta(days=lag) in complete for lag in [1,2,7])]
        values=[v for d in eligible for v in complete[d]]
        mean=sum(values,F(0))/len(values); second=sum((v*v for v in values),F(0))/len(values)
        assert len(eligible)==ref[name]['train_days'],(name,len(eligible),ref[name]['train_days'])
        assert abs(float(mean)-ref[name]['training_mean_kwh'])<1e-12
        ledgers[name]={'training_days':[d.date().isoformat() for d in eligible], 'training_days_count':len(eligible),
          'hour_count':len(values),'mean_exact':mean,'mean_float':float(mean),'frozen_mean':ref[name]['training_mean_kwh'],
          'second_moment_exact':second,'second_moment_kwh_squared':float(second),'square_of_mean_kwh_squared':float(mean*mean),
          'value_sequence_sha256':hashlib.sha256(json.dumps(list(map(str,values)),separators=(',',':')).encode()).hexdigest()}
    return ledgers,hashes

def load_totals(chain):
    p=chain/'original_raw/prepared/data_blem_hourly_endpoints.csv'
    starts={}; ends={}
    with p.open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t=stamp(row['interval_start_utc'])
            if t<datetime(2017,10,1,tzinfo=timezone.utc):continue
            if t.hour in (0,6,12):starts[(row['meter'],t.date().isoformat(),t.hour)]=int(row['start_counter_integer'])
            if t.hour in (5,11,17):ends[(row['meter'],t.date().isoformat(),t.hour-5)]=int(row['end_counter_integer'])
    totals={'original/%s/%s/%02d'%key:F(ends[key]-value,10**10) for key,value in starts.items() if key in ends}
    p=BASE/'external_heatpump/hourly/train_test_hourly_counters.csv'; outer={}
    with p.open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t=stamp(row['timestamp_utc'])
            if t.year==2025 and t.month==7 and t.hour in (0,6,12,18) and row['valid']=='1':
                outer[(row['system_id'],t.date().isoformat(),t.hour)]=F(row['counter_kwh'])
    for (system,day,hour),value in outer.items():
        if hour in (0,6,12) and (system,day,hour+6) in outer:
            totals[f'external/hpm_{system}/{day}/{hour:02d}']=outer[system,day,hour+6]-value
    return totals

def profile(c,q):
    cuts=(0,*q,6)
    return [max(max(row[a:b])-min(row[a:b]) for a,b in zip(cuts,cuts[1:])) for row in c]

def covers(c,thresholds):
    rules=[]
    for k in range(1,6):
        intervals=[]
        for j in range(1,6):
            if j==k:continue
            cuts=(0,*sorted((j,k)),6); segs=list(zip(cuts,cuts[1:])); lo=F(0);hi=F(1);ok=True
            for row,threshold in zip(c,thresholds):
                a=max(max(row[l:r])-min(row[l:r]) for l,r in segs if r<=k)
                b=max(max(row[l:r])-min(row[l:r]) for l,r in segs if l>=k)
                if a>b:hi=min(hi,(threshold-b)/(a-b))
                elif a<b:lo=max(lo,(threshold-b)/(a-b))
                elif b>threshold:ok=False
            if ok and lo<=hi:intervals.append({'second':j,'lower':lo,'upper':hi})
        end=F(0);started=False
        for x in sorted(intervals,key=lambda x:(x['lower'],x['upper'],x['second'])):
            if x['lower']>end:break
            started=True;end=max(end,x['upper'])
        if started and end==1:rules.append({'first':k,'intervals':intervals})
    return rules

def quantiles(values):
    v=sorted(map(float,values))
    if not v:return {'n':0}
    def q(p):
        x=(len(v)-1)*p;i=int(x);return v[i]+(x-i)*(v[min(i+1,len(v)-1)]-v[i])
    return {'n':len(v),'min':v[0],'q25':q(.25),'median':q(.5),'q75':q(.75),'max':v[-1]}

def summarize(rows):
    out={}
    for name in ['all','original','external']+sorted({r['cohort']+'/'+r['system'] for r in rows}):
        group=[r for r in rows if name=='all' or r['cohort']==name or r['cohort']+'/'+r['system']==name]
        saving=[r for r in group if r['baseline_saving']]
        joint=[r for r in saving if r['joint_only']]
        binding=[p for r in saving for p in r['contrasts'] if p['deletion_binding']]
        allc=[p for r in saving for p in r['contrasts']]
        out[name]={'blocks':len(group),'baseline_saving':len(saving),'joint_only':len(joint),
          'scalar_obstruction':len(saving)-len(joint),'joint_only_matched_half':sum(r['matched_half'] for r in joint),
          'matched_half':sum(r['matched_half'] for r in saving),
          'binding_contrasts':len(binding),'saving_blocks_with_no_single_deletion_binding_contrast':sum(not any(p['deletion_binding'] for p in r['contrasts']) for r in saving),
          'all_initial_widths_kwh_squared':quantiles(p['W0_exact'] for p in allc),
          'binding_initial_widths_kwh_squared':quantiles(p['W0_exact'] for p in binding),
          'binding_initial_width_to_training_second_moment':quantiles(p['W0_over_training_second_moment'] for p in binding),
          'binding_pair_counts':dict(Counter(p['pair'] for p in binding)),
          'minimum_obstruction_contrast_count':dict(sorted(Counter(r['minimum_obstruction_contrasts'] for r in saving).items())),
          'floor_results':{}}
        for factor in rows[0]['floors']:
            f=[r['floors'][factor] for r in group];s=[r['floors'][factor] for r in saving]
            total=sum(x['fixed_minimum'] for x in f); used=sum(x['selected_budget'] for x in f)
            out[name]['floor_results'][factor]={'fixed_total':total,'adaptive_two_else_minimum_fixed_total':used,'saved_readings':total-used,
              'saving_percent':100*(total-used)/total if total else 0,'saving_cases':sum(x['saving'] for x in f),
              'retained_baseline_saving_cases':sum(x['saving'] for x in s),'new_saving_cases':sum(x['saving'] for x in f)-sum(x['saving'] for x in s),
              'retained_joint_only_baseline':sum(r['floors'][factor]['saving'] for r in joint),
              'baseline_now_fixed_at_most_two':sum(x['fixed_minimum']<=2 for x in s),
              'fixed_budget_histogram':dict(sorted(Counter(x['fixed_minimum'] for x in f).items()))}
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--chain-dir',type=Path);p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args()
    start=time.perf_counter();protocol=read(HERE/'PROTOCOL.json');factors=list(map(F,protocol['floor_factor_grid']))
    if args.chain_dir:
        inputs,provenance=rb.binding.source_inputs(args.chain_dir)
        training,training_hashes=training_scales(args.chain_dir);totals=load_totals(args.chain_dir)
        pp=args.chain_dir/'precision/plans.json';plans={r['id']:r for r in read(pp)['plans']}
        # Cache only the declared audit inputs and provenance, never optional
        # evaluation answers or outcomes. A clean package can replay all blocks.
        compact_plans={k:{name:v[name] for name in ['pair_case_ids','original_c_binary64','precision_lower_exact','precision_upper_exact']} for k,v in plans.items()}
        write(HERE/'frozen_inputs.json',{'inputs':inputs,'full_source_run_provenance':provenance,'training':training,
          'training_hashes':training_hashes,'totals':totals,'plans':compact_plans})
        write(HERE/'frozen_input_manifest.json',{'frozen_inputs_sha256':sha(HERE/'frozen_inputs.json'),
          'scope':'Frozen coefficients, retained totals, original training moments and their source provenance. Default recomputes policies; it does not reconstruct raw training data.'})
    else:
        inputs,provenance,training,training_hashes,totals,plans=frozen()
    baseline=read(HERE.parent/'reading_budget/executed_all/ledger.json');old={r['id']:r for r in baseline['rows']}
    ledger=[];count=Counter()
    for inp in inputs:
        ident=inp['id'];c=inp['coefficients'];plan=plans[ident];cohort,system,*_=ident.split('/');scale=F(training[cohort+'/'+system]['second_moment_exact']);E=totals[ident]
        assert E>0
        raw=[list(map(F.from_float,row)) for row in plan['original_c_binary64']]
        widths=[E*(max(row)-min(row)) for row in raw]
        for a,b in zip(c,raw):assert a==[(x-min(b))/(max(b)-min(b)) for x in b]
        profiles={q:profile(c,q) for q in SETS}
        scalar=[min(len(q) for q,w in profiles.items() if w[r]<=F(1,2)) for r in range(6)]
        fixed=min(len(q) for q,w in profiles.items() if max(w)<=F(1,2))
        assert fixed==old[ident]['fixed_minimum_readings']
        saving=fixed>2 and old[ident]['adaptive_minimum_readings']==2
        contrasts=[]
        for r in range(6):
            deleted=min(len(q) for q,w in profiles.items() if max(w[:r]+w[r+1:])<=F(1,2))
            contrasts.append({'pair':'/'.join(plan['pair_case_ids'][r].split('/')[-2:]),'case_id':plan['pair_case_ids'][r],
              'scalar_minimum_fixed':scalar[r],'minimum_fixed_after_deletion':deleted,'deletion_binding':deleted<fixed,
              'W0_exact':widths[r],'W0_kwh_squared':float(widths[r]),'W0_over_training_second_moment':widths[r]/scale})
        row={'id':ident,'cohort':cohort,'system':system,'coefficient_digest':inp['coefficient_digest'],'known_total_exact':E,
          'baseline_fixed_minimum':fixed,'baseline_saving':saving,'joint_only':saving and max(scalar)<=2,
          'matched_half':plan['precision_lower_exact']=='1/2' and plan['precision_upper_exact']=='1/2',
          'contrasts':contrasts,'floors':{}}
        if saving:
            # Enumerate target subsets, not data: isolate the minimum joint order
            # responsible for failure of every fixed batch of two readings.
            success_rows=[{i for i,w in enumerate(profile_) if w<=F(1,2)} for q,profile_ in profiles.items() if len(q)==2]
            for number in range(1,7):
                blocking=[sub for sub in combinations(range(6),number) if not any(set(sub)<=good for good in success_rows)]
                if blocking:break
            row['minimum_obstruction_contrasts']=number
            row['minimum_obstruction_subsets']=blocking
        for factor in factors:
            eps=factor*scale;thresholds=[max(F(1,2),eps/w) for w in widths]
            good=[q for q,w in profiles.items() if all(x<=t for x,t in zip(w,thresholds))]
            q=min(good,key=lambda q:(len(q),q));rules=covers(c,thresholds)
            adaptive=len(q) if len(q)<=1 else 2 if rules else None
            if factor==0:assert adaptive==old[ident]['adaptive_minimum_readings']
            used=min(len(q),adaptive if adaptive is not None else len(q))
            row['floors'][str(factor)]={'epsilon_exact':eps,'thresholds_normalized':thresholds,'fixed_minimum':len(q),'fixed_batch':q,
              'adaptive_minimum_at_most_two':adaptive,'adaptive_cover':rules[0] if rules else None,
              'selected_budget':used,'saving':used<len(q),'original_half_rule_changed':any(t>F(1,2) for t in thresholds)}
            count['floor_block_plans']+=1;count['fixed_batch_threshold_checks']+=32
        ledger.append(row)
    assert sum(r['baseline_saving'] for r in ledger)==225
    args.output_dir.mkdir(parents=True,exist_ok=True)
    write(args.output_dir/'training_scales.json',{'status':'PASS','systems':training,'input_hashes':training_hashes})
    write(args.output_dir/'ledger.json',{'status':'PASS','rows':ledger})
    report={'status':'PASS','protocol_sha256':sha(HERE/'PROTOCOL.json'),'producer_sha256':sha(__file__),
      'ledger_sha256':sha(args.output_dir/'ledger.json'),'training_scales_sha256':sha(args.output_dir/'training_scales.json'),
      'provenance':provenance,'training_input_hashes':training_hashes,'summaries':summarize(ledger),'counts':count,
      'quantile_method':'linear interpolation at (n-1)*p; descriptive, no confidence interval',
      'binding_definition':'deleting this contrast strictly reduces the minimum fixed half-width budget; tied/redundant rows may be jointly binding without any single deletion binding',
      'no_withheld_evaluation_answers_used':True,'new_fits':0,'elapsed_seconds':time.perf_counter()-start}
    write(args.output_dir/'report.json',report)
    print(json.dumps(rb.binding.clean({'status':'PASS','summaries':{k:report['summaries'][k] for k in ['all','original','external']},'elapsed_seconds':report['elapsed_seconds']}),indent=2))

if __name__=='__main__':main()
