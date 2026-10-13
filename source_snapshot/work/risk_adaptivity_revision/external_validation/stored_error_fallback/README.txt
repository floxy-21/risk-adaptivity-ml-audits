Certified budget escalation for the 29 external cases
===================================================

This is a post-analysis assurance policy, not a revision of the primary
two-query experiment. The original error model, cases, coefficients and
precision threshold remain unchanged: nonnegative increments, exact retained
endpoint total E, five stored internal prefix readouts with fixed hidden errors
in [-0.01E,0.01E], and required terminal width at most 0.5 of the initial width.
The error allowance is illustrative, not a calibrated physical meter accuracy.
No hidden fine-resolution answers or recorded replay outcomes select a policy.

Result
------
All 29 cases have a fixed three-query batch with a rigorously verified width
upper bound below the unchanged threshold. The policy keeps the certified
two-query first/successor supports for 22 cases and uses a fixed three-query
batch for the seven other cases. It therefore guarantees precision for all
29 cases with budgets 22*2 + 7*3 = 65, compared with 29*3 = 87 for the
certified fixed-batch alternative. The mean allowance is 65/29 = 2.2414,
the maximum is three, and the reduction in summed reserved allowances is
22/87 = 25.2874 percent. These are conditional mathematical reading budgets,
not measured HTTP request counts, wall time, money, or expected stopping cost.
The public full-range export remains a separate, faster measured alternative.

The primary two-query guarantee remains 22/29. Existing exact lower witnesses
in ../stored_error_sensitivity/failure_diagnostics/ exclude every deterministic
adaptive policy with at most two queries for the other seven cases. Together
with the new three-query upper certificates, they prove a minimum deterministic
budget of three for those seven cases. The previously proved zero-error batch
upper success of one half extends by feasible-set inclusion, excluding a
deterministic fixed two-query guarantee in all 29 cases; hence three is the
minimum fixed guaranteed budget on this panel. These are not claims about
minimum expected stopping cost or all randomized adaptive policies.

Computation and exact certificates
---------------------------------
run_fallback.py evaluates all 31 nonempty batches per case (899 LPs) with the
existing generic robust solver. It uses tolerance 2e-8 only to select numerical
proposals, then verifies the selected fixed batch by exact rational weak
duality. All 29 selected batches have three queries. Binary64 source
coefficients are converted exactly to rational numbers and divided by their
exact positive range; they are never translated. The error allowance is the
exact rational 1/100. All dual multipliers, model rows, variable boxes,
stationarity residuals and residual box corrections are exported.

The independent fixed-certificate checker reconstructs the 22-variable model
from frozen source coefficients. All 29 certificates pass; the smallest margin
below 1/2 is about 0.04110483. Floating multipliers only propose certificates:
the concluding inequalities use exact arithmetic. The upper bounds need not
be the exact LP optima, and a small floating residual alone is not the proof.

Executable policy without an online optimizer
---------------------------------------------
build_branch_certificates.py derives an affine upper bound on each supported
second-query conditional worst width from the existing exact support dual.
The exported bounds have the form intercept + slope*t, where t is the first
normalized stored readout. Exact rational evaluation at the domain endpoints
and every line intersection verifies that the lower envelope is <=1/2 on
the entire feasible first-answer interval [-1/100,101/100], in all 22 cases.
This is a continuum certificate, not a finite replay test.

policy.py provides execute(case_id, read_boundary). The callback receives a
one-based internal boundary 1..5 and returns the stored readout relative to
the known initial counter, divided by E. A Fraction or decimal string supports
exact decimal input; a float is interpreted as its exact binary64 value.
The two-query policy reads its first boundary and chooses the smallest exact
affine upper bound for the second. The three-query policy selects its whole
batch before any answer. An exact monotone-prefix feasibility check rejects
transcripts outside the declared bounded-error model. No network operation,
model fitting, numerical LP or hidden target is used by the runtime.

The affine-bound branch can differ from an exact conditional LP minimizer.
It retains the same first/successor support and precision guarantee, but old
recorded replay success/width measurements are not attributed to this new
post-analysis policy. Implementation checks use six energy vertices plus the
uniform profile, crossed with five fixed error patterns; all 1,015 executions
obey their budgets and all 29 deliberately infeasible cases are rejected.
Those tests exercise code; the rational continuum certificate proves the
guarantee for all feasible answers.

Entry commands (from the supplement/repository root; offline)
-------------------------------------------------------------
1. Recompute numerical proposals and fixed certificates (NumPy/SciPy; ~9 s):
python work/risk_adaptivity_revision/external_validation/stored_error_fallback/run_fallback.py

2. Derive affine branching certificates (standard library; <1 s):
python work/risk_adaptivity_revision/external_validation/stored_error_fallback/build_branch_certificates.py

3. Independently check all fixed certificates (standard library; <1 s):
python work/risk_adaptivity_revision/external_validation/stored_error_fallback/INDEPENDENT_CERTIFICATE_CHECK.py --output fallback_check.json

4. Independently verify the entire first-answer continuum and executable
branching at all breakpoints/midpoints (standard library; <1 s):
python work/risk_adaptivity_revision/external_validation/stored_error_fallback/INDEPENDENT_BRANCH_CHECK.py --output fallback_branch_checks.json

5. Check executable callbacks on constructed model-feasible inputs (~5 s):
python work/risk_adaptivity_revision/external_validation/stored_error_fallback/policy.py --self-test --output fallback_execution_checks.json

The independent continuum checker passed all 44 lines for all 22 cases and
also verified 110 feasible breakpoint/midpoint execution transcripts. The
minimum full-domain margin is approximately 0.0037592273. A clean package run
should execute
these checks against the frozen geometry before any producer rewrites that
hash-locked input. No model refitting or network access is required.

File map
--------
PROTOCOL.txt and protocol_lock.json: study rule and pre-computation hashes.
all_batches.csv: every numerical batch and budget, including failed budgets.
cases.json: budget minima/proposals for every one of the 29 retained cases.
fixed_batch_certificates.json: 29 exact dual upper certificates.
prescriptions.json: complete case-specific two/three-query deployment plans.
report.json: numerical producer counts, timings and exact budget arithmetic.
branch_certificates.json: exact conditional affine bounds and full-domain checks.
branch_report.json: affine-bound derivation output, with no solver calls.
execution_checks.json and execution_test_traces.json: fixed implementation tests.
INDEPENDENT_CERTIFICATE_CHECKS.json: separate exact fixed-certificate verification.
INDEPENDENT_BRANCH_CHECKS.json: separate continuum and runtime verification.
