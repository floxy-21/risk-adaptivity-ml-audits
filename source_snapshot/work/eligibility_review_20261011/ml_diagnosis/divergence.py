import json,collections
from pathlib import Path
r=Path('work/decision_revision/confirmation'); out=Path('work/eligibility_review_20261011/ml_diagnosis')
a=collections.defaultdict(lambda:collections.Counter())
for line in (r/'trajectories.jsonl').open():
 j=json.loads(line)['policies']; m=j['ml_decision']; w=j['width_one']; mt=m['trace'];wt=w['trace']
 if not mt:continue
 d=m['paid_requests']-w['paid_requests']; bucket='win' if d<0 else 'loss' if d>0 else 'tie'
 first=next((k for k,(u,v) in enumerate(zip(mt,wt),1) if u['query']!=v['query']),0)
 a[bucket]['cases']+=1;a[bucket]['divergence_at_'+str(first)]+=1;a[bucket]['same_first_query']+=mt[0]['query']==wt[0]['query']
 if mt[0]['query']==wt[0]['query']:a[bucket]['net_extra_reads_same_first']+=d
 else:a[bucket]['net_extra_reads_different_first']+=d
print(json.dumps(a,indent=2));(out/'divergence.json').write_text(json.dumps(a,indent=2))
