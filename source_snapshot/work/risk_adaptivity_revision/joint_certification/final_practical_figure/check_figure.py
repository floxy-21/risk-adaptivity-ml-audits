"""Independent standard-library check of plotted exact geometry and replay points."""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import argparse
import csv
import hashlib
import json

HERE=Path(__file__).resolve().parent
JC=HERE.parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read_curve(points):
    points=[tuple(map(F,p)) for p in points]
    if points[0][0]!=0 or points[-1][0]!=1 or any(a[0]>=b[0] for a,b in zip(points,points[1:])):
        raise AssertionError('Curve does not partition [0,1]')
    return points


def interpolate(curve,t):
    for (x,a),(z,b) in zip(curve,curve[1:]):
        if x<=t<=z:return a+(b-a)*(t-x)/(z-x)
    raise AssertionError('Point outside figure curve')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=HERE/'independent_check.json')
    args=parser.parse_args()
    data=json.loads((HERE/'figure_data.json').read_text())
    for name,expected in data['input_sha256'].items():
        if digest(JC/name)!=expected:raise AssertionError('Source input changed: '+name)
    plan_data=json.loads((JC/'precision_external_results/plans.json').read_text())
    plan=next(r for r in plan_data['plans'] if r['id']==data['case'])
    source_cases={}
    for path,expected in plan_data['source_hashes'].items():
        pp=JC.parent/path.replace('\\','/')
        if digest(pp)!=expected:raise AssertionError('Frozen geometry changed')
        source_cases.update({r['id']:r for r in json.loads(pp.read_text())['cases']})
    C=[]
    for key in plan['pair_case_ids']:
        raw=[F.from_float(x) for x in source_cases[key]['c']]
        lo,hi=min(raw),max(raw)
        C.append([(v-lo)/(hi-lo) for v in raw])
    if [[str(x) for x in r] for r in C]!=data['normalized_coefficients_exact']:
        raise AssertionError('Plotted coefficients differ from frozen source')
    # Reconstruct conditional coefficients by distributing unit prefix/suffix
    # mass into all final segments. No producer/helper imports are used.
    lines={}
    for second in [1,3,4,5]:
        segments=list(zip([0,*sorted([2,second])],[*sorted([2,second]),6]))
        current=[]
        for c in C:
            widths=[max(c[a:b])-min(c[a:b]) for a,b in segments]
            left=max(w for (a,b),w in zip(segments,widths) if b<=2)
            right=max(w for (a,b),w in zip(segments,widths) if a>=2)
            current.append((left-right,right))
        lines[second]=current
        if [[str(x) for x in r] for r in current]!=data['conditional_lines_exact'][str(second)]:
            raise AssertionError('Conditional line mismatch')
    all_lines=[line for rows in lines.values() for line in rows]
    points={F(0),F(1)}
    for (a,b),(c,d) in combinations(all_lines,2):
        if a!=c:
            t=(d-b)/(a-c)
            if 0<=t<=1:points.add(t)
    curves={int(j):read_curve(ps) for j,ps in data['curves_exact'].items()}
    adaptive=read_curve(data['adaptive_curve_exact'])
    points.update(t for ps in [*curves.values(),adaptive] for t,w in ps)
    checks=0;maximum=F(0)
    for t in sorted(points):
        conditional={j:max(a*t+b for a,b in ls) for j,ls in lines.items()}
        for j,width in conditional.items():
            if interpolate(curves[j],t)!=width:raise AssertionError('Plotted successor envelope mismatch')
            checks+=1
        value=min(conditional.values())
        if interpolate(adaptive,t)!=value:raise AssertionError('Plotted adaptive envelope mismatch')
        maximum=max(maximum,value);checks+=1
    theta=F(data['exact_switch'])
    witness=json.loads((JC/'main_inspectable_certificate_check.json').read_text())
    if theta!=F(witness['exact_switch']) or maximum!=F(data['exact_maximum']) or maximum>=F(1,2):
        raise AssertionError('Switch/maximum disagrees with checked certificate')
    if max(a*theta+b for a,b in lines[1])!=maximum or max(a*theta+b for a,b in lines[4])!=maximum:
        raise AssertionError('Switch is not the selected-envelope maximum')
    table=list(csv.DictReader((JC/'review_sensitivity/results/threshold_summary.csv').open(newline='',encoding='utf8')))
    replay_checks=0
    for cohort,policies in data['replay_percent_exact'].items():
        for policy,curve in policies.items():
            for tau,y in curve:
                rows=[r for r in table if r['cohort']==cohort and r['meter']=='ALL' and F(r['threshold'])==F(tau) and r['baseline']==('fixed' if policy=='adaptive' else policy)]
                if len(rows)!=1:raise AssertionError('Missing unique source replay row')
                row=rows[0];field='adaptive_success_count' if policy=='adaptive' else 'baseline_success_count'
                expected=100*F(row[field])/int(row['blocks'])
                if F(y)!=expected:raise AssertionError('Plotted percentage differs from integer case counts')
                replay_checks+=1
    if replay_checks!=30:raise AssertionError('Incomplete policy/threshold/source figure')
    result={'status':'PASS','case':data['case'],'source_contrasts_checked':6,
            'conditional_lines_checked':24,'exact_envelope_points_checked':len(points),
            'envelope_equalities':checks,'replay_points_checked':replay_checks,
            'exact_switch':str(theta),'exact_maximum':str(maximum),
            'source_sha256':digest(Path(__file__)),'figure_data_sha256':digest(HERE/'figure_data.json'),
            'scope':'Exact reconstruction of plotted geometry and integer-count replay percentages; not new observations or optimization.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
