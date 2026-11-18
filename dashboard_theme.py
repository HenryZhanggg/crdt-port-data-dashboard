"""Shared presentation for the public overview and research workspaces."""
import streamlit as st


def apply_dashboard_theme() -> None:
    st.markdown('''<style>
    :root {
        --port-bg:#080B12; --port-panel:#111722; --port-divider:#253041;
        --port-ink:#F2F5F9; --port-muted:#95A2B5; --port-accent:#7C83FD;
        --port-teal:#7C83FD;
    }
    html, body, [data-testid="stAppViewContainer"] {background:var(--port-bg); color:var(--port-ink);}
    [data-testid="stHeader"] {background:rgba(8,11,18,.94);}
    .block-container {max-width:1680px; padding-top:3rem; padding-bottom:3rem;}
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {gap:.9rem;}
    [data-testid="stMainBlockContainer"], [data-testid="stColumn"] {min-width:0;}
    [data-testid="stAppViewContainer"] h1 {font-size:2rem; line-height:1.2; letter-spacing:-.04em; padding-bottom:.5rem;}
    h2, h3 {letter-spacing:-.025em;}
    h2 {font-size:1.4rem;}
    h3 {font-size:1.15rem;}
    p, li {line-height:1.55;}
    a {text-underline-offset:3px;}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color:var(--port-muted);}
    [data-testid="stSidebar"] {background:var(--port-panel); border-right:1px solid var(--port-divider);}
    [data-testid="stSidebar"] h1 {font-size:1.2rem; line-height:1.4;}
    .workbench-header {
        display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:.7rem 1.5rem;
        background:#111722;
        color:var(--port-ink); border:1px solid #30364b; border-radius:14px; padding:1.15rem 1.35rem;
    }
    .workbench-header > div {display:flex; align-items:center; flex-wrap:wrap; gap:.4rem 1.2rem; min-width:0;}
    .workbench-brand {font-size:1.12rem; font-weight:650; letter-spacing:-.025em;}
    .workbench-subtitle, .workbench-region {font-size:.73rem; line-height:1.5; letter-spacing:.04em; color:var(--port-muted);}

    .workspace-context {
        display:flex; flex-wrap:wrap; gap:.35rem 1.2rem; padding:.65rem .85rem;
        background:var(--port-panel); border:1px solid var(--port-divider);
        border-left:3px solid var(--port-accent); border-radius:8px;
        color:var(--port-muted); font-size:.76rem; line-height:1.6;
    }
    .workspace-context span {min-width:0; overflow-wrap:anywhere;}
    .workspace-context span:first-child {color:var(--port-ink); font-weight:600;}
    .integration-steps {
        display:flex; flex-wrap:wrap; gap:.35rem .75rem; padding:.7rem .85rem;
        background:#111722; border:1px solid var(--port-divider); border-radius:8px;
        color:#C5C9F4; font-size:.78rem; line-height:1.7;
    }
    .integration-steps span {color:#66728A;}
    .workspace-meta {
        display:flex; flex-wrap:wrap; justify-content:space-between; gap:.4rem 1rem;
        color:var(--port-muted); border-bottom:1px solid var(--port-divider);
        padding:.25rem 0 .75rem; margin:0; font-size:.74rem; line-height:1.5;
    }
    .st-key-workspace_toolbar {padding:.8rem 1rem; background:var(--port-panel); border:1px solid var(--port-divider); border-radius:12px;}
    .st-key-workspace_toolbar [data-testid="stWidgetLabel"] p {font-size:.75rem; color:var(--port-muted);}
    .st-key-workspace_shortcuts, .st-key-data_actions {max-width:720px;}
    .st-key-workspace_shortcuts [data-testid="stButton"] button {min-height:2.4rem;}
    .st-key-workspace_shortcuts [data-testid="stButton"] p {font-size:.8rem;}
    [data-testid="stButton"] button, [data-testid="stDownloadButton"] button,
    [data-testid="stPopover"] button {border-radius:8px; transition:border-color .15s, background .15s;}
    [data-testid="stButton"] button[kind="primary"] {box-shadow:0 0 18px rgba(124,131,253,.1);}
    [data-testid="stTextInput"] [data-baseweb="input"],
    [data-testid="stDateInput"] [data-baseweb="input"],
    [data-testid="stSelectbox"] [data-baseweb="select"] > div {
        border:1px solid var(--port-divider); background:#0D121D; border-radius:8px;
    }
    [data-testid="stExpander"], [data-testid="stDataFrame"] {border-radius:10px; border-color:var(--port-divider);}
    [data-testid="stDataFrame"] {overflow:hidden;}
    [data-testid="stTabs"] [data-baseweb="tab-list"] {gap:1rem; border-bottom:1px solid var(--port-divider);}
    [data-testid="stTabs"] [data-baseweb="tab"] {font-size:.83rem;}
    [data-testid="stAlert"] {border-radius:10px;}
    [data-testid="stMetric"] {
        background:var(--port-panel); border:1px solid var(--port-divider); border-radius:12px;
        min-height:100px; padding:.9rem 1rem; overflow:hidden;
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
        color:var(--port-muted); font-size:.76rem; line-height:1.4;
        white-space:normal !important; overflow:visible; overflow-wrap:anywhere; text-overflow:clip;
    }
    [data-testid="stMetricValue"] {
        color:var(--port-ink); font-size:1.65rem; line-height:1.5; font-weight:600;
        font-variant-numeric:tabular-nums; white-space:normal; overflow-wrap:anywhere;
    }
    .stPlotlyChart {border:0; border-radius:10px; padding:0; background:var(--port-panel); overflow:hidden;}
    .st-key-workbench_spatial, .st-key-workbench_inspector, [class*="st-key-workbench_panel_"],
    .st-key-semantic_objects, .st-key-semantic_spatial, .st-key-semantic_inspector,
    .st-key-semantic_content, .st-key-semantic_analysis,
    .st-key-semantic_observed_map, .st-key-semantic_observed_inspector,
    .st-key-daily_spatial, .st-key-daily_updates, .st-key-daily_content, .st-key-daily_places,
    .st-key-daily_weather_trend, .st-key-daily_water_trend, .st-key-daily_public_media {
        background:var(--port-panel); border-color:var(--port-divider); border-radius:12px;
    }
    .workbench-panel-title {
        display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:.35rem;
        padding-bottom:.7rem; border-bottom:1px solid var(--port-divider); color:var(--port-muted);
        font-size:.7rem; font-weight:600; line-height:1.5; letter-spacing:.09em;
    }
    .workbench-panel-title span {font-size:.68rem; font-weight:400; letter-spacing:0; color:var(--port-muted);}
    .workbench-identity {font-size:.73rem; line-height:1.7; color:var(--port-muted); overflow-wrap:anywhere;}
    .workbench-reading {font-size:1.8rem; font-weight:500; line-height:1.3; font-variant-numeric:tabular-nums; color:var(--port-ink); margin:.3rem 0;}
    .workbench-reference {margin:.3rem 0; display:grid; grid-template-columns:75px minmax(0,1fr); gap:.45rem .7rem; font-size:.77rem;}
    .workbench-reference dt {color:var(--port-muted);}
    .workbench-reference dd {margin:0; font-variant-numeric:tabular-nums; overflow-wrap:anywhere;}
    .port-map-context, .port-map-legend {
        display:flex; flex-wrap:wrap; gap:.45rem 1rem; padding:.65rem .8rem;
        background:#0D121D; color:var(--port-muted); font-size:.71rem; line-height:1.5;
    }
    .port-map-context {justify-content:space-between; border-radius:8px 8px 0 0; letter-spacing:.05em;}
    .port-map-legend {align-items:center; border-radius:0 0 8px 8px;}
    .port-map-legend span {display:inline-flex; align-items:center; gap:.4rem;}
    .port-map-legend i {display:inline-block; width:7px; height:7px; border-radius:50%;}
    .quality-note {display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; padding:.55rem .7rem;
        border:1px solid var(--port-divider); background:#151D2A; border-radius:8px; margin:.2rem 0; color:var(--port-muted); font-size:.76rem;}
    .quality-note strong {font-weight:500; color:var(--port-ink);}
    .quality-dot {width:7px; height:7px; border-radius:50%; display:inline-block; flex-shrink:0;}
    .monitor-hero {padding:1.4rem; border:1px solid #30364b; border-radius:14px;
        background:linear-gradient(115deg,#171B2F,#111722 70%); margin:.3rem 0 .8rem;}
    .monitor-hero h2 {color:var(--port-ink); font-size:1.45rem !important; padding:0 !important; margin:.45rem 0;}
    .monitor-hero p {color:var(--port-muted); margin-bottom:0; padding:0; font-size:.9rem;}
    .eyebrow {font-size:.68rem; letter-spacing:.12em; font-weight:600; color:#ADB2FF;}
    .stream-card, .action-item {border:1px solid var(--port-divider); border-radius:10px; background:var(--port-panel); padding:.9rem 1rem; margin:.4rem 0;}
    .stream-card h3 {font-size:.85rem !important; padding:0 !important; margin:0 0 .4rem;}
    .stream-card .reading {font-size:1.8rem; font-weight:600; line-height:2.1rem; font-variant-numeric:tabular-nums;}
    .stream-card small, .action-meta {color:var(--port-muted); font-size:.8rem;}
    .action-list {display:grid; gap:.55rem;}
    .action-title {display:flex; gap:.55rem; align-items:center; font-weight:600; color:var(--port-ink);}
    .action-meta {margin-top:.22rem;}
    .action-body {margin-top:.4rem; color:var(--port-ink); font-size:.9rem; line-height:1.5;}
    .state-pill {display:inline-block; border-radius:999px; padding:.12rem .5rem; font-size:.73rem; background:#202A3A; color:#C5CFDD; white-space:nowrap;}
    .st-key-semantic_heading h3, .st-key-daily_heading h3 {font-size:1.65rem; font-weight:600; padding:.2rem 0;}
    .st-key-semantic_heading [data-testid="stVerticalBlock"] {gap:.2rem;}
    .st-key-semantic_context {background:var(--port-panel); border:1px solid var(--port-divider); border-radius:12px; padding:.75rem 1rem;}
    .st-key-semantic_context [data-testid="stWidgetLabel"] p,
    .st-key-semantic_spatial [data-testid="stWidgetLabel"] p,
    .st-key-semantic_objects [data-testid="stWidgetLabel"] p {font-size:.75rem; color:var(--port-muted);}
    .st-key-semantic_objects, .st-key-semantic_inspector, .st-key-semantic_analysis {gap:.55rem;}
    .st-key-semantic_objects [data-testid="stButton"] button,
    .st-key-semantic_inspector [data-testid="stButton"] button {min-height:2.5rem; text-align:left;}
    .st-key-semantic_objects [data-testid="stButton"] p,
    .st-key-semantic_inspector [data-testid="stButton"] p {font-size:.8rem; line-height:1.4;}
    [class*="st-key-semantic_"] [data-testid="stCaptionContainer"] p,
    [class*="st-key-daily_"] [data-testid="stCaptionContainer"] p {color:var(--port-muted); font-size:.77rem; line-height:1.55;}
    .st-key-semantic_inspector pre {white-space:pre-wrap; overflow-wrap:anywhere; font-size:.75rem;}
    .st-key-semantic_content [data-testid="stTabs"] {gap:.4rem;}
    .semantic-status {display:flex; flex-wrap:wrap; gap:.4rem .5rem; color:var(--port-muted); font-size:.65rem; line-height:1.5; letter-spacing:.04em;}
    .semantic-status span {padding:.2rem .5rem; background:#1A2232; border:1px solid #303B50; border-radius:5px;}
    .semantic-legend {display:flex; flex-wrap:wrap; gap:.4rem 1rem; color:var(--port-muted); font-size:.72rem;}
    .semantic-legend span {display:inline-flex; align-items:center; gap:.4rem;}
    .semantic-legend i {display:inline-block; flex-shrink:0; background:var(--port-accent);}
    .semantic-node {width:8px; height:8px; border-radius:50%;}
    .semantic-edge {width:18px; height:2px;}
    .semantic-legend .semantic-muted {height:1px; background:#58657A;}
    .semantic-fields {grid-template-columns:64px minmax(0,1fr); margin:.2rem 0; gap:.5rem .6rem;}
    [class*="st-key-semantic_"] [data-testid="stMarkdownContainer"]:has(> .semantic-status),
    [class*="st-key-semantic_"] [data-testid="stMarkdownContainer"]:has(> .semantic-fields),
    [class*="st-key-semantic_"] [data-testid="stMarkdownContainer"]:has(> .workbench-panel-title),
    [class*="st-key-daily_"] [data-testid="stMarkdownContainer"]:has(> .workbench-panel-title) {margin-bottom:0;}
    .st-key-semantic_inspector .semantic-fields dt, .st-key-semantic_inspector .semantic-fields dd {font-size:.77rem; line-height:1.6;}
    .st-key-daily_summary [data-testid="stMetricValue"] {font-size:1.65rem; font-weight:600;}
    .daily-update-title {font-size:.9rem; line-height:1.5; font-weight:600; color:var(--port-ink);}
    .daily-update {padding:.8rem 0; border-bottom:1px solid var(--port-divider);}
    .daily-update:last-child {border-bottom:0;}
    .daily-category {font-size:.64rem; font-weight:600; letter-spacing:.08em; line-height:1.6; color:var(--port-muted); margin-bottom:.25rem; text-transform:uppercase;}
    .daily-update-title a {color:#B0B5FF; text-decoration:none;}
    .daily-update-title a:hover {color:#CFD2FF; text-decoration:underline;}
    .daily-source {font-size:.75rem; color:var(--port-muted); line-height:1.6;}
    .daily-media {display:block; width:100%; aspect-ratio:16/9; object-fit:cover; border-radius:9px; border:1px solid var(--port-divider);}
    @media (max-width:700px) {
        .block-container {padding:3rem .85rem 2rem;}
        [data-testid="stAppViewContainer"] h1 {font-size:1.55rem !important; line-height:1.25;}
        h2, h3 {font-size:1.15rem; line-height:1.4;}
        .workbench-header {padding:1rem; gap:.7rem;}
        .workbench-brand {font-size:1rem;}
        .workbench-subtitle, .workbench-region, .workspace-meta {font-size:.69rem; overflow-wrap:anywhere;}
        .st-key-workspace_toolbar {padding:.6rem;}
        [data-testid="stHorizontalBlock"] {flex-direction:column;}
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {width:100% !important; flex:1 1 auto !important; min-width:0;}
        .st-key-workspace_shortcuts [data-testid="stHorizontalBlock"] {flex-direction:row; flex-wrap:wrap; gap:.4rem;}
        .st-key-workspace_shortcuts [data-testid="stColumn"] {width:auto !important; flex:1 1 135px !important; min-width:0;}
        .st-key-workbench_summary [data-testid="stHorizontalBlock"],
        .st-key-daily_summary [data-testid="stHorizontalBlock"] {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.55rem;}
        .st-key-workbench_summary [data-testid="stColumn"], .st-key-daily_summary [data-testid="stColumn"] {width:auto; min-width:0;}
        [data-testid="stMetric"] {min-height:92px; padding:.75rem;}
        [data-testid="stMetricValue"], .st-key-daily_summary [data-testid="stMetricValue"] {font-size:1.4rem;}
        [data-testid="stMetricLabel"] p {font-size:.72rem;}
        .st-key-semantic_heading h3, .st-key-daily_heading h3 {font-size:1.4rem;}
        .monitor-hero {padding:1rem;}
        .monitor-hero h2 {font-size:1.25rem !important; line-height:1.4;}
        .workbench-reference {grid-template-columns:68px minmax(0,1fr);}
    }
    @media (pointer:coarse) {[data-testid="stButton"] button, [data-testid="stPopover"] button {min-height:44px;}}
    </style>''', unsafe_allow_html=True)
