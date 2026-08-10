# noqa: INP001
"""Compile subleq assembly into image in the format of np.ndarray."""

import argparse
import contextlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

import numpy as np
from rich import print  # noqa: A004

from .link import link_sources
from .subleq import Lark_StandAlone, Transformer, VisitError

DEBUG = False

_STRING_ESCAPES = {
    r'\"': '"',
    r"\\": "\\",
    r"\n": "\n",
    r"\r": "\r",
    r"\t": "\t",
    r"\0": "\0",
}


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


@dataclass(frozen=True)
class _Literal:
    value: int


@dataclass(frozen=True)
class _LiteralPool: ...


_InstructionToken = str | int | _Next | _Label | _Literal | _LiteralPool


@dataclass
class _Macro:
    ident: str
    args: list[str]
    instructions: list[_InstructionToken]
    call_counter = 0

    def expand(self, actual_args: Iterable[_InstructionToken]) -> list[_InstructionToken]:
        actual_args = list(actual_args)
        if len(actual_args) != len(self.args):
            msg = f"Macro '{self.ident}' expects {len(self.args)} arguments, got {len(actual_args)}"
            raise CompilationError(msg)

        arg_map = dict(zip(self.args, actual_args, strict=False))

        # Every label defined by a macro is private to that invocation. Keeping
        # the mangled name local prevents macro internals from changing the
        # caller's global-label scope. This is essential for nested macros.
        labels: dict[str, str] = {}
        for instr in self.instructions:
            if isinstance(instr, _Label):
                if instr.name in labels:
                    msg = (
                        f"Label {instr.name!r} is defined twice in macro {self.ident!r}"
                    )
                    raise CompilationError(msg)
                base_name = instr.name.removeprefix("@")
                labels[instr.name] = f"@{self.ident}_{self.call_counter}_{base_name}"

        # Replace macro-private label definitions and references.
        instructions = [
            _Label(name=labels[instr.name])
            if isinstance(instr, _Label) and instr.name in labels
            else instr
            for instr in self.instructions
        ]
        instructions = [
            labels[instr] if isinstance(instr, str) and instr in labels else instr
            for instr in instructions
        ]

        # Replace argument names with the values supplied by the caller.
        instructions = [
            arg_map.get(instr, instr) if isinstance(instr, str) else instr
            for instr in instructions
        ]
        for instr in instructions:
            if not isinstance(
                instr, (str, _Next, int, _Label, _Literal, _LiteralPool)
            ):
                msg = f"Unsupported instruction token: {instr!r}"
                raise TypeError(msg)

        self.call_counter += 1
        return instructions


class _SubleqTransformer(Transformer):
    def __init__(self) -> None:
        self.labels = set()
        self.macros = {}

    def start(self, items) -> list[_InstructionToken]:  # noqa: ANN001
        return self.instructions(items)

    def instructions(self, items) -> list[_InstructionToken]:  # noqa: ANN001
        instructions = []
        for item in items:
            if isinstance(item, str) or not isinstance(item, Iterable):
                instructions.append(item)
                continue
            instructions.extend(item)
        return instructions

    def instruction(self, items) -> list[_InstructionToken]:
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
            if len(args) != 3:
                msg = f"subleq opcode requires 3 arguments, got {len(args)}"
                raise CompilationError(msg)
            return args
        raise CompilationError(f"Opcode {name!r} not recognized.")

    def args(self, items) -> list[_InstructionToken]:
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

    def data(self, items) -> tuple[str | _Label]:  # noqa: ANN001
        return items

    def macro(self, items) -> Iterable:  # noqa: ANN001
        defines, *instructions = items
        ident, *args = defines
        if ident in self.macros:
            raise CompilationError(f"Macro {ident!r} is defined twice")
        m = _Macro(ident, args, self.instructions(instructions))
        self.macros[ident] = m
        return []

    def byte(self, items):
        for x in items:
            # assert x == x & 0xFF, f"The data in the '.byte' directive must be of size byte 0x{x:x}"
            x = np.int8(x) if x < 0 else np.uint8(x)
        return items

    def word(self, items):
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

    def literal(self, items) -> _Literal:
        (value,) = items
        return _Literal(value % (1 << 16))

    def literal_pool(self, items) -> _LiteralPool:  # noqa: ARG002
        return _LiteralPool()

    def string(self, items):
        (token,) = items
        raw = str(token)[1:-1]
        characters: list[str] = []
        index = 0
        while index < len(raw):
            if raw[index] == "\\":
                escape = raw[index : index + 2]
                characters.append(_STRING_ESCAPES[escape])
                index += 2
                continue
            characters.append(raw[index])
            index += 1
        return [ord(char) for char in characters]

    def LOCAL_LABEL(self, token):
        return token.value

    def value(self, items):
        if len(items) != 2:
            assert False, "Unreachable code"
        return "".join(items)  # if it starts with an "@"

    def local_label_def(self, items):
        name = items[0]
        return _Label(name="@" + name)


def subleq_compile(source: str) -> tuple[np.ndarray, dict[str, int]]:
    """Compile subleq assembly into image in the format of np.ndarray."""
    parser = Lark_StandAlone(propagate_positions=True)
    tree = parser.parse(source)
    debug(tree)
    transformer = _SubleqTransformer()
    try:
        instructions = transformer.transform(tree)
    except VisitError as error:
        if isinstance(error.orig_exc, CompilationError):
            raise error.orig_exc from error
        raise
    debug(instructions)

    literal_values = list(
        dict.fromkeys(
            inst.value for inst in instructions if isinstance(inst, _Literal)
        )
    )
    literal_pool_count = sum(isinstance(inst, _LiteralPool) for inst in instructions)
    if literal_pool_count > 1:
        raise CompilationError("The .literals directive may appear only once")
    if literal_values and literal_pool_count == 0:
        raise CompilationError(
            "Immediate literals require a .literals directive to reserve their storage"
        )

    # Labels do not occupy memory, so the first pass records their addresses
    # while preserving the scope in which every emitted value appeared.
    labels: dict[str, int] = {}
    local_labels: dict[tuple[str, str], int] = {}
    scoped_values: list[tuple[str | int | _Literal, str]] = []
    literal_addresses: dict[int, int] = {}
    scope = "<start of file>"
    address = 0

    for inst in instructions:
        if isinstance(inst, _LiteralPool):
            for literal_value in literal_values:
                literal_addresses[literal_value] = address
                scoped_values.append((literal_value, scope))
                address += 1
            continue

        if isinstance(inst, _Label):
            if inst.name.startswith("@"):
                key = (scope, inst.name)
                if key in local_labels:
                    msg = (
                        f"Local label {inst.name!r} is defined twice in scope {scope!r}"
                    )
                    raise CompilationError(msg)
                local_labels[key] = address
                continue

            if inst.name in labels:
                raise CompilationError(f"Global label {inst.name!r} is defined twice")
            labels[inst.name] = address
            scope = inst.name
            continue

        if isinstance(inst, _Next):
            value: str | int = address + 1
        else:
            value = inst
        scoped_values.append((value, scope))
        address += 1

    debug("Global labels", labels, sep="\n")
    debug("Local labels", local_labels, sep="\n")

    # Resolve references in the scope captured at their source position.
    machine_code: list[int] = []
    for value, value_scope in scoped_values:
        if isinstance(value, _Literal):
            value = literal_addresses[value.value]
        elif isinstance(value, str):
            if value.startswith("@"):
                key = (value_scope, value)
                if key not in local_labels:
                    msg = (
                        f"Local label {value!r} is not defined in scope {value_scope!r}"
                    )
                    raise CompilationError(msg)
                value = local_labels[key]
            else:
                if value not in labels:
                    raise CompilationError(f"Global label {value!r} is not defined")
                value = labels[value]

        with contextlib.suppress(TypeError, ValueError):
            value = int(value)
        if not isinstance(value, int):
            msg = f"Value {value!r} could not be reduced to an integer"
            raise CompilationError(msg)
        machine_code.append(value)

    data = np.zeros((len(machine_code),), dtype=np.uint16)

    for i, x in enumerate(machine_code):
        data[i] = np.uint16(x % (1 << 16))

    return data, labels


def subleq_compile_files(inputs: Sequence[Path]) -> tuple[np.ndarray, dict[str, int]]:
    """Link and compile one or more source files in the given order."""
    return subleq_compile(link_sources(list(inputs)))


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Add compiler arguments to a standalone or subcommand parser."""
    parser.add_argument(
        "input",
        type=Path,
        nargs="+",
        help="Input source files, linked in the order given",
    )
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
    parser.set_defaults(command_handler=execute)


def execute(args: argparse.Namespace) -> None:
    """Compile a source file using parsed command-line arguments."""

    global DEBUG  # noqa: PLW0603
    DEBUG = args.debug

    debug(f"Input files: {args.input!r}")

    data, labels = subleq_compile_files(args.input)

    output_filename = args.output or args.input[0]
    output_filename = output_filename.with_suffix(".npy")
    if args.labels:
        lbstr = json.dumps(labels)
        output_filename.with_suffix(".labels").write_text(lbstr)
    np.save(output_filename, data)
    print(f"Compiled output saved to {output_filename!r}. {len(data)} instructions")


def main(argv: Sequence[str] | None = None) -> None:
    """Run the standalone compiler entry point."""
    parser = argparse.ArgumentParser(description="SUBLEQ compiler (gcc-style)")
    configure_parser(parser)
    execute(parser.parse_args(argv))


if __name__ == "__main__":
    main()
