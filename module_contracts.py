"""WP handovers and data-only partner packages; validation does not certify science."""
import json
import math
from pathlib import Path
import re

import pandas as pd


def load_module_registry() -> list[dict]:
    """Read the bundled prototype capability inventory, independently of uploads."""
    return json.loads((Path(__file__).parent / "data" / "wp_modules.json").read_text(encoding="utf-8"))


def _strings(record, fields, path):
    if not isinstance(record, dict):
        raise ValueError(f"{path} must be a JSON object.")
    result = {}
    for field in fields:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path}.{field} must be a nonempty string.")
        result[field] = value
    return result


def _choice(record, field, choices):
    value = record.get(field)
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{field} must be one of {', '.join(sorted(choices))}.")
    return value


def _records(record, field, limit=5000):
    values = record.get(field)
    if not isinstance(values, list) or not values:
        raise ValueError(f"{field} must be a nonempty list.")
    if limit is not None and len(values) > limit:
        raise ValueError(f"{field} must contain at most {limit} records.")
    return values


def _utc(value, field):
    # A restricted ISO form avoids pandas' permissive natural-language parsing.
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:\d{2})"
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError(f"{field} must be an ISO timestamp with an explicit timezone.")
    try:
        return pd.Timestamp(value).tz_convert("UTC").isoformat()
    except (ValueError, OverflowError) as error:
        raise ValueError(f"{field} must be a valid timezone-aware ISO timestamp.") from error


def validate_package(payload: dict) -> dict:
    """Return independent, validated contract fields with UTC times or raise ValueError.

    Extra fields are omitted. IDs, ontology versions and provider validation claims
    remain declarations; no URL, code, identity authority or external service is used.
    """
    result = _strings(payload, ["schema_version", "module_id", "artifact_type", "ontology_version"], "package")
    if result["schema_version"] != "1.0":
        raise ValueError("schema_version must be 1.0.")
    kind = _choice(payload, "artifact_type", {"model_run", "dependencies"})
    result["generated_at"] = _utc(payload.get("generated_at"), "generated_at")
    if "notes" in payload:
        if not isinstance(payload["notes"], str):
            raise ValueError("notes must be a string.")
        result["notes"] = payload["notes"]
    if kind == "model_run":
        _choice(payload, "module_id", {"WP3", "WP4", "WP5"})
        result.update(_strings(payload, ["scenario_id", "run_id", "model_name", "model_version"], "package"))
        result["evidence_role"] = _choice(payload, "evidence_role", {"simulated", "forecast", "estimated"})
        result["validation_status"] = _choice(payload, "validation_status", {"unvalidated", "validated_by_provider"})
        result["input_products"] = [_strings(row, ["product_id", "version"], "input_products")
                                    for row in _records(payload, "input_products", limit=None)]
        result["outputs"] = []
        for row in _records(payload, "outputs"):
            output = _strings(row, ["entity_id", "metric", "unit"], "outputs")
            value = row.get("value")
            finite = (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and math.isfinite(value))
            if not finite:
                raise ValueError("outputs.value must be a finite number, not a boolean.")
            output.update(value=value, valid_time=_utc(row.get("valid_time"), "outputs.valid_time"))
            result["outputs"].append(output)
    else:
        _choice(payload, "module_id", {"WP4"})
        result.update(_strings(payload, ["dataset_id", "version"], "package"))
        result["evidence_role"] = _choice(payload, "evidence_role", {"declared", "inferred", "simulated"})
        result["relationships"] = []
        for row in _records(payload, "relationships"):
            relationship = _strings(row, ["source_id", "target_id", "relation_type", "evidence_ref"], "relationships")
            if relationship["source_id"] == relationship["target_id"]:
                raise ValueError("Dependency source_id and target_id must differ.")
            relationship["direction"] = _choice(row, "direction", {"directed", "bidirectional"})
            relationship["valid_from"] = _utc(row.get("valid_from"), "relationships.valid_from")
            if "valid_to" not in row:
                raise ValueError("relationships.valid_to is required; use null for an open interval.")
            relationship["valid_to"] = None if row["valid_to"] is None else _utc(row["valid_to"], "relationships.valid_to")
            if relationship["valid_to"] is not None and pd.Timestamp(relationship["valid_to"]) <= pd.Timestamp(relationship["valid_from"]):
                raise ValueError("relationships.valid_to must be after valid_from.")
            result["relationships"].append(relationship)
    return result


def compare_run_outputs(left: dict, right: dict) -> pd.DataFrame:
    """Outer-join exact output references and calculate B minus A only for matches."""
    left, right = validate_package(left), validate_package(right)
    if left["artifact_type"] != "model_run" or right["artifact_type"] != "model_run":
        raise ValueError("Comparison requires two model_run packages.")
    if left["ontology_version"] != right["ontology_version"]:
        raise ValueError("Comparison requires the same ontology_version.")
    keys = ["entity_id", "metric", "unit", "valid_time"]
    frames = []
    for package, suffix in [(left, "a"), (right, "b")]:
        frame = pd.DataFrame(package["outputs"], dtype=object)
        if frame.duplicated(keys).any():
            raise ValueError(f"Duplicate output reference in run {package['run_id']}.")
        frames.append(frame.rename(columns={"value": f"value_{suffix}"}))
    result = frames[0].merge(frames[1], on=keys, how="outer", validate="one_to_one", indicator=True)
    deltas = []
    for value_a, value_b, state in zip(result["value_a"], result["value_b"], result["_merge"]):
        if state != "both":
            deltas.append(float("nan"))
            continue
        try:
            delta = value_b - value_a
        except OverflowError as error:
            raise ValueError("Comparison delta must be finite; numeric range exceeded.") from error
        if isinstance(delta, float) and not math.isfinite(delta):
            raise ValueError("Comparison delta must be finite; numeric range exceeded.")
        deltas.append(delta)
    result["delta"] = pd.Series(deltas, index=result.index, dtype=object)
    result["state"] = result["_merge"].astype(str).map({"both": "Matched", "left_only": "A only", "right_only": "B only"})
    return result[keys + ["value_a", "value_b", "delta", "state"]]


def package_template(kind: str) -> dict:
    """Create an illustrative download; callers must never import it implicitly."""
    common = {"schema_version": "1.0", "artifact_type": kind, "ontology_version": "example-unapproved-1",
              "generated_at": "2026-11-13T12:00:00Z", "notes": "Illustrative integration template, not a CRDT result"}
    if kind == "model_run":
        return dict(common, module_id="WP3", scenario_id="demo:weather", run_id="demo:run_a",
                    model_name="Example model", model_version="example-1", evidence_role="simulated",
                    validation_status="unvalidated", input_products=[{"product_id": "demo:input", "version": "1"}],
                    outputs=[{"entity_id": "demo:terminal_a", "metric": "demo:service_loss", "value": 10,
                              "unit": "%", "valid_time": "2026-11-13T13:00:00Z"}])
    if kind == "dependencies":
        return dict(common, module_id="WP4", dataset_id="demo:dependencies", version="example-1", evidence_role="declared",
                    relationships=[{"source_id": "demo:terminal_a", "target_id": "demo:road_a",
                                    "relation_type": "demo:requires_access", "direction": "directed",
                                    "evidence_ref": "demo:provider_note", "valid_from": "2026-11-13T12:00:00Z", "valid_to": None}])
    raise ValueError("Template kind must be model_run or dependencies.")
