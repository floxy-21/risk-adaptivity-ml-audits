"""Smoke-check the new-cohort oracle driver on already-used development cases."""
from pathlib import Path
import json
import subprocess
import sys
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=ROOT/'work/external_deadline/validation/trajectories.jsonl'


def main():
    fixture=HERE/'smoke_fixture';fixture.mkdir(exist_ok=False)
    records=[]
    with SOURCE.open() as stream:
        for _ in range(120):records.append(json.loads(next(stream)))
    ids={x['case_id'] for x in records}
    with (fixture/'source_cases.jsonl').open('w') as out:
        for row in records:out.write(json.dumps(row,separators=(',',':'))+'\n')
    rows=pd.read_csv(ROOT/'work/decision_revision/prototype/full/cases.csv')
    rows[rows.case_id.isin(ids)].to_csv(fixture/'cases.csv',index=False,float_format='%.17g')
    (fixture/'run_result.json').write_text(json.dumps({'status':'passed','scope':'Synthetic wrapper of 120 previously used DEVELOPMENT cases only; not new confirmation.'})+'\n')
    subprocess.run([sys.executable,str(HERE/'confirmation_oracle.py'),'--run-dir',str(fixture),
                    '--reference',str(ROOT/'work/external_deadline/fitted/reference_targets.csv'),
                    '--reference-period','validation','--output-dir',str(HERE/'smoke_oracle')],check=True)
    result=pd.read_csv(HERE/'smoke_oracle/cases.csv')
    original=pd.read_csv(HERE/'cases.csv')
    paired=result.merge(original,on='case_id',suffixes=('_new','_old'),validate='one_to_one')
    assert len(paired)==120
    assert (paired.oracle_minimum_requests_new==paired.oracle_minimum_requests_old).all()
    report={'status':'passed','development_cases':120,'oracle_minima_match_previous_independent_enumeration':True,
            'new_confirmation_cases_read':0}
    (HERE/'smoke_check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
