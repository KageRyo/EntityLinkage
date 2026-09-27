from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from entitylinkage.config import load_config
from entitylinkage.errors import EntityLinkageError
from entitylinkage.matcher import Linker
from entitylinkage.output import (
    inspection_payload,
    serialize_summary_json,
    write_artifacts,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code or 0)

    try:
        return _dispatch(arguments)
    except (EntityLinkageError, OSError, ValueError) as error:
        print(f"entitylinkage: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"entitylinkage: execution failed: {error}", file=sys.stderr)
        return 2


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="entitylinkage")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate an EntityLinkage YAML configuration")
    validate.add_argument("path", type=Path)

    link = commands.add_parser("link", help="link records and write deterministic reports")
    link.add_argument("path", type=Path)
    link.add_argument("--output", type=Path, default=Path("entitylinkage-output"))

    audit = commands.add_parser("audit", help="summarize linkage status and reason codes")
    audit.add_argument("path", type=Path)

    inspect = commands.add_parser("inspect", help="show one record's linkage evidence")
    inspect.add_argument("record_id")
    inspect.add_argument("path", type=Path)
    return parser


def _dispatch(arguments: argparse.Namespace) -> int:
    loaded = load_config(arguments.path)
    if arguments.command == "validate":
        report = {
            "valid": True,
            "entities": len(loaded.entities),
            "records": len(loaded.records),
        }
        print(json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return 0

    results = Linker(loaded.config).link(loaded.entities, loaded.records)
    if arguments.command == "link":
        write_artifacts(results, arguments.output)
        print(serialize_summary_json(results))
        return 0
    if arguments.command == "audit":
        print(serialize_summary_json(results))
        return int(any(result.status in {"ambiguous", "unresolved"} for result in results))
    if arguments.command == "inspect":
        record = next((item for item in loaded.records if item.id == arguments.record_id), None)
        if record is None:
            raise EntityLinkageError(f"unknown record ID: {arguments.record_id!r}")
        result = next(item for item in results if item.record_id == record.id)
        print(
            json.dumps(
                inspection_payload(record, result),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        )
        return 0
    raise EntityLinkageError(f"unknown command: {arguments.command!r}")
