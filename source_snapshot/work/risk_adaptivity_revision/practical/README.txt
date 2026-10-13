Practical certificate evaluation and extended archive comparison
================================================================

Run from the root of the supplied research package with its declared Python
environment. No network access, raw-data reconstruction, or model fitting is
required. NumPy, pandas, SciPy and the original production script dependencies
are required (the package requirements file provides the complete environment).

1. Replay a proposal/certificate gate from frozen public endpoints:

   python work/risk_adaptivity_revision/practical/audit_decision_gate.py --output-dir replay/practical/gate

   Outputs replay/practical/gate/action_ledger.csv, cohort_summary.csv and
   verification.json. Frozen reference outputs remain in practical/results/.
   Observed run: 7.704 seconds including parsing/output; 0.462 seconds for
   40,176 gate calls and ledger columns after parsing. This does not regenerate
   the input endpoints. certificate_gate.py is a small reusable JSON/stdin
   interface accepting lower, upper and proposed_direction (-1, 0 or 1).
   It accepts no reference target and does not authenticate the supplied
   endpoint provenance. The separately supplied practical_api examples cover
   evaluator-input validation, reconstruction and endpoint witness creation.

2. Regenerate the new full comparison grid on the existing additional consumers:

   python work/risk_adaptivity_revision/practical/replicate_archive_grid.py --output-dir replay/practical/replication

   Outputs replay/practical/replication/period_cases.csv, summary.csv,
   run_manifest.json and verification.json. Frozen reference outputs remain
   in practical/replication/. Observed run: 39.35 seconds. The run_manifest records
   the frozen protocol, launch time and input hashes BEFORE computation; its
   status field is the launch snapshot. The subsequent verification.json is
   the completion report and must say passed. The optional --output-dir flag
   writes a separate replay. Results contain all 19,440 declared period cases.

   Required frozen inputs:
   outputs/study_holdout_consumers_predictions.csv
   outputs/study_holdout_consumers_selection.json
   outputs/study_holdout_consumers.json

   Production imports:
   outputs/run_energy_rank_study.py
   outputs/study_period_archive.py
   outputs/study_archive_access.py
   and their bundled source dependencies (including study_recovery.py).

   The additional 30 consumers are not newly untouched. Their six-hour primary
   recovery outcomes had already been inspected. This extension uses the full
   grid fixed in replication_protocol.txt, with no retuning, fresh training,
   outcome filtering, new forecasting architecture, or production outage data.
   Stable high-demand masks are generated from the parsed frozen CSV targets;
   deterministic seed-labelled repeats are retained and are dependent.

3. Independently check the new paired endpoints as whole-period linear programs:

   python work/risk_adaptivity_revision/practical/check_replication_lp.py --replication-dir replay/practical/replication --output-dir replay/practical/independent_lp

   Outputs replay/practical/independent_lp/independent_lp_cases.csv and
   independent_lp_verification.json. The checker reads the fresh grid from
   --replication-dir and never writes to that directory unless explicitly
   selected as --output-dir. Observed original run: 19.86 seconds.
   This checker imports no production bound or closure routine and reads only
   the frozen inputs plus the full-grid output. It checks first/last consumers,
   every gap, mask, block length and total tolerance, and seed 1103: 432 period
   comparisons / 864 LP endpoint solves. It also verifies that the prediction
   file hash matches the original archived model run. It does not independently
   refit forecasts or independently solve the separate-loss quadratic minima.

   The frozen report's script_sha256 refers to the original execution source,
   retained byte-for-byte as replication/check_replication_lp_recorded.py.
   That file is an archival source snapshot, not the replay entry point. The
   current entry point adds only output/input directory flags and removes an
   unused import; its mathematical calculation is unchanged. A fresh run
   records the current entry point's hash in its new completion report.

Result interpretation
---------------------
The original exact-total Portugal gate allows 7,836/9,720 donor proposals
with paired bounds, compared with 2,513/9,720 with separate-loss bounds.
The 73.86% reduction is in unresolved certificates (7,207 to 1,884).
All donor proposals in this primary archive grid are correct at the observed
reference. An unresolved sharp interval nevertheless admits an opposing
completion. The ledger identifies its endpoint but does not export full
witness vectors; the practical_api worked examples do so separately.

The new extended grid certifies 7,753/9,720 versus 2,527 with exact totals,
and 7,424/9,720 versus 2,010 with 5% total tolerance. No issued certificate
has a wrong sign against the reference, and no separate-only certificate
occurs. These counts describe retrospective certificates under constructed
outages and declared archive access. They do not measure deployment actions,
time saved, labor saved, retrieval costs, forecast accuracy improvements,
or an adaptivity advantage on the real traces. The historical 0.97% reading
saving is not altered or redefined by this analysis.

Reproduction comparison
-----------------------
CSV numeric results, scenario keys, method counts and source hashes should
agree with the saved reports within the declared tolerances. Timings,
timestamps, absolute paths and platform-specific floating-point formatting
can differ. Byte-level CSV hashes are recorded as provenance for this run;
they are not a claim that every platform produces identical CSV serialization.
The immutable protocol, run inputs and scripts are separate from completion
reports so that replay timing cannot be mistaken for a new pre-analysis plan.
