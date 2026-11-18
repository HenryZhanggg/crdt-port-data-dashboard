# Connected Data Integration Implementation Plan

> For agentic workers: use subagent-driven-development. User approved the proposed design on 18 November 2026; proceed without another design gate.

**Goal:** Connect source intake, explicit semantic linkage, time/quality decisions and traceable model-input handoff within the existing three-page dashboard.

**Architecture:** Reuse existing API/CSV normalisers, snapshot validation, provenance exports and model-input checks. A small pure linkage service applies confirmed common object/concept declarations while retaining source identities and incompatible units/datums separately. Keep source access explicit, session-local and permission-scoped.

**Tech stack:** Existing Python, pandas, Streamlit and Plotly; no new dependency or paid service.

## Task 1: Explicit joint data product
- [x] In integration_product.py, implement integration_bindings(records) and apply_integration_bindings(records, bindings).
- [x] Test unconfirmed and incomplete bindings, exact common meaning across API/CSV, incompatible unit/datum/qualifier separation, provenance, duplicate bindings and conflicting same-time values.
- [x] Run .venv/Scripts/python.exe -m unittest discover -s tests -p test_integration_product.py -q before and after implementation.

## Task 2: Continuous integration workspace
- [x] In integration_views.py, retain current Connected sources / Upload CSV routes and add Combine API + CSV using the same normalised records and recorded intake metadata.
- [x] Add explicit common identity/concept editor before availability checks; original and mapped previews plus linked/unmatched/incompatible outcomes remain inspectable.
- [x] Keep existing decision-time snapshot, audit and model-input builder; export mapping and linkage evidence in existing report rules and downloadable data product.
- [x] In data_views.py, default to Integration, followed by Sources and Quality. Move partner intake into a collapsed section without removing functionality; migrate legacy Partner packages navigation.
- [x] Add meaningful AppTest coverage for combined intake, no implicit fetch, rejected/retained mappings, access scope and package source-failure evidence; run affected existing view tests.

## Task 3: Monitor to integration handoff
- [x] In monitor_workspace.py and workspace_links.py, expose Integrate selected data with exact object/reference/date/permission context.
- [x] Provide workspace_context_summary() for a compact cross-page ribbon; no background fetch, substitution, invented operational links or causal claims.
- [x] Clarify existing relation graph evidence categories in data_relation_views.py; preserve source identity/time evidence and proximity-only candidates.
- [x] Run affected workspace-links, Monitor and relationship view tests.

## Task 4: Navigation and visual hierarchy
- [x] In app.py, retain internal Data route and public deep links; label navigation Data & Integration and retain state safely excluding raw editor/action keys.
- [x] Bump matching app/data/integration build identifiers to2026-11-18.1 and update visible release date.
- [x] In dashboard_theme.py, refine compact graphite/violet workflow/context presentation; keep everyday Overview separate from historical analysis context.
- [x] Run routing, navigation, lock/permission/state tests. Cosmetic CSS requires visual QA, not implementation-mirroring tests.

## Task 5: Verify and publish approved dashboard update
- [x] Update README and docs/data-integration-workbench.md with actual behavior and limitations.
- [x] Run all unit/AppTests, compile touched modules, inspect git diff and request independent spec/code review.
- [x] Exercise protected local app using fixture-only QA where supported; no secrets in output, captures or commits.
- [x] Publish only this task's changes to repository main after verification, preserving unrelated untracked plan. Verify remote revision and deployment response; report any browser verification limitation accurately.

**Boundaries:** No persistent history service, new vendor stack, automatic entity resolution, fabricated historical arrival time, datum conversion, imputation or partner-model execution. These were not required for this bounded update. Formal WP1 approval and receiving-WP scientific acceptance remain separate.

## Verification outcome

- Production code revision: `1581054`; published to repository `main`.
- Build: `2026-11-18.1`. All371 unit/AppTests passed; touched Python modules compile and Git whitespace checks pass.
- Installed Edge headless verified local fixture-only API/CSV mapping, product export, actual connection-node selection, Monitor handoff and current Overview context with no page or Streamlit exceptions. Synthetic QA records are not operational evidence.
- Streamlit was asleep and was awakened. Its public login banner confirmed build2026-11-18.1 at 2026-11-18T14:17:17.718324+00:00.
- The protected deployed workspace was not signed into: no local dashboard password was available. Its functionality was exercised locally; authenticated cloud verification remains an owner-session check. No password was printed, stored or changed.
- QA records/screenshots remain local and were excluded from publication. Formal WP1 mapping approval, source temporal-meaning acceptance and partner model validation remain separate.
