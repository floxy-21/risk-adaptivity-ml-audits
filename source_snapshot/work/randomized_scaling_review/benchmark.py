"""Frozen, isolated scaling measurements; never modifies the research APIs."""
from pathlib import Path
import os, sys, json, csv, time, math, hashlib, subprocess, ctypes, traceback, platform
from ctypes import wintypes
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
API=ROOT/'work'/'randomized_recovery_root'
CAP=1024**3
TIMEOUT=20.

class PMC(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
              ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
              ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
              ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
              ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
def memory(pid=None):
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    p=ctypes.WinDLL('psapi',use_last_error=True)
    k.GetCurrentProcess.restype=wintypes.HANDLE
    k.OpenProcess.restype=wintypes.HANDLE
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    p.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD]
    h=k.GetCurrentProcess() if pid is None else k.OpenProcess(0x410,False,pid)
    if not h:return {'current':0,'peak':0}
    data=PMC();data.cb=ctypes.sizeof(data)
    ok=p.GetProcessMemoryInfo(h,ctypes.byref(data),data.cb)
    if pid is not None:k.CloseHandle(h)
    return {'current':int(data.WorkingSetSize),'peak':int(data.PeakWorkingSetSize)} if ok else {'current':0,'peak':0}

def counts(sizes,budget):
    q=min(budget,sum(m-1 for m in sizes));dp=[0]*(q+1);dp[0]=1;product=1
    for m in sizes:
        local=[math.comb(m,k) for k in range(min(q,m-1)+1)]
        product*=sum(local)
        dp=[sum(dp[b-k]*local[k] for k in range(min(b,len(local)-1)+1)) for b in range(q+1)]
    return dp[q],product

def freeze():
    import numpy as np
    if (HERE/'instances.json').exists():raise RuntimeError('Refuse to overwrite frozen instances')
    specs=[(g,m,f,p) for g in (1,2,4) for m in (6,12) for f in (.25,.5) for p in (0,1)]
    specs += [(1,m,.5,p) for m in (24,48) for p in (0,1)]
    cases=[]
    for idx,(g,m,f,p) in enumerate(specs):
        rng=np.random.default_rng(20261010+1000*g+10*m+p)
        base=np.sort(rng.uniform(-1,1,m)) if p==0 else np.repeat(np.linspace(-1,1,m//3),3)
        coeff=[(base[rng.permutation(m)]*(2.**j if p else 1.)).tolist() for j in range(g)]
        energies=(np.geomspace(.1,10,g) if p and g>1 else np.ones(g)).tolist()
        b=math.floor(g*m*f);batches,candidateproduct=counts([m]*g,b)
        cases.append(dict(case=f'C{idx+1:02}',blocks=g,coordinates_per_block=m,
                          total_coordinates=g*m,budget=b,query_fraction=b/(g*m),
                          retained_fraction=1-b/(g*m),profile='tied-heterogeneous' if p else 'distinct-homogeneous',
                          coefficients=coeff,energies=energies,batches=batches,candidate_product=candidateproduct,
                          enumerated_eligible=batches<=25000 and candidateproduct<=100000))
    doc=dict(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
             protocol_sha256=hashlib.sha256((HERE/'protocol.txt').read_bytes()).hexdigest(),
             api_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [API/'compact_randomized.py',API/'compact_policy.py']},cases=cases)
    (HERE/'instances.json').write_text(json.dumps(doc,indent=2),encoding='utf-8')
    print(json.dumps({'cases':len(cases),'enumerated_eligible':sum(c['enumerated_eligible'] for c in cases),'manifest_sha256':hashlib.sha256((HERE/'instances.json').read_bytes()).hexdigest()}),flush=True)

def worker(index,method,out):
    start_all=time.perf_counter()
    import numpy as np, scipy
    sys.path.insert(0,str(API));import compact_randomized as cr;import compact_policy as cp
    case=json.loads((HERE/'instances.json').read_text())['cases'][index]
    captured=[];original=cr.linprog
    def wrapped(c,*args,**kw):
        opts=dict(kw.get('options',{}));opts.update(threads=1);kw['options']=opts
        s=time.perf_counter();res=original(c,*args,**kw);solve_seconds=time.perf_counter()-s
        checkstart=time.perf_counter()
        c=np.asarray(c);ae=kw['A_eq'];au=kw['A_ub'];be=np.asarray(kw['b_eq']);bu=np.asarray(kw['b_ub'])
        detail=dict(solver_seconds=solve_seconds,solver_success=bool(res.success),solver_status=int(res.status),solver_message=str(res.message),
                    variables=len(c),equalities=len(be),inequalities=len(bu),nonzeros=int((ae.nnz if hasattr(ae,'nnz') else np.count_nonzero(ae))+(au.nnz if hasattr(au,'nnz') else np.count_nonzero(au))))
        if res.success:
            x=res.x;ye=res.eqlin.marginals;yu=res.ineqlin.marginals;lo=res.lower.marginals
            eqerr=ae@x-be;slack=bu-au@x
            primal=max(np.max(np.abs(eqerr),initial=0),np.max(-slack,initial=0),np.max(-x,initial=0),0.)
            dual=max(np.max(yu,initial=0),np.max(-lo,initial=0),0.)
            station=float(np.max(np.abs(c-ae.T@ye-au.T@yu-lo),initial=0))
            dualobj=float(be@ye+bu@yu);gap=abs(float(res.fun)-dualobj)
            pscale=max(1.,float(np.max(np.abs(be),initial=0)),float(np.max(np.abs(bu),initial=0)))
            dscale=max(1.,float(np.max(np.abs(c),initial=0)))
            detail.update(primal_absolute=float(primal),primal_normalized=float(primal/pscale),dual_absolute=float(dual),dual_normalized=float(dual/dscale),stationarity_absolute=station,stationarity_normalized=station/dscale,duality_gap_absolute=gap,duality_gap_normalized=gap/max(1.,abs(float(res.fun))),dual_objective=dualobj)
        detail['diagnostic_seconds']=time.perf_counter()-checkstart;captured.append(detail);return res
    cr.linprog=wrapped
    imported=time.perf_counter();baseline=memory()
    result=dict(case=case['case'],method=method,status='error',baseline_working_set_bytes=baseline['current'],import_seconds=imported-start_all,versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__))
    try:
        begin=time.perf_counter()
        if method=='compact':
            policy=cp.solve_policy(case['coefficients'],case['energies'],case['budget'])
            end=time.perf_counter();result.update(value=policy.worst_expected_width,lp_value=policy.lp_value,policy_diagnostics=policy.diagnostics)
            rng=np.random.default_rng(90100+index)
            for _ in range(20):
                batch=policy.sample(rng)
                assert sum(map(len,batch))==policy.query_count<=case['budget']
                assert all(len(set(q))==len(q) and all(0<=i<len(c) for i in q) for q,c in zip(batch,case['coefficients']))
            result['sample_checks']=20
        else:
            raw=cr.solve_enumerated(case['coefficients'],case['energies'],case['budget']);end=time.perf_counter();result.update(raw)
        elapsed=end-begin
        result.update(status='success',instrumented_method_seconds=elapsed,method_seconds=elapsed-sum(d['diagnostic_seconds'] for d in captured))
    except BaseException as exc:
        result.update(error=repr(exc),traceback=traceback.format_exc())
    result['lp_checks']=captured;result['peak_working_set_bytes']=memory()['peak'];result['total_worker_seconds']=time.perf_counter()-start_all
    Path(out).write_text(json.dumps(result,indent=2),encoding='utf-8')

def run():
    manifest=json.loads((HERE/'instances.json').read_text());rows=[]
    env=os.environ.copy()
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):env[key]='1'
    env['PYTHONDONTWRITEBYTECODE']='1'
    for index,case in enumerate(manifest['cases']):
        for method in ('compact','enumerated'):
            row={k:v for k,v in case.items() if k not in ('coefficients','energies')};row['method']=method
            if method=='enumerated' and not case['enumerated_eligible']:
                row.update(status='not_attempted_by_frozen_size_rule');rows.append(row);continue
            out=HERE/f"{case['case']}_{method}.json";log=HERE/f"{case['case']}_{method}.log"
            if out.exists():raise RuntimeError('Refuse to replace prior measurement '+str(out))
            begin=time.perf_counter();peak=0;reason=None
            with log.open('w',encoding='utf-8') as stream:
                proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker',str(index),method,str(out)],stdout=stream,stderr=stream,env=env,cwd=HERE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                while proc.poll() is None:
                    mem=memory(proc.pid);peak=max(peak,mem['peak'])
                    if mem['current']>CAP:reason='memory_cap';proc.kill();break
                    if time.perf_counter()-begin>TIMEOUT:reason='timeout';proc.kill();break
                    time.sleep(.05)
                proc.wait()
            row.update(parent_wall_seconds=time.perf_counter()-begin,parent_observed_peak_bytes=peak,exit_code=proc.returncode)
            if reason:row.update(status=reason)
            elif out.exists():row.update(json.loads(out.read_text()))
            else:row.update(status='worker_failed_without_result')
            rows.append(row)
            (HERE/'results.json').write_text(json.dumps({'manifest':{k:v for k,v in manifest.items() if k!='cases'},'rows':rows},indent=2),encoding='utf-8')
            print(f"{case['case']} {method} {row['status']} {row['parent_wall_seconds']:.3f}s peak {max(peak,row.get('peak_working_set_bytes',0))/2**20:.1f}MiB",flush=True)
    (HERE/'results.json').write_text(json.dumps({'manifest':{k:v for k,v in manifest.items() if k!='cases'},'rows':rows},indent=2),encoding='utf-8')
    summarize()

def summarize():
    data=json.loads((HERE/'results.json').read_text());rows=data['rows'];cases=json.loads((HERE/'instances.json').read_text())['cases']
    lookup={(r['case'],r['method']):r for r in rows};compared=[]
    fields=['case','method','blocks','coordinates_per_block','total_coordinates','budget','retained_fraction','profile','batches','candidate_product','status','variables','equalities','inequalities','nonzeros','value','method_seconds','solver_seconds','parent_wall_seconds','peak_working_set_mib','primal_normalized','dual_normalized','stationarity_normalized','duality_gap_normalized','finite_objective_discrepancy_normalized']
    for case in cases:
        a=lookup.get((case['case'],'compact'),{});b=lookup.get((case['case'],'enumerated'),{})
        if a.get('status')==b.get('status')=='success':
            scale=max(1.,sum(e*(max(c)-min(c)) for e,c in zip(case['energies'],case['coefficients'])))
            err=abs(a['value']-b['value'])/scale;compared.append(err)
            a['finite_objective_discrepancy_normalized']=b['finite_objective_discrepancy_normalized']=err
    flat=[]
    for row in rows:
        r=row.copy()
        if r.get('lp_checks'):r.update(r['lp_checks'][0])
        r['peak_working_set_mib']=max(r.get('peak_working_set_bytes',0),r.get('parent_observed_peak_bytes',0))/2**20
        flat.append({k:r.get(k,'') for k in fields})
    with (HERE/'results.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(flat)
    success=[r for r in rows if r['method']=='compact' and r['status']=='success']
    summary={'cases':len(cases),'compact_successes':len(success),'compact_failures':[{'case':r['case'],'status':r['status']} for r in rows if r['method']=='compact' and r['status']!='success'],
             'finite_comparisons':len(compared),'max_finite_discrepancy_normalized':max(compared,default=None),
             'maxima':{k:max((r['lp_checks'][0][k] for r in success),default=None) for k in ['primal_normalized','dual_normalized','stationarity_normalized','duality_gap_normalized']},
             'method_seconds_range':[min(r['method_seconds'] for r in success),max(r['method_seconds'] for r in success)],
             'peak_mib_range':[min(r['peak_working_set_bytes']/2**20 for r in success),max(r['peak_working_set_bytes']/2**20 for r in success)],
             'host':{'platform':platform.platform(),'processor':platform.processor()},'single_run':True}
    summary['numerical_checks_pass']=all(v<=1e-7 for v in summary['maxima'].values()) and all(v<=1e-7 for v in compared)
    (HERE/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='freeze':freeze()
    elif mode=='worker':worker(int(sys.argv[2]),sys.argv[3],sys.argv[4])
    elif mode=='run':run()
    elif mode=='summarize':summarize()
