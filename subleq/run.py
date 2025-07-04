import numpy as np

from rich import print
from functools import wraps

import argparse
from pathlib import Path

DEBUG = True


@wraps(print)
def debug(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


IO_ADDR = 0x03
HALT_ADDR = 0x00


def print_data(data):
    for i, x in enumerate(data):
        print(f"{i:x}: {x:x}")


def subleq(data, pc):
    debug(pc, pc + 1, pc + 2)
    a, b, c = data[pc], data[pc + 1], data[pc + 2].astype(np.uint16)
    debug(a, b, c)

    da = data[a]
    if a == IO_ADDR:
        da = -int(input("> "))
    db = data[b]
    debug(da, db)

    if b == IO_ADDR:
        print("<", da)
    else:
        data[b] -= da
    debug()
    if data[b] <= 0:
        if c == HALT_ADDR:
            debug("HALT")
            return None
        return c
    return pc + 3


def main():
    parser = argparse.ArgumentParser(description="Subleq")
    parser.add_argument("input", type=Path, help="Input source file")
    parser.add_argument(
        "-g", dest="debug", action="store_true", help="Enable debug mode"
    )
    args = parser.parse_args()

    global DEBUG
    DEBUG = args.debug

    data = np.load(args.input)

    pc = 0
    while pc is not None:
        pc = subleq(data, pc)


if __name__ == "__main__":
    main()
