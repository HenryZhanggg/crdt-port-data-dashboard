# Monitoring, Data Quality and Visuals Implementation Plan

**Goal:** Make observation freshness, selected time coverage and tide-gauge compatibility visible, with clearer monitoring charts and a spatial view.

**Architecture:** Keep the existing Streamlit app and catalogue. Add pure data-quality functions and a small SOSA ontology with SHACL validation; render the monitoring views in a separate module. Pass the selected date range into EA and WebTRIS requests.

**Tech Stack:** Streamlit, pandas, Plotly, pydeck, RDFLib, pySHACL, unittest.

- [x] Add tests for UTC date filtering, stale/sample/future timestamps, gaps and incompatible tide datums. Verified the initial missing-module failure before implementation.
- [x] Implement the quality functions, SOSA instance mapping and SHACL shapes. Tested missing datum, contradictory mAOD datum and missing coordinates.
- [x] Parameterise observation requests and test dates with fake API responses. Verified 268 actual EA observations and their measure definitions.
- [x] Add overview coverage charts, selectable map layers, independent weather charts, station-specific water charts and a Data Quality view.
- [x] Pass 13 unit/AppTest tests, compile source and validate all 268 actual observations. Browser checks pass for Overview, Weather, GIS, Data Quality and mobile overflow; screenshots inspected.
- [x] Update README and publisher inputs; build and integrity-check the source ZIP with a SHA-256 file manifest.
- [ ] Publish the existing cloud deployment. Blocked by unavailable non-interactive GitHub write authentication; source package and local preview are ready.

Freshness describes observation age, not API connectivity. Historical statistics and demonstration data remain identified as such. No model inference or asset-risk claims are added in this iteration.
