# EntityLinkage v0.1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python library and CLI that links external records to canonical entities conservatively and produces deterministic, explainable results.

**Architecture:** Use immutable domain models and pure normalization/matching functions, with strict YAML parsing, explicit overrides, deterministic serializers, and a thin `argparse` CLI around the core. Keep the examples synthetic and the package independent of TAG-Twin, network services, and databases.

**Tech Stack:** Python 3.11+, PyYAML, `uv`, `pytest`, `ruff`, Hatchling, GitHub Actions.

**Spec:** [docs/superpowers/specs/2026-09-27-entitylinkage-design.md](../specs/2026-09-27-entitylinkage-design.md)

## Global Constraints

- Require Python `>=3.11`.
- PyYAML is the only required runtime dependency.
- Do not depend on TAG-Twin, TWDisaster, disaster-specific schemas, HydroCast, typhoon naming rules, or private data.
- No database or network calls are required.
- Keep `resolved`, `ambiguous`, `unresolved`, and `not_applicable` distinct; never auto-select among multiple valid candidates.
- OR-combine candidate rules, AND-combine constraints, and make missing-value behavior explicit.
- Manual overrides are explicit, validated, and applied only when `apply_overrides: true`.
- Keep JSON, CSV, candidate ordering, evidence, and reason codes deterministic; do not insert timestamps.
- Keep v0.1.0 free of fuzzy or ML-based resolution, review UI, lineage DAGs, spatial joins, and dataset-specific validation.
- Use only fully synthetic example records; document the TWDisaster dogfood limitation without copying its data or reusing its crosswalk as evidence.
- Build and verify the package, but do not publish it as part of this implementation plan.

## Review Focus

- Duplicate YAML mapping keys can silently overwrite earlier values; `test_loader_rejects_duplicate_mapping_keys` must prove they fail validation (Task 4).
- YAML can coerce unquoted dates and booleans into non-string types; `test_loader_rejects_unquoted_date_attribute` and `test_loader_rejects_non_boolean_applicable` must prove the parser rejects them (Task 4).
- Exact scalar equality must distinguish `false` from `0`, and empty string from missing; `test_equal_constraint_is_type_sensitive` and `test_empty_constraint_value_is_present` must pin that behavior (Task 3).
- Records with no usable identity values differ from usable values that match nothing; `test_all_identity_inputs_missing_is_insufficient_metadata` and `test_usable_unmatched_identity_is_no_identity_candidate` must prove the stable reason codes (Task 3).
- CSV evidence may contain commas, quotes, or newlines; `test_csv_round_trip_preserves_structured_evidence` must prove valid LF-delimited CSV round-trips those cells (Task 5).

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `pyproject.toml`, `uv.lock` | Package metadata, runtime/development dependencies, build settings, and tool configuration. |
| `src/entitylinkage/__init__.py`, `model.py`, `errors.py` | Public API, immutable input/result types, version, and domain exceptions. |
| `src/entitylinkage/normalize.py`, `matcher.py` | Deterministic text normalization and pure conservative candidate evaluation. |
| `src/entitylinkage/config.py`, `overrides.py` | Safe YAML loading, strict schema validation, and explicit reviewed decisions. |
| `src/entitylinkage/audit.py`, `output.py` | Status/reason summaries, inspection payloads, and deterministic JSON/CSV artifacts. |
| `src/entitylinkage/cli.py` | Noninteractive `validate`, `link`, `audit`, and `inspect` commands. |
| `tests/unit/`, `tests/cli/` | Focused unit and command contract tests, including `tests/unit/test_examples.py`. |
| `examples/basic/`, `examples/ambiguous/`, `examples/manual-review/` | Fully synthetic offline workflows with known expected statuses. |
| `docs/dogfood/twdisaster.md` | Public-data dogfood decision, method, and current limitation. |
| `README.md` | Installation, quick start, data contract, statuses, rules, limitations, and related-tool boundaries. |
| `.github/workflows/ci.yml` | Lint, tests, wheel build/install, CLI smoke tests, and deterministic-output check. |

## Shared Interfaces

Use frozen dataclasses and copy incoming mappings into read-only mappings. Define `Scalar = str | int | float | bool | None`. `Entity` has `id: str`, `name: str`, `aliases: tuple[str, ...] = ()`, and `attributes: Mapping[str, Scalar]`. `Record` has `id: str`, `name: str | None = None`, `attributes: Mapping[str, Scalar]`, `applicable: bool = True`, and `not_applicable_reason: str | None = None`.

`NormalizationConfig` has `case_fold: bool` and `punctuation: Literal["preserve", "remove", "space"]`. `CandidateRule` has `id`, `type: Literal["normalized_name", "exact_value"]`, and optional `entity_field`/`record_field` references required only for `exact_value`. `EqualConstraint` has `id`, `entity_field`, `record_field`, and `missing: Literal["ignore", "reject"]`. `Override` has `record_id`, `status: Literal["resolved", "not_applicable"]`, `reason`, and optional `entity_id` required only for `resolved`.

`LinkageConfig` contains normalization, candidate rules, constraints, required `apply_overrides`, and overrides. `Evidence` records `rule_id`, `phase: Literal["candidate", "constraint", "override"]`, a stable outcome, optional `entity_id`, and structured details. `LinkageResult` records `record_id`, status, nullable `entity_id`, sorted candidate IDs, sorted reason codes, normalized record name, and ordered evidence. `AuditSummary` has counts for all four statuses and sorted reason-code counts. `Linker(config: LinkageConfig).link(entities: Sequence[Entity], records: Sequence[Record]) -> tuple[LinkageResult, ...]` is the core API and sorts output by record ID. `load_config(path: Path) -> LinkageInput` returns validated entities, records, and config. Tests and later tasks must use these names and types consistently.

---

### Task 1: Scaffold the installable package

**Files:** Create `pyproject.toml`, `uv.lock`, an initially empty `src/entitylinkage/__init__.py`, `tests/unit/test_package.py`, and `.gitignore` entries for `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `dist/`, and `build/`.

**Interfaces:** Export `__version__ = "0.1.0"` from `entitylinkage`. Configure Python `>=3.11`, PyYAML as the only runtime dependency, and `pytest`/`ruff` as development dependencies. Do not add the console entry point until Task 6 creates `cli.py`.

- [x] **Step 1: Add the minimal Hatchling `pyproject.toml` with package metadata, Python floor, runtime/dev dependencies, and tool settings; add the empty package initializer and ignore entries; run `uv lock` and `uv sync --locked`.**
- [x] **Step 2: Write the package metadata test** in `tests/unit/test_package.py`; assert `entitylinkage.__version__ == "0.1.0"` and `importlib.metadata.version("entitylinkage") == "0.1.0"` in the synced project environment.
- [x] **Step 3: Run `uv run --locked pytest tests/unit/test_package.py -q`; it must fail because the empty initializer has no `__version__`.**
- [x] **Step 4: Add `__version__ = "0.1.0"` and rerun `uv run --locked pytest tests/unit/test_package.py -q`; both version assertions must pass.**
- [x] **Step 5: Run `uv run --locked ruff check .` and commit as `build: scaffold EntityLinkage package`.**

### Task 2: Add immutable models and deterministic normalization

**Files:** Create `src/entitylinkage/model.py`, `src/entitylinkage/errors.py`, `src/entitylinkage/normalize.py`, and `tests/unit/test_model.py`, `tests/unit/test_normalize.py`; update `.gitignore` for Python bytecode caches.

**Interfaces:** Implement the shared model types above, `EntityLinkageError`, `ConfigError`, and `normalize_text(value: str, config: NormalizationConfig) -> str`. Normalization order is NFKC, configured Unicode punctuation handling, optional Unicode case folding, then whitespace collapse and trim.

- [x] **Step 1: Write tests** asserting `normalize_text("  Ａlpha—B  ", NormalizationConfig(case_fold=True, punctuation="space")) == "alpha b"`; assert `case_fold=False` preserves case; assert punctuation modes produce `"a,b"`, `"ab"`, and `"a b"` for `"A,B"`; assert frozen model values reject field reassignment and copied attributes cannot be mutated through the original input mapping.
- [x] **Step 2: Run `uv run --locked pytest tests/unit/test_model.py tests/unit/test_normalize.py -q`; the normalization imports/tests must fail before implementation.**
- [x] **Step 3: Implement the dataclasses, read-only mapping copies, domain exceptions, and `normalize_text` in the named files; ignore `__pycache__/` and `*.py[cod]`.**
- [x] **Step 4: Run `uv run --locked pytest tests/unit/test_model.py tests/unit/test_normalize.py -q`; all normalization and immutability assertions must pass.**
- [x] **Step 5: Run `uv run --locked ruff check src/entitylinkage tests/unit` and commit as `feat: add linkage models and normalization`.**

### Task 3: Implement conservative matching and evidence

**Files:** Create `src/entitylinkage/matcher.py` and `tests/unit/test_matcher.py`; update `src/entitylinkage/__init__.py` to export `Linker`.

**Interfaces:** Implement `Linker(config: LinkageConfig).link(entities, records) -> tuple[LinkageResult, ...]`. Candidate rules are OR-combined; `normalized_name` matches an entity name or declared alias, while `exact_value` uses type-sensitive equality on configured fields. Apply each `EqualConstraint` to every generated candidate using its `ignore` or `reject` missing behavior. Sort candidates, evidence, and reason codes by stable IDs.

- [x] **Step 1: Write tests** asserting an alias plus matching `year` resolves to the sole entity with candidate and constraint evidence; exact `publisher_id` identity values can generate candidates; two valid candidates yield `ambiguous`, `entity_id is None`, sorted candidate IDs, and `multiple_valid_candidates`; no candidates yield `unresolved`; adding a second valid entity changes `resolved` to `ambiguous`; OR rules supporting different entities retain both candidates; empty identity values never generate candidates; missing `ignore` leaves a candidate while missing `reject` removes it; conflicting attributes yield `attribute_conflict`; results sort by record ID independent of input order; `from entitylinkage import Linker` works.
- [x] **Step 2: Add the Review Focus tests** `test_equal_constraint_is_type_sensitive`, `test_empty_constraint_value_is_present`, `test_all_identity_inputs_missing_is_insufficient_metadata`, and `test_usable_unmatched_identity_is_no_identity_candidate`; assert `False` does not equal `0`, `""` is present, and the two unresolved inputs receive their distinct reason codes.
- [x] **Step 3: Run `uv run --locked pytest tests/unit/test_matcher.py -q`; the tests must fail before matching is implemented.**
- [x] **Step 4: Implement candidate collection, constraint filtering, status classification, stable reason codes, normalized-name capture, and rule evidence in `matcher.py`; export `Linker` from `entitylinkage.__init__`.**
- [x] **Step 5: Run `uv run --locked pytest tests/unit/test_matcher.py -q` and `uv run --locked ruff check src/entitylinkage/matcher.py tests/unit/test_matcher.py`; all assertions must pass.**
- [x] **Step 6: Commit as `feat: add conservative entity matching`.**

### Task 4: Load and validate YAML; apply reviewed overrides

**Files:** Create `src/entitylinkage/config.py`, `src/entitylinkage/overrides.py`, `tests/unit/test_config.py`, and `tests/unit/test_overrides.py`; update `matcher.py` only to call the override helper before automatic matching.

**Interfaces:** Implement `LinkageInput(entities, records, config)` and `load_config(path: Path) -> LinkageInput`. Accept a YAML file or a directory containing `entitylinkage.yaml`. Reject duplicate YAML keys, unknown schema/rule keys, unsupported versions/types, invalid field references, duplicate IDs, duplicate normalized labels within one entity, malformed attribute scalars, and invalid override declarations. Cross-entity name/alias collisions remain valid. Implement `apply_override(record: Record, entities_by_id: Mapping[str, Entity], overrides_by_record_id: Mapping[str, Override]) -> LinkageResult | None` and invoke it only when `apply_overrides` is true.

- [x] **Step 1: Write loader tests** for one valid config; required `version`, normalization values, nonempty candidate rules, and boolean `apply_overrides`; duplicate entity/record/rule/override IDs; same-entity normalized alias duplicates; allowed cross-entity aliases; unknown keys and rule types; bad field paths; nested attributes; duplicate YAML keys; unquoted YAML dates; non-boolean `applicable`; non-finite floats; and a directory missing `entitylinkage.yaml`. Assert `applicable: false` requires `not_applicable_reason`, while a normal record may omit it.
- [x] **Step 2: Write override tests** asserting disabled overrides are rejected, a valid resolved override preserves `reviewed_identity_match` and takes precedence when enabled, `not_applicable` overrides omit `entity_id`, unknown IDs and malformed reason codes fail, and overrides cannot contradict an explicitly not-applicable record.
- [x] **Step 3: Run `uv run --locked pytest tests/unit/test_config.py tests/unit/test_overrides.py -q`; the tests must fail before the loader and override implementation.**
- [x] **Step 4: Implement safe YAML parsing with duplicate-key detection, strict field/type validation, normalized alias uniqueness checks, and override application with stable evidence.**
- [x] **Step 5: Run `uv run --locked pytest tests/unit/test_config.py tests/unit/test_overrides.py tests/unit/test_matcher.py -q`; the full loader, override, and matcher suites must pass.**
- [x] **Step 6: Run `uv run --locked ruff check src/entitylinkage tests/unit` and commit as `feat: validate linkage configs and overrides`.**

### Task 5: Add audit, inspection payloads, and deterministic artifacts

**Files:** Create `src/entitylinkage/audit.py`, `src/entitylinkage/output.py`, `tests/unit/test_audit.py`, and `tests/unit/test_output.py`.

**Interfaces:** Implement `audit_results(results: Sequence[LinkageResult]) -> AuditSummary`, `serialize_linkage_json(results) -> str`, `serialize_summary_json(results) -> str`, `serialize_linkage_csv(results) -> str`, `inspection_payload(record: Record, result: LinkageResult) -> dict[str, object]`, and `write_artifacts(results, output_dir: Path) -> None`. JSON and CSV must use the fixed schemas/columns in the design, sorted keys/IDs, canonical JSON for structured CSV cells, UTF-8, LF newlines, tool and Unicode database versions, and no timestamps or paths.

- [x] **Step 1: Write tests** for all four status counts, sorted recurring reason counts, stable JSON bytes, stable CSV bytes, alias-order-independent output, metadata version fields, no timestamps/paths, and the fixed CSV header `record_id,status,entity_id,candidate_entity_ids,reason_codes,evidence`.
- [x] **Step 2: Add `test_csv_round_trip_preserves_structured_evidence`**; serialize evidence containing a comma, quote, and newline, parse with `csv.DictReader`, then assert the parsed evidence JSON equals the original structure and output line endings are LF.
- [x] **Step 3: Run `uv run --locked pytest tests/unit/test_audit.py tests/unit/test_output.py -q`; tests must fail before these helpers exist.**
- [x] **Step 4: Implement the audit model, stable serializers, inspection payload, and artifact writer.**
- [x] **Step 5: Run `uv run --locked pytest tests/unit/test_audit.py tests/unit/test_output.py -q` and `uv run --locked ruff check src/entitylinkage tests/unit`; all assertions must pass.**
- [x] **Step 6: Commit as `feat: add deterministic linkage reports`.**

### Task 6: Add the noninteractive CLI

**Files:** Create `src/entitylinkage/cli.py`, `tests/cli/test_cli.py`; update `pyproject.toml` with the `entitylinkage = "entitylinkage.cli:main"` console script and export `main` only if needed by the package API.

**Interfaces:** Implement `main(argv: Sequence[str] | None = None) -> int` with `validate PATH`, `link PATH [--output DIR]`, `audit PATH`, and `inspect RECORD_ID PATH`. `link` defaults to `./entitylinkage-output`; `audit` returns 1 for ambiguous/unresolved results; malformed input and execution errors return 2; all other successful commands return 0. Print reports to stdout and errors to stderr.

- [x] **Step 1: Write CLI tests** invoking `main([...])` and asserting validate success; link creates `linkage.json`, `linkage.csv`, and `summary.json`; audit returns 1 for unresolved/ambiguous and 0 when only resolved/not-applicable records exist; inspect prints the record, normalized name, rule evidence, and final result; unknown record ID returns 2; malformed config returns 2 and writes the diagnostic to stderr.
- [x] **Step 2: Run `uv run --locked pytest tests/cli/test_cli.py -q`; tests must fail before command parsing and dispatch exist.**
- [x] **Step 3: Implement argparse commands, config loading, stable JSON stdout, output-directory handling, and exit/error mapping in `cli.py`; add the console entry point.**
- [x] **Step 4: Run `uv run --locked pytest tests/cli/test_cli.py -q` and `uv run --locked entitylinkage --help`; all command/exit-code assertions must pass and help must list the four commands.**
- [x] **Step 5: Run `uv run --locked ruff check src/entitylinkage tests/cli` and commit as `feat: add EntityLinkage CLI`.**

### Task 7: Add synthetic examples and complete user documentation

**Files:** Create `examples/basic/entitylinkage.yaml`, `examples/ambiguous/entitylinkage.yaml`, `examples/manual-review/entitylinkage.yaml`, `docs/dogfood/twdisaster.md`; replace `README.md`.

**Interfaces:** The basic example has four records with exact outcomes: alias plus year resolves to `product-001`; alias without year remains ambiguous between `product-001` and `product-002`; unknown title is unresolved; an out-of-scope record is not applicable. The ambiguous example isolates a shared-alias ambiguity. The manual-review example resolves an otherwise metadata-poor record only through an enabled explicit override.

- [x] **Step 1: Write example contract tests** loading all three directories and asserting the basic status sequence/counts, sorted ambiguous candidates, and manual override reason; assert all example names, aliases, and IDs are fictional publication/catalog values.
- [x] **Step 2: Run `uv run --locked pytest tests/unit/test_examples.py -q`; the tests must fail until the example files exist.**
- [x] **Step 3: Add the three synthetic YAML configs and run `validate`, `link`, `audit`, and `inspect` against them; confirm outputs match the example contract tests.**
- [x] **Step 4: Refresh the public TWDisaster data-model/crosswalk inspection read-only and document why it does not provide independent source-specific identity evidence; include source links, the inspection date, and no copied rows or private implementation details.**
- [x] **Step 5: Write README sections for purpose, conservative statuses, installation, quick start, entities, records, aliases, rules, missing values, manual overrides, the `Linker` Python API, deterministic outputs, inspection, limitations, EvidenceMatrix/LineageGuard boundaries, and the approved origin statement: “EntityLinkage was extracted from conservative identity-matching patterns developed for a real-world multi-source data pipeline.”**
- [x] **Step 6: Run `uv run --locked pytest tests/unit/test_examples.py -q`, all four CLI commands for each applicable example, and `uv run --locked ruff check .`; commit as `docs: add synthetic examples and usage guide`.**

### Task 8: Add CI and verify the distributable artifact

**Files:** Create `.github/workflows/ci.yml`; update `uv.lock` if tool configuration changes.

**Interfaces:** Run CI on Python 3.11, 3.12, and 3.13 using `uv`; use [actions/checkout v7](https://github.com/actions/checkout/releases), [actions/setup-python v7](https://github.com/actions/setup-python/releases), and [astral-sh/setup-uv v10.1.0](https://github.com/astral-sh/setup-uv) pinned to `bec219d24cd3e171d82865faccec33120bb574f4`, rechecking the official action references before implementation. CI must cover Ruff lint/format checks, pytest, wheel build, installation of the built wheel in a fresh virtual environment, installed CLI smoke commands, and repeated-output byte comparisons.

- [x] **Step 1: Write the workflow** with checkout, Python/uv setup, locked dependency sync, Ruff, pytest, `uv build`, and a fresh-environment wheel install; invoke installed `entitylinkage validate examples/basic`, `link`, `audit`, and `inspect`.
- [x] **Step 2: Run `uv run --locked ruff check .`, `uv run --locked ruff format --check .`, `uv run --locked pytest`, and `uv build`; all must pass and produce a wheel.**
- [x] **Step 3: Create a clean Python 3.11 environment, install only `dist/*.whl`, then run the installed console command against `examples/basic`; it must produce the expected counts without importing from the checkout.**
- [x] **Step 4: Run the same `link` command twice into separate directories and use `cmp` on `linkage.json`, `linkage.csv`, and `summary.json`; every pair must be byte-identical.**
- [x] **Step 5: Review the wheel contents and runtime dependency metadata; confirm there is no TAG-Twin runtime dependency or private data, then commit as `ci: verify EntityLinkage package and CLI`.**

## Plan Self-Review

- **Spec coverage:** Tasks 2–4 cover the data model, normalization, candidate/constraint rules, missing semantics, statuses, evidence, strict input validation, and overrides. Tasks 5–6 cover deterministic artifacts, audit/inspect, CLI behavior, and exit codes. Tasks 7–8 cover examples, documentation, dogfood limits, packaging, CI, offline install, and acceptance verification.
- **Step scan:** Every implementation step names the file or command and the observable assertion/result; the TDD steps identify failing tests before implementation and passing checks afterward.
- **Type consistency:** All tasks use the shared `Entity`, `Record`, `LinkageConfig`, `LinkageInput`, `LinkageResult`, `Evidence`, `Linker`, and serializer signatures defined above.
- **Review Focus:** Each of the five cases has named regression tests in its owning task; the matching task also covers the required second-candidate safety regression.
- **Proportion:** The plan fixes interfaces, tests, commands, and commit boundaries without prescribing function bodies already determined by those tests.
