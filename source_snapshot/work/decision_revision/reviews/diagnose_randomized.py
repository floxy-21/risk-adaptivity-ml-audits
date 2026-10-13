from pathlib import Path
import json
import numpy as np
import verify_decision_confirmation as checker

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
out=ROOT/'work/decision_revision/confirmation'
checked=0
with (out/'source_cases.jsonl').open() as source,(out/'trajectories.jsonl').open() as trace:
    for source_line,trace_line in zip(source,trace):
        case=json.loads(source_line);run=json.loads(trace_line)
        assert case['case_id']==run['case_id']
        a,b,observed,totals=(np.asarray(case[k],float) for k in ['a','b','initial_observed','totals'])
        for number,stage in enumerate(run['policies']['randomized_one']['trace']):
            try:checker.verify_randomized(a,b,observed,totals,stage['query'],stage['diagnostics'])
            except AssertionError as error:
                record={'case_id':case['case_id'],'stage':number,'error':str(error),'a':a.tolist(),'b':b.tolist(),
                        'observed':[None if not np.isfinite(x) else float(x) for x in observed],
                        'totals':totals.tolist(),'chosen':stage['query'],'diagnostics':stage['diagnostics'],
                        'checked_before_failure':checked}
                (HERE/'randomized_failure.json').write_text(json.dumps(record,indent=2)+'\n')
                print(json.dumps({k:v for k,v in record.items() if k not in ['a','b','observed','totals','diagnostics']}))
                raise SystemExit(1)
            observed[stage['query']]=stage['value'];observed=checker.free_closure(observed,totals);checked+=1
print(json.dumps({'status':'passed','states':checked}))
