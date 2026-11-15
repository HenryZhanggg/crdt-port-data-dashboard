# Shared context and source freshness implementation plan

> For agentic workers: use subagent-driven-development with separate ownership and review. User approved improvement points 1 and 2, and requested a grounded proposal for relationships between existing datasets.

**Goal:** Preserve object, measurement reference, source and dates when moving between the three workspaces, and make source/measurement freshness visible without opening technical details.

**Architecture:** Small callback-driven handoff dictionaries carry source-derived identifiers and explicit reference fields. Target views validate supplied context against returned records and existing partner navigation permissions. Freshness UI uses existing cached metadata, preserving the distinction between retrieval, publication, forecast-valid and observation times. The relationship proposal is research documentation, not automatic creation of dependencies.

**Tech stack:** Existing Streamlit, pandas, Pydeck and Plotly; no new runtime dependencies.

## Tasks

- [x] Add workspace_links.py pure context builders and callbacks. Overview water references open Monitor Connected observations with the same station/unit/datum and available UTC dates. Do not infer identity from names or coordinates.
- [x] Add Monitor-to-Data source/quality actions and selected-reference/counter filters. Preserve historical window and source metadata in previews and CSV/report/Turtle exports. Clear context explicitly or when users intentionally select another source/table/scope.
- [x] Retain permissions, widget-state and native map-selection boundaries. Missing requested references must be explained instead of silently substituted. Example objects remain isolated from real observation handoffs.
- [x] Add explicit station_reference to normalised daily water references, retaining current composite IDs for compatibility.
- [x] Show per-source check/publication/observation ages and forecast-valid times next to daily summaries. Surface unavailable, stale observations and link-only sources. Remove the implication that one maximum check timestamp applies to all sources.
- [x] Keep official reminders/notice and travel links discoverable before group news. Unknown validity does not imply an active alert; old RSS publication does not alone prove a failed feed. Retain dated history and all source licensing.
- [x] Write and verify a source-grounded draft of existing identity, observation, spatial, temporal, provenance and domain-dependency links. Record actual fields, existing adapter losses and required WP confirmations; do not fabricate causal relationships.
- [x] Run meaningful helper/AppTest regressions and the full unittest suite; verify real-reference handoffs, missing-reference handling, permission changes, mixed source freshness and existing exports.
- [x] Browser QA desktop/mobile with local controlled inputs. Independently review requirements and code quality, fix findings, then non-force push and observe the updated Streamlit version/login surface.

## Preservation boundaries

Keep Overview / Monitor / Data, current design and source cache policies. No new external contacts, user registrations, remote model execution or uploads to partners. MET retrieval remains cached for three hours; a source freshness label causes no extra request. Do not modify funding monitoring, original scientific data or unrelated untracked visual-navigation-layout.md.
