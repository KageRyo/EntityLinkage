# EntityLinkage

EntityLinkage is a small Python library and command-line tool for linking external records to a canonical set of entities. It makes conservative, explainable decisions from configured identity rules and preserves ambiguity and missing data for review.

> EntityLinkage was extracted from conservative identity-matching patterns developed for a real-world multi-source data pipeline.

## Decisions stay conservative

- **`resolved`** — exactly one candidate remains after all configured constraints.
- **`ambiguous`** — multiple candidates remain; EntityLinkage does not pick one by score or order.
- **`unresolved`** — no candidate remains. Reason codes distinguish missing identity information from usable values that matched nothing and from constraints that rejected candidates.
- **`not_applicable`** — the record is explicitly outside the configured entity scope.

Every result includes candidate IDs, stable reason codes, and evidence for candidate rules, constraints, and any reviewed override. A declared alias is evidence supplied by the configuration; the tool does not invent aliases or use fuzzy matching, external services, or machine learning.

## Install and try the examples

EntityLinkage requires Python 3.11 or newer. From a source checkout, install the locked development environment with [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked
```

You can also install the package from a checkout with `python -m pip install .`. PyYAML is the only runtime dependency.

Validate and link the synthetic basic example:

```sh
uv run --locked entitylinkage validate examples/basic
uv run --locked entitylinkage link examples/basic --output ./entitylinkage-output
uv run --locked entitylinkage inspect source-record-001 examples/basic
```

`link` writes `linkage.json`, `linkage.csv`, and `summary.json`. It returns success when the reports are written, even when records are ambiguous or unresolved. Use `audit` as a quality gate; it returns exit code 1 when either status occurs:

```sh
uv run --locked entitylinkage audit examples/basic
```

The examples under [`examples/`](examples/) use fictional publication and catalog names. They demonstrate alias matching, a year constraint, ambiguity, an unmatched record, an out-of-scope record, and a reviewed manual decision.

## Configuration

Each input is a YAML file or a directory containing `entitylinkage.yaml`. The top-level document has `version: 1`, `entities`, `records`, and `matching`, with an optional `overrides` list. See [`examples/basic/entitylinkage.yaml`](examples/basic/entitylinkage.yaml) for a complete example.

An entity has a unique `id`, a canonical `name`, optional explicit string `aliases`, and optional flat scalar `attributes`. A record has a unique `id`, an optional `name`, flat `attributes`, and an optional `applicable` flag. Attribute keys are user-defined flat field names. Values may be strings, integers, finite floats, booleans, or null; nested mappings and lists are rejected. Quote date-like strings in YAML so they are not parsed as dates. Empty strings are present values for constraints, while omitted and null attribute values are missing.

`matching.normalization` requires `case_fold` and `punctuation` (`preserve`, `remove`, or `space`). Names are normalized with Unicode NFKC, configured punctuation handling, optional case folding, and whitespace collapse. The same settings apply to canonical names, aliases, and record names; normalized record names appear in inspection output.

At least one candidate rule is required:

- `normalized_name` compares a record name with entity names and declared aliases.
- `exact_value` compares configured `name` or `attributes.<key>` fields using type-sensitive equality. Empty identity values do not create candidates.

Candidate rules are OR-combined: every entity supported by any rule remains a candidate. Constraints are AND-combined and filter each candidate. The `equal` constraint compares fields exactly and requires `missing: ignore` or `missing: reject`. Ignoring a missing value keeps the candidate without treating missing data as match evidence; rejecting it removes the candidate.

## Reviewed overrides

Overrides are intended for explicit reviewed decisions. Set `matching.apply_overrides: true` to enable them. A `resolved` override requires a known `entity_id`; a `not_applicable` override omits it. Both require a stable reason code such as `reviewed_identity_match`. Unknown IDs, duplicate override record IDs, invalid reason codes, disabled overrides, and overrides that contradict an input marked not applicable are rejected. When enabled, a valid override takes precedence over automatic matching and its reason appears in the result evidence.

## Python API

```python
from pathlib import Path

from entitylinkage import Linker
from entitylinkage.config import load_config

inputs = load_config(Path("examples/basic"))
results = Linker(inputs.config).link(inputs.entities, inputs.records)
for result in results:
    print(result.record_id, result.status, result.entity_id, result.reason_codes)
```

The core API accepts `Entity`, `Record`, and `LinkageConfig` values directly; configuration loading, file output, and command-line behavior remain separate from matching. `load_config` rejects duplicate YAML keys, unknown schema keys, malformed scalar values, invalid references, and duplicate normalized labels within one entity. Name or alias collisions across different entities are valid and result in ambiguity when both remain candidates.

## Reports and inspection

The CLI provides four noninteractive commands:

```text
entitylinkage validate PATH
entitylinkage link PATH [--output DIR]
entitylinkage audit PATH
entitylinkage inspect RECORD_ID PATH
```

JSON uses stable key ordering and compact encoding. CSV has the fixed columns `record_id,status,entity_id,candidate_entity_ids,reason_codes,evidence`; structured cells contain canonical JSON and rows end with LF. Reports include the EntityLinkage version and Unicode database version, contain no timestamps or filesystem paths, and are byte-identical for equivalent inputs under the same runtime versions. `inspect` shows the input record, normalized record name, rule evidence, candidate IDs, reasons, and final decision.

## Scope and limitations

EntityLinkage performs deterministic exact matching; it does not infer dates, apply domain-specific substitutions, score similarity, or guarantee that declared data is true. Review the evidence and source provenance before using a manual override. Unicode normalization behavior can vary with the runtime's Unicode database version, which is recorded in report metadata.

EntityLinkage can produce mapping evidence for tools such as EvidenceMatrix, which analyzes entity-by-source evidence coverage. It does not require or replace EvidenceMatrix. It also does not provide LineageGuard's artifact provenance and chain-of-custody functions.

The public TWDisaster files currently include event-source relationships and observations already connected to events. Those mappings are not independent labels for validating a source-to-event resolver, so this project does not claim a TWDisaster dogfood result or copy TWDisaster data. See the [read-only review](docs/dogfood/twdisaster.md).

## Development

```sh
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
```
