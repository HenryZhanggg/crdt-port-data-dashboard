from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from docx import Document


DEFAULT_DOCX = (
    Path.home()
    / "Desktop"
    / "DT-paper"
    / "CRDT-Data"
    / "CRDT Avaliable Datasets for Ports of Liverpool-draft-02-09.docx"
)
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "high_score_dataset_catalog.csv"
DEFAULT_JSON_OUT = Path(__file__).resolve().parents[1] / "data" / "high_score_dataset_catalog.json"

RANK_RE = re.compile(r"Rank\s*(\d)\s*/\s*5", re.IGNORECASE)
QUALITY_RE = re.compile(r"Data quality\s*(\d)\s*/\s*5", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
CATEGORY_RE = re.compile(r"^(?:\(([A-Z])\)|([A-Z])\))\s*(.+?)(?:\s*[–-]\s*Rank\s*(\d)\s*/\s*5)?$", re.IGNORECASE)


FIELD_PREFIXES = (
    "brief description",
    "brief description",
    "data availability",
    "data quality",
    "format",
    "cost",
    "period",
    "highlighted comment",
    "notes",
    "note",
    "low rank reason",
    "comment",
)


def read_docx_lines(path: Path) -> list[str]:
    document = Document(path)
    lines: list[str] = []
    for paragraph in document.paragraphs:
        for raw_line in paragraph.text.splitlines():
            line = raw_line.strip()
            if line:
                lines.append(line)
    return lines


def is_category(line: str) -> re.Match[str] | None:
    match = CATEGORY_RE.match(line)
    if not match:
        return None

    body = (match.group(3) or "").strip()
    lower = body.lower()
    if any(lower.startswith(prefix) for prefix in FIELD_PREFIXES):
        return None
    if lower.startswith("data for "):
        return None
    return match


def is_source_start(line: str) -> bool:
    clean = line.strip()
    lower = clean.lower()
    if clean.startswith(("- ", "* ")):
        return True
    if RANK_RE.search(clean) and not any(lower.startswith(prefix) for prefix in FIELD_PREFIXES):
        return True
    return False


def clean_title(line: str) -> str:
    title = re.sub(r"^[-*]\s*", "", line).strip()
    title = RANK_RE.sub("", title)
    title = QUALITY_RE.sub("", title)
    title = re.sub(r"\s*,\s*$", "", title)
    title = re.sub(r"\s*-\s*$", "", title)
    title = title.strip(" :;")
    return title or "Untitled source"


def extract_urls(text: str) -> list[str]:
    urls = []
    for url in URL_RE.findall(text):
        urls.append(url.rstrip(".,;"))
    return urls


def extract_first_field(lines: list[str], label: str) -> str:
    label_re = re.compile(rf"^(?:[•\-]\s*)?{re.escape(label)}\s*:\s*(.+)$", re.IGNORECASE)
    for line in lines:
        match = label_re.search(line)
        if match:
            return match.group(1).strip()
    return ""


def extract_by_any_label(lines: list[str], labels: tuple[str, ...]) -> str:
    for label in labels:
        value = extract_first_field(lines, label)
        if value:
            return value
    return ""


def infer_domain(title: str, category: str, text: str) -> str:
    haystack = f"{title} {category} {text}".lower()
    if any(word in haystack for word in ("weather", "met office", "flood", "tide", "sea level", "coastal", "rainfall")):
        return "Weather / Flood"
    if any(word in haystack for word in ("osm", "arcgis", "geojson", "shapefile", "geotiff", "pbf", "network structure", "vessel density", "geofabrik")):
        return "GIS / Network"
    if any(word in haystack for word in ("webtris", "highways", "road", "traffic", "rail", "public transport", "naptan", "network rail")):
        return "Hinterland Transport"
    if any(word in haystack for word in ("port", "maritime", "shipping", "vessel", "peel", "dft", "ons", "waterborne", "imf portwatch")):
        return "Port / Maritime"
    if any(word in haystack for word in ("air quality", "defra", "sensor")):
        return "Environment"
    return "Cross-cutting"


def infer_source_type(title: str, source_format: str, url: str, text: str) -> str:
    haystack = f"{title} {source_format} {url} {text}".lower()
    if "api" in haystack or "swagger" in haystack or "endpoint" in haystack:
        return "API"
    if any(word in haystack for word in ("geojson", "shapefile", "geotiff", "pbf", "arcgis", "raster")):
        return "GIS data"
    if any(word in haystack for word in ("spreadsheet", "csv", "excel", "ods", "downloadable")):
        return "Downloadable table"
    if any(word in haystack for word in ("dashboard", "interactive", "power bi", "html", "web map")):
        return "Dashboard / web"
    if any(word in haystack for word in ("sensor", "real-time", "near real-time")):
        return "Live feed"
    return "Metadata / web page"


def infer_connection_mode(source_type: str, source_format: str, text: str) -> str:
    haystack = f"{source_type} {source_format} {text}".lower()
    if "api" in haystack:
        return "API connector"
    if any(word in haystack for word in ("geojson", "shapefile", "geotiff", "pbf", "arcgis")):
        return "GIS file/layer import"
    if any(word in haystack for word in ("spreadsheet", "csv", "excel", "ods")):
        return "Scheduled file import"
    if any(word in haystack for word in ("power bi", "dashboard", "interactive", "html", "web map")):
        return "Manual snapshot / scraping review"
    if "sensor" in haystack or "real-time" in haystack:
        return "Streaming/API connector"
    return "Manual metadata review"


def infer_access_level(title: str, cost: str, text: str) -> str:
    haystack = f"{title} {cost} {text}".lower()
    if any(word in haystack for word in ("subject to prior agreement", "local data", "peel ports", "customer portal")):
        return "L2 partner/internal"
    if any(word in haystack for word in ("registration", "freemium", "subscription", "paid", "api key", "requires setting up api keys")):
        return "L1 restricted/registered"
    if any(word in haystack for word in ("free", "public", "open government licence", "open data", "osm licence", "no obvious per-download cost")):
        return "L0 public/open"
    return "L1 review required"


def infer_dashboard_use(domain: str, title: str, category: str, text: str) -> str:
    haystack = f"{title} {category} {text}".lower()
    if domain == "Weather / Flood":
        return "Crisis trigger, weather window, flood-risk signal"
    if domain == "Hinterland Transport":
        return "Road/rail access monitoring and disruption explanation"
    if domain == "GIS / Network":
        return "Base network layer, routing context, spatial exposure map"
    if "shipping" in haystack or "vessel" in haystack:
        return "Maritime movement, schedule, route, or port-call evidence"
    if "statistics" in haystack or "dft" in haystack or "ons" in haystack:
        return "Baseline benchmarking and demand context"
    return "Supporting evidence for dashboard service design"


def build_blocks(lines: list[str]) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    current_category = "Uncategorised"
    current_category_id = ""
    current_category_rank: int | None = None
    current_lines: list[str] = []
    current_meta = {"category": current_category, "category_id": current_category_id, "category_rank": current_category_rank}

    def flush() -> None:
        nonlocal current_lines
        if current_lines:
            blocks.append({**current_meta, "lines": current_lines})
            current_lines = []

    for line in lines:
        category_match = is_category(line)
        if category_match:
            flush()
            current_category_id = (category_match.group(1) or category_match.group(2) or "").upper()
            current_category = category_match.group(3).strip(" -")
            rank_text = category_match.group(4)
            current_category_rank = int(rank_text) if rank_text else None
            current_meta = {
                "category": current_category,
                "category_id": current_category_id,
                "category_rank": current_category_rank,
            }
            continue

        if line == "---":
            flush()
            continue

        if is_source_start(line) and current_lines and (line.lower().startswith("http") or line.lower().startswith(FIELD_PREFIXES)):
            current_lines.append(line)
        elif is_source_start(line):
            flush()
            current_meta = {
                "category": current_category,
                "category_id": current_category_id,
                "category_rank": current_category_rank,
            }
            current_lines = [line]
        elif current_lines:
            current_lines.append(line)

    flush()
    return blocks


def block_to_record(index: int, block: dict[str, object]) -> dict[str, object] | None:
    lines = list(block["lines"])  # type: ignore[index]
    text = "\n".join(lines)
    explicit_rank = RANK_RE.search(text)
    category_rank = block.get("category_rank")
    rank = int(explicit_rank.group(1)) if explicit_rank else category_rank
    if not isinstance(rank, int) or rank < 4:
        return None

    title = clean_title(lines[0])
    urls = extract_urls(text)
    url = urls[0] if urls else ""
    if title.lower().startswith("http") and url:
        title = urlparse(url).netloc or title

    data_quality_match = QUALITY_RE.search(text)
    data_quality = int(data_quality_match.group(1)) if data_quality_match else ""
    source_format = extract_by_any_label(lines, ("Format",))
    if not source_format:
        source_format = extract_by_any_label(lines, ("Data availability", "Data Availability"))
    cost = extract_by_any_label(lines, ("Cost",))
    period = extract_by_any_label(lines, ("Period",))
    brief_description = extract_by_any_label(lines, ("Brief Description", "Brief description"))
    highlighted_comment = extract_by_any_label(lines, ("Highlighted Comment", "Comment"))
    notes = extract_by_any_label(lines, ("Notes", "Note"))
    category = str(block.get("category", "Uncategorised"))

    domain = infer_domain(title, category, text)
    source_type = infer_source_type(title, source_format, url, text)
    connection_mode = infer_connection_mode(source_type, source_format, text)
    access_level = infer_access_level(title, cost, text)
    dashboard_use = infer_dashboard_use(domain, title, category, text)

    return {
        "source_id": f"HS{index:03d}",
        "category_id": block.get("category_id", ""),
        "category": category,
        "title": title,
        "rank": rank,
        "data_quality": data_quality,
        "domain": domain,
        "source_type": source_type,
        "url": url,
        "urls": " | ".join(urls),
        "format": source_format,
        "cost": cost,
        "period": period,
        "brief_description": brief_description,
        "highlighted_comment": highlighted_comment,
        "notes": notes,
        "access_level": access_level,
        "connection_mode": connection_mode,
        "dashboard_use": dashboard_use,
        "status": "Catalogued",
    }


def extract_catalog(docx_path: Path) -> list[dict[str, object]]:
    lines = read_docx_lines(docx_path)
    blocks = build_blocks(lines)
    records: list[dict[str, object]] = []
    record_index = 1
    for block in blocks:
        record = block_to_record(record_index, block)
        if record:
            records.append(record)
            record_index += 1
    return records


def write_catalog(records: list[dict[str, object]], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_id",
        "category_id",
        "category",
        "title",
        "rank",
        "data_quality",
        "domain",
        "source_type",
        "url",
        "urls",
        "format",
        "cost",
        "period",
        "brief_description",
        "highlighted_comment",
        "notes",
        "access_level",
        "connection_mode",
        "dashboard_use",
        "status",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract high-score CRDT-Port data sources from the dataset Word file.")
    parser.add_argument("--docx", type=Path, default=DEFAULT_DOCX, help="Path to CRDT data-source Word document.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output CSV path.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT, help="Output JSON path.")
    args = parser.parse_args()

    records = extract_catalog(args.docx)
    write_catalog(records, args.out, args.json_out)
    print(f"Extracted {len(records)} high-score sources to {args.out}")


if __name__ == "__main__":
    main()
