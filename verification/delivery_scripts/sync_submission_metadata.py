"""Keep prepared portal fields consistent with the saved manuscript."""
from pathlib import Path
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs'
path = OUT / 'PEERJ_SUBMISSION_METADATA.json'
history = OUT / 'pre_focus_PEERJ_SUBMISSION_METADATA.json'
if not history.exists():
    shutil.copy2(path, history)
data = json.loads(path.read_text())
assert 'not submitted' in data['status'].lower()
assert data['last_recorded_browser_attempt']['submitted'] is False
assert data['last_recorded_browser_attempt']['journal_form_accessed'] is False
source = (OUT / 'revised_manuscript.tex').read_text(encoding='utf-8')
assert r'\label{thm:two-target-collapse}' in source
assert r'\label{prop:assurance-feasibility}' in source
abstract = source.split(r'\begin{abstract}', 1)[1].split(r'\end{abstract}', 1)[0]
abstract = re.sub(r'\\textbf\{([^}]+)\}', r'\1', abstract)
abstract = abstract.replace(r'\geq', '>=').replace(r'\%', '%').replace('$', '')
abstract = '\n\n'.join(' '.join(p.split()) for p in abstract.strip().split('\n\n'))
assert '\\' not in abstract
assert '1/m' in abstract and 'two exact scalar readings' in abstract
data['abstract'] = abstract
data['release_tag'] = 'peerj-cs-2026-10-14-assurance'
data['release_focus'] = 'Fixed two-query joint-precision boundary and exact assurance feasibility.'
for key, filename in [('manuscript_sha256', 'revised_manuscript.tex'),
                      ('pdf_sha256', 'revised_manuscript.pdf')]:
    data[key] = hashlib.sha256((OUT / filename).read_bytes()).hexdigest()
path.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'status': 'PASS', 'source': data['manuscript_sha256'],
                  'prepared_abstract_words': len(abstract.split()),
                  'submission_status': data['status']}))
