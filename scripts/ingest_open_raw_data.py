from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

PORT_LAT = 53.448
PORT_LON = -3.015

DFT_PORT_PAGE = "https://www.gov.uk/government/statistical-data-sets/port-and-domestic-waterborne-freight-statistics-port"
ONS_WEEKLY_SHIPPING_PAGE = "https://www.ons.gov.uk/economy/economicoutputandproductivity/output/datasets/weeklyshippingindicators"
EA_ROOT = "https://environment.data.gov.uk/flood-monitoring"
NAPTAN_MERSEYSIDE_URL = "https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv&atcoAreaCodes=280"
WEBTRIS_SITES_URL = "https://webtris.highwaysengland.co.uk/api/v1/sites"
WEBTRIS_REPORT_URL = "https://webtris.highwaysengland.co.uk/api/v1/reports/Daily"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "CRDT-Port dashboard MVP data ingestion"})
    return session


def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def find_link_by_text(session: requests.Session, page_url: str, contains: str) -> str:
    soup = get_soup(session, page_url)
    for link in soup.find_all("a", href=True):
        text = " ".join(link.get_text(" ", strip=True).split())
        if contains.lower() in text.lower():
            return urljoin(page_url, link["href"])
    raise RuntimeError(f"Could not find link containing {contains!r} on {page_url}")


def download_file(session: requests.Session, url: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    response = session.get(url, timeout=120)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_column_name(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalise_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace({"z": None, "LOW": None, "[x]": None, "": None}), errors="coerce")


def distance_km(lat: float, lon: float, base_lat: float = PORT_LAT, base_lon: float = PORT_LON) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat - base_lat)
    d_lon = math.radians(lon - base_lon)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(base_lat)) * math.cos(math.radians(lat)) * math.sin(d_lon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def ingest_dft_port_statistics(session: requests.Session, statuses: list[dict[str, object]]) -> None:
    port0101_url = find_link_by_text(session, DFT_PORT_PAGE, "All freight tonnage traffic by port and year")
    port0602_url = find_link_by_text(session, DFT_PORT_PAGE, "UK ports: ship arrivals")

    port0101_path = download_file(session, port0101_url, RAW_DIR / "dft_port0101.ods")
    port0602_path = download_file(session, port0602_url, RAW_DIR / "dft_port0602.ods")

    traffic = pd.read_excel(port0101_path, sheet_name="port0101_(both_directions)", header=7)
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
    traffic_long.to_csv(DATA_DIR / "raw_dft_port_traffic_liverpool.csv", index=False, encoding="utf-8-sig")

    arrivals = pd.read_excel(port0602_path, sheet_name="Data", header=2)
    arrivals.columns = [clean_column_name(c) for c in arrivals.columns]
    arrivals = arrivals[arrivals["Port"].astype(str).str.contains("Liverpool", case=False, na=False)].copy()
    for col in ["Year", "Number", "Million deadweight tonnes", "Million gross tonnage"]:
        arrivals[col] = normalise_numeric(arrivals[col])
    arrivals.to_csv(DATA_DIR / "raw_dft_ship_arrivals_liverpool.csv", index=False, encoding="utf-8-sig")

    statuses.extend(
        [
            {
                "connector_id": "dft_port0101",
                "source": "DfT PORT0101 port freight tonnage",
                "domain": "Port / Maritime",
                "status": "connected",
                "records": len(traffic_long),
                "processed_file": "raw_dft_port_traffic_liverpool.csv",
                "raw_file": "raw/dft_port0101.ods",
                "last_ingested_utc": now_utc(),
                "access_note": "Open ODS download from GOV.UK",
                "url": port0101_url,
            },
            {
                "connector_id": "dft_port0602",
                "source": "DfT PORT0602 ship arrivals",
                "domain": "Port / Maritime",
                "status": "connected",
                "records": len(arrivals),
                "processed_file": "raw_dft_ship_arrivals_liverpool.csv",
                "raw_file": "raw/dft_port0602.ods",
                "last_ingested_utc": now_utc(),
                "access_note": "Open ODS download from GOV.UK",
                "url": port0602_url,
            },
        ]
    )


def ingest_ons_weekly_shipping(session: requests.Session, statuses: list[dict[str, object]]) -> None:
    xlsx_url = find_link_by_text(session, ONS_WEEKLY_SHIPPING_PAGE, "xlsx")
    xlsx_path = download_file(session, xlsx_url, RAW_DIR / "ons_weekly_shipping_2026.xlsx")

    sheets = {
        "1.Weekly All Visits NSA": "all_ship_visits",
        "3.Weekly C&T Visits NSA": "cargo_and_tanker_visits",
    }
    frames: list[pd.DataFrame] = []
    for sheet_name, metric in sheets.items():
        frame = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=5)
        frame.columns = [clean_column_name(c) for c in frame.columns]
        frame = frame[["Week", "Week ending", "All of UK", "Liverpool"]].copy()
        frame["metric"] = metric
        frame["week_ending"] = pd.to_datetime(frame["Week ending"], dayfirst=True, errors="coerce")
        frame["uk_total_visits"] = normalise_numeric(frame["All of UK"])
        frame["liverpool_visits"] = normalise_numeric(frame["Liverpool"])
        frames.append(frame[["metric", "Week", "week_ending", "uk_total_visits", "liverpool_visits"]])

    shipping = pd.concat(frames, ignore_index=True).dropna(subset=["week_ending"])
    shipping.to_csv(DATA_DIR / "raw_ons_weekly_shipping_liverpool.csv", index=False, encoding="utf-8-sig")
    statuses.append(
        {
            "connector_id": "ons_weekly_shipping",
            "source": "ONS weekly shipping indicators",
            "domain": "Port / Maritime",
            "status": "connected",
            "records": len(shipping),
            "processed_file": "raw_ons_weekly_shipping_liverpool.csv",
            "raw_file": "raw/ons_weekly_shipping_2026.xlsx",
            "last_ingested_utc": now_utc(),
            "access_note": "Open XLSX download from ONS",
            "url": xlsx_url,
        }
    )


def ingest_environment_agency(session: requests.Session, statuses: list[dict[str, object]]) -> None:
    stations_url = f"{EA_ROOT}/id/stations?lat={PORT_LAT}&long={PORT_LON}&dist=35&_view=full"
    floods_url = f"{EA_ROOT}/id/floods?lat={PORT_LAT}&long={PORT_LON}&dist=50"
    stations_payload = session.get(stations_url, timeout=60).json()
    floods_payload = session.get(floods_url, timeout=60).json()
    write_json(RAW_DIR / "ea_flood_stations_liverpool.json", stations_payload)
    write_json(RAW_DIR / "ea_flood_warnings_liverpool.json", floods_payload)

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
    stations.to_csv(DATA_DIR / "raw_ea_flood_stations_liverpool.csv", index=False, encoding="utf-8-sig")

    reading_rows: list[dict[str, object]] = []
    for station_reference in stations["station_reference"].dropna().astype(str).tolist():
        readings_url = f"{EA_ROOT}/data/readings?latest&stationReference={station_reference}&_view=full"
        response = session.get(readings_url, timeout=30)
        if response.status_code != 200:
            continue
        for reading in response.json().get("items", []):
            measure = reading.get("measure", {}) or {}
            station = measure.get("station", {}) or {}
            reading_rows.append(
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

    readings = pd.DataFrame(reading_rows)
    readings.to_csv(DATA_DIR / "raw_ea_latest_readings_liverpool.csv", index=False, encoding="utf-8-sig")

    flood_rows: list[dict[str, object]] = []
    for item in floods_payload.get("items", []):
        flood_area = item.get("floodArea", {}) or {}
        flood_rows.append(
            {
                "description": item.get("description", ""),
                "severity": item.get("severity", ""),
                "severity_level": item.get("severityLevel", ""),
                "is_tidal": item.get("isTidal", ""),
                "message": item.get("message", ""),
                "time_raised": item.get("timeRaised", ""),
                "time_severity_changed": item.get("timeSeverityChanged", ""),
                "river_or_sea": flood_area.get("riverOrSea", ""),
                "county": flood_area.get("county", ""),
            }
        )
    floods = pd.DataFrame(
        flood_rows,
        columns=[
            "description",
            "severity",
            "severity_level",
            "is_tidal",
            "message",
            "time_raised",
            "time_severity_changed",
            "river_or_sea",
            "county",
        ],
    )
    floods.to_csv(DATA_DIR / "raw_ea_flood_warnings_liverpool.csv", index=False, encoding="utf-8-sig")

    statuses.extend(
        [
            {
                "connector_id": "ea_flood_stations",
                "source": "Environment Agency flood monitoring stations near Liverpool",
                "domain": "Weather / Flood",
                "status": "connected",
                "records": len(stations),
                "processed_file": "raw_ea_flood_stations_liverpool.csv",
                "raw_file": "raw/ea_flood_stations_liverpool.json",
                "last_ingested_utc": now_utc(),
                "access_note": "Open REST API; no registration required",
                "url": stations_url,
            },
            {
                "connector_id": "ea_latest_readings",
                "source": "Environment Agency latest station readings near Liverpool",
                "domain": "Weather / Flood",
                "status": "connected",
                "records": len(readings),
                "processed_file": "raw_ea_latest_readings_liverpool.csv",
                "raw_file": "",
                "last_ingested_utc": now_utc(),
                "access_note": "Open REST API; latest readings fetched per station",
                "url": f"{EA_ROOT}/data/readings?latest&stationReference=<id>&_view=full",
            },
            {
                "connector_id": "ea_flood_warnings",
                "source": "Environment Agency current flood warnings near Liverpool",
                "domain": "Weather / Flood",
                "status": "connected",
                "records": len(floods),
                "processed_file": "raw_ea_flood_warnings_liverpool.csv",
                "raw_file": "raw/ea_flood_warnings_liverpool.json",
                "last_ingested_utc": now_utc(),
                "access_note": "Open REST API; zero rows means no active warning in the query radius",
                "url": floods_url,
            },
        ]
    )


def ingest_naptan(session: requests.Session, statuses: list[dict[str, object]]) -> None:
    csv_path = download_file(session, NAPTAN_MERSEYSIDE_URL, RAW_DIR / "naptan_merseyside.csv")
    stops = pd.read_csv(csv_path, low_memory=False)
    stops.columns = [clean_column_name(c) for c in stops.columns]
    if "Latitude" in stops and "Longitude" in stops:
        stops["distance_km"] = stops.apply(
            lambda row: distance_km(float(row["Latitude"]), float(row["Longitude"]))
            if pd.notna(row["Latitude"]) and pd.notna(row["Longitude"])
            else None,
            axis=1,
        )
        local = stops[stops["distance_km"].le(15)].copy()
    else:
        local = stops.copy()

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
        if col in local.columns
    ]
    local = local[keep_cols].sort_values("distance_km") if "distance_km" in local.columns else local[keep_cols]
    local.to_csv(DATA_DIR / "raw_naptan_liverpool_area.csv", index=False, encoding="utf-8-sig")

    statuses.append(
        {
            "connector_id": "naptan_merseyside",
            "source": "NaPTAN Merseyside public transport access nodes",
            "domain": "Hinterland Transport",
            "status": "connected",
            "records": len(local),
            "processed_file": "raw_naptan_liverpool_area.csv",
            "raw_file": "raw/naptan_merseyside.csv",
            "last_ingested_utc": now_utc(),
            "access_note": "Open CSV API download for ATCO area 280",
            "url": NAPTAN_MERSEYSIDE_URL,
        }
    )


def ingest_webtris(session: requests.Session, statuses: list[dict[str, object]]) -> None:
    sites_payload = session.get(WEBTRIS_SITES_URL, timeout=60).json()
    write_json(RAW_DIR / "webtris_sites.json", sites_payload)
    sites = pd.DataFrame(sites_payload.get("sites", []))
    sites = sites.rename(columns={"Id": "site_id", "Name": "name", "Description": "description", "Longitude": "lon", "Latitude": "lat", "Status": "status"})
    sites["distance_km"] = sites.apply(
        lambda row: distance_km(float(row["lat"]), float(row["lon"]))
        if pd.notna(row["lat"]) and pd.notna(row["lon"])
        else None,
        axis=1,
    )
    local_sites = sites[sites["distance_km"].le(20)].sort_values("distance_km").copy()
    local_sites.to_csv(DATA_DIR / "raw_webtris_sites_liverpool.csv", index=False, encoding="utf-8-sig")

    selected_site_ids = ["6806", "6807", "6980", "6981"]
    params = {
        "sites": ",".join(selected_site_ids),
        "start_date": "01052024",
        "end_date": "07052024",
        "page": 1,
        "page_size": 5000,
    }
    report_payload = session.get(WEBTRIS_REPORT_URL, params=params, timeout=120).json()
    write_json(RAW_DIR / "webtris_daily_a5036_may2024.json", report_payload)
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
    rows.to_csv(DATA_DIR / "raw_webtris_daily_a5036.csv", index=False, encoding="utf-8-sig")

    statuses.extend(
        [
            {
                "connector_id": "webtris_sites",
                "source": "National Highways WebTRIS sites near Liverpool",
                "domain": "Hinterland Transport",
                "status": "connected",
                "records": len(local_sites),
                "processed_file": "raw_webtris_sites_liverpool.csv",
                "raw_file": "raw/webtris_sites.json",
                "last_ingested_utc": now_utc(),
                "access_note": "Open WebTRIS REST API, no key required",
                "url": WEBTRIS_SITES_URL,
            },
            {
                "connector_id": "webtris_daily_a5036",
                "source": "National Highways WebTRIS A5036 daily sensor report",
                "domain": "Hinterland Transport",
                "status": "connected",
                "records": len(rows),
                "processed_file": "raw_webtris_daily_a5036.csv",
                "raw_file": "raw/webtris_daily_a5036_may2024.json",
                "last_ingested_utc": now_utc(),
                "access_note": "Historical raw 15-minute report for selected Liverpool access-road sensors",
                "url": WEBTRIS_REPORT_URL,
            },
        ]
    )


def write_status(statuses: list[dict[str, object]]) -> None:
    status_frame = pd.DataFrame(statuses)
    status_frame.to_csv(DATA_DIR / "raw_connector_status.csv", index=False, encoding="utf-8-sig")


def append_deferred_connectors(statuses: list[dict[str, object]]) -> None:
    timestamp = now_utc()
    statuses.extend(
        [
            {
                "connector_id": "metoffice_datahub",
                "source": "Met Office Weather DataHub observations/forecasts",
                "domain": "Weather / Flood",
                "status": "requires_api_key",
                "records": 0,
                "processed_file": "",
                "raw_file": "",
                "last_ingested_utc": timestamp,
                "access_note": "Not fetched because the source requires DataHub API credentials/subscription setup",
                "url": "https://datahub.metoffice.gov.uk/",
            },
            {
                "connector_id": "metoffice_nswws",
                "source": "Met Office NSWWS severe weather warnings",
                "domain": "Weather / Flood",
                "status": "requires_api_key",
                "records": 0,
                "processed_file": "",
                "raw_file": "",
                "last_ingested_utc": timestamp,
                "access_note": "Not fetched because issued warning GeoJSON requests require an x-api-key header",
                "url": "https://metoffice.github.io/nswws-public-api/",
            },
            {
                "connector_id": "network_rail_feeds",
                "source": "Network Rail open data feeds",
                "domain": "Hinterland Transport",
                "status": "requires_login",
                "records": 0,
                "processed_file": "",
                "raw_file": "",
                "last_ingested_utc": timestamp,
                "access_note": "Not fetched in MVP because NROD/NTROD feed access requires account setup",
                "url": "https://datafeeds.networkrail.co.uk/ntrod/",
            },
            {
                "connector_id": "local_partner_sensors",
                "source": "Local traffic and air-quality sensors",
                "domain": "Environment",
                "status": "requires_partner_agreement",
                "records": 0,
                "processed_file": "",
                "raw_file": "",
                "last_ingested_utc": timestamp,
                "access_note": "Not fetched because the Word file marks these as obtainable subject to prior agreement",
                "url": "",
            },
            {
                "connector_id": "peel_ports_vessel_board",
                "source": "Peel Ports Liverpool vessel arrivals/departures board",
                "domain": "Port / Maritime",
                "status": "requires_scraping_review_or_agreement",
                "records": 0,
                "processed_file": "",
                "raw_file": "",
                "last_ingested_utc": timestamp,
                "access_note": "Not fetched automatically in MVP because the source is a public Power BI/web board and needs scraping/permission review",
                "url": "https://www.peelports.com/marine/our-ports/liverpool/vessel-arrivals-and-departures-board",
            },
            {
                "connector_id": "osm_geofabrik_england",
                "source": "OSM England road and rail extracts from Geofabrik",
                "domain": "GIS / Network",
                "status": "deferred_large_gis_extract",
                "records": 0,
                "processed_file": "",
                "raw_file": "",
                "last_ingested_utc": timestamp,
                "access_note": "Not fetched in this MVP run because national PBF/shapefile extraction should be clipped in a GIS pipeline",
                "url": "https://download.geofabrik.de/europe/united-kingdom/england.html",
            },
        ]
    )


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = request_session()
    statuses: list[dict[str, object]] = []

    ingest_dft_port_statistics(session, statuses)
    ingest_ons_weekly_shipping(session, statuses)
    ingest_environment_agency(session, statuses)
    ingest_naptan(session, statuses)
    ingest_webtris(session, statuses)
    append_deferred_connectors(statuses)
    write_status(statuses)

    print(f"Ingested {len(statuses)} open raw data connectors into {DATA_DIR}")


if __name__ == "__main__":
    main()
