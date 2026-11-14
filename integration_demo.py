"""Illustrative partner handovers; metadata checks never approve or invoke models."""
import math


DEMO_CASES = {
    "shared_view": "Shared viewing only",
    "aligned": "Aligned illustrative handover",
    "missing_input": "Missing provider input",
    "missing_baseline": "Missing baseline capacity",
    "reference_mismatch": "Same unit, different capacity reference",
    "time_mismatch": "Different time basis",
    "dynamic_feedback": "Dynamic feedback requires design agreement",
}
_EXPRESSION = "usable_capacity = availability_ratio * baseline_capacity"


def get_demo_connection(case_id: str) -> dict:
    """Return a fresh, data-only fixture; no partner package is imported."""
    if case_id not in DEMO_CASES:
        raise ValueError("Unknown integration demo case.")
    common = {
        "version": "illustrative-1", "entity_id": "demo:facility_a",
        "ontology_version": "example-unapproved-1", "reference": "demo:nominal_capacity_v1",
        "time_basis": "2026-11-14T12:00Z/2026-11-14T13:00Z; hourly mean",
        "spatial_scope": "demo:facility_a footprint", "scenario_id": "demo:disruption_a",
    }
    connection = {
        "connection_id": f"demo:{case_id}", "title": DEMO_CASES[case_id],
        "status": "DEMO DRAFT", "mode": "handover",
        "notes": "Illustrative metadata and values, not a CRDT result or approved ontology. Partner models are not connected.",
        "source": dict(common, model_id="demo:facility_availability_model", wp="WP3",
                       variable="availability_ratio", unit="1", value=0.8,
                       evidence_ref="demo:illustrative_availability_note"),
        "target": dict(common, model_id="demo:service_capacity_model", wp="WP4",
                       variable="usable_capacity", unit="t/h", value=None,
                       evidence_ref="demo:illustrative_input_requirement"),
        "baseline": {"value": 1000, "unit": "t/h", "reference": common["reference"],
                     "evidence_ref": "demo:illustrative_nominal_capacity_note"},
        "adapter": {"id": "availability_times_baseline_v1", "expression": _EXPRESSION, "declared": True},
        "acceptance": {"provider": "Pending", "consumer": "Pending"},
    }
    if case_id == "shared_view":
        connection["mode"] = "view_only"
        connection["adapter"]["declared"] = False
    elif case_id == "missing_input":
        connection["source"]["value"] = None
    elif case_id == "missing_baseline":
        connection["baseline"]["value"] = None
    elif case_id == "reference_mismatch":
        connection["target"]["reference"] = "demo:another_nominal_capacity_v2"
    elif case_id == "time_mismatch":
        connection["target"]["time_basis"] = "2026-11-14T00:00Z/2026-11-15T00:00Z; daily mean"
    elif case_id == "dynamic_feedback":
        connection["mode"] = "dynamic"
    return connection


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def check_connection(connection: dict) -> list[dict]:
    """Check this one declared adapter; Pass means matching demo metadata only."""
    source, target = connection.get("source") or {}, connection.get("target") or {}
    baseline, adapter = connection.get("baseline") or {}, connection.get("adapter") or {}
    provider, consumer = source.get("wp") or "Provider WP", target.get("wp") or "Consumer WP"
    joint = f"{provider} + {consumer}"
    checks = []

    def add(name, valid, detail, owner=joint):
        checks.append({"check": name, "status": "Pass" if valid else "Blocked", "detail": detail, "owner": owner})

    mode = connection.get("mode")
    if mode == "handover":
        add("Connection mode", True, "Explicit provider output to consumer input declaration; no automatic model execution.")
    elif mode == "view_only":
        checks.append({"check": "Connection mode", "status": "Review", "owner": joint,
                       "detail": "Shared viewing only: two results on one screen do not create a model chain."})
    else:
        add("Connection mode", False,
            "Dynamic coupling needs time step, feedback direction, convergence and failure handling agreed by both model teams."
            if mode == "dynamic" else "Choose an explicit supported connection mode.")
    ratio = source.get("value")
    valid_ratio = _finite(ratio) and 0 <= ratio <= 1
    add("Provider value", valid_ratio,
        "Finite availability_ratio within [0, 1]." if valid_ratio else
        "A finite availability_ratio within [0, 1] is required; missing input stays missing and blocks downstream stages.", provider)
    fields = ["model_id", "version", "wp", "evidence_ref"]
    missing = [f"{side}.{field}" for side, record in [("source", source), ("target", target)]
               for field in fields if not _text(record.get(field))]
    add("Model provenance", not missing,
        "Declared model IDs, versions, WP responsibilities and evidence references present; not independently verified."
        if not missing else "Missing declaration: " + ", ".join(missing))
    for field, name in [("entity_id", "Entity identity"), ("ontology_version", "Ontology version"),
                        ("scenario_id", "Scenario"), ("spatial_scope", "Spatial scope"), ("time_basis", "Time basis")]:
        left, right = source.get(field), target.get(field)
        matches = _text(left) and left == right
        add(name, matches, f"Declared {field}: provider={left!r}; consumer={right!r}. "
            + ("Exact match; authority and scientific suitability still require partner review." if matches else
               "Nonempty matching declarations required; no implicit aggregation or mapping."))
    units = source.get("unit") == "1" and target.get("unit") == baseline.get("unit") == "t/h"
    add("Units", units, "This adapter requires ratio unit 1 and target/baseline t/h; it does not infer conversions.")
    reference = source.get("reference")
    references_match = _text(reference) and reference == target.get("reference") == baseline.get("reference")
    add("Capacity reference", references_match,
        f"Provider={reference!r}; consumer={target.get('reference')!r}; baseline={baseline.get('reference')!r}. "
        "All must identify the same declared nominal capacity; equal units alone are insufficient.")
    value = baseline.get("value")
    baseline_ok = _finite(value) and value > 0 and _text(baseline.get("evidence_ref"))
    add("Baseline capacity", baseline_ok,
        "Positive finite nominal capacity and evidence reference declared; use only the agreed capacity reference."
        if baseline_ok else "Positive finite baseline capacity with evidence is required; no default capacity is supplied.", consumer)
    adapter_ok = (adapter.get("declared") is True and adapter.get("id") == "availability_times_baseline_v1"
                  and adapter.get("expression") == _EXPRESSION and source.get("variable") == "availability_ratio"
                  and target.get("variable") == "usable_capacity")
    if mode == "view_only":
        checks.append({"check": "Declared adapter", "status": "Review", "owner": consumer,
                       "detail": "Shared viewing needs no adapter; no output-to-input mapping is activated."})
    else:
        add("Declared adapter", adapter_ok,
            "Illustrative declared mapping only: availability_ratio * baseline_capacity -> usable_capacity. "
            "The consumer WP must confirm the domain assumption; expressions are never evaluated as code.", consumer)
    checks.append({"check": "Provider and consumer acceptance", "status": "Review", "owner": joint,
                   "detail": "Pending provider and consumer scientific acceptance. Demo declarations cannot grant approval, "
                             "including when all technical metadata checks pass."})
    return checks


def connection_summary(checks: list[dict]) -> str:
    """Describe metadata readiness separately from acceptance and model execution."""
    if not checks:
        return "Blocked: no connection checks available. Partner models are not connected."
    blocked = [row["check"] for row in checks if row["status"] == "Blocked"]
    if blocked:
        return "Blocked: " + "; ".join(blocked) + ". Downstream handover stops; partner models are not connected."
    if any(row["check"] == "Connection mode" and row["status"] == "Review" for row in checks):
        return "Shared viewing only; no model chain is declared. Partner models are not connected."
    return "Illustrative technical metadata checks pass. Provider and consumer acceptance remains Pending; partner models are not connected."


def execution_preview(connection: dict, checks: list[dict]) -> list[dict]:
    """Preview dependencies and one fixed illustrative multiplication, never a run."""
    source, target = connection.get("source") or {}, connection.get("target") or {}
    provider, consumer = source.get("wp") or "Provider WP", target.get("wp") or "Consumer WP"
    current = check_connection(connection)
    by_name = {row["check"]: row["status"] for row in current}
    source_ok = by_name["Provider value"] == by_name["Model provenance"] == "Pass"
    mode = connection.get("mode")
    technical_ok = bool(checks) and not any(row["status"] == "Blocked" for row in checks + current)
    stages = [{"stage": "Provider output", "owner": provider, "status": "Pass" if source_ok else "Blocked",
               "reason": "Illustrative output available; no provider model was invoked." if source_ok else
                         "Required provider value or provenance missing/invalid; no zero filling."}]
    if mode == "view_only":
        adapter_status, adapter_reason = "Review", "Shared viewing has no output-to-input adapter execution."
        handover_status, handover_reason = "Blocked", "Shared display does not create a consumer input handover."
    elif technical_ok and mode == "handover":
        value = source["value"] * connection["baseline"]["value"]
        adapter_status, adapter_reason = "Pass", f"Illustrative fixed multiplication gives {value:g} t/h; this is not a model result."
        handover_status, handover_reason = "Review", "Technical declaration matches; Pending provider and consumer scientific acceptance."
    else:
        adapter_status, adapter_reason = "Blocked", "Upstream declaration/checks block the adapter; no substitute value is computed."
        handover_status, handover_reason = "Blocked", "Dependency blocked; resolve the failed checks before a consumer handover."
    stages.extend([
        {"stage": "Declared adapter", "owner": consumer, "status": adapter_status, "reason": adapter_reason},
        {"stage": "Consumer input handover", "owner": consumer, "status": handover_status, "reason": handover_reason},
        {"stage": "Partner model execution", "owner": f"{provider} + {consumer}", "status": "Blocked",
         "reason": "Partner models are not connected; no executable interface, model invocation or scientific approval is supplied."},
    ])
    return stages


def get_handover_template() -> dict:
    """Return a draft for partner completion, without populating partner claims."""
    template = get_demo_connection("aligned")
    template.update(connection_id="", title="Partner connection draft", status="DRAFT - partner completion required",
                    notes="Draft for partner discussion; no CRDT result, ontology approval or model execution.")
    for side in ["source", "target"]:
        template[side] = {field: None if field == "value" else "" for field in template[side]}
    template["baseline"] = {"value": None, "unit": "", "reference": "", "evidence_ref": ""}
    template["adapter"] = {"id": "", "expression": "", "declared": False}
    template.update(
        responsible_contacts={side: {"name": "", "organization": "", "contact": ""}
                              for side in ["provider", "consumer"]},
        purpose={"intended_use": "", "decision_context": ""},
        data_requirements={"required_inputs": [], "expected_outputs": [], "temporal_resolution": "", "spatial_resolution": ""},
        quality_policy={"quality_criteria": "", "missing_data_policy": "", "error_handling": ""},
        access_use_terms={"access_method": "", "licence": "", "use_terms": "", "restrictions": ""},
        verification_acceptance={"verification_method": "", "acceptance_criteria": "",
                                 "provider_status": "Pending", "consumer_status": "Pending"},
        execution_requirements={"trigger": "", "sequence": "", "interface": "", "failure_policy": ""},
        provenance_versions={"input_versions": [], "model_versions": [], "adapter_version": "", "review_record": ""},
    )
    return template
