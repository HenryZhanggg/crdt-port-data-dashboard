from __future__ import annotations

import hmac
import importlib
import json
import os
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from api_connectors import empty_bundle, fetch_raw_data_bundle
from dashboard_theme import apply_dashboard_theme, apply_overview_theme
from daily_service import load_daily_snapshot
from daily_views import render_daily_home
import data_views
from monitor_workspace import render_monitor_workspace
from workspace_links import workspace_context_summary, context_allowed

BASE_DIR=Path(__file__).parent
DATA_DIR=BASE_DIR/'data'
WORKSPACE_BUILD='2026-11-24.1'

st.set_page_config(page_title='CRDT port dashboard version 1',layout='wide',initial_sidebar_state='collapsed')

def get_dashboard_password() -> str:
    try:
        secret_password = st.secrets.get("DASHBOARD_PASSWORD")
    except Exception:
        secret_password = None

    return str(secret_password or os.getenv("DASHBOARD_PASSWORD", "")).strip()


def require_dashboard_authorisation() -> bool:
    if st.session_state.get("dashboard_authorised"):
        return True

    configured_password = get_dashboard_password()
    auth_panel = st.empty()
    with auth_panel.container():
        st.title("CRDT port dashboard version 1")
        st.subheader("Authorised access")
        st.caption("Enter the dashboard password to continue.")
        st.caption("Interface update: 24 November 2026 · Liverpool Overview and source coverage · build "+WORKSPACE_BUILD)

        if not configured_password:
            st.error("Dashboard password is not configured. Set DASHBOARD_PASSWORD in Streamlit secrets.")
            return False

        with st.form("dashboard_password_form"):
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Unlock dashboard")

        if submitted:
            if hmac.compare_digest(password, configured_password):
                st.session_state["dashboard_authorised"] = True
                auth_panel.empty()
                return True
            st.error("Incorrect password.")

    return False


@st.cache_data(ttl=60)
def load_csv(name: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    path = DATA_DIR / name
    return pd.read_csv(path, parse_dates=parse_dates)


@st.cache_data(ttl=300)
def load_service_area() -> dict:
    with (DATA_DIR / "service_area.geojson").open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=300)
def load_high_score_catalog() -> pd.DataFrame:
    path = DATA_DIR / "high_score_dataset_catalog.csv"
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "source_id",
                "category",
                "title",
                "rank",
                "data_quality",
                "domain",
                "source_type",
                "url",
                "format",
                "cost",
                "period",
                "brief_description",
                "highlighted_comment",
                "access_level",
                "connection_mode",
                "dashboard_use",
                "status",
            ]
        )

    catalog = pd.read_csv(path).fillna("")
    catalog["rank"] = pd.to_numeric(catalog["rank"], errors="coerce")
    catalog["data_quality"] = pd.to_numeric(catalog["data_quality"], errors="coerce")
    catalog["domain"] = catalog["domain"].replace({"Weather / Flood": "Weather / Water"})
    catalog["category"] = catalog["category"].str.replace(
        "flood risk", "water-level context", case=False, regex=False
    )
    catalog["dashboard_use"] = catalog["dashboard_use"].str.replace(
        "Crisis trigger, weather window, flood-risk signal",
        "Water-level and weather monitoring visualisation",
        regex=False,
    )
    return catalog


@st.cache_data(ttl=300, show_spinner=False)
def load_observation_source(source, start_date, end_date):
    return fetch_raw_data_bundle(start_date, end_date, sources=(source,))


@st.cache_data(ttl=86400, show_spinner=False)
def load_reference_source(source):
    return fetch_raw_data_bundle(sources=(source,))


def load_selected_api_bundle(start_date, end_date, sources) -> dict[str, pd.DataFrame]:
    bundle = empty_bundle()
    statuses = []
    for source in sources:
        result = load_observation_source(source, start_date, end_date) if source in {"ea", "water_level", "webtris"} else load_reference_source(source)
        for name, frame in result.items():
            if name == "status":
                # Connector calls also return an unrelated static deferred register.
                statuses.append(frame.loc[frame['status'].isin(['api_connected','api_no_data','api_error'])] if 'status' in frame else frame)
            elif not frame.empty:
                bundle[name] = frame
    if statuses:
        bundle["status"] = pd.concat(statuses, ignore_index=True).drop_duplicates("connector_id", keep="last")
    return bundle


def refresh_sources(sources,start_date,end_date):
    for source in sources:
        if source in {'ea','water_level','webtris'}:
            load_observation_source.clear(source,start_date,end_date)
        else:
            load_reference_source.clear(source)


def _navigate(page):
    st.session_state['dashboard_page']=page


def _apply_workspace_link():
    route=(st.query_params.get('workspace','').casefold(),st.query_params.get('tool','').casefold())
    if route[0]=='data' and route[1] in {'integration','sources'} and st.session_state.get('applied_workspace_link')!=route:
        st.session_state['dashboard_page']='Data'
        st.session_state['data_workspace_tab']=route[1].capitalize()
        st.session_state['applied_workspace_link']=route


def _render_current_data_workspace(*args,**kwargs):
    if getattr(data_views,'DATA_WORKSPACE_BUILD',None)!=WORKSPACE_BUILD:
        importlib.reload(data_views)
    if getattr(data_views,'DATA_WORKSPACE_BUILD',None)!=WORKSPACE_BUILD:
        st.error('The Data workspace update has not loaded completely. Please reopen the dashboard after deployment finishes.')
        return
    data_views.render_data_workspace(*args,**kwargs)


def _preserve_workspace_widgets():
    keys={'daily_place_id','daily_update_category','monitor_data_mode','monitor_mode',
          'monitor_source_choice','workbench_reference','workbench_layer_water','workbench_layer_traffic',
          'data_workspace_tab','data_source_id','data_source_search','data_quality_scope','data_role_filter','data_route_filter',
          'data_preview_mode','data_quality_mode',
          'monitor_dates_Historical browsing','data_preview_dates_Historical browsing',
          'data_quality_dates_Historical browsing'}
    integration_actions={'integration_load','integration_audit_download','integration_snapshot_download',
                         'integration_report_download','integration_collection_download','integration_timeline',
                         'integration_csv_file','integration_csv_apply','integration_csv_clear','integration_csv_mapping',
                         'integration_contract_inputs_download','integration_contract_checks_download','integration_contract_download',
                         'integration_link_apply','integration_link_download','integration_product_download'}
    for key in list(st.session_state):
        if key in keys or key.startswith(('data_table_','data_browse_')) or (key.startswith('integration_') and key not in integration_actions and not key.startswith(('integration_contract_requirements_','integration_link_bindings_'))):
            # Detach off-page widget values from Streamlit's widget cleanup.
            st.session_state[key]=st.session_state[key]


def _migrate_navigation():
    if 'dashboard_page' in st.session_state:
        return
    section=st.session_state.get('workspace_section','Monitoring')
    old=st.session_state.get('workspace_view_'+section,'Overview')
    monitoring={'Live Monitoring','GIS','Observation Explorer','Transport','Objects & Dependencies','Scenarios & Runs','Research & Replay'}
    data={'Dataset Catalogue','Data Status','Raw Data','Data Quality','Report Centre','Module Registry','Demonstrator Tasks','Governance Handover'}
    if old in monitoring:
        st.session_state['dashboard_page']='Monitor'
        st.session_state['monitor_data_mode']='Connected observations'
        if old in {'Observation Explorer','Research & Replay'}:
            st.session_state['monitor_source_choice']=['water_level']
        elif old=='Transport':
            st.session_state['monitor_source_choice']=['webtris']
    elif old in data:
        st.session_state['dashboard_page']='Data'
        if old in {'Data Quality','Report Centre'}:
            st.session_state['data_workspace_tab']='Quality'
    elif old in {'Monitor','Port connections example'}:
        st.session_state['dashboard_page']='Monitor'
        st.session_state['monitor_data_mode']='Example network'
    else:
        st.session_state['dashboard_page']='Overview'


def main():
    apply_dashboard_theme()
    if not require_dashboard_authorisation():
        st.stop()
    _preserve_workspace_widgets()
    partners=load_csv('partners.csv')
    st.sidebar.title('CRDT port dashboard version 1')
    if st.sidebar.button('Lock dashboard'):
        st.session_state['dashboard_authorised']=False
        for field in ['partner_runs','dependency_package','current_run_id','current_run_picker','workbench_entity_id','applied_workspace_link']:
            st.session_state.pop(field,None)
        for field in list(st.session_state):
            if field.startswith('integration_'):
                st.session_state.pop(field,None)
        st.rerun()
    partner_name=st.sidebar.selectbox('Partner',partners['partner_name'].tolist())
    partner=partners[partners['partner_name'].eq(partner_name)].iloc[0]
    views={name.strip() for name in partner['can_view'].split(',')}
    st.sidebar.caption('Prototype partner view · '+str(partner['access_level']))
    st.sidebar.caption('Dashboard build: '+WORKSPACE_BUILD)
    _migrate_navigation()
    _apply_workspace_link()
    pages=['Overview','Monitor']
    if views & {'dataset_catalog','raw_data','data_status'}:
        pages.append('Data')
    if st.session_state.get('dashboard_page') not in pages:
        st.session_state['dashboard_page']='Overview'
    page=st.session_state['dashboard_page']
    st.markdown('<header class="workbench-header"><div><span class="workbench-brand" role="heading" aria-level="1">CRDT port dashboard version 1</span>'
        '<span class="workbench-subtitle">CONNECTED PORT INTELLIGENCE</span></div>'
        '<span class="workbench-region">LIVERPOOL &amp; MERSEYSIDE</span></header>',unsafe_allow_html=True)
    with st.container(key='workspace_shortcuts'):
        for column,name in zip(st.columns(len(pages),gap='small'),pages):
            column.button('Data & Integration' if name=='Data' else name,key='nav_'+name,width='stretch',type='primary' if name==page else 'secondary',on_click=_navigate,args=(name,))
    context_slot=st.empty()
    if page=='Overview':
        apply_overview_theme()
        with st.spinner('Checking local weather, water levels and official updates'):
            snapshot=load_daily_snapshot()
        render_daily_home(snapshot)
    elif page=='Monitor':
        render_monitor_workspace(load_selected_api_bundle,load_csv('assets.csv'),load_service_area(),views,refresh=refresh_sources)
    else:
        _render_current_data_workspace(load_high_score_catalog(),load_selected_api_bundle,views,refresh=refresh_sources)
    summary=workspace_context_summary() if page!='Overview' else None
    context=st.session_state.get('data_handoff' if page=='Data' else 'monitor_handoff')
    if page=='Data' and 'raw_data' not in views or page!='Overview' and context and not context_allowed(context,views):
        summary=None
    if summary:
        fields=[summary['mode'],summary['label']]
        if summary.get('start') and summary.get('end'):
            fields.append(str(summary['start'])+' → '+str(summary['end']))
        fields.append(summary['time_basis'])
        context_slot.markdown('<div class="workspace-context" role="status">'+
            ''.join('<span>'+escape(str(value))+'</span>' for value in fields if value)+'</div>',unsafe_allow_html=True)



if __name__=='__main__':
    main()
