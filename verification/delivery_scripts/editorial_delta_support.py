"""Strict local binding for an independently executed prose-only delta check.

This does not rerun science or relabel a prior replay as a new execution.
"""
from pathlib import Path
import hashlib
import json

MODE = 'full_replay_plus_verified_editorial_delta'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load_verified_delta(root, replay, source_sha, pdf_sha=None):
    root = Path(root).resolve()
    path = root/'outputs/editorial_delta_verification.json'
    record = json.loads(path.read_text(encoding='utf8'))
    assert record['status'] == 'PASS' and record['verification_mode'] == MODE
    assert record['new_source_sha256'] == source_sha
    assert record['old_source_sha256'] == replay['manuscript_reproduced_sha256']
    assert record['old_source_sha256'] != record['new_source_sha256']
    assert record['baseline_replay_steps'] == len(replay['steps'])
    assert replay['status'] == 'passed' and replay['small'] is False
    assert record['baseline_replay_sha256'] == sha(root/'outputs/current_clean_package_replay.json')
    assert record['scientific_inventory_unchanged'] is True
    assert record['fresh_scientific_steps_executed'] == 0
    assert record['fresh_composition_build']['network_disabled'] is True
    assert record['fresh_composition_build']['returncode'] == 0
    assert record['fresh_composition_build']['source_sha256'] == source_sha
    if pdf_sha is not None:
        assert record['new_pdf_sha256'] == pdf_sha
    for name, digest in record['current_archive_sha256'].items():
        assert name in {'research_supplement.zip','Supplemental_Data_S1.zip','Supplemental_Data_S2.zip'}
        assert sha(root/'outputs'/name) == digest, name
    assert len(record['current_archive_sha256']) == 3
    for name, digest in record['artifact_sha256'].items():
        p = (root/name).resolve()
        assert p.is_relative_to(root) and p.is_file()
        assert sha(p) == digest, name
    for item in record['baseline_archives']:
        p = (root/item['path']).resolve()
        assert p.is_relative_to(root) and p.is_file()
        assert p.stat().st_size == item['bytes'] and sha(p) == item['sha256']
    assert sha(root/'work/risk_adaptivity_revision/peerj_revision/verify_editorial_delta.py') == record['verifier_sha256']
    return record


def execution_note(replay, delta=None):
    if delta is None:
        return (f"Fresh complete current replay: PASS, {len(replay['steps'])} steps; "
                "the current manuscript was reconstructed byte-for-byte.")
    return (f"Scientific verification: the preserved {len(replay['steps'])}-step clean replay passed "
            f"on source {delta['old_source_sha256']}. All scientific code, inputs and results "
            "in the final package are byte-identical. A subsequent, explicitly reviewed "
            "prose-only delta passed a fresh isolated manuscript rebuild and document checks. "
            "No second full scientific execution is claimed for the final prose revision.")
