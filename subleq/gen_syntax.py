"""Generate editor syntax highlighting from the executable Lark grammar."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path

from lark import Lark

from .analysis import DIRECTIVE_DOCS


def _terminal_patterns(grammar: str) -> dict[str, str]:
    parser = Lark(grammar, parser="lalr")
    return {terminal.name: terminal.pattern.to_regexp() for terminal in parser.terminals}


def _core_directives(grammar: str) -> list[str]:
    """Return dot-prefixed literal tokens in their grammar-source order."""
    return list(dict.fromkeys(re.findall(r'"(\.[A-Za-z][A-Za-z0-9-]*)"', grammar)))


def generate_textmate_grammar(grammar: str) -> dict:
    """Build a TextMate grammar, deriving lexical syntax from Lark."""
    terminals = _terminal_patterns(grammar)
    ident = terminals["IDENT"]
    directives = _core_directives(grammar)
    directives.extend(name for name in DIRECTIVE_DOCS if name not in directives)
    directive_pattern = r"(?:" + "|".join(
        re.escape(name[1:]) for name in directives
    ) + r")"
    identifier = rf"(?:{ident})"

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "SUBLEQ",
        "scopeName": "source.subleq",
        "patterns": [
            {"include": f"#{name}"}
            for name in (
                "comments", "strings", "characters", "macroDefinitions", "labels", "directives",
                "instructions", "numbers", "specialValues", "labelReferences",
            )
        ],
        "repository": {
            "comments": {"patterns": [{
                "name": "comment.line.semicolon.subleq", "match": ";.*$",
            }]},
            "strings": {"patterns": [{
                "name": "string.quoted.double.subleq",
                "begin": '"', "end": '"',
                "patterns": [{
                    "name": "constant.character.escape.subleq",
                    "match": r'\\["\\nrt0]',
                }],
            }]},
            "characters": {"patterns": [{
                "name": "constant.character.subleq",
                "match": r"'(?:[^'\\\n\r]|\\['\\nrt0])'?",
            }]},
            "macroDefinitions": {"patterns": [{
                "begin": rf"^(\s*)(\.macro)(\s+)({identifier})(?=\s|,|$)",
                "beginCaptures": {
                    "2": {"name": "keyword.control.directive.macro.subleq"},
                    "4": {"name": "entity.name.function.macro.subleq"},
                },
                "end": r"^(\s*)(\.endm)\b",
                "endCaptures": {
                    "2": {"name": "keyword.control.directive.macro.subleq"},
                },
                "patterns": [
                    {"include": f"#{name}"}
                    for name in (
                        "comments", "strings", "macroLabels", "directives",
                        "instructions", "numbers", "specialValues",
                    )
                ],
            }]},
            "macroLabels": {"patterns": [
                {
                    "name": "variable.other.label.subleq",
                    "match": rf"@?{identifier}(?=\s*:)",
                },
                {
                    "name": "variable.other.label.subleq",
                    "match": rf"@{identifier}",
                },
                {
                    "name": "variable.other.label.subleq",
                    "match": rf"(?<![A-Za-z0-9_]){identifier}(?![A-Za-z0-9_])",
                },
            ]},
            "labels": {"patterns": [
                {
                    "name": "variable.other.label.subleq",
                    "match": rf"@{identifier}(?=\s*:)",
                },
                {
                    "name": "variable.other.label.subleq",
                    "match": rf"(?<![A-Za-z0-9_]){identifier}(?=\s*:)",
                },
            ]},
            "directives": {"patterns": [{
                "name": "keyword.control.directive.subleq",
                "match": rf"\.{directive_pattern}\b",
            }]},
            "instructions": {"patterns": [
                {
                    "name": "keyword.control.instruction.subleq",
                    "match": r"\bsubleq\b",
                },
                {
                    "name": "support.function.macro.subleq",
                    "match": rf"^(?:\s*)({identifier})(?=\s|$)",
                    "captures": {"1": {"name": "support.function.macro.subleq"}},
                },
            ]},
            "numbers": {"patterns": [
                {"name": "constant.numeric.immediate.subleq", "match": r"#-?(?:\$[A-Fa-f0-9]+|%[01]+|\d+)(?![A-Za-z0-9_])"},
                {"name": "constant.numeric.hex.subleq", "match": r"-?\$[A-Fa-f0-9]+(?![A-Za-z0-9_])"},
                {"name": "constant.numeric.binary.subleq", "match": r"-?%[01]+(?![A-Za-z0-9_])"},
                {"name": "constant.numeric.decimal.subleq", "match": r"(?<![A-Za-z0-9_])-?\d+(?![A-Za-z0-9_])"},
            ]},
            "specialValues": {"patterns": [{
                "name": "constant.language.next-address.subleq",
                "match": terminals["QMARK"],
            }]},
            "labelReferences": {"patterns": [
                {
                    "name": "variable.other.label.subleq",
                    "match": rf"@{identifier}",
                },
                {
                    "name": "variable.other.label.subleq",
                    "match": rf"(?<![A-Za-z0-9_]){identifier}(?![A-Za-z0-9_])",
                },
            ]},
        },
    }


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("grammar", type=Path, nargs="?", default=Path("subleq.lark"))
    parser.add_argument(
        "-o", "--output", type=Path,
        default=Path("editors/vscode/syntaxes/subleq.tmLanguage.json"),
    )
    parser.set_defaults(command_handler=execute)


def execute(args: argparse.Namespace) -> None:
    generated = generate_textmate_grammar(args.grammar.read_text())
    args.output.write_text(json.dumps(generated, indent=2) + "\n")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate the TextMate grammar")
    configure_parser(parser)
    execute(parser.parse_args(argv))


if __name__ == "__main__":
    main()
