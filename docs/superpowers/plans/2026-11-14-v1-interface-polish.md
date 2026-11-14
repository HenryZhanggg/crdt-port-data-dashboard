# CRDT port dashboard version 1 interface polish

**Goal:** Apply the requested display name and the previously selected engineering-monitoring visual direction to the deployed dashboard.

**Design:** Retain the current object/map/inspector/product structure and native Streamlit controls. Use the exact name in browser, login, sidebar and header; a smaller workspace heading; compact white panels; readable captions; a navy relationship view consistent with the map. Shorten repeated DEMO suffixes in navigation while retaining explicit illustrative-data context, full object identity and provenance. No new data, model execution or interface dependencies.

**Implementation and verification:**

- [x] Rename visible application surfaces in app.py; keep access and navigation behavior intact.
- [x] Adjust scoped panel/context styling in workbench_views.py; compact navigation and headings in semantic_views.py; update the existing heading assertion.
- [x] 121 existing tests passed; git diff check clean. Independent diff review found no material issues. Browser checks passed for exact title/header name, desktop/390px layout, native map/graph picking, inverse navigation, scenario switching, evidence download and monitoring navigation. Screenshots inspected for label layout and overflow.
- [x] Implementation ab173a1 pushed without force to main; remote hash matched. Streamlit displayed the exact new login name/version marker and completed Password/Unlock form with no application errors. Protected workspace interactions were verified locally.
