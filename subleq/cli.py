"""Top-level command-line interface for the SUBLEQ toolchain."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text

from . import __version__
from . import compile as compiler
from . import gen_grammar
from . import gen_syntax
from . import formatter
from . import lsp
from . import run as emulator
from . import testing
from .compile import CompilationError
from .link import LinkError


def _print_compilation_error(error: CompilationError) -> None:
    """Render a compact compiler diagnostic with nearby source context."""
    console = Console(stderr=True)
    location = error.source_name or "<source>"
    if error.line is not None:
        location += f":{error.line}"
        if error.column is not None:
            location += f":{error.column}"
    console.print(Text.assemble(("error", "bold red"), f": {location}: {error}"))

    if error.source is None or error.line is None:
        return
    lines = error.source.splitlines()
    if not 1 <= error.line <= len(lines):
        return
    start = max(1, error.line - 2)
    end = min(len(lines), error.line + 2)
    snippet = "\n".join(lines[start - 1 : end])
    console.print(
        Syntax(
            snippet,
            "asm",
            line_numbers=True,
            start_line=start,
            highlight_lines={error.line},
            word_wrap=False,
        )
    )
    if error.column is not None:
        source_line = lines[error.line - 1]
        prefix = source_line[: max(0, error.column - 1)]
        visual_prefix = prefix.expandtabs(4)
        console.print(" " * (len(str(end)) + 2 + len(visual_prefix)) + "^", style="bold red")


def build_parser() -> argparse.ArgumentParser:
    """Build the complete command-line parser."""
    parser = argparse.ArgumentParser(
        prog="subleq",
        description="SUBLEQ assembler, emulator, parser generator, and language server",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    compile_parser = subcommands.add_parser(
        "compile",
        help="Compile assembly source to a NumPy image",
        description="Compile SUBLEQ assembly source to a NumPy image",
    )
    compiler.configure_parser(compile_parser)

    run_parser = subcommands.add_parser(
        "run",
        help="Compile and run assembly source",
        description="Compile SUBLEQ assembly source and run it immediately",
    )
    emulator.configure_source_parser(run_parser)

    test_parser = subcommands.add_parser(
        "test",
        help="Run test harnesses embedded in assembly source",
        description="Compile and run test harnesses embedded in SUBLEQ source",
    )
    testing.configure_parser(test_parser)

    format_parser = subcommands.add_parser(
        "fmt",
        help="Format assembly source in place",
        description="Format SUBLEQ assembly source in place",
    )
    formatter.configure_parser(format_parser)

    emulate_parser = subcommands.add_parser(
        "emulate",
        help="Run a compiled NumPy image",
        description="Run a compiled SUBLEQ NumPy image",
    )
    emulator.configure_image_parser(emulate_parser)

    grammar_parser = subcommands.add_parser(
        "gen-grammar",
        help="Regenerate the standalone parser",
        description="Generate a standalone Python parser from the Lark grammar",
    )
    gen_grammar.configure_parser(grammar_parser)

    syntax_parser = subcommands.add_parser(
        "gen-syntax",
        help="Regenerate the VS Code syntax grammar",
        description="Generate TextMate highlighting from the Lark grammar",
    )
    gen_syntax.configure_parser(syntax_parser)

    lsp_parser = subcommands.add_parser(
        "lsp",
        help="Run the language server over stdio",
        description="Run the SUBLEQ language server over standard input and output",
    )
    lsp_parser.add_argument(
        "--stdio",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    lsp_parser.set_defaults(command_handler=lambda _args: lsp.main())
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Parse arguments and dispatch one SUBLEQ subcommand."""
    args = build_parser().parse_args(argv)
    try:
        args.command_handler(args)
    except CompilationError as error:
        _print_compilation_error(error)
        raise SystemExit(1) from None
    except LinkError as error:
        Console(stderr=True).print(f"[bold red]error[/bold red]: {error}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
