"""One fixed-order timing pass; input loading and rational preparation separate."""
from fractions import Fraction as F
from pathlib import Path
import argparse,hashlib,json,platform,time

HERE=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=HERE/'results');args=parser.parse_args()
    start=time.perf_counter();raw=(HERE/'inputs/public_decision_inputs_coherent.json').read_bytes();data=json.loads(raw)
    load_seconds=time.perf_counter()-start;start=time.perf_counter();prepared=[]
    for c in data['cases']:
        prepared.append((c['id'],F(c['E']),F(c['epsilon']),sorted(c['forecast_vectors']),
            [(p['model_a'],p['model_b'],list(map(F,p['c'])),F(p['d'])) for p in c['pairs']]))
    preparation=time.perf_counter()-start
    expected={r['id']:r for r in json.loads((args.results/'case_gate.json').read_text())}
    times=[];start=time.perf_counter();cpu=time.process_time()
    for ident,E,eps,models,pairs in prepared:
        before=time.perf_counter();bounds={m:F(0) for m in models}
        for a,b,cc,d in pairs:
            bounds[a]=max(bounds[a],d+E*max(cc))
            bounds[b]=max(bounds[b],-d-E*min(cc))
        selected=[m for m in models if bounds[m]<=eps]
        elapsed=time.perf_counter()-before
        assert selected==expected[ident]['qualified']
        times.append(dict(id=ident,gate_seconds=elapsed))
    seconds=time.perf_counter()-start;cpu_seconds=time.process_time()-cpu
    vals=sorted(r['gate_seconds'] for r in times)
    result=dict(status='PASS',scope=__doc__,passes=1,cases=len(times),order='bundled input order',
        input_sha256=hashlib.sha256(raw).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        python=platform.python_version(),platform=platform.platform(),
        input_loading_seconds=load_seconds,rational_preparation_seconds=preparation,
        checked_gate_pass_wall_seconds=seconds,checked_gate_pass_cpu_seconds=cpu_seconds,
        gate_only_sum_seconds=sum(vals),gate_mean_seconds=sum(vals)/len(vals),gate_median_seconds=vals[len(vals)//2],
        gate_p95_seconds=vals[int(.95*(len(vals)-1))],gate_max_seconds=vals[-1],
        limits='Single local software pass, no population runtime inference; the gate requires the already-declared inputs.',cases_timing=times)
    (args.results/'gate_timing.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases_timing'},indent=2))

if __name__=='__main__':main()
