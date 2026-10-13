"""Expose the original MSE scale of the existing worked shared-query example.

No policy, precision threshold, forecasts or observations are changed. Values
refer to stored API-grid cumulative-kWh differences, not independently verified
physical clock-hour energy. Independent endpoint LPs check the six exact ranges.
"""
import argparse,csv,hashlib,json
from datetime import datetime,timezone
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE.parents[1]
CASE='external/hpm_1/2025-07-05/12'
MODELS=['daily','hist_gradient_boosting','mlp','ridge']
LABELS={'daily':'Daily','hist_gradient_boosting':'Boosting','mlp':'MLP','ridge':'Ridge'}

def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def interval(c,d,y,q):
    lo=hi=d;cuts=[0,*sorted(q),6]
    for a,b in zip(cuts,cuts[1:]):
        total=sum(y[a:b]);lo+=total*min(c[a:b]);hi+=total*max(c[a:b])
    return lo,hi
def lp_endpoints(c,d,energy,prefix,q):
    equalities=[np.ones(6)]+[np.r_[np.ones(k),np.zeros(6-k)] for k in q]
    rhs=[float(energy)]+[float(prefix[k]) for k in q]
    bounds=[]
    for sign in [1,-1]:
        r=linprog(sign*np.array(list(map(float,c))),A_eq=equalities,b_eq=rhs,bounds=[(0,None)]*6,
                  method='highs',options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
        assert r.success,r.message;bounds.append(float(d)+sign*r.fun)
    return bounds

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=HERE/'absolute_width_results');a=p.parse_args()
    paths={'geometry':BASE/'external_validation/replay/geometry.json',
           'plans':HERE/'empirical_external_results/empirical_plans.json',
           'ledger':HERE/'empirical_external_results/empirical_cases.csv',
           'forecasts':BASE/'external_validation/operational/fresh_fits_20261012/frozen_forecasts.csv',
           'counters':BASE/'external_heatpump/hourly/train_test_hourly_counters.csv',
           'raw_provider':BASE/'external_heatpump/hourly/system_1_test_2025July.json'}
    plans=read(paths['plans']);assert plans['inputs']['external']['sha256']==sha(paths['geometry'])
    plan=next(r for r in plans['plans'] if r['id']==CASE)
    geometry={r['id']:r for r in read(paths['geometry'])['cases']}
    cases=[geometry[k] for k in plan['pair_case_ids']];assert len(cases)==6
    with paths['ledger'].open(newline='',encoding='utf8') as f:ledger=next(r for r in csv.DictReader(f) if r['id']==CASE)
    with paths['forecasts'].open(newline='',encoding='utf8') as f:
        forecasts=[r for r in csv.DictReader(f) if r['system_id']=='1' and r['timestamp_utc'][:10]=='2025-07-05' and 12<=int(r['timestamp_utc'][11:13])<18]
    forecasts.sort(key=lambda r:r['timestamp_utc']);assert len(forecasts)==6
    with paths['counters'].open(newline='',encoding='utf8') as f:
        counters=[r for r in csv.DictReader(f) if r['system_id']=='1' and r['timestamp_utc'][:10]=='2025-07-05' and 12<=int(r['timestamp_utc'][11:13])<=18]
    counters.sort(key=lambda r:r['timestamp_utc']);assert len(counters)==7
    raw=json.loads(paths['raw_provider'].read_text(),parse_float=Decimal)['heatpump_elec_kwh']
    for r in counters:
        assert r['unit']=='kWh' and r['valid']=='1'
        token=raw[int(r['raw_row_index'])]
        assert F(token[1])==F(r['counter_kwh'])
        assert datetime.fromtimestamp(int(token[0]),timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')==r['timestamp_utc']
    C=[F(r['counter_kwh']) for r in counters];prefix=[v-C[0] for v in C];y=[b-a for a,b in zip(C,C[1:])]
    E=C[-1]-C[0];assert E==F(471,256) and min(y)>=0
    first=int(ledger['adaptive_first']);second=int(ledger['adaptive_second']);assert first==plan['geometry']['first_query']==2 and second==1
    rows=[];max_lp=0.0;max_coef_roundoff=F(0);max_direct_gap=F(0);direct_calls=0
    for case in cases:
        ma,mb=case['model_a'],case['model_b'];af=[float(r[ma]) for r in forecasts];bf=[float(r[mb]) for r in forecasts]
        assert af==case['forecast_a'] and bf==case['forecast_b']
        expected=[2*(b-a)/6 for a,b in zip(af,bf)];assert expected==case['c']
        c=list(map(F.from_float,case['c']));d=F.from_float(case['d'])
        exact_c=[(F.from_float(b)-F.from_float(a))/3 for a,b in zip(af,bf)]
        max_coef_roundoff=max(max_coef_roundoff,max(abs(x-z) for x,z in zip(c,exact_c)))
        W0=E*(max(c)-min(c));assert W0==F(case['W0_exact'])
        initial=interval(c,d,y,[]);terminal=interval(c,d,y,[first,second]);width=terminal[1]-terminal[0]
        for q,correct in [([],initial),([first,second],terminal)]:
            solved=lp_endpoints(c,d,E,prefix,q);direct_calls+=2
            max_lp=max(max_lp,max(abs(float(exact)-value) for exact,value in zip(correct,solved)))
        mse_a=sum((F.from_float(p)-v)**2 for p,v in zip(af,y))/6
        mse_b=sum((F.from_float(p)-v)**2 for p,v in zip(bf,y))/6
        reference=mse_a-mse_b;affine=d+sum(ci*yi for ci,yi in zip(c,y))
        max_direct_gap=max(max_direct_gap,abs(reference-affine))
        assert terminal[0]-F(1,10**12)<=reference<=terminal[1]+F(1,10**12)
        rows.append({'model_a':ma,'model_b':mb,'initial_width_kwh2':float(W0),'half_threshold_kwh2':float(W0/2),
                     'terminal_width_kwh2':float(width),'normalized_terminal_width':float(width/W0),
                     'initial_width_exact':str(W0),'half_threshold_exact':str(W0/2),'terminal_width_exact':str(width),
                     'initial_interval_exact':list(map(str,initial)),'terminal_interval_exact':list(map(str,terminal)),
                     'actual_mse_a_kwh2':float(mse_a),'actual_mse_b_kwh2':float(mse_b),
                     'actual_mse_difference_kwh2':float(reference),'recorded_half_success':width<=W0/2})
    assert max_lp<1e-10 and max_direct_gap<F(1,10**12)
    joint=max(r['normalized_terminal_width'] for r in rows)
    assert abs(joint-float(ledger['adaptive_recorded_J']))<1e-12
    # Verify the frozen second action from exact conditional joint ranges.
    conditional={}
    for j in [1,3,4,5]:
        values=[]
        for case in cases:
            c=list(map(F.from_float,case['c']));span=lambda lo,hi:max(c[lo:hi])-min(c[lo:hi]);ran=span(0,6)
            if j<first:alpha,beta=max(span(0,j),span(j,first)),span(first,6)
            else:alpha,beta=span(0,first),max(span(first,j),span(j,6))
            values.append((alpha*prefix[first]+beta*(E-prefix[first]))/(E*ran))
        conditional[j]=max(values)
    assert min(conditional,key=lambda j:(conditional[j],j))==second
    out=a.output_dir;out.mkdir(parents=True,exist_ok=True)
    report={'status':'PASS','scope':__doc__,'case':CASE,'selection':'Same pre-existing worked exact-half certificate, not a new representative-outcome sample',
            'loss_denominator':6,'counter_units':'kWh','loss_units':'kWh^2','E_exact':str(E),'E_kwh':float(E),
            'initial_counter_kwh_exact':str(C[0]),'final_counter_kwh_exact':str(C[-1]),'query_boundaries':[first,second],
            'query_grid_times_utc':[counters[k]['timestamp_utc'] for k in [first,second]],'observed_prefix_energy_exact':[str(prefix[k]) for k in [first,second]],
            'original_forecast_coefficients':'c_h = 2(b_h-a_h)/6; stored binary64 coefficient convention retained',
            'independent_endpoint_LPs':direct_calls,'maximum_endpoint_LP_discrepancy_kwh2':max_lp,
            'maximum_coefficient_binary64_roundoff':float(max_coef_roundoff),
            'maximum_direct_MSE_vs_stored_affine_gap_kwh2':float(max_direct_gap),
            'recorded_J':joint,'all_six_half_success':all(r['recorded_half_success'] for r in rows),'pairs':rows,
            'initial_information':'Only exact retained endpoint total and fixed forecasts; no optional internal value used to form W0 or its half-threshold',
            'interpretation':'Absolute stored-record audit precision; no financial/materiality threshold, device calibration, native-time accuracy, or winner guarantee inferred',
            'inputs':{k:{'path':v.relative_to(ROOT).as_posix(),'sha256':sha(v)} for k,v in paths.items()},'source_sha256':sha(Path(__file__))}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    with (out/'absolute_widths.csv').open('w',newline='',encoding='utf8') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
    tex=[r'\begin{table}[htbp]',r'\centering\small',r'\begin{tabular}{lrrrr}',r'\toprule',
         r'Model contrast & Initial $W_{r,0}$ & Target $W_{r,0}/2$ & Terminal $W_r$ & $W_r/W_{r,0}$\\',r'\midrule']
    for r in rows:
        tex.append(f"{LABELS[r['model_a']]}--{LABELS[r['model_b']]} & {r['initial_width_kwh2']:.6f} & {r['half_threshold_kwh2']:.6f} & {r['terminal_width_kwh2']:.6f} & {r['normalized_terminal_width']:.4f}"+r'\\')
    tex += [r'\bottomrule',r'\end{tabular}',r'\caption{Original loss scale for the existing HPM~1 worked example on 5 July 2025, 12:00--18:00 UTC. The first three numeric columns have units $\mathrm{kWh}^2$: they are widths and width targets for identification intervals of six-target MSE differences on stored API-grid increments. The retained endpoint difference is $E=1.83984375$ kWh. The unchanged adaptive policy retrieves the 14:00 register and then the 13:00 register. Normalization uses the initial width of each contrast, not a common numerical loss scale.}',r'\label{tab:absolute_joint_widths}',r'\end{table}']
    (out/'main_table.tex').write_text('\n'.join(tex)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['pairs','inputs']},indent=2))

if __name__=='__main__':main()
