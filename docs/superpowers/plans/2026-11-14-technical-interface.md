# Technical Interface Refresh Implementation Plan

**Goal:** Implement the previously presented engineering-monitoring interface in the existing CRDT-Port Streamlit dashboard.

**Design basis:** User selected the engineering-monitoring variant and requested a more technical interface. Use navy chrome, neutral work surfaces, teal accents, compact native controls, a shared object inspector and consistent evidence metadata. Keep all current source, identity, model, package, authorisation and scientific meanings.

**Architecture:** Retain Streamlit 1.57 and the existing native widget keys/callbacks. Change shared presentation in `app.py`, `workbench_views.py`, `monitoring_views.py` and `.streamlit/config.toml`. No new dependencies or data feeds.

## Tasks and verification

- [x] Inspect shared styles, overview composition, authorisation order, date controls and navigation. Verify clean remote baseline and run all 89 existing unittest cases.
- [x] Add a focused AppTest for truthful recent-observation labelling and historical date controls; confirm the original label fails the test, then passes after implementation. Existing tests cover optional-panel persistence.
- [x] Replace the large overview title with a compact navy identity header; put native time/date controls and refresh in one toolbar. Preserve date limits and cache-clearing behaviour. Keep all shortcuts and sidebar routes.
- [x] Apply neutral flat surfaces, thin borders, compact panel spacing, readable monospace values and a shared Plotly treatment. Preserve focus outlines, responsive wrapping, labels and touch targets.
- [x] Put existing summary metrics before the map; keep map/inspector selection and move the selected-observation chart directly beneath the map. Keep optional panel controls in a collapsed expander and retain their state.
- [x] Show concise inspector metadata for observation time, unit/datum and source, with full provenance in its existing expander. Render any data-derived HTML through escaping.
- [x] Run all unittest cases, compilation, `pip check` and `git diff --check`. Inspect authenticated local desktop and 390px layouts, native controls, navigation and password gate. Save review screenshots outside deployment inputs.
- [x] Review the final diff independently, address material issues and update README. Confirm remote main still matches the starting commit and existing repository push access remains available.

## Verification record

Streamlit 1.57.0: 90 unittest cases passed, compilation passed and `pip check` found no broken requirements. The added AppTest failed on the previous mode label before implementation. Independent review found no auth/state/escaping blockers; its documentation note was resolved. Local CUA inspection verified the password gate, real EA observations, desktop map/inspector, model and module routes, mobile chart layout, two-column metrics and wrapping shortcuts. At 390px the document width was 390px and the main scroll width equalled its client width. The desktop brand begins below the native toolbar. Screenshots are held outside deployment inputs in `outputs/dashboard-technical-20261114` in the parent workspace.

Delivery uses a normal push to existing remote main. Production protected-interior verification requires the real dashboard password and is separate from authenticated local QA.

## Scope boundaries

No invented operational risk, automatic polling, inferred dependencies, new model execution or completed-WP claims. The recent-observation mode is a query window; scientific data states remain separate. No credentials or captured observation payloads in commits. The active isolated checkout is `.worktrees/crdt-port-data-dashboard`; do not change unrelated workspace research or funding files.
