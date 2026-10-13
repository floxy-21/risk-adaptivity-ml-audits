"""Additive public UCI-only case export; original scientific files unchanged.

The full BLEM daily bound/query records are withheld from the redistribution
bundle: paired endpoints are linear measurements of source targets, even when
target columns themselves are absent. The complete local experiment and all
cohort summaries remain unchanged. Raw data plus study_recovery.py regenerate
the full case file; this exporter performs no experiment or model fitting.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    original=OUT/'study_recovery_cases.csv'
    public=OUT/'study_recovery_cases_public.csv'
    original_hash=sha(original)
    report=json.loads((OUT/'study_recovery.json').read_text(encoding='utf-8'))
    assert report['hashes'][original.name]==original_hash
    counts={};retained=0
    with original.open(newline='',encoding='utf-8') as source, public.open('w',newline='',encoding='utf-8') as target:
        reader,writer=csv.reader(source),csv.writer(target)
        header=next(reader);writer.writerow(header)
        cohort_index=header.index('cohort')
        for row in reader:
            cohort=row[cohort_index]
            counts[cohort]=counts.get(cohort,0)+1
            assert cohort in ('household','portugal','blem_counters')
            if cohort!='blem_counters':
                writer.writerow(row);retained+=1
    assert sha(original)==original_hash
    manifest={
        'status':'passed','created_utc':datetime.now(timezone.utc).isoformat(),
        'omitted_files':{original.name:{'sha256':original_hash,'bytes':original.stat().st_size,
            'rows':sum(counts.values()),'full_rows':sum(counts.values()),'public_rows':retained,
            'omitted_blem_rows':counts.get('blem_counters',0),
            'reason':'BLEM daily bound endpoints and query indices can disclose source readings algebraically; the mixed full case file is omitted from redistribution only.'}},
        'public_files':{public.name:{'sha256':sha(public),'bytes':public.stat().st_size,
            'rows':retained,'included_cohorts':['household','portugal'],
            'source_file':original.name,'full_file':original.name,
            'transformation':'Omit blem_counters rows only; retain every remaining original CSV field string, header and row ordering.'}},
        'public_to_full':{public.name:original.name},
        'cohort_source_rows':counts,'omitted_blem_rows':counts.get('blem_counters',0),
        'script_sha256':sha(Path(__file__)),'original_source_unchanged':True,
        'scope':'Public UCI-only detailed diagnostic rows plus unchanged full-cohort summary reports. This is a packaging restriction, not a scientific exclusion or a reanalysis.',
        'regeneration':'After exact raw input reconstruction, run outputs/study_recovery.py to regenerate full old recovery cases. The default review-revision command uses cached full-cohort diagnostics and does not rerun this historical extension.',
        'uci_attribution':[{'dataset':'Individual Household Electric Power Consumption','doi':'https://doi.org/10.24432/C58K54','license':'CC BY 4.0'},
                           {'dataset':'ElectricityLoadDiagrams20112014','doi':'https://doi.org/10.24432/C58C86','license':'CC BY 4.0'}]}
    (OUT/'study_recovery_cases_public_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'passed','original_rows':sum(counts.values()),'public_rows':retained,'omitted_blem_rows':counts.get('blem_counters',0),'original_unchanged':True},indent=2))


if __name__=='__main__':
    main()
