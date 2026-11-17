# Data validation and historical/updated-observation integration

The Data workspace implements an inspectable WP2 data workflow. It prepares candidate input records and exposes the evidence needed to discuss them with consuming WPs. Input acceptance and scientific model validation remain with those teams.

## 1. Establish source suitability

Sources joins the existing catalogue with curated findings from P0940-REP-103 C1, issued 4 November 2026. Fifteen catalogue entries have a report mapping; HS011 does not. Each mapped entry keeps PDF page references, temporal role, access assessment, useful tasks, limitations and proposed follow-up checks. Download the filtered register or report evidence JSON. Connector presence is not a successful current retrieval, and report ratings do not validate a model.

The separate provider notice for WebTRIS was checked on 17 November 2026. National Highways announced a pause in new monthly updates on 17 September 2026, with historical data remaining available in principle. The normal one-month publication lag and this pause are separate conditions. Selected counters and dates must still be requested and checked. An HTTP 204 report preserves retrieved counter metadata and an explicit `api_no_data` status; an API error remains an error.

## 2. Collect and retain evidence

Integration requests only the selected, permitted source families after **Load selected records**. The seven-day request limit bounds provider calls and browser processing. Source/date changes require a new collection; changing rules reuses the collected records. Exact incoming Monitor references remain scoped to the selected station/unit/datum or traffic counter.

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

## Supporting references

- Project report: P0940-REP-103 C1, 4 November 2026; curated page references and SHA-256 are in `data/validation_report.json`. The original PDF is not distributed in the repository.
- [Environment Agency flood-monitoring API reference](https://environment.data.gov.uk/flood-monitoring/doc/reference): observations, measurement definitions and time fields.
- [Apache Beam model](https://beam.apache.org/documentation/basics/): event time, processing time, windows and late data. This application uses pandas; citing the model does not imply a Beam deployment.
- [W3C SOSA/SSN](https://www.w3.org/TR/vocab-ssn/): common observation concepts used by the existing Quality graph.
- [W3C PROV-O](https://www.w3.org/TR/prov-o/): distinctions between data entities, processing activities and responsible agents. The CSV/JSON package retains provenance fields without claiming complete PROV-O encoding.
- [WebTRIS FAQ](https://webtris.highwaysengland.co.uk/Home/Faqs), [provider news](https://webtris.highwaysengland.co.uk/Home/News) and [API documentation](https://webtris.highwaysengland.co.uk/api/swagger/ui/index): publication lag, the dated pause notice and request resources.
