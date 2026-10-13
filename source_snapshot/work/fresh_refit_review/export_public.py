"""Preserve the established BLEM redistribution boundary in fresh-refit evidence."""
from pathlib import Path
import csv,hashlib,json
HERE=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while chunk:=f.read(8*1024*1024):h.update(chunk)
    return h.hexdigest()
def main():
    result=json.loads((HERE/'fresh_result.json').read_text());assert result['status']=='PASS'
    source=HERE/'fresh_predictions.csv';target=HERE/'fresh_predictions_public.csv'
    assert sha(source)==result['output_hashes']['fresh_predictions.csv']
    assert not target.exists(),'Refuse to overwrite public export'
    kept=omitted=0;meters=set()
    with source.open(newline='',encoding='utf-8') as f,target.open('w',newline='',encoding='utf-8') as out:
        reader=csv.DictReader(f);writer=csv.DictWriter(out,fieldnames=reader.fieldnames);writer.writeheader()
        for row in reader:
            if row['cohort']=='blem_counters':omitted+=1;continue
            writer.writerow(row);kept+=1;meters.add((row['cohort'],row['meter']))
    assert kept==159984 and omitted==6552 and len(meters)==61
    report=dict(status='PASS',public_rows=kept,public_series=61,omitted_rows=omitted,omitted_series=3,omitted_cohort='blem_counters',public_sha256=sha(target),local_full_sha256=sha(source),local_full_rows=kept+omitted,scope='Public export contains UCI household and Portugal rows only, including additional consumers. Full fresh BLEM target/persistence rows stay local. All-series aggregate comparisons and source/configuration hashes may be distributed. Full row replay requires raw-data reconstruction and fresh fitting.',source_hashes=result['source_hashes'])
    (HERE/'omission_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
