import json, collections
from pathlib import Path
import numpy as np
import pandas as pd
root=Path.cwd(); run=root/'work/decision_revision/confirmation'; out=root/'work/eligibility_review_20261011/ml_diagnosis'
f=pd.read_csv(run/'cases.csv'); q=f[f.initial_status=='unresolved'].pivot(index='case_id', columns='policy',values='paid_requests')
cost={}
for other in ['width_one','uniform_decision','hara_one','randomized_one']:
 d=q['ml_decision']-q[other]
 cost[other]={'wins':int((d<0).sum()),'ties':int((d==0).sum()),'losses':int((d>0).sum()),'records_saved_on_wins':int(-d[d<0].sum()),'extra_records_on_losses':int(d[d>0].sum()),'net_pooled_saved':int(-d.sum())}
first=collections.Counter(); rows=[]
for line in (run/'trajectories.jsonl').open():
 r=json.loads(line); ps=r['policies']; m=ps['ml_decision']['trace']; w=ps['width_one']['trace']
 if not m: continue
 first['cases']+=1; first['same_first_query']+=m[0]['query']==w[0]['query']
 first['ml_cert_first']+=m[0]['status'] in ['a','b']; first['width_cert_first']+=w[0]['status'] in ['a','b']
 first['ml_only_cert_first']+=(m[0]['status'] in ['a','b']) and not(w[0]['status'] in ['a','b'])
 first['width_only_cert_first']+=(w[0]['status'] in ['a','b']) and not(m[0]['status'] in ['a','b'])
 for p in ['ml_decision','uniform_decision']:
  for j,t in enumerate(ps[p]['trace']):
   rows.append({'policy':p,'step':j+1,'p':t['chosen_probability'],'success':t['status'] in ['a','b']})
a=pd.DataFrame(rows); cal=[]
for (pol,step),g in a.groupby(['policy','step']):
 cal.append({'policy':pol,'step':int(step),'n':len(g),'mean_predicted':float(g.p.mean()),'actual_success_rate':float(g.success.mean()),'brier':float(((g.p-g.success.astype(float))**2).mean())})
a['bin']=pd.cut(a.p,[-1e-12,.1,.3,.5,.7,.9,1+1e-12]); bins=[]
for (pol,bin_),g in a[a.step==1].groupby(['policy','bin'],observed=True):
 bins.append({'policy':pol,'bin':str(bin_),'n':len(g),'mean_predicted':float(g.p.mean()),'actual_success_rate':float(g.success.mean())})
o=pd.read_csv(root/'work/decision_revision/confirmation_oracle/cases.csv').set_index('case_id'); head={}
for p in ['ml_decision','width_one']:
 d=q[p]-o.reindex(q.index).oracle_minimum_requests
 head[p]={'cases_matching_hindsight':int((d==0).sum()),'cases_above_hindsight':int((d>0).sum()),'extra_pooled_queries':int(d.sum())}
r={'scope':'Read-only retrospective diagnosis of already reported confirmation results. No policy run, no tuning, not calibrated population inference.','cost_differences':cost,'first_query':dict(first),'selected_probabilities_by_stage':cal,'first_query_calibration_bins':bins,'oracle':head}
(out/'diagnostics.json').write_text(json.dumps(r,indent=2)); print(json.dumps(r,indent=2))
