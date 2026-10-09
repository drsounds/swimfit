"""Command line interface for the Swimler anonymizer."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from swimler.anonymizer import LocalOllamaVerifier
from swimler.processing import clean_bytes, clean_zip

DISCLAIMER = (
    "Disclaimer: Swimler is an aid, not a guarantee of GDPR compliance. "
    "You remain responsible for reviewing the output. Processing is local; "
    "no external services are used."
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swimler",
        description="Anonymize personal data in a UTF-8 text file or ZIP archive.",
    )
    parser.add_argument("input", type=Path, help="Input text file or ZIP archive")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Output directory (default: <input directory>/swimler-output)",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Accept all file changes automatically"
    )
    parser.add_argument("--model", default="llama3.2", help="Local Ollama model name")
    parser.add_argument(
        "--brand-word",
        action="append",
        default=[],
        help="Brand name to preserve (can be specified more than once)",
    )
    parser.add_argument(
        "--audit-log",
        type=Path,
        help="Audit log path (default: output directory/<input name>.audit.log)",
    )
    return parser


def _review(original: bytes, cleaned: bytes, filename: str) -> tuple[bool, bytes]:
    try:
        before = original.decode("utf-8").splitlines(keepends=True)
        after = cleaned.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return True, cleaned
    print(f"\nChanges for {filename}:")
    print(
        "".join(
            difflib.unified_diff(
                before, after, fromfile=f"{filename} (original)", tofile=f"{filename} (cleaned)"
            )
        )
    )
    while True:
        answer = input("[a]ccept, [m]end, [r]eject? ").strip().lower()
        if answer in {"a", "accept"}:
            return True, cleaned
        if answer in {"r", "reject"}:
            return False, original
        if answer in {"m", "amend"}:
            editor = shlex.split(os.environ.get("EDITOR", "vi"))
            with tempfile.TemporaryDirectory() as directory:
                amended_path = Path(directory) / f"amended{Path(filename).suffix}"
                amended_path.write_bytes(cleaned)
                subprocess.run([*editor, str(amended_path)], check=True)
                return True, amended_path.read_bytes()
        print("Choose accept, amend, or reject.")


def _audit_write(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as audit:
        audit.write(json.dumps(record, sort_keys=True) + "\n")


def _output_path(source: Path, output_dir: Path | None) -> Path:
    directory = output_dir or source.parent / "swimler-output"
    return directory / source.name


def _write_output(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(data)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _same_file(first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    try:
        return first.exists() and second.exists() and os.path.samefile(first, second)
    except OSError:
        return False


def _confirm_overwrite(path: Path, yes: bool) -> bool:
    if not path.exists() or yes:
        return True
    answer = input(f"Output {path} exists. Overwrite? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _process(
    source: Path,
    destination: Path,
    audit_path: Path,
    yes: bool,
    model: str,
    brands: Iterable[str],
) -> int:
    original = source.read_bytes()
    verifier = LocalOllamaVerifier(model)
    if zipfile.is_zipfile(source):
        reviewer = None if yes else _review
        cleaned, records = clean_zip(original, verifier, brands, reviewer)
        _write_output(destination, cleaned)
        for record in records:
            _audit_write(
                audit_path,
                {"timestamp": datetime.now(timezone.utc).isoformat(), **record},
            )
        _audit_write(
            audit_path,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "file": source.name,
                "operation": "write",
                "output": str(destination),
            },
        )
        return 0

    cleaned, records, kind = clean_bytes(source.name, original, verifier, brands)
    accepted = True
    if kind == "text" and cleaned != original and not yes:
        accepted, cleaned = _review(original, cleaned, source.name)
    if accepted:
        _write_output(destination, cleaned)
    if kind == "binary":
        records.append({"file": source.name, "operation": "skip_binary"})
    for record in records:
        _audit_write(
            audit_path,
            {"timestamp": datetime.now(timezone.utc).isoformat(), **record},
        )
    _audit_write(
        audit_path,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file": source.name,
            "operation": "write" if accepted else "reject",
            "output": str(destination) if accepted else None,
        },
    )
    return 0 if accepted else 1


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    print(DISCLAIMER, file=sys.stderr)

    source = args.input.expanduser().resolve()
    if not source.is_file():
        parser.error(f"input is not a file: {source}")
    destination = _output_path(source, args.output_dir.expanduser().resolve() if args.output_dir else None)
    if source == destination.resolve():
        parser.error("output path must not overwrite the input file")
    audit_path = (
        args.audit_log.expanduser().resolve()
        if args.audit_log
        else destination.parent / f"{source.name}.audit.log"
    )
    if _same_file(source, destination):
        parser.error("output path must not overwrite the input file")
    if _same_file(audit_path, source) or _same_file(audit_path, destination):
        parser.error("audit log path must differ from input and output files")
    if not _confirm_overwrite(destination, args.yes):
        print("Output was not overwritten.", file=sys.stderr)
        return 1

    try:
        return _process(
            source,
            destination,
            audit_path,
            args.yes,
            args.model,
            args.brand_word,
        )
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f"swimler: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            f"swimler: local anonymization failed ({exc}). "
            "No output was written.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
