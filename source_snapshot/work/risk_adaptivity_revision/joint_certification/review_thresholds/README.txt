FROZEN-CERTIFICATE THRESHOLD STABILITY

Question
For each of the 165 original and 57 external matched-half cases, on which
thresholds do the existing adaptive branches guarantee success while the
optimal randomized fixed batch has worst-record success exactly 1/2?

Input discipline
We retain the original first and second query choices, branch intervals,
uniform two-batch mixture, and adverse-record distribution. The calculation
uses normalized forecast-contrast coefficients and the unit simplex only.
It never reads withheld fine-resolution target answers, performs new model
fitting, or optimizes an acquisition policy. We tighten auxiliary proof
multipliers algebraically for the already selected pair of batches.

Default bundled-certificate replay
(from the project root; standard Python 3, no third-party packages)

python work/risk_adaptivity_revision/joint_certification/review_thresholds/threshold_stability.py
python work/risk_adaptivity_revision/joint_certification/review_thresholds/check_threshold_stability.py

These commands replay all 222 bundled rational certificates into replayed/.
They do not require or verify raw records, regenerate forecasts, or establish
the raw-source provenance in this run. The output explicitly records
execution_mode=bundled_certificate_replay and
source_records_verified_in_this_run=false. This is stronger than trusting the
saved interval values: the widths, branches, covering inequalities, adversary
inequalities, interval endpoints, and summary counts are recalculated.

Full-chain regeneration and source-linked verification

python work/risk_adaptivity_revision/joint_certification/review_thresholds/threshold_stability.py --chain-dir work/final_chain_20261014T031901Z/run --output-dir work/risk_adaptivity_revision/joint_certification/review_thresholds/executed
python work/risk_adaptivity_revision/joint_certification/review_thresholds/check_threshold_stability.py --chain-dir work/final_chain_20261014T031901Z/run --results work/risk_adaptivity_revision/joint_certification/review_thresholds/executed

The chain directory is an existing full source-chain run. To use a newly
regenerated full chain, pass its path with --chain-dir in both commands.
For example, from a release containing the documented full-chain sources:

python work/risk_adaptivity_revision/joint_certification/provenance_chain/run_chain.py --cohort all --output-dir outputs/threshold_full_chain

The output directory must be new. This route regenerates original-source
inputs with mandatory pinned SHA-256 checks, checks the external source
records, replays the frozen forecasts, and rebuilds the policies/certificates.
It can download about 31 MB of original raw data and takes roughly 15--20
minutes on the study workstation. It does not refit forecasting models.
Then substitute outputs/threshold_full_chain for --chain-dir in both
threshold commands above. An existing raw cache can be supplied using
--raw-dir. No --raw-run, --shared-run, or --precision-run reuse options are
needed for this fresh route.
--output-dir selects a different producer output directory; pass the same
directory to the checker with --results. --certificate-inputs selects another
saved inputs.json instead of the bundled executed/inputs.json; it is mutually
exclusive with --chain-dir. Full-chain mode verifies the current source hashes
and correspondence between geometry, saved policies and supplied coefficients.

Measured full-chain threshold runtimes on the study workstation: 43.2 seconds
for the producer and 59.3 seconds for the independent checker. The bundled
replay took 34.4 and 65.2 seconds. Concurrent tasks affect these timings.
The report records measured time, source and output hashes, and exact
rational interval endpoints. No floating-point feasibility tolerance is
used; each saved binary64 coefficient is treated as its exact rational
value. The original source-specific forecast units and provenance remain
in the parent full-chain inputs.

Outputs
  executed/inputs.json: source-linked frozen coefficient and certificate inputs.
  executed/intervals.json: all 222 exact half-open intervals [L,U), 36 pair-cover
      witnesses per case, and weighted-adversary crossover values for all ten
      two-query fixed batches.
  executed/report.json: source-, system-, and pooled summaries, exact quantiles,
      point-threshold counts, and whole symmetric-band counts.
  executed/independent_check.json: independently reconstructed widths,
      primal-edge verification of pair-cover minima, branch coverage, and
      weighted adverse-record inequalities.
  proof.txt: the continuum argument and strict upper-endpoint convention.
  manuscript_fragment.tex: short manuscript-ready result and table.

Interpretation
Each tau in [L,U) has adaptive success 1 and optimal randomized fixed-batch
success exactly 1/2 over the full uncapped exact-total simplex. The upper
endpoint is excluded because success means J <= tau. These are sufficient
ranges for frozen certificates, not a claim that the separation fails outside
the interval or that its maximal interval across all possible policies has
been found. Capacity constraints and reading errors belong to separate
analyses and are not incorporated here. These are 222 blocks, not 1,332
independent model-pair observations.

All 222 intervals contain 1/2 in their interior. The counts whose entire
closed bands are certified are 179 for [.49,.51], 119 for [.475,.525], and
53 for [.45,.55]. The corresponding original/external counts are 137/42,
93/26, and 41/12. Nearest-rank exact empirical quantiles are used, with no
interpolation. The scope is numerical/certificate verification within this
study, not external independent human validation.
