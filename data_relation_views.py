"""Selected-source relationships and separate spatial candidates."""
import hashlib
import json
from html import escape

import plotly.graph_objects as go

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


def _reset_connection_pick(identity):
    key='connection_graph_revision_'+identity
    st.session_state[key]=st.session_state.get(key,0)+1
    st.session_state.pop('connection_last_pick',None)


def _inspect_connection_graph(graph,context):
    layers={'Source':3,'Records':2,'Series':1,'Object':0}
    positions={}
    for kind,level in layers.items():
        nodes=[node for node in graph['nodes'] if node['kind']==kind]
        for index,node in enumerate(nodes):
            positions[node['id']]=(index-(len(nodes)-1)/2,level)
    figure=go.Figure()
    middle_x,middle_y,edge_data,edge_hover=[],[],[],[]
    for index,edge in enumerate(graph['edges']):
        first,last=positions[edge['source']],positions[edge['target']]
        pending='unverified' in edge['evidence'].lower()
        color='#D6AD70' if pending else '#8790C8'
        figure.add_trace(go.Scatter(x=[first[0],last[0]],y=[first[1],last[1]],mode='lines',
            line={'color':color,'width':1.5,'dash':'dash' if pending else 'solid'},hoverinfo='skip'))
        figure.add_annotation(x=last[0],y=last[1]+.12,ax=first[0],ay=first[1]-.12,
            xref='x',yref='y',axref='x',ayref='y',showarrow=True,arrowhead=2,arrowsize=.8,
            arrowwidth=1.2,arrowcolor=color,text='')
        middle_x.append((first[0]+last[0])/2);middle_y.append((first[1]+last[1])/2)
        edge_data.append(['edge',str(index)])
        edge_hover.append(escape(edge['relation']+' · '+edge['evidence']))
    figure.add_trace(go.Scatter(x=middle_x,y=middle_y,mode='markers',customdata=edge_data,
        marker={'size':11,'symbol':'diamond','color':'#8790C8'},unselected={'marker':{'opacity':.8}},hovertext=edge_hover,
        hovertemplate='%{hovertext}<extra>Relationship</extra>'))
    nodes=graph['nodes']
    figure.add_trace(go.Scatter(x=[positions[n['id']][0] for n in nodes],y=[positions[n['id']][1] for n in nodes],
        mode='markers+text',customdata=[['node',n['id']] for n in nodes],
        textfont={'color':'#CBD3E4'},unselected={'marker':{'opacity':.8},'textfont':{'color':'#A8B2C5'}},
        marker={'size':22,'color':['#9A94FF' if n['kind']=='Object' else '#667AA2' for n in nodes]},
        text=[escape(n['label'][:120]) for n in nodes],textposition='middle right',
        hovertext=[escape(n['kind']+' · '+n['evidence']) for n in nodes],
        hovertemplate='%{hovertext}<extra>Node</extra>'))
    figure.update_layout(height=440,showlegend=False,paper_bgcolor='#111722',plot_bgcolor='#111722',
        font={'color':'#EDF0F7','size':12},margin={'l':30,'r':130,'t':25,'b':25},
        xaxis={'visible':False},yaxis={'visible':False,'range':[-.4,3.4]},clickmode='event+select',dragmode=False)
    identity=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()[:12]
    event=st.plotly_chart(figure,width='stretch',key='connection_graph_'+identity+'_'+str(st.session_state.get('connection_graph_revision_'+identity,0)),
        on_select='rerun',selection_mode='points',config={'displayModeBar':False})
    labels={'node:'+n['id']:n['kind']+' · '+n['label'] for n in nodes}
    labels.update({'edge:'+str(i):'Relationship · '+edge['relation'] for i,edge in enumerate(graph['edges'])})
    key='connection_element_'+identity
    points=event.get('selection',{}).get('points',[]) if event else []
    if points:
        choice=points[-1].get('customdata',[])
        if isinstance(choice,(list,tuple)) and len(choice)==2:
            selected=str(choice[0])+':'+str(choice[1])
            signature=(identity,selected)
            if selected in labels and st.session_state.get('connection_last_pick')!=signature:
                st.session_state[key]=selected
                st.session_state['connection_last_pick']=signature
    if st.session_state.get(key) not in labels:
        preferred='node:'+context['entity_id']
        st.session_state[key]=preferred if preferred in labels else next(iter(labels))
    choice=st.selectbox('Inspect node or relationship',list(labels),format_func=labels.get,key=key,on_change=_reset_connection_pick,args=(identity,))
    if choice.startswith('edge:'):
        selected=graph['edges'][int(choice.split(':',1)[1])]
        st.caption('Relationship: '+selected['relation']+' · '+selected['evidence'])
        st.text(selected['source']+' → '+selected['target'])
    else:
        selected=next(node for node in nodes if 'node:'+node['id']==choice)
        st.caption(selected['kind']+' · '+selected['evidence'])
        st.text(selected['label'])
    with st.expander('Selected node or relationship fields'):
        st.json(selected)
    st.caption('Click a node or a diamond on an arrow to inspect its evidence, or use the selector above.')


def _inspect_nearby(entity_id):
    st.session_state.pop('monitor_handoff',None)
    st.session_state['workbench_entity_id']=entity_id
    st.session_state['workbench_last_map_id']=None
    st.session_state['workbench_map_revision']=st.session_state.get('workbench_map_revision',0)+1


def render_data_relations(bundle,context,entities):
    st.markdown('**Data connections**')
    st.caption('Shared objects link source records. Operational dependencies need domain evidence; executable model chains additionally need accepted input/output contracts. These are distinct relationship types.')
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
            _inspect_connection_graph(graph,context)
        else:
            st.info('No returned records for this object and measurement reference in the selected period.')
        if context['source']=='webtris':
            st.info('Mapping unverified · Traffic report rows are linked to counters through description matching. Confirm the identity before model use.')
        st.caption('Source references are retained. Series and record-set IDs are provisional workspace identifiers.')
        for gap in graph['gaps']:
            if not gap.startswith(('Mapping unverified:','Source timezone unverified;')):
                st.caption(gap)
        with st.expander('Technical details · connection evidence and source fields'):
            st.json(graph)
            st.download_button('Download graph DOT',_relation_dot(graph).encode(),
                'CRDT_data_connections.dot','text/vnd.graphviz',key='connection_dot_download')
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
