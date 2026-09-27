# TWDisaster identity evidence review

**Inspected:** 2026-09-28 (read-only)  
**Upstream revision:** [`d600dee84d7e9646395d147722e95c7115f81582`](https://github.com/KageRyo/TWDisaster/commit/d600dee84d7e9646395d147722e95c7115f81582), the `main` tip observed during inspection.

## Public model and files

The public data model describes four UTF-8 CSV tables: events, observations, sources, and event-source relationships. At the inspected revision, they contain 76 events, 395 observations, 88 sources, and 89 event-source relationships. Events expose a canonical `name` and `aliases_json`. Sources expose publication metadata including `title` and `url`. Each observation already carries both `event_id` and `source_id`; `event_sources.csv` records source/event pairs that support at least one included observation.

This structure does not provide an independent source-specific event label for EntityLinkage to evaluate. The observation rows already join a source to an event, and the event-source table records that same relationship. Treating either as an input crosswalk would reuse the mapping under evaluation. A source can also support more than one event, so a source title is not necessarily a single-entity identity.

## Read-only title comparison

As a narrow diagnostic, source titles were compared with event names and declared aliases using NFKC normalization, Unicode case folding, and whitespace collapse. One source title exactly matched a canonical event name or alias; that event/source pair was already present in `event_sources.csv`. A substring scan found 36 source titles containing at least one normalized event name or alias; 32 of the resulting event/source pairs were already in the published relationship table. These are candidate-text observations only: substring containment does not establish identity, and the existing crosswalk cannot serve as independent confirmation.

No source rows were copied into this repository, no aliases or mappings were invented, and no private implementation details were inspected. This dataset therefore is not claimed as a TWDisaster dogfood validation. The examples in this project remain fully synthetic. Reassess only if TWDisaster publishes source-specific event identity labels independent of its observation and event-source mappings.

## Sources

- [TWDisaster data model](https://github.com/KageRyo/TWDisaster/blob/main/docs/data-model.md)
- [events.csv](https://github.com/KageRyo/TWDisaster/blob/main/data/events.csv)
- [observations.csv](https://github.com/KageRyo/TWDisaster/blob/main/data/observations.csv)
- [sources.csv](https://github.com/KageRyo/TWDisaster/blob/main/data/sources.csv)
- [event_sources.csv](https://github.com/KageRyo/TWDisaster/blob/main/data/event_sources.csv)
