"""Configure explicit feature bindings without requesting feeds or running models."""
import hashlib
import json

import streamlit as st

from model_inputs import build_model_inputs


def render_model_input_builder(records, snapshot, rules):
    with st.expander('Build a model input table'):
        st.caption('Name one feature for each selected measurement series and confirm its expected unit. '
                   'Source identities, units and datums remain separate; these bindings do not establish scientific suitability.')
        if snapshot.empty:
            st.info('Select measurement series with observations before configuring model inputs.')
            return
        metadata = ['series_id', 'source_id', 'source', 'entity_id', 'metric', 'unit', 'datum_uri']
        defaults = snapshot.reindex(columns=metadata).reset_index(drop=True)
        defaults.insert(0, 'input_name', ['feature_' + str(index + 1) for index in range(len(defaults))])
        defaults['expected_unit'] = defaults['unit']
        defaults['required'] = True
        identity = hashlib.sha256(defaults[metadata].to_json(orient='records').encode()).hexdigest()[:12]
        editor_key = 'integration_contract_requirements_' + identity
        base_key, saved_key = 'integration_contract_base_' + identity, 'integration_contract_saved_' + identity
        if editor_key not in st.session_state or base_key not in st.session_state:
            st.session_state[base_key] = st.session_state.get(saved_key, defaults).copy(deep=True)
        # Keep the editor's input fixed while mounted; changed defaults reset its edit state.
        requirements = st.data_editor(st.session_state[base_key], hide_index=True, width='stretch', num_rows='fixed',
            disabled=metadata, key=editor_key,
            column_config={'input_name': st.column_config.TextColumn('Input name', required=True),
                           'expected_unit': st.column_config.TextColumn('Expected unit', required=True),
                           'required': st.column_config.CheckboxColumn('Required')})
        st.session_state[saved_key] = requirements.copy(deep=True)
        allow = st.checkbox('Allow configured time assumptions for these inputs', value=False,
                            key='integration_contract_allow_time_assumptions')
        st.caption('Time assumption permission accepts the stated conversion for this table; its unverified status remains in every export.')
        try:
            wide, checks = build_model_inputs(snapshot, requirements, allow_time_assumptions=allow)
        except ValueError as error:
            st.error(str(error))
            return
        required = checks.loc[checks['required']]
        if required['passed'].all():
            st.success('Configured checks passed for all required inputs.')
        else:
            st.warning('Required inputs need attention. Missing values remain empty in the input table.')
        st.dataframe(wide, hide_index=True, width='stretch')
        st.dataframe(checks, hide_index=True, width='stretch')
        replay = rules.get('availability_mode') == 'replay'
        evidence = 'Simulated replay; availability and loss follow scenario rules' if replay else 'Dashboard retrieval; provider publication time is unknown'
        st.caption(evidence + '. Configured checks cover data availability and declared units; model validation belongs to the receiving team.')
        selected_records = records.loc[records['series_id'].isin(requirements['series_id'])]
        contract = {'cutoff': wide.iloc[0]['cutoff'].isoformat(), 'rules': rules,
                    'evidence_class': evidence, 'allow_time_assumptions': allow,
                    'result': 'Configured checks passed' if required['passed'].all() else 'Required checks failed',
                    'requirements': json.loads(requirements.to_json(orient='records', date_format='iso')),
                    'inputs': json.loads(wide.to_json(orient='records', date_format='iso')),
                    'checks': json.loads(checks.to_json(orient='records', date_format='iso')),
                    'source_records': json.loads(selected_records.to_json(orient='records', date_format='iso')),
                    'scope': 'Candidate feature table; no model execution or scientific acceptance'}
        st.download_button('Download model input CSV', wide.to_csv(index=False).encode(),
            'CRDT_model_inputs.csv', 'text/csv', key='integration_contract_inputs_download', on_click='ignore')
        st.download_button('Download input checks CSV', checks.to_csv(index=False).encode(),
            'CRDT_model_input_checks.csv', 'text/csv', key='integration_contract_checks_download', on_click='ignore')
        st.download_button('Download input contract JSON', json.dumps(contract, indent=2, default=str, allow_nan=False).encode(),
            'CRDT_model_input_contract.json', 'application/json', key='integration_contract_download', on_click='ignore')
