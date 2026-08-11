"""Editor-oriented source analysis for the SUBLEQ assembly language."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .harness import HarnessSyntaxError, parse_test_harness

IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
TOKEN_RE = re.compile(rf"@?{IDENT}|\.[A-Za-z_][A-Za-z0-9_]*")
LABEL_RE = re.compile(rf"\s*(?P<name>@?{IDENT})\s*:")
MACRO_RE = re.compile(r"\s*\.macro\s+(?P<signature>[^;]+?)\s*$")
END_MACRO_RE = re.compile(r"\s*\.endm\s*$")
INSTRUCTION_RE = re.compile(rf"\s*(?P<name>{IDENT})(?P<arguments>.*)$")
TEST_RE = re.compile(r'\s*\.test\s+(?:"[^"]*"|' + IDENT + r")\s*$")
END_TEST_RE = re.compile(r"\s*\.endt\s*$")


DIRECTIVE_DOCS = {
    ".include": (
        'Link a project module with `.include "path.s"` or a packaged '
        "standard-library module with `.include <core.s>`."
    ),
    ".data": "Begin a general data block. End it with `.endd`.",
    ".endd": "End a `.data` block.",
    ".macro": (
        "Define a macro with `.macro name parameter, ...`. The name is "
        "separated from its parameters by whitespace."
    ),
    ".endm": "End a macro definition.",
    ".byte": "Emit one word for each numeric byte value.",
    ".word": "Emit one 16-bit word for each numeric value.",
    ".dword": "Emit each 32-bit value as a high word followed by a low word.",
    ".ascii": "Emit one word per character.",
    ".asciiz": "Emit one word per character followed by a zero word.",
    ".fill": "Emit `count` copies of a numeric value.",
    ".res": "Reserve a number of zero-filled words.",
    ".literals": (
        "Emit one word for every unique `#number` immediate used by the program. "
        "Immediate operands are rewritten to the corresponding word addresses."
    ),
    ".test": "Begin an embedded source test. End it with `.endt`.",
    ".endt": "End an embedded source test.",
    ".set": "Set a global memory cell before an embedded test runs.",
    ".assert": "Assert a global memory cell's value after the program halts.",
    ".assert-output": "Assert the exact bytes written to the I/O cell.",
}

SUBLEQ_DOC = "Subtract `memory[a]` from `memory[b]`, then branch to `target` when the signed result is less than or equal to zero."


@dataclass(frozen=True)
class Span:
    """A single-line, zero-based source span using Python character offsets."""

    line: int
    start: int
    end: int

    def contains(self, line: int, character: int) -> bool:
        return self.line == line and self.start <= character <= self.end


@dataclass
class Symbol:
    """A macro or label definition."""

    name: str
    kind: str
    span: Span
    scope: str
    documentation: str = ""
    parameters: tuple[str, ...] = ()
    instruction_count: int | None = None
    uri: str | None = None
    source_line: str = ""


@dataclass
class Invocation:
    """An instruction or macro invocation."""

    name: str
    span: Span
    end_character: int
    arguments: tuple[str, ...]
    scope: str
    macro_owner: str | None


@dataclass(frozen=True)
class AnalysisDiagnostic:
    """A diagnostic independent of any editor protocol implementation."""

    span: Span
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class HoverResult:
    """Markdown hover content and the token it applies to."""

    span: Span
    markdown: str


@dataclass(frozen=True)
class InlayResult:
    """An editor-neutral inlay hint."""

    line: int
    character: int
    label: str
    tooltip: str


@dataclass
class DocumentAnalysis:
    """Symbols, references, diagnostics, and editor queries for one document."""

    text: str
    lines: list[str]
    macros: dict[str, Symbol] = field(default_factory=dict)
    global_labels: dict[str, Symbol] = field(default_factory=dict)
    scoped_labels: dict[tuple[str, str], Symbol] = field(default_factory=dict)
    invocations: list[Invocation] = field(default_factory=list)
    diagnostics: list[AnalysisDiagnostic] = field(default_factory=list)
    scope_by_line: list[str] = field(default_factory=list)
    macro_by_line: list[str | None] = field(default_factory=list)
    uri: str | None = None
    external_macro_names: set[str] = field(default_factory=set)
    test_analysis_by_line: dict[int, DocumentAnalysis] = field(default_factory=dict)

    @classmethod
    def parse(
        cls,
        text: str,
        *,
        uri: str | None = None,
        external_macros: dict[str, Symbol] | None = None,
        external_global_labels: dict[str, Symbol] | None = None,
    ) -> DocumentAnalysis:
        """Analyze source without requiring it to be complete or compilable."""
        try:
            harness = parse_test_harness(text)
        except HarnessSyntaxError:
            return cls._parse_plain(
                text,
                uri=uri,
                external_macros=external_macros,
                external_global_labels=external_global_labels,
            )

        analysis = cls._parse_plain(
            harness.production_source,
            uri=uri,
            external_macros=external_macros,
            external_global_labels=external_global_labels,
        )
        analysis.text = text
        analysis.lines = text.splitlines()
        for test in harness.tests:
            test_source = "\n" * test.line + test.body
            test_analysis = cls._parse_plain(
                test_source,
                uri=uri,
                external_macros=analysis.macros,
                external_global_labels=analysis.global_labels,
            )
            first_body_line = test.line
            last_body_line = test.line + len(test.body.splitlines())
            for line in range(first_body_line, last_body_line):
                analysis.test_analysis_by_line[line] = test_analysis
            analysis.diagnostics.extend(test_analysis.diagnostics)
        return analysis

    @classmethod
    def _parse_plain(
        cls,
        text: str,
        *,
        uri: str | None = None,
        external_macros: dict[str, Symbol] | None = None,
        external_global_labels: dict[str, Symbol] | None = None,
    ) -> DocumentAnalysis:
        """Analyze one program without interpreting embedded test blocks."""
        macros = dict(external_macros or {})
        analysis = cls(
            text=text,
            lines=text.splitlines(),
            macros=macros,
            global_labels=dict(external_global_labels or {}),
            uri=uri,
            external_macro_names=set(macros),
        )
        analysis._scan()
        analysis._finish()
        return analysis

    def _scan(self) -> None:
        current_global = "<start of file>"
        current_macro: str | None = None
        in_data = False
        in_test = False
        pending_comments: list[str] = []

        for line_number, source_line in enumerate(self.lines):
            code, comment = split_comment(source_line)
            stripped = code.strip()

            if current_macro is None and TEST_RE.fullmatch(code):
                in_test = True
                self.scope_by_line.append(current_global)
                self.macro_by_line.append(None)
                pending_comments.clear()
                continue
            if in_test:
                self.scope_by_line.append(current_global)
                self.macro_by_line.append(None)
                if END_TEST_RE.fullmatch(code):
                    in_test = False
                pending_comments.clear()
                continue

            if not stripped:
                self.scope_by_line.append(
                    macro_scope(current_macro) if current_macro else current_global
                )
                self.macro_by_line.append(current_macro)
                if comment is None:
                    pending_comments.clear()
                else:
                    pending_comments.append(clean_comment(comment))
                continue

            macro_match = MACRO_RE.fullmatch(code)
            if current_macro is None and macro_match:
                signature = parse_macro_signature(macro_match.group("signature"))
                name = signature[0] if signature else ""
                name_start = source_line.find(name)
                span = Span(line_number, name_start, name_start + len(name))
                if not re.fullmatch(IDENT, name):
                    self.diagnostics.append(
                        AnalysisDiagnostic(
                            span, "A macro definition requires a valid name"
                        )
                    )
                elif name in self.macros:
                    self.diagnostics.append(
                        AnalysisDiagnostic(span, f"Macro {name!r} is defined twice")
                    )
                else:
                    self.macros[name] = Symbol(
                        name=name,
                        kind="macro",
                        span=span,
                        scope=macro_scope(name),
                        documentation=join_comments(pending_comments),
                        parameters=signature[1:],
                        uri=self.uri,
                        source_line=source_line,
                    )
                current_macro = name
                self.scope_by_line.append(macro_scope(name))
                self.macro_by_line.append(name)
                pending_comments.clear()
                continue

            if current_macro is not None and END_MACRO_RE.fullmatch(code):
                self.scope_by_line.append(macro_scope(current_macro))
                self.macro_by_line.append(current_macro)
                current_macro = None
                pending_comments.clear()
                continue

            scope = macro_scope(current_macro) if current_macro else current_global
            remainder_start = 0
            first_label = True
            while label_match := LABEL_RE.match(code, remainder_start):
                name = label_match.group("name")
                name_start = label_match.start("name")
                span = Span(line_number, name_start, name_start + len(name))

                if current_macro is not None:
                    key = (scope, name)
                    self._add_scoped_label(
                        key,
                        Symbol(
                            name,
                            "macro label",
                            span,
                            scope,
                            join_comments(pending_comments) if first_label else "",
                            uri=self.uri,
                            source_line=source_line,
                        ),
                    )
                elif name.startswith("@"):
                    key = (current_global, name)
                    self._add_scoped_label(
                        key,
                        Symbol(
                            name,
                            "local label",
                            span,
                            current_global,
                            join_comments(pending_comments) if first_label else "",
                            uri=self.uri,
                            source_line=source_line,
                        ),
                    )
                else:
                    current_global = name
                    scope = current_global
                    symbol = Symbol(
                        name,
                        "global label",
                        span,
                        current_global,
                        join_comments(pending_comments) if first_label else "",
                        uri=self.uri,
                        source_line=source_line,
                    )
                    if name in self.global_labels:
                        self.diagnostics.append(
                            AnalysisDiagnostic(
                                span, f"Global label {name!r} is defined twice"
                            )
                        )
                    else:
                        self.global_labels[name] = symbol

                remainder_start = label_match.end()
                first_label = False

            scope = macro_scope(current_macro) if current_macro else current_global
            self.scope_by_line.append(scope)
            self.macro_by_line.append(current_macro)

            remainder = code[remainder_start:]
            remainder_text = remainder.strip()
            if remainder_text.startswith(".data"):
                in_data = ".endd" not in remainder_text
                pending_comments.clear()
                continue
            if in_data:
                if remainder_text.startswith(".endd"):
                    in_data = False
                pending_comments.clear()
                continue

            instruction_match = INSTRUCTION_RE.fullmatch(remainder)
            if instruction_match:
                name = instruction_match.group("name")
                relative_start = instruction_match.start("name")
                name_start = remainder_start + relative_start
                arguments = parse_arguments(instruction_match.group("arguments"))
                self.invocations.append(
                    Invocation(
                        name=name,
                        span=Span(line_number, name_start, name_start + len(name)),
                        end_character=len(code.rstrip()),
                        arguments=arguments,
                        scope=scope,
                        macro_owner=current_macro,
                    )
                )

            pending_comments.clear()

        if current_macro is not None:
            symbol = self.macros.get(current_macro)
            span = symbol.span if symbol else Span(max(len(self.lines) - 1, 0), 0, 1)
            self.diagnostics.append(
                AnalysisDiagnostic(span, f"Macro {current_macro!r} is missing .endm")
            )

    def _add_scoped_label(self, key: tuple[str, str], symbol: Symbol) -> None:
        if key in self.scoped_labels:
            self.diagnostics.append(
                AnalysisDiagnostic(
                    symbol.span,
                    f"Label {symbol.name!r} is defined twice in scope {symbol.scope!r}",
                )
            )
        else:
            self.scoped_labels[key] = symbol

    def _finish(self) -> None:
        """Validate invocations and calculate recursive macro sizes."""
        for invocation in self.invocations:
            if invocation.name == "subleq":
                if len(invocation.arguments) != 3:
                    self.diagnostics.append(
                        AnalysisDiagnostic(
                            invocation.span,
                            f"subleq expects 3 arguments, got {len(invocation.arguments)}",
                        )
                    )
                continue

            macro = self.macros.get(invocation.name)
            if macro is None:
                self.diagnostics.append(
                    AnalysisDiagnostic(
                        invocation.span, f"Unknown opcode or macro {invocation.name!r}"
                    )
                )
                continue
            if len(invocation.arguments) != len(macro.parameters):
                self.diagnostics.append(
                    AnalysisDiagnostic(
                        invocation.span,
                        f"Macro {invocation.name!r} expects {len(macro.parameters)} arguments, got {len(invocation.arguments)}",
                    )
                )

        cache: dict[str, int | None] = {
            name: self.macros[name].instruction_count
            for name in self.external_macro_names
        }
        for name, macro in self.macros.items():
            if name in self.external_macro_names:
                continue
            macro.instruction_count = self._macro_instruction_count(
                macro.name, cache, ()
            )

        for name, macro in self.macros.items():
            if name in self.external_macro_names:
                continue
            if macro.instruction_count is None:
                self.diagnostics.append(
                    AnalysisDiagnostic(
                        macro.span,
                        f"Cannot calculate instruction count for macro {macro.name!r}",
                        severity="warning",
                    )
                )

    def _macro_instruction_count(
        self,
        name: str,
        cache: dict[str, int | None],
        stack: tuple[str, ...],
    ) -> int | None:
        if name in cache:
            return cache[name]
        if name in stack:
            cache[name] = None
            return None

        total = 0
        for invocation in self.invocations:
            if invocation.macro_owner != name:
                continue
            if invocation.name == "subleq":
                total += 1
                continue
            if invocation.name not in self.macros:
                cache[name] = None
                return None
            count = self._macro_instruction_count(
                invocation.name, cache, (*stack, name)
            )
            if count is None:
                cache[name] = None
                return None
            total += count

        cache[name] = total
        return total

    def token_at(self, line: int, character: int) -> tuple[str, Span] | None:
        """Return the language token under an editor position."""
        if line < 0 or line >= len(self.lines):
            return None
        code, _ = split_comment(self.lines[line])
        for match in TOKEN_RE.finditer(code):
            if match.start() <= character <= match.end():
                return match.group(), Span(line, match.start(), match.end())
        return None

    def definition_at(self, line: int, character: int) -> Symbol | None:
        """Resolve the macro or label under a position."""
        token_result = self.token_at(line, character)
        if token_result is None:
            return None
        token, _ = token_result
        if token.startswith(".") or token == "subleq":
            return None

        test_analysis = self.test_analysis_by_line.get(line)
        if test_analysis is not None:
            return test_analysis.definition_at(line, character)

        invocation = self._invocation_at(line, character)
        if invocation and invocation.name in self.macros:
            return self.macros[invocation.name]

        for symbol in self._all_symbols():
            if symbol.span.contains(line, character):
                return symbol

        macro_name = (
            self.macro_by_line[line] if line < len(self.macro_by_line) else None
        )
        if macro_name:
            macro = self.macros.get(macro_name)
            if macro and token in macro.parameters:
                return None
            return self.scoped_labels.get((macro_scope(macro_name), token))

        scope = self.scope_by_line[line] if line < len(self.scope_by_line) else ""
        if token.startswith("@"):
            return self.scoped_labels.get((scope, token))
        return self.global_labels.get(token) or self.macros.get(token)

    def hover_at(self, line: int, character: int) -> HoverResult | None:
        """Build Markdown documentation for the token under a position."""
        token_result = self.token_at(line, character)
        if token_result is None:
            return None
        token, token_span = token_result

        if token == "subleq":
            markdown = f"```subleq\nsubleq a, b, target\n```\n\n{SUBLEQ_DOC}"
            return HoverResult(token_span, markdown)
        if token in DIRECTIVE_DOCS:
            return HoverResult(token_span, f"**`{token}`**\n\n{DIRECTIVE_DOCS[token]}")

        test_analysis = self.test_analysis_by_line.get(line)
        if test_analysis is not None:
            return test_analysis.hover_at(line, character)

        symbol = self.definition_at(line, character)
        if symbol is None:
            return None
        if symbol.kind == "macro":
            arguments = ", ".join(symbol.parameters)
            signature = f"{symbol.name}{' ' if arguments else ''}{arguments}"
            sections = [f"```subleq\n{signature}\n```"]
            if symbol.documentation:
                sections.append(
                    without_repeated_macro_signature(
                        symbol.documentation,
                        symbol.name,
                    )
                )
            if symbol.instruction_count is not None:
                noun = (
                    "instruction" if symbol.instruction_count == 1 else "instructions"
                )
                sections.append(
                    f"Expands to **{symbol.instruction_count} SUBLEQ {noun}**."
                )
            return HoverResult(token_span, "\n\n".join(sections))

        sections = [f"**{symbol.kind}** `{symbol.name}`"]
        if symbol.kind != "global label":
            sections.append(f"Scope: `{symbol.scope}`")
        if symbol.documentation:
            sections.append(symbol.documentation)
        return HoverResult(token_span, "\n\n".join(sections))

    def inlay_hints(
        self, start_line: int = 0, end_line: int | None = None
    ) -> list[InlayResult]:
        """Return instruction-count hints for macro invocations in a line range."""
        if end_line is None:
            end_line = len(self.lines) - 1
        hints = []
        for invocation in self.invocations:
            if not start_line <= invocation.span.line <= end_line:
                continue
            macro = self.macros.get(invocation.name)
            if macro is None or macro.instruction_count is None:
                continue
            noun = "instruction" if macro.instruction_count == 1 else "instructions"
            hints.append(
                InlayResult(
                    invocation.span.line,
                    invocation.end_character,
                    f": {macro.instruction_count} {noun}",
                    f"Expands to {macro.instruction_count} native SUBLEQ {noun}.",
                )
            )
        child_analyses = {
            id(analysis): analysis
            for line, analysis in self.test_analysis_by_line.items()
            if start_line <= line <= end_line
        }
        for analysis in child_analyses.values():
            hints.extend(analysis.inlay_hints(start_line, end_line))
        return hints

    def _invocation_at(self, line: int, character: int) -> Invocation | None:
        return next(
            (
                invocation
                for invocation in self.invocations
                if invocation.span.contains(line, character)
            ),
            None,
        )

    def _all_symbols(self) -> tuple[Symbol, ...]:
        return (
            *self.macros.values(),
            *self.global_labels.values(),
            *self.scoped_labels.values(),
        )


def split_comment(line: str) -> tuple[str, str | None]:
    """Split a semicolon comment while respecting quoted strings."""
    quoted = False
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
        elif character == "\\" and quoted:
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif character == ";" and not quoted:
            return line[:index], line[index + 1 :]
    return line, None


def clean_comment(comment: str) -> str:
    """Remove comment syntax while preserving intentional indentation."""
    comment = comment.rstrip()
    if comment.startswith(" "):
        comment = comment[1:]
    if comment and not comment.strip(";=- "):
        return ""
    return comment


def join_comments(comments: list[str]) -> str:
    """Render comment lines as Markdown without collapsing source spacing."""
    start = 0
    end = len(comments)
    while start < end and not comments[start]:
        start += 1
    while end > start and not comments[end - 1]:
        end -= 1

    paragraphs: list[str] = []
    current: list[str] = []
    for line in comments[start:end]:
        if not line:
            if current:
                paragraphs.append("  \n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append("  \n".join(current))
    return "\n\n".join(paragraphs)


def parse_macro_signature(signature: str) -> tuple[str, ...]:
    """Parse canonical or legacy macro declaration syntax."""
    match = re.fullmatch(
        rf"(?P<name>{IDENT})(?:(?:\s*,\s*|\s+)(?P<parameters>"
        rf"{IDENT}(?:\s*,\s*{IDENT})*))?",
        signature.strip(),
    )
    if match is None:
        return ()
    parameters = match.group("parameters")
    if parameters is None:
        return (match.group("name"),)
    return (
        match.group("name"),
        *(parameter.strip() for parameter in parameters.split(",")),
    )


def without_repeated_macro_signature(documentation: str, name: str) -> str:
    """Drop a leading signature comment already rendered by macro hover."""
    first_paragraph, separator, remainder = documentation.partition("\n\n")
    if (
        separator
        and first_paragraph.startswith(f"`{name}")
        and first_paragraph.endswith("`")
    ):
        return remainder
    return documentation


def parse_arguments(arguments: str) -> tuple[str, ...]:
    """Parse the language's simple comma-separated argument list."""
    arguments = arguments.strip()
    if not arguments:
        return ()
    return tuple(argument.strip() for argument in arguments.split(","))


def macro_scope(name: str | None) -> str:
    """Return the private source-analysis scope for a macro body."""
    return f"<macro {name}>"
