# /// script
# dependencies = [
#   "lark",
# ]
# ///


# 	uv run python -m lark.tools.standalone subleq.grammar > subleq.py

from lark.tools.standalone import gen_standalone
from lark import Lark
from pathlib import Path


def main():
    grammar = Path("subleq.lark").read_text()
    out = Path("subleq/subleq.py")
    with out.open("w") as f:
        lark_inst = Lark(grammar, parser="lalr")
        gen_standalone(lark_inst, out=f)


if __name__ == "__main__":
    main()
