EXTERNAL FIXED-DEADLINE REVISION: THREE REPRODUCTION LEVELS

Run commands from the extracted supplement root. Use Python 3.12 and the
pinned environment in outputs/requirements-study.txt:
  python -m pip install -r outputs/requirements-study.txt

Each wrapper invocation creates work/external_replay_<UTC timestamp>/.
It preserves original distributed files. Its final machine-readable report
is outputs/external_revision_reproduction.json within that isolated tree;
the command prints its complete path. Per-step logs and elapsed times are
kept there. No command submits a manuscript or compiles a PDF.

1. SMALL VERIFICATION: NO EXTERNAL DATA OR LARGE DOWNLOAD

  python work/reproduce_external_revision.py --small

This stages code only and checks analytic/enumerated acquisition examples,
compact-versus-finite optimization, the secondary-policy example, causal
forecast features, leakage/cost corruption fixtures, and 150 complete
synthetic five-policy trajectories. A separate five-policy multistage
regression checks that later reveals cannot modify earlier snapshots.
It does not inspect real test outcomes. The original small-check component
completed in about 19.9 seconds in an isolated run after the timestamp
correction; the final report records both components' actual times.

2. HEADLINE REPRODUCTION FROM FROZEN FORECASTS AND RECOVERY TRACES

  python work/reproduce_external_revision.py

This runs the small checks, independently verifies selected literal London
source rows against hourly references, and reconstructs every validation
and test trajectory's information, bounds, decisions and charged requests.
The independent checker imports none of the forecast/evaluator/acquisition
implementations. It reconstructs all five summary tables, B80, its baseline
comparison and the predeclared practical criterion. It also checks feature
arrays, chronology, early/later archive counts and copy provenance.
For the distributed runs, every repaired trace is compared to its preserved
original and the logging-only alias correction is independently checked.

The code then restores distributed verifier-report bytes in the disposable
copy and executes work/build_external_manuscript.py. The generated TeX must
match the supplied final manuscript's SHA256 exactly. Fresh verification
reports are retained inside the wrapper result before that restoration.

This is a replay from frozen forecasts and selected batches. It does not
fit forecasting models again or claim independent reimplementation of
their learning algorithms. It does not measure fresh acquisition planning
runtime: the distributed timing observations remain the reported ones.
The independent checks do not prove policy optimality on every new case;
the mathematical results and separately enumerated fixtures support that
claim. The first complete independent validation and test checks took
512.6 and 363.7 seconds, respectively, on the study machine. Thus the
sequential default route should be budgeted for roughly 15 minutes plus
source, small-check and manuscript work on that machine; the actual clean
replay report records every step. Hardware and dependency versions affect
elapsed time.

To additionally rerun fitting and acquisition from the bundled quality-
filtered hourly references:
  python work/reproduce_external_revision.py --refit

This runs new causal preparation, all 60 fits for 20 selected households,
validation/test acquisition, summarization and independent verification in
the disposable workspace. Distributed fitted/validation/test directories
are retained beside the fresh outputs as *_distributed_reference. Fresh
outputs do not silently replace the manuscript tables and this mode does
not regenerate the manuscript from changed outcomes. It does not require
the 8.54GB full raw CSV. Floating-point and LP tie selection can vary across
platforms; inspect the fresh reports rather than assuming byte identity.

3. OFFICIAL RAW SOURCE, FRESH FITTING AND ACQUISITION

Download the official London Datastore archive into a separate cache:
https://data.london.gov.uk/download/vqm0d/3527bf39-d93e-4071-8451-df2ade1ea4f2/LCL-FullData.zip

Its frozen SHA256 is:
68a35598cc8e70898a7651c482216fb096a0a6910c2d180c616632dfc7a9b014
ZIP size: 801,674,949 bytes. Its member CC_LCL-FullData.csv is 8,542,818,238
bytes. The ZIP uses Deflate64, so an ordinary Python zipfile installation
does not suffice for extraction. Install/use a 7-Zip-compatible command:
  7z x /path/to/cache/LCL-FullData.zip -o/path/to/cache/extracted

Then run:
  python work/reproduce_external_revision.py --raw --raw-archive /path/to/cache/LCL-FullData.zip --raw-csv /path/to/cache/extracted/CC_LCL-FullData.csv

The wrapper verifies BOTH frozen full-source hashes, reparses all source
rows, reapplies the training-only household selection and quality rules,
and requires reconstructed hourly references to match their frozen hash.
It then performs the same fresh fit/acquisition route above. Source files
are read-only. The 7-Zip binary and large full raw files are not included.
This route requires substantially more disk, memory and time than replay;
the completed original source manifest records its measured preparation
time. Fresh full-source extraction/refitting is not claimed merely because
the smaller bundled literal-source verifier passed.

INFORMATION AND SOURCE LIMITS

The independent source ultimately used is Low Carbon London. A prior REFIT
source-only inventory yielded no households under its strict complete-
support rule. That infeasibility, the source-only switch and all amended
dates are preserved; no REFIT forecast/acquisition outcomes were used to
choose London. The London source contains half-hour kWh readings, while
temporal six-hour totals, outages and issue/cutoff timing are constructed
benchmark inputs. Its clock labels are assigned to a UTC-shaped benchmark
coordinate; physical UTC, interval-start orientation and production arrival
times were not independently verified. No actual/estimated source flag is
available. These are energy-reference comparisons, not measured selective
retrieval savings in an operating utility.

Validation uses a surrogate scale calibrated from the complete validation
window, so its acquisition replay is a retrospective feasibility diagnostic.
The scale is frozen before the test. Both preserve the same fixed 80%
coverage criterion. Conditional curves retain initially non-certified ties
in their denominator. There is no post-test coverage-target tuning.

IMPLEMENTATION CORRECTIONS AND PRESERVED HISTORY

A first forecast execution failed before any archive/acquisition outcomes
were emitted: pandas 3 retained microsecond-resolution integer dates where
the saved-array name/reader assumed nanoseconds. Its three partial fits were
discarded, serialization was made explicitly nanosecond-based, and a
round-trip fixture was added before the complete run. This was an input-
serialization correction; model parameters and experimental criteria did
not change. Preserved diagnostics distinguish failed development execution
from the final complete fit. The independent checker reconstructs dated
arrays from source-hourly timestamps and cannot accept the 1970-date error.

The first independent trajectory replay also identified a logging alias:
an intermediate stage's saved posterior-observation array was mutated by
the following stage's paid reveals. The actual next-stage prior state,
query choices, paid costs, bounds and outcomes were stored correctly. The
logging assignment now takes an explicit array copy. Original compressed
traces, original execution reports and the executed evaluator source are
preserved; trace_logging_repair.json pins their hashes and records the
correction. The independent checker compares every original and repaired
record, permits changes only to the affected posterior snapshots, and
requires each original discrepancy to be exactly explained by the next
batch's recorded reveals. It separately reconstructs every repaired
snapshot from the preceding state, current paid reveals and aggregate
closure. All numerical outcomes and experimental input hashes must remain
unchanged. This is a disclosed trace repair, not a second experiment or a
change to model/policy parameters after inspecting outcomes.

HISTORICAL MATERIAL AND WHAT IS FRESHLY CHECKED

The new command does not repeatedly execute the earlier long historical
suite. The predecessor 274-file release is pinned by SHA256
81b0ea77c4124fc3a71b9695a99483fe440886d9403e1383d549d44683422be7.
Its preserved work/external_deadline/prior_release/supplement_delta_verification.json
records the passed full baseline plus explicitly checked additive delta.
The final package's delta report identifies byte-identical carried-forward
members and the newly executed checks. A hash match establishes unchanged
bytes, not a fresh independent execution of the old experiments.

For the separate original historical reproduction/refit routes retain:
  python work/reproduce_final_revision.py
  python work/reproduce_final_revision.py --fresh-refit
Their existing documentation distinguishes bundled UCI reconstruction from
BLEM raw-source regeneration and its redistribution limits. Those commands
reproduce the pre-external manuscript, not the new external revision.

NAVIGATION

experiment_protocol.txt, period_amendment.txt, source_amendment.txt:
  Preserved pre-outcome design and source-only changes.
source/lcl_protocol.txt and source/lcl_clock_amendment.txt:
  Source cohort, quality and clock conventions.
data/lcl/selection.json, household_inventory.json, daily_quality.csv:
  All 100 considered IDs, training-only selection and day exclusions.
config.json and fitted/frozen_config.json:
  Original preparation config and its saved copy. Both are required because
  prepared.json pins the original config path/hash. Keep them in the package.
fitted/forecast_archive.csv, candidate_days.csv, reference_targets.csv:
  Issued predictions, all eligible/ineligible dates, separate reference data.
validation/ and test/:
  Every trajectory, archive snapshot, case row, summary and verification.
review/verify_external.py:
  Independently written arithmetic/chronology/accounting replay.
reproduction/CLAIM_TO_EVIDENCE.txt:
  Exact claim boundaries and executable evidence routes.

All reported paths above are relative to work/external_deadline/ unless
they begin with work/ or outputs/. Protocol-path rebasing in the wrapper
always targets the current extracted workspace, never an old checkout.
