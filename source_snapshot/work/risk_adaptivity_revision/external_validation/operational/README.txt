EXTERNAL PUBLIC-API OPERATIONAL VALIDATION

Actual completed work
=====================
Protocol/source selection: protocol_lock.json and PROTOCOL.txt, fixed before
external forecasting or treatment outcomes; IDs 1,2,7 are unchanged.
Source: HeatpumpMonitor.org public stored cumulative electricity-kWh feeds,
CC BY 4.0; source metadata/caches and retrieval records are in the sibling
work/risk_adaptivity_revision/external_heatpump directory.

Fresh unchanged model fits: fresh_fits_20261012/training_report.json.
Jan--Jun 2025 training, July 2025 test; 2,232 forecast rows across 93 issue
days. Fixed daily persistence/ridge/HGB/MLP specifications; no tuning,
retries or replacements. All fits completed without convergence warnings.
MLP epochs were 392,279,344. Fitting took 22.735 seconds in this environment.
The model fitting is chronological in the provider's API-grid order; native
measurement/arrival times are unavailable. It is not a verified production
midnight-deployment experiment. See IMPLEMENTATION_NOTE.txt and the source
TIMESTAMP_INTERFACE_NOTE.txt for the distinction.

Actual HTTP benchmark: http_benchmark_20261012/.
30 policy trials, three earliest pre-answer eligible daily-versus-MLP tasks,
two repetitions per task/policy, 60 total actual public requests including
the six common endpoint reads. No prototype server, simulated latency,
per-reading tariff, private API or author/journal contact was involved.
All five policies reached half-width precision on these three tasks.

Observed mean incremental API I/O (excludes logged client rate-limit wait):
  exact adaptive        0.496509 seconds, 2 requests, 104.333 body bytes
  fixed minimax batch   0.539298 seconds, 2 requests, 104.667 body bytes
  mean-optimal batch    0.581857 seconds, 2 requests, 104.333 body bytes
  greedy adaptive      0.551294 seconds, 2 requests, 104.333 body bytes
  full hourly range    0.331244 seconds, 1 request,  226.667 body bytes

These observations favor the provider's full-range interface on request count
and API I/O time for this small workload. The approximately 122-byte selective
body reduction is small in absolute terms, excludes HTTP/TLS overhead, and is
not a measured monetary saving. Full recovery returns all seven hourly grid
samples including retained endpoints; a five-interior-point response could
reduce its incremental body size further. No selective benefit is attributed
to the two redundant endpoints. A one-request full range also supplies the
initial endpoints for an end-to-end audit, whereas selective end-to-end
acquisition needs the separately recorded endpoint reads.

Mean completion time including the imposed one-request-per-second throttle
was 1.984212 seconds for adaptive and 1.039547 seconds for full range. These
client-throttled completion times are not intrinsic provider latencies.
Both measurements, every request, and per-case medians/ranges are retained.
The three cases do not support a precise population speedup confidence claim.

Verification
============
verify_http.py reopened the original independently cached July JSON and
reconstructed the exact expected body for all 60 HTTP responses. Every
reconstructed payload SHA256 matched the actually received payload hash.
The checker independently evaluated all 12 adaptive second-query choices,
checked all request/sample budgets, and verified that all 30 terminal
intervals contain the cached reference loss contrast. Maximum containment
discrepancy was 1.735e-18. See http_benchmark_20261012/verification.json.
Transport offline unit tests passed (two tests); they are not service results.

What each file reproduces
=========================
train_external.py: fresh fitting with explicit external calendar and unchanged
  architectures; predicts when past features are available regardless of
  current target completeness. No network access.
measurement.py: actual read-only public HTTP instrumentation, persistent
  connections within trials, a strict request cap, logged throttle waiting,
  payload sizes/hashes and request CPU time. No retries or cache-busting.
benchmark_http.py: freezes timing case IDs and balanced policy order before
  optional replies. Default is plan-only; --execute makes the actual GETs.
verify_http.py: network-free source-hash/interval/budget verification and
  descriptive policy/per-case timing summaries.
test_measurement.py: offline transport-accounting/guard tests.
fresh_fits_20261012/: frozen forecasts, calendar ledger and training report.
http_benchmark_20261012/: plan, actual logs, all trials, setup measurements,
  result summary, independent checks and descriptive aggregate CSVs.

Commands (from the supplement/workspace root)
============================================
Replay verification without making public requests:

  python work/risk_adaptivity_revision/external_validation/operational/verify_http.py --benchmark-dir work/risk_adaptivity_revision/external_validation/operational/http_benchmark_20261012

Refit unchanged models into a NEW directory:

  python work/risk_adaptivity_revision/external_validation/operational/train_external.py --counter-csv work/risk_adaptivity_revision/external_heatpump/hourly/train_test_hourly_counters.csv --output-dir NEW_FIT_DIRECTORY

Write an offline timing plan into a NEW directory:

  python work/risk_adaptivity_revision/external_validation/operational/benchmark_http.py --forecasts NEW_FIT_DIRECTORY/frozen_forecasts.csv --counter-csv work/risk_adaptivity_revision/external_heatpump/hourly/train_test_hourly_counters.csv --output-dir NEW_PLAN_DIRECTORY

Add --execute to that last command only when intentionally repeating public
traffic in a new directory. It makes up to 60 read-only GETs, limited to one
request start per second. Do not automatically rerun live timing as part of
every package check. Public latency/cache state and timestamps will differ.

Limits
======
The exact target is a stored API-grid cumulative difference, not a verified
native clock-hour physical energy amount. Public metadata does not establish
direct raw-register provenance, historical interpolation settings or exact
physical metering error. The API-grid causality check does not verify native
measurement availability at midnight. Quantization/physical-error extensions
require their separately declared measurement model; exact stored-sample
claims cannot silently be promoted to physical guarantees.
Request CPU is measured; total optimizer CPU is not separately captured in
this execution (planning wall time is). Response-body bytes exclude TLS and
packet overhead. Selective request count is per pair; system-wide comparisons
must share retrieved readings across model pairs. No journal acceptance
probability or production monetary saving follows from this benchmark.

Optional numerical comparison after the fresh-fit command:
  python work/risk_adaptivity_revision/external_validation/operational/compare_fresh_forecasts.py --candidate NEW_FIT_DIRECTORY/frozen_forecasts.csv --output outputs/external_fresh_fit_comparison.json
This verifies 2,232 rows and 8,928 forecast values using atol=1e-10, rtol=1e-8.
No refitting or network access occurs in the comparator. The independent
fresh process within this study matched all four saved prediction columns
exactly; this is not a claim of external human or implementation validation.
