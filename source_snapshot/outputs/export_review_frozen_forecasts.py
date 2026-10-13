"""Additive lossless textual export for no-refit review-analysis reconstruction.

UCI targets are included under the source CC BY 4.0 licenses. BLEM targets and
their daily-persistence copies are omitted and must be reconstructed from the
pinned original counters. All retained CSV fields keep their original strings;
unlike the earlier numerical export, this script never parses forecast floats.
Existing scientific source files are read-only.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = OUT/'study_predictions.csv'
    summary_path = OUT/'study_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    original_hash = sha(source)
    assert original_hash == summary['artifacts']['study_predictions.csv']['sha256']
    expected_fields = ['cohort','meter','timestamp','truth_kwh','daily','ridge','hist_gradient_boosting','mlp']
    target = OUT/'review_frozen_forecasts.csv'
    rows = omitted = 0
    with source.open(newline='',encoding='utf-8') as src, target.open('w',newline='',encoding='utf-8') as dst:
        reader, writer = csv.reader(src), csv.writer(dst)
        header = next(reader)
        assert header == expected_fields
        writer.writerow(header)
        for row in reader:
            assert len(row)==len(header)
            if row[0]=='blem_counters':
                row[3] = row[4] = ''
                omitted += 1
            else:
                assert row[0] in ('household','portugal')
            writer.writerow(row)
            rows += 1
    assert sha(source)==original_hash
    metadata = {
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'format':'Original CSV header, row ordering, retained field strings and csv.writer CRLF serialization',
        'rows':rows,'omitted_blem_target_and_daily_rows':omitted,
        'included_uci_target_rows':rows-omitted,'models':summary['design']['models'],
        'original_predictions_sha256':original_hash,'output_sha256':sha(target),
        'script_sha256':sha(Path(__file__)),'study_summary_sha256':sha(summary_path),
        'retained_fields_are_original_strings':True,'model_refitting':False,
        'omission':'Only BLEM truth_kwh and daily fields are blank; targets and persistence copies are obtained from pinned raw counters, never fabricated.',
        'uci_attribution':[
            {'title':'Individual Household Electric Power Consumption','repository':'UCI Machine Learning Repository',
             'doi':'https://doi.org/10.24432/C58K54','license':'CC BY 4.0',
             'changes':'Minute average power converted to complete hourly kWh; eligible original held-out rows retained.'},
            {'title':'ElectricityLoadDiagrams20112014','repository':'UCI Machine Learning Repository',
             'doi':'https://doi.org/10.24432/C58C86','license':'CC BY 4.0',
             'changes':'End-stamped quarter-hour average power shifted to interval starts and summed/divided by four; eligible original held-out rows retained.'}],
        'limitations':'Reproduces frozen-predictor evaluation; not independent forecasting, fresh training or a new validation population.'}
    (OUT/'review_frozen_forecasts.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'rows':rows,'omitted_blem_rows':omitted,'original_unchanged':True,
                      'output_sha256':metadata['output_sha256']},indent=2))


if __name__=='__main__':
    main()
