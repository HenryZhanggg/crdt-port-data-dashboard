from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pandas as pd
from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD


EX = Namespace("https://example.org/crdt-port/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
SH = Namespace("http://www.w3.org/ns/shacl#")
ONTOLOGY_DIR = Path(__file__).parent / "ontology"


def filter_dates(frame, column, start, end):
    if frame.empty or column not in frame or start is None or end is None:
        return frame.copy()
    times = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
    first = pd.Timestamp(start, tz="UTC")
    last = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    return frame.loc[times.ge(first) & times.lt(last)].copy()


def assess_series(name, frame, time_column, kind, now=None, stale_minutes=60, value_column=None, cadence_minutes=None):
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    times = pd.to_datetime(frame.get(time_column, pd.Series(dtype=str)), utc=True, errors="coerce", format="mixed")
    latest = times.max()
    age = (now - latest).total_seconds() / 60 if pd.notna(latest) else None
    if frame.empty:
        state = "Unavailable"
    elif kind in {"Sample", "Reference", "Statistics"}:
        state = {"Sample": "Sample", "Reference": "Reference", "Statistics": "Historical statistics"}[kind]
    elif pd.isna(latest):
        state = "Unknown time"
    elif age < -5:
        state = "Future timestamp"
    else:
        state = "Current" if age <= stale_minutes else "Stale"
    valid_times = times.dropna().sort_values().drop_duplicates()
    gaps = 0
    if cadence_minutes and len(valid_times) > 1:
        intervals = valid_times.diff().dt.total_seconds().div(60 * cadence_minutes)
        gaps = int(intervals.sub(1).clip(lower=0).fillna(0).apply(lambda v: int(v)).sum())
    invalid_values = 0
    if value_column and value_column in frame:
        numeric = pd.to_numeric(frame[value_column], errors="coerce")
        invalid_values = int((numeric.isna() | numeric.isin([float("inf"), float("-inf")])).sum())
    source_first = str(frame.loc[times.idxmin(), time_column]) if times.notna().any() else ""
    source_latest = str(frame.loc[times.idxmax(), time_column]) if times.notna().any() else ""
    result = {
        "Source": name, "Kind": kind, "State": state, "Records": len(frame),
        "First UTC": times.min(), "Latest UTC": latest,
        "Age (min)": round(age, 1) if age is not None else None,
        "Invalid times": int(times.isna().sum()), "Invalid values": invalid_values,
        "Missing intervals": gaps, "Duplicate timestamps": int(times.dropna().duplicated().sum()),
        "Source first timestamp": source_first, "Source latest timestamp": source_latest,
    }
    if kind in {"Sample", "Statistics"}:
        result.update({"First UTC": pd.NaT, "Latest UTC": pd.NaT, "Age (min)": None})
    return result


def measure_datum(measure):
    datum = measure.get("datumType", "")
    if isinstance(datum, dict):
        datum = datum.get("@id", "")
    uri = str(datum or "")
    labels = {"datumAOD": "Ordnance Datum Newlyn", "datumLocal": "Local tide gauge datum"}
    suffix = uri.rsplit("/", 1)[-1]
    if suffix in labels:
        return labels[suffix], uri
    if measure.get("unitName") == "m" and measure.get("ordnanceDatumMeasure") and measure.get("@id"):
        return "Local tide gauge datum", str(measure["@id"]) + "#local-datum"
    return "Unknown datum", ""


def compatibility(left, right):
    for field, message in [
        ("site_key", "Different or unverified monitoring locations"),
        ("parameter", "Different or unverified observed properties"),
        ("qualifier", "Different or unverified measurement categories"),
        ("datum_uri", "Different or unverified vertical datums; no conversion applied"),
        ("unit", "Different or unverified units; no conversion applied"),
    ]:
        if not left.get(field) or not right.get(field) or left[field] != right[field]:
            return False, message
    return True, "Same location, property, datum and unit; timestamps still require alignment"


def quality_table(bundle, weather, transport, now=None):
    rows = []
    water = bundle.get("water_levels", pd.DataFrame())
    if not water.empty:
        for (station, unit), group in water.groupby(["station_reference", "unit"], dropna=False):
            rows.append(assess_series(f"Water {station} | {unit}", group, "date_time", "Observation", now, 60, "value", 15))
    else:
        rows.append(assess_series("Liverpool water level", water, "date_time", "Observation", now))
    traffic = bundle.get("webtris_daily", pd.DataFrame())
    if not traffic.empty and "site_id" in traffic:
        for station, group in traffic.groupby("site_id", dropna=False):
            result = assess_series(f"Traffic {station}", group, "timestamp", "Observation", now, 180, "Total Volume", 15)
            if pd.to_datetime(group["timestamp"], errors="coerce").dt.tz is None:
                result.update({"State": "Timezone unverified", "First UTC": pd.NaT, "Latest UTC": pd.NaT, "Age (min)": None})
            rows.append(result)
    else:
        rows.append(assess_series("A5036 traffic", traffic, "timestamp", "Observation", now, 180))
    rows.append(assess_series("Weather demonstration", weather, "timestamp", "Sample", now))
    rows.append(assess_series("Transport demonstration", transport, "reported_at", "Sample", now))
    shipping = bundle.get("weekly_shipping", pd.DataFrame())
    status = bundle.get("status", pd.DataFrame())
    queried_shipping = "connector_id" in status and status["connector_id"].astype(str).str.startswith("ons").any()
    if not shipping.empty or queried_shipping:
        rows.append(assess_series("ONS shipping", shipping, "week_ending", "Statistics", now))
    return pd.DataFrame(rows)


def observation_graph(water):
    graph = Graph().parse(ONTOLOGY_DIR / "port_monitoring.ttl", format="turtle")
    graph.bind("port", EX)
    graph.bind("sosa", SOSA)
    for index, row in water.reset_index(drop=True).iterrows():
        station = EX[f"sensor/{quote(str(row.get('station_reference', 'unknown')), safe='')}"]
        observation = EX[f"observation/{index}"]
        location = f"{row.get('lat', 'unknown')},{row.get('lon', 'unknown')}"
        site = EX[f"site/{quote(location, safe='')}"]
        graph.add((station, RDF.type, SOSA.Sensor))
        graph.add((site, RDF.type, SOSA.FeatureOfInterest))
        reference = row.get("station_reference")
        if pd.notna(reference) and str(reference):
            graph.add((station, EX.stationReference, Literal(str(reference))))
        for column, predicate in [("lat", EX.latitude), ("lon", EX.longitude)]:
            coordinate = pd.to_numeric(row.get(column), errors="coerce")
            if pd.notna(coordinate):
                graph.add((site, predicate, Literal(float(coordinate), datatype=XSD.double)))
        graph.add((observation, RDF.type, EX.WaterLevelObservation))
        graph.add((observation, SOSA.madeBySensor, station))
        graph.add((observation, SOSA.hasFeatureOfInterest, site))
        graph.add((observation, SOSA.observedProperty, EX.WaterLevel))
        timestamp = pd.to_datetime(row.get("date_time"), utc=True, errors="coerce")
        if pd.notna(timestamp):
            graph.add((observation, SOSA.phenomenonTime, Literal(timestamp.isoformat(), datatype=XSD.dateTime)))
        value = pd.to_numeric(row.get("value"), errors="coerce")
        if pd.notna(value):
            graph.add((observation, SOSA.hasSimpleResult, Literal(float(value), datatype=XSD.double)))
        unit = row.get("unit")
        if pd.notna(unit) and str(unit):
            graph.add((observation, EX.unit, Literal(str(unit))))
        datum = row.get("datum_uri")
        if pd.notna(datum) and str(datum):
            graph.add((observation, EX.verticalDatum, URIRef(str(datum))))
        endpoint = row.get("api_endpoint")
        if pd.notna(endpoint) and str(endpoint):
            graph.add((observation, EX.sourceEndpoint, URIRef(str(endpoint))))
    return graph


def validate_observations(graph):
    conforms, report, _ = validate(graph, shacl_graph=str(ONTOLOGY_DIR / "observation_shapes.ttl"), inference="rdfs")
    rows = []
    for result in report.subjects(RDF.type, SH.ValidationResult):
        rows.append({"Observation": str(report.value(result, SH.focusNode)), "Field": str(report.value(result, SH.resultPath)), "Message": str(report.value(result, SH.resultMessage))})
    return bool(conforms), pd.DataFrame(rows, columns=["Observation", "Field", "Message"])
