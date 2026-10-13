Acquisition protocol selection
==============================

Purpose
-------
The acquisition interface determines which research guarantee is useful.
This small offline deployment component checks that interface explicitly and
chooses among existing certified protocols. It prevents a restricted-query
advantage from being presented as a reason to avoid a faster available bulk
export. It is an integration of proven guarantees, not a new optimization
theorem, a deployed service or new empirical evidence of adaptive superiority.

The uncertainty model and threshold are unchanged from the 29 external-case
stored-error study: six nonnegative true increments, exact retained endpoint
total E, fixed hidden internal stored-readout errors bounded by 0.01E, and
required width <=0.5 of the initial width. The allowance is declared and has
not been calibrated to the physical meter. Only certified existing cases are
supported; a new case requires its own checked mathematical certificate.
Selection is complete only over the supplied candidate certificates. An
escalation alone is not proof that no other protocol could work. The seven
two-query impossibility statements additionally use the exact lower witnesses.

The interface manifest states which boundaries are permitted, whether bulk,
fixed or answer-dependent acquisition is admissible, a maximum number of new
scalar readings, a maximum number of information rounds, transport grouping,
and the preference used to select among admissible certified protocols.

A scalar reading is one new stored internal prefix value. An information round
is one group of queries selected before receiving that group's answers. HTTP
requests are transport transactions. These three counts must not be conflated:
a fixed batch may use three HTTP requests in one information round; a range
export may return five new values in one request and one round. Unknown
transport counts stay null and cannot be used as optimization costs.

Frozen four-scenario evaluation
------------------------------
All four scenarios use all 29 cases and exactly the same measurement model.

Public range interface, request priority:
  29/29 choose one bulk range response. It contains all five optional readings,
  including each case's certified three-query subset. Adding observations
  shrinks the feasible set, so that subset's precision certificate remains
  valid. This proves the requested bound, not zero true-target uncertainty.

Restricted individual-query interface, at most three readings/two rounds,
reading priority:
  22 choose the certified adaptive two-reading rule and seven choose a fixed
  three-reading batch. All 29 are certified. Reserved readings total 65 and
  information rounds total 51. HTTP transaction counts are unspecified.

Restricted interface, at most two readings/two rounds:
  22 choose adaptive two-reading recovery and seven explicitly require
  escalation. No query is executed for those seven and the cap is not exceeded.
  The two-reading primary guarantee remains 22/29.

Restricted interface, at most three readings/one round:
  All 29 choose the certified fixed three-reading batch, with 87 reserved
  readings and 29 information rounds. HTTP transaction counts are unspecified.

The three restricted scenarios are declared benchmark interfaces, not claims
about an observed HPM restriction. They do not supply measured costs. A
separate fixed logical test uses a hypothetical native multipoint request:
request priority chooses fixed-three, while reading priority chooses
adaptive-two. No claim is made that the current HPM API offers that arbitrary
native multipoint operation.

Evidence and provenance
-----------------------
PROTOCOL.txt and protocol_lock.json freeze all scenarios before the ledger.
They pin ten source files by SHA-256. The selector does not edit those files.
The case ledger records every candidate, inclusion or exclusion reason,
selected protocol, exact guarantee bound, source certificate and hash,
separate budget units and declared objective. All decisions are made before
any withheld response is accessed. Existing exact independent certificate
checks establish the mathematics; the new independent gate checker verifies
the integration, source correspondence and admissibility rules.

The 109 eligible case/scenario executions use a fixed constructed uniform
profile with zero error. Seven unavailable cases are blocked without calling
the acquisition callback. These tests validate code and dispatch; they are
not new data-derived performance results. Three incorrect model/budget/unit
inputs are rejected. Mathematical coverage relies on the source continuum
and fixed-batch certificates rather than on the finite execution tests.
Before dispatch, the interface and plan are revalidated against the current
certificate data; a modified or stale plan is rejected before any callback.

Recorded HTTP evidence, read without new requests
-----------------------------------------------
The existing microbenchmark has 30 policy trials, not 60 trials:
three cases x two repetitions x five policies. Its 60 HTTP requests comprise
54 policy-trial requests and six shared initial-endpoint setup requests.
There are six trials per policy. Mean API I/O is 0.33124 s for full range and
0.49651 s for adaptive retrieval. Mean logged completion including client
rate-limiter waiting is 1.03955 s versus 1.98421 s. The range response contains
about 226.7 body bytes versus 104.3 for adaptive retrieval, a small absolute
payload difference; range includes two already retained endpoints. These
are body bytes, not TLS wire bytes. Cache state was uncontrolled.

Those timings describe three prespecified tasks, not the 29 sensitivity cases
or a population latency estimate. Full range is the appropriate choice on the
measured public interface. Its zero reported audit width concerns exact stored
API-grid values, not the separate bounded-error true-increment model. Selective
initial endpoint acquisition is outside each policy-trial timer and must be
included separately in an end-to-end acquisition-from-scratch comparison.

Reproduction and interface
--------------------------
From the supplement/repository root, using standard Python only:
python work/risk_adaptivity_revision/protocol_selection/selector.py --output-dir protocol_selection_replay

This generates the 116-row detailed JSON/CSV ledger, aggregate report and
recorded HTTP summary without writing any prior source/output file, contacting
a provider, fitting a model or solving another optimization problem. Expected
runtime is below one second on the study machine. Do not rerun freeze_protocol.py;
its role is to record the already fixed study rule.

Independent integration check (standard library; approximately 1.2 seconds):
python work/risk_adaptivity_revision/protocol_selection/INDEPENDENT_CHECK.py --results-dir protocol_selection_replay --output-dir protocol_selection_independent_replay

The --results-dir argument selects the new producer outputs being checked;
its default is this directory's bundled results/. The checker validates and
hashes that selected ledger, report and recorded HTTP summary.

The independent check passes all 116 rows, 348 candidate exclusion sets,
certificate/hash correspondence, all seven exact two-query lower-witness
memberships, 109 dispatched callbacks and seven blocked cases. It separately
checks modified plans, malformed or infeasible responses, unsupported models,
budget units, unknown request costs and the hypothetical grouping example.
These checks do not solve another optimization problem or repeat old studies.
The interface schema rejects string/null/integer permission flags and
noninteger query identifiers. Eighteen malformed manifests are checked to
fail before acquisition callbacks, preventing JSON-like strings such as
"false" from being interpreted as an allowed operation.
Canonical finite-JSON comparison also rejects six nested plan mutations that
alias integer query identifiers or resource counts with booleans/floats.

The task-bound wrapper and APPLICATION_WORKFLOW.txt connect a saved task's
coefficients, meter, timestamps, endpoints and units to the requested readouts.
Task identifiers are checked by canonical hashes as well as equality; boolean
and floating aliases for integer identifiers are rejected. The separate binding
checker verifies all 29 descriptors and 58 retained endpoints against cached
decimal source tokens, then tests 109 constructed nonuniform dispatches and
seven blocked cases. These remain implementation checks, not new field trials.
Four analogous bound-plan mutations are rejected before callbacks, and ten
incorrect readout envelopes (including unhashable boundary values) are rejected.

python work/risk_adaptivity_revision/protocol_selection/check_bound_workflow.py --output-dir bound_workflow_checks
python work/risk_adaptivity_revision/protocol_selection/INDEPENDENT_BINDING_CHECK.py --output-dir independent_binding_checks

For programmatic use, Selector.select(case_id, interface) returns a plan
without observations. Selector.execute(selection, read_point=..., read_batch=...)
dispatches supplied callbacks. read_point(k) returns a normalized stored prefix;
read_batch(indices, mode=...) returns an exact mapping for a predetermined group.
The caller implements its real acquisition service. One batch callback is a
logical information round and may involve multiple HTTP requests. No network
implementation or artificial retrieval delay is supplied here.

Files
-----
selector.py: selector, callback dispatcher and reproducible offline evaluation.
results/case_ledger.json: every candidate and explicit exclusion reason.
results/case_ledger.csv: compact case/scenario table with certificate provenance.
results/report.json: scenario counts, dispatch checks and protocol/source hashes.
results/recorded_http_summary.json: summaries recomputed from original logs.
INDEPENDENT_CHECK.py and independent_results/report.json: independent gate check.
manuscript_fragment.tex: concise integration wording for the parent manuscript.
