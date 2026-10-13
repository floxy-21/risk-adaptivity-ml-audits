"""Retain the exact pre-correction independent LP formulation for diagnosis."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
text=(HERE/'verify_decision_confirmation.py').read_text()
text=text.replace("    lp_options={'primal_feasibility_tolerance':1e-10,'dual_feasibility_tolerance':1e-10}\n",'')
text=text.replace("method='highs-ds',options=lp_options)","method='highs')")
text=text.replace('    # An added primary-face slack can change the secondary objective\n    # appreciably in a nearly degenerate game. Use the actual optimum.\n','')
text=text.replace('secondary=linprog(expected,A_ub=game,b_ub=np.full(len(game),primal.fun),','secondary=linprog(expected,A_ub=game,b_ub=np.full(len(game),primal.fun+1e-9),')
target=HERE/'verify_decision_confirmation_before_face_fix.py.txt'
assert not target.exists()
target.write_text(text)
print(target)
