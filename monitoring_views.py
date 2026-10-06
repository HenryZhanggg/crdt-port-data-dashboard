from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pydeck as pdk
import streamlit as st

from data_quality import compatibility, filter_dates, observation_graph, quality_table, validate_observations


COLORS = {"Current": "#168879", "Stale": "#c07822", "Sample": "#78879a", "Unavailable": "#b84f51", "Unknown time": "#b84f51", "Timezone unverified": "#c07822", "Future timestamp": "#b84f51", "Historical statistics": "#466887", "Reference": "#466887"}


def chart_style(fig, height=380):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=15, r=20, t=30, b=20),
                      font=dict(family="Source Sans Pro, sans-serif", size=13, color="#203847"),
                      hovermode="x unified", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", legend_title_text="")
    fig.update_xaxes(showgrid=True, gridcolor="#e9eef1")
    fig.update_yaxes(showgrid=True, gridcolor="#e9eef1")
    return fig


def utc_label(value):
    return "Not available" if pd.isna(value) else pd.Timestamp(value).strftime("%d %b %Y %H:%M UTC")


def state_badge(state, detail=""):
    color = COLORS.get(state, "#466887")
    st.markdown(f'<div class="quality-note"><span class="quality-dot" style="background:{color}"></span>'
                f'<strong>{escape(state)}</strong><span>{escape(detail)}</span></div>', unsafe_allow_html=True)


def selected_dates():
    return st.session_state.get("monitor_start"), st.session_state.get("monitor_end")


def coverage_chart(table):
    fig = go.Figure()
    for _, row in table.dropna(subset=["First UTC", "Latest UTC"]).iterrows():
        fig.add_trace(go.Scatter(x=[row["First UTC"], row["Latest UTC"]], y=[row["Source"], row["Source"]],
            mode="lines+markers", line=dict(width=7, color=COLORS.get(row["State"], "#466887")),
            marker=dict(size=9), name=row["State"], showlegend=False,
            hovertemplate=f'{escape(row["Source"])}<br>%{{x|%d %b %Y %H:%M}} UTC<br>{escape(row["State"])}<extra></extra>'))
    fig.update_xaxes(title="Observation time (UTC)")
    fig.update_yaxes(autorange="reversed")
    return chart_style(fig, max(250, 65 * len(fig.data)))


def render_monitoring_overview(bundle, weather, transport, catalog, assets, service_area):
    table = quality_table(bundle, weather, transport)
    water = bundle.get("water_levels", pd.DataFrame())
    status = bundle.get("status", pd.DataFrame())
    connected = int(status["status"].eq("api_connected").sum()) if not status.empty else 0
    latest = pd.to_datetime(water.get("date_time", pd.Series(dtype=str)), utc=True, errors="coerce").max()
    st.markdown('<div class="monitor-hero"><div class="eyebrow">LIVERPOOL / MONITORING WORKSPACE</div>'
                '<h2>Liverpool monitoring and data quality</h2>'
                '<p>Observation times, source coverage and measurement compatibility.</p></div>', unsafe_allow_html=True)
    cards = st.columns(4)
    cards[0].metric("Current observation streams", int(table["State"].eq("Current").sum()), help="Water: <=60 minutes old; traffic: <=180 minutes. API connectivity is counted separately.")
    cards[1].metric("Connected API / file feeds", connected)
    cards[2].metric("Catalogue candidates", int(catalog["rank"].ge(4).sum()) if not catalog.empty else 0)
    cards[3].metric("Water observations", len(water))
    state_badge("Current" if table["State"].eq("Current").any() else "Unavailable", f"Latest water observation: {utc_label(latest)}")
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Observation coverage")
        st.plotly_chart(coverage_chart(table), width="stretch")
        st.caption("Only streams with a verified UTC time basis appear here. Segments show first and last returned timestamps, not uninterrupted coverage.")
    with right:
        st.subheader("Data readiness")
        readiness = table.groupby("State").size().rename("Streams").reset_index()
        fig = px.bar(readiness, x="Streams", y="State", orientation="h", text="Streams", color="State", color_discrete_map=COLORS)
        fig.update_layout(showlegend=False)
        st.plotly_chart(chart_style(fig, 320), width="stretch")
    st.subheader("Monitoring locations")
    render_monitoring_map(bundle, assets, service_area, compact=True)
    with st.expander("Sources and observation timestamps", expanded=False):
        st.dataframe(table[["Source", "Kind", "State", "Records", "Latest UTC", "Age (min)"]], hide_index=True, width="stretch")


def render_monitoring_map(bundle, assets, service_area, compact=False):
    if not compact:
        st.subheader("Monitoring map")
    layers = []
    if service_area:
        layers.append(pdk.Layer("GeoJsonLayer", service_area, filled=True, stroked=True,
            get_fill_color=[22, 136, 121, 15], get_line_color=[22, 136, 121, 140], line_width_min_pixels=2))
    controls = st.columns(3)
    show_water = controls[0].checkbox("Water gauges", value=True, key=f"map_water_{compact}")
    show_traffic = controls[1].checkbox("Traffic counters", value=True, key=f"map_traffic_{compact}")
    show_demo = controls[2].checkbox("Demonstration assets", value=False, key=f"map_demo_{compact}")
    map_rows = []
    water = bundle.get("water_levels", pd.DataFrame())
    if show_water and not water.empty:
        for station, group in water.groupby("station_reference"):
            row = group.sort_values("date_time").iloc[-1]
            map_rows.append({"lat": row.get("lat"), "lon": row.get("lon"), "name": f"Water gauge {station}",
                "detail": f"{row.get('value')} {row.get('unit')} | {row.get('datum')}", "color": [22, 136, 121, 220], "radius": 120})
    traffic = bundle.get("webtris_sites", pd.DataFrame())
    if show_traffic and not traffic.empty:
        for _, row in traffic.iterrows():
            map_rows.append({"lat": row.get("lat"), "lon": row.get("lon"), "name": f"Traffic counter {row.get('site_id')}",
                "detail": str(row.get("description", "Reference location; not a port-gate queue measurement")), "color": [52, 99, 150, 200], "radius": 85})
    if show_demo:
        for _, row in assets.iterrows():
            map_rows.append({"lat": row["lat"], "lon": row["lon"], "name": row["name"], "detail": "Demonstration asset; operational state not verified", "color": [120, 135, 154, 170], "radius": 140})
    points = pd.DataFrame(map_rows)
    if not points.empty:
        points["lat"] = pd.to_numeric(points["lat"], errors="coerce")
        points["lon"] = pd.to_numeric(points["lon"], errors="coerce")
        points = points.dropna(subset=["lat", "lon"])
        layers.append(pdk.Layer("ScatterplotLayer", points, get_position="[lon, lat]", get_radius="radius",
            get_fill_color="color", stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2, radius_min_pixels=6, pickable=True))
        if not compact:
            layers.append(pdk.Layer("TextLayer", points, get_position="[lon, lat]", get_text="name", get_size=12,
                get_color=[32, 56, 71], get_pixel_offset=[0, -17], get_text_anchor="middle", get_alignment_baseline="bottom"))
    deck = pdk.Deck(map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=pdk.ViewState(latitude=53.448, longitude=-3.015, zoom=11.5, pitch=0),
        layers=layers, tooltip={"text": "{name}\n{detail}"})
    st.pydeck_chart(deck, width="stretch", height=360 if compact else 560)
    st.caption("Teal: water gauges. Blue: traffic-counter reference locations. Grey: optional demonstration assets. The service-area outline is a demonstration boundary.")
    if not compact:
        st.dataframe(points.drop(columns=["color", "radius"], errors="ignore"), hide_index=True, width="stretch")


def render_monitoring_weather(bundle, weather):
    start, end = selected_dates()
    water = filter_dates(bundle.get("water_levels", pd.DataFrame()), "date_time", start, end)
    st.subheader("Water-level observations")
    if water.empty:
        st.info("No water observations returned for this period. The EA live API retains about 28 days; older replay needs archive data.")
    else:
        water = water.copy()
        water["series"] = water["station_reference"].astype(str) + " | " + water["unit"].astype(str) + " | " + water["datum"].astype(str)
        station = st.selectbox("Gauge and vertical reference", water["series"].unique().tolist())
        chosen = water[water["series"].eq(station)].sort_values("date_time")
        row = chosen.iloc[-1]
        unit = str(row["unit"])
        state = quality_table({"water_levels": chosen}, pd.DataFrame(), pd.DataFrame()).iloc[0]
        cards = st.columns(3)
        cards[0].metric("Latest in selected period", f"{float(row['value']):.3f} {unit}")
        cards[1].metric("Observed range", f"{chosen['value'].max() - chosen['value'].min():.3f} {unit}")
        cards[2].metric("Missing 15-minute intervals", int(state["Missing intervals"]))
        state_badge(state["State"], f"{utc_label(state['Latest UTC'])} | {row['datum']}")
        chart_rows = chosen[["date_time", "value"]].copy()
        chart_rows["date_time"] = pd.to_datetime(chart_rows["date_time"], utc=True)
        if not chart_rows.empty:
            chart_rows = chart_rows.drop_duplicates("date_time").set_index("date_time").asfreq("15min").reset_index()
        fig = px.line(chart_rows, x="date_time", y="value", markers=True, labels={"date_time": "Observation time (UTC)", "value": f"Water level ({unit})"}, color_discrete_sequence=["#168879"])
        fig.update_traces(connectgaps=False, line_width=2.5)
        fig.update_xaxes(rangeslider_visible=True)
        fig = chart_style(fig, 460)
        fig.update_layout(margin=dict(l=15, r=20, t=30, b=65))
        st.plotly_chart(fig, width="stretch")
        st.caption("One measurement reference is shown at a time. Curves break at missing 15-minute observations; no datum conversion or gap filling is applied.")
    st.subheader("Weather demonstration")
    state_badge("Sample", "Local demonstration records, not a connected weather service.")
    selected = filter_dates(weather, "timestamp", start, end)
    if selected.empty:
        st.info("The sample weather dates do not overlap the selected period.")
        if st.checkbox("Show the sample weather on its own dates", value=False):
            selected = weather.copy()
    if not selected.empty:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
            subplot_titles=["Temperature (C)", "Wind speed (mph)", "Rainfall (mm)"])
        for position, (column, label, color) in enumerate([
            ("temperature_c", "Temperature (C)", "#b87036"), ("wind_speed_mph", "Wind speed (mph)", "#346396"), ("rainfall_mm", "Rainfall (mm)", "#168879")], 1):
            fig.add_trace(go.Scatter(x=selected["timestamp"], y=selected[column], mode="lines+markers", name=label, line=dict(color=color)), row=position, col=1)
        fig.update_layout(showlegend=False)
        fig.update_xaxes(title_text="Sample timestamps; timezone unspecified", row=3, col=1)
        st.plotly_chart(chart_style(fig, 600), width="stretch")


def render_monitoring_transport(bundle, demonstration):
    start, end = selected_dates()
    frame = filter_dates(bundle.get("webtris_daily", pd.DataFrame()), "timestamp", start, end)
    st.subheader("Access-road traffic observations")
    st.caption("Traffic counts and speeds describe road counters; they do not directly measure port-gate queues.")
    if frame.empty:
        st.info("No traffic observations returned for the selected period. A connected endpoint can still return an empty or delayed series.")
    else:
        sites = frame["site_id"].dropna().astype(str).unique().tolist() if "site_id" in frame else []
        if sites:
            chosen = st.multiselect("Traffic counters", sites, default=sites[:2])
            frame = frame[frame["site_id"].astype(str).isin(chosen)].copy()
        for metric, label in [("Total Volume", "Vehicles per 15-minute interval"), ("Avg mph", "Average speed (mph)")]:
            if metric in frame and not frame.empty:
                fig = px.line(frame.sort_values("timestamp"), x="timestamp", y=metric, color="site_id" if "site_id" in frame else None, labels={"timestamp": "Source timestamp (timezone unverified)", metric: label})
                st.plotly_chart(chart_style(fig, 300), width="stretch")
        st.dataframe(frame.head(200), hide_index=True, width="stretch")
    with st.expander("Demonstration transport events"):
        state_badge("Sample", "Illustrative events, not verified live incident records.")
        selected = filter_dates(demonstration, "reported_at", start, end)
        if selected.empty:
            st.info("Demonstration events do not overlap this period.")
        else:
            st.dataframe(selected, hide_index=True, width="stretch")


def render_data_quality(bundle, weather, transport):
    st.subheader("Data quality and compatibility")
    table = quality_table(bundle, weather, transport)
    cards = st.columns(3)
    cards[0].metric("Current streams", int(table["State"].eq("Current").sum()))
    cards[1].metric("Stale observations", int(table["State"].eq("Stale").sum()))
    cards[2].metric("Demonstration streams", int(table["Kind"].eq("Sample").sum()))
    st.caption("Freshness budgets are display checks: water 60 minutes, traffic 180 minutes after timezone verification. Traffic times without verified timezone cannot be classified as current. Historical mode evaluates coverage, while age still reports age relative to now. Missing intervals are counted only within returned timestamp extents.")
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button("Download quality report", table.to_csv(index=False).encode(), "monitoring_quality.csv", "text/csv")
    water = bundle.get("water_levels", pd.DataFrame())
    st.subheader("Water-series compatibility")
    if water.empty:
        st.info("Water-series compatibility needs returned observations and measure metadata.")
        return
    series = water.groupby(["station_reference", "unit"], dropna=False).last().reset_index()
    pairs = []
    for i in range(len(series)):
        for j in range(i + 1, len(series)):
            left, right = series.iloc[i].to_dict(), series.iloc[j].to_dict()
            allowed, reason = compatibility(left, right)
            pairs.append({"Series A": f"{left['station_reference']} | {left['unit']}", "Series B": f"{right['station_reference']} | {right['unit']}", "Direct comparison": "Metadata compatible" if allowed else "Blocked", "Reason": reason})
    if pairs:
        st.dataframe(pd.DataFrame(pairs), hide_index=True, width="stretch")
    st.caption("Sharing a place name or numeric unit is insufficient. Compatible metadata still requires overlapping times, appropriate sensor calibration and measurement provenance.")
    st.subheader("Ontology observation validation")
    graph = observation_graph(water)
    conforms, issues = validate_observations(graph)
    if conforms:
        st.success(f"{len(water)} observations satisfy the configured SHACL structure checks.")
    else:
        st.warning(f"{len(issues)} constraint violations found. Inspect the evidence before combining series.")
        st.dataframe(issues, hide_index=True, width="stretch")
    st.caption("SOSA maps observations to sensors, monitored sites, properties and observation time. RDFS supplies class relationships; SHACL checks the configured required fields. These checks do not establish measurement accuracy or predict flood risk.")
    fig = go.Figure(go.Sankey(node=dict(label=["Sensor", "Observation", "Monitoring site", "Water-level property", "Vertical datum", "UTC timestamp"], color=["#346396", "#168879", "#346396", "#78879a", "#c07822", "#78879a"]),
        link=dict(source=[1, 1, 1, 1, 1], target=[0, 2, 3, 4, 5], value=[1, 1, 1, 1, 1], color="rgba(22,136,121,0.18)")))
    fig.update_layout(title="Schema relationships (illustration; link width has no quantitative meaning)")
    st.plotly_chart(chart_style(fig, 270), width="stretch")
    st.download_button("Download observation graph (Turtle)", graph.serialize(format="turtle"), "port_observations.ttl", "text/turtle")
