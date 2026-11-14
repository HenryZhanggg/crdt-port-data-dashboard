# Partner module integration

The workbench accepts data-only JSON handovers for partner model outputs and cross-sector relationships. Importing a package puts validated content in the current authorised user's Streamlit session. It does not run a model, fetch an evidence URL, execute uploaded code or publish the upload. Templates are downloads for integration work; they must never be installed as imported results automatically.

`data/wp_modules.json` records WP1–WP7 inputs, outputs, task references, responsibilities, available prototype capabilities and pending partner deliverables. Task references follow the 17 September 2025 Gantt. The distributed adaptation proposal was revised on 14 November 2026: WP1 supplies common guidance, WP2 supplies source access and quality evidence, and each consuming WP owns its internal semantic adaptation, input construction and scientific verification. WP2 adapts its own monitoring module. Gantt institution labels describe the listed task participants; they do not appoint a new software integration lead or establish current completion. WP5 ID50 has no independent T number or developer label. WP3 includes T3.0 and has no T3.5 in that source. Hosting, software integration, shared frontend and ID50 implementation owners still need agreement.

## Ontology guided main page demo

Overview is the default semantic demonstration. Its local RDF types/labels determine object navigation; declared relation instances and validity determine matching connections; class-to-view profiles and object/time/scenario context determine displayed products. Map picks, graph picks and related-object buttons update the same demo selection. The date defaults to the fixed sample day of 14 November 2026, while real monitoring keeps separate current/historical controls under Live Monitoring.

The demonstration vocabulary and entities are in `ontology/semantic_demo.ttl`. Products, profiles, scenarios and non-executable model descriptors are in `data/semantic_demo.json`. All entities, relationships, coordinates, values and evidence sources are explicitly illustrative. Product gaps remain missing. The semantic loader only reads fixed package-local files and exposes no uploaded-query/code/endpoint execution. Formal WP1 alignment and real model integration require partner handovers.

The former Integration Demo page, shortcut, files and dedicated tests have been retired. Partner JSON result/dependency intake described below is retained. The main demo never imports its fixtures into partner session packages.

For real integration, each connection still requires provider/consumer agreement about the exact output and input, identity, meaning, units/reference, time/space, adaptation, missing/error policy, provenance, permitted use, verification and acceptance. The provider explains/verifies its output; the consumer owns model-entry adaptation unless another assignment is explicitly agreed. WP4 T4.4 coordinates interoperability and WP3 T3.8 coordinates executable chains. Software integration, shared frontend, ID50 development and operations implementers require explicit appointment.

## Minimum handover

Provide the product and version, responsible provider, inputs and outputs, entity identifiers, units and time basis, evidence and quality, applicable conditions, access/use terms, receiving team and acceptance method. The JSON contracts below carry the small subset needed for inspection; provide the remaining governance and scientific evidence through the agreed partner handover process.

All identifiers and ontology versions remain provider declarations. Schema validation does not establish WP1 terminology approval, canonical identity, domain-confirmed dependencies, model accuracy or institutional acceptance. `validated_by_provider` is a provider claim, not project acceptance. A run may describe simulated, forecast or estimated outputs; it cannot label model outputs as observations.

## Model result package

Required top-level fields:

| Field | Contract |
| --- | --- |
| `schema_version` | `"1.0"` |
| `module_id` | `"WP3"`, `"WP4"` or `"WP5"` |
| `artifact_type` | `"model_run"` |
| `scenario_id`, `run_id` | Nonempty provider identifiers |
| `model_name`, `model_version`, `ontology_version` | Nonempty strings |
| `generated_at` | ISO timestamp with an explicit timezone |
| `input_products` | Nonempty list of objects, each with nonempty `product_id` and `version` |
| `evidence_role` | `"simulated"`, `"forecast"` or `"estimated"` |
| `validation_status` | `"unvalidated"` or `"validated_by_provider"` |
| `outputs` | 1–5000 output objects |
| `notes` | Optional string |

Each output requires nonempty `entity_id`, `metric` and `unit`, finite numeric `value` (booleans are rejected), and timezone-aware ISO `valid_time`. Units and metric meanings must be agreed by providers and consumers; the prototype performs no unit, datum or semantic conversion.

## Dependency package

Required top-level fields are `schema_version: "1.0"`, `module_id: "WP4"`, `artifact_type: "dependencies"`, nonempty `dataset_id`, `version` and `ontology_version`, timezone-aware ISO `generated_at`, `evidence_role` and 1–5000 `relationships`. Evidence role is `"declared"`, `"inferred"` or `"simulated"`; optional `notes` is a string.

Each relationship requires nonempty `source_id`, `target_id`, `relation_type` and `evidence_ref`, `direction: "directed"` or `"bidirectional"`, timezone-aware ISO `valid_from` and an explicit `valid_to`. Use JSON `null` for an open interval; a supplied end must be later than the start. Self-dependencies are rejected. An evidence reference is retained as text and is never fetched. The prototype cannot verify that an endpoint exists in a partner's authoritative asset inventory or that the relationship is scientifically confirmed.

## Validation and comparison APIs

```python
from module_contracts import (
    compare_run_outputs, load_module_registry, package_template, validate_package,
)

registry = load_module_registry()  # seven handover records
validated = validate_package(uploaded_json)  # ValueError on invalid content
comparison = compare_run_outputs(run_a, run_b)
illustrative_download = package_template("model_run")
```

`validate_package` returns an independent copy of recognised, validated fields. Extra fields are omitted, and timestamps are normalised to UTC without mutating the input. Supported ISO forms use `YYYY-MM-DDTHH:MM[:SS[.fraction]]Z` or a `+/-HH:MM` timezone offset; fractions may contain up to nine digits. It reads no secrets and performs no network or file access. `load_module_registry` reads only the bundled registry.

`compare_run_outputs` accepts model runs from different scenarios so a baseline can be compared with an intervention. Both must declare the same `ontology_version`. It matches exactly on `entity_id`, `metric`, `unit` and UTC-normalised `valid_time`. Equivalent timezone offsets match; different units or valid times remain separate rows. Duplicate matching keys within either run are rejected to avoid a many-to-many join.

The returned DataFrame columns are `entity_id`, `metric`, `unit`, `valid_time`, `value_a`, `value_b`, `delta`, `state`. `delta` is B minus A for `Matched` rows. `A only` and `B only` rows retain a missing opposite value and missing delta; absence is never replaced with zero. An exact-key match and shared ontology version do not establish that model assumptions, evidence roles or model versions are scientifically comparable. Display the A/B scenario and model metadata with the comparison.

## Illustrative templates

`package_template("model_run")` and `package_template("dependencies")` each return a fresh, valid example with this exact note:

> Illustrative integration template, not a CRDT result

The model example uses `demo:terminal_a`, an example ontology version and unvalidated simulated output. The dependency example connects demo identifiers and declares its evidence. Providers should replace the illustrative values and retain their actual evidence status. Downloading or viewing these templates does not import them into the session, and template validation does not turn them into project results.

The present application provides a prototype shared shell and SOSA checks (WP1), existing data and monitoring (WP2), result import/display (WP3), dependency import/display (WP4), visualisation inspection (WP5), four task presets (WP6) and governance handover records (WP7). Formal WP1 ontology, live inference, verified operational dependencies, security models, production institutional authorisation, completed demonstrations and enforced institutional policies remain pending.
