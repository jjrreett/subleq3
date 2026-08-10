"""Language Server Protocol support for SUBLEQ assembly."""

from __future__ import annotations

from functools import lru_cache

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from .analysis import DocumentAnalysis, Span


SERVER = LanguageServer(
    "subleq-language-server",
    "0.1.0",
    text_document_sync_kind=types.TextDocumentSyncKind.Incremental,
)


@lru_cache(maxsize=32)
def analyze(text: str) -> DocumentAnalysis:
    """Reuse an analysis while a document's text is unchanged."""
    return DocumentAnalysis.parse(text)


def document_analysis(ls: LanguageServer, uri: str) -> DocumentAnalysis:
    """Analyze the current in-memory version of a document."""
    document = ls.workspace.get_text_document(uri)
    return analyze(document.source)


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
        uri=params.text_document.uri,
        range=lsp_range(analysis, symbol.span),
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
