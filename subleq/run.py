# noqa: INP001
"""Compile or load programs and execute them in the SUBLEQ emulator."""

import argparse
import json
import os
import sys
import time
from collections import deque
from collections.abc import Callable, Sequence
from functools import wraps
from pathlib import Path

import numpy as np

from . import const
from .compile import print_compile_warning, subleq_compile_files_with_source_map

DEBUG = True
CLOCK_HZ = 1_000_000
MICRO_INSTRUCTIONS_PER_INSTRUCTION = 6
INSTRUCTIONS_PER_SECOND = CLOCK_HZ / MICRO_INSTRUCTIONS_PER_INSTRUCTION
TIMING_BATCH_SIZE = 256


class ExecutionLimitError(Exception):
    """A program did not halt within its configured instruction limit."""


class ExecutionFaultError(Exception):
    """Execution reached an address that cannot be decoded safely."""


@wraps(print)
def debug(*args: tuple, **kwargs: dict) -> None:
    """If DEBUG: print."""
    if DEBUG:
        print(*args, **kwargs, file=sys.stderr)


def print_data(data: np.ndarray) -> None:
    """Print the subleq memory."""
    for i, x in enumerate(data):
        print(f"{i:x}: {x:x}")


def format_value(v):
    return f"{int(v):5d} (0x{int(v) & 0xFFFF:04X}, {np.int16(v):6d})"


def debug_instruction(pc, data, rlabels):
    a, b, c = (
        data[pc],
        data[pc + 1],
        data[pc + 2],
    )
    da, db = np.int16(data[a]), np.int16(data[b])
    with np.errstate(over="ignore"):
        ndb = db - da
    debug(
        f"data[{pc:5d}] = {a:5d} -> data[{a:5d}] = {np.uint16(da):6x} : {rlabels.get(a, ''):15s}"
    )
    debug(
        f"data[{pc + 1:5d}] = {b:5d} -> data[{b:5d}] = {np.uint16(db):6x} : {rlabels.get(b, ''):15s} -> {ndb:5d}, {np.uint16(ndb):6x}, {np.uint16(ndb):0>16b}"
    )
    debug(
        f"data[{pc + 2:5d}] = {c:5d}                         : {rlabels.get(c, ''):15s}"
    )
    debug("-" * 50)


def report_misaligned_pc(pc, data, rlabels, previous_instruction) -> None:
    """Print the transition that brought execution to an unaligned PC."""
    print(
        f"WARNING: unaligned instruction PC={int(pc)} "
        f"(0x{int(pc):04X}, PC % 3 = {int(pc) % 3}) "
        f"{rlabels.get(int(pc), '')}",
        file=sys.stderr,
    )
    if previous_instruction is None:
        print("  no previous instruction (initial PC)", file=sys.stderr)
    else:
        previous_pc, a, b, c, result, transition = previous_instruction
        print(
            f"  arrived from PC={previous_pc} (0x{previous_pc:04X}): "
            f"subleq {a}, {b}, {c}; result={result} (0x{result & 0xFFFF:04X}); "
            f"{transition}",
            file=sys.stderr,
        )
    start = max(0, int(pc) - 3)
    stop = min(len(data), int(pc) + 6)
    words = " ".join(f"[{index}]={int(data[index])}" for index in range(start, stop))
    print(f"  nearby memory: {words}", file=sys.stderr)


def report_execution_trace(trace, rlabels, source_map=None) -> None:
    """Print the most recently completed instructions, oldest first."""
    if not trace:
        print("Execution traceback: no completed instructions", file=sys.stderr)
        return
    print(
        f"Execution traceback (last {len(trace)} completed instructions):",
        file=sys.stderr,
    )
    for pc, a, b, c, result, transition in trace:
        label = rlabels.get(pc, "")
        label_text = f" {label}" if label else ""
        location = (source_map or {}).get(pc)
        source_text = f" [{location[0]}:{location[1]}]" if location else ""
        print(
            f"  PC={pc:5d} (0x{pc:04X}, mod 3={pc % 3}){label_text}{source_text}: "
            f"subleq {a}, {b}, {c}; result={result:6d} "
            f"(0x{result & 0xFFFF:04X}); {transition}",
            file=sys.stderr,
        )


def execution_fault(message, trace, rlabels, source_map=None) -> None:
    """Report useful machine history and stop without a Python traceback."""
    print(f"EXECUTION FAULT: {message}", file=sys.stderr)
    report_execution_trace(trace, rlabels, source_map)
    raise ExecutionFaultError(message)


def subleq(
    data: np.ndarray,
    labels: dict[str, int],
    *,
    max_instructions: int | None = None,
    output_handler: Callable[[bytes], None] | None = None,
    pc_mod_counts: list[int] | None = None,
    source_map: dict[int, tuple[str, int]] | None = None,
    instructions_per_second: float | None = INSTRUCTIONS_PER_SECOND,
) -> int:
    """Emulate a subleq computer on a bank of data."""
    count = 0
    timing_started = time.perf_counter()

    def pace(*, force: bool = False) -> None:
        """Limit average emulation speed without relying on microsecond sleeps."""
        if instructions_per_second is None or instructions_per_second <= 0:
            return
        if not force and count % TIMING_BATCH_SIZE:
            return
        remaining = count / instructions_per_second - (
            time.perf_counter() - timing_started
        )
        if remaining > 0:
            time.sleep(remaining)
    if pc_mod_counts is None:
        pc_mod_counts = [0, 0, 0]
    elif len(pc_mod_counts) != 3:
        raise ValueError("pc_mod_counts must contain exactly three counters")

    # reverse the dictionary
    rlabels = {}
    for label, addr in labels.items():
        if addr in rlabels:
            rlabels[addr] += " " + label
            continue
        rlabels[addr] = label

    pc = np.uint16(0)
    previous_instruction = None
    # Keep a small machine-level traceback even without --debug. Runtime faults
    # need to explain the emulated program's path, not merely expose a Python
    # exception from the emulator implementation.
    trace = deque(maxlen=32)
    while True:
        if max_instructions is not None and count >= max_instructions:
            raise ExecutionLimitError(
                f"program did not halt within {max_instructions} instructions"
            )
        pc_mod_counts[int(pc) % 3] += 1
        if int(pc) % 3:
            report_misaligned_pc(pc, data, rlabels, previous_instruction)
            if trace is not None:
                report_execution_trace(trace, rlabels, source_map)
        count += 1
        if int(pc) + 2 >= len(data):
            execution_fault(
                f"cannot fetch three-word instruction at PC={int(pc)} "
                f"(memory contains {len(data)} words)",
                trace,
                rlabels,
                source_map,
            )
        a, b, c = (
            data[pc],
            data[pc + 1],
            data[pc + 2],
        )
        invalid_addresses = [int(address) for address in (a, b) if address >= len(data)]
        if invalid_addresses:
            execution_fault(
                f"instruction at PC={int(pc)} references memory outside "
                f"0..{len(data) - 1}: {invalid_addresses}",
                trace,
                rlabels,
                source_map,
            )
        debug_instruction(pc, data, rlabels)

        da, db = data[a], data[b]

        if a == const.IO_ADDR:
            da = (-eval(input())) % (1 << 16)  # noqa: S307

        if b == const.IO_ADDR:
            output_value = int(da)
            if not 0 <= output_value <= 0xFF:
                location = (source_map or {}).get(int(pc))
                source_text = (
                    f" [{location[0]}:{location[1]}]" if location else ""
                )
                source_label = rlabels.get(int(a))
                source_description = (
                    f"address {int(a)} ({source_label})"
                    if source_label
                    else f"address {int(a)}"
                )
                execution_fault(
                    f"instruction at PC={int(pc)}{source_text} attempted character "
                    f"output of {output_value} "
                    f"({int(np.int16(da))} signed, 0x{output_value:04X}) from "
                    f"{source_description}; expected a byte in 0..255",
                    trace,
                    rlabels,
                    source_map,
                )
            emitted = bytes([output_value])
            if output_handler is None:
                os.write(1, emitted)
            else:
                output_handler(emitted)

        elif b == const.INSPECT_ADDR:
            print(f" < {da:5d}, {np.uint16(da):6x}, {np.uint16(da):16b}")

        else:
            with np.errstate(over="ignore"):
                db = db - da
            data[b] = db

        signed_result = int(db.astype(np.int16))
        if signed_result <= 0:
            if c == const.HALT_ADDR:
                debug("HALT")
                pace(force=True)
                return count
            previous_instruction = (
                int(pc), int(a), int(b), int(c), signed_result, "branch taken"
            )
            if trace is not None:
                trace.append(previous_instruction)
            pc = c
            pace()
            continue
        previous_instruction = (
            int(pc), int(a), int(b), int(c), signed_result, "fall-through (+3)"
        )
        if trace is not None:
            trace.append(previous_instruction)
        pc += 3
        pace()


def add_debug_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared emulator debug option."""
    parser.add_argument(
        "-g",
        dest="debug",
        action="store_true",
        help="Enable debug mode",
    )


def configure_source_parser(parser: argparse.ArgumentParser) -> None:
    """Add arguments for compiling and running assembly source."""
    parser.add_argument(
        "input",
        type=Path,
        nargs="+",
        help="Input source files, linked in the order given",
    )
    add_debug_argument(parser)
    parser.set_defaults(command_handler=execute_sources)


def configure_image_parser(parser: argparse.ArgumentParser) -> None:
    """Add arguments for running an existing NumPy image."""
    parser.add_argument("input", type=Path, help="Input NumPy image")
    parser.add_argument(
        "-l",
        "--labels",
        action="store_true",
        help="Load the matching labels file",
        dest="labels",
    )
    add_debug_argument(parser)
    parser.set_defaults(command_handler=execute_image)


def execute_data(
    data: np.ndarray,
    labels: dict[str, int],
    *,
    debug_enabled: bool,
    display_name: str,
    source_map: dict[int, tuple[str, int]] | None = None,
) -> None:
    """Run compiled memory and print an execution summary."""
    global DEBUG  # noqa: PLW0603
    DEBUG = debug_enabled

    t = time.time()
    pc_mod_counts = [0, 0, 0]
    print("---------------------------------", flush=True)
    try:
        count = subleq(
            data, labels, pc_mod_counts=pc_mod_counts, source_map=source_map
        )
    except KeyboardInterrupt:
        print("\n---------------------------------")
        print(f"{display_name} interrupted by user")
        return
    except EOFError:
        print("\n---------------------------------")
        print(f"{display_name} stopped because input was closed")
        return
    except ExecutionFaultError as error:
        print("\n---------------------------------")
        print(f"{display_name} stopped: {error}")
        return
    finally:
        print(
            "PC modulo 3 counts: "
            + ", ".join(
                f"PC % 3 == {remainder}: {value}"
                for remainder, value in enumerate(pc_mod_counts)
            )
        )
    print("\n---------------------------------")
    print(
        f"{display_name} halted in {count} instructions, "
        f"{time.time() - t:.3f} seconds"
    )


def execute_sources(args: argparse.Namespace) -> None:
    """Compile linked assembly sources in memory and run them."""
    data, labels, source_map = subleq_compile_files_with_source_map(
        args.input,
        warning_handler=print_compile_warning,
    )
    execute_data(
        data,
        labels,
        debug_enabled=args.debug,
        display_name=", ".join(str(path) for path in args.input),
        source_map=source_map,
    )


def execute_image(args: argparse.Namespace) -> None:
    """Load and run an existing NumPy image."""
    data = np.load(args.input)
    labels = {}
    if args.labels:
        with args.input.with_suffix(".labels").open("r") as fp:
            labels = json.load(fp)
    execute_data(
        data,
        labels,
        debug_enabled=args.debug,
        display_name=str(args.input),
    )


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Add standalone emulator arguments for backward compatibility."""
    configure_image_parser(parser)


def execute(args: argparse.Namespace) -> None:
    """Run an image for backward-compatible module callers."""
    execute_image(args)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the standalone emulator entry point."""
    parser = argparse.ArgumentParser(description="SUBLEQ emulator")
    configure_parser(parser)
    execute(parser.parse_args(argv))


if __name__ == "__main__":
    main()
