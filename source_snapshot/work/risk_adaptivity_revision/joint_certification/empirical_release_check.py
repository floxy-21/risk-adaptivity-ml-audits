"""Compare fresh shared-budget scientific ledgers with frozen release ledgers."""
import argparse,csv,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent

def equivalent(a,b,path='root'):
    if type(a)!=type(b):raise AssertionError((path,'type',type(a).__name__,type(b).__name__))
    if isinstance(a,dict):
        assert a.keys()==b.keys(),path
        for k in a:equivalent(a[k],b[k],path+'.'+k)
    elif isinstance(a,list):
        assert len(a)==len(b),path
        for i,(x,y) in enumerate(zip(a,b)):equivalent(x,y,f'{path}[{i}]')
    elif isinstance(a,float):assert math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-10),(path,a,b)
    else:assert a==b,(path,a,b)

def csv_equal(old,new):
    with old.open(newline='',encoding='utf8') as f:original=list(csv.reader(f))
    with new.open(newline='',encoding='utf8') as f:fresh=list(csv.reader(f))
    assert len(original)==len(fresh) and original[0]==fresh[0]
    for i,(a,b) in enumerate(zip(original[1:],fresh[1:]),1):
        assert len(a)==len(b)
        for j,(x,y) in enumerate(zip(a,b)):
            if x==y:continue
            try:p,q=float(x),float(y)
            except ValueError:raise AssertionError((str(old),i,j,x,y))
            assert math.isfinite(p) and math.isfinite(q) and math.isclose(p,q,rel_tol=1e-8,abs_tol=1e-10),(str(old),i,j,x,y)
    return len(original)-1

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exact-dir',type=Path,required=True);p.add_argument('--capacity-dir',type=Path,required=True)
    p.add_argument('--noise-dir',type=Path,required=True);p.add_argument('--capacity-noise-dir',type=Path)
    p.add_argument('--precision-dir',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();counts={}
    counts['exact']=csv_equal(HERE/'empirical_external_results/empirical_cases.csv',a.exact_dir/'empirical_cases.csv')
    counts['capacity']=csv_equal(HERE/'empirical_external_capacity_results/empirical_capacity_cases.csv',a.capacity_dir/'empirical_capacity_cases.csv')
    for label,folder,frozen in [('noise',a.noise_dir,'empirical_noise_results'),('capacity_noise',a.capacity_noise_dir,'empirical_capacity_noise_results')]:
        if folder is None:continue
        old=json.loads((HERE/frozen/'empirical_noise_cases.json').read_text());new=json.loads((folder/'empirical_noise_cases.json').read_text())
        equivalent(old,new,label);counts[label]=len(old)
    if a.precision_dir is not None:
        old=json.loads((HERE/'empirical_precision_results/cases.json').read_text());new=json.loads((a.precision_dir/'cases.json').read_text())
        equivalent(old,new,'precision');counts['precision']=len(old)
    result={'status':'PASS','scientific_case_rows_matched':counts,'relative_tolerance':1e-8,'absolute_tolerance':1e-10,
            'scope':'Case-by-case fresh versus frozen scientific outputs; timing, paths and report provenance metadata are not compared'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
