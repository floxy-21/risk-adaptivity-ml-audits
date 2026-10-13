"""Supplemental calls to frozen batch API; no production edits or new study."""
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'work/external_deadline/acquisition'))
from acquisition import POLICIES, select_batch
from study_recovery import prepare_blocks

results=[]
for label, c, obs, totals in [
    ('one_block_two_unknown', [0,1,0,0,0,0], [None,None,0,0,0,0], [1]),
    ('two_blocks_two_unknown_each', [0,1,0,0,0,0,0,2,0,0,0,0], [None,None,0,0,0,0,None,None,0,0,0,0], [1,1]),
    ('three_unknown_equal_remainder', [0,1,1,0,0,0], [None,None,None,0,0,0], [1]),
]:
    a=np.ones(len(c));b=a+len(c)*np.asarray(c)/2
    obs=np.asarray(obs,dtype=float)
    for policy in POLICIES:
        for seed in range(8):
            report=select_batch(policy,a,b,obs,totals,budget=2,rng=np.random.default_rng(seed),surrogate_mean=np.full(len(c),.4),surrogate_sd=.5)
            q=report['query_indices']
            assert len(q)<=2 and len(set(q))==len(q)
            for start in range(0,len(c),6):
                m=int(np.isnan(obs[start:start+6]).sum())
                assert sum(start<=i<start+6 for i in q)<=max(0,m-1)
            if label=='one_block_two_unknown':assert len(q)==1
            if label=='two_blocks_two_unknown_each':assert len(q)==2
            results.append({'fixture':label,'policy':policy,'seed':seed,'batch':q})

details=[]
for period, target, policy in [('validation','MAC000004|2013-12-11|1103|0-3','hara'),('test','MAC000022|2014-02-26|2207|0-2','greedy')]:
    with (ROOT/f'work/external_deadline/{period}/trajectories.jsonl').open(encoding='utf-8') as f:
        for line in f:
            case=json.loads(line)
            if case['case_id']!=target:continue
            coeff=2*(np.asarray(case['b'])-np.asarray(case['a']))/len(case['a'])
            for stage in case['policies'][policy]['stages']:
                blocks=prepare_blocks(coeff,stage['before'],case['totals'])
                details.append({'period':period,'case':target,'policy':policy,'query':stage['batch'],
                                'blocks':[{'indices':b.indices,'coefficients':b.coefficients,'energy_production':b.energy,
                                           'energy_fsum':case['totals'][b.indices[0]//6]-math.fsum(x for x in stage['before'][6*(b.indices[0]//6):6*(b.indices[0]//6)+6] if x is not None)} for b in blocks],
                                'diagnostics':stage['diagnostics']})
            break

out={'status':'passed','fixture_calls':len(results),'results':results,'near_zero_diagnostic':details,
     'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
     'interpretation':'Counts smaller than mathematical count-only capacity may be valid at-most choices; active-energy diagnostics distinguish summation ulps.'}
(OUT/'batch_api_fixtures.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':out['status'],'fixture_calls':len(results),'near_zero_diagnostic':details},indent=2))
