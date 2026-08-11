"""Parse test harnesses embedded in SUBLEQ assembly source."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
NUMBER = r"-?(?:\d+|\$[A-Fa-f0-9]+|%[01]+)"
VALUE = rf"(?:{NUMBER}|{IDENT})"
_TEST_RE = re.compile(
    r'^\s*\.test\s+(?:"(?P<quoted>(?:[^"\\]|\\.)*)"|(?P<bare>'
    + IDENT
    + r"))\s*(?:;.*)?$"
)
_END_RE = re.compile(r"^\s*\.endt\s*(?:;.*)?$")
_SET_RE = re.compile(
    rf"^\s*\.set\s+(?P<label>{IDENT})\s*,\s*(?P<value>{VALUE})\s*(?:;.*)?$"
)
_ASSERT_RE = re.compile(
    rf"^\s*\.assert\s+(?P<label>{IDENT})\s*,\s*(?P<value>{VALUE})\s*(?:;.*)?$"
)
_OUTPUT_RE = re.compile(
    r'^\s*\.assert-output\s+(?P<value>"(?:[^"\\]|\\["\\nrt0])*")\s*(?:;.*)?$'
)


class HarnessSyntaxError(Exception):
    """An embedded source test is malformed."""


@dataclass(frozen=True)
class MemoryExpectation:
    """Expected final value of a global memory cell."""

    label: str
    value: int | str


@dataclass(frozen=True)
class SourceTest:
    """One independently compiled and executed source test."""

    name: str
    body: str
    initial_values: tuple[MemoryExpectation, ...]
    assertions: tuple[MemoryExpectation, ...]
    expected_output: bytes | None
    line: int


@dataclass(frozen=True)
class ParsedHarness:
    """Production source plus all tests removed from it."""

    production_source: str
    tests: tuple[SourceTest, ...]


def parse_number(value: str) -> int:
    """Parse an assembly number and normalize it to one 16-bit word."""
    return int(value.replace("$", "0x").replace("%", "0b"), 0) % (1 << 16)


def parse_value(value: str) -> int | str:
    """Parse a numeric word or retain a global label reference."""
    if re.fullmatch(IDENT, value):
        return value
    return parse_number(value)


def decode_string(value: str) -> str:
    """Decode the assembly string escapes accepted by output assertions."""
    return json.loads(value.replace(r"\0", r"\u0000"))


def parse_test_harness(source: str) -> ParsedHarness:
    """Extract test blocks while preserving production-source line numbers."""
    production: list[str] = []
    tests: list[SourceTest] = []
    names: set[str] = set()
    lines = source.splitlines(keepends=True)
    index = 0

    while index < len(lines):
        line = lines[index]
        start = _TEST_RE.fullmatch(line.rstrip("\r\n"))
        if start is None:
            if _END_RE.fullmatch(line.rstrip("\r\n")):
                raise HarnessSyntaxError(f"line {index + 1}: .endt without .test")
            production.append(line)
            index += 1
            continue

        name = start.group("quoted") or start.group("bare")
        if name in names:
            raise HarnessSyntaxError(f"line {index + 1}: duplicate test name {name!r}")
        names.add(name)
        start_line = index + 1
        production.append("\n" if line.endswith("\n") else "")
        index += 1
        body: list[str] = []
        initial_values: list[MemoryExpectation] = []
        assertions: list[MemoryExpectation] = []
        expected_output: bytes | None = None

        while index < len(lines):
            line = lines[index]
            stripped = line.rstrip("\r\n")
            if _END_RE.fullmatch(stripped):
                production.append("\n" if line.endswith("\n") else "")
                index += 1
                break
            if _TEST_RE.fullmatch(stripped):
                raise HarnessSyntaxError(
                    f"line {index + 1}: test blocks cannot be nested"
                )

            directive = _SET_RE.fullmatch(stripped)
            if directive:
                initial_values.append(
                    MemoryExpectation(
                        directive.group("label"), parse_value(directive.group("value"))
                    )
                )
                body.append("\n" if line.endswith("\n") else "")
            else:
                directive = _ASSERT_RE.fullmatch(stripped)
                if directive:
                    assertions.append(
                        MemoryExpectation(
                            directive.group("label"),
                            parse_value(directive.group("value")),
                        )
                    )
                    body.append("\n" if line.endswith("\n") else "")
                else:
                    output = _OUTPUT_RE.fullmatch(stripped)
                    if output:
                        if expected_output is not None:
                            raise HarnessSyntaxError(
                                f"line {index + 1}: only one .assert-output is allowed per test"
                            )
                        expected_output = decode_string(output.group("value")).encode()
                        body.append("\n" if line.endswith("\n") else "")
                    else:
                        body.append(line)
            production.append("\n" if line.endswith("\n") else "")
            index += 1
        else:
            raise HarnessSyntaxError(
                f"line {start_line}: test {name!r} is missing .endt"
            )

        tests.append(
            SourceTest(
                name=name,
                body="".join(body),
                initial_values=tuple(initial_values),
                assertions=tuple(assertions),
                expected_output=expected_output,
                line=start_line,
            )
        )

    return ParsedHarness("".join(production), tuple(tests))


def strip_test_harness(source: str) -> str:
    """Return source suitable for a normal production compilation."""
    return parse_test_harness(source).production_source
