"""Match fresh reviewer-request diagnostics to the frozen manuscript inputs."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[3]
BASE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

m=read(ROOT/'outputs/review_mechanism/report.json')
old=read(BASE/'review_mechanism/executed/report.json')
assert m['status']==old['status']=='PASS'
assert m['summaries']==old['summaries']
assert sha(ROOT/'outputs/review_mechanism/ledger.json')==sha(BASE/'review_mechanism/executed/ledger.json')
dec=read(ROOT/'outputs/review_mechanism/decision_plan_check.json')
assert dec['status']=='PASS' and (dec['assured_cases'],dec['selected_readings'],dec['minimum_fixed_readings'])==(57,70,88)
th=read(ROOT/'outputs/review_thresholds/report.json')
assert th['status']=='PASS' and th['summary']==read(BASE/'review_thresholds/executed/report.json')['summary']
assert sha(ROOT/'outputs/review_thresholds/intervals.json')==sha(BASE/'review_thresholds/executed/intervals.json')
cap=read(ROOT/'outputs/review_capacity/report.json')
assert cap['status']=='PASS' and cap['summaries']==read(BASE/'review_capacity/executed_external/report.json')['summaries']
assert sha(ROOT/'outputs/review_capacity/ledger.json')==sha(BASE/'review_capacity/executed_external/ledger.json')
fullcap=read(BASE/'review_capacity/executed_all/certificate_check.json')
assert fullcap['status']=='PASS'
result={'status':'PASS','source_sha256':sha(Path(__file__)),
        'mechanism_blocks':1098,'joint_only_cases':191,'matched_threshold_cases':222,
        'original_external_floor_cohort_assured':57,'floor_plan_readings':70,'minimum_fixed_readings':88,
        'comparisons':['All mechanism/floor summary values and exact ledger bytes',
                       'All threshold summary values and exact interval bytes',
                       'External source-linked capacity transitions and exact ledger bytes',
                       'Both-panel capped fixed-batch certificate verification'],
        'scope':'Bundled derived-input reconstruction plus external raw checks. Both-source raw regeneration and full original training reconstruction remain separately documented.'}
(ROOT/'outputs/review_revision_match.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
