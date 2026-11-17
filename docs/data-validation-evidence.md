# Data Validation Report evidence in Data

The Data workspace uses curated metadata derived from **Data Validation Report, P0940 CRDT-Port Project, P0940-REP-103, C1, 4 November 2026**, issued for client use. The original has 182 pages. Its SHA-256 is `fe877c665ed8ade110094680400ec2ce4dba35fe98d6240b397b09c0fb01a1b6`.

`data/validation_report.json` links report findings to the 16 existing `HS001`-`HS016` catalogue entries. It is not a copy of the full report and does not add every dataset reviewed there. It contains paraphrased source strengths, access assessments, limitations and page references. `required_checks` and `recommendations` are implementation follow-up actions derived from the findings, rather than quoted report requirements.

## Evidence boundaries

- `report_assessment` means a source was assessed in the dated C1 report. It does not establish a successful current request, a live connection, a complete dataset, accepted ontology alignment or scientific suitability for a partner model.
- `HS011` is a generic local traffic/air-quality-sensor catalogue entry without a one-to-one report match. It is marked `not_mapped`, has no report findings or page references, and requires source-specific evidence.
- Report ratings are not reproduced as automated runtime quality scores. Access, subscription, licence and feed conditions must be rechecked when a source is actually connected.
- No full report, operational records, credentials or private filesystem locations are included in the deployment data.
- WP2 validates source access, coverage and data quality. Consuming teams confirm domain mappings, model-entry adaptation and scientific acceptance under the agreed project division of work.

## Particularly important findings

| Catalogue source | C1 pages | Integration consequence |
| --- | --- | --- |
| DfT port statistics (`HS001`) | 11-16 | Annual/quarterly aggregates support baselines; they do not supply individual live vessel movements. |
| EA flood monitoring (`HS004`) | 61-66 | Latest readings need station/measure context and do not form a complete history; retrieve historical records explicitly. |
| WebTRIS (`HS007`) | 86-88 | Fine-grained observations have approximately one month of publication lag and should remain labelled historical. |
| NaPTAN (`HS009`) | 102-104 | Access-node reference data supplies identity/location rather than service-running status. |
| Network Rail (`HS010`) | 119-121 | Registration and feed-specific formats, update bases and reference identifiers need confirmation. |
| Peel Ports marine information (`HS012`) | 128-131 | Public HTML/PDF is not a confirmed structured API or permission to republish; notices need validity and supersession handling. |
| ONS weekly shipping (`HS014`) | 156-159 | Weekly port-level aggregates cannot supply individual-vessel, berth or cargo details. |
| OSM/Geofabrik (`HS015`, `HS016`) | 167-173 | Spatial references and snapshots do not establish live operating conditions or validated functional dependencies. |

## Check

Run `.venv/Scripts/python.exe -m unittest discover -s tests -p test_validation_report.py -q` from the repository. The checks enforce revision/date traceability, catalogue linkage, bounded report-page references, the unmapped local entry and separation of delayed/aggregate sources from live labels.
