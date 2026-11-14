"""Fixed project and scientific evidence downloads, outside operational navigation."""
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st


ROOT=Path(__file__).parent


def project_archive():
    tasks=[]
    for code,title,modules in [
        ('T6.1','Transport congestion & logistics',['WP2','WP3','WP4']),
        ('T6.2','Incident response & recovery',['WP2','WP3','WP4','WP5']),
        ('T6.3','Severe-weather management',['WP2','WP3','WP5']),
        ('T6.4','Supply-chain disruption',['WP2','WP3','WP4'])]:
        tasks.append({'status':'DRAFT - not an accepted demonstration','task_id':code,'task':title,
            'required_modules':modules,'acceptance_requirements':[
                'Confirm user decision and permitted interventions with operational partners',
                'Validate the required data coverage, units and time alignment',
                'Record model versions, inputs and scientific validation',
                'Check evidence distinctions, missing inputs and access constraints',
                'Record user feedback and assign each issue to its module owner']})
    governance={'status':'DRAFT - policy decisions pending','controls':[
        {'area':'Application access','implemented':'Password gate before loading data',
         'handover_needed':'Institutional identity, server-side authorisation and audit ownership'},
        {'area':'Partner views','implemented':'Prototype navigation rules',
         'handover_needed':'Approved roles, per-product access and data-owner permission'},
        {'area':'Partner packages','implemented':'Schema checks; session-local intake; no uploaded code execution',
         'handover_needed':'Provider identity, semantic alignment and scientific review'},
        {'area':'Data provenance','implemented':'Source/time metadata, diagnostics and exports',
         'handover_needed':'Reviewed retention, licences and cross-partner sharing rules'},
        {'area':'Service ownership','implemented':'Streamlit application and connector code',
         'handover_needed':'Named hosting, release, incident response and maintenance teams'}]}
    buffer=BytesIO()
    with ZipFile(buffer,'w',ZIP_DEFLATED) as archive:
        archive.writestr('wp_modules.json',(ROOT/'data/wp_modules.json').read_bytes())
        archive.writestr('module-integration.md',(ROOT/'docs/module-integration.md').read_bytes())
        archive.writestr('demonstrator_tasks.json',json.dumps(tasks,indent=2))
        archive.writestr('governance_handover.json',json.dumps(governance,indent=2))
    return buffer.getvalue()


def research_archive():
    buffer=BytesIO()
    with ZipFile(buffer,'w',ZIP_DEFLATED) as archive:
        for name in ['research_signature_summary.csv','research_signature_folds.csv','research_provenance.json']:
            archive.writestr(name,(ROOT/'data'/name).read_bytes())
        archive.writestr('README.txt',
            'Archived offline Liverpool 12-hour warning-aligned sparse-learning experiment.\n'
            'These results are independent of current dashboard observation dates.\n'
            'Four-fold means and sample SD across folds; SD is not a confidence interval.\n'
            'Thresholds were selected on validation data. Four event clusters limit generalisation.\n'
            'False-positive windows per represented day are not alert episodes.\n'
            'Event recall follows the experiment window rule. These are not current port risk estimates.\n'
            'See research_provenance.json for the source workbook hash and definitions.\n')
    return buffer.getvalue()


def render_archives():
    with st.expander('Project documents and research archive'):
        st.caption('WP handovers, draft demonstrator/governance records and archived scientific evidence.')
        left,right=st.columns(2)
        left.download_button('Download project documents',project_archive(),'CRDT_project_documents.zip','application/zip')
        right.download_button('Download research archive',research_archive(),'CRDT_research_archive.zip','application/zip')
