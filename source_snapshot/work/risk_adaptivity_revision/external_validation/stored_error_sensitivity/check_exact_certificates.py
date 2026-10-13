"""LP-free exact verification of bounded-error support-policy certificates.

Independently reconstructs the endpoint LP from source coefficients and query
indices. Imports neither the certificate generator nor any numerical solver.
"""
import argparse
from collections import Counter
import csv
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def reconstructed(c, first, seconds, delta):
    dimension = 22*len(seconds)+2
    eta, answer = dimension-2, dimension-1
    objective = [F(-int(j == eta)) for j in range(dimension)]
    inequalities, rhs, equalities = [], [], []
    # Construct sparsely to avoid reusing the producer's array-building code.
    for start in range(0, eta, 11):
        for sign in (1, -1):
            inequalities.append({start+h:F(sign) for h in range(6)})
            rhs.append(F(sign))
    for index, second in enumerate(seconds):
        u, v = 22*index, 22*index+11
        width = {eta:F(1)}
        for hour in range(6):
            width[u+hour] = -c[hour]
            width[v+hour] = c[hour]
        inequalities.append(width); rhs.append(F(0))
        for start in (u, v):
            row = {start+h:F(1) for h in range(first)}
            row[start+6+first-1] = F(1)
            row[answer] = F(-1)
            equalities.append(row)
        row = {}
        for start, sign in ((u,1),(v,-1)):
            for hour in range(second): row[start+hour] = F(sign)
            row[start+6+second-1] = F(sign)
        equalities.append(row)
    dense = lambda rows: [[row.get(j,F(0)) for j in range(dimension)] for row in rows]
    boxes = []
    for j in range(eta):
        boxes.append((F(0),F(1)) if j%11 < 6 else (-delta,delta))
    boxes.extend([(F(0),F(1)),(-delta,F(1)+delta)])
    return objective,dense(inequalities),rhs,dense(equalities),[F(0)]*len(equalities),boxes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'exact_certificates/verification.json')
    args=parser.parse_args();started=time.perf_counter()
    path=HERE/'exact_certificates/certificates.json'
    saved=json.loads(path.read_text());assert saved['schema']=='bounded-error-rational-dual-box-v1'
    ledger_path=HERE/'case_ledger.csv';geom_path=HERE.parent/'replay/geometry.json'
    for name,source in [('case_ledger_sha256',ledger_path),('geometry_sha256',geom_path),('protocol_sha256',HERE/'PROTOCOL.txt')]:
        assert sha(source)==saved['inputs'][name]
    geometry={row['id']:row for row in json.loads(geom_path.read_text())['cases']}
    with ledger_path.open(newline='',encoding='utf-8') as stream: rows=list(csv.DictReader(stream))
    wanted={(row['id'],F(row['delta'])):row for row in rows if F(row['delta'])>0 and row['adaptive_guarantee']=='True'}
    assert Counter(delta for _,delta in wanted)=={F(1,1000):27,F(1,100):22}
    assert len(saved['certificates'])==49
    seen=set();margins=[];maximum_correction=F(0)
    for proof in saved['certificates']:
        delta=F(proof['delta_exact']);key=(proof['id'],delta)
        assert key in wanted and key not in seen;seen.add(key)
        row=wanted[key];first=int(row['best_first_query']);seconds=[int(x) for x in row['sparse_second_queries'].split(';')]
        assert proof['first']==first and proof['seconds']==seconds
        assert first in range(1,6) and 1<=len(seconds)<=2 and len(set(seconds))==len(seconds)
        assert all(q in range(1,6) and q!=first for q in seconds)
        original=[F.from_float(float(v)) for v in geometry[key[0]]['c']]
        scale=max(original)-min(original);assert scale>0
        c=[v/scale for v in original]
        assert original==list(map(F,proof['original_coefficients_exact']))
        assert scale==F(proof['range_exact']) and c==list(map(F,proof['normalized_coefficients_exact']))
        f,A,b,E,h,boxes=reconstructed(c,first,seconds,delta)
        assert f==list(map(F,proof['objective'])) and b==list(map(F,proof['b_ub']))
        assert h==list(map(F,proof['b_eq']))
        assert A==[list(map(F,z)) for z in proof['A_ub']]
        assert E==[list(map(F,z)) for z in proof['A_eq']]
        assert boxes==[tuple(map(F,z)) for z in proof['bounds']]
        lam=list(map(F,proof['inequality_multipliers']));nu=list(map(F,proof['equality_multipliers']))
        assert len(lam)==len(A) and len(nu)==len(E) and all(x<=0 for x in lam)
        r=list(f)
        for weight,vector in [*zip(lam,A),*zip(nu,E)]:
            for j,coefficient in enumerate(vector): r[j]-=weight*coefficient
        assert r==list(map(F,proof['stationarity_residual']))
        linear=sum(x*y for x,y in zip(lam,b))+sum(x*y for x,y in zip(nu,h))
        correction=sum(min(value*lo,value*hi) for value,(lo,hi) in zip(r,boxes))
        upper=-linear-correction
        assert linear==F(proof['row_term_exact'])
        assert correction==F(proof['residual_box_correction_exact'])
        assert upper==F(proof['certified_upper_exact'])
        assert F(proof['threshold_exact'])==F(1,2)
        assert F(1,2)-upper==F(proof['certified_margin_exact'])>0
        assert upper>=0
        margins.append(F(1,2)-upper);maximum_correction=max(maximum_correction,abs(correction))
    assert seen==set(wanted)
    # These checks harden the original numerical diagnostics without changing
    # its frozen producer or using floating residuals to prove the upper bound.
    numerical=json.loads((HERE/'report.json').read_text())
    for value in numerical['max_numerical_residuals'].values():
        assert math.isfinite(value) and 0<=value<=2e-8
    for name in ['max_zero_error_A_discrepancy','max_zero_error_D_discrepancy','max_Helly_support_discrepancy']:
        assert 0<=numerical[name]<=2e-8
    output={'status':'PASS','certificates':49,'by_delta':{'1/1000':27,'1/100':22},
        'matrix_reconstruction':'Independent sparse semantic construction; all exported coefficients/boxes/multipliers checked',
        'arithmetic':'Python Fraction only for certificates; no LP solver imported or run',
        'minimum_margin_exact':str(min(margins)),'minimum_margin':float(min(margins)),
        'maximum_absolute_box_correction':float(maximum_correction),
        'checked_numerical_diagnostics_tolerance':2e-8,
        'scope':'Rigorous support-defined adaptive-policy guarantee at the unchanged threshold; no exact optimum or floating online-branch implementation claim',
        'certificate_sha256':sha(path),'source_sha256':sha(Path(__file__)),
        'seconds':time.perf_counter()-started}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2),flush=True)


if __name__=='__main__': main()
