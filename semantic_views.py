"""Geographic Monitor; illustrative assets and source observations stay separate."""
from datetime import date
from html import escape
import json
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from monitoring_views import chart_style
from network_map import network_deck
from semantic_service import SemanticDemo
from workspace_data import water_chart_series


def _choose_object(entity_id, type_uri, name=''):
    st.session_state['semantic_entity_id'] = entity_id
    if st.session_state.get('semantic_type', 'All') not in ('All', type_uri):
        st.session_state['semantic_type'] = 'All'
    query = st.session_state.get('semantic_search', '').strip().casefold()
    if query and query not in (entity_id+' '+name).casefold():
        st.session_state['semantic_search'] = ''
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


def _spatial_view(entities, relations, selected, graph, revision, visible_ids=None):
    if graph:
        positions = {row['entity_id']: (math.cos(2*math.pi*i/len(entities)), math.sin(2*math.pi*i/len(entities)))
                     for i, row in enumerate(entities)}
        fig = go.Figure()
        for relation in relations:
            a, b = positions[relation['source_id']], positions[relation['target_id']]
            active = selected in (relation['source_id'], relation['target_id'])
            fig.add_trace(go.Scatter(x=[a[0], b[0]], y=[a[1], b[1]], mode='lines',
                line={'color':'#7C83FD' if active else '#5F6E84','width':2.4 if active else 1},
                hoverinfo='skip', showlegend=False))
            fig.add_annotation(x=(a[0]+b[0])/2, y=(a[1]+b[1])/2, text=escape(relation['relation_label']),
                showarrow=False, bgcolor='#111722', borderpad=2,
                font={'size':11,'color':'#F2F5F9' if active else '#95A2B5'})
            fig.add_annotation(x=a[0]+.72*(b[0]-a[0]), y=a[1]+.72*(b[1]-a[1]),
                    ax=a[0]+.55*(b[0]-a[0]), ay=a[1]+.55*(b[1]-a[1]),
                    xref='x', yref='y', axref='x', ayref='y', text='', showarrow=True,
                    arrowhead=2, arrowcolor='#7C83FD' if active else '#5F6E84', arrowsize=1)
        fig.add_trace(go.Scatter(x=[positions[row['entity_id']][0] for row in entities],
            y=[positions[row['entity_id']][1] for row in entities], mode='markers+text',
            text=[row['type_label'] for row in entities], hovertext=[row['name'] for row in entities],
            textposition=['middle left' if positions[row['entity_id']][0]>.7 else
                          'middle right' if positions[row['entity_id']][0]<-.7 else 'top center' for row in entities],
            customdata=[[row['entity_id']] for row in entities],
            marker={'size':[24 if row['entity_id']==selected else 17 for row in entities],
                    'color':['#7C83FD' if row['entity_id']==selected else '#95A2B5' for row in entities],
                    'line':{'color':'#F2F5F9','width':1}},
            hovertemplate='%{hovertext}<br>%{customdata[0]}<extra>Illustrative object</extra>', showlegend=False))
        fig.update_xaxes(visible=False, range=[-1.5,1.5]); fig.update_yaxes(visible=False, range=[-1.4,1.5])
        fig = chart_style(fig, 420).update_layout(hovermode='closest', paper_bgcolor='#111722',
            plot_bgcolor='#111722', font={'color':'#F2F5F9','size':12})
        event = st.plotly_chart(fig, width='stretch', key=f'semantic_graph_{revision}',
                               on_select='rerun', selection_mode='points')
        return _selected_id(event, graph=True)
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


def _change_observed():
    st.session_state['semantic_observed_revision'] = st.session_state.get('semantic_observed_revision', 0)+1


def _render_available_observations(snapshot):
    from daily_views import _link, _number, _place_label, _plain, _source, _water_frame, _when

    tide = snapshot['tide']
    series = tide.get('series', []) if tide.get('status')=='available' else []
    query = st.text_input('Search observations', key='semantic_observed_search', on_change=_change_observed).strip().casefold()
    lookup = {row['id']:row for row in series if query in (row['id']+' '+row['name']).casefold()}
    pending = st.session_state.pop('semantic_observed_pending', None)
    if pending in lookup:
        st.session_state['semantic_observed_id'] = pending
        _change_observed()
    if not lookup:
        st.info('No observations match this search.' if series else
                _plain(tide.get('message')) or 'Water observations are not available.')
        _source(tide)
        _link('Open water data source', tide.get('source_url'))
        return
    if st.session_state.get('semantic_observed_id') not in lookup:
        st.session_state['semantic_observed_id'] = next(iter(lookup))
    selected_id = st.selectbox('Water reference', list(lookup),
        format_func=lambda value:_place_label(lookup[value]), key='semantic_observed_id', on_change=_change_observed)
    selected = lookup[selected_id]
    points = []
    for entry in lookup.values():
        lat, lon = entry.get('lat'), entry.get('lon')
        if lat is None or lon is None or not math.isfinite(float(lat)) or not math.isfinite(float(lon)) or abs(float(lat))>90 or abs(float(lon))>180:
            continue
        points.append({'entity_id':entry['id'], 'name':escape(_plain(entry['name'])),
            'type_uri':'source:WaterLevelReference', 'lat':lat, 'lon':lon})
    map_area, inspector = st.columns([2.4,1], gap='small')
    with map_area, st.container(border=True, key='semantic_observed_map'):
        if points:
            deck = network_deck(points, [], selected_id, evidence='Source water reference')
            event = st.pydeck_chart(deck, height=420, width='stretch', on_select='rerun', selection_mode='single-object',
                key=f"semantic_observed_map_{st.session_state.get('semantic_observed_revision',0)}")
            picked = _selected_id(event)
            if picked in lookup and picked!=selected_id:
                st.session_state['semantic_observed_pending'] = picked
                st.rerun()
        else:
            st.info('No source coordinates are available for these observations.')
        st.caption('Source gauge coordinates only. No asset dependency links or bindings to the example network are asserted.')
    now = pd.Timestamp.now(tz='UTC')
    frame = _water_frame(selected, now)
    measured = frame.dropna(subset=['value'])
    latest = measured.iloc[-1] if not measured.empty else None
    with inspector, st.container(border=True, key='semantic_observed_inspector'):
        st.markdown('**'+_plain(selected['name'])+'**')
        st.caption('Source ID: '+selected_id)
        st.metric('Latest observation', _number(latest['value'],2)+' '+_plain(selected.get('unit','')) if latest is not None else 'Not available')
        st.caption('Observed '+_when(latest['date_time']) if latest is not None else 'No current reading returned')
        st.caption('Reference: '+_plain(selected.get('datum','Unknown reference')))
        _source(tide)
    readings, connections, sources = st.tabs(['Readings','Connections','Sources'])
    with readings:
        if measured.empty:
            st.info('No current readings were returned. Missing values are not replaced with zero.')
        else:
            chart = water_chart_series(frame)
            fig = go.Figure(go.Scatter(x=chart.index, y=chart.values, mode='lines+markers',
                connectgaps=False, line={'color':'#7C83FD','width':2}))
            fig.update_layout(xaxis_title='Observed time (UTC)', yaxis_title=_place_label(selected))
            st.plotly_chart(chart_style(fig,250), width='stretch', key='semantic_observed_readings')
            st.dataframe(frame, hide_index=True, width='stretch')
    with connections:
        st.caption('No asset dependency links have been supplied for these source observations.')
    with sources:
        _source(tide)
        _link('Open reference source', selected.get('source_url') or tide.get('source_url'))
        st.json({key:value for key,value in selected.items() if key!='rows'})


def render_semantic_demo(snapshot=None):
    with st.container(key='semantic_heading'):
        st.subheader('CRDT port dashboard version 1')
    network_mode = st.radio('Network data', ['Example network','Available observations'],
        horizontal=True, key='semantic_network_mode', on_change=_change_type)
    if network_mode=='Available observations':
        if snapshot is None:
            from daily_service import load_daily_snapshot
            snapshot = load_daily_snapshot()
        _render_available_observations(snapshot)
        return
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
        controls = st.columns([1,1.25], gap='small')
        view = controls[0].radio('Spatial view', ['Map','Relations'], key='semantic_spatial_view', horizontal=True,
                                 on_change=_change_type)
        relation_labels = {'All':'All declared relationships', **{r['uri']:r['label'] for r in service.relation_types()}}
        relation_type = controls[1].selectbox('Relationship',list(relation_labels),format_func=relation_labels.get,
                                            key='semantic_relation', on_change=_change_type)
        relation_arg = None if relation_type=='All' else relation_type
        relations = service.relations(relation_type=relation_arg, start=start, end=end)
        picked = _spatial_view(entities, relations, selected, view=='Relations', st.session_state.get('semantic_revision',0),
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
            areas = st.tabs([t['label'] for t in tabs]+['Connections','Sources'])
            for tab, area in zip(tabs, areas):
                with area:
                    products = service.products(selected, tab['id'], start, end,
                                                 scenario_id=scenario if mode=='Scenario results' else None)
                    for product in products:
                        _product_panel(product)
                    if not products:
                        st.info('No sample product matches this object, view and period.')
            with areas[-2]:
                for edge in related:
                    provider = next(source for source in service.sources if source['source_id']==edge['evidence_ref'])
                    st.markdown('**'+edge['relation_label']+'**')
                    st.caption(edge['source_id']+' → '+edge['target_id']+' · '+edge['direction']+' relative to selected asset')
                    st.caption('Evidence: '+edge['evidence_role']+' · '+edge['evidence_ref'])
                    st.caption('Provider: '+provider['name']+' · local illustrative package')
                    st.caption('Valid '+edge['valid_from']+' to '+edge['valid_to'])
                if not related:
                    st.info('No declared connections match the selected asset, relationship and period.')
            with areas[-1]:
                st.caption(service.metadata['ontology_status'])
                st.caption(entity['coordinate_note'])
                st.dataframe(pd.DataFrame(service.sources), hide_index=True, width='stretch')
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
