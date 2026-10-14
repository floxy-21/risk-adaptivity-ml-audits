FINAL CHALLENGER DIAGNOSTICS

Purpose
1. Separate fixed-guaranteed, adaptive-only-guaranteed and not-guaranteed
   deterministic two-query blocks at the existing half-width target.
2. Test whether the saved greedy first query loses the guarantee even when
   its second query is chosen optimally after the first answer.
3. Keep the certified deterministic/two-batch-cover decisions and replace
   only the old mean-width fallback by the saved deterministic worst-width
   batch. This policy change depends only on pre-query coefficient geometry.

These are retrospective diagnostics on the existing panels. They are not a
new locked confirmation. No forecasting model is fitted. No optimum for
full-panel randomized precision risk is claimed.

DEFAULT OFFLINE COMMANDS (from the extracted supplement root)
  python work/risk_adaptivity_revision/joint_certification/final_challenger_diagnostics/analyze.py
  python work/risk_adaptivity_revision/joint_certification/final_challenger_diagnostics/check.py

analyze.py requires the study's pinned NumPy. check.py uses only Python's
standard library. Both accept output-directory/file options; see --help.

The default analysis freshly reconstructs coefficient inequalities for the
279 external blocks. For the original 819 blocks it replays saved derived
interval certificates, with no original coefficients or raw traces bundled.
The default checker checks all interval covers, uncovered-answer membership,
case joins, replay outcomes and paired summaries. It does not reconstruct
the original coefficient-to-interval derivation from the public inputs.

BOTH-SOURCE COEFFICIENT VERIFICATION
First execute the complete pinned source route described in
  work/risk_adaptivity_revision/joint_certification/provenance_chain/README.txt
For example:
  python work/risk_adaptivity_revision/joint_certification/provenance_chain/run_chain.py --cohort all --raw-dir PATH_TO_PINNED_BLEM_CACHE --output-dir all_chain_new
Then:
  python work/risk_adaptivity_revision/joint_certification/final_challenger_diagnostics/verify_source.py --shared-plans all_chain_new/shared/empirical_plans.json --precision-plans all_chain_new/precision/plans.json --output source_check_new.json
  python work/risk_adaptivity_revision/joint_certification/final_challenger_diagnostics/analyze.py --precision-plans all_chain_new/precision/plans.json --output-dir diagnostics_full_new
  python work/risk_adaptivity_revision/joint_certification/final_challenger_diagnostics/check.py --precision-plans all_chain_new/precision/plans.json --results diagnostics_full_new --output diagnostic_full_check_new.json

This freshly derives all 1,098 coefficient-to-interval certificates. The
original coefficients remain local. The already executed same-study full
coefficient check is full_source_independent_check.json; source_verification.json
records 6,588 coefficient-row joins to the previously regenerated source
catalogs. A separate earlier private input containing original coefficients
was moved outside the packaged directory and is not a supplement input.
The preparer can recreate the public frozen_inputs.json from those catalogs.

METHOD AND CONVENTIONS
For each first boundary k and second boundary j, the conditional worst joint
width is max_r{a_r*t+b_r*(1-t)}. The half-width success set is the intersection
of the rational linear inequalities a_r*t+b_r*(1-t)<=1/2 and [0,1]. A first
query guarantees half-width exactly when the four second-action intervals
cover [0,1]. Otherwise an uncovered rational answer t and its strictly
positive min_j g_kj(t)-1/2 are exported. All five first queries are checked.
The fixed-batch guarantee is the maximum segment coefficient range; all ten
batches are enumerated. Thus the three regimes are exact for the serialized
binary64-derived contrast vectors, not formal certificates about physical
measurement accuracy or model-estimation uncertainty.

The saved greedy rule minimizes the one-query worst joint width, breaks ties
by best two-query continuation, and then uses the optimal conditional second
query. This is stronger than an arbitrary myopic continuation. The reported
failure belongs to this saved first choice, not to every possible greedy rule.

Replay reports both J<=1/2 (strict rational comparison) and J<=1/2+10^-8
(the original general-replay convention). New fixed-fallback outcomes are
identical under both conventions. The older mean-fallback external score
changes from 72.546916% to 72.620854%, as already documented in the earlier
threshold sensitivity, because one batch lies about 1.11e-16 above half.
No historical result is replaced or silently given a different tolerance.

Paired outcomes for a randomized comparator are expected counts, calculated
analytically over its saved batch weights. They are not Monte Carlo samples.
The four cells are both succeed, adaptive only, comparator only and neither.
Descriptive intervals use 2,000 percentile bootstrap draws, linear quantiles,
with synchronized seven-day circular calendar blocks within each source;
PCG64 SeedSequence([20261014, source_id, 7]), source_id 0 original/1 external.
All systems and all blocks of a sampled date move together. With only three
systems per source, these are within-panel summaries, not population inference.

OUTPUTS
results/regime_certificates.json: each first-query interval cover or rational
  uncovered answer, plus the three-way regime and greedy-first diagnostic.
results/regime_cases.csv and regime_summary.{csv,json}: block/source/system
  results, including recorded greedy successes among its ex-ante failures.
results/replay_cases.{csv,json}: paired policy success probabilities for every
  block, both conventions, and exact new batch weights.
results/paired_summary.{csv,json}: source/system paired cells and intervals.
results/bootstrap_draws.json: explicit date-resampling indices.
results/report.json: scope, counts, source hashes and complete panel summaries.
results/fallback_attribution.json and fallback_attribution_{cases,groups}.csv:
  exact decomposition of the recorded-score deficit against pure fixed
  batching. All nonmatched blocks have equal success probabilities (their
  selected queries need not be identical). The entire deficit is 47 original
  and 14 external expected successes, on the matched-half subsets only:
  fixed155 versus cover108 of165, and fixed51 versus cover37 of57.
  The cover counts integrate its randomized batch weights. Since the exact
  randomized-batch minimax success is1/2 on each matched-half instance, every
  fixed batch has worst-case success0; a deterministic success indicator has
  worst-case value0 or1, and value1 would contradict that optimum.
  analyze.py regenerates this decomposition; fallback_attribution.py also
  provides a standalone entry point with --input and --output-dir options.
independent_check.json: default public checker scope and discrepancies.
full_source_independent_check.json: actually executed both-source check.
source_verification.json: source-catalog and coefficient digest joins.
manuscript_fragment.tex: concise measured-results wording for integration.

The checker's coefficient route independently forms segment-width vectors,
then takes prefix/suffix maxima, rather than importing the producer's envelope
code. On the chronologically first block of each system it additionally
enumerates all line intersections for each of the five first queries.
These checks supplement the analytic argument; they are same-study execution,
not external specialist review or a proof of the paper's universal theorem.
