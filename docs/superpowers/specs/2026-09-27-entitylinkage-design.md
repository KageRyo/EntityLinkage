# EntityLinkage v0.1.0 Design

**Status:** For user review; implementation has not started.

**Date:** 2026-09-27

## Purpose

EntityLinkage is a standalone Python library and command-line tool for conservatively linking external records to a canonical set of entities. Each record receives an explicit `resolved`, `ambiguous`, `unresolved`, or `not_applicable` result with stable, machine-readable evidence.

The v0.1.0 design favors auditable rules and reproducible output over match rate. It does not depend on TAG-Twin, TWDisaster, disaster-specific fields, private data, a database, or network services.

## Goals and boundaries

- Model canonical entities, external records, and linkage results with generic identifiers and attributes.
- Support normalized exact name and declared-alias matching, exact configured identity values, and exact attribute constraints.
- Preserve missing-data semantics, candidate evidence, stable reason codes, and explicit reviewed decisions.
- Provide a thin, noninteractive CLI and a Python API over a file-independent matching core.
- Produce deterministic JSON, CSV, audit summaries, and per-record inspection output.

EntityLinkage is not a fuzzy or probabilistic resolver, a deduplication system, a knowledge graph, a lineage or release validator, a data catalog, an ETL framework, or a workflow service. Fuzzy matching, semantic alias generation, machine learning, web lookups, review UI, spatial joins, and dataset-specific schema validation are out of scope for v0.1.0.

## Approaches considered

1. **Declarative YAML with candidate rules and constraints — selected.** This follows the supplied YAML examples, makes matching behavior reviewable beside the input data, and keeps the core usable from both CLI and Python. PyYAML is the only required runtime dependency.
2. **Declarative JSON.** This would use only the standard library for input parsing, but makes the hand-authored configuration less readable. The library result model remains independent of this format choice.
3. **Python-defined rule plugins.** This is flexible for application developers, but makes matching configuration harder to validate, share, and inspect in the CLI. A plugin system is unnecessary for the first release.

## Architecture

The package uses a pure matching core, a strict input loader and validator, a thin `argparse` CLI, and separate deterministic output and audit helpers. The core accepts validated configuration and in-memory entity and record values; it does not read files or print output.

The proposed source layout is:

```text
src/entitylinkage/
├── __init__.py
├── model.py
├── normalize.py
├── rules.py
├── matcher.py
├── overrides.py
├── audit.py
├── output.py
└── cli.py
```

Input parsing and validation live in `config.py`. Keep modules only where they preserve a clear boundary; this layout is not a requirement to split trivial code into separate files.

The public API is centered on `Linker(config).link(entities, records)`. Validated configuration and result models are immutable; matching helpers are pure functions. YAML loading, CLI formatting, and file writing remain outside the matcher.

## Input contract

Each example directory contains one `entitylinkage.yaml` file; commands also accept the file path directly. The top-level document has `version: 1`, `entities`, `records`, and `matching`, with optional `overrides`.

Entities have a nonempty string `id`, a nonempty string `name`, optional string-list `aliases`, and optional flat `attributes` mapping. Records have a nonempty string `id`, an optional `name`, optional flat `attributes`, and optional `applicable` flag; an omitted or null record name is missing. `applicable` defaults to true. A false value requires `not_applicable_reason` and cannot be combined with an override. Attribute keys are user-defined strings; the core does not reserve names such as `year`, `date`, `region`, or `publisher`. Attribute values are strings, integers, finite floats, booleans, or null; omitted fields and YAML `null` are missing. YAML date values must be quoted strings.

```yaml
version: 1

entities:
  - id: product-001
    name: Alpha Product
    aliases: [Alpha]
    attributes:
      year: 2024
      publisher_id: catalog-17

records:
  - id: source-record-001
    name: Alpha
    attributes:
      year: 2024
      publisher_id: catalog-17
  - id: source-record-002
    name: Outside Reference
    applicable: false
    not_applicable_reason: outside_reference_scope

matching:
  normalization:
    case_fold: true
    punctuation: preserve
  candidate_rules:
    - id: name
      type: normalized_name
    - id: publisher-id
      type: exact_value
      entity_field: attributes.publisher_id
      record_field: attributes.publisher_id
  constraints:
    - id: same-year
      type: equal
      entity_field: attributes.year
      record_field: attributes.year
      missing: ignore
  apply_overrides: false

overrides: []
```

The loader uses a safe YAML parser and rejects duplicate mapping keys. It rejects unknown keys in the schema and rule declarations, unsupported versions or rule types, invalid field-reference syntax, malformed values, and invalid override declarations. `attributes` remain an open, flat mapping so field names stay domain-neutral. Field references use core `name` or `attributes.<key>` paths; keys are checked against this grammar, while an absent value in an individual row is handled by the configured missing-data rule. `matching.normalization` requires explicit `case_fold` and `punctuation` values; `candidate_rules` is required and nonempty; `constraints` and `overrides` default to empty lists; `apply_overrides` is a required boolean. Booleans, integers, and floats are distinct for exact equality. Text values that YAML could interpret as numbers, booleans, or dates must be quoted.

Entity IDs must be unique among entities; record IDs must be unique among records. Duplicate normalized names or aliases within one entity are invalid. The same normalized name or alias across different entities is valid evidence for an ambiguous result. Rule IDs and override record IDs must be unique.

## Matching rules and missing values

Rules are divided by role so combination behavior is explicit:

- **Candidate rules are OR-combined.** Each rule contributes every entity it supports; the union is the candidate set. `normalized_name` compares the record name with each entity name and declared aliases. `exact_value` compares configured attribute fields by exact, type-sensitive equality and supports explicit external identity keys. Missing or empty identity values never create candidates.
- **Constraints are AND-combined.** Each configured `equal` constraint filters every generated candidate. Equality is exact and type-sensitive; text normalization is not applied to attributes. This supports user-selected year, date, region, category, version, publisher, or identifier fields without special-casing their names.
- **Missing behavior is configured per constraint.** `missing: ignore` leaves that candidate unchanged and records `missing_ignored`; it is not positive match evidence. `missing: reject` removes the candidate and records `missing_rejected`. A present unequal value removes the candidate and records `mismatch`.

At least one candidate rule is required. Constraints may be empty. No score or priority is assigned to rules. If an exact identifier and a name rule support different entities, both remain candidates unless configured constraints disqualify one; the matcher does not silently favor one rule.

An `equal` date constraint compares the configured scalar values exactly; ISO dates are quoted strings. v0.1.0 does not infer a year from a date, parse dates from names, or compare date ranges.

For constraints, omitted and null values are missing; an empty string is an explicit value and compares exactly. For identity rules, an empty string or a normalized name that becomes empty is unusable and cannot create a candidate.

For text used by `normalized_name`, normalization is deterministic and configurable in this order: Unicode NFKC; optional punctuation handling; optional case folding; then whitespace collapse and trimming. `punctuation` is one of `preserve`, `remove`, or `space`; it applies to Unicode characters whose category starts with `P`, with `space` replacing each such character with an ASCII space before whitespace collapse. `case_fold` controls Unicode case folding. The normalized values are available in inspection output. This behavior has no TAG-specific substitutions. Attribute equality remains exact regardless of text-normalization settings. Result metadata records the Unicode database version used by the runtime so a normalization environment can be identified.

## Status and evidence model

Records are evaluated in this order:

1. An explicitly out-of-scope record (`applicable: false`) becomes `not_applicable`; it must include a stable `not_applicable_reason` code and is not sent through matching.
2. If `matching.apply_overrides: true`, a validated override is applied before automatic rules.
3. Candidate rules run, then constraints filter their union.
4. Exactly one remaining candidate becomes `resolved`; more than one becomes `ambiguous`; none becomes `unresolved`.

An override can set only `resolved` or `not_applicable` in v0.1.0. A resolved override must name a known entity; a not-applicable override must omit `entity_id`. Both require a stable reason code and a known record ID. For example:

```yaml
matching:
  apply_overrides: true

overrides:
  - record_id: source-record-001
    status: resolved
    entity_id: product-001
    reason: reviewed_identity_match
  - record_id: source-record-002
    status: not_applicable
    reason: outside_reference_scope
```

Override use must be enabled explicitly with `apply_overrides: true`; a nonempty override list with `apply_overrides: false` is a validation error. Overrides cannot contradict an input record explicitly marked not applicable.

Every result has `record_id`, `status`, nullable `entity_id`, sorted `candidate_entity_ids`, sorted `reason_codes`, and an `evidence` list. Evidence identifies the rule, its phase and outcome, and the supported record/entity values or candidate IDs needed to explain the decision. A normalized-name match records whether the entity name or a declared alias matched. An applied override records its review reason. Stable reason codes include `no_identity_candidate`, `attribute_conflict`, `insufficient_metadata`, and `multiple_valid_candidates`; a not-applicable result preserves its declared reason code. User-supplied reason codes must match `[a-z][a-z0-9_]*`.

For an unresolved record with no generated candidates, use `insufficient_metadata` when all applicable identity inputs are missing and `no_identity_candidate` when at least one usable identity value was present but matched no entity. When constraints remove all candidates, preserve the applicable `attribute_conflict` and/or `insufficient_metadata` codes. Ambiguous results use `multiple_valid_candidates` and never select one candidate automatically.

## Deterministic output and audit

Entities, records, candidates, reason codes, and evidence are sorted by stable IDs and rule IDs. Alias input order does not affect matching or output. JSON uses UTF-8, stable key ordering, fixed separators, and no timestamps; CSV uses the fixed columns `record_id,status,entity_id,candidate_entity_ids,reason_codes,evidence`, stable row ordering, UTF-8, and LF line endings. Structured CSV cells use canonical JSON serialization. Non-finite numbers and non-serializable values are rejected. Output files contain no input or output paths.

`linkage.json` and `summary.json` contain the fixed `entitylinkage-results-v1` schema version, tool version, and Unicode database version. `linkage.json` also contains sorted result records; `summary.json` contains counts for all four statuses and sorted reason-code counts. It contains no subjective quality score. Repeated runs with equivalent input values, the same EntityLinkage version, and the same Unicode database produce byte-identical JSON and CSV artifacts.

`audit` computes these counts and recurring unresolved/ambiguity reason codes without requiring an output directory. `inspect` shows the selected record, normalized name values, candidate rule outcomes, candidate entities, constraint outcomes, overrides if applied, reason codes, and final status.

## CLI and exit codes

```text
entitylinkage validate PATH
entitylinkage link PATH [--output DIR]
entitylinkage audit PATH
entitylinkage inspect RECORD_ID PATH
```

`PATH` is a configuration file or a directory containing exactly one `entitylinkage.yaml`. `link` writes `linkage.json`, `linkage.csv`, and `summary.json` to `./entitylinkage-output` by default or to the directory supplied with `--output`, then prints the summary to stdout. `validate`, `audit`, and `inspect` print their report to stdout. All commands are noninteractive, and errors go to stderr. Inspecting an unknown record ID is an execution error.

Exit codes are `0` for a valid/successful command, `1` when `audit` finds one or more ambiguous or unresolved records, and `2` for malformed input/configuration or execution errors. `link` succeeds with exit code `0` when it writes valid artifacts even if some results are unresolved or ambiguous; `audit` is the explicit quality gate. `not_applicable` does not cause audit failure.

## Packaging, CI, and documentation

The distribution uses `pyproject.toml`, `uv`, `pytest`, and `ruff`, requires Python `>=3.11`, and exposes the `entitylinkage` import and console command. The current repository license is Apache-2.0 and remains in place. The exact PyPI distribution endpoint returned HTTP 404 during the 2026-09-27 design check; availability must be rechecked before publishing.

GitHub Actions covers lint, tests, package build, installation of the built wheel into a fresh environment, installed-package CLI smoke tests, and deterministic repeated-output checks. Tests include schema and duplicate-ID validation; duplicate aliases within one entity and allowed collisions across entities; alias and configured attribute matching; NFKC, whitespace, case, and punctuation normalization; missing and conflicting attributes; all four statuses; overrides; stable reason codes and ordering; deterministic JSON/CSV; CLI exit codes; and the safety regression where adding a second valid candidate changes `resolved` to `ambiguous`.

The README explains the use case, conservative statuses, installation and quick start, entities and records, aliases and rules, missing values, manual overrides, deterministic outputs, inspection, limitations, and how EntityLinkage differs from EvidenceMatrix and LineageGuard. Public examples under `examples/basic`, `examples/ambiguous`, and `examples/manual-review` are fully synthetic, run offline, and use fictional publication/catalog records to demonstrate aliases, year constraints, collisions, unresolved records, and review decisions. No TWDisaster or private data is copied into them. The README may use the approved origin sentence: “EntityLinkage was extracted from conservative identity-matching patterns developed for a real-world multi-source data pipeline.” It will not expose private implementation details.

## Public-data dogfood decision

TWDisaster is public, but its current data model provides canonical events, source-level records, and an `event_sources.csv` table that already maps sources to events. The current public files contain 76 events, 88 sources, and 89 event-source relationships. A read-only comparison using NFKC, case folding, and whitespace normalization found one source title that exactly equals a canonical event name or alias; a substring scan found names or aliases inside 36 titles, 32 of which overlap an existing event-source relationship. Those substrings are only candidate hints, not independently curated event labels, and substring matching is not an automatic resolver in v0.1.0. Source-level records also do not express one event identity when a source supports multiple events. Using `event_sources.csv` as automatic input would reuse the mapping being evaluated. Therefore v0.1.0 will not claim a TWDisaster linkage dogfood result or copy its data into this project. The limitation and decision are documented; the public synthetic examples provide the first realistic workflow without inventing aliases or mappings. Reassess if TWDisaster later publishes independent source-specific event labels.

References inspected for this decision: [TWDisaster data model](https://github.com/KageRyo/TWDisaster/blob/main/docs/data-model.md), [events.csv](https://github.com/KageRyo/TWDisaster/blob/main/data/events.csv), [sources.csv](https://github.com/KageRyo/TWDisaster/blob/main/data/sources.csv), and [event_sources.csv](https://github.com/KageRyo/TWDisaster/blob/main/data/event_sources.csv).

## Implementation sequence

After this design is reviewed and approved, the implementation plan will sequence the work as:

1. Define immutable core models, normalization, matching rules, evidence, and conservative result classification.
2. Add strict YAML loading/validation, configured overrides, audit and inspection APIs, and deterministic JSON/CSV writers.
3. Add the CLI and fully synthetic examples.
4. Add focused tests, packaging metadata, CI, and complete README documentation.
5. Build and install the package in a clean environment, run the full acceptance suite and CLI/determinism smoke tests, then inspect the final Git and CI state.

The implementation remains limited to this design's v0.1.0 scope. Publishing a PyPI release or pushing/merging implementation changes is a separate delivery action requiring its own review.
