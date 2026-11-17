# Data validation and integration verification

17 November 2026. Baseline: `503b9f5`.

## Delivered scope

Data now contains Sources, Integration, Quality and Partner packages. Sources adds report-grounded temporal roles, connector-route filters, PDF page references, limitations, follow-up actions and register/evidence downloads. Integration adds explicit source/date collection, exact measurement selection, common-field inspection, collection/replay availability modes, freshness/delay/missingness controls, input snapshots, decision audits and reproducible exports.

Report findings were derived from the actual 182-page P0940-REP-103 C1 PDF, dated 4 November 2026. Fifteen catalogue entries have a mapping; HS011 remains unmapped. The original PDF is not published. `data/validation_report.json` retains its SHA-256 and distinguishes report assessment, derived follow-up actions and separately checked provider notices.

## Verification evidence

- Full offline unittest suite: **306 tests passed**, 44.935 seconds, after the functional fixes and documentation update. Focused tests also cover reference labels, delayed/missing replay, partial/all-empty source evidence, current-source status preservation and lock/navigation behavior.
- Local browser QA used actual captured EA observations and the actual initial WebTRIS response failure, not fabricated operational records. At 1600×1100 and 390×900 it verified report-role filtering, source findings, explicit collection, snapshot display, replay controls, decision audit and valid evidence ZIP download. No Streamlit exceptions or horizontal document overflow were observed. Desktop and mobile screenshots were visually inspected.
- Public source probe on 17 November 2026 returned **422 EA water records** for 16–17 November. The three measurement references remained separate, with missing values retained for stale inputs under the selected rule.
- A follow-up WebTRIS probe at **12:14 UTC** returned **114 local counter metadata records**. The selected counters' report for 20–21 August 2026 returned **HTTP 204**, now represented as `api_no_data`; it did not establish absence of historical data for other counters/periods. The initial JSON parsing error and the subsequent classification fix are recorded separately.
- The National Highways news page was checked on 17 November 2026. Its 17 September notice describes a pause in new monthly updates while historic records remain available in principle. The UI retains the notice date, check date and source link, without guessing a restart date.
- Independent review found source-URI fallback, numeric counter identity and measurement-label issues; all received regression fixes. Partial-source and all-empty collection evidence were added to exports. A navigation test found Streamlit action widgets could not be assigned through session state; the preservation logic now excludes those actions.

Evidence is stored outside deployment inputs in the parent workspace's `outputs/data-integration-validation-20261117`, including `source-probe.json`, `source-probe-followup.json`, `browser-verification.json`, screenshots and a downloaded integration ZIP. Local QA uses a separate preview wrapper; deployment remains `app.py`.

## Interpretation

Collected mode establishes dashboard retrieval time, not original historical publication or operator receipt. Replay delivery times and losses are explicitly simulated. Available values passed the selected data checks; they have not thereby passed scientific model acceptance. Traffic timezone assumptions remain unverified. WP1 semantic alignment, each consuming WP's model adaptation and the deployment of durable collectors/shared storage remain separate responsibilities.

## Cloud release

Code revision `544439e` was pushed without force to the existing GitHub `main` branch. At **12:20 UTC on 17 November 2026**, the public Streamlit app's embedded application frame showed the new “Data validation and integration workbench” release marker, password field and Unlock dashboard button, with zero Streamlit exceptions. The app did not require waking. `deployment-verification.json` and `streamlit-online-version.png` record this check. Protected interactions were verified locally; no claim is made that the cloud password-protected workflow was exercised.

The unrelated pre-existing untracked visual-navigation-layout plan was left untouched.
