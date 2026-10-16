"""Align user-facing review documents to the successfully tested final release."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'outputs'
d=json.loads((OUT/'risk_delivery_verification.json').read_text())
assert d['status']=='PASS'
assert d['release_tag']=='peerj-cs-2026-10-14-assurance' and d['pdf_pages']==28
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
head=f"FINAL PEERJ COMPUTER SCIENCE REVIEW -- 14 October 2026\nSource SHA256: {d['manuscript_sha256']}\nPDF SHA256: {d['pdf_sha256']}\nPages: {d['pdf_pages']}\n"
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
The absolute-width example distinguishes original loss units from normalized
precision. Prior work is credited by objective and precise statement.
The policy table and worked certificate distinguish mean risk, precision
guarantees, recorded success and retrieval costs. An unchanged-policy exploratory sweep
uses all five targets from 0.40 to 0.60; unresolved batch-probability gaps are
quantified. Older separate-pair controls remain in S6. Active prose replaces repeated framing; mathematical notation remains where
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
table makes its closed/open partition and overlapping fallback label explicit.
The current compiled-source review covers the workflow and displayed equations.
The elementary finite-action consequence closes the no-certainty branch for
all randomized adaptive policies under the declared uncapped exact-total
noiseless prefix model. Its 19/20 bound is explicitly not claimed optimal.

2. EXPERIMENTAL DESIGN -- addressed within the stated research scope.
Models, chronological splits, information cutoffs, source versions, query
dictionaries, costs, budgets, thresholds and tie rules are documented.
Comparators receive identical information and two shared readings. The
precision-matched batch challenger is distinguished from mean-width and
deterministic worst-width baselines; unresolved optimization gaps are retained.
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
analytic proof. The empirical studies remain separate and unchanged.
The assurance checker verifies 583 seed-independent adverse distributions and
11,660 strictly failing fibers on all 489 original and 94 external no-certainty
cases. All coefficient normalizations agree exactly. These source-bound checks
use no recorded answers or outcomes. The default offline job independently
regenerates the 94 external distributions and 1,880 fibers; original coefficients
are checked by the separate pinned-source route and are not redistributed.
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
Submission remains blocked by the recorded browser startup failure before page
creation. These delivery checks do not constitute a fresh portal attempt.
'''
verification=f"\nFINAL ARTIFACT VERIFICATION\nPASS: {d['replay_steps']} steps in a fresh network-disabled stage from the two publisher ZIP files, {d['journal_manifested_members']} manifested members, {d['elapsed_replay_seconds']:.2f} seconds. Main source reproduced byte-for-byte. Combined ZIP size: {d['journal_total_zip_bytes']/1e6:.2f} MB. Full historical archive integrity also passed.\n"
(OUT/'PEERJ_CRITERIA_AUDIT.txt').write_text(criteria+verification)
latest=(OUT/'LATEST_REVIEW_FIXES_20261013.txt').read_text()
assert d['manuscript_sha256'] in latest and d['pdf_sha256'] in latest
latest=latest.split('\nFINAL ARTIFACT VERIFICATION\n',1)[0]
latest=latest.replace('after the final package checks\nand factual author declarations','after factual author declarations; the final package checks passed')
(OUT/'LATEST_REVIEW_FIXES_20261013.txt').write_text(latest+verification)
for name in ['peerj_five_point_audit.txt','peerj_final_followup_review_20261013.txt','peerj_joint_package_review.txt']:
    (OUT/name).write_text(head+'\nCurrent comprehensive response: LATEST_REVIEW_FIXES_20261013.txt\nPeerJ-specific criteria: PEERJ_CRITERIA_AUDIT.txt\n\n'+latest+verification)
letter=OUT/'peerj_cover_letter.txt';s=letter.read_text()
s=re.sub(r'Together (?:they|the supplemental files) occupy [0-9.]+ MB',
         f"Together the supplemental files occupy {d['journal_total_zip_bytes']/1e6:.2f} MB",s)
if 'A completed source-to-table run also reproduced both panels' not in s:
    s=s.replace('The editable manuscript and both supplemental files accompany the submission materials.',
    'A completed source-to-table run also reproduced both panels and all 1,098 outcome rows. The main text gives the planner and absolute-width example. The editable manuscript and both supplemental files accompany the submission materials.')
assurance_letter=('The focused 28-page manuscript pairs the fixed-two-query joint-precision '
                  'boundary with an assurance-feasibility consequence: on 489 original and '
                  '94 external cases, no randomized adaptive two-reading policy can '
                  'guarantee precision under the declared uncapped exact-total noiseless '
                  'prefix model. The 19/20 upper bound is not claimed optimal. Exact '
                  'source-bound witnesses use no recorded answers; the default offline '
                  'replay independently regenerates the external certificates.\n\n')
if 'The focused 28-page manuscript pairs the fixed-two-query joint-precision' not in s:
    s=s.replace('The editable manuscript and both supplemental files accompany the submission materials.',
                assurance_letter+'The editable manuscript and both supplemental files accompany the submission materials.')
letter.write_text(s)
declarations=OUT/'PEERJ_AUTHOR_DECLARATIONS.txt'
s=declarations.read_text()
s=re.sub(r'(Source SHA-256:\s*)[0-9a-f]{64}',lambda m:m.group(1)+d['manuscript_sha256'],s)
s=re.sub(r'(PDF SHA-256:\s*)[0-9a-f]{64}',lambda m:m.group(1)+d['pdf_sha256'],s)
s=re.sub(r'The current \d+-step clean-package replay',f"The current {d['replay_steps']}-step clean-package replay",s)
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
