"""Geographic Monitor; illustrative assets and source observations stay separate."""
from datetime import date
from html import escape
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from monitoring_views import chart_style
from network_map import network_deck
from semantic_service import SemanticDemo


def _choose_object(entity_id, type_uri, name=''):
    st.session_state['semantic_entity_id'] = entity_id
    if st.session_state.get('semantic_type', 'All') not in ('All', type_uri):
        st.session_state['semantic_type'] = 'All'
    query = st.session_state.get('semantic_search', '').strip().casefold()
    if query and query not in (entity_id+' '+name).casefold():
        st.session_state['semantic_search'] = ''
    st.session_state['semantic_revision'] = st.session_state.get('semantic_revision', 0) + 1


def _change_type():
    st.session_state['semantic_revision'] = st.session_state.get('semantic_revision', 0) + 1


def _selected_id(event):
    if event:
        for records in event.get('selection', {}).get('objects', {}).values():
            if records:
                return records[0].get('entity_id')
    return None


def _spatial_view(entities, relations, selected, revision, visible_ids=None):
    deck = network_deck(entities, relations, selected, visible_ids)
    event = st.pydeck_chart(deck, height=420, width='stretch', key=f'semantic_map_{revision}', on_select='rerun',
                            selection_mode='single-object')
    return _selected_id(event)


def _product_panel(product):
    st.markdown('**' + product['title'] + '**')
    st.caption(product['role'] + ' · ' + product['product_id'])
    frame = pd.DataFrame(product['rows'])
    if frame.empty:
        st.info('No sample records match this time and scenario. Missing data is not replaced with zero.')
        return
    if product['kind'] == 'series':
        for metric in product['metrics']:
            if metric['key'] not in frame:
                continue
            fig = go.Figure(go.Scatter(x=pd.to_datetime(frame['timestamp'], utc=True), y=frame[metric['key']],
                mode='lines+markers', connectgaps=False, line={'color':'#7C83FD','width':2}, name=metric['label']))
            fig.update_layout(xaxis_title='Sample time (UTC)', yaxis_title=f"{metric['label']} ({metric['unit']})")
            st.plotly_chart(chart_style(fig, 225), width='stretch', key=product['product_id']+'_'+metric['key'])
            if metric.get('datum'):
                st.caption('Reference: ' + metric['datum'])
    else:
        st.dataframe(frame, hide_index=True, width='stretch')
        st.caption(' · '.join(f"{m['label']}: {m['unit']}" for m in product['metrics']))
    with st.expander('Source, quality and interpretation · ' + product['title']):
        st.json({'provenance':product['provenance'], 'quality':product['quality']})


def render_semantic_demo():
    service = SemanticDemo()
    entities = service.entities()
    ids = {row['entity_id']:row for row in entities}
    pending = st.session_state.pop('semantic_pending_entity', None)
    if pending in ids:
        _choose_object(pending, ids[pending]['type_uri'], ids[pending]['name'])
    if st.session_state.get('semantic_entity_id') not in ids:
        st.session_state['semantic_entity_id'] = 'demo:terminal_a'
    with st.container(key='semantic_example_status'):
        st.markdown('<div class="semantic-status"><span>ILLUSTRATIVE DATA</span>'
            '<span>DRAFT ONTOLOGY</span><span>SAMPLE DAY · 14 NOV 2026</span></div>', unsafe_allow_html=True)
    start = end = date(2026, 11, 14)
    left, centre, right = st.columns([.9,2.5,1.25], gap='small')
    with left, st.container(border=True, key='semantic_objects'):
        st.markdown('<div class="workbench-panel-title">OBJECT REGISTER</div>', unsafe_allow_html=True)
        types = {'All':'All types', **{r['uri']:r['label'] for r in service.types()}}
        query = st.text_input('Search assets', key='semantic_search', on_change=_change_type).strip().casefold()
        type_uri = st.selectbox('Object type', list(types), format_func=types.get, key='semantic_type',
                                on_change=_change_type)
        candidates = service.entities(None if type_uri=='All' else type_uri)
        candidates = [row for row in candidates if query in (row['entity_id']+' '+row['name']).casefold()]
        if not candidates:
            st.info('No assets match this search and type. Clear the search or change the type.')
            return
        if st.session_state['semantic_entity_id'] not in {e['entity_id'] for e in candidates}:
            st.session_state['semantic_entity_id'] = candidates[0]['entity_id']
        selected = st.session_state['semantic_entity_id']
        for entity in candidates:
            st.button(entity['name'].removesuffix(' (DEMO)'), key='semantic_object_'+entity['entity_id'], width='stretch',
                      type='primary' if entity['entity_id']==selected else 'secondary',
                      on_click=_choose_object, args=(entity['entity_id'],entity['type_uri'],entity['name']))
            st.caption(entity['type_label'])
    entity = ids[selected]
    with centre, st.container(border=True, key='semantic_spatial'):
        st.markdown('<div class="workbench-panel-title">SPATIAL & RELATIONSHIP VIEW</div>', unsafe_allow_html=True)
        relation_labels = {'All':'All declared relationships', **{r['uri']:r['label'] for r in service.relation_types()}}
        relation_type = st.selectbox('Relationship',list(relation_labels),format_func=relation_labels.get,
                                            key='semantic_relation', on_change=_change_type)
        relation_arg = None if relation_type=='All' else relation_type
        relations = service.relations(relation_type=relation_arg, start=start, end=end)
        picked = _spatial_view(entities, relations, selected, st.session_state.get('semantic_revision',0),
                               [row['entity_id'] for row in candidates])
        if picked in ids and picked!=selected:
            st.session_state['semantic_pending_entity'] = picked
            st.rerun()
        st.caption(f"{len(relations)} declared illustrative relationships · {relation_labels[relation_type]}")
        st.caption('Fictional assets · approximate coordinates · arrows follow the recorded source → target predicate.')
        st.markdown('<div class="semantic-legend"><span><i class="semantic-node"></i>Selected object</span>'
            '<span><i class="semantic-edge"></i>Direct declared link</span>'
            '<span><i class="semantic-edge semantic-muted"></i>Other declared link</span></div>', unsafe_allow_html=True)
    with right, st.container(border=True, key='semantic_inspector'):
        st.markdown('<div class="workbench-panel-title">OBJECT INSPECTOR</div>', unsafe_allow_html=True)
        st.markdown('**' + entity['name'].removesuffix(' (DEMO)') + '**')
        st.markdown('<dl class="workbench-reference semantic-fields"><dt>Object ID</dt><dd>'
            +escape(entity['entity_id'])+'</dd><dt>Type</dt><dd>'+escape(entity['type_uri'])+'</dd>'
            '<dt>Evidence</dt><dd>Illustrative</dd></dl>', unsafe_allow_html=True)
        st.caption('Source aliases: '+', '.join(entity['source_ids']))
        st.markdown('<div class="workbench-panel-title">RELATED OBJECTS</div>', unsafe_allow_html=True)
        related = service.related(selected, relation_type=relation_arg, start=start, end=end)
        for item in related:
            neighbor = ids[item['neighbor_id']]
            st.button(item['display_relation']+' · '+item['neighbor_name'].removesuffix(' (DEMO)'), width='stretch',
                      key='semantic_related_'+item['neighbor_id'], on_click=_choose_object,
                      args=(item['neighbor_id'],neighbor['type_uri'],neighbor['name']))
        if not related:
            st.caption('No matching declared relationship in this selection; this does not establish independence.')
    with st.container(border=True, key='semantic_content'):
        profile = service.profile(selected)
        readings, connections, results, sources = st.tabs(['Readings', 'Connections', 'Results', 'Sources'])
        with readings:
            for tab in profile['tabs']:
                if tab['kind'] != 'scenario':
                    for product in service.products(selected, tab['id'], start, end):
                        _product_panel(product)
        with connections:
            for edge in related:
                provider = next(source for source in service.sources if source['source_id']==edge['evidence_ref'])
                st.markdown('**'+edge['relation_label']+'**')
                st.caption(edge['source_id']+' → '+edge['target_id']+' · '+edge['direction']+' relative to selected asset')
                st.caption('Evidence: '+edge['evidence_role']+' · '+edge['evidence_ref'])
                st.caption('Provider: '+provider['name']+' · local illustrative package')
                st.caption('Valid '+edge['valid_from']+' to '+edge['valid_to'])
            if not related:
                st.info('No declared connections match the selected asset and relationship.')
        with results:
            st.caption('Synthetic scenario results for the illustrative sample day. These are fixed example outputs.')
            scenarios = {scenario['scenario_id']:scenario['name'] for scenario in service.scenarios}
            scenario = st.selectbox('Scenario', list(scenarios), format_func=scenarios.get, key='semantic_scenario')
            products = [product for tab in profile['tabs'] if tab['kind']=='scenario'
                        for product in service.products(selected, tab['id'], start, end, scenario_id=scenario)]
            for product in products:
                _product_panel(product)
            if not products:
                st.caption('No synthetic result is supplied for this object and scenario.')
            if st.session_state.get('partner_runs'):
                from workbench_views import render_runs
                st.markdown('**Published partner results**')
                render_runs()
        with sources:
            st.caption(service.metadata['ontology_status'])
            st.caption(entity['coordinate_note'])
            st.dataframe(pd.DataFrame(service.sources), hide_index=True, width='stretch')
    with st.expander('Semantic definitions, products and relationship evidence'):
        st.write(service.metadata['ontology_status'])
        st.caption(service.metadata['coordinate_note']+' '+service.metadata['relation_note'])
        st.dataframe(pd.DataFrame(relations), hide_index=True, width='stretch')
        st.download_button('Download this demo context', json.dumps({'entity_id':selected,'type_uri':entity['type_uri'],
            'start':str(start),'end':str(end),'scenario_id':scenario,
            'relationship_filter':relation_arg,'relations':relations,'ontology_status':service.metadata['ontology_status'],
            'evidence_role':'illustrative'},indent=2), 'CRDT_semantic_demo_context.json','application/json')
