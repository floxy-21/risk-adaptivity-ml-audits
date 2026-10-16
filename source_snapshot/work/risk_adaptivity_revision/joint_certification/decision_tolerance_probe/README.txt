DECISION TOLERANCE OF THE FROZEN TWO-READING POLICIES

Question and chronology
Does the precision policy also certify a model whose loss is close to the
smallest loss among the four frozen predictors? This is a retrospective
diagnostic of all 819 original and 279 external blocks. It changes neither
the models nor their acquisition policies. protocol.json was written before
this diagnostic's tolerance outcomes were calculated. Its full factor grid
is retained: 0, .001, .005, .01, .025, .05, .1 times training M2. The primary
.01 factor comes from the existing absolute-floor analysis, not these new
outcomes. These tolerances are sensitivity values, not calibrated decision
thresholds or measured financial losses.

Decision definition
For each model m and each other model j, use the sharp upper endpoint of
loss_m-loss_j. Reversing a stored pair uses minus its LOWER endpoint.
The sharp worst regret of m is the maximum of zero and these three upper
endpoints. Model m is certified epsilon-optimal if that maximum is <=epsilon.
If several models qualify, choose the lexicographically first. Strict-winner
certification is evaluated separately with all three directed endpoints <0.
The epsilon=0 and strict counts happen to agree on these records; the tests
are not mathematically interchangeable at a tie.

All five policies spend two readings on the same uncapped exact-total,
exact-prefix observation model. Adaptive and greedy second queries follow
the already saved first-answer rules. Deterministic and randomized batches
are frozen. No policy is selected using its decision success. The randomized
mean-width and uniform counts are expected counts across their batch choices.
The first optimizes mean width, not this retrospective decision objective.

DEFAULT: BUNDLED DERIVED-ENDPOINT REPLAY, ALL 1,098 BLOCKS
Run from the project root with standard Python 3.11 or later:

python work/risk_adaptivity_revision/joint_certification/decision_tolerance_probe/replay_saved.py

This reconstructs all 38,430 block/factor/policy outcomes from the saved
pair-interval endpoints and orientations. It independently checks model
decisions, strict winners, all source/system summaries, paired outcomes and
56 descriptive bootstrap intervals. It reproduces case_outcomes.csv byte
for byte and writes readable all-grid summaries to saved_replay/.
It imports neither analyze.py nor the endpoint helper.

Its inputs are protocol.json and results/{saved_endpoint_inputs.json,
case_outcomes.csv,report.json}, together with analyze.py for the pinned
producer hash. This default route does NOT bind endpoints to raw original
records, refit forecasts, or regenerate acquisition policies. The derived
inputs contain no fine-answer vector. They retain all endpoint results,
frozen batch weights, recorded branch choices and stored reference regrets.

FULL SOURCE REGENERATION AND INDEPENDENT ENDPOINT CHECK
First generate the both-source provenance chain, using a new output path:

python work/risk_adaptivity_revision/joint_certification/provenance_chain/run_chain.py --cohort all --output-dir outputs/decision_full_chain

Then run:

python work/risk_adaptivity_revision/joint_certification/decision_tolerance_probe/analyze.py --chain-dir outputs/decision_full_chain
python work/risk_adaptivity_revision/joint_certification/decision_tolerance_probe/check.py --chain-dir outputs/decision_full_chain
python work/risk_adaptivity_revision/joint_certification/decision_tolerance_probe/replay_saved.py

The chain root supplies shared/empirical_plans.json, shared/empirical_cases.csv,
original_raw/results/geometry.json and original_raw/prepared/ source records.
Their exact frozen SHA-256 hashes must match protocol.json. Other paths in
that protocol resolve within the release. Its historical run-directory name
records provenance; --chain-dir replaces it, so that directory is not needed.
The full chain uses pinned BLEM source records and bundled external records;
see the parent provenance-chain instructions for download and refitting levels.
This diagnostic itself replays frozen forecasts, not newly fitted models.

The full producer imports decision_replay.py for the endpoint calculations;
its hash is pinned in protocol.json. The independent check.py imports neither
that helper nor the producer. It reconstructs all 65,880 pair/batch intervals
from source-record segment totals, checks exact feasible extremizers and dual
coefficient inequalities, checks 2,196 saved adaptive branch decisions, and
enumerates 6,048 vertex objectives on first/middle/last blocks of each system.
All 57,573 qualified model/threshold checks agree with the stored affine
contrast on the actual source record. This is not a fresh model-fitting check.

The full raw-mode results/block_certificates.json contains original-source
fine answers for internal checking. It is intentionally excluded from both
release ZIP files. The source route recreates it locally. Only the derived
saved_endpoint_inputs.json is distributed. --out selects another producer
folder; use --results on both checkers to read that folder.

Uncertainty
All effects are paired by block. The descriptive 95% intervals use 2,000
synchronized seven-day circular calendar-block resamples, percentile endpoints
with linear interpolation at (n-1)*p, seed 20261015 for original and 20261016
for external. Each day carries all its meters and intraday blocks. There are
three systems per source; these intervals do not estimate a population of
independent systems. Exact rational counts are used before summary display.

Main findings
At epsilon=.01*M2, adaptive/greedy/fixed certify 189/186/188 of 819 original
blocks and 277/277/263 of 279 external blocks. The original adaptive-minus-fixed
effect is 0.12 percentage points (descriptive 95% interval -1.34 to 1.71).
The external effect is 5.02 points (2.51 to 8.60): 14 adaptive-only, 0 fixed-only,
263 both and 2 neither. Twelve of the 14 adaptive-only cases are HPM 2, two HPM 1.
Adaptive offers no primary decision gain over greedy externally, and the
original adaptive-minus-greedy interval includes zero.
The strict-winner comparison remains 123/118/122 original and 207/208/201 external.
The complete grid, including reversals against fixed or greedy, is supplied.

Output map
protocol.json: unchanged pre-analysis choices and source hashes.
analyze.py: full-source exact diagnostic and saved-input export.
check.py: separate full-source mathematical and summary verification.
results/report.json: all source/system effects and bootstrap intervals.
results/case_outcomes.csv: all 38,430 exact rational policy outcomes.
results/saved_endpoint_inputs.json: derived endpoint inputs for bundled replay.
results/independent_check.json: actual full-source verification report.
saved_replay/report.json: actual default replay status and hashes.
saved_replay/all_factors_and_systems.csv: readable full-grid results.
saved_replay/paired_outcomes.csv: four paired outcome cells and intervals.
manuscript_fragment.tex: optional compact retrospective decision table.
