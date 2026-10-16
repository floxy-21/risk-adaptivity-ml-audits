"""Pinned saved-input route; explicitly not raw-source regeneration."""
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def frozen():
    path=HERE/'frozen_inputs.json';manifest=read(HERE/'frozen_input_manifest.json')
    assert sha(path)==manifest['frozen_inputs_sha256'],'Bundled input mismatch'
    value=read(path);inputs=value['inputs']
    for row in inputs:
        raw=value['plans'][row['id']]['original_c_binary64']
        c=[list(map(F,v)) for v in row['coefficients']]
        for expected,binary in zip(c,raw):
            r=list(map(F.from_float,binary))
            assert expected==[(x-min(r))/(max(r)-min(r)) for x in r]
        canonical=[[str(v) for v in r] for r in c]
        assert hashlib.sha256(json.dumps(canonical,separators=(',',':')).encode()).hexdigest()==row['coefficient_digest']
        row['coefficients']=c
        assert F(value['totals'][row['id']])>0
    provenance={'mode':'bundled_frozen_inputs_recalculation','raw_sources_regenerated_in_this_run':False,
      'training_targets_reconstructed_in_this_run':False,'frozen_inputs_sha256':sha(path),
      'full_source_run_provenance':value['full_source_run_provenance']}
    return inputs,provenance,value['training'],value['training_hashes'],{k:F(v) for k,v in value['totals'].items()},value['plans']

