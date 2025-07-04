from dataclasses import dataclass
from collections.abc import Iterable
import numpy as np

from rich import print
from functools import wraps
from .subleq import Lark_StandAlone, Transformer

import argparse
from pathlib import Path

DEBUG = True


@wraps(print)
def debug(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


IO_ADDR = 0x03
HALT_ADDR = 0x00


@dataclass
class Label:
    name: str


@dataclass
class Next: ...


@dataclass
class Macro:
    ident: str
    args: list[str]
    instructions: list[str | Next]

    def expand(self, actual_args):
        if len(actual_args) != len(self.args):
            raise ValueError(
                f"Macro '{self.ident}' expects {len(self.args)} arguments, got {len(actual_args)}"
            )

        arg_map = dict(zip(self.args, actual_args))
        expanded = []

        for instr in self.instructions:
            if isinstance(instr, str):
                # Replace argument name with its actual value
                expanded.append(arg_map.get(instr, instr))
            elif isinstance(instr, Next):
                expanded.append(Next())
            else:
                raise TypeError(f"Unsupported instruction token: {instr}")
        return expanded


class SubleqTransformer(Transformer):
    def __init__(self):
        self.labels = set()
        self.macros = {}

    def start(self, items):
        instructions = []
        for item in items:
            if isinstance(item, str) or not isinstance(item, Iterable):
                instructions.append(item)
                continue
            instructions.extend(item)
        return instructions

    def instructions(self, items):
        instructions = []
        for item in items:
            if isinstance(item, str) or not isinstance(item, Iterable):
                instructions.append(item)
                continue
            instructions.extend(item)
        return instructions

    def macro_args(self, items):
        return items

    def macro_block(self, items):
        ident, macro_args, *instructions = items
        m = Macro(ident, macro_args, self.instructions(instructions))
        self.macros[ident] = m
        return []

    def macro_call(self, items):
        ident, args = items
        return self.macros[ident].expand(args)

    def label_def(self, items):
        label = items[0]
        if label in self.labels:
            raise
        self.labels.add(label)
        return Label(name=label)

    def single_arg(self, items):
        a = items[0]
        return a, a, Next()

    def double_arg(self, items):
        a, b = items[0], items[1]
        return a, b, Next()

    def triple_arg(self, items):
        a, b, c = [x for x in items]
        return a, b, c

    def data_block(self, items):
        return items

    def IDENT(self, token):
        return token.value

    def NUMBER(self, token):
        return eval(token.value)


def compile(source: str):
    parser = Lark_StandAlone()
    tree = parser.parse(source)
    debug(tree)
    transformer = SubleqTransformer()
    instructions = transformer.transform(tree)
    debug(instructions)

    code = []
    labels = {"IO": IO_ADDR, "HALT": HALT_ADDR}
    for inst in instructions:
        if isinstance(inst, Label):
            labels[inst.name] = len(code)
            continue
        if isinstance(inst, Next):
            code.append(len(code) + 1)
            continue
        code.append(inst)

    code = [labels.get(c, c) for c in code]

    data = np.array(code, dtype=np.int16)

    return data


def main():
    parser = argparse.ArgumentParser(description="Subleq compiler (gcc-style)")
    parser.add_argument("input", type=Path, help="Input source file")
    parser.add_argument("-o", "--output", type=Path, help="Output filename")
    parser.add_argument(
        "-g", dest="debug", action="store_true", help="Enable debug mode"
    )
    args = parser.parse_args()

    global DEBUG
    DEBUG = args.debug

    debug(f"Input file: {args.input!r}")

    source = args.input.read_text()
    data = compile(source)

    output_filename = args.output or args.input
    output_filename = output_filename.with_suffix(".npy")
    np.save(output_filename, data)
    print(f"Compiled output saved to {output_filename!r}")


if __name__ == "__main__":
    main()
