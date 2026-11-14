# Maritime Map Refresh

**Goal:** Give the deployed monitoring and GIS maps a coherent maritime palette, readable sensor labels and linked selection.

**Approach:** Retain Streamlit/pydeck and all real coordinates, datum/freshness rules and source-derived IDs. Share a small native map-presentation helper between the home map and GIS. Use OpenFreeMap's public vector source with an authored navy style; keep attribution. A data-URL style string avoids the installed Streamlit 1.57 custom-style-object incompatibility without new hosting or credentials.

**References:** Rotterdam Weather & Tide (https://www.portofrotterdam.com/en/up-to-date-information/weather-tides-and-water-depth), Singapore MPA Maritime Digital Twin (https://www.mpa.gov.sg/maritime-singapore/innovation-and-r-d/maritime-digital-twin), OpenFreeMap quick start (https://openfreemap.org/quick_start/). Adapt their map/detail/layer hierarchy, without copying screenshots or claiming their vessel/forecast capabilities.

- [x] Test that map presentation preserves co-located source coordinates and IDs, labels each object separately and highlights only the selected object. Test label selection reaches the shared inspector and native selection resets on manual object choice. Membership hashing prevents row-index retargeting after layer changes.
- [x] Add `port_map.py`: authored style, semantic palette, screen-pixel sensor marks/labels and non-pickable selected ring. Add no operational geometries, relationships, coverage or hazard effects.
- [x] Connect `workbench_views.py` and `monitoring_views.py`; preserve `monitoring-points` ID and selection metadata. Make label picks inspectable; keep layout offsets in presentation only. Add a compact labelled legend.
- [x] Verify the custom vector basemap actually renders in the browser before retaining it. Inspect desktop/mobile, selection changes, labels at shared coordinates and the GIS route. Run appropriate existing tests, compile and dependency checks.
- [x] Review the implementation independently, resolve selected-label/native-pick issues, and document the shared style/provider and camera-reset boundary. Add a public release caption so production deployment can be checked without unlocking protected content.

## Verification

95 unittest cases passed; Python compilation, dependency and diff checks passed. Label-routing, manual-choice reset and GIS demo-boundary tests failed before their fixes. Old reference tests now select source IDs rather than assuming display row order. Local CUA verified the actual OpenFreeMap navy basemap, place labels and attribution in Overview and GIS. Clicking E70139 changed the inspector to its mAOD/Ordnance Datum Newlyn reference and selected-label border; manually choosing E70124 restored its local reference and cleared the old native highlight; clicking E70139 again worked. At 390px the map, labels and legend fit, and document/main widths showed no page overflow. Screenshots are held outside the deployment repository in the parent workspace's `outputs/dashboard-maritime-map-20261114` folder.

Delivery uses a normal push to the existing main deployment branch, followed by a public release-caption check. The protected production interior is not unlocked; its exact source is tested locally with the existing real-data connectors.

**Boundaries:** Navy water fill is cartographic styling, not water-depth information. Marker colours are source/freshness roles, not port risk. White rings denote selection only. Keep demo assets opt-in. Do not fabricate AIS, port boundaries, live incidents, bathymetry, dependencies or 3D building heights.
