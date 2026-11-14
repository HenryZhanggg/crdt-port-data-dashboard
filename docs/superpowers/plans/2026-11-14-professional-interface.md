# Professional version 1 interface refinement

**Goal:** Rename the inner page to CRDT port dashboard version 1 and refine the approved engineering-monitoring design.

**Design:** Preserve white analytical panels and navy spatial views. Consolidate the page context, label inspector identity/time/evidence fields, emphasize declared edges touching the selected object, and provide a textual legend. Put longer coordinate/cascade/model caveats in existing detail expanders. Retain all data roles, directions, native selections and disabled model execution. Rename the home shortcut System overview, retaining its route.

**Files:** semantic_views.py owns presentation; workbench_views.py owns the shared CSS and home shortcut; app.py owns the overview breadcrumb and release marker; data/semantic_demo.json carries the display metadata. Update existing UI assertions and README to match visible names.

- [x] Applied scoped display changes without modifying products, relationships or access behavior. Corrected Streamlit custom-HTML negative margins and inspector font inheritance; adjusted the map camera to keep edge labels inside the view.
- [x] 121 tests passed; independent diff review found no material issues. Browser checks passed for the exact inner title and System overview shortcut, non-overlapping status/context layout, desktop/390px layout, native map/graph selection, inverse jumps, scenario context, context download and monitoring navigation. Screenshots inspected.

**Release:** Commit scoped files and push without force to the existing main branch. Confirm the completed Streamlit login form and unique release marker; record browser evidence in outputs/professional-interface-20261114. Protected content is tested locally unless an authorized online session is available.
