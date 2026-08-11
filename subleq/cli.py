"""Top-level command-line interface for the SUBLEQ toolchain."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__
from . import compile as compiler
from . import gen_grammar
from . import lsp
from . import run as emulator
from . import testing


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
    args.command_handler(args)


if __name__ == "__main__":
    main()
