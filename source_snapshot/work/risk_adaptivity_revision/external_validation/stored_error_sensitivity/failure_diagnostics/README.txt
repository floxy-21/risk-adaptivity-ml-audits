Purpose
=======
This new diagnostic explains all nine failed positive-error case/allowance
combinations in the frozen sensitivity (two at 0.001, seven at 0.01). It changes
no case, input, threshold, original output, solver or protocol. The preceding
49 exact upper certificates remain unchanged.

Result
======
All nine failures have exact feasible lower witnesses ruling out every
deterministic adaptive policy with at most two permitted counter queries.
Each of the five possible first queries has a common first answer and four
endpoint pairs, one for each distinct second query. Each pair has identical
queried readouts and a true contrast difference strictly greater than 1/2.
This is an information obstruction in the fixed hidden-error model, not an
optimization failure. It does not rule out randomized adaptive policies.

At delta=0.001 the lower widths are 0.5021666666666664 and 0.503. At delta=0.01
they range from 0.5000059060297954 to 0.53. The smallest excess is proved as an
exact rational inequality, including the near-threshold case. The two cases
failing at 0.001 had essentially no numerical headroom at zero error (A=0.5).
The remaining five lose their previous headroom at the larger allowance.
Errors let different true segment allocations produce the same observed
prefix readings. That enlarges terminal information fibers and can prevent
two observations from halving the original width.

Reproduction (no network, no training, no raw meter archive)
=========================================================
From the supplement root:
python work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/failure_diagnostics/check_lower_witnesses.py --output lower_verification.json

The checker uses only Python's standard library. It reconstructs coefficient
fractions from the frozen geometry and checks all constraints directly; it
does not import the generator or call an LP solver. It verifies input hashes
and exact correspondence to all failed positive-level rows. The --output
argument redirects the report without changing the frozen verification file.

Optional regeneration, requiring the documented NumPy/SciPy environment:
python work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/failure_diagnostics/build_lower_witnesses.py

The generator uses floating LP solutions only to propose endpoint witnesses.
It rounds proposed first answers to a rational grid of spacing 1e-10, then
reconstructs exact feasible vertices and validates every inequality with
Fractions. Any feasible first answer suffices for a lower witness; this
rounding is not a changed precision threshold or altered model. Generation
takes approximately three seconds on the study machine. The exported lower
values differ from the previously reported floating optima by at most
2.061e-11; they are rigorous lower bounds, not claims of exact optima.

Files
=====
PROTOCOL.txt: fixed diagnostic selection and scope.
witnesses.json: exact coefficients, endpoint records and readout traces.
case_ledger.csv: all nine case-level results and original reported optima.
generation_report.json: generation counts, hashes and timing.
verification.json: solver-free exact check output.
proof.tex: deterministic transcript argument and proposed manuscript wording.

Scope
=====
The total endpoints are exact; only the five internal stored readouts have
fixed hidden bounded errors. Values 0.001 and 0.01 are illustrative model
allowances, not calibrated physical accuracies or observed noisy replays.
The conclusion is specific to the unchanged two-query dictionary, hard
budget, and original half-width threshold. More information, a different
budget or a different target would constitute a different problem.
