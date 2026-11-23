# Data validation and historical/updated-observation integration

The Data workspace implements an inspectable WP2 data workflow. It prepares candidate input records and exposes the evidence needed to discuss them with consuming WPs. Input acceptance and scientific model validation remain with those teams.

## Open the workbench

Open **Data & Integration**, then choose **Browse datasets & downloads** or **Open integration workbench**. Both the [datasets link](https://crdt-port-data-dashboard.streamlit.app/?workspace=data&tool=sources) and the [integration link](https://crdt-port-data-dashboard.streamlit.app/?workspace=data&tool=integration) open their tab after authentication. The login page and Data workspace display build `2026-11-23.2`.

## 1. Establish source suitability

Sources joins the existing 16-entry catalogue with curated findings from P0940-REP-103 C1, issued 4 November 2026. Fifteen original entries have a report mapping. The additional 21 reference entries cover the remaining families in the earlier project source inventory. Each source card shows its preview on the left and access or download on the right. Turn on **Browse connected records** to request a supported dataset. Reference entries link to their providers when available. Select a dataset to see a chart, location map or sample records. A CSV contains all returned records for that selection, including rows beyond the sample.

Under **Environment Agency**, select **Liverpool water levels · historical archive** for the project-held public extract. The CSV preserves 4,896 original records from three provider measurements across 5–13 September and 10–17 November 2025. Separate native axes distinguish measurements in m and mAOD. The provenance JSON includes the 17 input files, exact times and measures, licence and checksums. The archive provides observation times. Its original publication and receipt times are unknown. **Flood warnings** uses the existing current Liverpool-area provider snapshot and shows the provider response when there are no downloadable rows.

The separate provider notice for WebTRIS was checked on 17 November 2026. National Highways announced a pause in new monthly updates on 17 September 2026, with historical data remaining available in principle. The normal one-month publication lag and this pause are separate conditions. Selected counters and dates must still be requested and checked. An HTTP 204 report preserves retrieved counter metadata and an explicit `api_no_data` status; an API error remains an error.

## 2. Collect and retain evidence

Use **Use in Integration** from the supported water or traffic product in Sources. The button preselects the product and a valid preview date range when available. Integration requests the selected, permitted source families after **Load selected records**. The seven-day request limit bounds provider calls and browser processing. Source/date changes require a new collection, while changing rules reuses the collected records. Monitor handoffs carry station, unit, datum and the selected provider measure URI when known, or the selected traffic counter. The API scope persists when adding a CSV.

**Validation report for selected sources** shows C1 pages 61–66 for EA and 86–88 for WebTRIS. **Observation coverage** summarises the returned selection before mapping. The table counts normalized rows per variable and reports the first and last offset-aware event times. Times derived from explicit timezone assumptions have separate counts and bounds. A WebTRIS site catalogue response contributes no traffic observation rows. The exported evidence retains the source report, scoped request results and time bounds. Coverage between the first and last times requires a separate gap check.

The source records, request period, connector status, collection timestamps and context are retained in the current session and exported. The application does not run an unattended collector or a durable shared database. Locking clears integration session data. An empty collection can still export its request/check evidence as JSON.

## 3. Map without losing measurement meaning

Normalized records retain source, object and series IDs; observed variable, value and unit; reference datum, qualifier and measure URI; event time and dashboard retrieval time; original timestamp, source URI and raw record. Series fingerprints separate incompatible measurements. Integer-like traffic IDs are stable across pandas numeric coercion. These are provisional workspace identities and a draft observation profile, not approved project ontology identifiers.

Water units and datums are never converted. Traffic timestamps lacking an offset remain blocked unless a user chooses a recorded UTC or Europe/London assumption. Such an assumption does not establish the provider's actual time convention. Ambiguous/nonexistent local timestamps remain invalid.

## 4. Apply explicit availability and quality rules

At a timezone-aware UTC cut-off, the workbench excludes future events, records not yet collected, invalid metadata/values and exact duplicates. It selects the latest eligible observation separately for each measurement series. An observation older than the selected age limit becomes stale; conflicting latest values remain conflicting. Missing, invalid, stale and conflicting outputs retain a missing value. Earlier observations remain in the audit rather than being silently zero-filled.

**Collected snapshot** uses the dashboard retrieval timestamp. This establishes when this application had the record, not when the provider first published it or when a historical operator received it. It cannot establish historical real-time knowledge before collection.

**Replay scenario** constructs availability as event time plus a selected delay and can deterministically drop every Nth record. It examines processing behavior under assumptions. Its timings are not measured provider latency, and the results do not establish port risk or model accuracy. Every audit row retains effective availability, eligibility, exclusion reason and whether its value was selected.

## 5. Export and agree the receiving contract

The integration ZIP contains `observations.csv`, `snapshot.csv`, `audit.csv`, `rules.json` and an evidence-boundary README. Rules include the requested sources, scoped collection status, request period, selected series, context, time assumption, cut-off, freshness, replay settings and collection time. Partial-source failures remain in the package even when another source returns observations.

Use these artifacts to agree required variables/objects, accepted units/references, temporal resolution and valid age, missing-data policy, model triggers and checking references with each receiving WP. WP1 supplies common semantic guidance; WP2 supplies access and source-quality evidence; each consuming WP owns domain adaptation, model-input construction and scientific verification. Inspecting or exporting records does not execute a model.

## 6. Map partner CSV observations

Choose Upload CSV and preview its original fields. Map entity ID, value and full observation date-time columns; declare metric/unit from a column or constant. Water-level records additionally need a datum and qualifier. Concept URIs remain user declarations and are preserved with original rows; no canonical cross-source identity is inferred. The UTF-8 parser accepts at most 2 MB, 10,000 data rows and 100 unique columns, rejecting malformed files without silently skipping rows. Event timestamps require an explicit ISO date and time. Offset-free values need a recorded UTC/Europe-London assumption; ambiguous local times, partial dates and relative terms remain invalid.

Apply column mapping to create the same canonical records used by the connected-source workflow. Availability is the actual dashboard upload time, not an invented historical arrival. A changed file or delivered mapping invalidates the old approved snapshot. Loaded records can be retained after the upload control unmounts, visibly labelled as session data, and explicitly cleared. They are never written to the public repository or sent to another service by the import.

## 7. Construct an explicit model input table

Expand Build a model input table after selecting measurement series and a decision cut-off. Assign a unique input name to each exact series, confirm expected units and mark required inputs. The builder preserves each feature's source, entity, metric, unit, datum, record evidence and common cut-off. It does not aggregate distinct measurements or infer causal relationships. Stale, conflicting, invalid, missing or unit-mismatched features remain missing; use of time-assumed records requires explicit permission. A CSV feature row, check table and JSON contract are exportable with the selected records and processing rules.

Saved requirements are kept separately from the editor widget state, using a stable base during editing and restoring saved choices after page unmount. Invalid edits remain correctable. The configured checks are useful for handover and reproducibility, with scientific suitability still decided by the receiving WP.


## Connected multi-source product (18 November 2026)

The visible workflow is **Select data → Map common meaning → Align and check → Review product → Export inputs**. Sources and Quality are supporting tabs. Partner product/dependency intake is collapsed inside Integration; old Partner packages navigation migrates there.

**Combine API + CSV** runs the existing API request and bounded CSV mapping paths together. Original source rows retain their own intake timestamps. If an API returns no observations, a mapped CSV can still proceed with that API failure/empty result preserved in the report. No record is fabricated to fill an absent source. Combined metadata leaves the global period/object context unset and preserves `api_request_period`/`api_observation_context` plus each intake separately. The CSV's own event period is retained; selected API collection dates do not silently clip or redate it.

The common-meaning editor requires an explicit common object identifier, concept and confirmation per measurement series. Matching declarations group only exact units, datum and qualifier. Confirmation also declares equal temporal support; unknown source semantics need review rather than an automatic equivalence claim. Unconfirmed or incomplete declarations keep their original series; incompatible definitions stay separate with an inspectable reason. These declared semantic associations do not infer spatial or operational dependence, and do not prove official identity approval. All original source identities/series/metrics and raw evidence remain recoverable in the observation evidence.

The long-form product preserves exact UTC observation times; it does not resample, interpolate, average or convert units. Availability checks use a common explicit decision cut-off. Original collection and event times, missingness and conflicts remain visible. Model-input checks operate on the resulting exact common-series snapshot and preserve per-source evidence in their contract.

The integrated-record CSV and existing ZIP are available next to results. The ZIP's `rules.json` carries `joint_product.profile_version`, `bindings` and `linkage` plus every intake in `input_collection.collections` for combined mode. This supports reproducible handover; durable collection/storage and executed model chains remain outside this update.

## Supporting references

- Project report: P0940-REP-103 C1, 4 November 2026; curated page references and SHA-256 are in `data/validation_report.json`. The original PDF is not distributed in the repository.
- [Environment Agency flood-monitoring API reference](https://environment.data.gov.uk/flood-monitoring/doc/reference): observations, measurement definitions and time fields.
- [Apache Beam model](https://beam.apache.org/documentation/basics/): event time, processing time, windows and late data. This application uses pandas; citing the model does not imply a Beam deployment.
- [W3C SOSA/SSN](https://www.w3.org/TR/vocab-ssn/): common observation concepts used by the existing Quality graph.
- [W3C PROV-O](https://www.w3.org/TR/prov-o/): distinctions between data entities, processing activities and responsible agents. The CSV/JSON package retains provenance fields without claiming complete PROV-O encoding.
- [WebTRIS FAQ](https://webtris.highwaysengland.co.uk/Home/Faqs), [provider news](https://webtris.highwaysengland.co.uk/Home/News) and [API documentation](https://webtris.highwaysengland.co.uk/api/swagger/ui/index): publication lag, the dated pause notice and request resources.
