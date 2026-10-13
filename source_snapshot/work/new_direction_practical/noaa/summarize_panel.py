"""Source-fixed zero-query summaries; no forecast fitting or case selection."""
import csv, hashlib, json
from pathlib import Path
from datetime import datetime, timezone

P=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sign=lambda l,u: 'control' if u < -1e-10 else 'ensemble' if l > 1e-10 else 'unresolved'

def main():
    j=json.loads((P/'panel_result.json').read_text())
    assert j['status']=='passed' and len(j['cases'])==52 and not j['failures']
    f=json.loads((P/'forecast_panel.json').read_text())
    assert len(f['records'])==260
    rows=[]
    for c in j['cases']:
        a=c['control_3h_mm'];b=c['ensemble_3h_mm'];T=c['total_mm']
        coeff=[2*(bb-aa)/8 for aa,bb in zip(a,b)]
        const=sum(aa*aa-bb*bb for aa,bb in zip(a,b))/8
        low_total=max(0,T-2.54);high_total=T+2.54
        m=min(coeff);M=max(coeff)
        slo=const+(low_total if m>=0 else high_total)*m
        shi=const+(high_total if M>=0 else low_total)*M
        assert slo<=c['lower']+1e-9 and shi>=c['upper']-1e-9
        raw=c['signed_unrepaired_sensitivity']
        rows.append(dict(date=c['date'],kind=c['kind'],recorded_total_mm=T,paired_lower=c['lower'],paired_upper=c['upper'],paired_width=c['width'],paired_decision=c['strict_decision'],individual_lower=c['independent_contrast'][0],individual_upper=c['independent_contrast'][1],individual_decision=sign(*c['independent_contrast']),uniform_point=c['uniform_point'],uniform_decision=sign(c['uniform_point'],c['uniform_point']),signed_raw_lower=raw['lower'],signed_raw_upper=raw['upper'],signed_raw_decision=sign(raw['lower'],raw['upper']),nominal_2p54mm_total_lower=low_total,nominal_2p54mm_total_upper=high_total,nominal_2p54mm_gap_lower=slo,nominal_2p54mm_gap_upper=shi,nominal_2p54mm_decision=sign(slo,shi),observed_gap=c.get('observed_gap','')))
    with (P/'panel_comparisons.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    natural=[r for r in rows if r['kind']=='natural_accumulation'];controls=[r for r in rows if r['kind']=='complete_control']
    repair_records=[x for x in f['records'] if x['packing_repairs']]
    repairs=[r for x in repair_records for r in x['packing_repairs']]
    record=[dict(date=r['date'],paired=[r['paired_lower'],r['paired_upper']],decision=r['paired_decision'],individual_decision=r['individual_decision'],uniform_decision=r['uniform_decision'],nominal_2p54mm_decision=r['nominal_2p54mm_decision']) for r in natural]
    def counts(group,key):return {k:sum(r[key]==k for r in group) for k in ['control','ensemble','unresolved']}
    whole_lower=(sum(r['paired_lower'] for r in natural)+sum(r['observed_gap'] for r in controls))/52
    whole_upper=(sum(r['paired_upper'] for r in natural)+sum(r['observed_gap'] for r in controls))/52
    summary=dict(status='passed',created_utc=datetime.now(timezone.utc).isoformat(),script_sha256=sha(__file__),source_hashes={n:sha(P/n) for n in ['protocol.txt','sensitivity_amendment.txt','implementation_note.txt','build_panel.py','observation_panel.json','forecast_panel.json','panel_result.json','USC00010140.csv','USC00010140.15m.csv','station_inventory.csv','readme.csv.txt','readme.15min.txt','public_source_search.json']},natural_days=9,complete_dry_controls=43,omitted_calendar_days=9,forecast_member_days=260,grib_messages=2080,range_download_bytes=sum(int(x['provenance']['headers']['Content-Length']) for x in f['records']),natural_paired_decisions=counts(natural,'paired_decision'),natural_individual_decisions=counts(natural,'individual_decision'),natural_nominal_tolerance_decisions=counts(natural,'nominal_2p54mm_decision'),all_case_raw_preprocessing_decision_changes=sum(r['paired_decision']!=r['signed_raw_decision'] for r in rows),packing_repaired_member_days=len(repair_records),packing_repaired_bin_pairs=len(repairs),maximum_negative_raw_increment_mm=min([r['raw_second'] for r in repairs],default=0),whole52day_interval=[whole_lower,whole_upper],whole52day_decision=sign(whole_lower,whole_upper),natural_cases=record,limitations=['Purposively selected single-station9event panel; no prevalence or general forecast-skill claim.','All43complete controls have zero recorded rainfall, mostlyZassumed zeros. They only check degenerate dry bounds.','No finer truth for natural periods; no natural decision-error rate can be calculated.','Exactness is conditional on reported totals; nominal2.54mm perturbation is not a validated physical error bound.','GEFSv12 retrospective forecasts, nominal00cycle and physical03initialization; selected valid windows start06UTC.','Nearest gridpoint8.6565km away; grid-area vs station observation representativeness remains.','Nonnegative preprocessing repairs differently packed nested fields; all raw increments and endpoint sensitivity retained.','No hourly acquisition-cost, recoverability, actual operational deployment, ML model or SOTA claim.','Public-source closure refers only to documented checked endpoints/files; unavailable legacy endpoints do not prove global absence.'])
    summary['natural_paired_outcomes']={'strict_ensemble':sum(r['paired_decision']=='ensemble' for r in natural),'strict_control':sum(r['paired_decision']=='control' for r in natural),'sign_ambiguous':sum(r['paired_lower']<0<r['paired_upper'] for r in natural),'identified_tie':sum(r['paired_lower']==r['paired_upper']==0 for r in natural)}
    summary['complete_dry_control_outcomes']={'strict_control':sum(r['paired_decision']=='control' for r in controls),'strict_ensemble':sum(r['paired_decision']=='ensemble' for r in controls),'identified_tie':sum(r['paired_lower']==r['paired_upper']==0 for r in controls)}
    summary['decision_label_note']='Legacy unresolved labels mean no strict decision; exact ties are separately identified here. No frozen numerical result changed.'
    (P/'panel_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
