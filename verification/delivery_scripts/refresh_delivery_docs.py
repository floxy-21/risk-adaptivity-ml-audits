"""Align user-facing review documents to the successfully tested final release."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'outputs'
d=json.loads((OUT/'risk_delivery_verification.json').read_text())
assert d['status']=='PASS'
assert d['verification_mode'] in {'fresh_full_replay','full_replay_plus_verified_editorial_delta'}
assert isinstance(d['execution_description'],str) and d['execution_description'].strip()
execution_description=d['execution_description']
letter_execution=(
    f"All {d['replay_steps']} scientific replay steps passed before two final prose clarifications. "
    "The final package preserves identical scientific code, inputs and results; "
    "a separate editorial check rebuilt the revised manuscript."
    if d['verification_mode']=='full_replay_plus_verified_editorial_delta'
    else f"All {d['replay_steps']} steps passed in an isolated offline run.")
assert d['release_tag']=='peerj-cs-2026-10-16-retrieval-gate'
assert d['manuscript_title']=='Adaptive Reading Budgets for Joint Forecast Audits with Cumulative Data'
editorial=json.loads((OUT/'risk_editorial_verification.json').read_text())
assert editorial['status']=='passed'
assert editorial['manuscript_sha256']==d['manuscript_sha256']
assert editorial['pdf_sha256']==d['pdf_sha256']
assert d['pdf_pages']==editorial['pdf_pages'] and d['pdf_pages']>0
assert d['submission_status']=='not submitted'
assert hashlib.sha256((OUT/'revised_manuscript.tex').read_bytes()).hexdigest()==d['manuscript_sha256']
assert hashlib.sha256((OUT/'revised_manuscript.pdf').read_bytes()).hexdigest()==d['pdf_sha256']
boundary=d['two_target_boundary']
assert boundary['family_sizes']==[3,5,10]
assert boundary['numerical_verification']['actual_total_LPs']==7131
assurance=d['assurance_feasibility']
assert assurance['status']=='PASS' and assurance['success_upper_bound']=='19/20'
assurance_dir=ROOT/'work/risk_adaptivity_revision/joint_certification/assurance_feasibility'
assert hashlib.sha256((assurance_dir/'verify_assurance.py').read_bytes()).hexdigest()==assurance['source_sha256']
assert hashlib.sha256((assurance_dir/'proof.txt').read_bytes()).hexdigest()==assurance['proof_sha256']
for key in ['full_report','external_report']:
    assert hashlib.sha256((ROOT/assurance[key]['path']).read_bytes()).hexdigest()==assurance[key]['sha256']
diagnostics=d['empirical_review_revision']
assert diagnostics['status']=='PASS' and diagnostics['joint_only_blocks']==191
assert diagnostics['external_baseline_cohort']=={'blocks':57,'assured':57,'selected_readings':70,
    'minimum_fixed_readings':88,'still_need_feedback':18,'now_fixed_suffices':39}
assert diagnostics['external_full_panel']['selected_readings']==358
assert diagnostics['external_full_panel']['minimum_fixed_readings']==378
for relative,digest in diagnostics['artifact_sha256'].items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
completion=d['precision_completion'];decision=d['decision_tolerance']
assert completion['status']==decision['status']=='PASS'
assert completion['previously_open_cases_closed']==418 and completion['full_panel_exact_optima']==1098
assert decision['cases']==1098 and decision['primary_factor']=='1/100'
for evidence in [completion,decision]:
    for relative,digest in evidence['source_artifact_sha256'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
budget=d['budget_revision']
assert budget['status']=='PASS' and d['replay_steps']==7+len(json.loads((ROOT/'work/risk_adaptivity_revision/replay_jobs.json').read_text()))
assert budget['exact_support_width_evaluations']==126195
assert budget['fixed_three_vs_adaptive_two_cases']==225
assert budget['qualifying_reading_reduction']=='1/3'
assert budget['additional_feedback_rounds_on_qualifying_cases']==225
for relative,digest in budget['artifact_sha256'].items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
# Keep the new application bound to the checked evidence; this script is still
# gated by the completed current delivery above and is not a readiness shortcut.
gate_dir=ROOT/'work/risk_adaptivity_revision/practical_retrieval_gate'
gate_report_path=gate_dir/'results/report.json'
gate_check_path=gate_dir/'results/independent_check.json'
gate=json.loads(gate_report_path.read_text())
gate_check=json.loads(gate_check_path.read_text())
assert gate['status']==gate_check['status']=='PASS'
assert gate['input_sha256']==hashlib.sha256((gate_dir/'inputs/public_decision_inputs_coherent.json').read_bytes()).hexdigest()
assert gate['source_sha256']==hashlib.sha256((gate_dir/'analyze.py').read_bytes()).hexdigest()
assert gate_check['source_sha256']==hashlib.sha256((gate_dir/'check_saved.py').read_bytes()).hexdigest()
assert gate_check['analyzed_report_sha256']==hashlib.sha256(gate_report_path.read_bytes()).hexdigest()
assert gate_check['input_sha256']==gate['input_sha256']
assert gate_check['exact_gates_checked']==gate['blocks']==1098
assert gate_check['direct_vertex_loss_checks']==gate['exact_vertex_mse_checks']==39528
assert gate['epsilon_training_m2_factor']=='1/100'
gate_original=gate['cohorts']['original'];gate_external=gate['cohorts']['external']
assert (gate_original['zero_query_certificates'],gate_original['blocks'])==(8,819)
assert (gate_external['zero_query_certificates'],gate_external['blocks'])==(198,279)
assert gate_original['retrospective']['archive_after_gate_remaining_blocks']==9
assert gate_external['retrospective']['archive_after_gate_remaining_blocks']==3
head=f"FINAL PEERJ COMPUTER SCIENCE REVIEW -- {d['review_date']}\nSource SHA256: {d['manuscript_sha256']}\nPDF SHA256: {d['pdf_sha256']}\nPages: {d['pdf_pages']}\n"
criteria=head+f'''
Policy evidence includes live checks on 13 October 2026 at:
https://peerj.com/journals/computer-science/editorial-criteria
https://peerj.com/journals/computer-science/policies/
https://peerj.com/journals/computer-science/author-instructions
Target article type: Research Article. PeerJ's research criteria assess
reporting, design and validity rather than promised importance or impact.

1. BASIC REPORTING -- addressed in the reviewed files.
The structured abstract, introduction, methods, results, discussion and
conclusions identify the computer-science acquisition/certification problem.
The focused main text gives the two-target boundary with both optimality bounds,
the assurance-feasibility consequence, a worked source-derived certificate and
the complete two-query planner with its tie convention. Scalar classification
and mean-risk developments remain in the supplement.
The new fixed-budget family shows adaptive precision success one versus
optimal randomized-batch success 1/m with two affine targets and two coordinate
queries; all three pairs of three constructed nonnegative forecast vectors
retain the separation. Its growing dictionary, shrinking normalized margin
and three-query fixed alternative are stated. The contribution is separated
from established vector recovery, minimax reasoning and sparse-policy bounds.
The support argument identifies the precise additional obstruction: all m
specific batches are necessary for positive worst-record success and their
uniform mixture is uniquely optimal. This is a consequence of the constructed
adverse records, not a claim to have introduced minimax theory.
The absolute-width example distinguishes original loss units from normalized
precision. Prior work is credited by objective and precise statement.
The policy table and worked certificate distinguish mean risk, precision
guarantees, recorded success and retrieval costs. An unchanged-policy exploratory sweep
uses all five targets from 0.40 to 0.60. The new exact completion closes the
previous 418 batch-probability gaps; all 1,098 current precision optima have
matching rational certificates. Older separate-pair controls remain in S6.
Active prose replaces repeated framing; mathematical notation remains where
needed for reproducibility. Tables and references are readable in the rendered
{d['pdf_pages']}-page PDF. Letter paper, one-inch margins, 12-point Times-family text,
left alignment and line numbers follow the instructions. The {d['abstract_words']}-word
abstract is below the journal limit. Editable LaTeX and PDF are supplied.
The two-panel figure exposes the exact conditional geometry and source-specific
threshold curves. The scalar precision bound's premises are explicitly
distinguished from the joint objective; curvature alone proves no separation.
An introductory workflow exposes the admissible bulk, fixed, adaptive and
extended-audit routes within the exact-total noiseless model. Policy objectives
are separated from guarantees and recorded outcomes. The certificate-status
table separates exact current optima from retained historical fallback controls.
The current compiled-source review covers the workflow and displayed equations.
The elementary finite-action consequence closes the no-certainty branch for
all randomized adaptive policies under the declared uncapped exact-total
noiseless prefix model. Its 19/20 bound is explicitly not claimed optimal.

2. EXPERIMENTAL DESIGN -- addressed within the stated research scope.
Models, chronological splits, information cutoffs, source versions, query
dictionaries, costs, budgets, thresholds and tie rules are documented.
Comparators receive identical information and two shared readings. The
precision-optimal batch challenger is distinguished from mean-width and
deterministic worst-width baselines. A coefficient-only secondary width rule
resolves policy choice before recorded answers are read; exact primary
precision is reverified after numerical secondary refinement.
The complete three-way assurance partition, saved greedy-first-query limitation
and deterministic-fallback diagnostic expose the practical decision and stronger
controls. Their post-hoc chronology and source-reconstruction scopes are explicit.
On the external panel, exact adaptation certifies a best model on 207 blocks
and greedy adaptation on 208, despite exact adaptation's higher joint-precision
success. Capacity information reduces the precision advantage and measured API
retrieval favors bulk. Protocol feasibility follows from the stated model,
without an empirically validated selective-access deployment or privacy benefit.
Retrospective extensions are not called untouched confirmation. Six pairwise
comparisons within one block are not treated as six independent observations.
Paired outcomes, per-system effects, synchronized calendar-block resampling
and sensitivity intervals are reported. There are only three systems per
source. Unit costs, caps and error allowances are declared models, not
validated tariffs or device specifications. Bulk retrieval remains a control.
An additional fixed-policy diagnostic links the interval to epsilon-optimal
model certification at a declared training-scale tolerance. At the primary
tolerance, adaptive certification counts are 189/277 original/external,
fixed-batch counts 188/263, and greedy counts 186/277. This supports a gain
over fixed batching on the external panel, while preserving the greedy tie.

A supplementary safe stopping application returns a model within the unchanged
0.01-training-second-moment tolerance. With retained endpoints, it avoids
{gate_original['zero_query_certificates']}/{gate_original['blocks']} original
and {gate_external['zero_query_certificates']}/{gate_external['blocks']} external
per-block fetches. All four models share each acquisition. These are declared-
schedule replay counts; twelve separate public API calls include full-record
downloads for validation. Cold request-oriented access selects direct bulk,
and historical access uses available rounded forecast copies before range
batching. The table retains unfavorable cold and whole-period comparisons.
This application does not establish monetary savings, cost dominance, a
latency advantage, or improved joint-precision performance. The tolerance is
a stated audit requirement, not a calibrated deployment threshold.

3. VALIDITY OF FINDINGS -- addressed by separate proof and execution evidence.
Analytic proofs establish the general and constructed guarantees. Numerical
checks do not purport to prove a universal theorem. Exact rational branch,
covering and adverse-record witnesses support the central assurance claims.
The current replay checks the new construction by exact rational certificates
and {boundary['numerical_verification']['actual_total_LPs']:,} endpoint/whole-branch
LPs at m=3,5,10. The maximum width discrepancy is
{boundary['numerical_verification']['maximum_width_discrepancy']:.16g}; comparison
tolerance is 1e-7 and primal/dual solver tolerances are 1e-9. These finite
checks support implementation; the universal family claim follows from the
analytic proof. The original empirical studies are retained; the four new diagnostics are separately identified.
The assurance checker verifies 583 seed-independent adverse distributions and
11,660 strictly failing fibers on all 489 original and 94 external no-certainty
cases. All coefficient normalizations agree exactly. These source-bound checks
use no recorded answers or outcomes. The default offline job independently
regenerates the 94 external distributions and 1,880 fibers; this job checks
original coefficients through the separate pinned-source route. New diagnostic
jobs separately replay bundled derived coefficient certificates.
The proof and current checker, reports and witnesses are hash-bound in the
delivery record. This is an elementary certainty consequence rather than a
claimed new general theorem or optimized randomized-adaptive success value.
The latest source-to-table run actually regenerates both panels from pinned
original inputs and frozen forecasts, then reconciles policies, certificates
and all 1,098 outcome rows. Source mismatch tests fail as intended. Default
offline reproduction is explicitly distinct from original raw regeneration
and fresh fitting. Practical conclusions concern certificate precision under
the declared interface. Monetary savings, deployed superiority and improved
downstream model choice are not established or claimed. Negative controls
and combined-capacity/error limitations remain visible.

The minimum fixed-budget addition makes the readout constraint an output of
the assurance requirement. A general O(R*n) range scan computes the exact
minimum fixed prefix budget, including randomized sure-success batches.
Across all 1,098 blocks, 35,136 subset checks and a separate shortest-path
checker agree. The independent run checks 737,856 fixed endpoint pairs,
41,400 adaptive endpoint pairs and 500 adaptive interval covers. General
constructed instances cover 180 inputs and 20,440 enumerated batches.
On 168 original and 57 external blocks spanning all six systems, the exact
comparison is three fixed versus two adaptive readings: one third fewer
reserved readouts with one extra feedback round per qualifying block.
Certified adaptation with a minimum fixed fallback reduces full-panel totals
from 2,625 to 2,457 and 743 to 686 (6.40% and 7.67%). No optional answers were
used to derive these retrospective counts. The scope is the uncapped,
noiseless exact-total model. Adaptive budgets above two remain unsolved.
The 126,195 exact support evaluations and four added replay jobs are bound to
the current scripts, reports and archive manifest. Default budget replay
covers the external panel; both-source evidence retains its separate chain.

FOUR EMPIRICAL REVIEW ISSUES -- resolved by new computations.
Scalar fixed-budget checks isolate a joint-only obstruction on 191 of the 225
baseline reading-saving blocks (137 original and 54 external). The remaining
34 contain at least one scalar obstruction; 188 of the 222 matched-half cases
are joint-only. Binding contrasts are reported in original loss units.
The absolute floor is 1% of the training mean squared hourly consumption and
uses no withheld evaluation answers. All 57 baseline external blocks remain
assured with at most two readings. Thirty-nine now need no feedback; the
unchanged 57-block cohort uses 70 readings versus 88 minimum fixed readings.
The complete 279-block external panel uses 358 versus 378 readings, with 18
retained and two newly qualifying feedback cases. Both denominators are shown.
This floor is a declared sensitivity scale, not a calibrated decision threshold.
Exact rational checks establish sufficient closed-left/open-right threshold
intervals for all 222 frozen matched-half certificates. Entire symmetric bands
[0.49,0.51], [0.475,0.525] and [0.45,0.55] retain adaptive certainty and batch
worst-record success exactly one half in 179, 119 and 53 cases. Outside an
interval the frozen certificate is inconclusive; no maximality is asserted.
Matched-cohort capacity tables separate exclusions from added information.
Of the 225 baseline saving cases, the E/2 cap excludes 25, makes 191 fixed-
certifiable and leaves nine requiring feedback. The E/3 cap excludes 75 and
makes all 150 retained cases fixed-certifiable. Additional capacity can remove
the advantage; the counts do not hide either selection or this consequence.
Eleven new jobs replay the derived inputs and certificates, independently check
endpoints and reconcile the manuscript counts. Bundled both-panel certificate
replay is distinct from original raw-source/training reconstruction, whose
pinned execution evidence is retained. External raw-source checks run by default.

DATA, CODE AND PUBLICATION PREPARATION
Reviewers receive complete current code, proofs, case ledgers, attributed
bundled data and regeneration instructions in Supplemental Data S1 and S2.
Original BLEM raw data are regenerated locally under pinned source hashes;
no unsupported redistribution license is asserted. The two files comply
with the 30 MB individual and 50 MB combined upload limits. The larger
private development archive preserves history separately.

The manuscript acknowledges supervised generative-AI assistance and identifies
unknown historical model-version details as unknown. Existing funding,
conflict and exclusivity facts come from the author. The author has personally
confirmed checking the AI tools' terms of use and publication suitability.
Final content accountability, disclosure accuracy, record retention, portal
declarations and fees remain separate author matters; see
PEERJ_AUTHOR_DECLARATIONS.txt. The confirmed tools-terms check does not establish
that every other submission term has been satisfied.

VERDICT
No unresolved blocking scientific or presentation flaw was identified by
the internal reviews and current compiled-source follow-up. Earlier reviews
retain their original source hashes; latest_compiled_review.txt identifies the
current source/PDF review. The paper is suitable for PeerJ CS consideration;
acceptance remains an editorial decision. This is not external human peer
review, a formal proof certificate for the universal theorem, or a calibrated
greater-than-80% probability. No external person was contacted. Nothing was
submitted to a journal.
Signed-in PeerJ submission preparation is recorded in the current browser
diagnostic. These delivery checks do not submit the manuscript or perform a
fresh portal action.
'''
verification=f"\nFINAL ARTIFACT VERIFICATION\n{execution_description}\nCurrent publisher package: {d['journal_manifested_members']} manifested members; combined ZIP size {d['journal_total_zip_bytes']/1e6:.2f} MB. Recorded scientific execution time: {d['elapsed_replay_seconds']:.2f} seconds. Full historical archive integrity also passed.\n"
(OUT/'PEERJ_CRITERIA_AUDIT.txt').write_text(criteria+verification)
latest=(OUT/'LATEST_REVIEW_FIXES_20261013.txt').read_text()
assert d['manuscript_sha256'] in latest and d['pdf_sha256'] in latest
latest=latest.split('\nFINAL ARTIFACT VERIFICATION\n',1)[0]
latest=latest.replace('after the final package checks\nand factual author declarations','after factual author declarations; the final package checks passed')
(OUT/'LATEST_REVIEW_FIXES_20261013.txt').write_text(latest+verification)
for name in ['peerj_five_point_audit.txt','peerj_final_followup_review_20261013.txt','peerj_joint_package_review.txt']:
    (OUT/name).write_text(head+'\nCurrent comprehensive response: LATEST_REVIEW_FIXES_20261013.txt\nPeerJ-specific criteria: PEERJ_CRITERIA_AUDIT.txt\n\n'+latest+verification)
letter=f'''Dear Academic Editor,

Please consider "{d['manuscript_title']}" as a Research Article in PeerJ Computer Science.

We study how many cumulative readings an auditor needs to guarantee the
precision of several forecast comparisons, and when feedback reduces this
requirement. The contribution combines exact acquisition algorithms, matching
lower bounds and executable certificates.

The central construction uses two affine targets and two coordinate queries.
For every integer m >= 3, adaptation guarantees precision while optimal
randomized batching has worst-record success exactly 1/m. Every one of m
specified batches is necessary for positive worst-record success, and their
uniform mixture is uniquely optimal. Each scalar target separately has a fixed
two-query guarantee. We distinguish this joint obstruction from established
vector recovery and minimax reasoning. The main text supplies the proof.

The application uses frozen forecasts and cumulative-meter records from six
systems. On 225 of 1,098 blocks, two adaptive readings replace three necessary
and sufficient fixed readings. Separate scalar-budget checks identify the
joint-only mechanism on 191 of those blocks. On 222 blocks, matching certificates
establish adaptive certainty versus randomized-batch worst-record success one
half; 179 retain this exact separation throughout thresholds [0.49,0.51].

We solve the batch-precision game on all 1,098 blocks, closing every previous
optimization gap. Rational branch covers and adverse distributions make the
optima verifiable without trusting the LP solver. A common coefficient-only
secondary rule chooses the policy before recorded replay.

A training-scale absolute precision floor preserves assurance for all 57 baseline
external blocks; 39 now need no feedback. Matched capacity controls also identify
when fixed acquisition suffices. The study is retrospective.

Supplementary analyses also document tolerance-based model-choice fetches avoided
with retained endpoints ({gate_original['zero_query_certificates']}/{gate_original['blocks']}
original; {gate_external['zero_query_certificates']}/{gate_external['blocks']} external),
while cold and historical access favor direct bulk or archive-aware range batching;
these conditional replay counts are not monetary savings.

Supplemental Data S1 and S2 ({d['journal_total_zip_bytes']/1e6:.2f} MB combined) contain
code, frozen inputs, per-case ledgers, exact witnesses and a results-to-command
map. {letter_execution} The package
separates bundled certificate replay, raw-source reconstruction and fresh model
fitting. Editable source accompanies the {d['pdf_pages']}-page manuscript.

We request handling expertise in algorithms, exact optimization, optimal recovery,
information-based complexity or robust optimization. These match the methods;
the forecasting models provide the application.

This manuscript is unpublished and is not under consideration elsewhere. I
received no external funding and declare no competing interests. The paper
discloses supervised generative-AI assistance. I am the sole corresponding author.

Sincerely,
Jishan Kapoor
Independent Researcher, Toronto M4Y 1C9, Canada
kapoorjishan19@gmail.com
'''
assert 350 <= len(letter.split()) <= 450
(OUT/'peerj_cover_letter.txt').write_text(letter)
declarations=OUT/'PEERJ_AUTHOR_DECLARATIONS.txt'
s=declarations.read_text()
s=re.sub(r'(Source SHA-256:\s*)[0-9a-f]{64}',lambda m:m.group(1)+d['manuscript_sha256'],s)
s=re.sub(r'(PDF SHA-256:\s*)[0-9a-f]{64}',lambda m:m.group(1)+d['pdf_sha256'],s)
release_facts=(
    'Release facts for the agent to verify, not extra author questions\n'
    '- Both current Supplemental Data S1/S2 files meet the individual and total\n'
    '  size limits and extract into the documented common directory.\n'
    f'- {execution_description}\n'
    '- The final manuscript, package manifests and uploaded file hashes must correspond.\n'
    '- Source attribution and included permissive licenses remain in the\n'
    '  submission materials; excluded raw BLEM traces are not reintroduced.\n\n')
s=re.sub(r'Release facts for the agent to verify, not extra author questions\n.*?(?=Readiness distinction\n)',
         lambda m:release_facts,s,flags=re.S)
s=s.replace('unverified personal review or terms check has already happened.',
            'unverified final-content review or record-retention inventory has already happened.')
s=s.replace('2. AI-tool publication terms\n'
            '   I have checked the terms applying to the generative-AI tools used for\n'
            '   this work and confirmed that the material I am submitting is suitable\n'
            "   for publication under the journal's terms.\n\n",'')
s=s.replace('3. Disclosure accuracy','2. Disclosure accuracy')
s=s.replace('4. Retained records','3. Retained records')
terms_fact=("- The author personally checked the terms of use of the AI tools used in\n"
            "  this work and confirmed that the material is suitable for publication.\n"
            "  This is a supplied author confirmation, not an independent legal review\n"
            "  or confirmation of unrelated portal terms or fees.\n")
if terms_fact not in s:
    s=s.replace('- No external funding; no competing interests.\n',
                '- No external funding; no competing interests.\n'+terms_fact)
declarations.write_text(s)
print(json.dumps({'status':'PASS','source':d['manuscript_sha256'],'steps':d['replay_steps']}))
