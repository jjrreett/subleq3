# noqa: INP001
"""Emulates a subleq computer from an np.ndarray based image."""

import argparse

# from rich import print  # noqa: A004
import json
from functools import wraps
from pathlib import Path

import numpy as np
import sys
import os
import time

from . import const

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
            da = (-eval(input("> "))) % (1 << 16)  # noqa: S307

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


def main() -> None:
    """Entrypoint."""
    parser = argparse.ArgumentParser(description="Subleq")
    parser.add_argument("input", type=Path, help="Input source file")
    parser.add_argument(
        "-l",
        "--labels",
        action="store_true",
        help="Input labels file",
        dest="labels",
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

    data = np.load(args.input)

    labels = {}
    if args.labels:
        with args.input.with_suffix(".labels").open("r") as fp:
            labels = json.load(fp)

    t = time.time()
    print("---------------------------------")
    count = subleq(data, labels)
    print("\n---------------------------------")
    print(f"{args.input} halted in {count} instructions, {time.time() - t:.3f} seconds")


if __name__ == "__main__":
    main()
