# Data workbench access and CSV/model-input verification

17 November 2026. Baseline `f936400`. Workspace build `2026-11-17.2`.

## Diagnosis and change

The supplied authenticated Firefox screenshot showed the exact pre-544439e three-tab Data layout, without the newer report metrics. Current source declares four tabs unconditionally, including for Terminal operator. The prior deployment check established the public login marker, not the protected Data workspace. A feed cache cannot remove a navigation tab; a retained old render/session, server instance or missed module update remains unconfirmed as the specific cause.

Data now offers a prominent Open integration workbench button and a safe query route, `?workspace=data&tool=integration&release=20261117b`, applied only after authentication and only once per route/session. App, Data and Integration expose build markers. If the already-imported Data or Integration module advertises a different build, its source is reloaded before use; persistent disagreement produces a visible deployment message. This is a tested build-consistency check, not evidence that a particular cloud cache caused the original screenshot.

Integration now accepts bounded, explicitly mapped CSV observations alongside the existing connected sources. Both paths share series selection, availability/replay rules, snapshot/audit exports and a model-input requirement editor. Uploaded records retain file hashes, original rows, actual upload time and provisional mapping declarations. A CSV timestamp must include an explicit ISO date and time; relative/partial strings remain invalid. Model input exports retain exact series, units, references, a common cutoff, missing-value states and record lineage. Saved editor choices survive consecutive edits and page unmounts.

## Verification

- Full offline suite: **348 tests passed in 49.541 seconds**.
- Full-entry-point routing tests exercise authenticated Terminal operator → Data → visible workbench shortcut, traffic-only controls and zero unsolicited feed calls.
- Query-route tests verify direct workbench entry after authentication and normal subsequent navigation. Deliberately stale Data imports are reloaded before rendering. Independent review also verified a deliberately stale Integration import.
- CSV tests cover byte/row/column limits, malformed files, raw row-number retention, explicit field mappings, invalid values, complete timestamps, timezone assumptions/DST, missing water references, changed upload/mapping invalidation and session clearing.
- Model tests cover exact series bindings, unit mismatch, missing/stale/conflicting/invalid inputs, assumption opt-in, common cutoff, per-feature provenance and JSON export scope. Real AppTest editor-state payloads verify consecutive name/unit edits, stable editor identity and restoration after unmount.
- Integrated app tests exercise retained uploaded observations, second reruns, model-input export availability and Monitor/Data navigation without provider requests. Action/file-uploader/editor widget state is excluded from direct session-state preservation; lock clears integration data and requirements.
- Independent reviews found manufactured dates from permissive parsing and unstable editor defaults. Both received focused red/green regressions and fixes. No blocking findings remained in final review.

## Verification boundary

The Windows Firefox inspection was stopped by the computer-use tool because browser URL-policy enforcement is unsupported for that browser. No alternate Windows browser-automation technique was used to bypass that restriction. This release's protected cloud workflow and mobile layout were **not** reverified in a browser. Publication is verified through the repository's main ref; a successful Git push alone does not establish what the user's retained authenticated page currently renders.

Test logs and the user screenshot reference remain outside deployment inputs in the parent workspace's `outputs/data-workbench-access-20261117`. No uploaded CSV, credentials or full project PDF is included in the repository.
