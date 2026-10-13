"""Stdlib-only reconstruction from distributed NOAA source/forecast excerpts.

This verifies archived decode metadata and arithmetic; it does not independently
decode GRIB bytes or prove absence of records beyond the documented source search.
"""
from pathlib import Path
import hashlib,json,math
P=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def close(a,b):
    assert math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9),(a,b)

def contrast(a,b,y):
    return sum((u-v)**2-(u-w)**2 for u,v,w in zip(y,a,b))/8

def main():
    obs=json.loads((P/'observation_panel.json').read_text())
    forecasts=json.loads((P/'forecast_panel.json').read_text())
    result=json.loads((P/'panel_result.json').read_text())
    assert result['status']=='passed' and len(result['cases'])==52
    fby={};repairs=0
    for f in forecasts['records']:
        assert len(f['messages'])==8
        vals=[m['value'] for m in f['messages']]
        rebuilt=[];signed=[]
        for i in range(0,8,2):
            x,t=vals[i:i+2]
            q=.5*sum(2**f['messages'][k]['binaryScaleFactor']/10**f['messages'][k]['decimalScaleFactor'] for k in [i,i+1])
            assert x>=0 and t>=0 and x-t<=q+1e-8
            first=min(x,t);rebuilt.extend([first,t-first]);signed.extend([x,t-x])
            repairs+=x>t
        for a,b in zip(rebuilt,f['forecast_3h_mm']):close(a,b)
        for a,b in zip(signed,f['signed_raw_3h_mm']):close(a,b)
        fby[f['date'],f['member']]=(rebuilt,signed)
    oby={x['date']:x for x in obs['cases']}
    vertices=0;natural=0;dry=0;certified=0
    for c in result['cases']:
        o=oby[c['date']];r=o['hourly_source_record']
        vals=[int(r[f'HR{h:02}Val']) for h in range(24)]
        if o['kind']=='natural_accumulation':
            assert [r[f'HR{h:02}MF'].strip() for h in range(24)]==['a']+['.']*22+['A']
            total=vals[23]*.254;natural+=1
        else:
            assert all(v==0 for v in vals)
            total=sum(vals)*.254;dry+=1
        close(total,c['total_mm'])
        for variant in [0,1]:
            a=fby[c['date'],'c00'][variant]
            b=[sum(fby[c['date'],m][variant][i] for m in ['c00','p01','p02','p03','p04'])/5 for i in range(8)]
            ds=[]
            for i in range(8):
                y=[0]*8;y[i]=total;ds.append(contrast(a,b,y));vertices+=1
            ref=c if variant==0 else c['signed_unrepaired_sensitivity']
            close(min(ds),ref['lower']);close(max(ds),ref['upper'])
            close(contrast(a,b,[total/8]*8),ref['uniform_point'])
            if variant==0:
                for x,y in zip(a,c['control_3h_mm']):close(x,y)
                for x,y in zip(b,c['ensemble_3h_mm']):close(x,y)
                if o['kind']=='natural_accumulation':certified+=min(ds)>1e-10 or max(ds)<-1e-10
    assert (natural,dry,repairs,certified)==(9,43,28,2)
    out=dict(status='passed',script_sha256=sha(__file__),source_hashes={n:sha(P/n) for n in ['observation_panel.json','forecast_panel.json','panel_result.json']},days=52,forecast_member_days=len(fby),decoded_message_records=2080,raw_and_preprocessed_direct_vertex_checks=vertices,natural_cases=natural,complete_zero_controls=dry,preprocessed_natural_certificates=certified,packing_repaired_bin_pairs=repairs,scope='Distributed metadata/excerpt arithmetic only; no freshGRIBdecode, fullsource re-download or global publicarchive absence proof.')
    (P/'lightweight_reproduction.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
