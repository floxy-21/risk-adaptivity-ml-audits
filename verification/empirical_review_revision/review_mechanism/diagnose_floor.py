"""Distinguish preserved assurance from the continued need for feedback."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);a=p.parse_args()
    rows=json.loads((a.results/'ledger.json').read_text())['rows'];checks=0
    for row in rows:
        previous_fixed=6;previous_adaptive=None;previous_thresholds=None
        for value in row['floors'].values():
            fixed=value['fixed_minimum'];adaptive=value['adaptive_minimum_at_most_two']
            assert fixed<=previous_fixed
            if previous_adaptive is not None:assert adaptive is not None and adaptive<=previous_adaptive
            previous_fixed,previous_adaptive=fixed,adaptive;checks+=1
    summaries={}
    for name in ['all','original','external']+sorted({r['cohort']+'/'+r['system'] for r in rows}):
        subset=[r for r in rows if r['baseline_saving'] and (name=='all' or r['cohort']==name or r['cohort']+'/'+r['system']==name)]
        byfloor={}
        for factor in rows[0]['floors']:
            given=[r['floors'][factor] for r in subset]
            assert all(v['adaptive_minimum_at_most_two'] is not None and v['adaptive_minimum_at_most_two']<=2 for v in given)
            byfloor[factor]={'original_saving_cohort':len(given),'assured_with_at_most_two':len(given),
              'still_need_feedback':sum(v['saving'] for v in given),
              'fixed_suffices':sum(v['fixed_minimum']<=2 for v in given),
              'fixed_minimum_budget_histogram':dict(sorted(Counter(v['fixed_minimum'] for v in given).items())),
              'best_identified_adaptive_minimum_budget_histogram':dict(sorted(Counter(v['adaptive_minimum_at_most_two'] for v in given).items()))}
        summaries[name]=byfloor
    out={'status':'PASS','ledger_sha256':sha(a.results/'ledger.json'),'checker_sha256':sha(__file__),
      'monotonic_budget_checks':checks,'summaries':summaries,
      'interpretation':'The absolute floor relaxes each precision constraint. Every original adaptive guarantee remains valid. Cases moving to fixed budgets zero, one or two require less acquisition; they are not adaptive-certificate failures.',
      'unit_identity':'Initial paired six-hour MSE width = retained block energy(kWh) times range of 2*(b-a)/6(kWh). Floor = factor times training mean squared hourly energy(kWh^2).'}
    (a.results/'floor_assurance_diagnostic.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','primary_external':summaries['external']['1/100'],'primary_all':summaries['all']['1/100']},indent=2))
if __name__=='__main__':main()
