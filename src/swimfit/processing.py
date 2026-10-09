"""File and ZIP processing without extracting archive members to disk."""

from __future__ import annotations

import io
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from swimfit.anonymizer import Detector, anonymize_line


def _clean_rows(
    text: str, detector: Detector, brands: Iterable[str], member: str
) -> tuple[str, list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    lines = text.splitlines(keepends=True)
    cleaned_lines: list[str] = []
    for row_number, line in enumerate(lines, start=1):
        content = line.rstrip("\r\n")
        ending = line[len(content) :]
        cleaned, operations = anonymize_line(content, detector, brands)
        cleaned_lines.append(cleaned + ending)
        if operations:
            records.append(
                {
                    "file": member,
                    "row": row_number,
                    "operation": "redact",
                    "counts": operations,
                }
            )
    return "".join(cleaned_lines), records


def _clean_delimited(
    text: str,
    suffix: str,
    detector: Detector,
    brands: Iterable[str],
    member: str,
) -> tuple[str, list[dict[str, object]]]:
    if not text:
        return text, []
    separator = "\t" if suffix in {".tsv", ".tab"} else ","
    try:
        frame = pd.read_csv(
            io.StringIO(text),
            sep=separator,
            header=None,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            skip_blank_lines=False,
        )
    except pd.errors.ParserError as exc:
        raise ValueError(f"Unable to parse delimited text file {member!r}: {exc}") from exc

    records: list[dict[str, object]] = []
    for row_index in range(len(frame.index)):
        for column_index in range(len(frame.columns)):
            original = frame.iat[row_index, column_index]
            cleaned, operations = anonymize_line(str(original), detector, brands)
            frame.iat[row_index, column_index] = cleaned
            if operations:
                records.append(
                    {
                        "file": member,
                        "row": row_index + 1,
                        "column": column_index + 1,
                        "operation": "redact",
                        "counts": operations,
                    }
                )

    output = io.StringIO(newline="")
    frame.to_csv(output, index=False, header=False, sep=separator, lineterminator="\n")
    cleaned_text = output.getvalue()
    if text.endswith(("\n", "\r")) and cleaned_text and not cleaned_text.endswith("\n"):
        cleaned_text += "\n"
    if text.startswith("\ufeff"):
        cleaned_text = "\ufeff" + cleaned_text
    return cleaned_text, records


def clean_bytes(
    member: str,
    data: bytes,
    detector: Detector,
    brands: Iterable[str] = (),
) -> tuple[bytes, list[dict[str, object]], str]:
    """Clean UTF-8 text bytes, returning unchanged bytes for binary data."""
    if b"\x00" in data:
        return data, [], "binary"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data, [], "binary"

    if Path(member).suffix.lower() in {".csv", ".tsv", ".tab"}:
        cleaned, records = _clean_delimited(
            text, Path(member).suffix.lower(), detector, brands, member
        )
    else:
        cleaned, records = _clean_rows(text, detector, brands, member)
    return cleaned.encode("utf-8"), records, "text"


def clean_zip(
    data: bytes,
    detector: Detector,
    brands: Iterable[str] = (),
    reviewer=None,
) -> tuple[bytes, list[dict[str, object]]]:
    """Clean text entries while copying all other ZIP members unchanged."""
    import zipfile

    source = io.BytesIO(data)
    output = io.BytesIO()
    records: list[dict[str, object]] = []
    with zipfile.ZipFile(source, "r") as archive:
        with zipfile.ZipFile(output, "w") as cleaned_archive:
            cleaned_archive.comment = archive.comment
            for info in archive.infolist():
                member_data = archive.read(info)
                if info.is_dir():
                    cleaned_archive.writestr(info, member_data)
                    continue
                cleaned_data, member_records, kind = clean_bytes(
                    info.filename, member_data, detector, brands
                )
                if kind == "text" and cleaned_data != member_data and reviewer is not None:
                    accepted, cleaned_data = reviewer(
                        member_data, cleaned_data, info.filename
                    )
                    if not accepted:
                        member_records.append(
                            {"file": info.filename, "operation": "reject"}
                        )
                cleaned_archive.writestr(info, cleaned_data)
                records.extend(member_records)
                if kind == "binary":
                    records.append(
                        {"file": info.filename, "operation": "skip_binary"}
                    )
    return output.getvalue(), records
