from __future__ import annotations

import pandas as pd

from data_quality import assess_series


ENTITY_COLUMNS = ["entity_id", "name", "kind", "evidence_role", "state", "lat", "lon", "station_reference",
                  "unit", "datum", "datum_uri", "site_id", "source_url", "latest_time"]


def _text(value):
    return "" if pd.isna(value) else str(value)


def _site_id(value):
    return str(int(value)) if isinstance(value, float) and value.is_integer() else _text(value)


def _source_url(bundle, connector_id):
    status = bundle.get("status", pd.DataFrame())
    if "connector_id" not in status or "api_endpoint" not in status:
        return ""
    source = status.loc[status["connector_id"].eq(connector_id), "api_endpoint"]
    return _text(source.iloc[0]) if not source.empty else ""


def selected_water(bundle: dict, entity: dict) -> pd.DataFrame:
    """Return raw rows for one station, unit and vertical reference."""
    water = bundle.get("water_levels", pd.DataFrame())
    if entity.get("kind") != "Water" or water.empty:
        return pd.DataFrame()
    mask = pd.Series(True, index=water.index)
    for field in ["station_reference", "unit", "datum_uri"]:
        values = water.get(field, pd.Series("", index=water.index)).fillna("").astype(str)
        mask &= values.eq(_text(entity.get(field)))
    return water.loc[mask].copy()


def build_entities(bundle: dict, assets: pd.DataFrame | None = None, include_demo: bool = False) -> pd.DataFrame:
    """Build source-derived workspace IDs; these are not WP1 canonical IDs."""
    rows = []
    water = bundle.get("water_levels", pd.DataFrame())
    if not water.empty:
        for station, group in water.groupby("station_reference", sort=False, dropna=False):
            times = pd.to_datetime(group["date_time"], utc=True, errors="coerce", format="mixed")
            row = group.iloc[times.argmax()] if times.notna().any() else group.iloc[-1]
            entity = {"entity_id": f"water:{_text(station)}", "name": f"Water gauge {_text(station)}",
                      "kind": "Water", "evidence_role": "Observed", "lat": row.get("lat"), "lon": row.get("lon"),
                      "station_reference": _text(station), "unit": _text(row.get("unit")),
                      "datum": _text(row.get("datum")), "datum_uri": _text(row.get("datum_uri")),
                      "source_url": _text(row.get("api_endpoint")) or _source_url(bundle, "ea_liverpool_tide_water_level_api")}
            reference = selected_water(bundle, entity).reset_index(drop=True)
            quality = assess_series(entity["name"], reference, "date_time", "Observation", value_column="value", cadence_minutes=15)
            entity.update(state=quality["State"], latest_time=quality["Latest UTC"])
            rows.append(entity)
    sites = bundle.get("webtris_sites", pd.DataFrame())
    traffic = bundle.get("webtris_daily", pd.DataFrame())
    if not sites.empty:
        for site_id, group in sites.groupby(sites["site_id"].map(_site_id), sort=False):
            row = group.iloc[0]
            observations = traffic.loc[traffic.get("site_id", pd.Series("", index=traffic.index)).map(_site_id).eq(site_id)]
            entity = {"entity_id": f"traffic:{_text(site_id)}", "name": f"Traffic counter {_text(site_id)}",
                      "kind": "Traffic", "evidence_role": "Reference", "state": "Reference location",
                      "lat": row.get("lat"), "lon": row.get("lon"), "site_id": _text(site_id), "latest_time": pd.NaT,
                      "source_url": _text(row.get("api_endpoint")) or _source_url(bundle, "webtris_sites_api")}
            if not observations.empty:
                quality = assess_series(entity["name"], observations.reset_index(drop=True), "timestamp", "Observation",
                                        stale_minutes=180, value_column="Total Volume", cadence_minutes=15)
                times = observations.get("timestamp", pd.Series(dtype=str)).map(lambda value: pd.to_datetime(value, errors="coerce"))
                unverified = any(pd.notna(value) and value.tzinfo is None for value in times)
                entity.update(evidence_role="Observed", state="Timezone unverified" if unverified else quality["State"],
                              latest_time=pd.NaT if unverified else quality["Latest UTC"],
                              source_url=_source_url(bundle, "webtris_daily_a5036_api") or entity["source_url"])
            rows.append(entity)
    if include_demo and assets is not None:
        for _, row in assets.drop_duplicates("asset_id").iterrows():
            rows.append({"entity_id": f"demo:{_text(row['asset_id'])}", "name": _text(row.get("name")),
                         "kind": "Demonstration", "evidence_role": "Illustrative", "state": "Sample",
                         "lat": row.get("lat"), "lon": row.get("lon"), "latest_time": pd.NaT})
    entities = pd.DataFrame(rows, columns=ENTITY_COLUMNS)
    for field, limit in [("lat", 90), ("lon", 180)]:
        coordinates = pd.to_numeric(entities[field], errors="coerce")
        entities[field] = coordinates.where(coordinates.between(-limit, limit))
    text_columns = [field for field in ENTITY_COLUMNS if field not in {"lat", "lon", "latest_time"}]
    entities[text_columns] = entities[text_columns].fillna("")
    return entities


def choose_entity(entities: pd.DataFrame, current_id: str | None, map_id: str | None = None,
                  last_map_id: str | None = None) -> str | None:
    ids = entities.get("entity_id", pd.Series(dtype=str)).tolist()
    if map_id in ids and map_id != last_map_id:
        return map_id
    if current_id in ids:
        return current_id
    return ids[0] if ids else None
