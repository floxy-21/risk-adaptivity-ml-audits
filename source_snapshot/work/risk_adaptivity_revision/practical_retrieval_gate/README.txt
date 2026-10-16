PRACTICAL RETRIEVAL GATE: OFFLINE REPRODUCTION

Contract
--------
Return one of four fixed forecast models with block MSE no more than
epsilon=0.01 times the frozen training second moment above the best candidate.
This is a downstream model-choice requirement, not the paper's joint
half-initial-width precision objective. A selected model need not be the exact
empirical winner: 26 of the 198 external gate-selected models are not exact
winners, but every selected model meets the declared tolerance on replay.

Run from the supplement root (Python standard library only; no network):

python work/risk_adaptivity_revision/practical_retrieval_gate/run.py --out outputs/practical_retrieval_gate_replay

This executes four checks in sequence:
1. analyze.py recomputes all 1,098 exact gates, 39,528 direct vertex MSE checks,
   warm/cold shared-fetch cache ledgers, complete request/row frontiers, and a
   rounding-safe benchmark forecast-archive alternative.
2. check_saved.py independently checks request/cache accounting, small exact
   range partitions, all twelve cached HTTP responses and their overlap, all
   279 public endpoint totals and all 279 external model decisions. It issues
   no requests and imports no optimizer or analyzer.
3. time_gate.py performs one fixed-order exact-gate timing pass. Loading and
   rational preparation are separate. Timings naturally vary across machines;
   counts and decisions must agree exactly.
4. check_tolerance_scale.py checks and regenerates the supplementary six-system
   loss-scale table; see its exact raw-source/replay distinction below.

All commands accept their own --out or --results argument, shown by --help.
Expected run_report.json: PASS, steps=4, network_requests=0. Expected final
independent_check.json includes case_policy_cache_checks=4392,
exact_gates_checked=1098, direct_vertex_loss_checks=39528,
saved_HTTP_requests_checked=12, saved_HTTP_rows_checked=4623,
exact_live_total_checks=279, external_zero_query_decisions_validated=198,
external_bulk_selected_decisions_validated=81.

Results-to-command map
----------------------
Gate count/per-system count and minimum worst-completion excess loss:
  analyze.py -> case_gate.json and report.json.
Warm/cold request and returned-counter-value table:
  analyze.py -> request_plans.json, report.json, routing_decisions.json.
Every request/row tradeoff and actual coalesced ranges:
  analyze.py -> range_frontiers.json and cost_frontier.csv.
Permitted next-day persistence record, rounding box and safe selected model:
  analyze.py -> archive_copy_trace.json.
Saved public-service semantics, payload hashes, 279 live totals/decisions:
  check_saved.py -> independent_check.json; observed timings and original body
  sizes remain in http_probe/http_log.json and http_probe/report.json.
One local exact-gate compute-time pass:
  time_gate.py -> gate_timing.json. The manuscript's measured pass is frozen
  separately in inputs/reported_gate_timing.json; repeated run times vary.

All four models/six pairs share one acquired set. A range returns every
hourly value inside its bounds, including cached endpoints and unneeded hours;
those rows are charged. Immediate cold acquisition reuses a preceding block's
cached ending counter. A repeated complete audit needs zero further requests.
Cold request-oriented routing chooses direct bulk, because learning endpoints
first can add a second request. Retrospective access uses legitimate later
forecast copies before requesting data and coalesces remaining ranges.

Data and chronology
-------------------
inputs/public_decision_inputs_coherent.json is frozen at SHA256
4dab6420e1a365feb9bd08d21ebb936f347c21b445848a49b898086dd8029230.
It contains fixed forecast vectors, exact outer totals and training-only
second moments, not the withheld original-source counter trace. All six paired
contrasts are calculated from the same four binary64 forecast vectors using
exact rational arithmetic. PROTOCOL.txt was fixed before the twelve requests.
The source reconstruction, source hashes and parser versions are preserved in
source_reference/. These snapshots document the prior construction; they are
not default entry points. This is an exploratory extension on existing panels,
not a previously untouched confirmation.

The external API permits range retrieval; it does not enforce two readings.
The 70.97% request reduction is conditional accounting for separate immediate
block audits whose endpoints are already available. It is not a claim about
the whole-period bulk service. On the actual twelve-request validation,
three gated fine spans returned 58,965 body bytes, while three full spans
returned 64,357. Obtaining the coarse endpoint grid first increases the gated
total to 69,809 bytes and six requests. Body bytes exclude headers/TLS. I/O
times are descriptive, with uncontrolled provider caching; no price, energy,
population latency advantage or deployed cost saving was measured.

Rounding and archive access
---------------------------
The original daily persistence values here are generated by the benchmark's
documented prior-day parser, not claimed as historical production log files.
The external values preserve the original float through round-trip parsing.
Archive decisions use conservative neighboring-binary64 enclosures, never
treat a rounded saved float as an exact physical counter increment. All 810
original and 270 external next-day-copy cases certify the epsilon requirement
under those enclosures. The remaining fine-range counts assume endpoints are
already held; cold access must include them. The immediate decision gate never
reads a future forecast or a withheld fine answer.

Optional raw-source validation
------------------------------
verify_source_inputs.py is independently written within this study and reads
the original frozen forecast files, declared outer counters, training-scale
ledger and prior-day persistence inputs. It is distinct from default replay
of bundled derived inputs. Run after the journal's documented original-source
regeneration has produced a full chain:

python work/risk_adaptivity_revision/practical_retrieval_gate/verify_source_inputs.py --workspace . --chain-dir PATH_TO_FULL_CHAIN --out outputs/practical_gate_source_check

See verify_source_inputs.py --help for expected source paths. Original
fine-source records are not bundled in this folder.
source_check_results/ records the completed source-bound check, not external
human validation. Fresh forecast fitting remains a separate full-study route.

System-level tolerance context (supplementary table)
--------------------------------------------------
The unchanged epsilon=0.01*M2 is now shown in absolute kWh-squared units for
each of the six systems, beside realized loss scales on all existing blocks.
The table reports pooled four-model median MSE, median blockwise best MSE,
median within-block maximum-minus-minimum MSE, and the count of blocks where
all four model MSEs fall within epsilon. The best is a descriptive hindsight
reference, not the performance of one deployable model. These metrics add no
model, tolerance, selected cohort, policy, or significance test.

Default offline command from the supplement root:

python work/risk_adaptivity_revision/practical_retrieval_gate/check_tolerance_scale.py --out outputs/tolerance_scale

The command regenerates summary.json and tolerance_scale_fragment.tex from
inputs/tolerance_scale_summary.json, checks its pins and mathematical units,
and independently recomputes all 279 external blocks from bundled public API
samples using an expanded quadratic loss formula. Original-source quantities
are six-system aggregate replay only by default; no original per-block losses
or fine-answer arrays are distributed. The original three systems' counts and
metrics were independently recomputed on the completed pinned raw-source chain:

python work/risk_adaptivity_revision/practical_retrieval_gate/check_tolerance_scale.py --chain-dir PATH_TO_FULL_CHAIN --out outputs/tolerance_scale_full_source

This optional command checks all 1,098 blocks. It must reproduce the same table
and system medians exactly. The completed evidence is retained in
results/tolerance_scale_full_source/independent_check.json. To regenerate the
safe aggregate input itself after obtaining the pinned original source:

python work/risk_adaptivity_revision/practical_retrieval_gate/build_tolerance_scale.py --chain-dir PATH_TO_FULL_CHAIN --out outputs/tolerance_scale_summary_rebuilt.json

The builder uses direct squared residuals and verifies all 6,588 exact paired
loss identities; the checker uses independently reconstructed cumulative
samples and expanded quadratic losses. Only system aggregate statistics are
exported. Runtime was a few seconds on the reported local environment. This
descriptive context remains an exploratory supplementary analysis of the same
frozen forecasts, not a new confirmation study or calibrated decision threshold.
