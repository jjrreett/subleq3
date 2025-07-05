# noqa: INP001
"""Emulates a subleq computer from an np.ndarray based image."""

import argparse
from functools import wraps
from pathlib import Path

import numpy as np
# from rich import print  # noqa: A004

DEBUG = True


@wraps(print)
def debug(*args: tuple, **kwargs: dict) -> None:
    """If DEBUG: print."""
    if DEBUG:
        print(*args, **kwargs)


IO_ADDR = 0x03
HALT_ADDR = 0x00


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

    # debug(f"\n[PC={pc:5d}] Executing SUBLEQ {a}, {b}, {c}")
    # debug("-" * 60)
    debug(f"data[{pc:5d}] = {a:5d} -> data[{a:5d}] = {np.uint16(da):6x} : {rlabels.get(a, ''):10s}")
    debug(
        f"data[{pc + 1:5d}] = {b:5d} -> data[{b:5d}] = {np.uint16(db):6x} : {rlabels.get(b, ''):10s} -> {db - da:5d}, {np.uint16(db) - np.uint16(da):6x}"
    )
    debug(f"data[{pc + 2:5d}] = {c:5d}                         : {rlabels.get(c, ''):10s}")
    debug("-" * 50)


def subleq(data: np.ndarray, labels: dict[str, int]) -> None:
    """Emulate a subleq computer on a bank of data."""

    # reverse the dictionary
    rlabels = {}
    for label, addr in labels.items():
        if addr in rlabels:
            rlabels[addr] += " " + label
            continue
        rlabels[addr] = label

    pc = np.uint16(0)
    while True:
        debug_instruction(pc, data, rlabels)
        a, b, c = (
            data[pc],
            data[pc + 1],
            data[pc + 2],
        )

        if a == IO_ADDR:
            data[a] = (-eval(input("> "))) % (1 << 16)  # noqa: S307

        if b == IO_ADDR:
            print(f"< {data[a]:5d}, {np.uint16(data[a]):6x}")
        else:
            post = data[b] - data[a]
            data[b] = post

        if data[b].astype(np.int16) <= 0:
            if c == HALT_ADDR:
                debug("HALT")
                return
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

    import json

    labels = {}
    if args.labels:
        with args.input.with_suffix(".labels").open("r") as fp:
            labels = json.load(fp)

    subleq(data, labels)


if __name__ == "__main__":
    main()
