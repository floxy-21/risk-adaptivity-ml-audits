ONLINE RESOURCE 1: EXECUTABLE RESEARCH SUPPLEMENT
Article: Risk and Adaptivity in Certifying Machine-Learning Model Comparisons
Journal target: PeerJ Computer Science
Author/correspondence: Jishan Kapoor, kapoorjishan19@gmail.com
Affiliation: Independent Researcher, Toronto M4Y 1C9, Canada

CURRENT PAPER -- ONE ENTRY COMMAND
  python work/risk_adaptivity_revision/reproduce.py

REVIEWER QUICK START
Extract both publisher ZIP files into the same empty directory. All commands
below start from that root. Use a disposable extraction for focused commands;
the full replay creates its own isolated stage.

1. Inspect the central proof without an optimization solver (Python stdlib):
   python -S work/risk_adaptivity_revision/two_target_boundary/verify_boundary.py --solver-free --output outputs/two_target_exact.json
   python work/risk_adaptivity_revision/joint_certification/proof_check_joint.py
   python work/risk_adaptivity_revision/joint_certification/check_main_inspectable_certificate.py
   These check the fixed-budget two-target boundary, the shared-prefix
   construction, and the printed external witness.
   They do not regenerate the forecasts or all empirical cases.
   The independent LP check of the new boundary is also in the full replay:
   python work/risk_adaptivity_revision/two_target_boundary/verify_boundary.py --output outputs/two_target_lp.json
2. Reproduce the current paper offline after installing the pinned environment:
   python -m pip install -r requirements.txt
   python work/risk_adaptivity_revision/reproduce.py
   Allow about 20 minutes on the study host. The driver validates source hashes,
   replays bundled external inputs and all-panel derived results, and rebuilds
   the manuscript. It does not refit models or download original BLEM inputs.
3. Reconstruct both source panels with their frozen forecasts:
   python work/risk_adaptivity_revision/joint_certification/provenance_chain/run_chain.py --cohort all --output-dir complete_source_chain
   This downloads three version-pinned BLEM source files unless --raw-dir points
   to a valid local cache; the output directory must not already exist. Source
   hash mismatches fail. It regenerates policies, certificates and table rows
   for both panels, without refitting models. Read the chain README for scope.
   A fresh single-invocation run with no producer-reuse flags is recorded in
   joint_certification/provenance_chain/executed/fresh_both_panel_replay_20261014.json
   under work/risk_adaptivity_revision. It reconciled all 1,098 ledger rows
   exactly and regenerated the 165 original / 57 external half-success cases.

Start with work/risk_adaptivity_revision/CURRENT_RESULTS_MAP.txt for a direct
table-by-table and claim-by-claim map of the current revision: commands,
inputs, outputs, validation fields and any raw-source requirements.
The final_challenger_diagnostics folder supplies the exact three-way guarantee
classification, the greedy-first-query check, and a fixed-fallback comparison.
Its default replay checks both panels' saved certificates and derives the
external panel's inequalities; the original derivation uses the raw route.
The final_practical_figure folder contains the geometry/replay figure, its exact inputs and a
solver-free checker. Both additions are included in the default replay.
The map separates current results from optional historical development.
The main paper is shortened; full current methods and controls remain in
editorial/online_extended_methods.tex (S1 scaling; S2 historical gates and
controls; S3 data/forecast protocol; S4 historical grid; S5 full compact
construction; S6 extended counter checks, measurement proofs and full
counter replay; S7 detailed computational verification; S8 shared-query
proofs, paired outcomes and protocol selection; S9 scalar examples and the
complete growing-family proof; S10 general-polytope algorithms). Its own reference
list includes every work cited in those supporting sections.

CURRENT SHARED-BUDGET RESULTS -- PUBLIC OFFLINE ROUTE
All commands below are included in the current default replay. It preserves
the earlier checks and adds source-to-forecast linkage, input-mismatch guards
and the absolute-width example. Read the final execution
report for completion; a configured job count is not evidence that it ran.
  python work/risk_adaptivity_revision/joint_certification/empirical_shared_audit.py
  python work/risk_adaptivity_revision/joint_certification/empirical_check.py
  python work/risk_adaptivity_revision/joint_certification/independent_shared_review.py
  python work/risk_adaptivity_revision/joint_certification/precision_batch.py
  python work/risk_adaptivity_revision/joint_certification/precision_batch_check.py
  python work/risk_adaptivity_revision/joint_certification/precision_adaptive_link.py
  python work/risk_adaptivity_revision/joint_certification/empirical_precision_replay.py
  python work/risk_adaptivity_revision/joint_certification/independent_precision_replay_check.py
Defaults use only the 279-block external panel and bundled public frozen
geometry/counter inputs. All six model pairs share the same two readings.
The original 819-block numerical summaries and paired ledgers are supplied as
derived results; their original raw geometry and register responses are not
redistributed. Full raw regeneration remains the separately documented route.

Capacity, bounded-error and paired-outcome commands are indexed in
CURRENT_RESULTS_MAP.txt and joint_certification/README.txt. Capped records
that violate the declared capacity are retained and flagged, not presented
as valid cap-based replay outcomes. The complete cap/error control remains
in the paper. Saved exact noisy certificates are checked with the standard
library; re-solving every robust LP is optional. Paired bootstrap intervals
resample synchronized seven-day calendar blocks, with a one-day sensitivity,
and describe only these fixed panels. They do not measure deployment savings.

INTERFACE-AWARE ACQUISITION
  python work/risk_adaptivity_revision/protocol_selection/selector.py --output-dir protocol_selection_replay
The reference selector checks 29 existing certificate cases under four
declared interfaces (116 decisions). Bulk availability, scalar readings,
information rounds and transport requests are explicit and distinct.
See protocol_selection/README.txt for dispatch callbacks and checks.
For a task-bound request/response interface, use protocol_selection/bound_workflow.py.
APPLICATION_WORKFLOW.txt supplies worked saved comparisons and the envelope schema.
The default reproduction command also checks all 29 contrast vectors against
frozen geometry, verifies forecast hashes, reconstructs 58 retained endpoints,
and exercises rejected task, interface and response metadata. These are
software and provenance checks, not new empirical gains or device calibration.

READING VERSUS FEEDBACK COST
  python work/risk_adaptivity_revision/protocol_selection/cost_frontier.py --output-dir outputs/cost_frontier_replay
  python work/risk_adaptivity_revision/protocol_selection/INDEPENDENT_COST_CHECK.py --results-dir outputs/cost_frontier_replay --output outputs/cost_frontier_check.json
These commands are included in the current full replay. The exact
declared-cost analysis exports 174 case/ratio choices and checks 306 candidates.
It identifies when feedback is worth its extra information round while keeping
the same assurance. It does not estimate monetary savings or new API timings.

NEW COUNTER STUDY -- ONE RAW-SOURCE ENTRY COMMAND
  python work/risk_adaptivity_revision/counter_adaptive/reproduce_counter.py

This rebuilds all 4,914 cumulative-counter tasks from the three pinned original files,
using frozen forecasts, and checks the reported primary guarantees and replay.
An existing cache may be supplied with --data-dir PATH. The code generates raw-
dependent geometries and queried answers locally. Read counter_adaptive/README.txt
for paths, exact commands, runtimes, information scope and numerical treatment.
The original 13-step full replay is retained in executed/full_clean_replay.json;
its scope predates the counter addition. New fresh replay records are separate.

Extract the ZIP first. Use Python 3.12 and install requirements.txt (identical
scientific environment to outputs/requirements-study.txt). The tested host is
Windows 11; old optional workflows may rely on Windows conventions. The current
command verifies every distributed file against MANIFEST.sha256, copies the
package into a new isolated directory, and executes the classification checks,
general-polytope LPs, dual-completion checks, paired solver-table reconstruction,
public whole-period endpoint analysis, and independent historical tie-policy
checks. The practical and constructed jobs in work/risk_adaptivity_revision/replay_jobs.json
rerun the pair gate, four-model selection, extended30-consumer grid, two
independent bound checkers, actual-input audit examples, constructed counter checks, counter ledger consistency and exact feedback-triage
certificates/recommendations, precision-cover diagnostics, bounded-error checks,
cap sensitivity, stored-readout error sensitivity, exact upper and lower
certificates, the two-or-three-reading fallback and its executable rational
branches, source qualification, cached new-source replay
and cached HTTP-trace verification.
Their fresh ledgers
must match the archived scientific entries within the stated tolerances.
The command finally reconstructs the exact
current editable manuscript. It performs no model training; an audit hook blocks
network calls in every default replay subprocess. The original BLEM raw-source
route remains separate. Public new-source caches are bundled and replayed offline.

For mathematical checks only:
  python work/risk_adaptivity_revision/reproduce.py --small

CERTIFIED 29-CASE BUDGET FALLBACK
The separate post-analysis fallback retains the 1% internal-readout allowance
and original precision target. It certifies all 29 external cases using two
readings in 22 cases and three in seven: 65 summed hard reading allowances
versus 87 for guaranteeing nonadaptive batches. This does not change 22/29
under a two-reading budget or claim measured API savings. The executable
policy uses exact rational branching with no online LP. Its proof, code,
checks and regeneration commands are in
work/risk_adaptivity_revision/external_validation/stored_error_fallback/README.txt.

Individual entry points and archived runtimes are documented in math/README.txt,
general/README.txt and dual/README.txt below work/risk_adaptivity_revision.
The classification check took about11seconds, the general-polytope suite under
one second, and the80-case dual check about32seconds on the available shared
host. The default also parses historical empirical traces and checks2,148
secondary LPs. The preceding 63-step replay took about 21 minutes on the study
host; allow roughly 20--30 minutes plus extraction/copying time for this 69-step
revision. Runtime varies with hardware and storage; consult the release log
for the actual measured final duration.
These are planning descriptions of observed runs, not universal runtime bounds.

PREVIOUS PAIRWISE COUNTER EVIDENCE
Before retrieving optional registers, the complete decision rule identifies
4371 tasks where a fixed batch suffices,290 where feedback is essential and
253 without a deterministic two-query guarantee. All290 feedback-essential
cases attain the exact randomized-batch success bound1/2. The post-analysis
fallback avoids sequential feedback in4371 cases while preserving primary
precision success pointwise; it does not reduce the two-reading count.
See counter_adaptive/feedback_triage/README.txt for exact commands and scope.

The complementary historical outcomes are:
* The additional30-consumer grid certifies7753/9720comparisons versus2527using
  separate-loss bounds (exact totals), and7424versus2010at5%total tolerance.
* The original archive certifies933/1620donor-selected models against allthree
  alternatives versus167with separate-loss bounds:52.72%fewer unresolved cases.
Both use zero additional readings. These are all-completions historical
certification gains, not improved donor accuracy or measured production savings.
The30consumers were previously examined; the extended grid is a fresh computation
from frozen forecasts, not an untouched-data claim. Practical scripts and
limits are documented in practical/, practical_multi/ and practical_api/.

The wrapper retains fresh reports in outputs/risk_clean_replay.json and per-step
logs. Timing, machine metadata, LP witnesses or dual solutions can vary between
runs. Compare the stated numerical tolerances and counts, not fresh JSON byte
hashes. Frozen manuscript inputs are restored only after the fresh reports have
been retained, and the final manuscript must exactly match the SHA256 recorded
in outputs/risk_release_manifest.json. No output is silently substituted for a
failed run. The manifest gives expected hashes for every frozen source/output.

REPRODUCTION LEVELS
1. Current mathematical/empirical replay: command above. Uses bundled forecast
   records/endpoints. The public certificate-grid replay includes60,264 matched
   comparisons;5,832 BLEM counter comparisons require raw-source regeneration.
   The comparative timing table replays archived measurements; it does not rerun
   the28-process scaling experiment or claim repeated timing estimates.
2. Previous complete experimental package: restore its exact file layout with
     python work/risk_adaptivity_revision/restore_previous_package.py --destination work/previous_release_copy
   Then follow the restored README.txt. All previous scientific members remain
   byte-identical; only the current main source and top-level README are replaced
   in this release, with their old versions preserved. This route includes the
   old acquisition experiment and its unchanged0.9738064% household-average saving.
   Its denominator and uncertainty calculation have not changed.
3. Raw inputs and fresh fitting: the restored previous README and
   work/certificate_grid_review/README.txt distinguish raw UCI reconstruction,
   BLEM download/regeneration, saved-forecast replay, and fresh model refitting.
   Those network/training steps are not claimed as fresh executions by the
   current default command. Historical completed fitting checks are archived
   with their original scope and hashes. No raw BLEM traces are redistributed.

SCIENTIFIC SCOPE
The universal classification is proved algebraically. Numerical checks cover
constructed examples and declared polytope/aggregate fixtures; they are not a
numerical proof for every convex set. Dual certificates are binary64 numerical
witnesses with reported feasibility and pricing gaps, not outward-rounded formal
certificates. Synthetic risk separations are not empirical forecasting gains.
All historical adverse outcomes are retained. Review notes are not external
independent replication. No manuscript has been submitted by this package.


Frozen task-binding checks run before the external replay regenerates geometry.json.
The driver rejects a frozen-input check scheduled after a mutating regeneration job.
Regenerated scientific ledgers are still checked before frozen inputs are restored.


FINAL-REVIEW SYSTEM EFFECTS AND DEPENDENCE CHECKS
  python work/risk_adaptivity_revision/joint_certification/final_review_analysis.py
  python work/risk_adaptivity_revision/joint_certification/final_review_check.py
Default jobs: final_review_dependence and final_review_independent. These two
checks use the bundled full-panel derived outcome ledgers, without original
raw data, new forecasts, policy changes or retuning. Seven-day intervals remain
primary. The additional fourteen-day synchronized circular-block sensitivity
and leave-one-system-out comparisons retain the declared original precision
threshold and actual capacity-compatibility flags.
Outputs: joint_certification/final_review_results/{report.json,system_effects.csv,
dependence_sensitivity.csv,draws.json,precision_catalog.json,main_system_table.tex,
supporting_dependence_table.tex}; independent report final_review_independent.json.
Fresh wrapper outputs: outputs/final_review_dependence/ and
outputs/final_review_independent.json. The main system table is
tab:joint_system_effects; S8 reports tab:joint_long_dependence.
Full-panel precision counts classify closed-zero, closed-half, closed-one and
open-gap bounds separately from the overlapping fallback-policy classification.
The independent checker recounts all 1,098 derived precision records and checks
116 temporal/system-omission comparisons. Archived full coefficient-only plans
were matched before these derived summaries were frozen; public replay does
not claim to reconstruct original raw-dependent plans.

INSPECTABLE SHARED-QUERY RESULT
The main theorem and worked real-data certificate are verified without an optimizer.
See joint_certification/INSPECTABLE_CERTIFICATES.txt for the four-command chain.
  python work/risk_adaptivity_revision/joint_certification/check_main_inspectable_certificate.py
This default step checks the actual printed real-data coefficients, outward
enclosures, branch coverage, 36 covering multipliers and matching adverse records.
Output: joint_certification/main_inspectable_certificate_check.json.
The existing proof_check_joint.py verifies the constructed mean-risk theorem;
precision_batch_check.py and precision_adaptive_link.py check all 279 external
inputs and recover the 57 exact-half guarantees. Original-panel certification
requires the separately documented raw-source regeneration route.
