"""Reference integrity and bounded multimodal artifact inspection."""

from __future__ import annotations

import csv
import hashlib
import io
import mimetypes
import os
import re
import struct
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET


EXTENSION_TYPES = {
    ".png": "screenshot", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".bmp": "image", ".webp": "image", ".pdf": "pdf", ".docx": "document",
    ".doc": "document", ".odt": "document", ".xlsx": "worksheet",
    ".xls": "worksheet", ".ods": "worksheet", ".csv": "csv", ".tsv": "csv",
    ".html": "html", ".htm": "html", ".md": "plain_text", ".txt": "plain_text",
    ".json": "structured_data", ".jsonl": "structured_data", ".yaml": "structured_data",
    ".yml": "structured_data", ".py": "source_code", ".js": "source_code",
    ".ts": "source_code", ".tsx": "source_code", ".jsx": "source_code",
    ".java": "source_code", ".go": "source_code", ".rs": "source_code",
    ".pptx": "presentation", ".eml": "email", ".wav": "audio", ".mp3": "audio",
    ".mp4": "video", ".mov": "video",
}


class ReferenceError(ValueError):
    pass


class ReferenceChangedError(ReferenceError):
    pass


def path_from_locator(locator: str) -> Path:
    """Resolve a local path/file URI. Network and arbitrary URL schemes are rejected."""
    value = (locator or "").strip()
    if not value:
        raise ReferenceError("source locator is required")
    if value.startswith("\\\\"):
        raise ReferenceError("UNC/network references are not allowed")
    # urllib treats a Windows drive letter as a URI scheme.
    if re.match(r"^[A-Za-z]:[\\/]", value):
        try:
            return Path(value).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ReferenceError(f"source is unavailable: {locator}") from exc
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme.lower() != "file":
        raise ReferenceError("reference mode currently supports local files only")
    if parsed.scheme.lower() == "file":
        if parsed.netloc not in {"", "localhost"}:
            raise ReferenceError("remote file authorities are not allowed")
        raw = unquote(parsed.path)
        if os.name == "nt" and re.match(r"^/[A-Za-z]:/", raw):
            raw = raw[1:]
        value = raw
    try:
        return Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ReferenceError(f"source is unavailable: {locator}") from exc


def infer_artifact_type(path: Path, mime_type: str = "") -> str:
    suffix_type = EXTENSION_TYPES.get(path.suffix.lower())
    if suffix_type:
        return suffix_type
    mime = (mime_type or mimetypes.guess_type(path.name)[0] or "").lower()
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("text/"):
        return "plain_text"
    return "binary"


def fingerprint_file(path: Path, chunk_size: int = 1024 * 1024) -> Dict[str, Any]:
    resolved = Path(path).resolve(strict=True)
    if not resolved.is_file():
        raise ReferenceError(f"source is not a regular file: {resolved}")
    before = resolved.stat()
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    after = resolved.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ReferenceChangedError("source changed while it was being fingerprinted")
    return {
        "canonical_path": str(resolved),
        "content_hash": "sha256:" + digest.hexdigest(),
        "byte_length": after.st_size,
        "source_modified_at": datetime.fromtimestamp(
            after.st_mtime, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z"),
        "source_identity": {
            "device": int(getattr(after, "st_dev", 0)),
            "inode": int(getattr(after, "st_ino", 0)),
            "mtime_ns": int(after.st_mtime_ns),
        },
    }


def verify_reference(path: Path, expected: Dict[str, Any], *, strong: bool = True) -> Dict[str, Any]:
    try:
        resolved = Path(path).resolve(strict=True)
    except (OSError, RuntimeError):
        # A same-directory rename can be identified safely by stable file
        # identity without broad filesystem crawling or implicitly trusting it.
        identity = expected.get("source_identity") or {}
        original = Path(path)
        try:
            for candidate in original.parent.iterdir():
                stat = candidate.stat()
                if candidate.is_file() and (
                    int(getattr(stat, "st_dev", 0)) == int(identity.get("device", -1))
                    and int(getattr(stat, "st_ino", 0)) == int(identity.get("inode", -2))
                ):
                    return {
                        "status": "moved",
                        "reason": "registered file identity exists under a different name",
                        "candidate_path": str(candidate.resolve()),
                    }
        except OSError:
            pass
        return {"status": "unavailable", "reason": "source cannot be resolved"}
    if str(resolved) != str(expected.get("canonical_path") or resolved):
        return {"status": "forbidden", "reason": "canonical path no longer matches registration"}
    try:
        stat = resolved.stat()
    except OSError as exc:
        return {"status": "unavailable", "reason": str(exc)}
    if not resolved.is_file():
        return {"status": "invalid", "reason": "source is not a regular file"}
    identity = expected.get("source_identity") or {}
    quick_changed = (
        int(expected.get("byte_length", stat.st_size)) != stat.st_size
        or int(identity.get("mtime_ns", stat.st_mtime_ns)) != stat.st_mtime_ns
    )
    if quick_changed and not strong:
        return {"status": "changed", "reason": "size or modification time changed"}
    if strong:
        try:
            actual = fingerprint_file(resolved)
        except ReferenceChangedError as exc:
            return {"status": "changed", "reason": str(exc)}
        except (OSError, ReferenceError) as exc:
            return {"status": "unavailable", "reason": str(exc)}
        if actual["content_hash"] != expected.get("content_hash"):
            return {"status": "changed", "reason": "SHA-256 fingerprint changed", "actual": actual}
    return {"status": "available", "reason": "fingerprint verified" if strong else "metadata verified"}


def read_registered_bytes(path: Path, expected: Dict[str, Any], *, start: int = 0, length: Optional[int] = None) -> bytes:
    result = verify_reference(path, expected, strong=True)
    if result["status"] != "available":
        if result["status"] == "changed":
            raise ReferenceChangedError(result["reason"])
        raise ReferenceError(result["reason"])
    if start < 0 or (length is not None and length < 0):
        raise ValueError("byte range must be non-negative")
    with Path(path).open("rb") as handle:
        handle.seek(start)
        return handle.read() if length is None else handle.read(length)


def _segment(locator: Dict[str, Any], text: str, **extra: Any) -> Dict[str, Any]:
    value = {"native_locator": locator, "text": text}
    value.update(extra)
    return value


def _bounded_text(path: Path, locator: Dict[str, Any], max_text: int) -> Dict[str, Any]:
    requested = locator.get("lines") or [1, 500]
    start = max(1, int(requested[0]))
    end = max(start, int(requested[1]))
    selected_lines: List[str] = []
    total_lines = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for total_lines, line in enumerate(handle, 1):
            if start <= total_lines <= end:
                selected_lines.append(line.rstrip("\r\n"))
            if total_lines > end:
                break
    selected = "\n".join(selected_lines)[:max_text]
    return {
        "segments": [_segment({"lines": [start, min(end, total_lines)]}, selected)],
        "metadata": {"lines_scanned": total_lines, "encoding": "utf-8"},
        "parser": {"name": "stdlib-text", "version": "1"},
    }


def _inspect_csv(path: Path, locator: Dict[str, Any], max_text: int) -> Dict[str, Any]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    start, end = locator.get("rows") or [1, 50]
    rows: List[List[str]] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        for number, row in enumerate(reader, 1):
            if number > end:
                break
            if number >= start:
                rows.append(row)
    rendered = "\n".join(delimiter.join(cell for cell in row) for row in rows)[:max_text]
    return {
        "segments": [_segment({"rows": [start, start + max(0, len(rows) - 1)]}, rendered)],
        "metadata": {"delimiter": delimiter, "returned_rows": len(rows)},
        "parser": {"name": "stdlib-csv", "version": "1"},
    }


class _HTMLText(HTMLParser):
    def __init__(self, max_text: int):
        super().__init__(convert_charrefs=True)
        self.max_text = max_text
        self.heading = ""
        self.blocks: List[Tuple[str, str]] = []
        self._tag = ""
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._tag = tag.lower()
        if self._tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        self._tag = ""

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        value = " ".join(data.split())
        if not value:
            return
        if self._tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading = value
        if sum(len(text) for _, text in self.blocks) < self.max_text:
            self.blocks.append((self.heading, value))


def _inspect_html(path: Path, locator: Dict[str, Any], max_text: int) -> Dict[str, Any]:
    parser = _HTMLText(max_text)
    with path.open("rb") as handle:
        parser.feed(handle.read(4 * 1024 * 1024).decode("utf-8", errors="replace"))
    segments = [
        _segment({"dom": f"text()[{index}]", "heading": heading}, text)
        for index, (heading, text) in enumerate(parser.blocks, 1)
    ]
    return {
        "segments": segments,
        "metadata": {"text_blocks": len(segments)},
        "parser": {"name": "stdlib-html", "version": "1"},
    }


def _read_zip_member(archive: zipfile.ZipFile, member: str, limit: int = 64 * 1024 * 1024) -> bytes:
    info = archive.getinfo(member)
    if info.file_size > limit:
        raise ValueError(f"archive member exceeds {limit} bytes: {member}")
    return archive.read(member)


def _inspect_docx(path: Path, locator: Dict[str, Any], max_text: int) -> Dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(_read_zip_member(archive, "word/document.xml"))
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: List[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
        if text:
            paragraphs.append(text)
    start, end = locator.get("paragraphs") or [1, min(100, len(paragraphs))]
    rendered = "\n".join(paragraphs[start - 1:end])[:max_text]
    return {
        "segments": [_segment({"paragraphs": [start, min(end, len(paragraphs))]}, rendered)],
        "metadata": {"paragraphs": len(paragraphs)},
        "parser": {"name": "stdlib-docx", "version": "1"},
    }


def _column_number(reference: str) -> int:
    letters = re.match(r"[A-Za-z]+", reference or "")
    value = 0
    for char in (letters.group(0).upper() if letters else "A"):
        value = value * 26 + ord(char) - 64
    return value


def _range_bounds(value: str) -> Tuple[int, int, int, int]:
    match = re.fullmatch(r"([A-Za-z]+)(\d+)(?::([A-Za-z]+)(\d+))?", value or "A1:Z50")
    if not match:
        raise ValueError("worksheet range must use A1 notation")
    c1, r1 = _column_number(match.group(1)), int(match.group(2))
    c2 = _column_number(match.group(3) or match.group(1))
    r2 = int(match.group(4) or match.group(2))
    return min(c1, c2), min(r1, r2), max(c1, c2), max(r1, r2)


def _inspect_xlsx(path: Path, locator: Dict[str, Any], max_text: int) -> Dict[str, Any]:
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    with zipfile.ZipFile(path) as archive:
        shared: List[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(_read_zip_member(archive, "xl/sharedStrings.xml"))
            for item in shared_root.findall(f"{{{main_ns}}}si"):
                shared.append("".join(node.text or "" for node in item.iter(f"{{{main_ns}}}t")))
        workbook = ET.fromstring(_read_zip_member(archive, "xl/workbook.xml"))
        rels = ET.fromstring(_read_zip_member(archive, "xl/_rels/workbook.xml.rels"))
        targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall(f"{{{package_rel_ns}}}Relationship")
        }
        sheets = []
        for sheet in workbook.findall(f".//{{{main_ns}}}sheet"):
            name = sheet.attrib.get("name", "Sheet")
            relationship = sheet.attrib.get(f"{{{rel_ns}}}id", "")
            target = targets.get(relationship, "")
            if target.startswith("/"):
                target = target.lstrip("/")
            elif not target.startswith("xl/"):
                target = "xl/" + target
            sheets.append((name, target))
        requested_sheet = locator.get("sheet") or (sheets[0][0] if sheets else "")
        target = next((target for name, target in sheets if name == requested_sheet), "")
        if not target:
            raise ValueError(f"worksheet not found: {requested_sheet}")
        sheet_root = ET.fromstring(_read_zip_member(archive, target))
    c1, r1, c2, r2 = _range_bounds(locator.get("range") or "A1:Z50")
    values: List[str] = []
    for cell in sheet_root.findall(f".//{{{main_ns}}}c"):
        reference = cell.attrib.get("r", "A1")
        row_match = re.search(r"\d+", reference)
        row = int(row_match.group(0)) if row_match else 1
        col = _column_number(reference)
        if not (c1 <= col <= c2 and r1 <= row <= r2):
            continue
        value_node = cell.find(f"{{{main_ns}}}v")
        formula_node = cell.find(f"{{{main_ns}}}f")
        value = value_node.text if value_node is not None and value_node.text is not None else ""
        if cell.attrib.get("t") == "s" and value.isdigit() and int(value) < len(shared):
            value = shared[int(value)]
        if formula_node is not None and formula_node.text:
            value = f"={formula_node.text} -> {value}"
        values.append(f"{reference}\t{value}")
    rendered = "\n".join(values)[:max_text]
    return {
        "segments": [_segment({"sheet": requested_sheet, "range": locator.get("range") or "A1:Z50"}, rendered)],
        "metadata": {"sheets": [name for name, _ in sheets], "returned_cells": len(values)},
        "parser": {"name": "stdlib-xlsx", "version": "1"},
    }


def _image_dimensions(path: Path) -> Tuple[Optional[int], Optional[int]]:
    with path.open("rb") as handle:
        header = handle.read(32)
        if header.startswith(b"\x89PNG") and len(header) >= 24:
            return struct.unpack(">II", header[16:24])
        if header[:6] in {b"GIF87a", b"GIF89a"}:
            return struct.unpack("<HH", header[6:10])
        if header.startswith(b"BM") and len(header) >= 26:
            return struct.unpack("<II", header[18:26])
        if header.startswith(b"\xff\xd8"):
            handle.seek(2)
            while True:
                marker = handle.read(1)
                if not marker:
                    break
                if marker != b"\xff":
                    continue
                code = handle.read(1)
                while code == b"\xff":
                    code = handle.read(1)
                if code in {b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"}:
                    length = struct.unpack(">H", handle.read(2))[0]
                    data = handle.read(length - 2)
                    return struct.unpack(">HH", data[1:5])[::-1]
                size = handle.read(2)
                if len(size) != 2:
                    break
                handle.seek(max(0, struct.unpack(">H", size)[0] - 2), 1)
    return None, None


def _inspect_image(path: Path, locator: Dict[str, Any], max_text: int) -> Dict[str, Any]:
    width, height = _image_dimensions(path)
    region = locator.get("region") or [0.0, 0.0, 1.0, 1.0]
    if len(region) != 4 or any(float(value) < 0 or float(value) > 1 for value in region):
        raise ValueError("image region must contain four normalized values from 0 to 1")
    return {
        "segments": [_segment({"region": region}, "", attachment={"kind": "image", "path": str(path)})],
        "metadata": {"width": width, "height": height},
        "parser": {"name": "stdlib-image-metadata", "version": "1"},
    }


def _inspect_pdf(path: Path, locator: Dict[str, Any], max_text: int) -> Dict[str, Any]:
    pages: List[Dict[str, Any]] = []
    parser_name = "pdf-metadata-fallback"
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        requested = locator.get("pages") or [1, min(10, len(reader.pages))]
        for page_number in range(max(1, requested[0]), min(len(reader.pages), requested[1]) + 1):
            text = (reader.pages[page_number - 1].extract_text() or "")[:max_text]
            pages.append(_segment({"page": page_number}, text))
        page_count = len(reader.pages)
        parser_name = "pypdf"
    except (ImportError, OSError, ValueError, KeyError):
        with path.open("rb") as handle:
            sample = handle.read(min(path.stat().st_size, 16 * 1024 * 1024))
        page_count = len(re.findall(rb"/Type\s*/Page\b", sample))
        requested = locator.get("pages") or [1, page_count]
        pages = [_segment({"pages": requested}, "")]
    return {
        "segments": pages,
        "metadata": {"pages": page_count, "text_extraction": parser_name == "pypdf"},
        "parser": {"name": parser_name, "version": "1"},
    }


def inspect_artifact(
    path: Path,
    *,
    artifact_type: str = "",
    native_locator: Optional[Dict[str, Any]] = None,
    max_text: int = 16_000,
) -> Dict[str, Any]:
    """Inspect a registered artifact without persisting or copying source bytes."""
    resolved = Path(path).resolve(strict=True)
    kind = artifact_type or infer_artifact_type(resolved)
    locator = native_locator or {}
    if not 0 <= max_text <= 32_000:
        raise ValueError("max_text must be between 0 and 32,000")
    if kind == "csv":
        details = _inspect_csv(resolved, locator, max_text)
    elif kind == "html":
        details = _inspect_html(resolved, locator, max_text)
    elif kind == "document" and resolved.suffix.lower() == ".docx":
        details = _inspect_docx(resolved, locator, max_text)
    elif kind == "worksheet" and resolved.suffix.lower() == ".xlsx":
        details = _inspect_xlsx(resolved, locator, max_text)
    elif kind in {"image", "screenshot"}:
        details = _inspect_image(resolved, locator, max_text)
    elif kind == "pdf":
        details = _inspect_pdf(resolved, locator, max_text)
    elif kind in {"plain_text", "source_code", "structured_data", "chat", "transcript", "email"}:
        details = _bounded_text(resolved, locator, max_text)
    else:
        details = {
            "segments": [_segment(locator or {"bytes": [0, 0]}, "")],
            "metadata": {"inspection": "metadata-only"},
            "parser": {"name": "binary-metadata", "version": "1"},
        }
    mime_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    return {
        "artifact_type": kind,
        "mime_type": mime_type,
        "source_locator": str(resolved),
        **details,
    }
