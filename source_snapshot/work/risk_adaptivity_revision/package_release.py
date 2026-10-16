"""Add current theory/code to the complete preceding scientific supplement."""
from pathlib import Path
import copy, hashlib, json, zipfile
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'work/risk_adaptivity_revision'
PRIOR=BASE/'prior_release/research_supplement.zip'
OLD_SHA='e88e3dd1726c64060577b40f5cda7fb57a225e7ec7ad70eb486d95761dde1c92'
EXCLUDED_EDITORIAL_NOTES={
    'work/external_deadline/editorial/pretest_scientific_review.txt',
    'work/external_deadline/editorial/provisional_numerical_review.txt',
    'work/risk_adaptivity_revision/external_validation/stored_error_sensitivity/failure_diagnostics/INTERNAL_LOWER_REVIEW.txt',
}
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''): h.update(b)
    return h.hexdigest()

def stream_hash(source, destination=None):
    """Copy/hash large scientific members with bounded memory."""
    h=hashlib.sha256()
    for block in iter(lambda: source.read(1 << 20), b''):
        h.update(block)
        if destination is not None: destination.write(block)
    return h.hexdigest()

def include_current_path(p):
    """Single reviewable filter for current additions; no private review notes.

    New-source public API caches are deliberately included for offline replay.
    The original BLEM raw-derived records retain their regeneration-only route.
    """
    if not p.is_file() or '__pycache__' in p.parts: return False
    if p.relative_to(ROOT).as_posix() in EXCLUDED_EDITORIAL_NOTES: return False
    rel=p.relative_to(BASE).as_posix()
    if rel.startswith('peerj_revision/'): return False  # private editorial/reviewer working notes
    if rel.startswith('joint_review/'): return False  # reviewed production copies are in joint_certification
    if rel == 'joint_certification/decision_tolerance_probe/results/block_certificates.json':
        return False  # original BLEM fine answers; sanitized derived endpoint inputs are bundled
    if rel.startswith(('counter_adaptive/pilot/','counter_adaptive/continuation/')): return False
    if rel.startswith('prior_release/') and p.name not in {'revised_manuscript.tex','README_prior.txt','MANIFEST_prior.sha256','requirements_prior.txt'}: return False
    if p.name.endswith('_review.txt') or p.name.startswith('final_pdf_visual_review') or p.name in {'final_review.txt','math_review_notes.txt','proof_review_memo.txt'}: return False
    if p.name in {'HUMAN_REVIEW_BRIEF.txt','INTERNAL_INDEPENDENT_REVIEW.txt','LITERATURE_JOURNAL_REVIEW.txt','HELly_REFERENCE.txt','INTERNAL_REPLAY_CHECKS.json','peerj_fit_verification_20261012.txt','SCIENTIFIC_SYNTHESIS_REVIEW.txt','literature_review.md','INTERNAL_REVIEW.txt'}: return False
    if p.name in {'check_practical_selection.py','practical_selection_diagnostic.json','cap_sensitivity_cases.csv'}: return False
    if any(part.startswith(('replay_','raw_cache','__')) for part in p.relative_to(BASE).parts[:-1]): return False
    if rel in {'joint_certification/final_practical_figure/practical_guarantee_replay.pdf',
               'joint_certification/final_practical_figure/practical_guarantee_replay.png'}: return True
    return p.suffix.lower() in {'.py','.tex','.txt','.json','.csv','.jsonl','.md','.sha256','.gz'}

def main():
    print('Checking preceding release and frozen composition.',flush=True)
    assert sha(PRIOR)==OLD_SHA
    with zipfile.ZipFile(PRIOR) as old:
        (BASE/'prior_release/README_prior.txt').write_bytes(old.read('README.txt'))
        (BASE/'prior_release/MANIFEST_prior.sha256').write_bytes(old.read('MANIFEST.sha256'))
        old_requirements=old.read('requirements.txt')
        assert old_requirements==old.read('outputs/requirements-study.txt')
        (BASE/'prior_release/requirements_prior.txt').write_bytes(old_requirements)
    paths={ROOT/'outputs/revised_manuscript.tex',ROOT/'outputs/risk_release_manifest.json',ROOT/'outputs/requirements-study.txt',BASE/'replay_jobs.json'}
    for name in ('risk_editorial_verification.json','fresh_environment_setup_20261013.json'):
        p=ROOT/'outputs'/name
        if p.is_file(): paths.add(p)
    for p in BASE.rglob('*'):
        if include_current_path(p): paths.add(p)
    composition=json.loads((ROOT/'outputs/risk_release_manifest.json').read_text())
    for name,expected in composition['input_sha256'].items():
        assert name not in EXCLUDED_EDITORIAL_NOTES, 'Excluded editorial composition input: '+name
        p=ROOT/name; assert sha(p)==expected,name
        assert not p.is_relative_to(BASE) or include_current_path(p), 'Excluded private composition input: '+name
        paths.add(p)
    additions={p.relative_to(ROOT).as_posix():p for p in paths}
    additions['README.txt']=BASE/'README.txt'
    additions['requirements.txt']=ROOT/'outputs/requirements-study.txt'
    assert not (set(additions)&EXCLUDED_EDITORIAL_NOTES)
    destination=ROOT/'outputs/research_supplement.zip'
    staging=ROOT/'outputs/research_supplement.risk-building.zip'
    hashes={}; preserved=0; replaced=[]; omitted_inherited=[]
    print('Writing complete supplement.',flush=True)
    with zipfile.ZipFile(PRIOR) as old,zipfile.ZipFile(staging,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as new:
        for info in old.infolist():
            if info.filename=='MANIFEST.sha256': continue
            if info.filename in EXCLUDED_EDITORIAL_NOTES:
                omitted_inherited.append({'path':info.filename,'bytes':info.file_size,
                    'sha256':hashlib.sha256(old.read(info.filename)).hexdigest()})
                continue
            if info.filename in additions:
                replaced.append(info.filename); continue
            with old.open(info) as source, new.open(copy.copy(info),'w',force_zip64=True) as dest:
                hashes[info.filename]=stream_hash(source,dest)
            preserved+=1
        for name,p in sorted(additions.items()):
            with p.open('rb') as source, new.open(name,'w',force_zip64=True) as dest:
                hashes[name]=stream_hash(source,dest)
        omission_note={'prior_archive_sha256':OLD_SHA,
            'configured_paths':sorted(EXCLUDED_EDITORIAL_NOTES),
            'omitted_inherited_editorial_notes':sorted(omitted_inherited,key=lambda item:item['path']),
            'retained_historical_mathematical_rationale':{
                'path':'work/randomized_tie_review/theory_review.txt',
                'sha256':hashes['work/randomized_tie_review/theory_review.txt'],
                'scope':'Retained as substantive mathematical rationale and an actual hash-pinned checker input. '
                        'This is historical internal AI-assisted review, not external validation or a new review of the current manuscript.'},
            'scope':'These internal editorial/review notes are omitted from the current scientific package. '
                    'The inherited notes remain in the unchanged previous private archive; local originals '
                    'are not deleted. They are excluded from current historical-recoverability counts. '
                    'Scientific inputs, code, outputs and protocols are retained unchanged.'}
        omission_bytes=(json.dumps(omission_note,indent=2)+'\n').encode()
        omission_name='EXCLUDED_EDITORIAL_NOTES.json'
        hashes[omission_name]=hashlib.sha256(omission_bytes).hexdigest()
        new.writestr(omission_name,omission_bytes)
        new.writestr('MANIFEST.sha256','\n'.join(f'{h}  {n}' for n,h in sorted(hashes.items()))+'\n')
    # Read every compressed member back; no claim of package readiness from writing alone.
    print('Checking all compressed members and historical preservation.',flush=True)
    with zipfile.ZipFile(staging) as z:
        assert len(z.namelist())==len(set(z.namelist()))==len(hashes)+1
        assert not (set(z.namelist())&EXCLUDED_EDITORIAL_NOTES)
        # read() checks each member CRC as well as the explicit SHA256 below.
        for name,expected in hashes.items():
            with z.open(name) as source: assert stream_hash(source)==expected,name
        old_manifest=(BASE/'prior_release/MANIFEST_prior.sha256').read_text().splitlines()
        historical=0
        specials={'README.txt':'work/risk_adaptivity_revision/prior_release/README_prior.txt',
                  'outputs/revised_manuscript.tex':'work/risk_adaptivity_revision/prior_release/revised_manuscript.tex',
                  'requirements.txt':'work/risk_adaptivity_revision/prior_release/requirements_prior.txt',
                  'outputs/requirements-study.txt':'work/risk_adaptivity_revision/prior_release/requirements_prior.txt'}
        for line in old_manifest:
            expected,name=line.split('  ',1)
            if name in EXCLUDED_EDITORIAL_NOTES:
                assert name not in hashes,name
                assert any(item['path']==name and item['sha256']==expected
                           for item in omitted_inherited),name
                continue
            assert hashes[specials.get(name,name)]==expected,name
            historical+=1
        assert historical+len(omitted_inherited)==len(old_manifest)
    staging.replace(destination)
    report={'status':'passed','zip_sha256':sha(destination),'zip_bytes':destination.stat().st_size,
            'manifested_members':len(hashes),'old_members_preserved_in_place':preserved,
            'old_members_exactly_recoverable':historical,'replaced_paths':sorted(replaced),
            'old_editorial_notes_omitted':sorted(omitted_inherited,key=lambda item:item['path']),
            'editorial_omission_manifest':'EXCLUDED_EDITORIAL_NOTES.json',
            'new_manuscript_sha256':composition['output_sha256'],
            'scope':'Complete member integrity and scientific historical preservation, excluding the explicitly '
                    'listed internal editorial notes retained only in the prior private archive/local files; '
                    'executable clean replay reported separately.'}
    (ROOT/'outputs/risk_supplement_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
