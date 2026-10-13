"""Check bundled counter ledgers/reports; raw-source replay is separate."""
from fractions import Fraction
from pathlib import Path
import argparse,json
import pandas as pd

HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=json.loads((HERE/'summary/report.json').read_text())
    l=pd.read_csv(HERE/'summary/certificate_ledger.csv')
    assert len(l)==4914*5 and l.id.nunique()==4914
    primary=l[l.fraction==.5]; assert len(primary)==4914
    assert primary.adaptive_guarantee.sum()==4661
    assert primary.strong_separation.sum()==290
    assert (primary.loc[primary.strong_separation,'batch_upper']<=.5).all()
    for name in ['meter','model_a','model_b']:
        assert primary[name].notna().all()
    assert not r['screening_all_met'] and not r['screening_criteria']['at_least_10_percent_strong']
    allp=pd.read_csv(HERE/'summary/all_policy_summary.csv').set_index('policy')
    sub=pd.read_csv(HERE/'summary/separation_policy_summary.csv').set_index('policy')
    assert abs(allp.loc['adaptive','success_0.5']-4847/4914)<1e-12
    assert abs(sub.loc['adaptive','success_0.5']-1)<1e-12
    assert abs(sub.loc['det_batch','success_0.5']-282/290)<1e-12
    ids=set(); strong=guarantees=0
    for phase in ['pilot','continuation']:
        v=json.loads((HERE/f'math_review/{phase}_verification.json').read_text())
        raw=json.loads((HERE/f'math_review/{phase}_replay_verification.json').read_text())
        assert v['status']=='PASS' and raw['status']=='PASS'
        for w in v['primary_exact_witnesses']:
            assert w['id'] not in ids;ids.add(w['id'])
            weights=[Fraction(x) for x in w['weights_exact']]
            assert min(weights)>=0 and sum(weights)==1
            aa=Fraction(w['A_exact_original_coefficients']); uu=Fraction(w['adverse_upper_exact_original_coefficients'])
            claimed=primary[primary.id==w['id']].iloc[0]
            if claimed.adaptive_guarantee:
                assert aa<=Fraction(1,2);guarantees+=1
            if claimed.strong_separation:
                assert aa<=Fraction(1,2) and uu<=Fraction(1,2);strong+=1
    assert len(ids)==4914 and (guarantees,strong)==(4661,290)
    half=json.loads((HERE/'math_review/half_cover_verification.json').read_text())
    dist=json.loads((HERE/'summary/batch_bound_distribution.json').read_text())
    assert half['status']=='PASS' and half['strong_cases']==dist['cases']==290
    assert dist['exactly_half']==290 and dist['below_40pct']==dist['below_30pct']==0
    seen=set()
    for w in half['cover_witnesses']:
        assert w['id'] in ids and w['id'] not in seen;seen.add(w['id'])
        assert w['batch_optimum_exact']=='1/2' and w['probabilities']==['1/2','1/2']
        prefix,suffix=w['cover_intervals']
        assert Fraction(prefix['left'])==0 and Fraction(suffix['right'])==1
        assert Fraction(prefix['right'])>=Fraction(suffix['left'])
        for z in (prefix,suffix):
            aa,bb=Fraction(z['alpha']),Fraction(z['beta'])
            for x in (Fraction(z['left']),Fraction(z['right'])):
                assert 0<=x<=1 and aa*x+bb*(1-x)<=Fraction(1,2)
    assert len(seen)==290
    report={'status':'PASS','tasks':4914,'ledger_rows':len(l),'primary_guarantees':guarantees,'primary_strong':strong,'exact_half_cover_witnesses':len(seen),'screening_prevalence_met':False,'scope':'Bundled report/ledger/table consistency, rational witness masses and covering-interval algebra. Does not reopen raw registers or recompute original-coefficient envelopes. Use reproduce_counter.py and check_half_cover.py for those fresh checks.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
