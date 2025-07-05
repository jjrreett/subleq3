# noqa: INP001
"""Compile subleq assembly into image in the format of np.ndarray."""

import argparse
import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

import numpy as np
from rich import print  # noqa: A004

from .subleq import Lark_StandAlone, Transformer

DEBUG = True


@wraps(print)
def debug(*args: tuple, **kwargs: dict) -> None:
    """If DEBUG: print."""
    if DEBUG:
        print(*args, **kwargs)


IO_ADDR = 0x03
HALT_ADDR = 0x00


@dataclass
class _Label:
    name: str


@dataclass
class _Next: ...


@dataclass
class _Macro:
    ident: str
    args: list[str]
    instructions: list[str | _Next | _Label]
    call_counter = 0

    def expand(self, actual_args: Iterable[str]) -> list[str | _Next | _Label]:
        if len(actual_args) != len(self.args):
            msg = f"Macro '{self.ident}' expects {len(self.args)} arguments, got {len(actual_args)}"
            raise ValueError(msg)

        arg_map = dict(zip(self.args, actual_args, strict=False))
        expanded = []

        labels = {}

        for instr in self.instructions:
            if isinstance(instr, str):
                # Replace argument name with its actual value
                expanded.append(arg_map.get(instr, instr))
            elif isinstance(instr, (_Next, int)):
                expanded.append(instr)
            elif isinstance(instr, _Label):
                mangled_name = f"{self.ident}_{self.call_counter}_{instr.name}"
                labels[instr.name] = mangled_name
                expanded.append(_Label(name=mangled_name))
            else:
                msg = f"Unsupported instruction token: {instr!r}"
                raise TypeError(msg)
        self.call_counter += 1

        remap_labels = []
        for instr in expanded:
            if isinstance(instr, str) and instr in labels:
                remap_labels.append(labels[instr])
            else:
                remap_labels.append(instr)

        debug(f"Macro {self.ident!r} expanded to:")
        debug(remap_labels)

        return remap_labels


class _SubleqTransformer(Transformer):
    def __init__(self) -> None:
        self.labels = set()
        self.macros = {}

    def start(self, items) -> list[str | _Next | _Label]:  # noqa: ANN001
        return self.instructions(items)

    def instructions(self, items) -> list[str | _Next | _Label]:  # noqa: ANN001
        instructions = []
        for item in items:
            if isinstance(item, str) or not isinstance(item, Iterable):
                instructions.append(item)
                continue
            instructions.extend(item)
        return instructions

    def macro_args(self, items) -> Iterable[str]:  # noqa: ANN001
        return items

    def macro_block(self, items) -> Iterable:  # noqa: ANN001
        ident, macro_args, *instructions = items
        m = _Macro(ident, macro_args, self.instructions(instructions))
        self.macros[ident] = m
        return []

    def macro_call(self, items) -> list[str | _Next | _Label]:  # noqa: ANN001
        ident, args = items
        return self.macros[ident].expand(args)

    def label_def(self, items) -> _Label:  # noqa: ANN001
        return _Label(name=items[0])

    def single_arg(self, items) -> tuple[str | _Next]:  # noqa: ANN001
        a = items[0]
        return a, a, _Next()

    def double_arg(self, items) -> tuple[str | _Next]:  # noqa: ANN001
        a, b = items
        return a, b, _Next()

    def triple_arg(self, items) -> tuple[str | _Next]:  # noqa: ANN001
        a, b, c = items
        return a, b, c

    def data_block(self, items) -> tuple[str | _Label]:  # noqa: ANN001
        return items

    def IDENT(self, token) -> str:  # noqa: ANN001, N802
        return token.value

    def NUMBER(self, token) -> int:  # noqa: ANN001, N802
        return eval(token.value)  # noqa: S307


def subleq_compile(source: str) -> tuple[np.ndarray, dict[str, int]]:
    """Compile subleq assembly into image in the format of np.ndarray."""
    parser = Lark_StandAlone()
    tree = parser.parse(source)
    debug(tree)
    transformer = _SubleqTransformer()
    instructions = transformer.transform(tree)
    debug(instructions)

    code = []
    labels = {"IO": IO_ADDR, "HALT": HALT_ADDR}
    for inst in instructions:
        if isinstance(inst, _Label):
            labels[inst.name] = len(code)
            continue
        if isinstance(inst, _Next):
            code.append(len(code) + 1)
            continue
        code.append(inst)

    code = [labels.get(c, c) for c in code]

    data = np.zeros((len(code),), dtype=np.uint16)

    for i, x in enumerate(code):
        data[i] = np.uint16(x % (1 << 16))

    return data, labels


def main() -> None:
    """Entrypoint."""
    parser = argparse.ArgumentParser(description="Subleq compiler (gcc-style)")
    parser.add_argument("input", type=Path, help="Input source file")
    parser.add_argument("-o", "--output", type=Path, help="Output filename")
    parser.add_argument(
        "-l", "--labels", dest="labels", action="store_true", help="Save labels to output.labels"
    )
    parser.add_argument(
        "-g",
        dest="debug",
        action="store_true",
        help="Enable debug mode",
    )
    args = parser.parse_args()

    global DEBUG  # noqa: PLW0603
    DEBUG = args.debug

    debug(f"Input file: {args.input!r}")

    source = args.input.read_text()
    data, labels = subleq_compile(source)

    output_filename = args.output or args.input
    output_filename = output_filename.with_suffix(".npy")
    if args.labels:
        lbstr = json.dumps(labels)
        output_filename.with_suffix(".labels").write_text(lbstr)
    np.save(output_filename, data)
    print(f"Compiled output saved to {output_filename!r}. {len(data)} instructions")


if __name__ == "__main__":
    main()
