"""Selected-source relationships and separate spatial candidates."""
import json

import streamlit as st

from data_relations import build_data_relations, nearby_candidates


def _relation_dot(graph):
    quote=lambda value:json.dumps(str(value),ensure_ascii=False)
    lines=['digraph connections {',
        'graph [rankdir=TB,bgcolor="transparent",pad="0.25",nodesep="0.3",ranksep="0.45"];',
        'node [shape=box,style="rounded,filled",fontname="Arial",fontsize=12,fontcolor="#EDF0F7",fillcolor="#151D2B",color="#64728A",margin="0.18,0.12"];',
        'edge [fontname="Arial",fontsize=10,fontcolor="#A8B2C5",color="#8790C8",arrowsize=0.7];']
    for node in graph['nodes']:
        color='#9A94FF' if node['kind']=='Object' else '#64728A'
        label=node['label']+'\n'+node['evidence']
        detail=node['kind']+' · '+node['evidence']
        lines.append(f'{quote(node["id"])} [label={quote(label)},tooltip={quote(detail)},color="{color}"];')
    labels={'returnsRecords':'provides records','recordsInSeries':'records in series','recordedFor':'recorded for'}
    for edge in graph['edges']:
        pending='unverified' in edge['evidence'].lower()
        style='dashed' if pending else 'solid'
        color='#D6AD70' if pending else '#8790C8'
        label=labels.get(edge['relation'],edge['relation'])
        lines.append(f'{quote(edge["source"])} -> {quote(edge["target"])} [label={quote(label)},style="{style}",color="{color}"];')
    return '\n'.join(lines+['}'])


def _inspect_nearby(entity_id):
    st.session_state.pop('monitor_handoff',None)
    st.session_state['workbench_entity_id']=entity_id
    st.session_state['workbench_last_map_id']=None
    st.session_state['workbench_map_revision']=st.session_state.get('workbench_map_revision',0)+1


def render_data_relations(bundle,context,entities):
    st.markdown('**Data connections**')
    if context is None:
        st.info('Select a monitoring object to inspect its source and records.')
        return
    graph=build_data_relations(bundle,context)
    metadata=graph['metadata']
    count=metadata['actual_record_count']
    with st.container(border=True,key='connected_data_graph'):
        st.caption('SOURCE → RETURNED RECORDS → MEASUREMENT SERIES → OBJECT')
        cards=st.columns(3,gap='small')
        cards[0].metric('Source products',sum(n['kind']=='Source' for n in graph['nodes']))
        cards[1].metric('Measurement series',sum(n['kind']=='Series' for n in graph['nodes']))
        cards[2].metric('Returned records',count)
        st.caption(metadata['time_basis']+' · Selected dates: '+context['start']+' to '+context['end'])
        if count:
            st.graphviz_chart(_relation_dot(graph),width='stretch',height=440)
        else:
            st.info('No returned records for this object and measurement reference in the selected period.')
        if context['source']=='webtris':
            st.info('Mapping unverified · Traffic report rows are linked to counters through description matching. Confirm the identity before model use.')
        st.caption('Source references are retained. Series and record-set IDs are provisional workspace identifiers.')
        for gap in graph['gaps']:
            if not gap.startswith(('Mapping unverified:','Source timezone unverified;')):
                st.caption(gap)
        with st.expander('Connection evidence and source fields'):
            st.json(graph)
        st.download_button('Download connection evidence',json.dumps(graph,ensure_ascii=False,indent=2,default=str).encode(),
                           'CRDT_data_connections.json','application/json',key='connection_evidence_download')
    with st.expander('Nearby objects · spatial candidates'):
        st.caption('Within 5 km by great-circle distance between supplied coordinates. Proximity does not establish road connectivity or a service dependency.')
        nearby=nearby_candidates(entities,context['entity_id'])
        if nearby.empty:
            st.caption('No other mapped source objects meet this rule in the enabled layers.')
        else:
            st.dataframe(nearby,hide_index=True,width='stretch')
            labels=nearby.set_index('Object ID')['Object'].to_dict()
            if st.session_state.get('connection_nearby') not in labels:
                st.session_state['connection_nearby']=next(iter(labels))
            target=st.selectbox('Nearby object',list(labels),format_func=labels.get,key='connection_nearby')
            st.button('Inspect nearby object',on_click=_inspect_nearby,args=(target,),key='connection_inspect_nearby')
