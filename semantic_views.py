"""Ontology-guided home demo; synthetic products remain separate from live feeds."""
from datetime import date
from html import escape
import json
import math

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from monitoring_views import chart_style
from port_map import MARITIME_STYLE
from semantic_service import SemanticDemo


def _choose_object(entity_id, type_uri):
    st.session_state['semantic_entity_id'] = entity_id
    if st.session_state.get('semantic_type', 'All') not in ('All', type_uri):
        st.session_state['semantic_type'] = 'All'
    st.session_state['semantic_revision'] = st.session_state.get('semantic_revision', 0) + 1


def _show_scenario():
    st.session_state['semantic_content_mode'] = 'Scenario results'


def _change_type():
    st.session_state['semantic_revision'] = st.session_state.get('semantic_revision', 0) + 1


def _selected_id(event, graph=False):
    if not event:
        return None
    selection = event.get('selection', {})
    if graph:
        points = selection.get('points', [])
        if points:
            value = points[0].get('customdata')
            return value[0] if isinstance(value, (list, tuple)) and value else value
    else:
        for records in selection.get('objects', {}).values():
            if records:
                return records[0].get('entity_id')
    return None


def _spatial_view(entities, relations, selected, graph, revision):
    ids = {row['entity_id']: row for row in entities}
    if graph:
        positions = {row['entity_id']: (math.cos(2*math.pi*i/len(entities)), math.sin(2*math.pi*i/len(entities)))
                     for i, row in enumerate(entities)}
        fig = go.Figure()
        for relation in relations:
            a, b = positions[relation['source_id']], positions[relation['target_id']]
            active = selected in (relation['source_id'], relation['target_id'])
            fig.add_trace(go.Scatter(x=[a[0], b[0]], y=[a[1], b[1]], mode='lines',
                line={'color':'#41c2cc' if active else '#496374','width':2.4 if active else 1},
                hoverinfo='skip', showlegend=False))
            fig.add_annotation(x=(a[0]+b[0])/2, y=(a[1]+b[1])/2, text=escape(relation['relation_label']),
                showarrow=False, bgcolor='#112434', borderpad=2,
                font={'size':11,'color':'#d9eef5' if active else '#91aab9'})
            if relation['relation_type'] != 'demo:connectedTo':
                fig.add_annotation(x=a[0]+.72*(b[0]-a[0]), y=a[1]+.72*(b[1]-a[1]),
                    ax=a[0]+.55*(b[0]-a[0]), ay=a[1]+.55*(b[1]-a[1]),
                    xref='x', yref='y', axref='x', ayref='y', text='', showarrow=True,
                    arrowhead=2, arrowcolor='#41c2cc' if active else '#678697', arrowsize=1)
        fig.add_trace(go.Scatter(x=[positions[row['entity_id']][0] for row in entities],
            y=[positions[row['entity_id']][1] for row in entities], mode='markers+text',
            text=[row['type_label'] for row in entities], hovertext=[row['name'] for row in entities],
            textposition=['middle left' if positions[row['entity_id']][0]>.7 else
                          'middle right' if positions[row['entity_id']][0]<-.7 else 'top center' for row in entities],
            customdata=[[row['entity_id']] for row in entities],
            marker={'size':[24 if row['entity_id']==selected else 17 for row in entities],
                    'color':['#41c2cc' if row['entity_id']==selected else '#9ab6c9' for row in entities],
                    'line':{'color':'#d9eef5','width':1}},
            hovertemplate='%{hovertext}<br>%{customdata[0]}<extra>Illustrative object</extra>', showlegend=False))
        fig.update_xaxes(visible=False, range=[-1.5,1.5]); fig.update_yaxes(visible=False, range=[-1.4,1.5])
        fig = chart_style(fig, 365).update_layout(hovermode='closest', paper_bgcolor='#112434',
            plot_bgcolor='#112434', font={'color':'#d9e8ef','size':12})
        event = st.plotly_chart(fig, width='stretch', key=f'semantic_graph_{revision}',
                               on_select='rerun', selection_mode='points')
        return _selected_id(event, graph=True)
    points = [dict(row, color=[65,194,204] if row['entity_id']==selected else [154,182,201],
                   label_border=1 if row['entity_id']==selected else 0,
                   label_anchor='start' if row['lon'] < -3.0165 else 'end') for row in entities]
    links = [{'source':[ids[r['source_id']]['lon'], ids[r['source_id']]['lat']],
              'target':[ids[r['target_id']]['lon'], ids[r['target_id']]['lat']],
              'name':r['relation_label'],
              'color':[65,194,204,240] if selected in (r['source_id'],r['target_id']) else [129,157,176,120],
              'width':3 if selected in (r['source_id'],r['target_id']) else 1.2} for r in relations]
    layers = [pdk.Layer('LineLayer', links, get_source_position='source', get_target_position='target',
                         get_color='color', get_width='width', width_min_pixels=1),
              pdk.Layer('ScatterplotLayer', points, id='semantic_objects', get_position='[lon, lat]',
                         get_fill_color='color', get_radius=55, radius_min_pixels=7, pickable=True),
              pdk.Layer('ScatterplotLayer', [row for row in points if row['entity_id']==selected],
                         get_position='[lon, lat]', get_radius=85, radius_min_pixels=11, filled=False,
                         stroked=True, get_line_color=[255,255,255], line_width_min_pixels=2),
              pdk.Layer('TextLayer', points, id='semantic_labels', get_position='[lon, lat]', get_text='type_label',
                         get_color=[223,239,247], get_size=12, get_pixel_offset=[0,-19],
                         font_family=pdk.types.String('Consolas, monospace'),
                         background=True, get_background_color=[10,29,43,235], background_padding=[5,3],
                         get_border_width='label_border', get_border_color=[65,194,204,255],
                         get_text_anchor='label_anchor', pickable=True)]
    deck = pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=53.4475,longitude=-3.0165,zoom=13.15),
                    map_style=MARITIME_STYLE, tooltip={'html':'<b>{name}</b><br/>Illustrative object'})
    event = st.pydeck_chart(deck, height=365, width='stretch', key=f'semantic_map_{revision}', on_select='rerun',
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
                mode='lines+markers', connectgaps=False, line={'color':'#157985','width':2}, name=metric['label']))
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
        _choose_object(pending, ids[pending]['type_uri'])
    if st.session_state.get('semantic_entity_id') not in ids:
        st.session_state['semantic_entity_id'] = 'demo:terminal_a'
    with st.container(key='semantic_heading'):
        st.subheader('CRDT port dashboard version 1')
        st.markdown('<div class="semantic-status"><span>ILLUSTRATIVE DATA</span>'
            '<span>DRAFT ONTOLOGY</span><span>SAMPLE DAY · 14 NOV 2026</span></div>', unsafe_allow_html=True)
    with st.container(key='semantic_context'):
        cols = st.columns([1.3,1.4,1.3], gap='small')
        period = cols[0].date_input('Demo period', value=(date(2026,11,14),date(2026,11,14)), key='semantic_period')
        mode = cols[1].radio('Content mode', ['Observations & state','Scenario results'], horizontal=True,
                             key='semantic_content_mode')
        scenarios = {s['scenario_id']:s['name'] for s in service.scenarios}
        scenario = cols[2].selectbox('Scenario', list(scenarios), format_func=scenarios.get,
                                     key='semantic_scenario', disabled=mode!='Scenario results')
    if len(period)!=2:
        st.info('Select both dates for the demo period.')
        return
    start, end = period
    left, centre, right = st.columns([.9,2.5,1.25], gap='small')
    with left, st.container(border=True, key='semantic_objects'):
        st.markdown('<div class="workbench-panel-title">OBJECT REGISTER</div>', unsafe_allow_html=True)
        types = {'All':'All types', **{r['uri']:r['label'] for r in service.types()}}
        type_uri = st.selectbox('Object type', list(types), format_func=types.get, key='semantic_type',
                                on_change=_change_type)
        candidates = service.entities(None if type_uri=='All' else type_uri)
        if st.session_state['semantic_entity_id'] not in {e['entity_id'] for e in candidates}:
            st.session_state['semantic_entity_id'] = candidates[0]['entity_id']
        selected = st.session_state['semantic_entity_id']
        for entity in candidates:
            st.button(entity['name'].removesuffix(' (DEMO)'), key='semantic_object_'+entity['entity_id'], width='stretch',
                      type='primary' if entity['entity_id']==selected else 'secondary',
                      on_click=_choose_object, args=(entity['entity_id'],entity['type_uri']))
            st.caption(entity['type_label'])
    entity = ids[selected]
    with centre, st.container(border=True, key='semantic_spatial'):
        st.markdown('<div class="workbench-panel-title">SPATIAL & RELATIONSHIP VIEW</div>', unsafe_allow_html=True)
        controls = st.columns([1,1.25], gap='small')
        view = controls[0].radio('Spatial view', ['Map','Relations'], key='semantic_spatial_view', horizontal=True)
        relation_labels = {'All':'All declared relationships', **{r['uri']:r['label'] for r in service.relation_types()}}
        relation_type = controls[1].selectbox('Relationship',list(relation_labels),format_func=relation_labels.get,
                                            key='semantic_relation')
        relation_arg = None if relation_type=='All' else relation_type
        relations = service.relations(relation_type=relation_arg, start=start, end=end)
        picked = _spatial_view(entities, relations, selected, view=='Relations', st.session_state.get('semantic_revision',0))
        if picked in ids and picked!=selected:
            st.session_state['semantic_pending_entity'] = picked
            st.rerun()
        st.caption(f"{len(relations)} declared illustrative relationships · {relation_labels[relation_type]}")
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
                      args=(item['neighbor_id'],neighbor['type_uri']))
        if not related:
            st.caption('No matching declared relationship in this selection; this does not establish independence.')
        st.markdown('<div class="workbench-panel-title">VIEW CONTEXT</div>', unsafe_allow_html=True)
        st.markdown('<dl class="workbench-reference semantic-fields"><dt>Period</dt>'
            f'<dd>{start}<br>to {end}</dd><dt>Content</dt><dd>'
            +escape(scenarios[scenario] if mode=='Scenario results' else 'Illustrative observations and state')
            +'</dd></dl>', unsafe_allow_html=True)
    content, analysis = st.columns([3.4,1.25], gap='small')
    with content, st.container(border=True, key='semantic_content'):
        st.markdown('<div class="workbench-panel-title">OBJECT DATA & RESULTS</div>', unsafe_allow_html=True)
        profile = service.profile(selected)
        tabs = [t for t in profile['tabs'] if (t['kind']=='scenario') == (mode=='Scenario results')]
        if not tabs:
            st.info('No content profile is registered for this mode.')
        else:
            for tab, area in zip(tabs, st.tabs([t['label'] for t in tabs])):
                with area:
                    products = service.products(selected, tab['id'], start, end,
                                                 scenario_id=scenario if mode=='Scenario results' else None)
                    for product in products:
                        _product_panel(product)
                    if not products:
                        st.info('No sample product matches this object, view and period.')
    with analysis, st.container(border=True, key='semantic_analysis'):
        st.markdown('<div class="workbench-panel-title">RELATED ANALYSES</div>', unsafe_allow_html=True)
        for model in service.models(selected):
            st.markdown('**'+model['name']+'**')
            st.markdown('<div class="semantic-status"><span>MODEL NOT CONNECTED</span></div>', unsafe_allow_html=True)
            st.button('Run model', key='semantic_run_'+model['model_id'], disabled=True, width='stretch')
            with st.expander('Model requirements & status'):
                st.caption(model['description'])
                st.caption('Required products: '+', '.join(model['required_products']))
                st.caption(model['status_reason'])
        st.button('View illustrative results', on_click=_show_scenario, width='stretch', key='semantic_view_results')
    with st.expander('Semantic definitions, products and relationship evidence'):
        st.write(service.metadata['ontology_status'])
        st.caption(service.metadata['coordinate_note']+' '+service.metadata['relation_note'])
        st.dataframe(pd.DataFrame(relations), hide_index=True, width='stretch')
        st.download_button('Download this demo context', json.dumps({'entity_id':selected,'type_uri':entity['type_uri'],
            'start':str(start),'end':str(end),'mode':mode,'scenario_id':scenario if mode=='Scenario results' else None,
            'relationship_filter':relation_arg,'relations':relations,'ontology_status':service.metadata['ontology_status'],
            'evidence_role':'illustrative'},indent=2), 'CRDT_semantic_demo_context.json','application/json')
