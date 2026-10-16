"""Verify a narrowly reviewed prose delta after a preserved full clean replay.

The plan pins old/new archives, exact replacement hunks, and allowed JSON leaves.
Every archive member is rehashed. Scientific files cannot be allowlisted here.
The only executed package command is the unchanged manuscript builder, with
network disabled and WITHOUT --freeze. Prior replay records are never changed.
"""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

from editorial_delta_support import MODE, sha

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RD = 'work/risk_adaptivity_revision/'
TEXT_ALLOWED = {
    RD+'editorial/source_protocols_short.tex',
    RD+'joint_certification/precision_completion_probe/results_exact.tex',
    'outputs/revised_manuscript.tex',
    RD+'editorial/online_extended_methods.tex',
}
JSON_ALLOWED = {'outputs/risk_release_manifest.json', 'outputs/risk_editorial_verification.json'}
BUILDER = RD+'build_manuscript.py'
DRIVER = RD+'reproduce.py'
JOBS = RD+'replay_jobs.json'
APPROVED_PROSE = {
    RD+'joint_certification/precision_completion_probe/results_exact.tex': (
        'Completing the 418 previously unresolved games took 92.09 seconds on the\nrecorded host',
        'For the 418 of 1,098 games whose initial lower and upper precision bounds\ndiffered, exact completion took 92.09 seconds on the recorded host'),
    RD+'editorial/source_protocols_short.tex': (
        'We use the first three consumer IDs in the pinned BLEM cumulative-counter\nsource \\citep{blem}. Training covers January--September',
        'We use a prespecified three-consumer case series: the lexicographically first\nthree IDs in the pinned BLEM cumulative-counter source \\citep{blem}. The\nsource-preparation protocol fixed this ID rule before model fitting and\nevaluation. Training covers January--September'),
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def bound(item):
    p = (ROOT/item['path']).resolve()
    assert p.is_relative_to(ROOT) and p.is_file(), item['path']
    assert sha(p) == item['sha256'], item['path']
    return p


def stream_digest(handle, output=None):
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(4 << 20), b''):
        digest.update(block)
        if output is not None:
            output.write(block)
    return digest.hexdigest()


class ArchiveUnion:
    def __init__(self, stack, paths):
        self.members = {}
        for path in paths:
            archive = stack.enter_context(zipfile.ZipFile(path))
            for item in archive.infolist():
                name = item.filename
                pure = PurePosixPath(name)
                assert not item.is_dir() and not pure.is_absolute() and '..' not in pure.parts
                assert '\\' not in name and ':' not in name and name not in self.members, name
                self.members[name] = (archive, item)
        text = self.read('MANIFEST.sha256').decode('utf8')
        pairs = [line.split('  ', 1) for line in text.splitlines()]
        self.manifest = {name: digest for digest, name in pairs}
        assert len(self.manifest) == len(pairs)
        assert set(self.members) == set(self.manifest) | {'MANIFEST.sha256'}
        for name, digest in self.manifest.items():
            archive, item = self.members[name]
            with archive.open(item) as f:
                assert stream_digest(f) == digest, name

    def read(self, name):
        archive, item = self.members[name]
        return archive.read(item)

    def extract(self, dest):
        for name, (archive, item) in self.members.items():
            target = (dest/name).resolve()
            assert target.is_relative_to(dest.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as src, target.open('wb') as out:
                digest = stream_digest(src, out)
            if name != 'MANIFEST.sha256':
                assert digest == self.manifest[name]


def json_leaf_changes(old, new, prefix=()):
    if isinstance(old, dict) and isinstance(new, dict):
        assert set(old) == set(new), ('JSON keys changed', prefix)
        return set().union(*(json_leaf_changes(old[k], new[k], prefix+(k,)) for k in old))
    if isinstance(old, list) and isinstance(new, list):
        assert len(old) == len(new), ('JSON list length changed', prefix)
        return set().union(*(json_leaf_changes(a,b,prefix+(str(i),)) for i,(a,b) in enumerate(zip(old,new))))
    return set() if old == new and type(old) is type(new) else {prefix}


def verify_text(old, new, spec, name):
    assert hashlib.sha256(old).hexdigest() == spec['old_sha256']
    assert hashlib.sha256(new).hexdigest() == spec['new_sha256']
    original = old.decode('utf8')
    changed = original
    assert spec['hunks'], name
    if name in APPROVED_PROSE:
        before, after = APPROVED_PROSE[name]
        assert spec['hunks']==[{'old':before,'new':after,'count':1}]
    for hunk in spec['hunks']:
        before, after = hunk['old'], hunk['new']
        assert (before,after) in APPROVED_PROSE.values(), ('Unapproved prose hunk',name)
        assert before and before != after and isinstance(hunk['count'], int) and hunk['count'] > 0
        assert changed.count(before) == hunk['count'], ('Unexpected replacement multiplicity',name)
        changed = changed.replace(before, after)
    assert changed.encode('utf8') == new, ('Unreviewed text change',name)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--python', type=Path, default=ROOT/'work/review-env/Scripts/python.exe')
    p.add_argument('--stage', type=Path)
    p.add_argument('--compress-stage', action='store_true', help='Enable lossless NTFS compression on the fresh extraction directory.')
    p.add_argument('--promote-journal-record', action='store_true')
    args=p.parse_args()
    plan_path=args.plan.resolve()
    assert plan_path.is_relative_to(HERE.resolve())
    plan=read(plan_path)
    assert plan['schema']==1 and plan['scope']=='reviewed_prose_only'
    old, new = plan['baseline'], plan['current']
    old_full=bound(old['full_zip']); new_full=bound(new['full_zip'])
    old_parts=[bound(x) for x in old['parts']]; new_parts=[bound(x) for x in new['parts']]
    assert len(old_parts)==len(new_parts)==2
    assert new_full == (ROOT/'outputs/research_supplement.zip').resolve()
    assert {p.name for p in new_parts} == {'Supplemental_Data_S1.zip','Supplemental_Data_S2.zip'}
    assert all(p.parent == (ROOT/'outputs').resolve() for p in new_parts)
    old_replay_path=bound(old['replay']); replay=read(old_replay_path)
    assert replay['status']=='passed' and replay['small'] is False and len(replay['steps'])==101
    assert all(step['returncode']==0 for step in replay['steps'])
    assert sha(ROOT/'outputs/current_clean_package_replay.json')==sha(old_replay_path)
    invocation_path=bound(old['invocation']); invocation=read(invocation_path)
    journal_path=bound(old['journal']); old_journal=read(journal_path)
    assert old_journal['status']=='passed' and old_journal['clean_replay_steps']==101
    if 'clean_replay_sha256' in old_journal:
        assert old_journal['clean_replay_sha256']==sha(old_replay_path)
    assert old_journal['source_zip_sha256']==sha(old_full)
    assert invocation['assembly']['source_zip_sha256']==sha(old_full)
    assert {x['sha256'] for x in old_journal['parts']} == {sha(p) for p in old_parts}
    assert {x['sha256'] for x in invocation['assembly']['parts']} == {sha(p) for p in old_parts}
    assert Path(invocation['python_executable']).resolve()==args.python.resolve()
    review_path=bound(plan['review'])
    review=review_path.read_text(encoding='utf8')
    assert 'PASS' in review and 'prose' in review.lower()
    assert set(plan['text_changes']) <= TEXT_ALLOWED
    assert set(APPROVED_PROSE) <= set(plan['text_changes'])
    assert set(plan['json_changes']) <= JSON_ALLOWED
    assert 'outputs/revised_manuscript.tex' in plan['text_changes']
    assert 'outputs/risk_release_manifest.json' in plan['json_changes']
    allowed=set(plan['text_changes'])|set(plan['json_changes'])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    stage=(args.stage or ROOT/'work'/('editorial_delta_'+stamp)).resolve()
    assert stage.is_relative_to((ROOT/'work').resolve()) and not stage.exists()
    evidence=HERE/'editorial_delta_evidence'/stamp
    evidence.mkdir(parents=True,exist_ok=False)
    facts=[]
    with contextlib.ExitStack() as stack:
        a=ArchiveUnion(stack,[old_full]); b=ArchiveUnion(stack,[new_full])
        c=ArchiveUnion(stack,old_parts); d=ArchiveUnion(stack,new_parts)
        assert set(a.manifest)==set(b.manifest), 'Full archive additions/removals are forbidden'
        assert set(c.manifest)==set(d.manifest), 'Journal archive additions/removals are forbidden'
        changes={name for name in a.manifest if a.manifest[name]!=b.manifest[name]}
        assert changes==allowed, ('Unexpected or missing full archive delta',sorted(changes ^ allowed))
        for name,spec in plan['text_changes'].items():
            verify_text(a.read(name),b.read(name),spec,name)
        for name,spec in plan['json_changes'].items():
            assert a.manifest[name]==spec['old_sha256'] and b.manifest[name]==spec['new_sha256']
            leaf_changes=json_leaf_changes(json.loads(a.read(name)),json.loads(b.read(name)))
            assert leaf_changes=={tuple(x) for x in spec['allowed_paths']}, (name,leaf_changes)
            if name=='outputs/risk_release_manifest.json':
                legal={('output_sha256',),('online_extended_methods_sha256',)}
                legal.update(('input_sha256',n) for n in APPROVED_PROSE)
            else:
                legal={(key,) for key in ['review_date','completed_utc','manuscript_sha256',
                    'pdf_sha256','extended_methods_sha256','pdf_pages']}
            assert leaf_changes <= legal, ('Non-editorial metadata change',name,leaf_changes-legal)
        # All numerics, code, configuration and frozen results are outside the
        # above fixed allowlist; equality is over the complete member inventory.
        for key in [BUILDER,DRIVER,JOBS,'requirements.txt','outputs/requirements-study.txt']:
            assert a.manifest[key]==b.manifest[key]==c.manifest[key]==d.manifest[key]
        jobs=json.loads(d.read(JOBS))
        assert len(jobs)+7==len(replay['steps'])
        assert [(x['script'],x.get('args',[])) for x in jobs] == [
            (x['script'],x['arguments']) for x in replay['steps'][6:-1]]
        release_old=json.loads(a.read('outputs/risk_release_manifest.json'))
        release_new=json.loads(b.read('outputs/risk_release_manifest.json'))
        assert release_old['output_sha256']==replay['manuscript_reproduced_sha256']
        assert old_journal['manuscript_sha256']==release_old['output_sha256']
        assert release_new['output_sha256']==b.manifest['outputs/revised_manuscript.tex']
        assert release_new['online_extended_methods_sha256']==b.manifest[RD+'editorial/online_extended_methods.tex']
        assert set(release_old['input_sha256'])==set(release_new['input_sha256'])
        altered_inputs={n for n in release_old['input_sha256'] if release_old['input_sha256'][n]!=release_new['input_sha256'][n]}
        assert altered_inputs==set(plan['text_changes'])-{'outputs/revised_manuscript.tex',RD+'editorial/online_extended_methods.tex'}
        assert release_old['output_sha256'] in review and release_new['output_sha256'] in review
        for n,h in release_new['input_sha256'].items():
            assert b.manifest[n]==h
        for n in set(c.manifest)&set(a.manifest)-{'README.txt'}:
            assert c.manifest[n]==a.manifest[n],n
        for n in set(d.manifest)&set(b.manifest)-{'README.txt'}:
            assert d.manifest[n]==b.manifest[n],n
        journal_changes={n for n in c.manifest if c.manifest[n]!=d.manifest[n]}
        expected_journal=allowed&set(c.manifest)
        omission='JOURNAL_OMITTED_FILES.json'
        assert journal_changes==expected_journal|{omission}
        omit_old=json.loads(c.read(omission));omit_new=json.loads(d.read(omission))
        assert json_leaf_changes(omit_old,omit_new)=={('source_archive_sha256',)}
        assert omit_old['source_archive_sha256']==sha(old_full)
        assert omit_new['source_archive_sha256']==sha(new_full)
        for label, archive in [('old_full',a),('new_full',b),('old_journal',c),('new_journal',d)]:
            (evidence/(label+'_MANIFEST.sha256')).write_bytes(archive.read('MANIFEST.sha256'))
        stage.mkdir()
        if args.compress_stage:
            compressed=subprocess.run(['compact.exe','/C',str(stage)],capture_output=True,text=True)
            assert compressed.returncode==0, compressed.stdout+compressed.stderr
        d.extract(stage)
        expected_pins=d.manifest.copy()
        facts=[{'path':n,'old_sha256':a.manifest[n],'new_sha256':b.manifest[n]} for n in sorted(changes)]
    # No network; same dependency environment as the completed baseline run.
    bootstrap=('import runpy,sys\nfrom pathlib import Path\n'
        'def no_network(event, arguments):\n'
        '    if event in {"socket.connect","socket.getaddrinfo","socket.gethostbyname"}:\n'
        '        raise RuntimeError("Network disabled during editorial rebuild")\n'
        'sys.addaudithook(no_network)\n'
        'p=sys.argv[1];sys.argv=sys.argv[1:]\n'
        'sys.path.insert(0,str(Path(p).parent));runpy.run_path(p,run_name="__main__")')
    log=evidence/'composition_build.log'
    env=dict(os.environ)
    env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    with log.open('w',encoding='utf8') as f:
        result=subprocess.run([str(args.python.resolve()),'-c',bootstrap,str(stage/BUILDER)],
            cwd=stage,env=env,stdout=f,stderr=subprocess.STDOUT)
    assert result.returncode==0, str(log)
    for name,digest in expected_pins.items():
        assert sha(stage/name)==digest, ('Build changed manifested file',name)
    source_sha=sha(stage/'outputs/revised_manuscript.tex')
    assert sha(ROOT/'outputs/revised_manuscript.tex')==source_sha
    ed=read(ROOT/'outputs/risk_editorial_verification.json')
    assert ed['status']=='passed' and ed['manuscript_sha256']==source_sha
    assert ed['pdf_sha256']==sha(ROOT/'outputs/revised_manuscript.pdf')
    assert ed['builtin_main_compile']=='success'
    assert sha(ROOT/'outputs/risk_editorial_verification.json')==expected_pins['outputs/risk_editorial_verification.json']
    claims=read(HERE/'originality_resolution_20261014/final_claims_report.json')
    assert claims['status']=='PASS' and claims['manuscript_source_sha256']==source_sha
    assert claims['manuscript_pdf_sha256']==ed['pdf_sha256']
    assert claims['editorial_verification_sha256']==sha(ROOT/'outputs/risk_editorial_verification.json')
    assembly_path=bound(new['assembly']); assembly=read(assembly_path)
    assert assembly['source_zip_sha256']==sha(new_full)
    assert {x['sha256'] for x in assembly['parts']}=={sha(p) for p in new_parts}
    assert assembly['configured_steps']==101
    artifact_paths=[plan_path,review_path,old_replay_path,invocation_path,journal_path,assembly_path,
        ROOT/'outputs/risk_editorial_verification.json',HERE/'originality_resolution_20261014/final_claims_report.json',
        Path(__file__),HERE/'editorial_delta_support.py',*evidence.iterdir()]
    report={'status':'PASS','verification_mode':MODE,'completed_utc':datetime.now(timezone.utc).isoformat(),
        'old_source_sha256':replay['manuscript_reproduced_sha256'],'new_source_sha256':source_sha,
        'new_pdf_sha256':ed['pdf_sha256'],'baseline_replay_steps':len(replay['steps']),
        'baseline_replay_sha256':sha(old_replay_path),'baseline_replay_path':rel(old_replay_path),
        'baseline_archives':[{'path':rel(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in [old_full,*old_parts]],
        'current_archive_sha256':{p.name:sha(p) for p in [new_full,*new_parts]},
        'scientific_inventory_unchanged':True,'full_manifest_members':len(a.manifest),
        'journal_manifest_members':len(expected_pins),'reviewed_changed_members':facts,
        'fresh_scientific_steps_executed':0,
        'fresh_composition_build':{'script':BUILDER,'arguments':[],'network_disabled':True,
            'python_executable':str(args.python.resolve()),'returncode':0,'source_sha256':source_sha,
            'ntfs_compressed_stage':args.compress_stage,
            'stage':str(stage),'log':rel(log),'log_sha256':sha(log)},
        'verifier_sha256':sha(Path(__file__)),
        'artifact_sha256':{rel(p):sha(p) for p in artifact_paths},
        'scope':'Preserved full 101-step clean replay plus byte-identical scientific inventory and a subsequent reviewed prose-only delta. Only final manuscript composition was freshly rerun. No new full scientific run, model fit, data analysis or field measurement is claimed.'}
    report_path=ROOT/'outputs/editorial_delta_verification.json'
    report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    if args.promote_journal_record:
        journal=dict(assembly)
        journal.update(status='passed',verification_mode=MODE,manuscript_sha256=source_sha,
            baseline_clean_replay='current_clean_package_replay.json',baseline_clean_replay_steps=101,
            baseline_clean_replay_sha256=sha(old_replay_path),baseline_source_sha256=replay['manuscript_reproduced_sha256'],
            editorial_delta_report=rel(report_path),editorial_delta_sha256=sha(report_path),
            fresh_scientific_steps_executed=0,scope=report['scope'])
        assert 'clean_replay_steps' not in journal and 'clean_replay' not in journal
        (ROOT/'outputs/journal_supplement_verification.json').write_text(json.dumps(journal,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':'PASS','verification_mode':MODE,'new_source_sha256':source_sha,
        'changed_members':[x['path'] for x in facts],'report':rel(report_path)},indent=2))


if __name__=='__main__':
    main()
