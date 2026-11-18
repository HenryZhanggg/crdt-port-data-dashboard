"""One source catalogue, quality workspace and partner intake."""
import importlib
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from data_quality import compatibility, observation_graph, quality_table, validate_observations
from project_archives import render_archives
from workbench_views import _import_package
from workspace_data import quality_findings, report_archive
from workspace_links import clear_context, context_allowed, context_label, filter_context_bundle
from validation_views import load_validation_report, validation_register, render_validation_summary, render_source_validation, render_provider_notice
import integration_views

DATA_WORKSPACE_BUILD='2026-11-18.1'


def _open_data_tool(tool):
    st.session_state['data_workspace_tab']=tool


SOURCE_PRODUCTS={
    'HS001':{'sources':('dft',),'tables':{'port_traffic':'Port freight','ship_arrivals':'Ship arrivals'}},
    'HS004':{'sources':('water_level','ea'),'tables':{'water_levels':'Liverpool water levels',
        'ea_stations':'Monitoring stations','ea_readings':'Latest station readings','ea_floods':'Flood warnings'}},
    'HS007':{'sources':('webtris',),'tables':{'webtris_daily':'Road traffic observations','webtris_sites':'Traffic reference locations'}},
    'HS009':{'sources':('naptan',),'tables':{'naptan':'Public transport access nodes'}},
    'HS014':{'sources':('ons',),'tables':{'weekly_shipping':'Weekly Liverpool shipping'}},
}


def _dates(prefix):
    today=pd.Timestamp.now(tz='UTC').date()
    mode=st.radio('Data period',['Recent observations','Historical browsing'],horizontal=True,key=prefix+'_mode',
        on_change=clear_context,args=('data_handoff',))
    first=(pd.Timestamp(today)-pd.Timedelta(days=1 if mode=='Recent observations' else 6)).date()
    dates=st.date_input('Data dates',value=(first,today),max_value=today,
        disabled=mode=='Recent observations',key=prefix+'_dates_'+mode,
        on_change=clear_context,args=('data_handoff',))
    if len(dates)!=2 or dates[0]>dates[1] or (dates[1]-dates[0]).days>6:
        st.info('Choose both dates within a period of up to seven calendar days.')
        return None
    st.caption('Water dates use UTC; traffic retains its source timezone, which has not been verified.')
    return tuple(value.isoformat() for value in dates)


def _source_link(url):
    try:
        parsed=urlparse(str(url))
        safe=parsed.scheme=='https' and parsed.hostname and parsed.port in (None,443) and not parsed.username and not parsed.password
    except ValueError:
        safe=False
    if safe:
        st.link_button('Open original source',url)


def _catalogue(catalog,load_bundle,views):
    report=load_validation_report()
    render_validation_summary(catalog,report,SOURCE_PRODUCTS)
    handoff=st.session_state.get('data_handoff')
    if handoff and handoff['source_id'] not in set(catalog['source_id']):
        st.info('The requested data source is not available in this catalogue. Clear the observation context to choose another source.')
        return
    query=st.text_input('Find a source',key='data_source_search',
        on_change=clear_context,args=('data_handoff',)).strip().casefold()
    fields=['source_id','title','domain','access_level','connection_mode']
    frame=catalog.loc[catalog[fields].astype(str).agg(' '.join,axis=1).str.casefold().str.contains(query,regex=False)].copy()
    register=validation_register(frame,report,SOURCE_PRODUCTS)
    roles=['All data roles',*sorted(register['Data role'].unique())]
    if handoff:
        st.session_state['data_role_filter']='All data roles'
        st.session_state['data_route_filter']='All routes'
    if st.session_state.get('data_role_filter') not in roles:
        st.session_state['data_role_filter']='All data roles'
    left,right=st.columns(2)
    role=left.selectbox('Data role',roles,key='data_role_filter',on_change=clear_context,args=('data_handoff',))
    route=right.selectbox('Dashboard route',['All routes','Connector available','Reference / access pending'],
        key='data_route_filter',on_change=clear_context,args=('data_handoff',))
    if role!='All data roles':
        register=register.loc[register['Data role'].eq(role)]
    if route!='All routes':
        register=register.loc[register['Dashboard route'].eq(route)]
    frame=frame.loc[frame['source_id'].isin(register['ID'])]
    if frame.empty:
        st.info('No sources match this search.')
        return
    st.dataframe(register,hide_index=True,width='stretch',height=300)
    st.download_button('Download filtered source register',register.to_csv(index=False).encode(),
        'CRDT_source_validation_register.csv','text/csv')
    labels=frame.set_index('source_id')['title'].to_dict()
    if st.session_state.get('data_source_id') not in labels:
        st.session_state['data_source_id']=None
    selected=st.selectbox('Data source',list(labels),format_func=labels.get,index=None,
        placeholder='Choose a source to inspect',key='data_source_id',on_change=clear_context,args=('data_handoff',))
    if selected is None:
        st.caption('Select a source for access conditions, available records and downloads. The catalogue itself does not request feeds.')
        return
    row=frame[frame['source_id'].eq(selected)].iloc[0]
    st.markdown('**'+str(row['title'])+'**')
    st.caption(str(row.get('brief_description','')))
    st.caption('Access: '+str(row.get('access_level',''))+' · '+str(row.get('cost','')))
    st.caption('Format: '+str(row.get('format',''))+' · Catalogue coverage: '+str(row.get('period','')))
    _source_link(row.get('url',''))
    render_provider_notice(selected)
    render_source_validation(report,selected)
    with st.expander('Catalogue metadata'):
        st.caption('Original source assessment, suggested use and access notes; catalogue entries do not establish current availability.')
        st.json(row.to_json())
    product=SOURCE_PRODUCTS.get(selected)
    if product is None:
        st.caption('Reference or access pending: '+str(row.get('connection_mode',''))+'. '+str(row.get('highlighted_comment','')))
        return
    if 'raw_data' not in views:
        st.caption('This prototype partner view includes the catalogue only.')
        return
    if selected=='HS004' and 'weather' not in views:
        st.caption('Water observations are outside this prototype partner view.')
        return
    if selected=='HS007' and 'transport' not in views:
        st.caption('Road traffic is outside this prototype partner view.')
        return
    if selected=='HS007':
        st.caption('Traffic counts are historical; [WebTRIS is usually published about one month after collection](https://webtris.highwaysengland.co.uk/Home/Faqs).')
    if not st.checkbox('Browse connected records',key='data_browse_'+selected,
        on_change=clear_context,args=('data_handoff',)):
        return
    dates=_dates('data_preview') if selected in {'HS004','HS007'} else (None,None)
    if dates is None:
        return
    with st.spinner('Retrieving the selected source'):
        bundle=load_bundle(*dates,(handoff['source'],) if handoff else product['sources'])
    if handoff:
        bundle=filter_context_bundle(bundle,handoff)
    status=bundle.get('status',pd.DataFrame())
    if not status.empty:
        st.dataframe(status.reindex(columns=['source','status','records','last_call_utc','access_note']),hide_index=True,width='stretch')
    table_key=st.selectbox('Dataset',list(product['tables']),format_func=product['tables'].get,key='data_table_'+selected,
        on_change=clear_context,args=('data_handoff',))
    records=bundle.get(table_key,pd.DataFrame())
    if records.empty:
        st.info('The requested measurement reference has no returned observations in this period. Clear the observation context to choose another reference.'
            if handoff else 'No records returned for this dataset. See the source status and coverage above.')
    else:
        st.caption(f'{len(records):,} returned records · preview shows up to 200 rows; download contains the full returned table.')
        st.dataframe(records.head(200),hide_index=True,width='stretch')
        st.download_button('Download dataset CSV',records.to_csv(index=False).encode(),table_key+'.csv','text/csv')
    if selected=='HS004':
        st.caption('Water values retain station, unit, vertical datum and source timestamps. No datum conversion is applied.')
    elif selected=='HS007':
        st.caption('Traffic counts and speeds describe road counters, not port-gate queues. Source timezone remains unverified.')


def _validation(water):
    if water.empty:
        st.caption('Detailed water validation needs observations and measurement metadata.')
        return
    with st.expander('Measurement compatibility and ontology checks'):
        references=water.groupby(['station_reference','unit','datum_uri'],dropna=False).last().reset_index()
        pairs=[]
        for i in range(len(references)):
            for j in range(i+1,len(references)):
                a,b=references.iloc[i].to_dict(),references.iloc[j].to_dict()
                allowed,reason=compatibility(a,b)
                pairs.append({'Reference A':str(a['station_reference'])+' | '+str(a['unit'])+' | '+str(a['datum_uri']),
                    'Reference B':str(b['station_reference'])+' | '+str(b['unit'])+' | '+str(b['datum_uri']),
                    'Direct comparison':'Metadata compatible' if allowed else 'Blocked','Reason':reason})
        if pairs:
            st.dataframe(pd.DataFrame(pairs),hide_index=True,width='stretch')
        graph=observation_graph(water)
        conforms,issues=validate_observations(graph)
        st.caption('Configured SHACL structure checks: '+('passed' if conforms else 'violations found')+'. This does not establish measurement accuracy or approved WP1 alignment.')
        if not conforms:
            st.dataframe(issues,hide_index=True,width='stretch')
        st.download_button('Download observation graph (Turtle)',graph.serialize(format='turtle'),'port_observations.ttl','text/turtle')


def _quality(load_bundle,views,refresh):
    handoff=st.session_state.get('data_handoff')
    choices={}
    if 'weather' in views:
        choices['Water levels']=('water_level',)
    if 'transport' in views:
        choices['Road traffic']=('webtris',)
    if len(choices)==2:
        choices={'Water and traffic':('water_level','webtris'),**choices}
    if not choices:
        st.caption('No observation streams are available in this prototype partner view.')
        return
    if st.session_state.get('data_quality_scope') not in choices:
        st.session_state.pop('data_quality_scope',None)
    scope=st.selectbox('Check data',list(choices),key='data_quality_scope',on_change=clear_context,args=('data_handoff',))
    if 'webtris' in choices[scope]:
        render_provider_notice('HS007')
    dates=_dates('data_quality')
    if dates is None:
        return
    if refresh and st.button('Refresh checked sources',key='data_quality_refresh'):
        refresh(choices[scope],*dates)
    with st.spinner('Checking observation sources'):
        bundle=load_bundle(*dates,choices[scope])
    if handoff:
        bundle=filter_context_bundle(bundle,handoff)
        table_key='water_levels' if handoff['source']=='water_level' else 'webtris_daily'
        if bundle[table_key].empty:
            st.info('The requested measurement reference has no returned observations in this period. Clear the observation context to choose another reference.')
            status=bundle.get('status',pd.DataFrame())
            if not status.empty:
                st.dataframe(status,hide_index=True,width='stretch')
            return
    table=quality_table(bundle,pd.DataFrame(),pd.DataFrame(),requested_sources=choices[scope])
    findings=quality_findings(table)
    if findings.empty:
        st.caption('No configured findings in the returned streams. Coverage is limited to the records supplied by each source.')
    else:
        st.dataframe(findings,hide_index=True,width='stretch')
    with st.expander('Full quality and source register'):
        st.dataframe(table,hide_index=True,width='stretch')
        st.dataframe(bundle.get('status',pd.DataFrame()),hide_index=True,width='stretch')
    st.caption('Quality states describe data usability. Missing, stale, invalid and unverified timestamps remain distinct.')
    left,right=st.columns(2)
    left.download_button('Download quality CSV',table.to_csv(index=False).encode(),'CRDT_quality.csv','text/csv')
    right.download_button('Export observation report',report_archive(bundle,table,*dates),'CRDT_observation_report.zip','application/zip')
    _validation(bundle.get('water_levels',pd.DataFrame()))


def render_data_workspace(catalog,load_bundle,views,refresh=None):
    st.subheader('Data & Integration')
    st.caption('Data workspace build: '+DATA_WORKSPACE_BUILD)
    handoff=st.session_state.get('data_handoff')
    if handoff:
        st.caption('Observation context: '+context_label(handoff))
        st.button('Clear observation context',key='data_clear_context',on_click=clear_context,args=('data_handoff',))
        if not context_allowed(handoff,views):
            st.info('The requested observation source is outside this partner view. Clear the observation context to browse the permitted catalogue.')
            return
    st.caption('Inspect source evidence, build a traceable data input, check quality, or import a partner product.')
    with st.container(key='data_actions'):
        left,right=st.columns(2)
        left.button('Open integration workbench',type='secondary' if st.session_state.get('data_workspace_tab','Integration')=='Integration' else 'primary',width='stretch',
            key='data_open_integration',on_click=_open_data_tool,args=('Integration',))
        right.button('View source validation',width='stretch',key='data_open_sources',
            on_click=_open_data_tool,args=('Sources',))
    legacy_partner=st.session_state.get('data_workspace_tab')=='Partner packages'
    if legacy_partner or st.session_state.get('data_workspace_tab') not in {'Integration','Sources','Quality'}:
        st.session_state['data_workspace_tab']='Integration'
    integration,sources,quality=st.tabs(['Integration','Sources','Quality'],key='data_workspace_tab',on_change='rerun')
    if sources.open:
        with sources:
            _catalogue(catalog,load_bundle,views)
    if integration.open:
        with integration:
            if getattr(integration_views,'INTEGRATION_WORKSPACE_BUILD',None)!=DATA_WORKSPACE_BUILD:
                importlib.reload(integration_views)
            if getattr(integration_views,'INTEGRATION_WORKSPACE_BUILD',None)!=DATA_WORKSPACE_BUILD:
                st.error('The integration workspace update has not loaded completely. Please reopen after deployment finishes.')
            else:
                integration_views.render_integration_workspace(load_bundle,views,refresh=refresh,handoff=handoff)
    if quality.open:
        with quality:
            _quality(load_bundle,views,refresh)
    if integration.open:
        with integration, st.expander('Partner products and dependencies',expanded=legacy_partner):
            if legacy_partner:
                st.session_state['data_show_partner_intake']=True
            show_partner=st.checkbox('Import or inspect a partner product',key='data_show_partner_intake')
            if show_partner:
                st.caption('Add published model results or declared dependency data. Imports stay in this session; no uploaded model or URL is executed.')
                _import_package('data')
                runs=st.session_state.get('partner_runs',{})
                if runs:
                    st.caption(str(len(runs))+' result packages available in Monitor → Results.')
                if st.session_state.get('dependency_package'):
                    st.caption('A dependency package is available in Monitor → Connections; source identity alignment still needs review.')
    render_archives()
