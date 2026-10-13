"""Targeted solver regressions: secondary ties and zero-valued games."""
import argparse,json
from pathlib import Path
import numpy as np
import empirical_shared_audit as solver

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path(__file__).with_suffix('.json'));a=p.parse_args()
    assert solver.choose([1.,1.],[.5,.5-1e-16])==0
    g=solver.geometry(np.tile([0.,0.,1.,1.,0.,0.],(6,1)))
    assert g['randomized_batch_optimum']==0 and np.isfinite(g['adverse_vertex_weights']).all()
    assert abs(sum(g['adverse_vertex_weights'])-1)<1e-12 and g['primal_dual_gap']<solver.TOL
    result={'status':'PASS','secondary_roundoff_tie_earliest':True,'zero_game_value':g['randomized_batch_optimum'],
            'zero_game_gap':g['primal_dual_gap'],'solver_source_sha256':solver.sha(Path(solver.__file__))}
    a.output.parent.mkdir(parents=True,exist_ok=True);solver.dump(a.output,result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
