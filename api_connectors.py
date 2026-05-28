from __future__ import annotations

import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO, StringIO
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


PORT_LAT = 53.448
PORT_LON = -3.015

DFT_PORT_PAGE = "https://www.gov.uk/government/statistical-data-sets/port-and-domestic-waterborne-freight-statistics-port"
ONS_WEEKLY_SHIPPING_PAGE = "https://www.ons.gov.uk/economy/economicoutputandproductivity/output/datasets/weeklyshippingindicators"
EA_ROOT = "https://environment.data.gov.uk/flood-monitoring"
NAPTAN_MERSEYSIDE_URL = "https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv&atcoAreaCodes=280"
WEBTRIS_SITES_URL = "https://webtris.highwaysengland.co.uk/api/v1/sites"
WEBTRIS_REPORT_URL = "https://webtris.highwaysengland.co.uk/api/v1/reports/Daily"
EA_TIDE_GAUGE_STATIONS_URL = f"{EA_ROOT}/id/stations?type=TideGauge&search=Liverpool&_view=full"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "CRDT-Port dashboard API connector"})
    return session


def distance_km(lat: float, lon: float, base_lat: float = PORT_LAT, base_lon: float = PORT_LON) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat - base_lat)
    d_lon = math.radians(lon - base_lon)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(base_lat)) * math.cos(math.radians(lat)) * math.sin(d_lon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def clean_column_name(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip())


def normalise_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace({"z": None, "LOW": None, "[x]": None, "": None}), errors="coerce")


def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=45)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def find_link_by_text(session: requests.Session, page_url: str, contains: str) -> str:
    soup = get_soup(session, page_url)
    for link in soup.find_all("a", href=True):
        text = " ".join(link.get_text(" ", strip=True).split())
        if contains.lower() in text.lower():
            return urljoin(page_url, link["href"])
    raise RuntimeError(f"Could not find remote data link containing {contains!r}")


def status_row(
    connector_id: str,
    source: str,
    domain: str,
    status: str,
    records: int,
    url: str,
    access_note: str,
) -> dict[str, object]:
    return {
        "connector_id": connector_id,
        "source": source,
        "domain": domain,
        "status": status,
        "records": records,
        "api_endpoint": url,
        "last_call_utc": now_utc(),
        "access_note": access_note,
    }


def empty_bundle() -> dict[str, pd.DataFrame]:
    return {
        "status": pd.DataFrame(),
        "port_traffic": pd.DataFrame(),
        "ship_arrivals": pd.DataFrame(),
        "weekly_shipping": pd.DataFrame(),
        "ea_stations": pd.DataFrame(),
        "ea_readings": pd.DataFrame(),
        "ea_floods": pd.DataFrame(),
        "water_levels": pd.DataFrame(),
        "naptan": pd.DataFrame(),
        "webtris_sites": pd.DataFrame(),
        "webtris_daily": pd.DataFrame(),
    }


def fetch_dft_port_statistics(session: requests.Session) -> tuple[dict[str, pd.DataFrame], list[dict[str, object]]]:
    port0101_url = find_link_by_text(session, DFT_PORT_PAGE, "All freight tonnage traffic by port and year")
    port0602_url = find_link_by_text(session, DFT_PORT_PAGE, "UK ports: ship arrivals")

    port0101_response = session.get(port0101_url, timeout=90)
    port0101_response.raise_for_status()
    port0101_bytes = BytesIO(port0101_response.content)
    traffic = pd.read_excel(port0101_bytes, sheet_name="port0101_(both_directions)", header=7)
    traffic.columns = [clean_column_name(c) for c in traffic.columns]
    traffic = traffic[traffic["Ports"].astype(str).str.contains("Liverpool", case=False, na=False)].copy()
    year_cols = [col for col in traffic.columns if re.match(r"^\d{4}", str(col))]
    traffic_long = traffic.melt(
        id_vars=["Ports", "Port Group [Note 1]", "Port Type"],
        value_vars=year_cols,
        var_name="year_label",
        value_name="tonnage_thousand_tonnes",
    )
    traffic_long["year"] = traffic_long["year_label"].astype(str).str.extract(r"(\d{4})").astype(int)
    traffic_long["tonnage_thousand_tonnes"] = normalise_numeric(traffic_long["tonnage_thousand_tonnes"])
    traffic_long = traffic_long.rename(
        columns={"Ports": "port", "Port Group [Note 1]": "port_group", "Port Type": "port_type"}
    )[["port", "port_group", "port_type", "year", "tonnage_thousand_tonnes"]]

    port0602_response = session.get(port0602_url, timeout=90)
    port0602_response.raise_for_status()
    port0602_bytes = BytesIO(port0602_response.content)
    arrivals = pd.read_excel(port0602_bytes, sheet_name="Data", header=2)
    arrivals.columns = [clean_column_name(c) for c in arrivals.columns]
    arrivals = arrivals[arrivals["Port"].astype(str).str.contains("Liverpool", case=False, na=False)].copy()
    for col in ["Year", "Number", "Million deadweight tonnes", "Million gross tonnage"]:
        arrivals[col] = normalise_numeric(arrivals[col])

    frames = {"port_traffic": traffic_long, "ship_arrivals": arrivals}
    statuses = [
        status_row(
            "dft_port0101_api",
            "DfT PORT0101 Liverpool port freight tonnage",
            "Port / Maritime",
            "api_connected",
            len(traffic_long),
            port0101_url,
            "Remote ODS read directly through GOV.UK link",
        ),
        status_row(
            "dft_port0602_api",
            "DfT PORT0602 Liverpool ship arrivals",
            "Port / Maritime",
            "api_connected",
            len(arrivals),
            port0602_url,
            "Remote ODS read directly through GOV.UK link",
        ),
    ]
    return frames, statuses


def fetch_ons_weekly_shipping(session: requests.Session) -> tuple[pd.DataFrame, dict[str, object]]:
    xlsx_url = find_link_by_text(session, ONS_WEEKLY_SHIPPING_PAGE, "xlsx")
    response = session.get(xlsx_url, timeout=90)
    response.raise_for_status()
    workbook = BytesIO(response.content)
    frames: list[pd.DataFrame] = []
    for sheet_name, metric in {
        "1.Weekly All Visits NSA": "all_ship_visits",
        "3.Weekly C&T Visits NSA": "cargo_and_tanker_visits",
    }.items():
        workbook.seek(0)
        frame = pd.read_excel(workbook, sheet_name=sheet_name, header=5)
        frame.columns = [clean_column_name(c) for c in frame.columns]
        frame = frame[["Week", "Week ending", "All of UK", "Liverpool"]].copy()
        frame["metric"] = metric
        frame["week_ending"] = pd.to_datetime(frame["Week ending"], dayfirst=True, errors="coerce")
        frame["uk_total_visits"] = normalise_numeric(frame["All of UK"])
        frame["liverpool_visits"] = normalise_numeric(frame["Liverpool"])
        frames.append(frame[["metric", "Week", "week_ending", "uk_total_visits", "liverpool_visits"]])

    shipping = pd.concat(frames, ignore_index=True).dropna(subset=["week_ending"])
    return shipping, status_row(
        "ons_weekly_shipping_api",
        "ONS weekly shipping indicators",
        "Port / Maritime",
        "api_connected",
        len(shipping),
        xlsx_url,
        "Remote XLSX read directly from ONS endpoint",
    )


def fetch_environment_agency(session: requests.Session) -> tuple[dict[str, pd.DataFrame], list[dict[str, object]]]:
    stations_url = f"{EA_ROOT}/id/stations?lat={PORT_LAT}&long={PORT_LON}&dist=35&_view=full"
    stations_response = session.get(stations_url, timeout=45)
    stations_response.raise_for_status()
    stations_payload = stations_response.json()

    station_rows: list[dict[str, object]] = []
    for item in stations_payload.get("items", []):
        lat = item.get("lat")
        lon = item.get("long")
        station_rows.append(
            {
                "station_reference": item.get("stationReference", ""),
                "label": item.get("label", ""),
                "river_name": item.get("riverName", ""),
                "town": item.get("town", ""),
                "catchment_name": item.get("catchmentName", ""),
                "station_type": item.get("type", ""),
                "status": str(item.get("status", "")).split("/")[-1],
                "lat": lat,
                "lon": lon,
                "distance_km": distance_km(float(lat), float(lon)) if lat is not None and lon is not None else None,
                "measure_count": len(item.get("measures", []) or []),
            }
        )
    stations = pd.DataFrame(station_rows).sort_values("distance_km")

    def fetch_station_reading(station_reference: str) -> list[dict[str, object]]:
        readings_url = f"{EA_ROOT}/data/readings?latest&stationReference={station_reference}&_view=full"
        response = session.get(readings_url, timeout=20)
        if response.status_code != 200:
            return []
        rows: list[dict[str, object]] = []
        for reading in response.json().get("items", []):
            measure = reading.get("measure", {}) or {}
            station = measure.get("station", {}) or {}
            rows.append(
                {
                    "station_reference": measure.get("stationReference", station_reference),
                    "station_label": station.get("label", ""),
                    "date_time": reading.get("dateTime", ""),
                    "parameter": measure.get("parameter", ""),
                    "qualifier": measure.get("qualifier", ""),
                    "unit": measure.get("unitName", ""),
                    "value": reading.get("value", None),
                    "period_seconds": measure.get("period", None),
                }
            )
        return rows

    reading_rows: list[dict[str, object]] = []
    station_refs = stations["station_reference"].dropna().astype(str).head(45).tolist()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_station_reading, station_reference) for station_reference in station_refs]
        for future in as_completed(futures):
            reading_rows.extend(future.result())
    readings = pd.DataFrame(reading_rows)
    if not readings.empty:
        readings["date_time"] = pd.to_datetime(readings["date_time"], errors="coerce")

    floods = pd.DataFrame()

    frames = {"ea_stations": stations, "ea_readings": readings, "ea_floods": floods}
    statuses = [
        status_row(
            "ea_monitoring_stations_api",
            "Environment Agency monitoring stations near Liverpool",
            "Weather / Water",
            "api_connected",
            len(stations),
            stations_url,
            "Direct REST API call",
        ),
        status_row(
            "ea_latest_readings_api",
            "Environment Agency latest station readings near Liverpool",
            "Weather / Water",
            "api_connected",
            len(readings),
            f"{EA_ROOT}/data/readings?latest&stationReference=<id>&_view=full",
            "Direct REST API calls for nearest stations",
        ),
    ]
    return frames, statuses


def fetch_liverpool_tide_water_levels(session: requests.Session) -> tuple[pd.DataFrame, dict[str, object]]:
    stations_response = session.get(EA_TIDE_GAUGE_STATIONS_URL, timeout=45)
    stations_response.raise_for_status()
    stations_payload = stations_response.json()

    station_lookup: dict[str, dict[str, object]] = {}
    for item in stations_payload.get("items", []):
        station_reference = str(item.get("stationReference", "")).strip()
        if not station_reference:
            continue
        lat = item.get("lat")
        lon = item.get("long")
        station_lookup[station_reference] = {
            "station_label": item.get("label", "Liverpool"),
            "lat": lat,
            "lon": lon,
            "distance_km": distance_km(float(lat), float(lon)) if lat is not None and lon is not None else None,
        }

    rows: list[dict[str, object]] = []
    for station_reference, station in station_lookup.items():
        readings_url = f"{EA_ROOT}/data/readings?stationReference={station_reference}&_sorted&_view=full&_limit=96"
        response = session.get(readings_url, timeout=45)
        response.raise_for_status()
        for reading in response.json().get("items", []):
            measure = reading.get("measure", {}) or {}
            unit = measure.get("unitName", "")
            rows.append(
                {
                    "station_reference": station_reference,
                    "station_label": station.get("station_label", "Liverpool"),
                    "date_time": reading.get("dateTime", ""),
                    "parameter": measure.get("parameter", ""),
                    "qualifier": measure.get("qualifier", ""),
                    "unit": unit,
                    "datum": "Ordnance Datum Newlyn" if unit == "mAOD" else "Local tide gauge datum",
                    "value": reading.get("value", None),
                    "lat": station.get("lat"),
                    "lon": station.get("lon"),
                    "distance_km": station.get("distance_km"),
                    "api_endpoint": readings_url,
                }
            )

    water_levels = pd.DataFrame(rows)
    if not water_levels.empty:
        water_levels["date_time"] = pd.to_datetime(water_levels["date_time"], errors="coerce")
        water_levels["value"] = normalise_numeric(water_levels["value"])
        water_levels = water_levels.drop_duplicates(
            subset=["station_reference", "date_time", "unit", "value"]
        ).sort_values(["station_reference", "date_time"])

    return water_levels, status_row(
        "ea_liverpool_tide_water_level_api",
        "Environment Agency Liverpool tide gauge water levels",
        "Water Level",
        "api_connected",
        len(water_levels),
        f"{EA_ROOT}/data/readings?stationReference=<Liverpool tide gauge>&_sorted&_view=full&_limit=96",
        "Direct REST API call to EA Tide Gauge API; values are near real-time 15-minute water levels",
    )


def fetch_naptan(session: requests.Session) -> tuple[pd.DataFrame, dict[str, object]]:
    response = session.get(NAPTAN_MERSEYSIDE_URL, timeout=90)
    response.raise_for_status()
    stops = pd.read_csv(StringIO(response.text), low_memory=False)
    stops.columns = [clean_column_name(c) for c in stops.columns]
    if {"Latitude", "Longitude"}.issubset(stops.columns):
        stops["distance_km"] = stops.apply(
            lambda row: distance_km(float(row["Latitude"]), float(row["Longitude"]))
            if pd.notna(row["Latitude"]) and pd.notna(row["Longitude"])
            else None,
            axis=1,
        )
        stops = stops[stops["distance_km"].le(15)].copy()
    keep_cols = [
        col
        for col in [
            "ATCOCode",
            "NaptanCode",
            "CommonName",
            "Street",
            "Indicator",
            "LocalityName",
            "Town",
            "StopType",
            "Status",
            "Latitude",
            "Longitude",
            "distance_km",
        ]
        if col in stops.columns
    ]
    stops = stops[keep_cols].sort_values("distance_km") if "distance_km" in keep_cols else stops[keep_cols]
    return stops, status_row(
        "naptan_merseyside_api",
        "NaPTAN Merseyside public transport access nodes",
        "Hinterland Transport",
        "api_connected",
        len(stops),
        NAPTAN_MERSEYSIDE_URL,
        "Direct CSV API call for ATCO area 280",
    )


def fetch_webtris(session: requests.Session) -> tuple[dict[str, pd.DataFrame], list[dict[str, object]]]:
    sites_response = session.get(WEBTRIS_SITES_URL, timeout=60)
    sites_response.raise_for_status()
    sites_payload = sites_response.json()
    sites = pd.DataFrame(sites_payload.get("sites", []))
    sites = sites.rename(
        columns={"Id": "site_id", "Name": "name", "Description": "description", "Longitude": "lon", "Latitude": "lat", "Status": "status"}
    )
    sites["distance_km"] = sites.apply(
        lambda row: distance_km(float(row["lat"]), float(row["lon"]))
        if pd.notna(row["lat"]) and pd.notna(row["lon"])
        else None,
        axis=1,
    )
    local_sites = sites[sites["distance_km"].le(20)].sort_values("distance_km").copy()

    selected_site_ids = ["6806", "6807", "6980", "6981"]
    params = {
        "sites": ",".join(selected_site_ids),
        "start_date": "01052024",
        "end_date": "07052024",
        "page": 1,
        "page_size": 5000,
    }
    report_response = session.get(WEBTRIS_REPORT_URL, params=params, timeout=90)
    report_response.raise_for_status()
    report_payload = report_response.json()
    rows = pd.DataFrame(report_payload.get("Rows", []))
    if not rows.empty:
        rows.columns = [clean_column_name(c) for c in rows.columns]
        for col in ["Total Volume", "Avg mph"]:
            if col in rows.columns:
                rows[col] = normalise_numeric(rows[col])
        site_lookup = local_sites[["site_id", "description"]].copy()
        site_lookup["Site Name"] = site_lookup["description"].astype(str)
        rows = rows.merge(site_lookup, how="left", on="Site Name")
        rows["timestamp"] = pd.to_datetime(
            rows["Report Date"].astype(str).str[:10] + " " + rows["Time Period Ending"].astype(str),
            errors="coerce",
        )

    frames = {"webtris_sites": local_sites, "webtris_daily": rows}
    statuses = [
        status_row(
            "webtris_sites_api",
            "National Highways WebTRIS sites near Liverpool",
            "Hinterland Transport",
            "api_connected",
            len(local_sites),
            WEBTRIS_SITES_URL,
            "Direct REST API call",
        ),
        status_row(
            "webtris_daily_a5036_api",
            "National Highways WebTRIS A5036 15-minute traffic report",
            "Hinterland Transport",
            "api_connected",
            len(rows),
            f"{WEBTRIS_REPORT_URL}?sites={','.join(selected_site_ids)}&start_date=01052024&end_date=07052024&page=1&page_size=5000",
            "Direct REST API report call for selected Liverpool access-road sensors",
        ),
    ]
    return frames, statuses


def deferred_connector_rows() -> list[dict[str, object]]:
    timestamp = now_utc()
    deferred = [
        (
            "metoffice_datahub",
            "Met Office Weather DataHub observations/forecasts",
            "Weather / Water",
            "requires_api_key",
            "https://datahub.metoffice.gov.uk/",
            "Needs DataHub API credentials/subscription setup",
        ),
        (
            "metoffice_nswws",
            "Met Office NSWWS severe weather warnings",
            "Weather / Water",
            "requires_api_key",
            "https://metoffice.github.io/nswws-public-api/",
            "Issued warning GeoJSON requests require an x-api-key header",
        ),
        (
            "network_rail_feeds",
            "Network Rail open data feeds",
            "Hinterland Transport",
            "requires_login",
            "https://datafeeds.networkrail.co.uk/ntrod/",
            "NROD/NTROD feed access requires account setup",
        ),
        (
            "local_partner_sensors",
            "Local traffic and air-quality sensors",
            "Environment",
            "requires_partner_agreement",
            "",
            "Needs CRDT partner agreement and endpoint details",
        ),
        (
            "peel_ports_vessel_board",
            "Peel Ports Liverpool vessel arrivals/departures board",
            "Port / Maritime",
            "requires_scraping_review_or_agreement",
            "https://www.peelports.com/marine/our-ports/liverpool/vessel-arrivals-and-departures-board",
            "Public web board needs scraping and permission review",
        ),
        (
            "osm_geofabrik_england",
            "OSM England road and rail extracts from Geofabrik",
            "GIS / Network",
            "deferred_large_gis_extract",
            "https://download.geofabrik.de/europe/united-kingdom/england.html",
            "Large national GIS extract should be clipped through a GIS service",
        ),
    ]
    return [
        {
            "connector_id": connector_id,
            "source": source,
            "domain": domain,
            "status": status,
            "records": 0,
            "api_endpoint": endpoint,
            "last_call_utc": timestamp,
            "access_note": note,
        }
        for connector_id, source, domain, status, endpoint, note in deferred
    ]


def fetch_raw_data_bundle() -> dict[str, pd.DataFrame]:
    session = request_session()
    bundle = empty_bundle()
    statuses: list[dict[str, object]] = []

    connector_calls = [
        ("dft", lambda: fetch_dft_port_statistics(session)),
        ("ons", lambda: fetch_ons_weekly_shipping(session)),
        ("ea", lambda: fetch_environment_agency(session)),
        ("water_level", lambda: fetch_liverpool_tide_water_levels(session)),
        ("naptan", lambda: fetch_naptan(session)),
        ("webtris", lambda: fetch_webtris(session)),
    ]

    for connector_name, call in connector_calls:
        try:
            result = call()
            if connector_name in {"dft", "ea", "webtris"}:
                frames, rows = result  # type: ignore[misc]
                bundle.update(frames)
                statuses.extend(rows)
            elif connector_name == "ons":
                frame, row = result  # type: ignore[misc]
                bundle["weekly_shipping"] = frame
                statuses.append(row)
            elif connector_name == "naptan":
                frame, row = result  # type: ignore[misc]
                bundle["naptan"] = frame
                statuses.append(row)
            elif connector_name == "water_level":
                frame, row = result  # type: ignore[misc]
                bundle["water_levels"] = frame
                statuses.append(row)
        except Exception as exc:  # Keep the dashboard usable if one public endpoint is down.
            statuses.append(
                status_row(
                    f"{connector_name}_api",
                    f"{connector_name.upper()} connector",
                    "Unknown",
                    "api_error",
                    0,
                    "",
                    str(exc),
                )
            )

    statuses.extend(deferred_connector_rows())
    bundle["status"] = pd.DataFrame(statuses)
    return bundle
