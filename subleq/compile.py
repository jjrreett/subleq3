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
from . import const
import contextlib

DEBUG = True


class CompilationError(Exception):
    """Failure to Compile."""


@wraps(print)
def debug(*args: tuple, **kwargs: dict) -> None:
    """If DEBUG: print."""
    if DEBUG:
        print(*args, **kwargs)


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

        instructions = self.instructions
        # find all local labels and compute the mangled form
        labels = {}
        for instr in instructions:
            if isinstance(instr, _Label):
                mangled_name = f"{self.ident}_{self.call_counter}_{instr.name}"
                labels[instr.name] = mangled_name
        # replace local labels with mangled form
        instructions = [
            _Label(name=labels[instr.name])
            if isinstance(instr, _Label) and instr.name in labels
            else instr
            for instr in self.instructions
        ]
        # replace idents referencing local labels with their mangled name
        instructions = [
            labels[instr] if isinstance(instr, str) and instr in labels else instr
            for instr in instructions
        ]

        # Replace argument name with its actual value
        instructions = [
            arg_map.get(instr, instr) if isinstance(instr, str) else instr for instr in instructions
        ]
        for instr in instructions:
            if not isinstance(instr, (str, _Next, int, _Label)):
                msg = f"Unsupported instruction token: {instr!r}"
                raise TypeError(msg)

        self.call_counter += 1

        debug(f"Macro {self.ident!r} expanded to:")
        debug(instructions)

        return instructions


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

    def instruction(self, items) -> list[str | _Next | _Label]:
        if not items or items[0] is None:
            return None

        if len(items) == 2:
            name, args = items
        else:
            name = items[0]
            args = []

        if name in self.macros:
            return self.macros[name].expand(args)
        if name == "subleq":
            assert len(args) == 3, f"subleq opcode requires 3 arguments, {len(args)}"
            return args
        raise CompilationError(f"Opcode {name!r} not recognized.")

    def args(self, items) -> list[str | _Next | int]:
        return list(items)

    def macro_args(self, items) -> Iterable[str]:  # noqa: ANN001
        return items

    def label_def(self, items) -> _Label:  # noqa: ANN001
        name = items[0]
        return _Label(name=name)

    def stmt(self, items) -> list:
        return []

    def IDENT(self, token) -> str:  # noqa: ANN001, N802
        return token.value

    def NUMBER(self, token) -> int:  # noqa: ANN001, N802
        val: str = token.value
        return eval(val.replace("$", "0x").replace("%", "0b"))  # noqa: S307

    def QMARK(self, token) -> int:  # noqa: ANN001, N802
        return _Next()

    def ASCII_CHARS(self, token):
        return [ord(char) for char in token]

    def data(self, items) -> tuple[str | _Label]:  # noqa: ANN001
        return items

    def macro(self, items) -> Iterable:  # noqa: ANN001
        defines, *instructions = items
        ident, *args = defines
        m = _Macro(ident, args, self.instructions(instructions))
        self.macros[ident] = m
        return []

    def byte(self, items):
        for x in items:
            # assert x == x & 0xFF, f"The data in the '.byte' directive must be of size byte 0x{x:x}"
            x = np.int8(x) if x < 0 else np.uint8(x)
        return items

    def word(self, items):
        for x in items:
            x = np.int16(x) if x < 0 else np.uint16(x)
        return items

    def dword(self, items):
        expanded = []
        for x in items:
            # assert x == x & 0xFFFF_FFFF, (
            #     f"The data in the '.dword' directive must be of size dword 0x{x:x}"
            # )
            x = np.int32(x) if x < 0 else np.uint32(x)
            expanded.append((x >> 16))  # high word
            expanded.append((x & 0xFFFF))  # low word
        return expanded

    def ascii(self, items):
        if len(items) == 0:
            return None
        if len(items) == 1:
            return items[0]
        assert False, "This code should be unreachable"

    def asciiz(self, items):
        if len(items) == 0:
            return [0]
        if len(items) == 1:
            return items[0] + [0]
        assert False, "This code should be unreachable"

    def fill(self, items):
        count, value = items
        return [value] * count

    def reserve(self, items):
        (count,) = items
        return self.fill((count, 0))


def subleq_compile(source: str) -> tuple[np.ndarray, dict[str, int]]:
    """Compile subleq assembly into image in the format of np.ndarray."""
    parser = Lark_StandAlone()
    tree = parser.parse(source)
    debug(tree)
    transformer = _SubleqTransformer()
    instructions = transformer.transform(tree)
    debug(instructions)

    code = []
    labels = const.get_labels()
    for inst in instructions:
        if isinstance(inst, _Label):
            if inst.name in labels:
                raise CompilationError(f"Label {inst.name!r} used twice")
            labels[inst.name] = len(code)
            continue
        if isinstance(inst, _Next):
            code.append(len(code) + 1)
            continue
        code.append(inst)

    code = [labels.get(c, c) for c in code]

    data = np.zeros((len(code),), dtype=np.uint16)

    for i, x in enumerate(code):
        with contextlib.suppress(ValueError):
            x = int(x)
        if not isinstance(x, int):
            msg = f"The label {x!r} was not reduced to an int"
            raise CompilationError(msg)
        assert isinstance(x, int), f"x must be an int {x!r}"
        data[i] = np.uint16(x % (1 << 16))

    return data, labels


def main() -> None:
    """Entrypoint."""
    parser = argparse.ArgumentParser(description="Subleq compiler (gcc-style)")
    parser.add_argument("input", type=Path, help="Input source file")
    parser.add_argument("-o", "--output", type=Path, help="Output filename")
    parser.add_argument(
        "-l",
        "--labels",
        dest="labels",
        action="store_true",
        help="Save labels to output.labels",
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
