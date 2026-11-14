"""Partner walkthrough; illustrative connections never enter the result registry."""
import json

import pandas as pd
import streamlit as st

from integration_demo import (
    DEMO_CASES,
    check_connection,
    connection_summary,
    execution_preview,
    get_demo_connection,
    get_handover_template,
)
from module_contracts import load_module_registry
from workbench_views import navigate


ROLES = [
    ('WP1', 'Common definitions and platform guide', 'Publish entity, relationship and metric definitions, interface conventions and examples.'),
    ('WP2', 'Source data, monitoring and quality', 'Supply source records/access, metadata, permissions, versions and quality/gap evidence; adapt its own monitoring module.'),
    ('WP3', 'Domain models and model-chain integration', 'Own internal adaptation and model inputs; deliver scenarios/impact/recovery. T3.8 coordinates execution chains.'),
    ('WP4', 'Dependencies and interoperability', 'Own internal adaptation and cross-sector models; confirm dependencies and exchange rules. T4.4: Lancaster and all partners.'),
    ('WP5', 'Security, ethics and integrated impact', 'Own internal adaptation and security models; define controls. ID50 integrates observations/results; developer to be agreed.'),
    ('WP6', 'User tasks, demonstrators and acceptance', 'Specify decisions and acceptance criteria; test the integrated system and return issues to responsible teams.'),
    ('WP7', 'Governance and rollout', 'Agree use/access, deployment and maintenance responsibilities. T7.3: Lancaster and all partners.'),
]


def render_integration_demo(catalog):
    st.subheader('Ontology-guided integration demo')
    st.caption('PARTNER WALKTHROUGH · DRAFT connections · illustrative values · no partner model is invoked')
    for col, title, description in zip(st.columns(3),
            ['Shared viewing', 'Data handover', 'Linked execution'],
            ['Find information from different teams for the same object, time and scenario.',
             'Connect one named output to one named input through an agreed conversion.',
             'Schedule accepted handovers in order, with missing-input and failure handling.']):
        with col, st.container(border=True):
            st.markdown('**' + title + '**')
            st.write(description)
    st.info('The ontology guide defines common meanings. Providers and consumers agree each connection; technical checks do not establish scientific acceptance.')

    workbench, delivery, presentation = st.tabs(['Connection workbench', 'Delivery & existing data', 'Partner presentation'])
    with workbench:
        case_id = st.selectbox('Connection example', list(DEMO_CASES), format_func=DEMO_CASES.get,
                               index=list(DEMO_CASES).index('shared_view'), key='integration_demo_case')
        connection = get_demo_connection(case_id)
        st.caption('All demo: objects, variables, models and values below are illustrative. Their example time/scenario is independent of the monitoring date controls.')
        source, target = connection['source'], connection['target']
        left, right = st.columns(2)
        for col, title, product in [(left, 'PROVIDER OUTPUT', source), (right, 'CONSUMER INPUT REQUIREMENT', target)]:
            with col, st.container(border=True):
                st.markdown('**' + title + '**')
                st.text(product['wp'] + ' · ' + product['model_id'])
                st.code(product['variable'], language=None)
                st.write('Object: ' + product['entity_id'])
                st.write('Unit: ' + product['unit'] + ' · Reference: ' + product['reference'])
                st.write('Time basis: ' + product['time_basis'])
                st.write('Spatial scope: ' + product['spatial_scope'])
                st.write('Scenario: ' + product['scenario_id'])
                if title == 'PROVIDER OUTPUT':
                    st.write('Illustrative value: ' + ('Missing' if product['value'] is None else str(product['value'])))
                st.caption('Version: ' + product['version'] + ' · Ontology: ' + product['ontology_version'])

        if connection['mode'] == 'handover':
            baseline = connection['baseline']
            st.markdown('**Declared adaptation for this example**')
            st.code(connection['adapter']['expression'], language=None)
            st.write('Illustrative baseline: ' + ('Missing' if baseline['value'] is None else str(baseline['value']))
                     + ' ' + baseline['unit'] + ' · Reference: ' + baseline['reference'])
            st.caption('This example formula needs domain agreement and a valid baseline. The platform does not infer it from an ontology relationship.')
        elif connection['mode'] == 'view_only':
            st.info('Shared viewing links information to an object. It does not hand an output to another model or create a calculation chain.')
        else:
            st.info('Dynamic feedback needs explicit initial conditions, exchange timing and a coupling method before it can be scheduled.')

        checks = check_connection(connection)
        summary = connection_summary(checks)
        if any(row['status'] == 'Blocked' for row in checks):
            st.error(summary)
        else:
            st.info(summary)
        check_frame = pd.DataFrame(checks)
        st.dataframe(check_frame[['check', 'status', 'owner']].rename(columns=str.title),
                     hide_index=True, width='stretch', height=len(checks) * 35 + 38)
        preferred = next((i for i, row in enumerate(checks) if row['status'] == 'Blocked'),
                         next((i for i, row in enumerate(checks) if row['status'] == 'Review'), 0))
        chosen = st.selectbox('Inspect a connection check', range(len(checks)), index=preferred,
                              format_func=lambda i: checks[i]['check'], key=f'integration_check_{case_id}')
        st.write(checks[chosen]['detail'])
        st.caption('Responsible: ' + checks[chosen]['owner'])
        st.caption('Pass means this illustrative check passed. Review means a partner decision is still needed. Blocked means the handover or execution cannot proceed.')

        if st.button('Preview execution order', type='primary', key='integration_preview'):
            st.markdown('**Conditional order preview**')
            st.dataframe(pd.DataFrame(execution_preview(connection, checks)).rename(columns=str.title),
                         hide_index=True, width='stretch')
            st.caption('Preview only: no model runs, source refresh, imported-result mutation or operational prediction takes place.')
        st.download_button('Download this connection draft',
                           json.dumps(dict(connection, checks=checks, execution_preview=execution_preview(connection, checks)), indent=2),
                           'CRDT_connection_demo_draft.json', 'application/json', key='integration_connection_download')

    with delivery:
        st.markdown('**Each WP owns its contribution; each connection has a provider and a consumer.**')
        st.dataframe(pd.DataFrame(ROLES, columns=['WP', 'Contribution', 'Delivery responsibility']),
                     hide_index=True, width='stretch')
        selected_wp = st.selectbox('Inspect a WP responsibility', range(len(ROLES)), format_func=lambda i: ROLES[i][0],
                                   key='integration_wp_responsibility')
        st.write(ROLES[selected_wp][1] + ': ' + ROLES[selected_wp][2])
        st.write('The provider explains and verifies the output. The consumer confirms input suitability and owns its model-entry adaptation, unless both teams explicitly agree otherwise.')
        st.caption('Gantt worklines guide ownership. Software integration, shared frontend, WP5 ID50 development and hosting/release/operations still need named implementers.')
        st.markdown('**Existing project data inventory**')
        st.write(f'{len(catalog)} source records are listed in the current project catalogue. Listing is not evidence of model-input readiness.')
        columns = [name for name in ['source_id', 'title', 'format', 'period', 'access_level', 'status'] if name in catalog]
        st.dataframe(catalog[columns], hide_index=True, width='stretch')
        st.button('Inspect project data catalogue', on_click=navigate, args=('Data & Research', 'Dataset Catalogue'),
                  key='integration_open_catalogue')
        st.caption('Source records remain separate from the illustrative connection above. Actual observations, quality and selected-object inspection are available through Monitor.')
        st.download_button('Download current WP responsibility register', json.dumps(load_module_registry(), indent=2),
                           'CRDT_WP_responsibilities.json', 'application/json', key='integration_roles_download')

    with presentation:
        st.markdown('**A short route for a partner meeting**')
        for text in [
            '1. Open Monitor: select an object and explain the current observations, time basis and evidence.',
            '2. Open this demo: distinguish shared viewing, an explicit data handover and linked execution.',
            '3. Compare the aligned example with missing-input, reference and time mismatches; inspect why they block.',
            '4. Preview the order: distinguish an illustrative adapter from an accepted, executable model chain.',
            '5. Ask each team to describe its products/models, input requirements, outputs, evidence and responsible contact.',
            '6. Ask each provider/consumer pair to agree one connection record and its verification method.'
        ]:
            st.write(text)
        st.markdown('**Partner handover checklist**')
        st.write('Product/model and version; purpose; responsible team; named inputs/outputs; object IDs and meanings; units/references; time and space; quality/missingness; transformations; access/use terms; verification and acceptance; execution requirements.')
        st.download_button('Download partner handover template', json.dumps(get_handover_template(), indent=2),
                           'CRDT_partner_handover_DRAFT.json', 'application/json', key='integration_template_download')
        st.caption('Fill in the draft for partner discussion. This demo does not register endpoints, accept approvals or execute submitted models.')
        st.markdown('Design background: [OpenMI exchange items and adapted outputs](https://docs.ogc.org/is/11-014r3/11-014r3.html) · [BMI model interfaces](https://bmi.csdms.io/en/stable/bmi.spec.html). This walkthrough borrows these principles; it does not implement those standards.')
