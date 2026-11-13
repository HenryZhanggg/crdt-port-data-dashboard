# CRDT-Port Modular Workbench Implementation Plan

**Goal:** Update the existing Streamlit application into the agreed map-led workbench, with shared inspection, optional panels, deeper analysis and accountable WP module handovers.

**Architecture:** Retain the current connectors, authentication, date limits, per-view fetching, monitoring diagnostics, offline research and report exports. Add a small WP registry, pure workspace identity/selection helpers and validated session-local partner packages. Compose these with existing views; use the current Streamlit runtime and dependencies.

**Tech stack:** Python, Streamlit 1.57.0, pandas, Plotly, pydeck, existing RDF/SHACL support. No new production dependency.

## Scope and baseline

- Isolated checkout: `.worktrees/crdt-port-data-dashboard`, branch `codex/modular-workbench`, starting commit `0708bf9`.
- Baseline: 37 unittest cases pass. Password remains before data loading. Existing partner selection remains prototype navigation, not institutional authorisation.
- Current capabilities are observations and archived research. Formal project ontology, operational dependency instances, live crisis models, recovery optimisation and production identity management must retain explicit pending status.

## Task 1: Module registry and partner result contracts

Files: `module_contracts.py`, `data/wp_modules.json`, `tests/test_module_contracts.py`, `docs/module-integration.md`.

- [x] Add failing tests for unknown module/artifact, missing metadata, non-finite/bool results, timezone-unaware times, bad dependency references/intervals, empty packages and incompatible run comparisons.
- [x] Implement the seven WP handover records; distinguish app implementation state from partner scientific readiness.
- [x] Validate session-local `model_run` and `dependencies` JSON packages. Never fetch uploaded URLs or execute uploaded code. Run output evidence stays simulated/forecast/estimated; dependency assertions retain their declared evidence.
- [x] Compare only matching entity, metric, unit and valid time; preserve unmatched outputs without zero filling.
- [x] Document a minimal partner handover and an illustrative, explicitly marked template.

## Task 2: Shared entity and selection helpers

Files: `workbench_data.py`, `tests/test_workbench_data.py`.

- [x] Add failing tests covering water/traffic/demo distinction, exact water reference freshness, missing coordinates and hidden/removed selection.
- [x] Build stable source-derived workspace IDs, not claimed WP1 canonical IDs. Water station identity is stable; its displayed measurement reference carries unit and datum separately.
- [x] Keep traffic with no returned observations a reference location, and demo assets a sample. Avoid deriving risk from quality or sample status.
- [x] Resolve map selection and fallback selection predictably, without stale map clicks overriding a newer user choice.

## Task 3: Workbench UI and deeper workspaces

Files: `workbench_views.py`, `app.py`, `monitoring_views.py`, `.streamlit/config.toml`, `tests/test_workbench_views.py`.

- [x] Add AppTest assertions for the map workbench, all new navigation routes, empty feeds, selection, partner restrictions and pending model states.
- [x] Implement map + shared inspector + selectable panel grid; use clear scope/time and source-evidence labels. Add quick navigation to objects/dependencies, scenarios/runs, data/evidence and WP handovers.
- [x] Reuse Explorer, Transport, Quality, Research/Replay and Report Centre; preserve existing source-specific requests and all legacy destinations.
- [x] Add relationship-package inspection, imported-run inspection/comparison, four demonstrator task presets and a WP module handover catalogue. Imports stay in the authorised user's current session and do not certify scientific validity.
- [x] Preserve password gate, lock, refresh, date validation and existing prototype partner navigation. Scenario browsing never launches a model implicitly.

## Task 4: Verification, review and delivery

Files: `README.md`, tests as needed; QA screenshots remain outside deployment inputs.

- [x] Run the complete unittest suite, compile checks and dependency checks. Resolve substantive regressions. Final run: 89 tests passed; compile and pip checks passed.
- [x] Run the application locally, inspect desktop and narrow layouts in the browser. New workspaces and 390px overflow checked in CUA; empty feeds and retained research/export routes covered by AppTest.
- [x] Obtain independent code/spec review; address important findings and repeat affected checks.
- [x] Commit only intended code/docs/tests. Checked remote main for concurrent changes and used a normal fast-forward push. Main application change: `54a6cd9`.
- [x] Verify the existing Streamlit URL updates. The deployed title is now `CRDT-Port | Resilience Workbench`; the existing password gate remains. Protected interior was verified locally, not unlocked on production.

## Verification record

Final code checks: 89 unittest cases passed, Python compilation passed, `pip check` passed and `git diff --check` passed. Independent contract/identity, UI and deployment-readiness reviews were completed and important findings resolved. CUA inspected the live-data local workbench, object/dependency, run, module, demonstrator and governance routes; a 390px-wide viewport had no horizontal page overflow. Production URL: https://crdt-port-data-dashboard.streamlit.app/.
