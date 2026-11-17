# Data workbench access and input preparation

**Goal:** Make the Data integration workspace directly discoverable and turn partner CSV records and selected observations into inspectable model-input tables.

**Approved scope:** The user supplied an authenticated screenshot with only the old three tabs and asked to fix visibility and continue useful data-integration improvements. Keep the existing three main workspaces. Implement the access fix and bounded CSV/contract features now; do not require another design approval.

**Diagnosis:** The screenshot matches the pre-544439e Data layout. Current source and full-entry-point AppTest show four tabs even for Terminal operator. A feed cache cannot remove a tab. A retained old rendered session, server instance or missed imported-module change remains possible; the exact cloud mechanism is unconfirmed. Previous public checks covered login only. Windows Firefox inspection was stopped by browser URL-policy enforcement; do not bypass that restriction with other Windows automation.

## Tasks

- [x] Add authenticated app and Data-module build markers, a prominent Open integration workbench button and a safe query-parameter deep link applied once after authentication.
- [x] Test Terminal operator navigation from app.py without feeds. Detect an outdated imported Data module by its build contract and reload that module only when the contract differs; expose a clear deployment error if it still differs.
- [x] Add bounded session-only CSV import (2 MB, 10,000 rows, 100 columns), explicit field mapping and declared metric/unit/reference/time assumptions, preserving invalid rows and original records.
- [x] Reuse existing availability, missing/conflict and replay logic for uploaded records without implying original historical receipt times or accepted ontology mapping.
- [x] Add a model-input requirement editor binding explicit input names to exact series and expected units; export a one-cutoff feature row, per-feature checks and reproducible contract/lineage.
- [x] Preserve configuration and collected/uploaded data across page navigation; clear them on lock. Never assign action/file-uploader state through the persistence helper.
- [x] Run focused and full tests, obtain an independent review, and publish scoped changes to the existing main branch. Use read-only repository access for publication evidence; keep protected online verification explicitly unconfirmed if browser policy prevents it.

## Boundaries

No arbitrary endpoint calls, uploaded code, new paid services, automatic cloud storage, formal WP1 terminology approval or partner model execution. CSV data remains in the user's session and its own download packages. Configured input checks do not establish scientific model accuracy. Explicit mapping does not establish canonical entity equivalence across providers. Existing units/datums and source permissions remain separate.
