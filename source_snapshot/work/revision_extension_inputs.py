"""Explicit lightweight files for the randomized and natural-record extensions.

Shared by packaging and isolated reconstruction. Never recursively copy a work
directory: the NOAA GRIB/dependency caches and exploratory pilots stay excluded.
"""
import hashlib
import json
from pathlib import Path

RANDOM_DIR = 'work/new_direction_randomized'
COMPACT_DIR = 'work/randomized_recovery_root'
NOAA_DIR = 'work/new_direction_practical/noaa'
TIE_DIR = 'work/randomized_tie_review'
SCALING_DIR = 'work/randomized_scaling_review'
HOLDOUT_DIR = 'work/randomized_holdout_review'
REFIT_DIR = 'work/fresh_refit_review'
REFIT_FILES = ('README.txt','protocol.txt','comparison_protocol.txt','refit.py',
               'export_public.py','verify_refit.py','prepared.json','selection.json',
               'fit_metadata.json','fresh_result.json','fresh_predictions_public.csv',
               'omission_manifest.json','independent_metrics_full.csv',
               'independent_metrics_public.csv','independent_verification.json',
               'independent_verification_public.json','refit_fragment.tex','provenance.json')
RANDOM_FILES = ('protocol.txt','implementation_note.txt','randomized_recovery_screen.py',
                'result.json','cases.csv','meters.csv','cohorts.csv','pairs.csv',
                'support.csv','lp_solutions.jsonl','independent_verification.json',
                'independent_free_copy_trace.csv')
COMPACT_FILES = ('compact_randomized.py','compact_policy.py','verify_compact_policy.py',
                 'compact_verification.json','policy_verification.json','protocol.txt',
                 'policy_protocol.txt','theory_section.tex','bibitem_suggestions.tex')
TIE_FILES = ('protocol.txt','audit_ties.py','policies.jsonl','selection_complete.json',
             'cases.csv','meters.csv','cohorts.csv','support.csv','result.json',
             'theory_review.txt','provenance_wording_amendment.txt',
             'verify_ties.py','independent_verification.json')
SCALING_FILES = ('protocol.txt','instances.json','benchmark.py','results.json',
                 'results.csv','summary.json','scaling_fragment.tex','provenance.json',
                 'verify_scaling.py','archival_verification.json')
HOLDOUT_FILES = ('README.txt','protocol.txt','holdout.py','verify_holdout.py',
                 'selection_inputs.jsonl','prepared.json','policies.jsonl',
                 'selection_complete.json','cases.csv','meters.csv','cohorts.csv',
                 'pairs.csv','support.csv','original_primary_meters.csv',
                 'original_primary_cohorts.csv','original_primary_pairs.csv',
                 'result.json','verification.json','independent_verification.json',
                 'holdout_fragment.tex','provenance.json')
NOAA_FILES = ('protocol.txt','sensitivity_amendment.txt','implementation_note.txt',
              'build_panel.py','summarize_panel.py','reproduce_extracted_panel.py',
              'export_lightweight.py','observation_panel.json','forecast_panel.json',
              'panel_result.json','panel_summary.json','panel_comparisons.csv',
              'forecast_values.csv','hourly_source_excerpt.csv','quarter_hour_source_excerpt.csv',
              'public_source_search.json','readme.csv.txt','readme.15min.txt',
              'lightweight_reproduction.json','README.txt','independent_observation_review.py',
              'independent_observation_review.json','independent_forecast_review.py',
              'independent_forecast_review.json','independent_grib_headers.jsonl',
              'manuscript_fragment.tex','bibitems.txt')
ALLOWED_FRAGMENT_TEX = frozenset((COMPACT_DIR+'/theory_section.tex',
                                COMPACT_DIR+'/bibitem_suggestions.tex',
                                NOAA_DIR+'/manuscript_fragment.tex',
                                SCALING_DIR+'/scaling_fragment.tex',
                                HOLDOUT_DIR+'/holdout_fragment.tex',
                                REFIT_DIR+'/refit_fragment.tex'))
EXTENSION_PATHS = ('work/revision_extension_inputs.py','work/integrate_randomized_revision.py',
                   'work/verify_randomized_revision.py',
                   'work/reproduce_final_revision.py',
                   'work/validate_supplement_delta.py',
                   'work/packaging_baseline_manifest.json',
                   'work/packaging_baseline_verification.json',
                   'work/final_peer_review/editorial_trim.py',
                   *(RANDOM_DIR+'/'+n for n in RANDOM_FILES),
                   *(COMPACT_DIR+'/'+n for n in COMPACT_FILES),
                   *(TIE_DIR+'/'+n for n in TIE_FILES),
                   *(SCALING_DIR+'/'+n for n in SCALING_FILES),
                   *(HOLDOUT_DIR+'/'+n for n in HOLDOUT_FILES),
                   *(REFIT_DIR+'/'+n for n in REFIT_FILES),
                   *(NOAA_DIR+'/'+n for n in NOAA_FILES),
                   NOAA_DIR+'/lightweight_manifest.json',
                   NOAA_DIR+'/lightweight_clean_verification.json')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def extension_paths(root):
    root=Path(root)
    missing=[n for n in EXTENSION_PATHS if not (root/n).is_file()]
    if missing: raise FileNotFoundError('Missing extension inputs: '+', '.join(missing))
    return EXTENSION_PATHS

def validate_extension_inputs(root):
    """Validate frozen small-source provenance; never execute analyses here."""
    root=Path(root)
    extension_paths(root)
    read=lambda rel:json.loads((root/rel).read_text(encoding='utf-8'))
    def match(relative,expected):
        # Historical Windows analyses recorded relative paths with backslashes.
        # Normalize only separators so archived provenance also checks on POSIX.
        relative=relative.replace('\\','/')
        assert sha(root/relative)==expected, 'Extension source mismatch: '+relative
    result=read(RANDOM_DIR+'/result.json')
    assert result['status']=='passed' and result['cases']==20736 and result['lp_solutions']==1074
    match(RANDOM_DIR+'/randomized_recovery_screen.py',result['script_hash'])
    match(RANDOM_DIR+'/protocol.txt',result['protocol_hash'])
    for name,expected in result['output_hashes'].items():match(RANDOM_DIR+'/'+name,expected)
    # result.json records the pre-revision manuscript hash as an immutable
    # historical context snapshot, not a dependency on the now revised TeX.
    audit=read(RANDOM_DIR+'/independent_verification.json')
    assert audit['status']=='passed' and audit['cases']==20736
    for name,expected in audit['source_hashes'].items():match(name,expected)
    compact=read(COMPACT_DIR+'/compact_verification.json')
    assert compact['status']=='passed'
    match(COMPACT_DIR+'/compact_randomized.py',compact['script_sha256'])
    match(COMPACT_DIR+'/protocol.txt',compact['protocol_sha256'])
    policy=read(COMPACT_DIR+'/policy_verification.json')
    assert policy['status']=='passed'
    for name,expected in policy['source_hashes'].items():match(COMPACT_DIR+'/'+name,expected)
    match(COMPACT_DIR+'/compact_verification.json',policy['source_value_report_sha256'])
    ties=read(TIE_DIR+'/result.json')
    assert ties['status']=='passed' and ties['case_count']==20736
    assert ties['positive_cases']==1074 and ties['secondary_lp_count']==2148
    assert ties['selection_completed_before_reference_read'] is True
    match(TIE_DIR+'/audit_ties.py',ties['script_sha256'])
    match(TIE_DIR+'/policies.jsonl',ties['selection_sha256'])
    for name,expected in ties['source_hashes'].items():match(name,expected)
    selection=read(TIE_DIR+'/selection_complete.json')
    assert selection['status']=='passed' and selection['reference_targets_read_for_selection'] is False
    match(TIE_DIR+'/policies.jsonl',selection['policy_sha256'])
    for name,expected in selection['inputs'].items():match(name,expected)
    tie_audit=read(TIE_DIR+'/independent_verification.json')
    assert tie_audit['status']=='passed'
    assert (tie_audit['original_cases_retained'],tie_audit['finite_game_matrices_reconstructed'],
            tie_audit['secondary_optimality_checks'],tie_audit['positive_support_checks'])==(20736,1074,2148,4693)
    match(TIE_DIR+'/verify_ties.py',tie_audit['script_sha256'])
    for name,expected in tie_audit['source_hashes'].items():match(name,expected)
    scaling=read(SCALING_DIR+'/provenance.json')
    for name,expected in scaling['file_sha256'].items():match(SCALING_DIR+'/'+name,expected)
    assert scaling['api_sha256_before']==scaling['api_sha256_after']
    for name,expected in scaling['api_sha256_after'].items():match(COMPACT_DIR+'/'+name,expected)
    scaling_audit=read(SCALING_DIR+'/archival_verification.json')
    assert scaling_audit['status']=='PASS'
    assert (scaling_audit['compact_cases'],scaling_audit['finite_comparisons'],
            scaling_audit['predeclared_skips'])==(28,12,16)
    match(SCALING_DIR+'/provenance.json',scaling_audit['provenance_sha256'])
    for name,expected in scaling_audit['source_hashes'].items():match(SCALING_DIR+'/'+name,expected)
    for name,expected in scaling_audit['api_hashes'].items():match(COMPACT_DIR+'/'+name,expected)
    holdout=read(HOLDOUT_DIR+'/provenance.json')
    assert holdout['status']=='FROZEN' and set(holdout['canonical_files'])==set(HOLDOUT_FILES)
    for name,expected in holdout['file_sha256'].items():match(HOLDOUT_DIR+'/'+name,expected)
    for name,expected in holdout['source_sha256'].items():match(name,expected)
    held_result=read(HOLDOUT_DIR+'/result.json')
    assert held_result['status']=='PASS' and held_result['selection_before_evaluation'] is True
    assert (held_result['consumers'],held_result['meter_days'],held_result['cases'],
            held_result['positive_width_cases'])==(30,3210,19260,899)
    match(HOLDOUT_DIR+'/holdout.py',held_result['script_sha256'])
    match(HOLDOUT_DIR+'/protocol.txt',held_result['protocol_sha256'])
    for name,expected in held_result['output_hashes'].items():match(HOLDOUT_DIR+'/'+name,expected)
    for name,expected in held_result['source_hashes'].items():match(name,expected)
    held_audit=read(HOLDOUT_DIR+'/independent_verification.json')
    assert held_audit['status']=='PASS'
    assert (held_audit['cases'],held_audit['positive_cases'],
            held_audit['positive_probability_batches'])==(19260,899,3958)
    for name,key in [('verify_holdout.py','checker_sha256'),('protocol.txt','protocol_sha256'),
                     ('policies.jsonl','policy_sha256'),('result.json','result_sha256')]:
        match(HOLDOUT_DIR+'/'+name,held_audit[key])
    for name,expected in held_audit['source_hashes'].items():match(name,expected)
    noaa=read(NOAA_DIR+'/lightweight_manifest.json')
    assert set(noaa['distributed_files'])==set(NOAA_FILES), 'NOAA whitelist changed'
    for name,record in noaa['distributed_files'].items():
        match(NOAA_DIR+'/'+name,record['sha256'])
        assert (root/NOAA_DIR/name).stat().st_size==record['bytes']
    clean=read(NOAA_DIR+'/lightweight_clean_verification.json')
    assert clean['status']=='passed'
    match(NOAA_DIR+'/lightweight_manifest.json',clean['manifest_sha256'])
    refit=read(REFIT_DIR+'/provenance.json')
    assert refit['status']=='FROZEN' and set(refit['canonical_public_files'])==set(REFIT_FILES)
    for name,expected in refit['file_sha256'].items():match(REFIT_DIR+'/'+name,expected)
    for name,expected in refit['source_sha256'].items():
        if name=='outputs/study_predictions.csv' and not (root/name).exists():
            assert read('outputs/review_frozen_forecasts.json')['original_predictions_sha256']==expected
        else:match(name,expected)
    fitted=read(REFIT_DIR+'/fresh_result.json')
    assert fitted['status']=='PASS' and not fitted['failures']
    assert (fitted['series_completed'],fitted['trained_estimators_completed'],fitted['prediction_rows'])==(64,192,166536)
    refit_public=read(REFIT_DIR+'/independent_verification_public.json')
    assert refit_public['status']=='passed'
    assert (refit_public['rows_compared'],refit_public['series_compared'],refit_public['forecast_values_compared'])==(159984,61,639936)
    for name,expected in refit_public['source_hashes'].items():match(name,expected)
    return {'randomized_cases':audit['cases'],'compact_lp_checks':audit['compact_versus_finite_game_checks'],
            'policy_cases':policy['cases'],'noaa_files':len(NOAA_FILES),
            'tie_policy_cases':ties['positive_cases'],'secondary_tie_lps':ties['secondary_lp_count'],
            'scaling_compact_cases':scaling_audit['compact_cases'],
            'scaling_finite_comparisons':scaling_audit['finite_comparisons'],
            'randomized_holdout_cases':held_audit['cases'],
            'randomized_holdout_supports':held_audit['positive_probability_batches'],
            'fresh_refit_public_rows':refit_public['rows_compared'],
            'fresh_refit_full_series_archived':fitted['series_completed'],
            'noaa_raw_decode_scope':'archived independent audit; clean replay uses decoded excerpts'}
