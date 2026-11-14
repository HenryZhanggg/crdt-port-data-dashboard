# Everyday port overview implementation

**Goal:** Deliver the approved everyday homepage: weather, tide/water level, official reminders, nearby travel, port news and favourite places, with technical material available on deeper pages.

**Architecture:** A small fixed-source service returns separately timestamped forecast, observation and official-information sections. A native Streamlit daily view presents source-aware summary cards, a geographic map, local updates and weather/water/travel/news tabs. Existing monitoring, partner intake and semantic demonstration remain available; default Overview becomes the daily page. No illustrative data is presented as current information.

**Sources:** MET Norway Locationforecast (forecast, attributed CC BY 4.0, three-hour cache for Liverpool), Met Office North West RSS (official warnings), existing EA Liverpool gauge connector (observations) and EA current flood warnings (30km location query). Peel Ports and National Highways official directories remain useful source links when an automatic feed is unavailable. Links are not counted as live incident records. Feed publication, observation/forecast valid time and retrieval time are distinct.

**Scope:** daily_service.py and tests/test_daily_service.py; daily_views.py and tests/test_daily_views.py; app.py routing/marker; workbench_views.py scoped CSS/navigation; existing UI test migration and README. Preserve the pre-existing untracked visual-navigation plan.

- [x] Source service: 15 focused tests and real/captured HTTP checks cover forecasts, warning feeds, group news, tide references/conflicts, failures and timestamps. Actual EA tide retrieval succeeded in 3.23s with two references/145 rows. Daily requests are bounded; no new dependencies.
- [x] Daily UI: 14 focused tests cover plain-language content, forecast/observation interpretation, selection/favourites, unavailable states, date-only news precision and safe original links. Desktop and 390px layouts inspected.
- [x] Integration: Overview is daily; the semantic page remains in More views / Port connections example. Primary navigation is Home/Monitor/More views. Auth and existing monitoring remain; refresh preserves the three-hour weather cache, verified RED/GREEN.
- [x] Verification: all 154 tests pass. Independent review approved after fixing duplicate conflict handling, date precision, licence linking and cache invalidation. Native map selection, manual selection reset, saved places, all content tabs, advanced navigation and mobile overflow checks passed. Captured actual-source UI checks passed for weather, EA measurements and dated Peel headlines.

**Release:** Commit only scoped changes, push without force to existing main, verify the unique Everyday port overview marker and completed Streamlit login form. Store local/browser evidence under outputs/everyday-home-20261114; protected UI is tested locally unless an authorized online session is available.
