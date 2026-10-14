"""Add current theory/code to the complete preceding scientific supplement."""
from pathlib import Path
import hashlib, json, zipfile
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'work/risk_adaptivity_revision'
PRIOR=BASE/'prior_release/research_supplement.zip'
OLD_SHA='e88e3dd1726c64060577b40f5cda7fb57a225e7ec7ad70eb486d95761dde1c92'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''): h.update(b)
    return h.hexdigest()

def include_current_path(p):
    """Single reviewable filter for current additions; no private review notes.

    New-source public API caches are deliberately included for offline replay.
    The original BLEM raw-derived records retain their regeneration-only route.
    """
    if not p.is_file() or '__pycache__' in p.parts: return False
    rel=p.relative_to(BASE).as_posix()
    if rel.startswith('peerj_revision/'): return False  # private editorial/reviewer working notes
    if rel.startswith('joint_review/'): return False  # reviewed production copies are in joint_certification
    if rel.startswith(('counter_adaptive/pilot/','counter_adaptive/continuation/')): return False
    if rel.startswith('prior_release/') and p.name not in {'revised_manuscript.tex','README_prior.txt','MANIFEST_prior.sha256','requirements_prior.txt'}: return False
    if p.name.endswith('_review.txt') or p.name.startswith('final_pdf_visual_review') or p.name in {'final_review.txt','math_review_notes.txt'}: return False
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
        p=ROOT/name; assert sha(p)==expected,name
        assert not p.is_relative_to(BASE) or include_current_path(p), 'Excluded private composition input: '+name
        paths.add(p)
    additions={p.relative_to(ROOT).as_posix():p for p in paths}
    additions['README.txt']=BASE/'README.txt'
    additions['requirements.txt']=ROOT/'outputs/requirements-study.txt'
    destination=ROOT/'outputs/research_supplement.zip'
    staging=ROOT/'outputs/research_supplement.risk-building.zip'
    hashes={}; preserved=0; replaced=[]
    print('Writing complete supplement.',flush=True)
    with zipfile.ZipFile(PRIOR) as old,zipfile.ZipFile(staging,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as new:
        for info in old.infolist():
            if info.filename=='MANIFEST.sha256': continue
            if info.filename in additions:
                replaced.append(info.filename); continue
            data=old.read(info.filename)
            hashes[info.filename]=hashlib.sha256(data).hexdigest()
            new.writestr(info,data);preserved+=1
        for name,p in sorted(additions.items()):
            data=p.read_bytes();hashes[name]=hashlib.sha256(data).hexdigest();new.writestr(name,data)
        new.writestr('MANIFEST.sha256','\n'.join(f'{h}  {n}' for n,h in sorted(hashes.items()))+'\n')
    # Read every compressed member back; no claim of package readiness from writing alone.
    print('Checking all compressed members and historical preservation.',flush=True)
    with zipfile.ZipFile(staging) as z:
        assert len(z.namelist())==len(set(z.namelist()))==len(hashes)+1
        # read() checks each member CRC as well as the explicit SHA256 below.
        for name,expected in hashes.items(): assert hashlib.sha256(z.read(name)).hexdigest()==expected,name
        old_manifest=(BASE/'prior_release/MANIFEST_prior.sha256').read_text().splitlines()
        historical=0
        specials={'README.txt':'work/risk_adaptivity_revision/prior_release/README_prior.txt',
                  'outputs/revised_manuscript.tex':'work/risk_adaptivity_revision/prior_release/revised_manuscript.tex',
                  'requirements.txt':'work/risk_adaptivity_revision/prior_release/requirements_prior.txt',
                  'outputs/requirements-study.txt':'work/risk_adaptivity_revision/prior_release/requirements_prior.txt'}
        for line in old_manifest:
            expected,name=line.split('  ',1)
            assert hashes[specials.get(name,name)]==expected,name
            historical+=1
    staging.replace(destination)
    report={'status':'passed','zip_sha256':sha(destination),'zip_bytes':destination.stat().st_size,
            'manifested_members':len(hashes),'old_members_preserved_in_place':preserved,
            'old_members_exactly_recoverable':historical,'replaced_paths':sorted(replaced),
            'new_manuscript_sha256':composition['output_sha256'],
            'scope':'Complete member integrity and historical preservation; executable clean replay reported separately.'}
    (ROOT/'outputs/risk_supplement_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
