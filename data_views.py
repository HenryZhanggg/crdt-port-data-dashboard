"""One source catalogue, quality workspace and partner intake."""
import importlib
import json
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

import daily_service
from data_quality import compatibility, observation_graph, quality_table, validate_observations
from dataset_preview import render_table_preview, returned_period
from project_archives import render_archives
from workbench_views import _import_package
from workspace_data import quality_findings, report_archive
from workspace_links import clear_context, context_allowed, context_label, filter_context_bundle
from validation_views import load_validation_report, validation_register, render_validation_summary, render_source_validation, render_provider_notice
import integration_views

DATA_WORKSPACE_BUILD='2026-11-25.1'
DATA_DIR=Path(__file__).parent/'data'


def _open_data_tool(tool):
    st.session_state['data_workspace_tab']=tool


def _preview_liverpool_archive():
    st.session_state['data_source_id']='HS004'
    st.session_state['data_browse_HS004']=True
    st.session_state['data_table_HS004']='ea_liverpool_archive'


def _use_source_in_integration(source,dates,context):
    _open_data_tool('Integration')
    st.session_state['integration_input_kind']='Connected sources'
    st.session_state['integration_sources']=[source]
    if context:
        st.session_state['data_handoff']=context
    else:
        clear_context('data_handoff')
        date_key='integration_dates_traffic' if source=='webtris' else 'integration_dates'
        if dates:
            st.session_state[date_key]=tuple(pd.Timestamp(day).date() for day in dates)
        else:
            st.session_state.pop(date_key,None)


SOURCE_PRODUCTS={
    'HS001':{'sources':('dft',),'tables':{'port_traffic':'Port freight','ship_arrivals':'Ship arrivals'}},
    'HS004':{'sources':('water_level','ea'),'integration':('water_level','water_levels'),'tables':{'water_levels':'Liverpool water levels',
        'ea_stations':'Monitoring stations','ea_readings':'Latest station readings','ea_floods':'Flood warnings',
        'ea_liverpool_archive':'Liverpool water levels · historical archive'}},
    'HS007':{'sources':('webtris',),'integration':('webtris','webtris_daily'),
        'tables':{'webtris_daily':'Road traffic observations','webtris_sites':'Traffic reference locations'}},
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


def _source_dataset(row, load_bundle, views, handoff, timing):
    selected=row['source_id']
    product=SOURCE_PRODUCTS.get(selected)
    unavailable=''
    if product is None:
        unavailable=('Provider access only · '+str(row.get('connection_mode',''))
                     if row.get('url') else 'No verified data access route recorded.')
    elif 'raw_data' not in views:
        unavailable='This prototype partner view includes the catalogue only.'
    elif selected=='HS004' and 'weather' not in views:
        unavailable='Water observations are outside this prototype partner view.'
    elif selected=='HS007' and 'transport' not in views:
        unavailable='Road traffic is outside this prototype partner view.'

    browsing=False
    table_key=None
    dates=(None,None)
    bundle={}
    archive_csv=None
    if not unavailable:
        browsing=st.checkbox('Browse connected records',key='data_browse_'+selected,
            on_change=clear_context,args=('data_handoff',))
        if browsing:
            table_key=st.selectbox('Dataset',list(product['tables']),format_func=product['tables'].get,
                key='data_table_'+selected,on_change=clear_context,args=('data_handoff',))
            if table_key=='ea_liverpool_archive':
                path=DATA_DIR/'ea_liverpool_archive.csv'
                if path.is_file():
                    bundle[table_key]=pd.read_csv(path,dtype=str,keep_default_na=False)
                    archive_csv=path.read_bytes()
            elif table_key=='ea_floods':
                warnings=daily_service.load_flood_warnings()
                items=warnings['items']
                if items:
                    bundle[table_key]=pd.DataFrame(items).rename(columns={'published_at':'reviewed_at'}).assign(
                        retrieved_at_utc=warnings['checked_at'],source_url=warnings['source_url'])
                bundle['status']=pd.DataFrame([{'source':warnings['source_name'],
                    'status':'No warnings returned' if warnings['status']=='available' and not items else warnings['status'],
                    'records':len(items),'last_call_utc':warnings['checked_at'],'access_note':warnings['message']}])
            else:
                if product.get('integration'):
                    dates=_dates('data_preview')
                if dates is not None:
                    with st.spinner('Retrieving the selected source'):
                        bundle=load_bundle(*dates,(handoff['source'],) if handoff else product['sources'])
                    if handoff:
                        bundle=filter_context_bundle(bundle,handoff)

    records=bundle.get(table_key,pd.DataFrame())
    status=bundle.get('status',pd.DataFrame())
    with st.container(border=True,key='source_dataset_preview'):
        left,right=st.columns([5,3])
        with left:
            st.markdown('**Data preview**')
            if not records.empty:
                render_table_preview(table_key,records)
            elif unavailable or not browsing:
                st.write(row.get('brief_description') or row.get('dashboard_use') or row['title'])
                if not unavailable:
                    st.caption('Turn on Browse connected records to preview a dataset.')
            elif dates is None:
                st.caption('Select a valid date range to preview the records.')
            elif table_key=='ea_floods':
                st.info('No current warning records to export. Check the provider response and official source.')
            elif table_key=='ea_liverpool_archive':
                st.info('Historical archive records are unavailable in this build.')
            else:
                st.info('The requested measurement reference has no returned observations in this period. Clear the observation context to choose another reference.'
                        if handoff else 'No records returned for this dataset. Check the source response below.')
            if not status.empty:
                with st.expander('Source response',expanded=records.empty):
                    st.dataframe(status.reindex(columns=['source','status','records','last_call_utc','access_note']),
                                 hide_index=True,width='stretch')
        with right:
            st.markdown('**Access and downloads**')
            st.caption(f"{selected} · {row.get('domain','')}")
            st.caption('Access: '+' · '.join(str(value) for value in (row.get('access_level'),row.get('cost')) if value))
            st.caption('Format: '+str(row.get('format',''))+' · '+timing)
            if unavailable:
                st.caption(unavailable)
            if table_key:
                st.markdown('**'+product['tables'][table_key]+'**')
            if not records.empty:
                st.caption(f'{len(records):,} returned records in the CSV')
                period=returned_period(table_key,records)
                if period:
                    st.caption(period)
                st.download_button('Download dataset CSV',archive_csv if archive_csv is not None else records.to_csv(index=False).encode(),
                    table_key+'.csv','text/csv',type='primary',on_click='ignore',width='stretch')
            if not unavailable and product.get('integration') and dates is not None:
                source,table=product['integration']
                if table_key in (None,table):
                    context=handoff if handoff and handoff['source']==source and handoff['source_id']==selected else None
                    st.button('Use in Integration',key='data_integrate_'+selected,on_click=_use_source_in_integration,
                        args=(source,dates if browsing else None,context),
                        help=f"Preselect {product['tables'][table]}. Collection starts when you choose Load selected records.")
            _source_link(row.get('url',''))
            if table_key=='water_levels':
                st.caption('Values retain the provider measurement, unit, vertical datum and source time.')
            elif table_key=='ea_liverpool_archive' and archive_csv is not None:
                manifest_bytes=(DATA_DIR/'ea_liverpool_archive_manifest.json').read_bytes()
                manifest=json.loads(manifest_bytes)
                spans=[f"{span['start_date']} to {span['end_date']}" for span in manifest['coverage']]
                st.caption('Historical observation windows (UTC) · '+' · '.join(spans))
                st.caption(manifest['attribution'])
                st.markdown('[Open EA daily archive]('+manifest['source_url']+') · [Open Government Licence]('+manifest['licence_url']+')')
                st.download_button('Download archive provenance JSON',manifest_bytes,'ea_liverpool_archive_manifest.json',
                    'application/json',on_click='ignore',width='stretch')
            elif table_key=='webtris_daily':
                st.caption('Road-counter observations use source timestamps with an unverified timezone.')
            elif table_key=='ea_floods':
                st.caption('Current EA warnings returned for the Liverpool-area query. Check validity with the provider.')
                st.markdown('[Open EA warning feed]('+daily_service.FLOODS_URL+')')


def _catalogue(catalog,load_bundle,views):
    inventory=pd.read_csv(DATA_DIR/'source_inventory_references.csv').fillna('')
    catalogue_sources=len(catalog)
    catalog=pd.concat([catalog,inventory],ignore_index=True).fillna('')
    report=load_validation_report()
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
    preview=st.container()
    with st.expander('Source register and validation'):
        render_validation_summary(catalog,report,SOURCE_PRODUCTS)
        st.caption(f'{catalogue_sources} existing catalogue entries and {len(inventory)} additional project inventory references.')
        st.dataframe(register,hide_index=True,width='stretch',height=300)
        st.download_button('Download filtered source register',register.to_csv(index=False).encode(),
            'CRDT_source_validation_register.csv','text/csv')
    labels=frame.set_index('source_id')['title'].to_dict()
    if st.session_state.get('data_source_id') not in labels:
        st.session_state['data_source_id']=None
    with preview:
        selected=st.selectbox('Data source',list(labels),format_func=labels.get,index=None,
            placeholder='Choose a source to preview or download',key='data_source_id',on_change=clear_context,args=('data_handoff',))
        if selected is None:
            if 'HS004' in labels and {'raw_data','weather'} <= views:
                st.button('Preview Liverpool historical water levels',on_click=_preview_liverpool_archive)
            return
        row=frame[frame['source_id'].eq(selected)].iloc[0]
        st.markdown('**'+str(row['title'])+'**')
        assessment = next((item for item in report['sources'] if item['source_id'] == selected
                           and item['evidence_status'] == 'report_assessment'), None)
        from_inventory=selected in set(inventory['source_id'])
        timing = ('C1 data role: ' + assessment['temporal_role'] if assessment
                  else 'Project source inventory' if from_inventory else 'Catalogue period: ' + str(row.get('period','')))
        render_provider_notice(selected)
        if selected=='HS007':
            st.caption('Traffic counts are historical; [WebTRIS is usually published about one month after collection](https://webtris.highwaysengland.co.uk/Home/Faqs).')
        _source_dataset(row,load_bundle,views,handoff,timing)
        if from_inventory:
            st.caption('Source discovered in the project inventory. Use the provider link for current access and reuse terms.')
        else:
            render_source_validation(report,selected)
        with st.expander('Catalogue metadata'):
            st.caption('Original source assessment, suggested use and access notes; catalogue entries do not establish current availability.')
            st.json(row.to_json())


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
    left,right=st.columns([5,3])
    with left:
        st.markdown('**Quality findings**')
        if findings.empty:
            st.caption('No configured findings in the returned streams. Coverage is limited to the records supplied by each source.')
        else:
            st.dataframe(findings,hide_index=True,width='stretch')
        with st.expander('Full quality and source register'):
            st.dataframe(table,hide_index=True,width='stretch')
            st.dataframe(bundle.get('status',pd.DataFrame()),hide_index=True,width='stretch')
    with right:
        st.markdown('**Quality downloads**')
        st.caption('Requested days · '+' to '.join(dates))
        st.download_button('Export observation report',report_archive(bundle,table,*dates),
            'CRDT_observation_report.zip','application/zip',type='primary',on_click='ignore',width='stretch')
        st.download_button('Download quality CSV',table.to_csv(index=False).encode(),
            'CRDT_quality.csv','text/csv',on_click='ignore',width='stretch')
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
        right.button('Browse datasets & downloads',type='secondary' if st.session_state.get('data_workspace_tab')=='Sources' else 'primary',
            width='stretch',key='data_open_sources',
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
