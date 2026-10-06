"""Archived research evidence and observed-stream replay, separate from forecasting."""
import json
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_quality import quality_table
from monitoring_views import chart_style, select_water_series, selected_dates, utc_label, water_level_figure
from workspace_data import report_archive, water_chart_series, window_features

DATA = Path(__file__).parent / "data"
GROUP_LABELS = {
    "context_only": "Temporal and site context", "time_only": "Cyclic time context", "station_only": "Station identity",
    "physical_shape_only": "Water-window shape", "physical_level_only": "Water-window level",
    "physical_all_no_context": "All water-window predictors", "hybrid_top10": "Hybrid ten-feature signature", "full": "All candidate predictors",
}


def playback_figure(data):
    def traces(checkpoint):
        past = data.iloc[:checkpoint + 1]
        context = water_chart_series(past)
        window = water_chart_series(past.iloc[-8:])
        return [go.Scatter(x=context.index, y=context.values, mode="lines", name="Observed history", connectgaps=False,
                    line=dict(color="#9baeb5", width=1.5)),
                go.Scatter(x=window.index, y=window.values, mode="lines+markers", name="Latest eight observations", connectgaps=False,
                    line=dict(color="#168879", width=3), marker=dict(size=5))]
    first = min(7, len(data) - 1)
    step = max(1, math.ceil((len(data) - first) / 95))
    checkpoints = sorted(set(list(range(first, len(data), step)) + [len(data) - 1]))
    fig = go.Figure(data=traces(first), frames=[go.Frame(name=str(i), data=traces(i)) for i in checkpoints])
    fig.update_layout(updatemenus=[dict(type="buttons", direction="left", x=0, y=-0.15, buttons=[
        dict(label="Play observed history", method="animate", args=[None, {"frame": {"duration": 300, "redraw": True}, "transition": {"duration": 0}, "fromcurrent": True}]),
        dict(label="Pause", method="animate", args=[[None], {"mode": "immediate", "frame": {"duration": 0, "redraw": False}}])])])
    fig.update_xaxes(title="Observation time (UTC)")
    fig.update_yaxes(title=f"Water level ({data.iloc[-1]['unit']})")
    fig = chart_style(fig, 430)
    fig.update_layout(margin=dict(l=15, r=20, t=30, b=90))
    return fig


def render_replay(bundle):
    st.caption("OBSERVATION REPLAY / NO MODEL INFERENCE")
    water = bundle.get("water_levels", pd.DataFrame())
    if water.empty:
        st.info("No water observations returned for replay. Choose recent dates; the live EA endpoint is not the historical warning archive.")
        return
    series = select_water_series(water, label="Replay gauge and vertical reference", key="replay_gauge")
    if series.empty:
        st.warning("No valid observation timestamps in this series.")
        return
    mode = st.radio("Replay mode", ["Window inspection", "Timeline playback"], horizontal=True, key="replay_mode")
    if mode == "Timeline playback":
        st.plotly_chart(playback_figure(series), width="stretch", key="timeline_playback")
        st.caption("Playback advances through at most 96 observed checkpoints. No forecast or warning score is generated; use Window inspection to inspect every checkpoint and its feature values.")
        return
    if len(series) > 1:
        checkpoint = st.slider("Replay checkpoint", min_value=0, max_value=len(series) - 1, value=len(series) - 1,
            key=f"replay_checkpoint_{series.iloc[0]['station_reference']}")
    else:
        checkpoint = 0
    past = series.iloc[:checkpoint + 1].reset_index(drop=True)
    window = past.iloc[-8:].reset_index(drop=True)
    features = window_features(window)
    row = past.iloc[-1]
    st.markdown(f"**Checkpoint {checkpoint + 1} / {len(series)}: {utc_label(row['date_time'])}**")
    st.caption("Eight consecutive 15-minute observations span 105 minutes, from t-7 to t. Only observations at or before this checkpoint enter the diagnostic window.")
    fig = water_level_figure(past, 370)
    highlighted = water_chart_series(window)
    fig.add_trace(go.Scatter(x=highlighted.index, y=highlighted.values, mode="lines+markers", name="Diagnostic window",
        connectgaps=False, line=dict(color="#346396", width=3), marker=dict(size=5)))
    if len(window) > 1:
        fig.add_vrect(x0=window.iloc[0]["date_time"], x1=row["date_time"], fillcolor="#346396", opacity=0.07, line_width=0)
    st.plotly_chart(fig, width="stretch")
    if features["valid"]:
        st.success("Complete diagnostic window: eight valid observations at the expected cadence.")
        cards = st.columns(4)
        for card, label, value, unit in [
            (cards[0], "Net water-level change", features["net_change"], "m"),
            (cards[1], "Within-window range", features["range"], "m"),
            (cards[2], "Largest 15-minute change", features["max_step"], "m"),
            (cards[3], "Fitted linear trend", features["trend_per_hour"], "m/h"),
        ]:
            card.metric(label, f"{value:+.3f} {unit}" if "change" in label.lower() and label.startswith("Net") else f"{value:.3f} {unit}")
    else:
        st.warning("Incomplete, irregular or conflicting window: eight finite, consecutive 15-minute values are required. Conflicting duplicates are withheld; no feature signature is inferred from affected observations.")
    with st.expander("Window observations and calculation definitions"):
        st.dataframe(window[["date_time", "value", "unit"]], hide_index=True, width="stretch")
        st.markdown("Net change: last minus first level. Range: maximum minus minimum. Largest change: maximum absolute difference between adjacent levels. Fitted trend: least-squares level change per elapsed hour.")
    st.info("This selected-gauge replay illustrates window construction. It does not reconstruct the archived training data, apply saved models or evaluate warning-event detection.")


def render_evidence():
    summary = pd.read_csv(DATA / "research_signature_summary.csv")
    folds = pd.read_csv(DATA / "research_signature_folds.csv")
    provenance = json.loads((DATA / "research_provenance.json").read_text())
    st.caption("ARCHIVED OFFLINE EXPERIMENT / NOT CURRENT PORT RISK")
    st.markdown("**Liverpool 12-hour warning-aligned sparse learning**")
    st.write("Compare feature families under the same sparse logistic model and incident-cluster validation. These results are independent of the observation dates selected in the sidebar.")
    choices = st.multiselect("Feature families", summary["feature_group"].tolist(),
        default=["hybrid_top10", "full", "context_only", "physical_all_no_context"], format_func=GROUP_LABELS.get)
    selected = summary[summary["feature_group"].isin(choices)].copy()
    if selected.empty:
        st.info("Select at least one feature family.")
        return
    selected["Label"] = selected["feature_group"].map(GROUP_LABELS)
    ap = go.Figure(go.Scatter(x=selected["test_ap_mean"], y=selected["Label"], mode="markers",
        marker=dict(size=10, color="#346396"), error_x=dict(type="data", array=selected["test_ap_std"], color="#346396")))
    f2 = go.Figure(go.Scatter(x=selected["sparse_f2_mean"], y=selected["Label"], mode="markers",
        marker=dict(size=10, color="#168879"), error_x=dict(type="data", array=selected["sparse_f2_std"], color="#168879")))
    for fig, title in [(ap, "Average precision"), (f2, "Validation-threshold F2")]:
        fig.update_xaxes(title=title, range=[0, 1])
        fig.update_yaxes(autorange="reversed", title="")
        st.plotly_chart(chart_style(fig, max(250, len(selected) * 50)), width="stretch")
    st.caption("Points are four-fold means; whiskers are sample SD across folds, not confidence intervals. Four independent warning-event clusters limit generalization claims.")
    display = selected[["Label", "n_features_mean", "test_ap_mean", "sparse_f2_mean", "event_recall_mean", "false_alarms_per_day_mean"]].rename(columns={
        "n_features_mean": "Predictors", "test_ap_mean": "AP", "sparse_f2_mean": "Validation-threshold F2", "event_recall_mean": "Event recall",
        "false_alarms_per_day_mean": "False-positive windows / represented day"})
    st.dataframe(display.round(3), hide_index=True, width="stretch")
    with st.expander("How to read these metrics", expanded=False):
        st.markdown("**AP (average precision):** summarizes positive-label ranking across precision-recall thresholds; higher is better.\n\n"
            "**Validation-threshold F2:** the usual F2 formula, with recall weighted four times as strongly as precision. The threshold is selected on validation data, not the held-out cluster. 'Sparse-F2' in the source report describes that threshold policy, not a different formula.\n\n"
            "**Event recall:** fraction of labelled warning events detected under the experiment's window-level rule. It is not the same as episode-policy hit rate.\n\n"
            "**False-positive windows per represented day:** non-warning rows above the threshold, divided by days represented in the test data. Consecutive rows are not merged into alert episodes.")
    with st.expander("Per-cluster results and provenance"):
        st.dataframe(folds[folds["feature_group"].isin(choices)].rename(columns={"feature_group": "Feature group"}), hide_index=True, width="stretch")
        st.json(provenance)
        st.download_button("Download archived experiment summary", summary.to_csv(index=False).encode(), "research_signature_summary.csv", "text/csv")


def render_research_workspace(bundle):
    st.subheader("Research and historical replay")
    st.caption("Inspect observed windows or explore verified archived experiments. Neither view provides a real-time flood forecast.")
    replay_tab, evidence_tab = st.tabs(["Historical replay", "Experiment evidence"])
    with replay_tab:
        render_replay(bundle)
    with evidence_tab:
        render_evidence()


def render_report_centre(bundle, weather, transport):
    st.subheader("Observation report centre")
    start, end = selected_dates()
    table = quality_table(bundle, weather, transport)
    water = bundle.get("water_levels", pd.DataFrame())
    traffic = bundle.get("webtris_daily", pd.DataFrame())
    cards = st.columns(3)
    cards[0].metric("Water rows", len(water))
    cards[1].metric("Traffic rows", len(traffic))
    cards[2].metric("Observation series", int(table["Kind"].eq("Observation").sum()))
    st.markdown(f"**Selected dates:** {start} to {end}")
    st.write("Download a self-contained HTML report, observation CSVs, a quality register and source/timestamp metadata in one ZIP. Each water reference is plotted separately.")
    st.caption("The report is an observation snapshot, not a flood forecast. Water dates use UTC; traffic preserves unverified source timestamps. Demonstration records are described in the quality register, not exported as live observations.")
    with st.expander("Report data-health preview", expanded=True):
        st.dataframe(table[["Source", "Kind", "State", "Records", "Latest UTC"]], hide_index=True, width="stretch")
    payload = report_archive(bundle, table, start, end)
    st.download_button("Download observation report ZIP", payload, f"CRDT_Port_report_{start}_{end}.zip", "application/zip", type="primary")
    st.info("Collection failures and missing coverage remain in the report. A successful export does not establish complete monitoring coverage or safe operating conditions.")
