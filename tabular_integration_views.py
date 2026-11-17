"""Session-local CSV preview and explicit observation field declarations."""
import hashlib
import json

import pandas as pd
import streamlit as st

from tabular_integration import map_tabular_observations, read_csv_upload


TIME_ASSUMPTIONS = {'Unverified — keep blocked': None, 'Assume UTC': 'UTC',
                    'Assume Europe/London': 'Europe/London'}


def _clear_upload():
    for key in list(st.session_state):
        if key.startswith('integration_csv_') or key == 'integration_upload_records':
            st.session_state.pop(key, None)


def render_csv_mapping(views):
    """Return only an approved matching mapping, including a retained session snapshot."""
    if 'raw_data' not in views:
        st.info('CSV integration requires raw-data access in the selected partner view.')
        return None
    st.caption('Upload a UTF-8 CSV: at most 2 MB, 10,000 rows and 100 columns. Records stay in this session. '
               'Mapping declares candidate identities and meaning; it does not establish spatial matches or terminology approval.')
    uploaded = st.file_uploader('Upload observation CSV', type=['csv'], max_upload_size=2, key='integration_csv_file')
    if uploaded is None:
        records = st.session_state.get('integration_upload_records')
        metadata = st.session_state.get('integration_csv_metadata')
        if records is not None and metadata:
            st.info(f"Uploaded records are still loaded in this session: {metadata['label']} ({len(records):,} rows).")
            st.button('Clear uploaded records', key='integration_csv_clear', on_click=_clear_upload)
            return records, metadata
        st.info('Choose a CSV to preview its original fields, then apply an explicit column mapping.')
        return None
    content = uploaded.getvalue()
    content_hash = hashlib.sha256(content).hexdigest()
    seen = st.session_state.get('integration_csv_seen', {})
    if seen.get('content_sha256') != content_hash:
        st.session_state.pop('integration_upload_records', None)
        st.session_state.pop('integration_csv_metadata', None)
        seen = {'content_sha256': content_hash, 'collected_at': pd.Timestamp.now(tz='UTC').isoformat()}
        st.session_state['integration_csv_seen'] = seen
    st.button('Clear uploaded records', key='integration_csv_clear', on_click=_clear_upload)
    try:
        frame = read_csv_upload(content)
    except ValueError as error:
        st.error(str(error))
        return None
    st.dataframe(frame.head(100), hide_index=True, width='stretch')
    st.caption(f'{len(frame):,} original data rows · preview shows up to 100. Invalid observations remain in the audit.')
    mapping, metadata = {}, {}
    fields = [('entity_id', 'Entity ID'), ('value', 'Observation value'), ('event_time', 'Observation time'),
              ('metric', 'Metric'), ('unit', 'Unit'), ('datum_uri', 'Datum URI'),
              ('qualifier', 'Qualifier'), ('concept_uri', 'Declared concept URI')]
    columns = [None, *frame.columns.tolist()]
    for field, _ in fields:
        key = 'integration_csv_' + field + '_column'
        if st.session_state.get(key) not in columns:
            st.session_state.pop(key, None)
    with st.form('integration_csv_mapping'):
        metadata['source_label'] = st.text_input('Upload label', value=uploaded.name, max_chars=200,
                                                key='integration_csv_label')
        metadata['kind'] = st.selectbox('Observation kind', ['generic', 'water_level'],
            format_func=lambda value: {'generic': 'Generic observations', 'water_level': 'Water level'}[value],
            key='integration_csv_kind')
        for field, label in fields:
            mapping[field] = st.selectbox(label + ' column', columns,
                format_func=lambda value: 'Choose a column' if value is None else value,
                key='integration_csv_' + field + '_column')
            if field not in {'entity_id', 'value', 'event_time'}:
                metadata[field] = st.text_input(label + ' constant (when no column is selected)', max_chars=500,
                                                key='integration_csv_' + field + '_constant')
        assumption = st.selectbox('CSV time assumption', list(TIME_ASSUMPTIONS), key='integration_csv_timezone')
        metadata['event_timezone'] = TIME_ASSUMPTIONS[assumption]
        st.caption('Metric and unit require a column or constant. Water level also requires a datum and qualifier. '
                   'Use complete ISO 8601 dates and times, e.g. 2026-11-01T10:00:00Z; a date or time alone is invalid. '
                   'Naive times stay blocked until you explicitly assume UTC or Europe/London; ambiguous local times remain invalid. '
                   'Availability uses the dashboard upload time, never an invented historical arrival.')
        applied = st.form_submit_button('Apply column mapping', key='integration_csv_apply', type='primary')
    signature = json.dumps({'content_sha256': content_hash, 'column_mapping': mapping, **metadata}, sort_keys=True)
    previous = st.session_state.get('integration_csv_metadata', {})
    if previous.get('signature') != signature:
        st.session_state.pop('integration_upload_records', None)
        st.session_state.pop('integration_csv_metadata', None)
    if applied:
        try:
            records = map_tabular_observations(frame, mapping, metadata, seen['collected_at'])
        except ValueError as error:
            st.error(str(error))
            return None
        collection = dict(metadata, signature=signature, content_sha256=content_hash,
            label=metadata['source_label'] or uploaded.name, filename=uploaded.name,
            source_id='CSV:' + content_hash, column_mapping=mapping, original_row_count=len(frame),
            mapped_at=seen['collected_at'], collected_at=seen['collected_at'],
            requested_sources=['csv_upload'], collection_period=None,
            traffic_timezone_assumption=None, observation_context=None,
            collection_status=[{'source_id': 'CSV:' + content_hash, 'status': 'mapped_upload',
                                'records': len(frame), 'access_note': 'User-declared CSV mapping; session-only'}],
            profile_status='User-declared CSV mapping; identities and concepts are provisional')
        st.session_state['integration_upload_records'] = records
        st.session_state['integration_csv_metadata'] = collection
        for key in ['integration_series', 'integration_cutoff_date', 'integration_cutoff_time']:
            st.session_state.pop(key, None)
    records = st.session_state.get('integration_upload_records')
    if records is None:
        st.info('Choose the fields and constants, then select Apply column mapping to use this CSV.')
        return None
    st.success(f'{len(records):,} mapped observations loaded in this session. Inspect row decisions before exporting.')
    return records, st.session_state['integration_csv_metadata']
