"""Small path-rebasing/containment regression; no empirical checks or writes."""
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('decision_builder',ROOT/'work/build_decision_manuscript.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
fixtures={
    'work/decision_revision/confirmation/summary.json':ROOT/'work/decision_revision/confirmation/summary.json',
    r'work\decision_revision\confirmation\summary.json':ROOT/'work/decision_revision/confirmation/summary.json',
    'D:/archive/work/outer/work/dreplay_nested/work/decision_revision/confirmation/cases.csv':ROOT/'work/decision_revision/confirmation/cases.csv',
    'D:/archive/work/outer/work/dreplay_nested/outputs/report.json':ROOT/'outputs/report.json',
    str(ROOT/'work/local/outputs/report.json'):ROOT/'work/local/outputs/report.json',
}
for source,expected in fixtures.items():assert builder.local_pin(source)==expected.resolve()
for invalid in ['../../outside.json','D:/archive/other/report.json','D:/archive/work/../../outside.json']:
    try:builder.local_pin(invalid)
    except AssertionError:pass
    else:raise AssertionError('Unsafe or unrecognized path accepted: '+invalid)
print('Passed five path-rebasing fixtures and three containment rejections.')
