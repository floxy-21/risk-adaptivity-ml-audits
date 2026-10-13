"""Validate archived scaling records; --rerun stages a new isolated measurement tree."""
from pathlib import Path
import csv, datetime, hashlib, json, math, os, shutil, subprocess, sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
API=ROOT/'work'/'randomized_recovery_root'
KEYS=('primal_normalized','dual_normalized','stationarity_normalized','duality_gap_normalized')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b):
    assert math.isfinite(float(a)) and math.isfinite(float(b))
    assert math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-13),(a,b)
def count(g,m,b):
    q=min(b,g*(m-1)); dp=[1]+[0]*q; product=1
    local=[math.comb(m,k) for k in range(min(q,m-1)+1)]
    for _ in range(g):
        product*=sum(local)
        dp=[sum(dp[s-k]*local[k] for k in range(min(s,len(local)-1)+1)) for s in range(q+1)]
    return dp[q],product
def verify():
    provenance=json.loads((HERE/'provenance.json').read_text())
    for name,h in provenance['file_sha256'].items(): assert digest(HERE/name)==h,name
    manifest=json.loads((HERE/'instances.json').read_text())
    assert digest(HERE/'protocol.txt')==manifest['protocol_sha256']
    for name,h in manifest['api_hashes'].items(): assert digest(API/name)==h,name
    results=json.loads((HERE/'results.json').read_text()); summary=json.loads((HERE/'summary.json').read_text())
    assert results['manifest']=={k:v for k,v in manifest.items() if k!='cases'}
    cases=manifest['cases']; rows=results['rows']; table=list(csv.DictReader((HERE/'results.csv').open(newline='')))
    assert len(cases)==28 and len(rows)==56 and len(table)==56
    lookup={(r['case'],r['method']):r for r in rows}; flat={(r['case'],r['method']):r for r in table}
    assert len(lookup)==len(flat)==56
    specs=[(g,m,f,p) for g in (1,2,4) for m in (6,12) for f in (.25,.5) for p in (0,1)]
    specs += [(1,m,.5,p) for m in (24,48) for p in (0,1)]
    discrepancies=[]; compact=[]; skips=0
    for index,(c,(g,m,f,p)) in enumerate(zip(cases,specs)):
        assert c['case']==f'C{index+1:02}' and (c['blocks'],c['coordinates_per_block'],c['budget'])==(g,m,math.floor(g*m*f))
        assert c['profile']==('tied-heterogeneous' if p else 'distinct-homogeneous')
        assert len(c['coefficients'])==len(c['energies'])==g and all(len(v)==m for v in c['coefficients'])
        assert all(e>0 for e in c['energies'])
        n,prod=count(g,m,c['budget']); eligible=n<=25000 and prod<=100000
        assert (c['batches'],c['candidate_product'],c['enumerated_eligible'])==(n,prod,eligible)
        for method in ('compact','enumerated'):
            r=lookup[c['case'],method]; t=flat[c['case'],method]
            for k in ('blocks','coordinates_per_block','total_coordinates','budget','profile','candidate_product'):
                assert r[k]==c[k] and str(r[k])==t[k]
            assert r['status']==t['status']
            if method=='enumerated' and not eligible:
                assert r['status']=='not_attempted_by_frozen_size_rule'; skips+=1; continue
            assert r['status']=='success' and r['exit_code']==0 and len(r['lp_checks'])==1
            lp=r['lp_checks'][0]; assert lp['solver_success'] and lp['solver_status']==0
            for k in KEYS: assert 0<=lp[k]<=1e-7; close(lp[k],t[k])
            for k in ('variables','equalities','inequalities','nonzeros'): assert lp[k]>0 and lp[k]==int(t[k])
            for k in ('value','method_seconds','parent_wall_seconds'): close(r[k],t[k])
            close(lp['solver_seconds'],t['solver_seconds'])
            close(max(r['peak_working_set_bytes'],r['parent_observed_peak_bytes'])/2**20,t['peak_working_set_mib'])
            assert 0<r['peak_working_set_bytes']<1024**3 and 0<r['method_seconds']<=r['parent_wall_seconds']<20
            close(r['instrumented_method_seconds']-lp['diagnostic_seconds'],r['method_seconds'])
            if method=='compact':
                compact.append(r); assert r['sample_checks']==20
                assert r['policy_diagnostics']['lp_dimensions']=={k:lp[k] for k in ('variables','equalities','inequalities')}
                scale=max(1.,sum(e*(max(a)-min(a)) for e,a in zip(c['energies'],c['coefficients'])))
                assert abs(r['value']-r['lp_value'])/scale<=1e-7
        if eligible:
            a=lookup[c['case'],'compact']; b=lookup[c['case'],'enumerated']
            scale=max(1.,sum(e*(max(v)-min(v)) for e,v in zip(c['energies'],c['coefficients'])))
            d=abs(a['value']-b['value'])/scale; assert d<=1e-7; discrepancies.append(d)
            for method in ('compact','enumerated'):close(d,flat[c['case'],method]['finite_objective_discrepancy_normalized'])
    assert len(compact)==summary['compact_successes']==28 and len(discrepancies)==summary['finite_comparisons']==12 and skips==16
    assert summary['compact_failures']==[] and summary['numerical_checks_pass'] and summary['single_run']
    close(max(discrepancies),summary['max_finite_discrepancy_normalized'])
    for k in KEYS: close(max(r['lp_checks'][0][k] for r in compact),summary['maxima'][k])
    for func,index in ((min,0),(max,1)):
        close(func(r['method_seconds'] for r in compact),summary['method_seconds_range'][index])
        close(func(r['peak_working_set_bytes']/2**20 for r in compact),summary['peak_mib_range'][index])
    return dict(status='PASS',check_kind='independent archival consistency and checksum checks; no optimization rerun',compact_cases=28,finite_comparisons=12,predeclared_skips=16,sample_budget_checks=560,source_hashes=provenance['file_sha256'],api_hashes=manifest['api_hashes'],provenance_sha256=digest(HERE/'provenance.json'))
def rerun():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    stage=HERE/('rerun_'+stamp)/'work'; target=stage/'randomized_scaling_review'; target.mkdir(parents=True,exist_ok=False)
    apitarget=stage/'randomized_recovery_root'; apitarget.mkdir()
    for name in ('protocol.txt','instances.json','benchmark.py'):shutil.copyfile(HERE/name,target/name)
    for name in ('compact_randomized.py','compact_policy.py'):shutil.copyfile(API/name,apitarget/name)
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
    # Explicit path/runpy avoids Windows long absolute script-path import behavior.
    bootstrap="import sys,runpy; p=sys.argv[1];sys.path.insert(0,str(__import__('pathlib').Path(p).parent));sys.argv=[p,'run'];runpy.run_path(p,run_name='__main__')"
    subprocess.run([sys.executable,'-c',bootstrap,str(target/'benchmark.py')],cwd=target,env=env,check=True)
    print(json.dumps({'rerun_directory':str(target),'note':'Fresh timing measurements are retained separately; the original archive was not overwritten.'}))
if __name__=='__main__':
    report=verify(); print(json.dumps(report,indent=2))
    if '--write-report' in sys.argv:(HERE/'archival_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if '--rerun' in sys.argv:rerun()
