"""Observation diagnostics and portable reports; no prediction or gap filling."""
from datetime import datetime, timezone
from html import escape
from io import BytesIO
import json
import zipfile

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from data_quality import filter_dates


def clean_water_series(frame):
    result = frame.copy()
    reference = [c for c in ["station_reference", "unit", "datum_uri"] if c in result]
    if reference and len(result[reference].drop_duplicates()) > 1:
        raise ValueError("Choose one gauge and measurement reference before calculating changes.")
    if result.empty:
        return result.assign(rate_per_hour=pd.Series(dtype=float))
    result["date_time"] = pd.to_datetime(result["date_time"], utc=True, errors="coerce")
    result["value"] = pd.to_numeric(result["value"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    result = result.dropna(subset=["date_time"]).sort_values("date_time", kind="stable")
    conflicts = result.groupby("date_time")["value"].transform("nunique", dropna=False).gt(1)
    result["duplicate_conflict"] = conflicts | result.get("duplicate_conflict", False)
    result.loc[result["duplicate_conflict"], "value"] = np.nan
    result = result.drop_duplicates("date_time", keep="last").reset_index(drop=True)
    elapsed = result["date_time"].diff()
    result["rate_per_hour"] = (result["value"].diff() / elapsed.dt.total_seconds().div(3600)).where(elapsed.eq(pd.Timedelta(minutes=15)))
    return result


def water_chart_series(frame):
    observed = frame.set_index("date_time")["value"]
    grid = pd.date_range(observed.index.min(), observed.index.max(), freq="15min")
    # Insert missing grid points without dropping observations off the expected grid.
    return observed.reindex(observed.index.union(grid).sort_values())


def window_features(window):
    times = pd.to_datetime(window["date_time"], utc=True, errors="coerce")
    values = pd.to_numeric(window["value"], errors="coerce")
    span = (times.iloc[-1] - times.iloc[0]).total_seconds() / 60 if len(times) > 1 else 0
    valid = len(window) == 8 and times.notna().all() and np.isfinite(values).all() and times.diff().iloc[1:].eq(pd.Timedelta(minutes=15)).all()
    result = {"valid": bool(valid), "duration_minutes": span, "net_change": np.nan,
        "range": np.nan, "max_step": np.nan, "trend_per_hour": np.nan}
    if valid:
        hours = (times - times.iloc[0]).dt.total_seconds().div(3600)
        result.update(net_change=float(values.iloc[-1] - values.iloc[0]), range=float(values.max() - values.min()),
            max_step=float(values.diff().abs().max()), trend_per_hour=float(np.polyfit(hours, values, 1)[0]))
    return result


def quality_findings(table):
    findings = []
    messages = {
        "Stale": ("Review", "Observations are past the freshness budget", "Check the source's latest timestamp and collection status; old data is not the same as absent data."),
        "Unavailable": ("Review", "No observations returned", "Check source coverage and the selected dates before interpreting this as a sensor outage."),
        "Unknown time": ("Action", "Observation timestamps cannot be verified", "Inspect timestamp fields before alignment or real-time use."),
        "Timezone unverified": ("Action", "Source timezone is unverified", "Confirm the provider's timezone and daylight-saving convention before joining streams."),
        "Future timestamp": ("Action", "Observation timestamp is ahead of collection time", "Check clock synchronization, timezone and upstream timestamps."),
    }
    for _, row in table.iterrows():
        if row.get("Kind") in {"Sample", "Reference"}:
            continue
        if row.get("State") in messages:
            severity, finding, action = messages[row["State"]]
            findings.append({"Priority": severity, "Source": row["Source"], "Finding": finding, "Next check": action})
        for column, finding in [("Missing intervals", "Missing sampling intervals"), ("Duplicate timestamps", "Duplicate timestamps"),
                                ("Invalid times", "Invalid timestamps"), ("Invalid values", "Invalid numeric values")]:
            count = row.get(column, 0)
            if pd.notna(count) and count > 0:
                findings.append({"Priority": "Action" if column.startswith("Invalid") else "Review", "Source": row["Source"],
                    "Finding": f"{finding}: {int(count)}", "Next check": "Inspect the source records; do not silently fill gaps or remove conflicting observations."})
    return pd.DataFrame(findings, columns=["Priority", "Source", "Finding", "Next check"]).sort_values("Priority", kind="stable").reset_index(drop=True)


def report_archive(bundle, table, start, end):
    water = filter_dates(bundle.get("water_levels", pd.DataFrame()), "date_time", start, end)
    traffic = filter_dates(bundle.get("webtris_daily", pd.DataFrame()), "timestamp", start, end)
    status = bundle.get("status", pd.DataFrame())
    metadata = {"exported_at_utc": datetime.now(timezone.utc).isoformat(), "selected_start": start,
        "selected_end": end, "water_records": len(water), "traffic_records": len(traffic),
        "scope": "Observation snapshot, not a flood forecast or a reproduction of archived model experiments",
        "water_time_basis": "UTC", "traffic_time_basis": "Source timestamps; timezone unverified",
        "transformations": "No datum conversion, imputation or risk inference",
        "sources": status.to_dict(orient="records"),
        "measurement_references": water[[c for c in ["station_reference", "unit", "datum", "datum_uri", "api_endpoint"] if c in water]].drop_duplicates().to_dict(orient="records")}
    plots = []
    if not water.empty:
        for (station, unit, datum), frame in water.groupby(["station_reference", "unit", "datum_uri"], dropna=False):
            chosen = clean_water_series(frame)
            if chosen.empty:
                continue
            # Resampling creates visible gaps only; values are never interpolated.
            chart = water_chart_series(chosen)
            fig = go.Figure(go.Scatter(x=chart.index, y=chart.values, mode="lines", connectgaps=False,
                line=dict(color="#168879", width=2.5)))
            title = f"{station} | {unit} | {frame.iloc[0].get('datum', datum)}"
            fig.update_layout(template="plotly_white", height=360, xaxis_title="Observation time (UTC)", yaxis_title=escape(f"Water level ({unit})"))
            plots.append(f"<h2>{escape(title)}</h2>" + fig.to_html(full_html=False, include_plotlyjs=True if not plots else False))
    charts = "".join(plots) or "<p>No water observations returned for this period.</p>"
    health = table.to_html(index=False, escape=True) if not table.empty else "<p>No quality records available.</p>"
    source_table = status.to_html(index=False, escape=True) if not status.empty else "<p>No source status records.</p>"
    html = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CRDT-Port observation report</title><style>body{{font:15px Georgia,serif;color:#203847;background:#f4f8f7;margin:0}}
main{{max-width:1100px;margin:32px auto;padding:32px;background:white}}h1,h2{{font-family:sans-serif}}h1{{border-bottom:3px solid #168879;padding-bottom:16px}}
table{{border-collapse:collapse;font:12px sans-serif}}td,th{{padding:8px;border:1px solid #dce7e8;text-align:left}}.table-wrap{{overflow:auto}}p{{line-height:1.6}}
</style><main><h1>CRDT-Port | Observation Report</h1><p>Selected calendar dates: {escape(str(start))} to {escape(str(end))}.
Exported at {escape(metadata['exported_at_utc'])}. This is a static snapshot, not a live dashboard or forecast.</p>
<p>No datum conversion or gap filling is applied. Conflicting duplicate values are withheld from charts and diagnostics; raw rows remain in CSVs. Each gauge and measurement reference has a separate chart.
Water observation times are UTC; traffic timestamps retain their unverified source timezone. Observation age and collection time are distinct.</p>
{charts}<h2>Data health</h2><div class="table-wrap">{health}</div><h2>Source provenance and collection time</h2>
<div class="table-wrap">{source_table}</div><p>CSV files contain the selected observation rows. Structure validation does not establish sensor accuracy or flood risk.</p></main></html>"""
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, frame in [("water_observations.csv", water), ("traffic_observations.csv", traffic),
                                ("data_quality.csv", table), ("source_status.csv", status)]:
            archive.writestr(filename, frame.to_csv(index=False))
        archive.writestr("metadata.json", json.dumps(metadata, indent=2, default=str))
        archive.writestr("report.html", html)
    return output.getvalue()
