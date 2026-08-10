# /// script
# dependencies = [
#   "lark",
# ]
# ///


# 	uv run python -m lark.tools.standalone subleq.grammar > subleq.py

import argparse
from collections.abc import Sequence
from pathlib import Path

from lark import Lark
from lark.tools.standalone import gen_standalone


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Add parser-generation arguments to a command parser."""
    parser.add_argument(
        "grammar",
        type=Path,
        nargs="?",
        default=Path("subleq.lark"),
        help="Grammar source (default: subleq.lark)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("subleq/subleq.py"),
        help="Generated parser (default: subleq/subleq.py)",
    )
    parser.set_defaults(command_handler=execute)


def execute(args: argparse.Namespace) -> None:
    """Generate the standalone parser using parsed arguments."""
    grammar = args.grammar.read_text()
    with args.output.open("w") as output:
        lark_inst = Lark(grammar, parser="lalr")
        gen_standalone(lark_inst, out=output)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the standalone parser-generator entry point."""
    parser = argparse.ArgumentParser(description="Generate the SUBLEQ parser")
    configure_parser(parser)
    execute(parser.parse_args(argv))


if __name__ == "__main__":
    main()
