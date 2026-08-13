# noqa: INP001
"""Compile subleq assembly into image in the format of np.ndarray."""

import argparse
import contextlib
import json
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

import numpy as np
from rich import print  # noqa: A004

from .analysis import DocumentAnalysis
from .harness import HarnessSyntaxError, strip_test_harness
from .link import link_sources, link_sources_with_origins
from .subleq import Lark_StandAlone, Transformer, UnexpectedInput, VisitError, v_args

DEBUG = False

_STRING_ESCAPES = {
    r'\"': '"',
    r"\'": "'",
    r"\\": "\\",
    r"\n": "\n",
    r"\r": "\r",
    r"\t": "\t",
    r"\0": "\0",
}


class CompilationError(Exception):
    """Failure to compile, optionally tied to a source location."""

    def __init__(
        self,
        message: str,
        *,
        source: str | None = None,
        source_name: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.source_name = source_name
        self.line = line
        self.column = column

    def attach_source(self, source: str, source_name: str | None = None) -> None:
        """Add source information when a lower compiler layer lacked a filename."""
        if self.source is None:
            self.source = source
        if self.source_name is None:
            self.source_name = source_name


def _syntax_error_message(error: UnexpectedInput) -> str:
    """Turn Lark's verbose parser dump into a compact headline."""
    token = getattr(error, "token", None)
    if token is not None:
        value = str(token)
        headline = f"unexpected {value!r}"
    else:
        char = getattr(error, "char", None)
        headline = f"unexpected character {char!r}" if char else "invalid syntax"

    expected = sorted(
        name
        for name in (getattr(error, "expected", ()) or ())
        if not name.startswith("__ANON_")
    )
    if expected:
        friendly = [
            name.replace("_NEWLINE", "newline").lower()
            for name in expected
        ]
        headline += "; expected " + ", ".join(friendly)
    return headline


@dataclass(frozen=True)
class MacroTradeoff:
    """Estimated code-size and runtime tradeoff for sharing a macro body."""

    macro: str
    body_instructions: int
    uses: int
    inline_instructions: int
    subroutine_instructions: int
    saved_instructions: int
    extra_cycles_per_call: int

    def message(self) -> str:
        return (
            f"macro {self.macro!r} expands to {self.body_instructions} SUBLEQ "
            f"instructions and is used {self.uses} times "
            f"({self.inline_instructions} inlined instructions). A shared "
            f"subroutine is estimated at {self.subroutine_instructions} "
            f"instructions, saving about {self.saved_instructions} instructions "
            f"({self.saved_instructions * 3} words), but adding roughly "
            f"{self.extra_cycles_per_call} instructions of call and argument "
            "overhead per invocation. This is a heuristic; indirect parameters, "
            "embedded data, and branch paths can change the tradeoff."
        )


_SUBROUTINE_ABI_MACROS = ("psh", "pop", "jsr", "rts")
_MIN_SHARED_MACRO_INSTRUCTIONS = 20


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
class _LiteralPool:
    capacity: int


@dataclass(frozen=True)
class _Bootstrap: ...


@dataclass(frozen=True)
class _Sourced:
    value: object
    line: int


_InstructionToken = str | int | _Next | _Label | _Literal | _LiteralPool | _Bootstrap


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
                instr,
                (str, _Next, int, _Label, _Literal, _LiteralPool, _Bootstrap),
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

    @v_args(meta=True)
    def instruction(self, meta, items) -> list[_InstructionToken]:
        if not items or items[0] is None:
            return None

        if len(items) == 2:
            name, args = items
        else:
            name = items[0]
            args = []

        if name in self.macros:
            return [_Sourced(value, meta.line) for value in self.macros[name].expand(args)]
        if name == "subleq":
            if len(args) != 3:
                msg = f"subleq opcode requires 3 arguments, got {len(args)}"
                raise CompilationError(msg)
            return [_Sourced(value, meta.line) for value in args]
        raise CompilationError(f"Opcode {name!r} not recognized.")

    def args(self, items) -> list[_InstructionToken]:
        return list(items)

    def macro_signature(self, items) -> list[str]:  # noqa: ANN001
        return list(items)

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
        body = [
            item.value if isinstance(item, _Sourced) else item
            for item in self.instructions(instructions)
        ]
        m = _Macro(ident, args, body)
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

    def char(self, items):
        (token,) = items
        return [ord(self._decode_escaped(str(token)[1:-1]))]

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

    def char_literal(self, items) -> _Literal:
        (token,) = items
        value = ord(self._decode_escaped(str(token)[1:]))
        return _Literal(value % (1 << 16))

    def literal_pool(self, items) -> _LiteralPool:
        (capacity,) = items
        return _LiteralPool(capacity)

    def bootstrap(self, items) -> _Bootstrap:  # noqa: ARG002
        return _Bootstrap()

    def string(self, items):
        (token,) = items
        return [ord(char) for char in self._decode_escaped(str(token)[1:-1])]

    @staticmethod
    def _decode_escaped(raw: str) -> str:
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
        return "".join(characters)

    def LOCAL_LABEL(self, token):
        return token.value

    def value(self, items):
        if len(items) != 2:
            assert False, "Unreachable code"
        return "".join(items)  # if it starts with an "@"

    def local_label_def(self, items):
        name = items[0]
        return _Label(name="@" + name)


def _effective_macro_uses(analysis: DocumentAnalysis) -> Counter[str]:
    """Count emitted macro expansions, including calls nested in macros."""
    uses: Counter[str] = Counter()

    def add_expansion(name: str, quantity: int, stack: tuple[str, ...]) -> None:
        if name not in analysis.macros or name in stack:
            return
        uses[name] += quantity
        macro = analysis.macros[name]
        if macro.instruction_count is None:
            return
        nested = Counter(
            invocation.name
            for invocation in analysis.invocations
            if invocation.macro_owner == name
            and invocation.name in analysis.macros
        )
        for nested_name, nested_quantity in nested.items():
            add_expansion(
                nested_name,
                quantity * nested_quantity,
                (*stack, name),
            )

    top_level = Counter(
        invocation.name
        for invocation in analysis.invocations
        if invocation.macro_owner is None and invocation.name in analysis.macros
    )
    for name, quantity in top_level.items():
        add_expansion(name, quantity, ())
    return uses


def macro_tradeoffs(source: str) -> list[MacroTradeoff]:
    """Find macros likely to save code space when converted to subroutines."""
    analysis = DocumentAnalysis.parse(source)
    if not all(name in analysis.macros for name in _SUBROUTINE_ABI_MACROS):
        return []

    costs = {
        name: analysis.macros[name].instruction_count
        for name in _SUBROUTINE_ABI_MACROS
    }
    if any(cost is None for cost in costs.values()):
        return []

    psh_cost = int(costs["psh"])
    pop_cost = int(costs["pop"])
    jsr_cost = int(costs["jsr"])
    rts_cost = int(costs["rts"])
    uses = _effective_macro_uses(analysis)
    tradeoffs: list[MacroTradeoff] = []

    for name, quantity in uses.items():
        macro = analysis.macros[name]
        body_cost = macro.instruction_count
        if (
            name in _SUBROUTINE_ABI_MACROS
            or body_cost is None
            or body_cost < _MIN_SHARED_MACRO_INSTRUCTIONS
            or quantity < 2
        ):
            continue

        parameter_count = len(macro.parameters)
        inline_cost = body_cost * quantity
        shared_body_cost = body_cost + rts_cost + parameter_count * pop_cost + 1
        call_site_cost = jsr_cost + parameter_count * psh_cost
        shared_cost = shared_body_cost + quantity * call_site_cost
        savings = inline_cost - shared_cost
        if savings <= 0:
            continue

        runtime_overhead = (
            jsr_cost
            + parameter_count * (psh_cost + pop_cost)
            + rts_cost
            + 1
        )
        tradeoffs.append(
            MacroTradeoff(
                macro=name,
                body_instructions=body_cost,
                uses=quantity,
                inline_instructions=inline_cost,
                subroutine_instructions=shared_cost,
                saved_instructions=savings,
                extra_cycles_per_call=runtime_overhead,
            )
        )

    return sorted(tradeoffs, key=lambda item: item.saved_instructions, reverse=True)


def print_compile_warning(message: str) -> None:
    """Print a compiler advisory with a consistent warning style."""
    print(f"[yellow]warning:[/yellow] {message}", file=sys.stderr)


def subleq_compile(
    source: str,
    *,
    warning_handler: Callable[[str], None] | None = None,
    source_origins: list[tuple[str, int] | None] | None = None,
    source_map: dict[int, tuple[str, int]] | None = None,
) -> tuple[np.ndarray, dict[str, int]]:
    """Compile subleq assembly into image in the format of np.ndarray."""
    try:
        source = strip_test_harness(source)
    except HarnessSyntaxError as error:
        raise CompilationError(str(error)) from error
    parser = Lark_StandAlone(propagate_positions=True)
    try:
        tree = parser.parse(source)
    except UnexpectedInput as error:
        raise CompilationError(
            _syntax_error_message(error),
            source=source,
            line=getattr(error, "line", None),
            column=getattr(error, "column", None),
        ) from error
    debug(tree)
    transformer = _SubleqTransformer()
    try:
        instructions = transformer.transform(tree)
    except VisitError as error:
        if isinstance(error.orig_exc, CompilationError):
            raise error.orig_exc from error
        raise
    debug(instructions)

    expanded_instructions: list[_InstructionToken] = []
    emitted_words = 0
    for instruction in instructions:
        if isinstance(instruction, _Bootstrap):
            if emitted_words != 0:
                raise CompilationError("The .bootstrap directive must emit at address 0")
            expanded_instructions.extend(
                [5, 5, "main", _Label("IO"), 0, _Label("INSPECT"), 0, 0]
            )
            emitted_words += 6
            continue
        expanded_instructions.append(instruction)
        if isinstance(instruction, _LiteralPool):
            emitted_words += instruction.capacity
        elif not isinstance(instruction, _Label):
            emitted_words += 1
    instructions = expanded_instructions

    literal_values = list(
        dict.fromkeys(
            value.value
            for inst in instructions
            if isinstance((value := inst.value if isinstance(inst, _Sourced) else inst), _Literal)
        )
    )
    literal_pool_count = sum(
        isinstance(inst.value if isinstance(inst, _Sourced) else inst, _LiteralPool)
        for inst in instructions
    )
    if literal_pool_count > 1:
        raise CompilationError("The .literals directive may appear only once")
    if literal_values and literal_pool_count == 0:
        raise CompilationError(
            "Immediate literals require a .literals count directive with enough capacity"
        )
    literal_pool = next(
        (inst for inst in instructions if isinstance(inst, _LiteralPool)), None
    )
    if literal_pool is not None and literal_pool.capacity < 0:
        raise CompilationError("The .literals capacity cannot be negative")
    if literal_pool is not None and len(literal_values) > literal_pool.capacity:
        raise CompilationError(
            f"The .literals pool reserves {literal_pool.capacity} words, "
            f"but {len(literal_values)} unique literals are required"
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
        origin_line = inst.line if isinstance(inst, _Sourced) else None
        if isinstance(inst, _Sourced):
            inst = inst.value
        if isinstance(inst, _LiteralPool):
            for literal_value in literal_values:
                literal_addresses[literal_value] = address
                scoped_values.append((literal_value, scope))
                address += 1
            for _ in range(inst.capacity - len(literal_values)):
                scoped_values.append((0, scope))
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
        if source_map is not None and origin_line is not None:
            if source_origins is not None and origin_line <= len(source_origins):
                origin = source_origins[origin_line - 1]
                if origin is not None:
                    source_map[address] = origin
            else:
                source_map[address] = ("<source>", origin_line)
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

    if warning_handler is not None:
        for tradeoff in macro_tradeoffs(source):
            warning_handler(tradeoff.message())

    return data, labels


def subleq_compile_files(
    inputs: Sequence[Path],
    *,
    warning_handler: Callable[[str], None] | None = None,
) -> tuple[np.ndarray, dict[str, int]]:
    """Link and compile one or more source files in the given order."""
    source = link_sources(list(inputs))
    try:
        return subleq_compile(source, warning_handler=warning_handler)
    except CompilationError as error:
        display_name = str(inputs[0]) if len(inputs) == 1 else "<linked source>"
        error.attach_source(source, display_name)
        raise


def subleq_compile_files_with_source_map(
    inputs: Sequence[Path],
    *,
    warning_handler: Callable[[str], None] | None = None,
) -> tuple[np.ndarray, dict[str, int], dict[int, tuple[str, int]]]:
    """Compile files and retain instruction-address source locations."""
    source, origins = link_sources_with_origins(list(inputs))
    source_map: dict[int, tuple[str, int]] = {}
    try:
        data, labels = subleq_compile(
            source,
            warning_handler=warning_handler,
            source_origins=origins,
            source_map=source_map,
        )
    except CompilationError as error:
        if error.line is not None and error.line <= len(origins):
            origin = origins[error.line - 1]
            if origin is not None:
                source_name, source_line = origin
                error.source_name = source_name
                error.line = source_line
                source_path = Path(source_name)
                if source_path.is_file():
                    error.source = source_path.read_text()
        if error.source_name is None:
            display_name = str(inputs[0]) if len(inputs) == 1 else "<linked source>"
            error.attach_source(source, display_name)
        raise
    return data, labels, source_map


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

    data, labels = subleq_compile_files(
        args.input,
        warning_handler=print_compile_warning,
    )

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
