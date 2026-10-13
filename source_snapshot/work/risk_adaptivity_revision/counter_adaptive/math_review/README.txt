Independent counter-adaptive mathematical verification
=====================================================

Files
  proof.tex: self-contained derivation, finite-game bound and exact example.
  check_counter_adaptive.py: separately implemented checks, imports no study code.
  verification.json: actual run output and source hash.

Run from repository root:
  python work/risk_adaptivity_revision/counter_adaptive/math_review/check_counter_adaptive.py
Requires NumPy and SciPy. The actual run used Python 3.12.14, NumPy 2.5.3,
SciPy 1.18.1; the available local environment is work/review-env/Scripts/python.exe.

Actual verification
  Eight coefficient vectors (one constructed and seven fixed-seed rational).
  800 independent conditional endpoint LPs.
  640 independent fixed-fiber endpoint LPs.
  Maximum width disagreement: 4.440892098500626e-16.
  Maximum conditional primal residual: 0 at stored precision.
  Comparison tolerance: 2e-8 * max(1,abs(analytic width)).
  Runtime: 11.0679 s on the local execution environment.
  Constructed first-cut exact values: 1,1,1,1/2,1.
  Finite-game primal and dual: both 0.5.
  Reconstructed rational adverse weights: half on e_2 and half on e_5.
  Exact rational upper bound: 1/2.
  Primal policy: equal mixture of cuts (2,4) and (4,5).
  A rational simplex grid of 1,287 points also has minimum success 1/2;
  this grid is a debugging check, not the proof over the continuum.
  The proof uses equally valid adverse weights half on e_1 and e_5.

Numerical reporting and threshold discipline
------------------------------------------
For the constructed example all envelope calculations and binary success
entries use Fraction arithmetic. The rational adverse weights satisfy the
simplex constraints exactly, and exact weighted-column enumeration gives
the upper bound. Thus its 1 versus 1/2 precision separation does not depend
on a floating-point threshold or a numerically approximate game objective.
LP comparisons are floating-point checks at the stated tolerance; they are
not formal interval-arithmetic validation of an arbitrary empirical run.

For empirical coefficients the strongest straightforward protocol at n=6 is:
1. Declare which numeric inputs define the problem (serialized decimals or
   stored binary floats), and convert those values exactly to Fractions.
2. Compute coefficient ranges, envelope endpoints/intersections, and the
   chosen fixed threshold exactly. This is only a small number of rational
   operations for five available prefixes. Equality counts as success.
3. Build the finite-profile success matrix using exact rational widths.
4. Use the LP to obtain adverse weights, clip tiny negatives and normalize.
   To obtain a formally feasible rational certificate, convert each retained
   nonnegative stored weight to a Fraction and normalize their exact sum.
   Then enumerate every batch and report the exact maximum weighted success.
   This certificate remains an upper bound even if the game LP was not
   solved optimally. Report its difference from the primal objective.
5. If ordinary floating arithmetic is used instead, report numerical
   tolerance honestly. Do not exclude borderline successes from the adverse
   matrix: this can make the apparent batch upper bound too small. Counting
   W<=tau+epsilon generously as success is conservative only when epsilon
   is a valid upper bound on the width evaluation error. A chosen heuristic
   epsilon is numerical checking, not a formal enclosure guarantee.

Fairness and scope
-----------------
The concentration-profile game bounds all randomized batches; its primal
distribution is not generally guaranteed optimal over every feasible
continuous record. Do not present vertex enumeration as exact tail-risk
optimization without a further proof. The exact constructed example does
have a separate continuum lower-bound proof, so equality is established.

The proposed two-query adaptive algorithm is optimal for deterministic
worst width. Whenever its width guarantee is no greater than the threshold,
it achieves the largest possible worst-record success, namely one. No claim
is made to solve arbitrary-threshold randomized adaptive precision risk.

The example's one-step minimax greedy first-cut scores are all tied. A poor
lexicographic first cut creates a misleading-looking gap; best greedy tie
matches the optimum. Use the universal randomized-batch bound as the strong
baseline; expose deterministic tie rules and best-tie sensitivity for greedy.

Queries in this model retrieve cumulative prefix readings, not individual
hourly targets. The operational availability of those counter readings must
be established from the permitted archive. Prefix replies must come from
the same actual record, and all competitors must receive the same totals,
prefix eligibility, hard query budget, and prior archive reconstruction.

This checker does not alter the manuscript, refit forecasts, rerun the
empirical study, or establish historical priority of the construction.

Full saved-geometry and raw-replay verification
----------------------------------------------
Two additional independent entry points audit the actual empirical outputs:

  python work/risk_adaptivity_revision/counter_adaptive/math_review/check_saved_geometry.py work/risk_adaptivity_revision/counter_adaptive/pilot/geometry.json --full --output work/risk_adaptivity_revision/counter_adaptive/math_review/pilot_verification.json
  python work/risk_adaptivity_revision/counter_adaptive/math_review/check_saved_geometry.py work/risk_adaptivity_revision/counter_adaptive/continuation/geometry.json --full --output work/risk_adaptivity_revision/counter_adaptive/math_review/continuation_verification.json

Without --full the geometry checker selects at most 36 evenly spaced cases.
With --full it checks every case and every batch, at all five thresholds.
It imports only the independent constructed checker in this directory, not
the study implementation. It interprets original serialized c values as
exact rationals, normalizes those original coefficients exactly, certifies
the selected first cut's original-coefficient envelope, reconstructs exactly
feasible rational adverse weights, and evaluates every batch under those
weights. It independently solves the finite-profile primal LPs and checks
conditional endpoint LPs on a fixed, evenly spaced subset of 12 cases per
phase (all first/second choices at first replies 0,1/2,1).

Both full phases PASS:
  Pilot: 1,080 cases, 5,400 finite games, 720 conditional LPs; 75.514 s.
  Continuation: 3,834 cases, 19,170 finite games, 720 conditional LPs; 167.670 s.
  All 49,140 batch columns checked, with no case exclusions.
  Maximum envelope discrepancy: 1.942890293094024e-16.
  Maximum original-vs-rounded normalization discrepancy: 2.7247790489966106e-16.
  Maximum conditional LP discrepancy: 1.1102230246251565e-16.
  Conditional LP primal residual: 0 at stored precision.
  No exact-versus-generous threshold-matrix entries differ.
  No understated batch upper bound; finite-game primal/dual differences 0.
  Secondary mean-optimal policy versus primary objective: at most 2.142e-10,
    within its declared numerical optimal-face tolerance, not exactly zero.
  Primary threshold 1/2: 4,661 exact adaptive guarantees; 290 exact strong
    separations. Every strong case has exact adverse upper bound <=1/2.
  Smallest exact slack 1/2-A among claimed primary guarantees: 0.0005537823579453208.
The reports' main counters aggregate all five thresholds. Primary-only
counts are obtained from their primary_exact_witnesses arrays, containing
the exact rational envelope values and adverse distributions per case.

The final replay uses exact original-coefficient second-query selection.
To audit it from original integer counter registers:

  python work/risk_adaptivity_revision/counter_adaptive/math_review/check_replay.py work/risk_adaptivity_revision/counter_adaptive/pilot --output work/risk_adaptivity_revision/counter_adaptive/math_review/pilot_replay_verification.json
  python work/risk_adaptivity_revision/counter_adaptive/math_review/check_replay.py work/risk_adaptivity_revision/counter_adaptive/continuation --output work/risk_adaptivity_revision/counter_adaptive/math_review/continuation_replay_verification.json

The raw replay checker requires original data_blem_consumer-*.csv files in
work, or --data-dir pointing to the documented regenerated raw files. It
does not redistribute those inputs. Their hashes appear in the reports.
It independently uses exact integer counter differences, Fraction endpoints
from original c and d, and exact first-answer-dependent second-query choice.
It checks all ten final batches, all five policy rows, the complete query
trace, and every threshold outcome for each case. Selected fiber endpoints
are independently optimized through LPs.

Both final raw replays PASS:
  4,914 exact query choices and source-time traces match.
  24,570 policy rows and 49,140 sharp batch intervals checked.
  Every batch contains the exact reference contrast.
  All threshold-success probabilities match without discrepancy.
  Maximum absolute width discrepancy: 7.771561172376096e-16.
  Maximum relative-width discrepancy: 1.1657341758564144e-15.
  Maximum scaled-width discrepancy: 5.10702591327572e-15.
  480 independently assembled endpoint LPs: maximum discrepancy 2.220446049250313e-16.
  Maximum LP primal residual: 8.881784197001252e-16.
  Runtime: 5.873 s pilot and 13.933 s continuation.
These checks validate the reported mathematical and numeric quantities;
they do not establish a field retrieval-cost advantage or a large all-task
average gain, and they do not change the prespecified study decision rule.

Post-analysis exact half-success structure and distribution
-----------------------------------------------------------
batch_half_structure.tex proves that if deterministic two-register
adaptation guarantees a specified precision, a randomized batch supported
on at most two batches guarantees success at least one half. The proof
uses the affine conditional-worst-width functions: their good sets are
closed prefix or suffix intervals of the first answer. The longest prefix
and earliest suffix cover the answer interval. Equal mixing gives the
universal one-half success floor. If an adverse distribution upper-bounds
all randomized batches by one half, the exact batch optimum is one half.

  python work/risk_adaptivity_revision/counter_adaptive/math_review/check_half_cover.py

The command also accepts --geometry PATH [PATH ...], --data-dir PATH and
--output PATH. The default geometry inputs are the pilot and continuation;
a freshly reconstructed single all-case geometry file can be supplied.
The complete 4,914-case input set is required, and all three raw counter
files must match their pinned source SHA-256 hashes. The final run used:

  python work/risk_adaptivity_revision/counter_adaptive/math_review/check_half_cover.py --geometry work/counter_reproduction_check_20261012T0250/results/geometry.json --data-dir work --output work/risk_adaptivity_revision/counter_adaptive/math_review/half_cover_verification.json

This separately implemented command first constructs all mixtures from
original coefficient geometry, then opens raw registers for a descriptive
replay. Ties choose the smallest second-query index after choosing the
furthest prefix endpoint and earliest suffix endpoint. It changes none of
the prespecified baseline results or screening criteria.

Actual output half_cover_verification.json:
  Exact covers checked for all 4,661 primary adaptive-guarantee instances.
  A single batch covers all first answers in 4,182 of those instances.
  Exact two-batch cover witnesses exported for all 290 strong instances.
  All 290 strong-instance batch optima equal exactly 1/2.
  Minimum, first quartile, median, third quartile and maximum: all 1/2.
  Number exactly 1/2: 290; below 0.4: 0; below 0.3: 0.
  Optional descriptive replay: this particular optimal policy has mean
    success 437/580 = 75.3448275862% across the 290 cases, with mean W/W0
    0.431159238553. It succeeds with probability one on 147 actual records
    and with probability one half on the remaining 143.
  Pilot descriptive mean success: 77.9411764706%; continuation: 74.5495495495%.
  Runtime of the final fresh-geometry run: 12.220 s.

The report additionally supplies representative_witnesses: the first
qualifying case in lexicographic date/block-start/model-pair order for each
meter, selected before the raw files are opened. earliest_three_per_meter
contains the first three under the same ordering for each meter. The three
representative first-query/second-query rules are:
  Meter 1, 2017-10-01 06:00, persistence/HGB: first 3, then 5 for t<=1/4,
    otherwise 2; guaranteed W/W0 <= 0.4668.
  Meter 2, 2017-10-01 06:00, persistence/MLP: first 4, then 5 for t<=1/2,
    otherwise 2; guaranteed W/W0 <= 0.4675.
  Meter 3, 2017-10-01 00:00, ridge/MLP: first 4, then 5 for t<=3/4,
    otherwise 1; guaranteed W/W0 <= 0.3929.
Here t is the first queried prefix mass divided by the outer total E;
boundary indices are relative to the block start. Each simple switch lies
inside the exact overlap of the selected good intervals, and both affine
pieces are checked at their relevant interval endpoints. The displayed
four-decimal ceilings are conservative for these three exact values.
These are sufficient two-branch witnesses, not a claim to reproduce every
branch of the full conditional-width-minimizing policy. Exact values and
source identities are in the JSON. half_cover_witness_table_rows.tex gives
ready-to-include rows with the equal-weight batch supports.

The aggregate above is a case average over the same 290-case subset;
separate meter and pair summaries are provided. The covering mixture is
one minimax-precision-optimal policy, selected by a declared geometry-only
rule. Its optimal worst-record value does not imply that every optimal
policy has the same historical success or that this policy maximizes
historical or population-average success. This post-analysis diagnostic
must remain separate from the prespecified comparator grid. The proof
establishes a guarantee limit for this hard-budget information model;
it does not establish measured deployment savings or universal practical
superiority on all 4,914 tasks.
