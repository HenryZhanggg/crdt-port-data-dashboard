from __future__ import annotations

import hmac
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from api_connectors import fetch_raw_data_bundle


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BASE_MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

STATUS_COLOR = {
    "Normal": [35, 134, 84, 190],
    "Low": [35, 134, 84, 190],
    "Watch": [219, 158, 48, 190],
    "Medium": [219, 158, 48, 190],
    "Warning": [204, 72, 72, 205],
    "High": [204, 72, 72, 205],
    "Severe": [119, 43, 43, 220],
}
CONNECTOR_STATUS_LABELS = {
    "api_connected": "Connected",
    "requires_api_key": "Needs API key",
    "requires_login": "Needs login",
    "requires_partner_agreement": "Partner agreement",
    "requires_scraping_review_or_agreement": "Scraping review",
    "deferred_large_gis_extract": "GIS deferred",
    "api_error": "API error",
}
CONNECTOR_STATUS_COLORS = {
    "Connected": "#2f855a",
    "Needs API key": "#c47f17",
    "Needs login": "#c47f17",
    "Partner agreement": "#6b7280",
    "Scraping review": "#6b7280",
    "GIS deferred": "#6b7280",
    "API error": "#991b1b",
}
HIGH_SCORE_PROCESSING = {
    "HS001": {
        "process_state": "Live remote file",
        "connector_ids": ["dft_port0101_api", "dft_port0602_api"],
        "data_surface": "Port freight tonnage and ship-arrival charts",
        "next_step": "Select additional DfT PORT tables if partners need cargo-type detail.",
    },
    "HS002": {
        "process_state": "Reference visual",
        "connector_ids": [],
        "data_surface": "Catalogue link only; source is an interactive DfT visual dashboard",
        "next_step": "Use as benchmark/reference; do not treat as raw data feed.",
    },
    "HS003": {
        "process_state": "GIS review",
        "connector_ids": [],
        "data_surface": "Catalogue link and GIS import placeholder",
        "next_step": "Confirm ArcGIS layer access and licensing before ingest.",
    },
    "HS004": {
        "process_state": "Live API",
        "connector_ids": [
            "ea_monitoring_stations_api",
            "ea_latest_readings_api",
            "ea_liverpool_tide_water_level_api",
        ],
        "data_surface": "Monitoring stations, latest readings and Liverpool tide water level",
        "next_step": "Agree which EA station measures should remain in the default view.",
    },
    "HS005": {
        "process_state": "Needs API key",
        "connector_ids": ["metoffice_datahub"],
        "data_surface": "Deferred connector row",
        "next_step": "Set up Met Office DataHub credentials/subscription.",
    },
    "HS006": {
        "process_state": "Needs API key",
        "connector_ids": ["metoffice_nswws"],
        "data_surface": "Deferred connector row",
        "next_step": "Set up NSWWS public API key if weather-warning visualisation is required.",
    },
    "HS007": {
        "process_state": "Live API",
        "connector_ids": ["webtris_sites_api", "webtris_daily_a5036_api"],
        "data_surface": "A5036 traffic flow chart and WebTRIS sensor map",
        "next_step": "Confirm exact sensor IDs for the preferred port access corridor.",
    },
    "HS008": {
        "process_state": "Portal reference",
        "connector_ids": [],
        "data_surface": "Catalogue link only",
        "next_step": "Review National Highways subscription services if more APIs are needed.",
    },
    "HS009": {
        "process_state": "Live remote CSV",
        "connector_ids": ["naptan_merseyside_api"],
        "data_surface": "Local public transport access-node table and map layer",
        "next_step": "Filter stop types once the service-area boundary is fixed.",
    },
    "HS010": {
        "process_state": "Needs login",
        "connector_ids": ["network_rail_feeds"],
        "data_surface": "Deferred connector row",
        "next_step": "Create Network Rail feed account and select relevant rail feeds.",
    },
    "HS011": {
        "process_state": "Needs partner endpoint",
        "connector_ids": ["local_partner_sensors"],
        "data_surface": "Deferred connector row",
        "next_step": "Ask partners for API endpoint, data dictionary and permitted demo fields.",
    },
    "HS012": {
        "process_state": "Permission review",
        "connector_ids": ["peel_ports_vessel_board"],
        "data_surface": "Deferred connector row",
        "next_step": "Confirm whether scraping or partner-provided API access is allowed.",
    },
    "HS013": {
        "process_state": "GIS review",
        "connector_ids": [],
        "data_surface": "Catalogue link only",
        "next_step": "Check whether vessel-density layers can be exported or called as a service.",
    },
    "HS014": {
        "process_state": "Live remote file",
        "connector_ids": ["ons_weekly_shipping_api"],
        "data_surface": "Weekly Liverpool shipping trend chart",
        "next_step": "Keep as national context; combine with port-specific data later.",
    },
    "HS015": {
        "process_state": "GIS deferred",
        "connector_ids": ["osm_geofabrik_england"],
        "data_surface": "Deferred connector row",
        "next_step": "Clip England OSM extract to the port access corridor using a GIS service.",
    },
    "HS016": {
        "process_state": "GIS deferred",
        "connector_ids": [],
        "data_surface": "Catalogue link only",
        "next_step": "Confirm HOTOSM API/download route and clip to UK seaport assets.",
    },
}
PROCESS_STATE_COLORS = {
    "Live API": "#2f855a",
    "Live remote file": "#2f855a",
    "Live remote CSV": "#2f855a",
    "Reference visual": "#6b7280",
    "Portal reference": "#6b7280",
    "GIS review": "#1f5ba3",
    "GIS deferred": "#1f5ba3",
    "Needs API key": "#c47f17",
    "Needs login": "#c47f17",
    "Needs partner endpoint": "#c47f17",
    "Permission review": "#c47f17",
}


st.set_page_config(
    page_title="CRDT-Port Data Visualisation",
    layout="wide",
    initial_sidebar_state="auto",
)


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
        st.title("CRDT-Port Data Visualisation Dashboard")
        st.subheader("Authorised access")
        st.caption("Enter the dashboard password to continue.")

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


def apply_professional_theme() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.8rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }
        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            min-height: 92px;
            padding: 0.72rem 0.82rem;
            overflow: hidden;
        }
        [data-testid="stMetricLabel"] {
            color: #4b5563;
            font-size: 0.78rem;
            line-height: 1.15rem;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.5rem;
            line-height: 1.85rem;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        h1 {
            font-size: 2rem;
            margin-bottom: 0.35rem;
        }
        h2, h3 {
            margin-top: 0.85rem;
        }
        .stPlotlyChart {
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 0.25rem;
            background: #ffffff;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #e5e7eb;
            border-radius: 6px;
        }
        .stRadio [role="radiogroup"] {
            gap: 0.4rem;
        }
        .action-list {
            display: grid;
            gap: 0.55rem;
        }
        .action-item {
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 0.72rem 0.82rem;
            background: #ffffff;
        }
        .action-title {
            display: flex;
            gap: 0.55rem;
            align-items: center;
            font-weight: 650;
            color: #111827;
        }
        .action-meta {
            color: #4b5563;
            font-size: 0.82rem;
            margin-top: 0.22rem;
        }
        .action-body {
            margin-top: 0.4rem;
            color: #111827;
            font-size: 0.92rem;
            line-height: 1.35rem;
        }
        .state-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 0.08rem 0.48rem;
            font-size: 0.75rem;
            background: #f3f4f6;
            color: #374151;
            white-space: nowrap;
        }
        @media (max-width: 700px) {
            .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }
            h1 {
                font-size: 1.45rem;
                line-height: 1.8rem;
            }
            h2, h3 {
                font-size: 1.12rem;
                line-height: 1.45rem;
            }
            [data-testid="stMetric"] {
                min-height: 78px;
            }
            [data-testid="stMetricValue"] {
                font-size: 1.25rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=60)
def load_csv(name: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    path = DATA_DIR / name
    return pd.read_csv(path, parse_dates=parse_dates)


@st.cache_data(ttl=300)
def load_optional_csv(name: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
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


@st.cache_data(ttl=900, show_spinner=False)
def load_api_raw_bundle() -> dict[str, pd.DataFrame]:
    return fetch_raw_data_bundle()


def format_optional_number(value: object, suffix: str = "", decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.{decimals}f}{suffix}"


def short_label(value: str, max_len: int = 30) -> str:
    if len(value) <= max_len:
        return value
    return f"{value[: max_len - 1]}…"


def build_high_score_processing_matrix(catalog: pd.DataFrame, api_status: pd.DataFrame) -> pd.DataFrame:
    if catalog.empty:
        return pd.DataFrame()

    status_lookup = api_status.set_index("connector_id").to_dict("index") if not api_status.empty else {}
    rows = []
    high_score = catalog[catalog["rank"].ge(4)].sort_values(["rank", "source_id"], ascending=[False, True])
    for _, source in high_score.iterrows():
        source_id = str(source["source_id"])
        plan = HIGH_SCORE_PROCESSING.get(
            source_id,
            {
                "process_state": "Catalogue only",
                "connector_ids": [],
                "data_surface": "Catalogue row",
                "next_step": "Confirm access route.",
            },
        )
        connector_rows = [status_lookup[item] for item in plan["connector_ids"] if item in status_lookup]
        connected_rows = [item for item in connector_rows if item.get("status") == "api_connected"]
        live_status = "Connected" if connected_rows else "Processed / pending access"
        if connector_rows and not connected_rows:
            mapped_status = connector_rows[0].get("status", "")
            live_status = CONNECTOR_STATUS_LABELS.get(str(mapped_status), str(mapped_status))
        records = int(
            sum(
                pd.to_numeric(pd.Series([item.get("records", 0)]), errors="coerce").fillna(0).iloc[0]
                for item in connected_rows
            )
        )
        rows.append(
            {
                "Source ID": source_id,
                "Source": source["title"],
                "Rank": int(source["rank"]) if pd.notna(source["rank"]) else None,
                "Domain": source["domain"],
                "Type": source["source_type"],
                "Access": source["access_level"],
                "Processing state": plan["process_state"],
                "Live status": live_status,
                "Records": records,
                "Dashboard surface": plan["data_surface"],
                "Next step": plan["next_step"],
                "URL": source["url"],
            }
        )
    return pd.DataFrame(rows)


def latest_water_level_summary(water_levels: pd.DataFrame) -> tuple[str, str]:
    if water_levels.empty:
        return "n/a", "Liverpool tide gauge data unavailable"
    levels = water_levels.dropna(subset=["date_time", "value"]).sort_values("date_time")
    if levels.empty:
        return "n/a", "No numeric water-level readings returned"
    preferred = levels[levels["unit"].eq("mAOD")]
    latest = (preferred if not preferred.empty else levels).iloc[-1]
    value = f"{float(latest['value']):.3f} {latest['unit']}"
    note = f"{latest['station_label']} | {latest['datum']} | {latest['date_time']}"
    return value, note


def allowed_views(partner_row: pd.Series) -> set[str]:
    return {item.strip() for item in partner_row["can_view"].split(",")}


def render_metric_card(label: str, value: str, help_text: str | None = None) -> None:
    st.metric(label=label, value=value, help=help_text)


def polish_chart(fig, height: int = 330):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=20, b=10),
        legend_title_text="",
        font=dict(size=12),
    )
    return fig


def render_access_banner(partner: pd.Series) -> None:
    st.sidebar.caption("Partner view")
    st.sidebar.write(f"**{partner['partner_name']}**")
    st.sidebar.write(f"Role: {partner['role']}")
    st.sidebar.write(f"Access: {partner['access_level']}")


def map_layers(assets: pd.DataFrame, service_area: dict) -> list[pdk.Layer]:
    map_df = assets.copy()
    map_df["color"] = map_df["status"].map(STATUS_COLOR)
    map_df["radius"] = map_df["asset_type"].map(
        {"Port": 260, "Terminal": 210, "Gate": 160, "Road segment": 170, "Rail link": 150, "Water-level context area": 190}
    ).fillna(150)

    return [
        pdk.Layer(
            "GeoJsonLayer",
            service_area,
            stroked=True,
            filled=True,
            get_fill_color=[31, 111, 120, 22],
            get_line_color=[31, 111, 120, 180],
            line_width_min_pixels=2,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position="[lon, lat]",
            get_radius="radius",
            get_fill_color="color",
            pickable=True,
        ),
    ]


def render_overview(
    assets: pd.DataFrame,
    weather: pd.DataFrame,
    transport: pd.DataFrame,
    sources: pd.DataFrame,
    catalog: pd.DataFrame,
) -> None:
    with st.spinner("Calling open data APIs"):
        api_bundle = load_api_raw_bundle()
    api_status = api_bundle.get("status", pd.DataFrame())
    processing = build_high_score_processing_matrix(catalog, api_status)
    connected = api_status[api_status["status"].eq("api_connected")] if not api_status.empty else pd.DataFrame()
    live_records = pd.to_numeric(connected.get("records", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    water_value, water_note = latest_water_level_summary(api_bundle.get("water_levels", pd.DataFrame()))

    top_metrics = st.columns(4)
    top_metrics[0].metric("Rank >=4 sources", str(len(processing)))
    top_metrics[1].metric("Connected data feeds", f"{len(connected)}/{len(api_status)}")
    top_metrics[2].metric("Visible API/file records", f"{live_records:,.0f}")
    top_metrics[3].metric("Latest water level", water_value, help=water_note)

    st.subheader("High-score source processing")
    if not processing.empty:
        processing_chart = processing.groupby(["Domain", "Processing state"], as_index=False).size()
        fig = px.bar(
            processing_chart,
            x="Domain",
            y="size",
            color="Processing state",
            labels={"size": "Sources"},
            color_discrete_map=PROCESS_STATE_COLORS,
        )
        st.plotly_chart(polish_chart(fig, height=330), width="stretch")

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("Live records by domain")
        if not connected.empty:
            connected_plot = connected.copy()
            connected_plot["records"] = pd.to_numeric(connected_plot["records"], errors="coerce").fillna(0)
            domain_records = connected_plot.groupby("domain", as_index=False)["records"].sum().sort_values("records")
            fig = px.bar(
                domain_records,
                x="records",
                y="domain",
                orientation="h",
                text="records",
                labels={"records": "Records", "domain": ""},
            )
            fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
            st.plotly_chart(polish_chart(fig, height=330), width="stretch")
        else:
            st.info("No connected data feeds are currently available.")
    with right:
        st.subheader("Dashboard data surfaces")
        surface_rows = [
            {"Surface": "Port / Maritime", "What is shown": "DfT port freight, DfT ship arrivals, ONS weekly shipping"},
            {"Surface": "Transport", "What is shown": "WebTRIS A5036 traffic and NaPTAN public transport nodes"},
            {"Surface": "Water level", "What is shown": "Liverpool tide gauge levels from Environment Agency API"},
            {"Surface": "GIS", "What is shown": "Port assets, service area, monitoring stations and transport nodes"},
            {"Surface": "Catalogue", "What is shown": "All rank >=4 Word-document sources and their processing state"},
        ]
        st.dataframe(pd.DataFrame(surface_rows), hide_index=True, width="stretch", height=330)

    st.subheader("Latest data snapshots")
    snapshot_cols = st.columns(4)
    weekly_shipping = api_bundle.get("weekly_shipping", pd.DataFrame())
    webtris_daily = api_bundle.get("webtris_daily", pd.DataFrame())
    naptan = api_bundle.get("naptan", pd.DataFrame())
    latest_weather = weather.sort_values("timestamp").iloc[-1] if not weather.empty else None
    if not weekly_shipping.empty:
        cargo = weekly_shipping[weekly_shipping["metric"].eq("cargo_and_tanker_visits")].sort_values("week_ending")
        visits = cargo["liverpool_visits"].iloc[-1] if not cargo.empty else None
    else:
        visits = None
    snapshot_cols[0].metric("Liverpool cargo/tanker visits", format_optional_number(visits))
    if not webtris_daily.empty and "Total Volume" in webtris_daily.columns:
        peak_volume = pd.to_numeric(webtris_daily["Total Volume"], errors="coerce").max()
    else:
        peak_volume = None
    snapshot_cols[1].metric("A5036 max 15-min volume", format_optional_number(peak_volume))
    snapshot_cols[2].metric("NaPTAN local nodes", f"{len(naptan):,}" if not naptan.empty else "n/a")
    snapshot_cols[3].metric(
        "Sample weather rows",
        str(len(weather)),
        help=f"Latest sample timestamp: {latest_weather['timestamp']}" if latest_weather is not None else None,
    )


def render_gis(assets: pd.DataFrame, service_area: dict) -> None:
    st.subheader("GIS Service View")
    deck = pdk.Deck(
        map_style=BASE_MAP_STYLE,
        initial_view_state=pdk.ViewState(latitude=53.448, longitude=-3.015, zoom=11.4, pitch=35),
        layers=map_layers(assets, service_area),
        tooltip={"text": "{name}\n{asset_type}\nStatus: {status}\nOwner: {owner}"},
    )
    st.pydeck_chart(deck, width="stretch", height=520)
    st.dataframe(
        assets[["asset_type", "name", "status", "owner", "notes"]].rename(
            columns={"asset_type": "Type", "name": "Asset", "status": "Status", "owner": "Owner", "notes": "Note"}
        ),
        hide_index=True,
        width="stretch",
    )


def render_weather(weather: pd.DataFrame) -> None:
    st.subheader("Weather and Water Level Data")
    latest = weather.sort_values("timestamp").iloc[-1]
    cols = st.columns(4)
    cols[0].metric("Temperature", f"{latest['temperature_c']} C")
    cols[1].metric("Wind", f"{latest['wind_speed_mph']} mph")
    cols[2].metric("Rainfall", f"{latest['rainfall_mm']} mm")
    with st.spinner("Calling Environment Agency water-level API"):
        api_bundle = load_api_raw_bundle()
    water_levels = api_bundle.get("water_levels", pd.DataFrame())
    water_value, water_note = latest_water_level_summary(water_levels)
    cols[3].metric("Liverpool water level", water_value, help=water_note)

    chart_df = weather.melt(
        id_vars=["timestamp"],
        value_vars=["temperature_c", "wind_speed_mph", "rainfall_mm"],
        var_name="Signal",
        value_name="Value",
    )
    fig = px.line(chart_df, x="timestamp", y="Value", color="Signal", markers=True)
    st.plotly_chart(polish_chart(fig, height=360), width="stretch")

    st.subheader("Liverpool Tide Gauge Water Level")
    if water_levels.empty:
        st.info("Liverpool tide gauge readings are not available from the API right now.")
        return

    water_plot = water_levels.dropna(subset=["date_time", "value"]).copy()
    water_plot["Series"] = water_plot["station_label"].astype(str) + " | " + water_plot["unit"].astype(str)
    fig = px.line(
        water_plot,
        x="date_time",
        y="value",
        color="Series",
        markers=True,
        labels={"date_time": "Time UTC", "value": "Water level", "Series": "Gauge"},
        hover_data=["station_reference", "qualifier", "datum"],
    )
    st.plotly_chart(polish_chart(fig, height=360), width="stretch")
    st.dataframe(
        water_plot[["station_reference", "station_label", "date_time", "qualifier", "value", "unit", "datum"]]
        .sort_values("date_time", ascending=False)
        .head(40),
        hide_index=True,
        width="stretch",
    )


def render_transport(transport: pd.DataFrame) -> None:
    st.subheader("Transport Data")
    counts = transport.groupby(["severity", "status"], as_index=False).size()
    fig = px.bar(counts, x="severity", y="size", color="status", labels={"size": "Events", "severity": "Severity"})
    st.plotly_chart(polish_chart(fig, height=320), width="stretch")
    st.dataframe(
        transport[["event_type", "location", "severity", "status", "reported_at", "owner", "impact"]].rename(
            columns={
                "event_type": "Type",
                "location": "Location",
                "severity": "Severity",
                "status": "Status",
                "reported_at": "Reported",
                "owner": "Owner",
                "impact": "Impact",
            }
        ),
        hide_index=True,
        width="stretch",
    )


def render_data_status(sources: pd.DataFrame, catalog: pd.DataFrame) -> None:
    with st.spinner("Checking data connectors"):
        api_bundle = load_api_raw_bundle()
    api_status = api_bundle["status"]

    st.subheader("Data Connection Status")
    if not api_status.empty:
        connected = api_status[api_status["status"].eq("api_connected")]
        cols = st.columns(4)
        cols[0].metric("Connected feeds", f"{len(connected)}/{len(api_status)}")
        cols[1].metric("Records visible", f"{pd.to_numeric(connected['records'], errors='coerce').fillna(0).sum():,.0f}")
        cols[2].metric("Pending access", str(len(api_status[api_status["status"].str.contains("requires", na=False)])))
        cols[3].metric("Domains covered", str(api_status["domain"].nunique()))

        left, right = st.columns([0.85, 1.35])
        with left:
            status_chart = api_status.copy()
            status_chart["Connector state"] = status_chart["status"].map(CONNECTOR_STATUS_LABELS).fillna(status_chart["status"])
            status_counts = status_chart.groupby(["Connector state"], as_index=False).size().sort_values("size", ascending=True)
            fig = px.bar(
                status_counts,
                x="size",
                y="Connector state",
                orientation="h",
                color="Connector state",
                text="size",
                labels={"size": "Sources", "Connector state": ""},
                color_discrete_map=CONNECTOR_STATUS_COLORS,
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(polish_chart(fig, height=300), width="stretch")
        with right:
            table = api_status.rename(
                columns={
                    "connector_id": "Connector",
                    "source": "Source",
                    "domain": "Domain",
                    "status": "Status",
                    "records": "Records",
                    "api_endpoint": "API endpoint",
                    "last_call_utc": "Last API call",
                    "access_note": "Access note",
                }
            )
            table["Status"] = table["Status"].map(CONNECTOR_STATUS_LABELS).fillna(table["Status"])
            st.dataframe(
                table[["Connector", "Source", "Domain", "Status", "Records", "Last API call", "Access note"]],
                hide_index=True,
                width="stretch",
            )

    st.subheader("Local Source Register")
    source_register = sources.rename(
        columns={
            "source_name": "Source",
            "source_type": "Type",
            "owner": "Owner",
            "update_cadence": "Cadence",
            "last_update": "Last update",
            "status": "Status",
            "access_level": "Access",
            "connection_mode": "Connection",
        }
    )[["Source", "Type", "Owner", "Cadence", "Last update", "Status", "Access", "Connection"]]
    st.dataframe(source_register, hide_index=True, width="stretch")

    st.subheader("Rank >=4 Word-source processing matrix")
    processing = build_high_score_processing_matrix(catalog, api_status)
    if processing.empty:
        st.info("No high-score Word-document source matrix is available.")
    else:
        state_counts = processing.groupby("Processing state", as_index=False).size().sort_values("size")
        fig = px.bar(
            state_counts,
            x="size",
            y="Processing state",
            orientation="h",
            text="size",
            labels={"size": "Sources", "Processing state": ""},
            color="Processing state",
            color_discrete_map=PROCESS_STATE_COLORS,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(polish_chart(fig, height=310), width="stretch")
        st.dataframe(
            processing[
                [
                    "Source ID",
                    "Source",
                    "Rank",
                    "Domain",
                    "Type",
                    "Processing state",
                    "Live status",
                    "Records",
                    "Dashboard surface",
                    "Next step",
                ]
            ],
            hide_index=True,
            width="stretch",
            height=430,
        )


def render_dataset_catalog(catalog: pd.DataFrame) -> None:
    st.subheader("High-score Dataset Catalogue")
    st.caption("Rank >= 4/5 candidate sources extracted from the CRDT available-datasets document.")

    if catalog.empty:
        st.warning("No high-score catalog is available yet. Run scripts/extract_docx_high_score_sources.py first.")
        return

    domains = sorted(catalog["domain"].dropna().unique().tolist())
    source_types = sorted(catalog["source_type"].dropna().unique().tolist())
    access_levels = sorted(catalog["access_level"].dropna().unique().tolist())

    controls = st.columns([0.9, 1.4, 1.2, 1.2])
    with controls[0]:
        min_rank = st.slider("Minimum rank", min_value=4, max_value=5, value=4, step=1)
    with controls[1]:
        selected_domains = st.multiselect("Domain", domains, placeholder="All domains")
    with controls[2]:
        selected_types = st.multiselect("Source type", source_types, placeholder="All types")
    with controls[3]:
        selected_access = st.multiselect("Access level", access_levels, placeholder="All access levels")

    active_domains = selected_domains or domains
    active_types = selected_types or source_types
    active_access = selected_access or access_levels

    filtered = catalog[
        catalog["rank"].ge(min_rank)
        & catalog["domain"].isin(active_domains)
        & catalog["source_type"].isin(active_types)
        & catalog["access_level"].isin(active_access)
    ].copy()

    if filtered.empty:
        st.info("No sources match the current filters.")
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("Selected sources", str(len(filtered)))
    metric_cols[1].metric("Rank-5 sources", str(len(filtered[filtered["rank"].eq(5)])))
    metric_cols[2].metric("API/GIS listed", str(len(filtered[filtered["source_type"].isin(["API", "GIS data"])])))
    metric_cols[3].metric("L2/internal sources", str(len(filtered[filtered["access_level"].str.contains("L2", na=False)])))

    with st.spinner("Checking processing state for selected sources"):
        api_status = load_api_raw_bundle().get("status", pd.DataFrame())
    processing = build_high_score_processing_matrix(catalog, api_status)
    selected_processing = processing[processing["Source ID"].isin(filtered["source_id"].astype(str))].copy()

    left, right = st.columns([1.1, 1])
    with left:
        chart_df = filtered.groupby(["domain", "rank"], dropna=False, as_index=False).size()
        fig = px.bar(
            chart_df,
            x="domain",
            y="size",
            color="rank",
            barmode="group",
            labels={"domain": "Domain", "size": "Sources", "rank": "Rank"},
        )
        st.plotly_chart(polish_chart(fig, height=330), width="stretch")
    with right:
        access_df = filtered.groupby(["access_level"], dropna=False, as_index=False).size()
        access_fig = px.bar(
            access_df,
            x="size",
            y="access_level",
            orientation="h",
            labels={"size": "Sources", "access_level": "Access level"},
        )
        st.plotly_chart(polish_chart(access_fig, height=330), width="stretch")

    if not selected_processing.empty:
        st.subheader("Processing state for selected sources")
        compact_processing = selected_processing[
            ["Source ID", "Source", "Processing state", "Live status", "Records", "Dashboard surface", "Next step"]
        ].copy()
        st.dataframe(compact_processing, hide_index=True, width="stretch", height=340)

    display_cols = [
        "source_id",
        "title",
        "rank",
        "data_quality",
        "domain",
        "source_type",
        "format",
        "period",
        "access_level",
        "connection_mode",
        "dashboard_use",
        "url",
    ]
    display = filtered[display_cols].rename(
            columns={
                "source_id": "Source ID",
                "title": "Source",
                "rank": "Rank",
                "data_quality": "Data quality",
                "domain": "Domain",
                "source_type": "Type",
                "format": "Format",
                "period": "Period",
                "access_level": "Access",
                "connection_mode": "Connection",
                "dashboard_use": "Dashboard use",
                "url": "URL",
            }
    )
    if not selected_processing.empty:
        display = display.merge(
            selected_processing[["Source ID", "Processing state", "Live status", "Records", "Next step"]],
            how="left",
            on="Source ID",
        )
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        height=430,
    )

    with st.expander("Selected source details", expanded=False):
        selected_title = st.selectbox("Source", filtered["title"].tolist())
        row = filtered[filtered["title"].eq(selected_title)].iloc[0]
        st.write(f"**Category:** {row['category']}")
        st.write(f"**Brief description:** {row['brief_description'] or 'Not provided in the Word file.'}")
        st.write(f"**Highlighted comment:** {row['highlighted_comment'] or 'Not provided in the Word file.'}")
        st.write(f"**Recommended dashboard use:** {row['dashboard_use']}")


def render_raw_data() -> None:
    with st.spinner("Calling open data APIs"):
        bundle = load_api_raw_bundle()

    status = bundle["status"]
    port_traffic = bundle["port_traffic"]
    ship_arrivals = bundle["ship_arrivals"]
    weekly_shipping = bundle["weekly_shipping"]
    ea_stations = bundle["ea_stations"]
    ea_readings = bundle["ea_readings"]
    water_levels = bundle["water_levels"]
    naptan = bundle["naptan"]
    webtris_sites = bundle["webtris_sites"]
    webtris_daily = bundle["webtris_daily"]

    st.subheader("API and Remote-file Data")
    st.caption("Open sources are queried through API or remote file endpoints and cached by Streamlit; no manual download/upload step is used.")

    if status.empty:
        st.warning("No API connector output is available.")
        return

    connected = status[status["status"].eq("api_connected")]
    deferred = status[~status["status"].eq("api_connected")]
    raw_records = pd.to_numeric(connected["records"], errors="coerce").fillna(0).sum()
    metric_cols = st.columns(4)
    metric_cols[0].metric("Connected feeds", str(len(connected)))
    metric_cols[1].metric("Live records", f"{raw_records:,.0f}")
    metric_cols[2].metric("Domains", str(status["domain"].nunique()))
    metric_cols[3].metric("Deferred sources", str(len(deferred)))

    raw_view = st.radio(
        "Raw data view",
        ["API Status", "Port / Maritime", "Water Level", "Weather / Monitoring", "Hinterland APIs"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if raw_view == "API Status":
        status_chart = status.copy()
        status_chart["Connector state"] = status_chart["status"].map(CONNECTOR_STATUS_LABELS).fillna(status_chart["status"])
        status_counts = status_chart.groupby(["Connector state"], as_index=False).size().sort_values("size", ascending=True)
        fig = px.bar(
            status_counts,
            x="size",
            y="Connector state",
            orientation="h",
            labels={"size": "Sources", "Connector state": ""},
            color="Connector state",
            text="size",
            color_discrete_map=CONNECTOR_STATUS_COLORS,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(polish_chart(fig, height=300), width="stretch")

        table = status.rename(
            columns={
                "connector_id": "Connector",
                "source": "Source",
                "domain": "Domain",
                "status": "Status",
                "records": "Records",
                "api_endpoint": "API endpoint",
                "last_call_utc": "Last API call",
                "access_note": "Access note",
            }
        )
        table["Status"] = table["Status"].map(CONNECTOR_STATUS_LABELS).fillna(table["Status"])
        st.dataframe(
            table[["Connector", "Source", "Domain", "Status", "Records", "Last API call", "Access note"]],
            hide_index=True,
            width="stretch",
            height=360,
            column_config={
                "Connector": st.column_config.TextColumn(width="medium"),
                "Source": st.column_config.TextColumn(width="large"),
                "Domain": st.column_config.TextColumn(width="medium"),
                "Status": st.column_config.TextColumn(width="small"),
                "Records": st.column_config.NumberColumn(width="small"),
                "Last API call": st.column_config.TextColumn(width="medium"),
                "Access note": st.column_config.TextColumn(width="large"),
            },
        )

    elif raw_view == "Port / Maritime":
        left, right = st.columns([1.1, 1])
        with left:
            if not port_traffic.empty:
                fig = px.line(
                    port_traffic,
                    x="year",
                    y="tonnage_thousand_tonnes",
                    color="port",
                    markers=True,
                    labels={"year": "Year", "tonnage_thousand_tonnes": "Thousand tonnes", "port": "Port"},
                )
                st.plotly_chart(polish_chart(fig, height=330), width="stretch")
            else:
                st.info("DfT port traffic data is not available yet.")
        with right:
            if not weekly_shipping.empty:
                metric_choice = st.selectbox(
                    "Weekly shipping metric",
                    weekly_shipping["metric"].dropna().unique().tolist(),
                    index=0,
                )
                weekly_view = weekly_shipping[weekly_shipping["metric"].eq(metric_choice)].tail(60)
                fig = px.line(
                    weekly_view,
                    x="week_ending",
                    y="liverpool_visits",
                    markers=True,
                    labels={"week_ending": "Week ending", "liverpool_visits": "Liverpool visits"},
                )
                st.plotly_chart(polish_chart(fig, height=330), width="stretch")
            else:
                st.info("ONS weekly shipping data is not available yet.")

        if not ship_arrivals.empty:
            arrivals_summary = ship_arrivals.groupby(["Year", "Ship type"], as_index=False)["Number"].sum()
            fig = px.line(
                arrivals_summary,
                x="Year",
                y="Number",
                color="Ship type",
                labels={"Number": "Arrivals"},
            )
            st.plotly_chart(polish_chart(fig, height=330), width="stretch")
            st.dataframe(ship_arrivals.tail(40), hide_index=True, width="stretch")

    elif raw_view == "Water Level":
        water_value, water_note = latest_water_level_summary(water_levels)
        metric_cols = st.columns(3)
        metric_cols[0].metric("Latest Liverpool level", water_value, help=water_note)
        metric_cols[1].metric("Water-level rows", f"{len(water_levels):,}")
        metric_cols[2].metric("Gauge series", str(water_levels["station_reference"].nunique()) if not water_levels.empty else "0")

        if water_levels.empty:
            st.info("Liverpool tide gauge water-level data is not available yet.")
        else:
            water_plot = water_levels.dropna(subset=["date_time", "value"]).copy()
            water_plot["Series"] = water_plot["station_label"].astype(str) + " | " + water_plot["unit"].astype(str)
            fig = px.line(
                water_plot,
                x="date_time",
                y="value",
                color="Series",
                markers=True,
                labels={"date_time": "Time UTC", "value": "Water level", "Series": "Gauge"},
                hover_data=["station_reference", "qualifier", "datum"],
            )
            st.plotly_chart(polish_chart(fig, height=360), width="stretch")

            if {"lat", "lon"}.issubset(water_levels.columns):
                map_df = water_levels.dropna(subset=["lat", "lon"]).drop_duplicates("station_reference")
                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=map_df,
                    get_position="[lon, lat]",
                    get_radius=160,
                    get_fill_color=[31, 91, 163, 190],
                    pickable=True,
                )
                deck = pdk.Deck(
                    map_style=BASE_MAP_STYLE,
                    initial_view_state=pdk.ViewState(latitude=53.448, longitude=-3.015, zoom=11.2),
                    layers=[layer],
                    tooltip={"text": "{station_label}\n{station_reference}\n{datum}"},
                )
                st.pydeck_chart(deck, width="stretch", height=330)

            st.dataframe(
                water_plot[
                    ["station_reference", "station_label", "date_time", "parameter", "qualifier", "value", "unit", "datum"]
                ]
                .sort_values("date_time", ascending=False)
                .head(80),
                hide_index=True,
                width="stretch",
                height=360,
            )

    elif raw_view == "Weather / Monitoring":
        map_cols = st.columns([1.2, 1])
        with map_cols[0]:
            if not ea_stations.empty and {"lat", "lon"}.issubset(ea_stations.columns):
                station_map = ea_stations.dropna(subset=["lat", "lon"]).copy()
                station_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=station_map,
                    get_position="[lon, lat]",
                    get_radius=95,
                    get_fill_color=[44, 123, 182, 170],
                    pickable=True,
                )
                deck = pdk.Deck(
                    map_style=BASE_MAP_STYLE,
                    initial_view_state=pdk.ViewState(latitude=53.448, longitude=-3.015, zoom=9.2),
                    layers=[station_layer],
                    tooltip={"text": "{label}\n{river_name}\n{status}\n{distance_km} km"},
                )
                st.pydeck_chart(deck, width="stretch", height=430)
                status_counts = ea_stations.groupby(["status"], as_index=False).size()
                fig = px.bar(
                    status_counts,
                    x="status",
                    y="size",
                    color="status",
                    labels={"status": "Station status", "size": "Stations"},
                )
                st.plotly_chart(polish_chart(fig, height=240), width="stretch")
            else:
                st.info("Environment Agency station data is not available yet.")
        with map_cols[1]:
            if not ea_readings.empty:
                st.metric("Latest readings", str(len(ea_readings)))
                st.dataframe(
                    ea_readings[["station_label", "date_time", "parameter", "qualifier", "value", "unit"]].head(30),
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("Latest reading data is not available yet.")

    elif raw_view == "Hinterland APIs":
        left, right = st.columns([1.15, 1])
        with left:
            if not webtris_daily.empty and "timestamp" in webtris_daily:
                site_options = sorted(webtris_daily["Site Name"].dropna().astype(str).unique().tolist())
                selected_sites = st.multiselect("WebTRIS site", site_options, default=site_options[:2])
                flow_view = webtris_daily[webtris_daily["Site Name"].astype(str).isin(selected_sites)].copy()
                fig = px.line(
                    flow_view,
                    x="timestamp",
                    y="Total Volume",
                    color="Site Name",
                    labels={"timestamp": "Time", "Total Volume": "15-min traffic volume"},
                )
                st.plotly_chart(polish_chart(fig, height=340), width="stretch")
            else:
                st.info("WebTRIS traffic data is not available yet.")
        with right:
            if not naptan.empty:
                st.metric("NaPTAN local nodes", f"{len(naptan):,}")
                if "StopType" in naptan.columns:
                    stop_counts = naptan.groupby(["StopType"], dropna=False, as_index=False).size().sort_values("size", ascending=False)
                    fig = px.bar(
                        stop_counts.head(8),
                        x="size",
                        y="StopType",
                        orientation="h",
                        labels={"size": "Nodes", "StopType": "Stop type"},
                    )
                    st.plotly_chart(polish_chart(fig, height=270), width="stretch")
                st.dataframe(naptan.head(20), hide_index=True, width="stretch")
            else:
                st.info("NaPTAN data is not available yet.")

        if not webtris_sites.empty or not naptan.empty:
            st.subheader("Transport Access Spatial Coverage")
            layers: list[pdk.Layer] = []
            if not naptan.empty and {"Latitude", "Longitude"}.issubset(naptan.columns):
                naptan_points = naptan.dropna(subset=["Latitude", "Longitude"]).copy()
                if len(naptan_points) > 1600:
                    naptan_points = naptan_points.sample(1600, random_state=7)
                naptan_points["tooltip_name"] = naptan_points["CommonName"].fillna("Transport node")
                naptan_points["tooltip_type"] = "NaPTAN node"
                layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=naptan_points,
                        get_position="[Longitude, Latitude]",
                        get_radius=38,
                        get_fill_color=[44, 123, 182, 120],
                        pickable=True,
                    )
                )
            if not webtris_sites.empty and {"lat", "lon"}.issubset(webtris_sites.columns):
                traffic_points = webtris_sites.dropna(subset=["lat", "lon"]).copy()
                traffic_points["tooltip_name"] = traffic_points["description"].fillna("WebTRIS site")
                traffic_points["tooltip_type"] = "WebTRIS site"
                layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=traffic_points,
                        get_position="[lon, lat]",
                        get_radius=135,
                        get_fill_color=[194, 65, 12, 180],
                        pickable=True,
                    )
                )
            deck = pdk.Deck(
                map_style=BASE_MAP_STYLE,
                initial_view_state=pdk.ViewState(latitude=53.448, longitude=-3.015, zoom=10.1),
                layers=layers,
                tooltip={"text": "{tooltip_name}\n{tooltip_type}\n{distance_km} km"},
            )
            st.pydeck_chart(deck, width="stretch", height=460)

        if not webtris_sites.empty:
            st.dataframe(
                webtris_sites[["site_id", "description", "status", "lat", "lon", "distance_km"]].head(40),
                hide_index=True,
                width="stretch",
            )


def main() -> None:
    apply_professional_theme()
    if not require_dashboard_authorisation():
        st.stop()

    partners = load_csv("partners.csv")
    assets = load_csv("assets.csv")
    weather = load_csv("weather_observations.csv", parse_dates=["timestamp"])
    transport = load_csv("transport_events.csv", parse_dates=["reported_at"])
    sources = load_csv("data_sources.csv", parse_dates=["last_update"])
    catalog = load_high_score_catalog()
    service_area = load_service_area()

    st.sidebar.title("CRDT-Port")
    if st.sidebar.button("Lock dashboard"):
        st.session_state["dashboard_authorised"] = False
        st.rerun()

    partner_name = st.sidebar.selectbox("Partner", partners["partner_name"].tolist(), index=0)
    partner = partners[partners["partner_name"].eq(partner_name)].iloc[0]
    render_access_banner(partner)
    views = allowed_views(partner)

    st.title("CRDT-Port Data Visualisation Dashboard")

    available_pages = []
    if "overview" in views:
        available_pages.append("Overview")
    if "gis" in views:
        available_pages.append("GIS")
    if "weather" in views:
        available_pages.append("Weather")
    if "transport" in views:
        available_pages.append("Transport")
    if "dataset_catalog" in views:
        available_pages.append("Dataset Catalogue")
    if "raw_data" in views:
        available_pages.append("Raw Data")
    if "data_status" in views:
        available_pages.append("Data Status")

    st.sidebar.divider()
    page = st.sidebar.radio("View", available_pages, index=0, label_visibility="collapsed")

    if page == "Overview":
        render_overview(assets, weather, transport, sources, catalog)
    elif page == "GIS":
        render_gis(assets, service_area)
    elif page == "Weather":
        render_weather(weather)
    elif page == "Transport":
        render_transport(transport)
    elif page == "Dataset Catalogue":
        render_dataset_catalog(catalog)
    elif page == "Raw Data":
        render_raw_data()
    elif page == "Data Status":
        render_data_status(sources, catalog)

    st.sidebar.divider()
    if st.sidebar.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
