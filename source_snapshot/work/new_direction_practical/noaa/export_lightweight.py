"""Additive export: preserve local full source/GRIB caches; distribute small excerpts."""
from pathlib import Path
import csv,json,hashlib
P=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    original=[]
    for name,out,url in [('USC00010140.csv','hourly_source_excerpt.csv','https://www.ncei.noaa.gov/data/coop-hourly-precipitation/v2/access/USC00010140.csv'),('USC00010140.15m.csv','quarter_hour_source_excerpt.csv','https://www.ncei.noaa.gov/pub/data/hpd/auto/v2/beta/15min/all_csv/USC00010140.15m.csv')]:
        with (P/name).open(newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames
            selected=[dict(source_data_row=i,**r) for i,r in enumerate(reader,1) if r['DATE'].startswith(('2008-12','2009-06'))]
        with (P/out).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['source_data_row']+fields);w.writeheader();w.writerows(selected)
        original.append(dict(name=name,url=url,sha256=sha(P/name),bytes=(P/name).stat().st_size,distributed_excerpt=out,excerpt_rows=len(selected)))
    f=json.loads((P/'forecast_panel.json').read_text())
    with (P/'forecast_values.csv').open('w',newline='') as out:
        cols=['date','member','local_start_hour','local_end_hour','forecast_mm','signed_raw_increment_mm','range_sha256']
        w=csv.DictWriter(out,fieldnames=cols);w.writeheader()
        for r in f['records']:
            for i,(v,raw) in enumerate(zip(r['forecast_3h_mm'],r['signed_raw_3h_mm'])):
                w.writerow(dict(date=r['date'],member=r['member'],local_start_hour=3*i,local_end_hour=3*i+3,forecast_mm=v,signed_raw_increment_mm=raw,range_sha256=r['provenance']['range_sha256']))
    included=['protocol.txt','sensitivity_amendment.txt','implementation_note.txt','build_panel.py','summarize_panel.py','reproduce_extracted_panel.py','export_lightweight.py','observation_panel.json','forecast_panel.json','panel_result.json','panel_summary.json','panel_comparisons.csv','forecast_values.csv','hourly_source_excerpt.csv','quarter_hour_source_excerpt.csv','public_source_search.json','readme.csv.txt','readme.15min.txt','lightweight_reproduction.json','README.txt']
    optional=['independent_observation_review.py','independent_observation_review.json','independent_forecast_review.py','independent_forecast_review.json','independent_grib_headers.jsonl','manuscript_fragment.tex','bibitems.txt']
    included.extend(n for n in optional if (P/n).exists())
    manifest=dict(original_sources=original,distributed_files={n:dict(sha256=sha(P/n),bytes=(P/n).stat().st_size) for n in included},not_distributed=['gefs_cache/','python_deps/','entire multidecade station CSVs','sourcePDFs'],scope='Small extracted records and all forecastdecode/provenance metadata. Reproduce numerical results from excerpts withoutnetwork/dependencies. Optional full download/decode needs ecCodes and NumPy plus original observation sources. Local independent source audit may require original files; inspect its statedscope.',gefs_source='https://noaa-gefs-retrospective.s3.amazonaws.com/',gefs_range_objects=260,gefs_grib_messages=2080)
    (P/'lightweight_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('exported',len(included),'files',sum(v['bytes'] for v in manifest['distributed_files'].values()),'bytes')
if __name__=='__main__':main()
