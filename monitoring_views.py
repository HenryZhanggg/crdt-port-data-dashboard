from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pydeck as pdk
import streamlit as st

from data_quality import compatibility, filter_dates, observation_graph, quality_table, validate_observations
from workspace_data import clean_water_series, quality_findings, water_chart_series


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


def select_water_series(water, label="Gauge and vertical reference", key="water_series"):
    water = water.copy()
    water["_series_key"] = water["station_reference"].astype(str) + "|" + water["unit"].astype(str) + "|" + water["datum_uri"].fillna("").astype(str)
    options = water["_series_key"].unique().tolist()
    labels = {name: f"{group.iloc[0]['station_reference']} | {group.iloc[0]['unit']} | {group.iloc[0]['datum']}" for name, group in water.groupby("_series_key", sort=False)}
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    selected = st.selectbox(label, options, format_func=labels.get, key=key)
    return clean_water_series(water[water["_series_key"].eq(selected)].drop(columns="_series_key"))


def water_level_figure(chosen, height=350):
    row = chosen.iloc[-1]
    chart_rows = water_chart_series(chosen)
    fig = go.Figure(go.Scatter(x=chart_rows.index, y=chart_rows.values, mode="lines",
        connectgaps=False, line=dict(color="#168879", width=2.5), name="Observed water level"))
    elapsed = chosen["date_time"].diff()
    gaps = [dict(type="rect", xref="x", yref="y domain", y0=0, y1=1,
        x0=chosen.loc[i - 1, "date_time"] + pd.Timedelta(minutes=15), x1=chosen.loc[i, "date_time"],
        fillcolor="#78879a", opacity=0.12, line_width=0, layer="below")
        for i in chosen.index[elapsed.gt(pd.Timedelta(minutes=15))]]
    fig.update_layout(shapes=gaps)
    fig.update_xaxes(title="Observation time (UTC)")
    fig.update_yaxes(title=f"Water level ({row['unit']})")
    return chart_style(fig, height)


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
    st.markdown('<div class="monitor-hero"><div class="eyebrow">LIVERPOOL / MONITORING WORKSPACE</div>'
                '<h2>Liverpool monitoring and data quality</h2>'
                '<p>Explore monitoring locations, inspect observations and review data health.</p></div>', unsafe_allow_html=True)
    observed = table[table["Kind"].eq("Observation")]
    issues = quality_findings(observed)
    cards = st.columns(4)
    cards[0].metric("Fresh / checked streams", f"{int(observed['State'].eq('Current').sum())} / {len(observed)}", help="Includes a missing-feed placeholder when no observations return. Freshness is not flood safety. Water: 60 minutes; traffic: 180 minutes only after timezone verification.")
    cards[1].metric("Feeds retrieved by this view", connected, help="Only water and traffic are requested on the monitoring home; this is not a health check of every catalogue source.")
    cards[2].metric("Data-health findings", len(issues), help="Missing, stale or unverifiable observations. These are not flood warnings.")
    cards[3].metric("Water observations", len(water))
    left, right = st.columns([1.45, 1])
    with left:
        st.subheader("Monitoring locations")
        selected = render_monitoring_map(bundle, assets, service_area, compact=True)
    with right:
        st.subheader("Water-gauge detail")
        if water.empty:
            state_badge("Unavailable", "No water observations returned for these dates.")
            st.info("Check selected dates and source status. An empty response does not prove a sensor outage.")
        else:
            if selected and selected.get("kind") == "Water":
                identity = f"{selected['station_reference']}|{selected['unit']}|{selected['datum_uri']}"
                if st.session_state.get("overview_map_focus") != identity:
                    st.session_state["overview_gauge"] = identity
                    st.session_state["overview_map_focus"] = identity
            chosen = select_water_series(water, label="Overview gauge", key="overview_gauge")
            if not chosen.empty:
                row = chosen.iloc[-1]
                quality = quality_table({"water_levels": chosen}, pd.DataFrame(), pd.DataFrame()).iloc[0]
                reading = f"{row['value']:.3f}" if pd.notna(row["value"]) else "Not valid"
                st.markdown(f'<div class="stream-card"><h3>{escape(str(row["station_reference"]))} / WATER LEVEL</h3>'
                    f'<div class="reading">{reading} <small>{escape(str(row["unit"]))}</small></div>'
                    f'<small>{escape(str(row["datum"]))}<br>{utc_label(row["date_time"])}</small></div>', unsafe_allow_html=True)
                state_badge(quality["State"], "Freshness describes observation age, not flood risk.")
                st.plotly_chart(water_level_figure(chosen, 220), width="stretch", key="overview_water_chart")
                retrieved = pd.to_datetime(chosen.get("retrieved_at_utc", pd.Series(dtype=str)), utc=True, errors="coerce").max()
                st.caption(f"Collected: {utc_label(retrieved)}. No predicted tide or risk inference is shown.")
    st.subheader("Observation coverage")
    st.plotly_chart(coverage_chart(observed), width="stretch")
    st.caption("Segments show the first and last returned UTC timestamps, not uninterrupted coverage. Traffic with an unverified time basis is excluded.")
    if not issues.empty:
        with st.expander(f"Review {len(issues)} data-health findings", expanded=False):
            st.dataframe(issues, hide_index=True, width="stretch")
    with st.expander("Source timestamps and scope", expanded=False):
        st.dataframe(observed[["Source", "State", "Records", "Latest UTC", "Age (min)"]], hide_index=True, width="stretch")
        st.caption("Demonstration weather and events are excluded from the monitoring KPIs. Published shipping statistics are available under Raw Data.")


def render_monitoring_map(bundle, assets, service_area, compact=False):
    if not compact:
        st.subheader("Monitoring map")
    layers = []
    if service_area:
        layers.append(pdk.Layer("GeoJsonLayer", service_area, id="service-area", filled=True, stroked=True,
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
            datum = "" if pd.isna(row["datum_uri"]) else row["datum_uri"]
            reference = group[group["unit"].eq(row["unit"]) & group["datum_uri"].fillna("").eq(datum)]
            state = quality_table({"water_levels": reference}, pd.DataFrame(), pd.DataFrame()).iloc[0]["State"]
            color = [192, 120, 34, 230] if state != "Current" else [22, 136, 121, 230]
            map_rows.append({"lat": row.get("lat"), "lon": row.get("lon"), "name": f"Water gauge {station}",
                "station_reference": str(station), "unit": str(row.get("unit", "")), "datum_uri": str(row.get("datum_uri", "")),
                "kind": "Water", "state": state,
                "detail": f"{row.get('value')} {row.get('unit')} | {row.get('datum')} | {state}", "color": color, "radius": 120})
    traffic = bundle.get("webtris_sites", pd.DataFrame())
    if show_traffic and not traffic.empty:
        for _, row in traffic.iterrows():
            map_rows.append({"lat": row.get("lat"), "lon": row.get("lon"), "name": f"Traffic counter {row.get('site_id')}",
                "kind": "Traffic", "state": "Reference location", "site_id": str(row.get("site_id")),
                "detail": str(row.get("description", "Reference location; not a port-gate queue measurement")), "color": [52, 99, 150, 220], "radius": 85})
    if show_demo:
        for _, row in assets.iterrows():
            map_rows.append({"lat": row["lat"], "lon": row["lon"], "name": row["name"], "kind": "Demonstration", "state": "Sample", "detail": "Demonstration asset; operational state not verified", "color": [120, 135, 154, 170], "radius": 140})
    points = pd.DataFrame(map_rows)
    if not points.empty:
        points["lat"] = pd.to_numeric(points["lat"], errors="coerce")
        points["lon"] = pd.to_numeric(points["lon"], errors="coerce")
        points = points.dropna(subset=["lat", "lon"])
        layers.append(pdk.Layer("ScatterplotLayer", points, id="monitoring-points", get_position="[lon, lat]", get_radius="radius",
            get_fill_color="color", stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2, radius_min_pixels=6, pickable=True))
        if not compact:
            layers.append(pdk.Layer("TextLayer", points, id="point-labels", get_position="[lon, lat]", get_text="name", get_size=12,
                get_color=[32, 56, 71], get_pixel_offset=[0, -17], get_text_anchor="middle", get_alignment_baseline="bottom"))
    deck = pdk.Deck(map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=pdk.ViewState(latitude=53.448, longitude=-3.015, zoom=11.5, pitch=0),
        layers=layers, tooltip={"text": "{name}\n{detail}"})
    event = st.pydeck_chart(deck, width="stretch", height=440 if compact else 540,
        on_select="rerun", selection_mode="single-object", key=f"monitoring_map_{compact}")
    objects = event.get("selection", {}).get("objects", {}).get("monitoring-points", [])
    selected = objects[0] if objects else None
    st.caption("Click a monitoring point to inspect it. Teal: fresh water observations; amber: other water states; blue: traffic reference locations. Grey assets and the outline are demonstrations, not risk classifications.")
    if not compact:
        if not points.empty:
            fallback = st.selectbox("Monitoring location", points["name"].tolist(), key="map_location_fallback")
            selected = selected or points[points["name"].eq(fallback)].iloc[0].to_dict()
            st.markdown(f"**Selected location: {escape(str(selected['name']))}**")
            st.write(selected["detail"])
            st.caption(f"Source type: {selected['kind']} | State: {selected['state']} | Coordinates: {selected['lat']}, {selected['lon']}")
        with st.expander("Location register", expanded=False):
            st.dataframe(points.drop(columns=["color", "radius"], errors="ignore"), hide_index=True, width="stretch")
    return selected


def render_monitoring_weather(bundle, weather):
    start, end = selected_dates()
    water = filter_dates(bundle.get("water_levels", pd.DataFrame()), "date_time", start, end)
    st.subheader("Water-level observations")
    if water.empty:
        st.info("No water observations returned for this period. The EA live API retains about 28 days; older replay needs archive data.")
    else:
        chosen = select_water_series(water, key="explorer_gauge")
        if chosen.empty:
            st.warning("The returned series has no valid observation timestamps.")
            return
        if len(chosen) > 1:
            first, last = st.select_slider("Visible observation interval", options=chosen["date_time"].tolist(),
                value=(chosen.iloc[0]["date_time"], chosen.iloc[-1]["date_time"]),
                format_func=lambda t: t.strftime("%d %b %H:%M UTC"), key=f"explorer_interval_{chosen.iloc[0]['station_reference']}")
            chosen = chosen[chosen["date_time"].between(first, last)].reset_index(drop=True)
        row = chosen.iloc[-1]
        unit = str(row["unit"])
        state = quality_table({"water_levels": chosen}, pd.DataFrame(), pd.DataFrame()).iloc[0]
        cards = st.columns(4)
        cards[0].metric("Latest in selected period", f"{float(row['value']):.3f} {unit}")
        cards[1].metric("Observed range", f"{chosen['value'].max() - chosen['value'].min():.3f} {unit}")
        cards[2].metric("Missing 15-minute intervals", int(state["Missing intervals"]))
        rate = row["rate_per_hour"]
        cards[3].metric("Latest valid change rate", f"{rate:+.2f} m/h" if pd.notna(rate) else "Not available", help="Calculated only between consecutive 15-minute observations; gaps are not bridged.")
        state_badge(state["State"], f"{utc_label(state['Latest UTC'])} | {row['datum']}")
        level_tab, rate_tab, records_tab = st.tabs(["Observed level", "Rate of change", "Selected records"])
        with level_tab:
            st.plotly_chart(water_level_figure(chosen, 400), width="stretch")
            st.caption("Shaded gaps contain no observed values. No datum conversion, interpolation or forecast is applied.")
        with rate_tab:
            rate_fig = go.Figure(go.Bar(x=chosen["date_time"], y=chosen["rate_per_hour"], marker_color="#346396"))
            rate_fig.update_xaxes(title="Observation time (UTC)")
            rate_fig.update_yaxes(title="Observed change rate (m/h)")
            st.plotly_chart(chart_style(rate_fig, 360), width="stretch")
        with records_tab:
            st.dataframe(chosen, hide_index=True, width="stretch")
        st.download_button("Download selected observations", chosen.to_csv(index=False).encode(),
            f"water_{row['station_reference']}_{start}_{end}.csv", "text/csv")
        st.caption("Downloads use the interval filter above; plot zoom does not change the exported rows.")
        with st.expander("Source and measurement metadata"):
            st.write({name: str(row.get(name, "Not provided")) for name in ["station_reference", "unit", "datum", "datum_uri", "api_endpoint", "retrieved_at_utc"]})
    with st.expander("Illustrative weather (not a live feed)"):
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
    findings = quality_findings(table)
    st.subheader("Data-health review queue")
    st.caption("These findings concern data usability, not flood severity or operational safety.")
    if findings.empty:
        st.success("No configured data-health findings for the returned observation streams.")
    else:
        st.dataframe(findings, hide_index=True, width="stretch")
    with st.expander("Full quality register"):
        st.dataframe(table, hide_index=True, width="stretch")
    status = bundle.get("status", pd.DataFrame())
    if not status.empty and status["status"].eq("api_error").any():
        with st.expander("Collection errors"):
            st.dataframe(status.loc[status["status"].eq("api_error"), ["source", "last_call_utc", "access_note"]], hide_index=True, width="stretch")
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
