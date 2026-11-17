"""Page-referenced report evidence, separate from observed connector status."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st


def load_validation_report():
    return json.loads((Path(__file__).parent / 'data/validation_report.json').read_text(encoding='utf-8'))


def render_provider_notice(source_id):
    for notice in load_validation_report().get('provider_notices', []):
        if notice['source_id'] == source_id:
            st.info(notice['summary'])
            st.caption(f"[Official provider notice]({notice['url']}) · {notice['notice_date']} · "
                       f"checked {notice['checked_date']}. {notice['timing_note']}")


def validation_register(catalog, report, implemented_sources):
    evidence = {row['source_id']: row for row in report['sources']}
    rows = []
    for source in catalog.to_dict('records'):
        record = evidence.get(source['source_id'], {})
        assessed = record.get('evidence_status') == 'report_assessment'
        rows.append({
            'ID': source['source_id'], 'Source': source['title'], 'Domain': source.get('domain', ''),
            'Data role': record.get('temporal_role', 'Unconfirmed'),
            'Report evidence': 'Assessed in report' if assessed else 'Mapping not confirmed',
            'Dashboard route': 'Connector available' if source['source_id'] in implemented_sources else 'Reference / access pending',
            'Access': record.get('access_category', source.get('access_level', '')),
            'Report pages': ', '.join(str(page) for page in record.get('report_pages', [])),
        })
    return pd.DataFrame(rows, columns=['ID', 'Source', 'Domain', 'Data role', 'Report evidence',
                                       'Dashboard route', 'Access', 'Report pages'])


def render_validation_summary(catalog, report, implemented_sources):
    meta = report['report']
    assessed = sum(row['evidence_status'] == 'report_assessment' for row in report['sources'])
    for column, label, value in zip(st.columns(3),
            ['Catalogue sources', 'Matched to validation report', 'Implemented data routes'],
            [len(catalog), assessed, len(set(catalog['source_id']) & set(implemented_sources))]):
        column.metric(label, value)
    st.caption(f"Validation baseline: {meta['reference']} {meta['revision']} · {meta['date']}. "
               'Report findings and implemented routes are separate from a current source-access check.')
    with st.expander('Integration priorities from the validation report'):
        for item in report.get('recommendations', []):
            st.markdown('**' + item['title'] + '**')
            st.write(item['action'])
            st.caption('Report basis: PDF pages ' + ', '.join(str(page) for page in item['report_pages']))
        st.caption(meta['interpretation_note'])
        st.download_button('Download report evidence JSON', json.dumps(report, indent=2).encode('utf-8'),
                           'CRDT_validation_report_evidence.json', 'application/json')


def render_source_validation(report, source_id):
    record = next((row for row in report['sources'] if row['source_id'] == source_id), None)
    with st.container(border=True):
        st.markdown('**Validation report findings**')
        if not record or record['evidence_status'] != 'report_assessment':
            st.info('A one-to-one report mapping has not been confirmed for this catalogue entry. '
                    'Confirm the dataset and access with its owner before planning an input.')
            return
        pages = ', '.join(str(page) for page in record['report_pages'])
        st.caption(f"{report['report']['reference']} {report['report']['revision']} · "
                   f"section {record['report_section']} · PDF pages {pages}")
        st.write(record['access_assessment'])
        left, right = st.columns(2)
        with left:
            st.markdown('**What this source supports**')
            for item in record['findings']:
                st.write('• ' + item)
            st.caption('Potential tasks: ' + ' · '.join(record['task_support']))
        with right:
            st.markdown('**Checks before integration**')
            for item in record['required_checks']:
                st.write('• ' + item)
        for item in record['limitations']:
            st.caption('Limit: ' + item)
        st.caption('Follow-up checks are proposed project actions; completing them requires source '
                   'evidence and the receiving team’s input requirements.')
