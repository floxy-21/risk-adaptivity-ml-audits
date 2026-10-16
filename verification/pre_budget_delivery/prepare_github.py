"""Prepare a private repository payload from the verified scientific release."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs'
DEST = ROOT / 'work/github_delivery_20261013'
REPO = 'floxy-21/risk-adaptivity-ml-audits'
TAG = 'peerj-cs-2026-10-14-assurance'
PREVIOUS_TAG = 'peerj-cs-2026-10-13-two-target'
EXCLUDED_EDITORIAL_NOTES={
    'work/external_deadline/editorial/pretest_scientific_review.txt',
    'work/external_deadline/editorial/provisional_numerical_review.txt',
    'work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/failure_diagnostics/INTERNAL_LOWER_REVIEW.txt',
}
DEST.mkdir(exist_ok=True)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''): h.update(block)
    return h.hexdigest()

def remove_stale_editorial_copies():
    """Remove only byte-verified copies, never workspace originals or trees."""
    snapshot=(DEST/'source_snapshot').resolve()
    assert snapshot.is_relative_to(DEST.resolve()) and snapshot.is_relative_to(ROOT.resolve())
    removed=[]
    for name in sorted(EXCLUDED_EDITORIAL_NOTES):
        target=snapshot/name
        resolved=target.resolve()
        assert resolved.is_relative_to(snapshot) and resolved != snapshot
        original=(ROOT/name).resolve()
        assert original.is_relative_to(ROOT.resolve()) and not original.is_relative_to(snapshot)
        assert original.is_file()
        if target.exists():
            assert target.is_file() and not target.is_symlink(),name
            original_sha=sha(original)
            assert sha(target)==original_sha, 'Staged editorial note differs from original: '+name
            target.unlink()
            assert original.is_file() and sha(original)==original_sha,name
            removed.append({'path':name,'sha256':original_sha})
    return removed

delivery = json.loads((OUT / 'risk_delivery_verification.json').read_text())
assert delivery['status'] == 'PASS'
assert delivery['release_tag']==TAG and delivery['pdf_pages']==28
assert delivery['submission_status']=='not submitted'
assert delivery['manuscript_sha256'] == sha(OUT / 'revised_manuscript.tex')
assert delivery['pdf_sha256'] == sha(OUT / 'revised_manuscript.pdf')
assert delivery['zip_sha256'] == sha(OUT / 'research_supplement.zip')
boundary=delivery['two_target_boundary']
boundary_dir=ROOT/'work/risk_adaptivity_revision/two_target_boundary'
assert boundary['source_sha256']==sha(boundary_dir/'verify_boundary.py')
assert boundary['theorem_fragment_sha256']==sha(boundary_dir/'main_theorem.tex')
assert boundary['family_sizes']==[3,5,10]
assert boundary['numerical_verification']['actual_total_LPs']==7131
assurance=delivery['assurance_feasibility']
assurance_dir=ROOT/'work/risk_adaptivity_revision/joint_certification/assurance_feasibility'
assert assurance['status']=='PASS' and assurance['success_upper_bound']=='19/20'
assert assurance['source_sha256']==sha(assurance_dir/'verify_assurance.py')
assert assurance['proof_sha256']==sha(assurance_dir/'proof.txt')
for key in ['full_report','external_report']:
    assert assurance[key]['sha256']==sha(ROOT/assurance[key]['path'])
assert assurance['full_check_counts']['seed_independent_adverse_distributions']==583
assert assurance['external_replay_check_counts']['seed_independent_adverse_distributions']==94
current_review=ROOT/delivery['current_source_review']['path']
assert delivery['current_source_review']['sha256']==sha(current_review)
assert delivery['manuscript_sha256'] in current_review.read_text()
assert delivery['pdf_sha256'] in current_review.read_text()
browser_diagnostic=Path(__file__).parent/'browser_startup_check_20261014.json'
assert delivery['last_recorded_browser_attempt']['diagnostic_sha256']==sha(browser_diagnostic)
assert delivery['last_recorded_browser_attempt']['checked_utc']==json.loads(browser_diagnostic.read_text())['checked_utc']
hygiene_path=Path(__file__).parent/'final_upload_hygiene.json'
hygiene=json.loads(hygiene_path.read_text())
hygiene_current=(hygiene.get('status')=='PASS'
    and hygiene.get('manuscript_sha256')==delivery['manuscript_sha256']
    and hygiene.get('pdf_sha256')==delivery['pdf_sha256']
    and all(hygiene.get('archives',{}).get(name,{}).get('sha256')==sha(OUT/name)
            for name in ['research_supplement.zip','Supplemental_Data_S1.zip','Supplemental_Data_S2.zip']))
hygiene_status=('matches the current manuscript and three archives' if hygiene_current
    else 'is a historical scan of its recorded hashes; it does not verify the current release')
count = 0
with zipfile.ZipFile(OUT / 'research_supplement.zip') as z:
    assert not (set(z.namelist())&EXCLUDED_EDITORIAL_NOTES)
    omitted=json.loads(z.read('EXCLUDED_EDITORIAL_NOTES.json'))
    assert set(omitted['configured_paths'])==EXCLUDED_EDITORIAL_NOTES
    assert delivery['historical_editorial_notes_omitted']==omitted['omitted_inherited_editorial_notes']
    removed_editorial_copies=remove_stale_editorial_copies()
    for entry in z.infolist():
        if entry.filename in EXCLUDED_EDITORIAL_NOTES: continue
        rel = Path(entry.filename)
        include = rel.suffix.lower() in {'.py','.tex','.txt','.md','.sha256'}
        include |= rel.suffix.lower() in {'.json','.csv','.jsonl'} and entry.file_size <= 1_000_000
        if not include: continue
        target = (DEST / 'source_snapshot' / rel).resolve()
        assert target.is_relative_to(DEST.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(entry))
        count += 1
for folder, names in {
    'manuscript': ['revised_manuscript.pdf','revised_manuscript.tex','peerj_cover_letter.txt','PEERJ_SUBMISSION_METADATA.json'],
    'verification': ['risk_delivery_verification.json','current_clean_package_replay.json',
                     'risk_supplement_verification.json','risk_editorial_verification.json',
                     'peerj_final_visual_review.txt','peerj_final_followup_review_20261013.txt',
                     'peerj_five_point_audit.txt','peerj_joint_package_review.txt',
                     'PEERJ_CRITERIA_AUDIT.txt',
                     'LATEST_REVIEW_FIXES_20261013.txt',
                     'PEERJ_AUTHOR_DECLARATIONS.txt','journal_supplement_verification.json',
                     'SUBMISSION_READINESS.txt','FINAL_PEER_REVIEW.txt',
                     'fresh_environment_setup_20261013.json',
                     'peerj_replay_invocation_20261013.json',
                     'peerj_native_crash_20261013.log',
                     'peerj_native_crash_invocation_20261013.json',
                     'peerj_native_crash_event_20261013.txt',
                     'counter_fresh_environment_retry.json']
}.items():
    (DEST / folder).mkdir(exist_ok=True)
    for name in names:
        shutil.copy2(OUT / name, DEST / folder / name)
visual_summary=OUT/'precision_boundary_summary.svg'
if visual_summary.is_file():
    shutil.copy2(visual_summary,DEST/'manuscript'/visual_summary.name)
for name in ['new_core_theory_review.txt','new_package_review.txt','peerj_final_fit_challenge.txt','peerj_practical_value_challenge.txt',
             'final_consistency_review.txt','final_practical_diagnostics_review.txt','latest_boundary_review.txt',
             'pre_two_target_latest_boundary_review.txt',
             'first_reader_prose_review.txt','final_upload_hygiene.json','final_upload_hygiene.txt',
             'browser_startup_check_20261014.json']:
    shutil.copy2(Path(__file__).parent/name,DEST/'verification'/name)
shutil.copy2(current_review,DEST/'verification'/'latest_compiled_review.txt')
(DEST/'verification'/'two_target_boundary').mkdir(exist_ok=True)
for name in ['proof_review_memo.txt','novelty_review.txt']:
    assert boundary['review_memos'][name]['sha256']==sha(boundary_dir/name)
    shutil.copy2(boundary_dir/name,DEST/'verification'/'two_target_boundary'/name)
(DEST/'verification'/'assurance_feasibility').mkdir(exist_ok=True)
for name in ['proof.txt','README.txt']:
    shutil.copy2(assurance_dir/name,DEST/'verification'/'assurance_feasibility'/name)
for key,name in [('full_report','full_source_report.json'),('external_report','external_report.json')]:
    shutil.copy2(ROOT/assurance[key]['path'],DEST/'verification'/'assurance_feasibility'/name)
(DEST/'verification'/'delivery_scripts').mkdir(exist_ok=True)
for name,digest in delivery['delivery_script_sha256'].items():
    path=Path(__file__).parent/name
    assert sha(path)==digest,name
    shutil.copy2(path,DEST/'verification'/'delivery_scripts'/name)
# Preserve the previous successful release replay and host-native crash history.
# These files retain their own source hashes rather than being relabelled current.
for path in OUT.glob('pre_additional_review*'):
    if path.is_file() and path.suffix.lower() in {'.json','.txt','.log'}:
        shutil.copy2(path,DEST/'verification'/path.name)
for path in OUT.glob('pre_editorial_review*'):
    if path.is_file() and path.suffix.lower() in {'.json','.txt','.log'}:
        shutil.copy2(path,DEST/'verification'/path.name)
for path in OUT.glob('pre_workflow_*'):
    if path.is_file() and path.suffix.lower() in {'.json','.txt','.log'}:
        shutil.copy2(path,DEST/'verification'/path.name)
for path in OUT.glob('pre_two_target_*'):
    if path.is_file() and path.suffix.lower() in {'.json','.txt','.log'}:
        shutil.copy2(path,DEST/'verification'/path.name)
for path in OUT.glob('pre_focus_*'):
    if path.is_file() and path.suffix.lower() in {'.json','.txt','.log','.tex','.pdf'}:
        shutil.copy2(path,DEST/'verification'/path.name)
for path in OUT.glob('pre_entry_revision_*'):
    if path.is_file() and path.suffix.lower() in {'.json','.txt','.log'}:
        shutil.copy2(path,DEST/'verification'/path.name)
for name in [
    'editorial_note_dependency_failure_20261014_assembly_report.json',
    'editorial_note_dependency_failure_20261014_full_archive_verification.json',
    'editorial_note_dependency_failure_20261014_peerj_clean_replay_20261013.log',
    'editorial_note_dependency_failure_20261014_peerj_replay_invocation_20261013.json',
    'editorial_note_dependency_failure_20261014_step06.log',
    'editorial_rationale_focused_retry_20261014.json',
    'editorial_rationale_focused_retry_20261014.log',
]:
    shutil.copy2(OUT/name,DEST/'verification'/name)
for name in ['peerj_disk_setup_failure_20261014.log', 'peerj_disk_setup_invocation_20261014.json', 'peerj_storage_compression_20261014.log', 'editorial_numeric_comparison_20261014.json']:
    shutil.copy2(OUT/name,DEST/'verification'/name)
figure_dir=ROOT/'work/risk_adaptivity_revision/joint_certification/final_practical_figure'
(DEST/'figures').mkdir(exist_ok=True)
for name in ['practical_guarantee_replay.pdf','practical_guarantee_replay.png','figure_data.json','independent_check.json']:
    shutil.copy2(figure_dir/name,DEST/'figures'/name)
files = ['revised_manuscript.pdf','revised_manuscript.tex','research_supplement.zip',
         'Supplemental_Data_S1.zip','Supplemental_Data_S2.zip']
checksums = ''.join(f'{sha(OUT / name)}  {name}\n' for name in files)
(DEST / 'RELEASE_SHA256.txt').write_text(checksums)
(OUT / 'RELEASE_SHA256.txt').write_text(checksums)
(OUT / 'GITHUB_RELEASE_NOTES.txt').write_text(f'''PeerJ Computer Science submission candidate, 14 October 2026.

Author: Jishan Kapoor. Private research archive; not submitted or accepted.
Release: {TAG}. The previous release {PREVIOUS_TAG} remains preserved.

The new central boundary keeps two coordinate queries and two affine targets:
adaptive precision success is one, while optimal randomized-batch success is
exactly 1/m for every m>=3. Each target separately has a fixed two-query
guarantee. The same separation holds for all three paired contrasts of three
constructed nonnegative forecast vectors. The dictionary grows with m,
normalized slack shrinks, and three fixed queries suffice; these are exact
constructed limits rather than newly measured practical gains.

The focused 28-page paper also closes the assurance-feasibility decision under
the uncapped exact-total noiseless prefix model. On 489 original and 94 external
blocks with no deterministic two-reading guarantee, every randomized adaptive
policy has worst-record success at most 19/20. An elementary finite-action
argument and exact source-bound witnesses establish this consequence; the bound
is not claimed tight or a novel general impossibility principle.
The full source-derived check verifies 583 seed-independent adverse distributions
and 11,660 strictly failing fibers without using recorded answers. The default
offline replay independently regenerates 94 external distributions and 1,880
fibers. The original-panel certificates retain their separate pinned-source
execution provenance. See verification/assurance_feasibility/.

The current replay includes solver-free rational checks and
{boundary['numerical_verification']['actual_total_LPs']:,} actual LPs at m=3,5,10.
Maximum observed width discrepancy:
{boundary['numerical_verification']['maximum_width_discrepancy']:.16g}
(comparison tolerance 1e-7; primal/dual solver tolerances 1e-9).
Current checker and mathematical-input hashes bind both new reports.
The analytic proof establishes the whole family; finite checks do not replace it.
See verification/two_target_boundary/ for the internal proof and prior-art memos.
Earlier empirical results, adverse controls and their chronology are unchanged.

The PDF and editable source correspond to the complete reproducibility supplement.
The final isolated replay passed all {delivery['replay_steps']} executable steps.
It ran from Supplemental_Data_S1.zip and Supplemental_Data_S2.zip extracted
together; each part is under 30 MB and the combined upload is under 50 MB.
The larger research_supplement.zip separately preserves development history.
Three internal editorial notes are intentionally excluded from scientific assets.
EXCLUDED_EDITORIAL_NOTES.json records the inherited omissions; they remain
in the previous private release/local originals and are not counted recoverable.
The retained historical tie-policy mathematical rationale is a hash-pinned
scientific checker input, not external or current-manuscript peer review.
See verification/current_clean_package_replay.json in the repository for scope,
runtime and per-step checks. The default run uses saved forecasts and does not
claim a fresh model-training run, new API measurements or external human review.

The current {delivery['pdf_pages']}-page manuscript centers the two-target boundary,
assurance feasibility and source-derived joint certificates. Scalar classification
and mean-risk developments remain in the supplement. The policy-objective
table, unresolved batch-probability gaps and five-threshold unchanged-policy checks
on all 1,098 blocks retain the measured limits.
The supplement retains both numerical boundary conventions, paired outcomes
and all full controls. Two command paths and two dependency pins were fixed;
the complete current publisher package was tested in the isolated pinned venv.
The final diagnostic reports the full fixed/adaptive/no-guarantee partition,
the greedy first-query assurance limitation and the fixed-batch fallback.
The two-panel source-linked figure displays the exact acquisition rule and
recorded precision curves. Independent exact checks verify its coordinates.
Earlier internal reviews retain their original source identities; the current
source/PDF assessment is verification/latest_compiled_review.txt.
The bounded prose cleanup removes revision-only wording and repeated caveats
while preserving numerical results, assumptions and unfavorable controls.
Its fragment-edit record is verification/first_reader_prose_review.txt;
that earlier edit record is distinct from the final compiled-source review.
The introductory workflow explains when the declared audit calls for bulk,
fixed, adaptive or extended acquisition. Policy objectives, exact guarantee
status and recorded comparisons are now distinguished directly. The current
compiled-source review covers the workflow and displayed equations. Prior
successful execution remains separately source-bound in pre_workflow_* records.
The pre_two_target_* records preserve the successful preceding release; they
are not presented as execution of the current theorem or current manuscript.
The pre_focus_* records preserve the immediately preceding manuscript, PDF,
execution records and private-release verification at their original hashes.
The upload-hygiene record {hygiene_status}.

The practical material includes shared-query certification of all model pairs,
an exact constructed adaptive-versus-batch boundary, complete-panel replay,
bounded-error certificates, capacity controls and paired-outcome diagnostics.
The final source-to-table run also regenerated both panels' 165/57 matched
certificates and all 1,098 outcome rows without numeric discrepancies. The
main text now includes the planner's algorithm box and absolute loss widths.
See joint_certification/provenance_chain/README.txt in the extracted package.
Modeled costs are distinguished from recorded API measurements. Historical
results and unfavorable controls are retained. Reused sources are not relabeled
as a newly untouched confirmation.
On the external panel, exact adaptation certifies a best model on 207 blocks
and greedy adaptation on 208, despite exact adaptation's higher joint-precision
success. Capacity information reduces the precision advantage, and measured
public-API retrieval favors bulk. No deployed selective interface, privacy or
compliance benefit, financial saving or improved model choice is established.
Submission remains blocked by the recorded browser startup failure before page
creation; these delivery steps do not access the portal or submit the manuscript.

Verify downloaded assets using RELEASE_SHA256.txt before extracting the supplement.
''')
(DEST / '.gitattributes').write_text('* -text\n')
(DEST / '.gitignore').write_text('__pycache__/\n.venv/\n*.pyc\nresearch_supplement.zip\n')
(DEST / 'README.md').write_text(f'''# Risk and Adaptivity in Certifying Machine-Learning Model Comparisons

Jishan Kapoor · Independent Researcher · Toronto, Canada

Research manuscript prepared for PeerJ Computer Science. This private repository
stores the author's submission materials; it does not indicate journal acceptance.

## Start here

- [Read the paper](manuscript/revised_manuscript.pdf).
- [Editable LaTeX source](manuscript/revised_manuscript.tex).
- [Complete reproducibility release](https://github.com/{REPO}/releases/tag/{TAG}).
- [Table-to-command map](source_snapshot/work/risk_adaptivity_revision/CURRENT_RESULTS_MAP.txt).
- [Fresh execution record](verification/current_clean_package_replay.json).
- [Earlier five-point review, retained with its original scope](verification/peerj_five_point_audit.txt).
- [Current compiled-source review](verification/latest_compiled_review.txt).
- [Earlier first-reader prose review](verification/first_reader_prose_review.txt).
- [Hash-bound upload-hygiene scan](verification/final_upload_hygiene.json).
- [Acquisition geometry and replay figure](figures/practical_guarantee_replay.pdf).
- [Fixed two-query proof review](verification/two_target_boundary/proof_review_memo.txt).
- [Precise prior-art comparison](verification/two_target_boundary/novelty_review.txt).
- [Assurance-feasibility proof](verification/assurance_feasibility/proof.txt).
- [Full source-derived assurance evidence](verification/assurance_feasibility/full_source_report.json).

The fixed-budget result uses two affine targets and two coordinate queries:
adaptation guarantees joint precision, while the best randomized fixed batch
has worst-case success exactly `1/m` for every `m >= 3`. Each target separately
has a fixed two-query guarantee. The same separation holds for all three paired
contrasts of three constructed nonnegative forecast vectors. Its dictionary
grows with `m`, its normalized margin shrinks, and three fixed queries suffice.
It proves a boundary for shared assurance, not an empirical or financial gain.

The accompanying assurance-feasibility consequence identifies when the declared
two-reading protocol cannot provide certainty even with randomized feedback.
On 489 original and 94 external blocks, every randomized adaptive policy has
worst-record success at most `19/20`. This elementary finite-action bound is
not claimed optimal. Source-derived exact witnesses use no recorded answers.
Together with the fixed and adaptive guarantee certificates, it supports a
choice among fixed, adaptive and extended acquisition under the specified model.

The {delivery['pdf_pages']}-page paper centers these two results and a worked
source-derived joint certificate. Scalar classification and mean-risk developments
remain in the supplement. Recorded outcomes retain the limits: exact adaptation
certifies a best model on 207 external blocks and greedy adaptation on 208,
despite exact adaptation's higher joint-precision success. Capacity information
reduces the precision advantage, and measured public-API retrieval favors bulk.
The query contract is declared; no deployed selective interface, privacy/compliance
benefit, financial saving or improved model choice is established.

## Reproduce the complete current paper

Download `Supplemental_Data_S1.zip` and `Supplemental_Data_S2.zip` from the release,
verify their SHA-256 values against `RELEASE_SHA256.txt`, and extract both into
the same empty directory. These publisher-sized files contain the current
reproduction package. Use the documented Python 3.12 environment:

```sh
python -m pip install -r requirements.txt
python work/risk_adaptivity_revision/reproduce.py
```

Run these commands from the extracted package root. The default entry point
checks all manifested files, creates a new isolated stage, blocks network access
during scientific replay, executes {delivery['replay_steps']} checks, compares saved
scientific results and reconstructs the current manuscript byte-for-byte.
The tested environment and exact scope appear in the verification record.
The verified run took about {delivery['elapsed_replay_seconds']/60:.1f} minutes on
the study host, plus extraction/copy time; allow several GB of free disk.

The new `two_target_exact` and `two_target_lp` jobs check the constructed family
at `m=3,5,10` with rational arithmetic and
{boundary['numerical_verification']['actual_total_LPs']:,} actual LPs, respectively.
The maximum recorded width discrepancy is
`{boundary['numerical_verification']['maximum_width_discrepancy']:.16g}` under a
`1e-7` comparison tolerance and `1e-9` primal/dual solver tolerances.
Both reports include the checker SHA-256 and canonical mathematical-input hash.
The all-size theorem rests on its proof; these finite checks test the implementation.

The `joint_assurance_feasibility` job independently regenerates exact adverse
distributions for 94 external no-certainty cases and checks 1,880 failing fibers.
The separately executed source-bound report covers both panels: 583 distributions
and 11,660 fibers. The full report, witnesses, current checker and proof are
hash-bound in the delivery record. Default replay does not recheck original raw
coefficients; the documented pinned-source route supplies that separate evidence.
The result concerns the uncapped exact-total noiseless prefix model and does not
transfer automatically to noisy or capacity-constrained interfaces.

Default replay uses frozen forecasts; it does not refit models, download source
data or repeat the archived API/timing measurements. Separate regeneration and
fresh-fitting commands are documented in the package. BLEM-derived raw traces are
regenerated locally rather than redistributed; attributed public-source caches
and constructed instances are bundled as documented.

A separate completed source-to-table run checked pinned original counters,
restored the exact frozen forecast archive, regenerated both panels' policies
and exact certificates, and reproduced all 1,098 outcome rows. Its commands,
scope and execution records are in `joint_certification/provenance_chain/`.
That run uses frozen models; it is not fresh fitting or external human review.

The latest review adds a five-threshold sensitivity over unchanged policies and
reports the remaining probability-bound gaps. The {delivery['pdf_pages']}-page main text separates
the mathematical optima, exact instance guarantees, recorded outcomes and API
costs. Complete controls remain in the supplement. The current full replay uses
a newly created isolated Python environment with all 11 runtime packages pinned.
The assurance consequence completes the exact three-way feasibility decision,
including all randomized adaptive policies in the no-certainty branch. The saved
greedy first-query limitation and stronger fixed-fallback control remain visible.
These are source-derived results rather than a new independent experiment.
The main figure is generated from exact source coefficients and case counts;
its standalone PDF/PNG and independent check are available in `figures/`.
An introductory workflow now explains the choice among bulk, fixed, adaptive
and extended acquisition under the declared exact-total noiseless model.
The policy and status tables distinguish optimization objectives, guaranteed
success and recorded outcomes; fallback is an overlapping label rather than
another status-partition cell. The final compiled-source review also records
the workflow and displayed-equation rendering checks. These are presentation
clarifications accompanying the new assurance consequence; recorded outcomes
and the scientific producer scripts are unchanged.

## Repository and release contents

`manuscript/` contains the final PDF, editable source and local cover letter.
`source_snapshot/` provides browsable code, methods, documentation and small
fixtures from the exact release. Large frozen inputs remain in the complete ZIP
release asset rather than Git history. Run the full package, not this intentionally
partial source snapshot. `verification/` contains the final execution and review
records. SHA-256 checksums identify the precise manuscript and supplement.
`verification/delivery_scripts/` contains the final post-replay publishing gates,
bound by hashes in the delivery record. They were updated separately from the
scientific package, whose exact manifested snapshot remains preserved.
Earlier internal review files are kept with their original source hashes;
they are not represented as fresh assessments of the final revision.
`verification/latest_compiled_review.txt` identifies the current artifact review.
`verification/first_reader_prose_review.txt` records the earlier fragment-level
clarity edits; it is not a separate final-PDF or external human review.
The `pre_workflow_*` files preserve the preceding successful replay at its
own source hash. The upload-hygiene record {hygiene_status}.
The `pre_two_target_*` files likewise retain the preceding successful release
as history, not as a substitute for the two new jobs or current source replay.
The `pre_focus_*` files preserve the immediately preceding manuscript, PDF and
verification history. The private release `{PREVIOUS_TAG}` remains available;
`{TAG}` identifies this focused revision.
Recorded host-native process failures and subsequent complete successful runs
remain separate execution history, rather than silently discarded failures.

The larger `research_supplement.zip` preserves historical development records.
Its `EXCLUDED_EDITORIAL_NOTES.json` explicitly identifies three internal notes
omitted from scientific assets. The inherited notes remain in the previous private
release/local originals and are excluded from the current recoverability count.
The retained `work/randomized_tie_review/theory_review.txt` provides substantive
historical mathematical rationale used as a hash-pinned checker input. It is
internal AI-assisted review, not external validation of the current manuscript.
The publisher package omits unused historical caches and lists those omissions;
its {delivery['replay_steps']}-step execution uses the same scientific files and driver. No browser
sessions, account credentials, registration forms or private outreach drafts are
part of this repository.

## Attribution and status

Author contributions and supervised generative-AI assistance are disclosed in the
manuscript. Internal checks are not external human peer review. Third-party source
and data notices remain in the supplement; no blanket relicensing is asserted.
This repository is private. The manuscript has not been submitted or accepted.
Submission remains blocked by the recorded browser startup failure before page
creation. Preparing or verifying this release performs no fresh portal check.
''', encoding='utf-8')
(DEST / 'CITATION.txt').write_text('''Kapoor, Jishan (2026).
Risk and Adaptivity in Certifying Machine-Learning Model Comparisons.
Unpublished research manuscript and accompanying software, 14 October 2026.
Independent Researcher, Toronto, Canada.
Prepared for PeerJ Computer Science; not submitted or accepted.
Use the release tag and checksums to identify the exact revision.
''')
large = [str(p.relative_to(DEST)) for p in DEST.rglob('*') if p.is_file() and p.stat().st_size >= 100_000_000]
assert not large, large
print(json.dumps({'repository_directory':str(DEST), 'repository':REPO,
                  'tag':TAG,'snapshot_files':count,'release_checksums':checksums,
                  'removed_verified_editorial_snapshot_copies':removed_editorial_copies}, indent=2))
