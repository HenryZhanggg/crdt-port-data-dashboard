# Graphite interface, geographic Monitor and waterfront media

Verified locally on 14 November 2026 against Streamlit 1.57.0 and Starlette 0.52.1.

## Delivered behavior

- Overview remains a source-based daily home: weather forecasts, measured water references, date-sorted categorized updates, saved places and compact trends.
- Monitor opens the illustrative draft-ontology geographic network with category icons, recorded predicate arrows, native object selection, search/type/relationship filters and connection evidence. Real gauge references are a separate mode and acquire no inferred asset links.
- More / Observations preserves the previous observation workbench and its original date/measurement controls. Other model, data and WP views remain available.
- From the waterfront provides two historical Seaforth photos from Wikimedia Commons and a user-initiated Peel Ports film player. Dates, source credits and licensing are visible; no live camera is asserted. The photo manifest records original files, source revisions, preview hashes and CC BY-SA terms. The film remains hosted by YouTube.
- Shared theme covers authentication, native widgets, charts, maps, panels and responsive layout. On narrow screens the map, register, feed and inspector stack vertically.

## Checks

- `python -m unittest discover -s tests -q`: **178 tests passed**. Includes source parsing, datum separation, authentication gating, cache isolation, native-selection state, graph directions, SVG image dimensions, media manifests and media response middleware.
- Browser QA at 1600×1100 and 390×900: photo decoding, lazy video player, update filter, saved reference selection, native geographic node click, manual/search selection reset, relationship filtering, canonical connection evidence, separate observed mode and More / Observations navigation passed. Mobile panels were checked to span at least 330 pixels and avoid document overflow.
- Browser tests used an authenticated local QA wrapper and captured official-source responses, not a production authentication bypass. No new provider requests were made for those replay checks. The production entry remains `app.py`.
- Independent requirements and code-quality reviews completed; findings on visible video copyright, navigation documentation, observation gaps and source check times were resolved.
- Protected interactions were verified locally. Deployment verification is limited to the remote revision and unauthenticated version/login surface unless separately recorded.

## Browser findings resolved

The initial local photo requests returned HTTP 500. Streamlit 1.57's media-aware gzip adapter overrides the responder start handling; the installed Starlette 1.10 body handling no longer matched that adapter. Pinning the existing transitive dependency to 0.52.1 restored image responses. A direct ASGI regression checks response-start before response-body for both gzip and identity encoding. Compare the [Streamlit adapter](https://github.com/streamlit/streamlit/blob/1.57.0/lib/streamlit/web/server/starlette/starlette_gzip_middleware.py) with the [compatible Starlette responder](https://github.com/encode/starlette/blob/0.52.1/starlette/middleware/gzip.py).

The initial node circles lacked visible symbols because browser ImageBitmap decoding requires intrinsic SVG dimensions. The generated SVG now supplies width and height, with an explicit regression test and browser recheck. This requirement is documented by [deck.gl Loading Data](https://deck.gl/docs/developer-guide/loading-data).

## Source and interpretation limits

Photo sources: [Seaforth waterfront](https://commons.wikimedia.org/wiki/File:Seaforth_Container_Terminal_2022.jpg), [Seaforth entrance](https://commons.wikimedia.org/wiki/File:Entrance_to_Seaforth_Container_Terminal,_Port_of_Liverpool.jpg). Official film: [Peel Ports Liverpool](https://www.peelports.com/port-locations/liverpool/).

The visual layout takes inspiration from the [WorldMonitor repository](https://github.com/koala73/worldmonitor). No external dependency network or current incident state was imported from it.

Historical media does not establish present operational conditions. Empty feeds do not establish an all-clear. Port-notice and road-incident automatic ingestion remain unconnected. Example assets, approximate coordinates, semantic definitions and scenario results remain illustrative; the consortium's approved ontology and executable partner models are still to be supplied. Arrows state recorded relationships and do not compute impacts.
