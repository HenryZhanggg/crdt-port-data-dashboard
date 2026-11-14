# Ontology guided home demo implementation

**Goal:** Replace the former connection-teaching page with the approved main-page demo: typed object navigation, map/relationship views, selected-object details, type-specific products, scenario context and related analyses. Publish to the existing Streamlit application.

**Scope:** The default Overview becomes the semantic demo. The existing observation workbench remains under Live Monitoring, with its original source access, quality and partner result functions. The old Integration Demo route, shortcut and implementation/tests are removed. Demo objects, relationships, data and outputs are explicitly illustrative and isolated from real source objects and imported packages. The local RDF vocabulary remains a draft, replaceable by the formal WP1 ontology.

## Work

- [x] Backend: TDD for local RDF object/type/relation queries, inverse navigation, validity/time and scenario filters, data products and type-to-view profiles. Files: semantic_service.py, ontology/semantic_demo.ttl, data/semantic_demo.json, tests/test_semantic_service.py.
- [x] UI: TDD AppTest for default landing, type/object selection, relation filtering, linked views, scenario products, separate live monitoring and removal of old entry points. Files: semantic_views.py, tests/test_semantic_views.py, app.py and small navigation edits in workbench_views.py.
- [x] Migration: keep legacy monitoring tests targeting Live Monitoring; handle stale session navigation; delete the retired demo modules/tests; update README/module integration guidance and mark the old plan superseded.
- [x] Verification: 121 tests passed; independent spec/quality review approved. Desktop and 390px browser checks passed for native map/graph selection, inverse jumps, scenario switching, context download, overflow, real monitoring navigation and retired entry removal. Regression tests cover stale chart selection and two-dimensional graph picking.
- [ ] Delivery: commit only scoped files, push without force to the existing main branch, verify the online version marker and report the published entry point.

## Acceptance

Ontology types and relation metadata determine navigation and view profiles; object/time/scenario context determines products. Equal coordinates or classes never create dependency instances. Missing products remain unavailable, synthetic gaps remain missing, model execution is disabled, and no uploaded code or arbitrary endpoint is executed. Every selection surface uses the same demo object ID while real monitoring retains its own state.
