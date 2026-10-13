COUNTER PRECISION STUDY -- CURRENT EXECUTABLE ENTRY

From the extracted supplement root (Python plus requirements.txt):
  python work/risk_adaptivity_revision/counter_adaptive/reproduce_counter.py

An existing raw cache can be supplied with --data-dir PATH. Otherwise only the
three pinned BLEM source files are downloaded. The helper writes a NEW output
tree; no archived result or manuscript input is overwritten. It reconstructs
the exact hourly endpoint interface, regenerates the omitted daily persistence
copies, and retains the existing ridge/boosting/MLP forecasts. No model refit,
UCI download or change to the old acquisition experiment occurs.

Read reproduction_report.json for the actual exit statuses. The fresh results
directory contains geometry.json, protocol_manifest.json, replay_cases.csv,
query_trace.json and numerical reports. Its summary directory reproduces the
current three counter tables, complete precision curves, per-meter/pair/phase
results and every policy comparison. Raw counter-dependent coefficients and
query answers are generated locally, not redistributed in this ZIP. Source
URLs, commit and SHA256 checks are in work/data_prepare_blem.py. The source
article's open-access status is not asserted to license the raw repository.

Declared protocol: protocol.txt, frozen before this study's geometry/replay.
Read information_flow_clarification.txt for the per-audit input boundary:
shared preprocessing reads endpoint tables, while each policy is restricted
to its own permitted inputs and previously queried answers. The code does
not claim physical file isolation. The frozen protocol is retained unchanged.
The source used for initial geometry is study_protocol_execution_v1.py; the
final entry study.py adds input hash gates and exact rational second-query
selection. implementation_amendment.txt records the change after preliminary
pilot replay; both panels were rerun without changing any threshold or task.
The primary threshold remains0.5W0. All4914 tasks and all five thresholds are
reported. The internally set10% primary prevalence target was not met.

Proof and constructed example: literature/counter_methods.tex and math_review/.
The independent geometry checker recomputes every original-coefficient envelope
and every adverse-profile upper certificate with rational arithmetic and solves
independent finite games and endpoint LPs. It imports no study.py policy code.
Independent raw-register replay can also be invoked on a regenerated results
directory, replacing PATH below:
  python work/risk_adaptivity_revision/counter_adaptive/math_review/check_replay.py PATH --data-dir RAW_CACHE --output outputs/counter_independent_replay.json

Original execution:
  pilot1080 plus continuation3834 tasks; geometry59.1+199.3s;
  final raw replay5.1+13.0s; full independent geometry75.5+167.7s;
  independent raw replay5.9+13.9s. These are single shared-host runs and
  depend on the environment; allow roughly5--10minutes for full regeneration.
The three counters provide819 physical block snapshots; pairs reuse them.
Each policy has a separate two-register budget per pair/block. They do not
constitute4914 independent meters or a shared four-model selection budget.

Current measured result:
 4661/4914 all-completions adaptive half-width guarantees.
 290/4914 (5.90%) guarantee success1 while every randomized batch has worst-case
 success <=1/2. All3meters and6pairs contribute cases. Recorded subset success:
 adaptive100%; best deterministic worst-width batch97.2414%; mean-optimal
 randomized batch80.0128%; greedy adaptive96.2069%; uniform41.7931%.
 Overall adaptive98.6365% versus deterministic98.2295% (0.4070pp).
 No claim of large universal observed gains, field costs or minimum requests.

The main supplement's default reproduce.py additionally checks the constructed
counter example and bundled ledger consistency. It does NOT download raw
counters; use the dedicated command above to freshly recompute this empirical
study. verify_packaged.py checks the bundled reports without claiming raw replay.

EXACT HALF-OPTIMUM DIAGNOSTIC AND THREE WITNESSES (POST-ANALYSIS)
After raw regeneration, replace GEOMETRY with the printed new results/geometry.json
and RAW_CACHE with the source directory (work, if it contains the pinned files):
  python work/risk_adaptivity_revision/counter_adaptive/math_review/check_half_cover.py --geometry GEOMETRY --data-dir RAW_CACHE --output outputs/counter_half_cover.json
This independently reconstructs exact covering intervals and adverse weights for
all290 cases. The continuum lower guarantee and finite adversarial upper bound
both equal1/2. Distribution: minimum, quartiles, median and maximum all1/2;
290exactly1/2;0below40%,30%or20%. The theorem is math_review/batch_half_structure.tex;
all290witnesses and the3earliest-meter examples are in half_cover_verification.json.
The three readable sufficient switches are1/4,1/2,3/4. They need not be the full
conditional-width-minimizing rule used in the prespecified replay.
The constructive precision-optimal mixture is nonunique. Its optional75.3448%
recorded success is a separate post-analysis diagnostic of this particular
fixed cover/tie rule, not the best observed success over all optimal mixtures.
It is not substituted into the original baseline comparisons or primary study.
