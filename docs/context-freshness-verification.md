# Linked views and source freshness

15 November 2026; baseline `2f0341e`.

## Implemented

- Overview water handoff carries source-derived station, unit, datum and up to seven available calendar dates into Monitor. Future-only records do not enable a handoff. Water visibility is restored without changing traffic visibility.
- Monitor actions open Data Sources or Quality with the exact measurement reference/counter and dates. Filters apply to displayed records, CSV, report ZIP and Turtle. Off-page widget state is preserved. Source, object, reference and date changes deliberately release the incoming context.
- Missing references and permission changes produce an explanation without silently querying a forbidden source or selecting another measurement. Normal Monitor-to-Data-to-Monitor journeys protect selection even with both source families enabled.
- Daily summaries show per-source check status, forecast issue/valid time and water observation age. Late water, unavailable/unchecked sources and official-link-only notices/travel remain visible. Feed publication time is separate from check time. Reminder items precede group news; unknown validity is not labelled active.
- WebTRIS historical publication lag is stated in Monitor traffic and the Data source preview. Original provider caches, HTTP loaders, media, source values and the three-page architecture remain.

## Verification

- Full offline unittest suite: **241 tests passed** in 25.720 seconds. This includes the full-app round trip, missing-datum handling, source permissions, future-only dates, map/reference/date changes, filtered exports and existing cache/scientific checks.
- Authenticated local browser QA at 1600×1100 and 390×900 verified Overview → Monitor → Data Sources/Quality → Monitor → Overview; station/unit/datum and dates stayed aligned. CSV, report ZIP and Turtle contained E70139/AOD and excluded E70124/local datum.
- Mixed-state browser inputs verified late water, forecast issue/valid/check times, unavailable and unchecked warning sources, and official-link-only updates. Desktop/mobile screenshots were visually inspected; linked pages fit 390px without horizontal document overflow.
- Local evidence is in the parent workspace's `outputs/context-freshness-20261115`, including `full-tests.log`, `browser-verification.json`, screenshots and downloaded exports. Inputs are synthetic and explicitly labelled; these checks verify UI behaviour, not present public feed availability. The deployment entry remains `app.py`, without QA wrappers.
- The non-force push and online version/login observation are recorded after deployment below.

Independent review reproduced a return-navigation fallback when an ordinary Monitor selection vanished. Retaining the selected Monitor context and accepting other enabled source families corrected it; missing-reference, date-change, native-map and datum-change regressions cover the fix. Final independent review found no remaining issues.

## Relationship proposal boundary

The accompanying research draft distinguishes source-confirmed identity/observation links, computed spatial/temporal associations, partner-confirmed dependencies and derived-product provenance. It does not create new production dependency edges or approve canonical project identities. Each consuming WP owns its internal semantic adaptation; WP2 supplies access, quality evidence, coordination and adaptation of its own monitoring module. Software integration/frontend/operations ownership still requires agreement.
