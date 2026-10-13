EXTERNAL DEADLINE ACQUISITION: IMPLEMENTATION AND ATTRIBUTION

API
Add this directory to sys.path, then:
  from acquisition import select_batch, POLICIES
  result = select_batch(policy, a, b, observed, totals, budget=2,
                        rng=np.random.default_rng(seed),
                        surrogate_mean=frozen_ridge_prediction,
                        surrogate_sd=frozen_validation_residual_rmse,
                        blocksize=6)

Policies are exact, greedy, hara, uniform, randomized. Each returns
query_indices, planning_seconds and JSON-compatible diagnostics. All arrays
have one coordinate per target interval. withheld observed entries are NaN;
the full hidden target vector must never be passed. totals has one exact
nonnegative temporal total per disjoint block. A stochastic policy needs an
explicit random generator. Hara alone requires the frozen surrogate mean/SD.

The evaluator performs aggregate singleton/zero-total closure before calling,
charges the full returned batch, reveals all requested values, closes again,
and recomputes the common sharp certificate. The batch optimizer does not
see outcomes inside the requested batch. Use separate independent audit
states for methods; no query is charged twice in a state. Planning time
covers the API call, including input checks, optimization and sampling.
The API is intended for serial calls within a process; independent worker
processes may be used. No input is mutated and no outcomes are read from disk.

EXACT AND GREEDY
Both reuse the frozen study_recovery.py routines. Their active coordinates
belong to positive-energy, nonconstant-coefficient blocks with at least two
unknowns. No method requests a last-in-block reading already deducible from
the exact total. Exact recovery minimizes the next batch's worst residual
width. It does not minimize the stopping procedure's eventual number of
queries. The existing deterministic tie rules normally apply. If the exact
routine returns an empty primary-optimal batch at positive width, the API
chooses the lexicographically first feasible full batch attaining the same
primary width, so repeated application cannot stall. The new rule is frozen
before external outcome evaluation and is checked on tied extreme contrasts.

HARA ACQUISITION + AGGREGATE CERTIFICATE
Primary source:
Hara, S., Matsuura, M., Honda, J., and Ito, S. (2024), Active model selection:
A variance minimization approach. Machine Learning 113, 8327-8345.
https://link.springer.com/article/10.1007/s10994-024-06603-1
https://doi.org/10.1007/s10994-024-06603-1

For a fixed model pair, equation (8) assigns probability proportional to the
surrogate expectation of the absolute loss difference. For squared loss:
 w_i = E |(a_i-Y_i)^2-(b_i-Y_i)^2|
     = |a_i-b_i| E |a_i+b_i-2Y_i|.
For Y_i ~ Normal(mu_i,sigma_i^2), let d_i=|a_i+b_i-2mu_i| and s_i=2sigma_i:
 E |a_i+b_i-2Y_i| = s_i sqrt(2/pi) exp[-d_i^2/(2s_i^2)]
                       + d_i erf[d_i/(sqrt(2)s_i)].
The zero-SD limit is d_i. This is an absolute contrast expectation; it is
not the absolute expectation of the contrast and not merely |a_i-b_i|.

The paper allows a surrogate trained on the candidates' training data.
Here its fixed mean is the candidate Ridge forecast, and its household SD
is the square root of mean validation squared residual, with a predeclared
positive scale floor. All fitting and SD calibration precede test outcomes.
Before acquisition, independent Gaussian coordinates are conditioned on the
remaining exact block total E. For unknown coordinate i with variance v_i,
 mu'_i = mu_i + v_i/sum(v)*(E-sum(mu)),
 v'_i = v_i - v_i^2/sum(v).
This uses the same observed targets and aggregates available to the other
policies. The proposal can put mass on negative energy. It is an approximate
acquisition model only; it never relaxes the final nonnegative certificate.
No surrogate refitting or fitting to queried test outcomes is performed.

Draws use q_i=w_i/sum(w) over currently eligible unselected indices and are
sampled without replacement within each batch. The weights are frozen during
a batch, and updated from the available observations/totals after its full
reveal. If all eligible weights are zero, the next draw is uniform. The same
eligibility rule excludes already-deducible and contrast-irrelevant targets
for every policy. This exclusion and batch operation are benchmark-specific.

Author source inspected:
https://github.com/sato9hara/active-model-selection
commit 33f6fab5f50d470bc2957a3ed1c4e86d94d82f5d
src/query.py, q_by_loss_diff_sub and q_by_loss_diff.
The author code sums discrete-surrogate probabilities times the absolute
loss contrasts and normalizes over remaining indices. Its default additive
epsilon is 0.01 for classification losses. Our rule implements the published
equation (8), equivalent to specifying eps=0, without an arbitrary additive
constant in regression loss units. The unmodified inspected source is
included as hara_author_query.py.txt with HARA_AUTHOR_LICENSE.txt (MIT); it
is a provenance reference, not an executed dependency.

The original work combines acquisition with LURE unbiased risk estimates;
its reported experiments use classification. This experiment evaluates the
published pairwise acquisition principle with a continuous Gaussian surrogate
and a common deterministic aggregate certificate. It is not a reproduction
of its classification performance or its complete statistical estimator.
No variance-optimality statement is claimed for this conditional surrogate,
nonnegative constrained audit, batched procedure or stopping decision.

RANDOMIZED RECOVERY
compact_secondary.py implements the frozen compact batch LP with the same
target-independent secondary rule used in the preceding revision: minimize
the uniform-within-block barycenter expected width on the primary minimax
face. Both primary and secondary optimization are compact LPs; no test
outcomes or realized certification enter them. Expected width coefficients,
duality residuals and sampling corrections are retained in diagnostics.

Per-block contrasts are shifted and divided by their range; energies become
E_g*range_g/initial_width. This preserves the primary and barycenter policy
objectives while improving scale. The unchanged compact_policy.py compiler
and exact fixed-cardinality sampler are reused via an isolated module with
an explicit secondary-solver dependency; no frozen baseline file is changed.
Residual tolerances are numerical checks, not interval arithmetic. The rule
may retain multiple optimum mixtures, and no pointwise dominance or maximum
certification claim follows. Positive-width batches respect a hard cap.

CHECK COMMAND
  python work/external_deadline/acquisition/check_acquisition.py
Checks the folded-normal expression against numerical quadrature; ten small
compact primary/secondary problems against a separately constructed finite
game with the alternative HiGHS IPM algorithm; sixty policy/seed eligibility,
immutability and deterministic replay cases; five all-observed cases; and
the empty-primary-optimum progress fixture. fixture_check.json records
residuals and code hashes. These checks use synthetic fixtures, not the
external dataset's forecast/recovery outcomes.
