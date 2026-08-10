# noqa: INP001
"""Compile or load programs and execute them in the SUBLEQ emulator."""

import argparse
import json
import os
import sys
import time
from collections.abc import Sequence
from functools import wraps
from pathlib import Path

import numpy as np

from . import const
from .compile import subleq_compile_files

DEBUG = True


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


def subleq(data: np.ndarray, labels: dict[str, int]) -> int:
    """Emulate a subleq computer on a bank of data."""
    count = 0

    # reverse the dictionary
    rlabels = {}
    for label, addr in labels.items():
        if addr in rlabels:
            rlabels[addr] += " " + label
            continue
        rlabels[addr] = label

    pc = np.uint16(0)
    while True:
        count += 1
        debug_instruction(pc, data, rlabels)
        a, b, c = (
            data[pc],
            data[pc + 1],
            data[pc + 2],
        )

        da, db = data[a], data[b]

        if a == const.IO_ADDR:
            da = (-eval(input())) % (1 << 16)  # noqa: S307

        if b == const.IO_ADDR:
            os.write(1, bytes([da]))

        elif b == const.INSPECT_ADDR:
            print(f" < {da:5d}, {np.uint16(da):6x}, {np.uint16(da):16b}")

        else:
            with np.errstate(over="ignore"):
                db = db - da
            data[b] = db

        if db.astype(np.int16) <= 0:
            if c == const.HALT_ADDR:
                debug("HALT")
                return count
            pc = c
            continue
        pc += 3


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
) -> None:
    """Run compiled memory and print an execution summary."""
    global DEBUG  # noqa: PLW0603
    DEBUG = debug_enabled

    t = time.time()
    print("---------------------------------", flush=True)
    try:
        count = subleq(data, labels)
    except KeyboardInterrupt:
        print("\n---------------------------------")
        print(f"{display_name} interrupted by user")
        return
    except EOFError:
        print("\n---------------------------------")
        print(f"{display_name} stopped because input was closed")
        return
    print("\n---------------------------------")
    print(
        f"{display_name} halted in {count} instructions, "
        f"{time.time() - t:.3f} seconds"
    )


def execute_sources(args: argparse.Namespace) -> None:
    """Compile linked assembly sources in memory and run them."""
    data, labels = subleq_compile_files(args.input)
    execute_data(
        data,
        labels,
        debug_enabled=args.debug,
        display_name=", ".join(str(path) for path in args.input),
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
