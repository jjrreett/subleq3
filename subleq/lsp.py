"""Language Server Protocol support for SUBLEQ assembly."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from .analysis import DocumentAnalysis, Span, Symbol
from .link import INCLUDE_RE

SERVER = LanguageServer(
    "subleq-language-server",
    "0.1.0",
    text_document_sync_kind=types.TextDocumentSyncKind.Incremental,
)


def included_symbols(
    text: str, directory: Path, seen: set[Path]
) -> tuple[dict[str, Symbol], dict[str, Symbol]]:
    """Load editor metadata from recursively included source modules."""
    macros: dict[str, Symbol] = {}
    labels: dict[str, Symbol] = {}
    for line in text.splitlines(keepends=True):
        match = INCLUDE_RE.fullmatch(line)
        if match is None:
            continue

        relative_name = match.group("relative")
        if relative_name is not None:
            path = (directory / relative_name).resolve()
        else:
            resource = resources.files("subleq.stdlib").joinpath(match.group("stdlib"))
            if not resource.is_file():
                continue
            path = Path(str(resource)).resolve()

        if path in seen or not path.is_file():
            continue
        seen.add(path)
        included_text = path.read_text()
        nested_macros, nested_labels = included_symbols(
            included_text, path.parent, seen
        )
        analysis = DocumentAnalysis.parse(
            included_text,
            uri=path.as_uri(),
            external_macros=nested_macros,
            external_global_labels=nested_labels,
        )
        macros.update(analysis.macros)
        labels.update(analysis.global_labels)
    return macros, labels


def document_analysis(ls: LanguageServer, uri: str) -> DocumentAnalysis:
    """Analyze the current in-memory version of a document."""
    document = ls.workspace.get_text_document(uri)
    path = Path(document.path)
    macros, labels = included_symbols(document.source, path.parent, {path.resolve()})
    return DocumentAnalysis.parse(
        document.source,
        uri=uri,
        external_macros=macros,
        external_global_labels=labels,
    )


def utf16_to_index(text: str, character: int) -> int:
    """Convert an LSP UTF-16 character offset to a Python string index."""
    consumed = 0
    for index, value in enumerate(text):
        width = len(value.encode("utf-16-le")) // 2
        if consumed + width > character:
            return index
        consumed += width
    return len(text)


def index_to_utf16(text: str, index: int) -> int:
    """Convert a Python string index to an LSP UTF-16 character offset."""
    return len(text[:index].encode("utf-16-le")) // 2


def lsp_position(
    analysis: DocumentAnalysis, line: int, character: int
) -> types.Position:
    """Convert an internal source position to LSP coordinates."""
    source_line = analysis.lines[line] if 0 <= line < len(analysis.lines) else ""
    return types.Position(line, index_to_utf16(source_line, character))


def lsp_range(analysis: DocumentAnalysis, span: Span) -> types.Range:
    """Convert an internal span to an LSP range."""
    return types.Range(
        lsp_position(analysis, span.line, span.start),
        lsp_position(analysis, span.line, span.end),
    )


def symbol_range(symbol: Symbol) -> types.Range:
    """Convert a definition span using the definition document's source line."""
    return types.Range(
        types.Position(
            symbol.span.line,
            index_to_utf16(symbol.source_line, symbol.span.start),
        ),
        types.Position(
            symbol.span.line,
            index_to_utf16(symbol.source_line, symbol.span.end),
        ),
    )


def python_character(analysis: DocumentAnalysis, position: types.Position) -> int:
    """Convert an incoming LSP position to a Python character offset."""
    if position.line < 0 or position.line >= len(analysis.lines):
        return 0
    return utf16_to_index(analysis.lines[position.line], position.character)


def publish_diagnostics(ls: LanguageServer, uri: str) -> None:
    """Publish fresh diagnostics for an opened or changed document."""
    analysis = document_analysis(ls, uri)
    severity = {
        "error": types.DiagnosticSeverity.Error,
        "warning": types.DiagnosticSeverity.Warning,
    }
    diagnostics = [
        types.Diagnostic(
            range=lsp_range(analysis, diagnostic.span),
            message=diagnostic.message,
            severity=severity[diagnostic.severity],
            source="subleq",
        )
        for diagnostic in analysis.diagnostics
    ]
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
    )


@SERVER.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: types.DidOpenTextDocumentParams) -> None:
    """Analyze a newly opened document."""
    publish_diagnostics(ls, params.text_document.uri)


@SERVER.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams) -> None:
    """Analyze an edited document."""
    publish_diagnostics(ls, params.text_document.uri)


@SERVER.feature(types.TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls: LanguageServer, params: types.DidCloseTextDocumentParams) -> None:
    """Clear diagnostics when an editor closes a document."""
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=params.text_document.uri,
            diagnostics=[],
        )
    )


@SERVER.feature(types.TEXT_DOCUMENT_HOVER)
def hover(ls: LanguageServer, params: types.HoverParams) -> types.Hover | None:
    """Show macro signatures, comments, sizes, and built-in documentation."""
    analysis = document_analysis(ls, params.text_document.uri)
    character = python_character(analysis, params.position)
    result = analysis.hover_at(params.position.line, character)
    if result is None:
        return None
    return types.Hover(
        contents=types.MarkupContent(types.MarkupKind.Markdown, result.markdown),
        range=lsp_range(analysis, result.span),
    )


@SERVER.feature(types.TEXT_DOCUMENT_DEFINITION)
def definition(
    ls: LanguageServer, params: types.DefinitionParams
) -> types.Location | None:
    """Navigate from a macro or label reference to its definition."""
    analysis = document_analysis(ls, params.text_document.uri)
    character = python_character(analysis, params.position)
    symbol = analysis.definition_at(params.position.line, character)
    if symbol is None:
        return None
    return types.Location(
        uri=symbol.uri or params.text_document.uri,
        range=symbol_range(symbol),
    )


@SERVER.feature(
    types.TEXT_DOCUMENT_INLAY_HINT,
    types.InlayHintOptions(resolve_provider=False),
)
def inlay_hints(
    ls: LanguageServer, params: types.InlayHintParams
) -> list[types.InlayHint]:
    """Display native instruction counts after macro invocations."""
    analysis = document_analysis(ls, params.text_document.uri)
    hints = analysis.inlay_hints(params.range.start.line, params.range.end.line)
    return [
        types.InlayHint(
            position=lsp_position(analysis, hint.line, hint.character),
            label=hint.label,
            kind=types.InlayHintKind.Type,
            tooltip=hint.tooltip,
            padding_left=True,
        )
        for hint in hints
    ]


def main() -> None:
    """Run the language server over standard input and output."""
    SERVER.start_io()


if __name__ == "__main__":
    main()
