EXECUTABLE ZERO-QUERY AUDIT GATE: TWO ACTUAL SAVED-FORECAST EXAMPLES

The interface supplies a usable computational action: either allow a pairwise
ranking because every compatible completion agrees, or withhold that guarantee.
It also identifies a model proven better than every competitor if one exists.
This is a retrospective model-audit action, not automatic model deployment.

Run either supplied evaluator-only snapshot from the supplement root:
  python work/risk_adaptivity_revision/practical_api/run_example.py work/risk_adaptivity_revision/practical_api/copies_available_input.json --output work/available_audit.json
  python work/risk_adaptivity_revision/practical_api/run_example.py work/risk_adaptivity_revision/practical_api/copies_absent_input.json --output work/absent_audit.json

These gate commands use only Python's standard library and the existing
outputs/energy_rank_bounds.py reference implementation. No training, endpoint
CSV replay, or reference truth is used by the evaluator. The two input JSON
files include the day's surviving readings, the four actual saved forecasts,
declared exact aggregate snapshots, and the meter's permitted saved persistence
forecast rows. The schema rejects an added hidden_truth field.

The output includes:
* Which direct copies were used, with original source row, source timestamp,
  target timestamp, source column and copied value.
* Exact-total deductions and numerical residual arithmetic.
* All six paired lower/upper loss bounds and the numerical decision margin.
* A complete attaining target vector for each lower and upper endpoint.
* ALLOW_RANKING or HOLD_RANKING for each pair, and a certified best model only
  when one is certified against all three competitors.
* A zero paid-query count and the full scheduled-target denominator.

For full regeneration from the already distributed public source files and
independent endpoint-LP checks, run:
  python work/risk_adaptivity_revision/practical_api/prepare_and_verify.py --output-dir work/practical_api_recheck
This command needs NumPy and SciPy. It reconstructs the actual inputs from
review_frozen_forecasts.csv, public_links.csv.gz and public_aggregates.csv.gz,
then verifies witnesses and all 24 endpoints using separately constructed LPs.
Only this verification stage reads reference truth, after the API has returned.
Known-coordinate and original-total witness residuals, independent LP agreement,
reference enclosure, and incorrect-certificate counts appear in verification.json.

Selection was not based on favorable prediction errors or certification:
we take the first Portugal six-hour contiguous mask, seed1103, six-hour exact
total case with permitted copies, and the first without, in the existing link
file ordering. They are MT_001 on2014-01-01 and2014-01-28 respectively.
The first reconstructs all six missing readings for free and certifies all six
pair rankings; persistence has the smallest certified loss. The second leaves
six readings unknown, certifies one pair, withholds five, and cannot certify a
best model. Both use zero paid requests. These examples demonstrate both output
branches, not a new estimate of performance or a claimed operational saving.

Critical scope: the totals are the ORIGINAL BENCHMARK TOTALS constructed from
complete historical public energy targets. They are not presented as naturally
surviving physical meter counters. Missingness and permitted archive access are
the existing retrospective benchmark design. No production arrival or retrieval
timestamps, prices, downstream outcomes, or forecast refits are introduced.

The underlying optimization is sharp in real arithmetic. The implementation is
floating point, not formal interval arithmetic. Small residual-total arithmetic
corrections and consistency tolerances are recorded explicitly. All observed
values and declared totals remain reviewable. Single API execution times include
input validation/closure/bounding and are diagnostic, not a runtime benchmark.
Timing-bearing JSON output hashes naturally change on a fresh execution.

INDEPENDENT EXTENDED-GRID CHECK

Run:
  python work/risk_adaptivity_revision/practical_api/replication_independent_check.py --output work/replication_independent_recheck.json

This independently recomputes paired and separate-loss endpoints for all 30
additional consumers on two fixed scenarios: six-hour contiguous gaps, seed
1103, six-hour exact totals; and twelve-hour scattered gaps, seed3301, daily
totals with 5% tolerance. It reads the original frozen predictions and the new
replication ledger; no production study bounds or closure routine is imported.
The separately implemented reference paired API and scalar water-filling plus
vertex individual-loss calculations check 360 period comparisons built from
6,420 daily snapshots. All 19,440 ledger decisions/counts are also reconciled.
Use --replication-dir to check a newly regenerated replication output directory.

Actual recorded run: 1,800 reference paired-API calls and 1,200 independently
coded individual-loss optimizations, max normalized discrepancies
1.0658141036401503e-14 paired and 1.0974658789118257e-14 separate, against
2e-8 * max(1, abs(reported endpoint)). Absolute differences are retained in the
JSON because energy scales differ substantially across consumers. The checker
does not independently recompute every grid scenario or refit the forecasts.

Information-flow review of replicate_archive_grid.py: complete targets enter
the prespecified mask/aggregate construction and subsequent reference checks.
The actual production bounding call accepts only predictions, visible/closed
targets, supplied totals, block size and tolerance. The fully archived fast
path evaluates losses from saved persistence copies, not from reference truth.
The high-demand mask is an explicitly oracle stress design; its implications
are deliberately not extra constraints in the declared feasible set. These
facts support the claimed retrospective benchmark, not a naturally observed
outage or independent untouched-source validation.
