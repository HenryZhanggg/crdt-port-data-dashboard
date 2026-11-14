# Partner integration demo implementation plan

> **For agentic workers:** Use subagent-driven-development for the connection checks, followed by independent review and application verification.

**Goal:** Extend the existing workbench with an English-language partner walkthrough of shared viewing, explicit output-to-input handovers and conditional execution-order previews.

**Architecture:** Keep source monitoring and partner result intake intact. A small pure Python module owns illustrative connection declarations/checks; a Streamlit view renders the explanation, selected connection, check details, order preview and downloadable draft. All fixture IDs and values are illustrative and remain separate from imported partner runs. Actual scientific approval, live model invocation and production ontology integration remain distinct pending handovers.

**Tech stack:** Existing Python, Streamlit and pandas; no new dependency or service.

## Scope and acceptance

- [x] Add an Integration Demo page and visible shortcut using current navigation permissions.
- [x] Explain the three connection levels; expose producer/consumer, specific variables, entity, units/reference, time/space, conversion, provenance, version and responsible teams.
- [x] Demonstrate aligned illustrative handover, absent input/baseline, reference/time mismatch and dynamic coupling design needs; missing values never become zero.
- [x] Distinguish technical checks, provider/consumer acceptance and actual execution. Previews never invoke partner models or import fixtures as real results.
- [x] Show WP1–7 responsibilities, with consuming WPs retaining their domain adaptation and scientific verification.
- [x] Export a draft connection record and handover template for partner discussion.
- [x] Correct only stale central-WP2 mapping allocations and the omitted T3.0 entry in existing registry/docs.

## Task 1 — Connection declarations and checks

Create `integration_demo.py` and `tests/test_integration_demo.py`. Write failing tests first; run `.venv/Scripts/python.exe -m unittest discover -s tests -p test_integration_demo.py -v`. Implement explicit metadata checks and conditional order previews, with no arbitrary formulas/code, URL fetching or model execution. Verify each fixture and mismatch, not just UI labels.

## Task 2 — Workbench view and navigation

Create `integration_views.py`; modify only routing/imports in `app.py` and shortcut/caption in `workbench_views.py`. Add AppTest coverage in `tests/test_integration_views.py` before wiring the new page. Use current containers, tables and navigation; include the current dataset inventory without asserting that listed sources satisfy model requirements. Check connection selection and preview states through AppTest.

## Task 3 — Allocation and partner guidance

Update `data/wp_modules.json`, `docs/module-integration.md` and the relevant README navigation paragraph. Preserve Gantt participants and unassigned software roles. Describe the demo's boundaries and a short presentation route; reference official OpenMI/BMI principles as background, without claiming full compliance.

## Task 4 — Verification and delivery

Run the full unittest suite in the existing `.venv`, review the diff for scientific/ownership claims and regressions, inspect the rendered demo on desktop/mobile, and verify the main monitoring screen remains intact. Use existing repository publishing practices only after local verification; report exact local/remote status without claiming that the full project model chain exists.

## Verification results

- Existing baseline: 95 tests passed in the project virtual environment.
- Connection checks: 21 tests passed; UI integration: 5 tests passed. Full final suite: 121 tests passed.
- Browser: aligned and blocked examples, connection/template downloads, return to Monitor, latest-source reference-check details, desktop and 390px mobile layout verified; no application exceptions or document overflow.
- Independent specification and code-quality reviews found no material gaps.
- Source changes do not add production dependencies or execute partner models.
