# Existing data connections implementation plan

**Goal:** Make the approved existing-data relationship proposal usable in Monitor while retaining Overview / Monitor / Data and the current engineering-monitoring presentation.

**Architecture:** Preserve original EA identifiers in existing responses. A pure helper builds a small source → returned-record-set → measurement-series → selected-object graph from actual selected raw records. Series and snapshots receive explicitly provisional, deterministic workspace identifiers. A Connections renderer shows this graph, its evidence and missing fields; nearby objects are separate spatial candidates. Partner-declared dependencies remain a separate section using the existing package checks.

**Stack:** Existing Streamlit native Graphviz renderer, pandas and standard-library hashes/JSON; no new dependency, database, request family or model execution.

- [x] Preserve actual EA station/measure/reading URIs and avoid deduplicating distinct measurement references; verify mocked connector regressions without changing request paths/cache policies.
- [x] Implement and test deterministic source/series/record-set relationships, raw conflict preservation, missing metadata, unverified WebTRIS description mapping and original time basis.
- [x] Render the selected object's evidence graph, details and JSON download in Connections; retain exact source/reference/date handoffs and existing dependency-package display.
- [x] Show valid nearby objects as explicitly labelled candidates within a fixed, displayed five-kilometre rule; support inspecting a candidate without manufacturing dependencies or changing source permissions.
- [x] Run focused and full unittest suites; independently review correctness and scope. Verify native graph rendering, downloads, object/reference changes, existing page handoffs and responsive layout in desktop/mobile browsers.
- [x] Update documentation/release marker, push scoped changes without force to the existing GitHub main branch, and observe the deployed version/login surface.

## Acceptance boundaries

No operational dependence, causal influence, datum conversion or cross-timezone alignment is inferred from proximity or synchronised curves. Example assets stay separate. WP1 common guidance and each consumer WP's internal adaptation responsibilities remain. Sources present only in the catalogue (including OSM network layers) are not asserted to be connected. Existing provider caches and password/partner-view boundaries remain. The unrelated untracked visual-navigation-layout.md plan is preserved.
