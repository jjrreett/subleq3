"""Deterministic formatting for SUBLEQ assembly source."""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from pathlib import Path

from rich import print

from .analysis import IDENT, split_comment

INDENT = 4
INLINE_COMMENT_COLUMN = 55
_LABEL_RE = re.compile(rf"(?P<label>@?{IDENT})\s*:")


def _render(code: str, comment: str | None, indent: int) -> str:
    code = code.strip()
    if not code and comment is not None:
        return ";" + comment.rstrip()
    formatted = " " * indent + code
    if comment is None:
        return formatted.rstrip()
    comment = comment.strip()
    separator = max(1, INLINE_COMMENT_COLUMN - len(formatted) - 1)
    return formatted + " " * separator + ";" + (f" {comment}" if comment else "")


def format_source(source: str) -> str:
    """Format one assembly document without changing its tokens."""
    output: list[str] = []
    in_macro = False
    current_global = False
    current_local = False
    data_indent: int | None = None

    for source_line in source.splitlines():
        code, comment = split_comment(source_line)
        stripped = code.strip()
        if not stripped and comment is None:
            output.append("")
            continue

        if data_indent is not None:
            if stripped.startswith(".endd"):
                output.append(_render(stripped, comment, data_indent))
                data_indent = None
            else:
                output.append(_render(stripped, comment, data_indent + INDENT))
            continue

        if stripped.startswith(".macro"):
            output.append(_render(stripped, comment, 0))
            in_macro = True
            current_global = False
            current_local = False
            continue
        if stripped.startswith(".endm"):
            output.append(_render(stripped, comment, 0))
            in_macro = False
            current_global = False
            current_local = False
            continue
        if stripped.startswith((".test", ".endt")):
            output.append(_render(stripped, comment, 0))
            current_global = False
            current_local = False
            continue

        label = _LABEL_RE.match(stripped)
        if label:
            name = label.group("label")
            if name.startswith("@") or in_macro:
                indent = INDENT
                current_local = True
            else:
                indent = 0
                current_global = True
                current_local = False
            output.append(_render(stripped, comment, indent))
            remainder = stripped[label.end() :].strip()
            if remainder.startswith(".data") and ".endd" not in remainder:
                data_indent = indent
            elif remainder.startswith("."):
                current_global = False
                current_local = False
            continue

        if current_local:
            indent = INDENT * 2
        elif current_global or in_macro:
            indent = INDENT
        else:
            indent = 0

        output.append(_render(stripped, comment, indent))
        if stripped.startswith(".data") and ".endd" not in stripped:
            data_indent = indent

    formatted = "\n".join(output)
    if source.endswith(("\n", "\r")):
        formatted += "\n"
    return formatted


def source_paths(inputs: Sequence[Path]) -> list[Path]:
    """Expand explicit source files and directories in stable order."""
    paths: list[Path] = []
    for item in inputs:
        if item.is_dir():
            paths.extend(sorted(item.rglob("*.s")))
        else:
            paths.append(item)
    return list(dict.fromkeys(paths))


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Add formatter arguments to the unified CLI parser."""
    parser.add_argument(
        "input",
        type=Path,
        nargs="+",
        help="Assembly files or directories to format",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report files needing formatting without changing them",
    )
    parser.set_defaults(command_handler=execute)


def execute(args: argparse.Namespace) -> None:
    """Format files in place or check that they are already formatted."""
    changed: list[Path] = []
    for path in source_paths(args.input):
        original = path.read_text()
        formatted = format_source(original)
        if formatted == original:
            continue
        changed.append(path)
        if not args.check:
            path.write_text(formatted)

    if args.check and changed:
        for path in changed:
            print(f"[red]needs formatting:[/red] {path}")
        raise SystemExit(1)
    if not args.check:
        noun = "file" if len(changed) == 1 else "files"
        print(f"Formatted {len(changed)} {noun}")
