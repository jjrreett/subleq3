"""Source-linker and packaged-standard-library tests."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from subleq import run
from subleq.compile import CompilationError, subleq_compile_files
from subleq.link import LinkError, link_sources


class SourceLinkerTests(unittest.TestCase):
    """Project modules should compose into one global address space."""

    def test_relative_include_exports_macros_and_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "library.s").write_text(
                ".macro emit value\n    .word value\n.endm\n"
                "library_value: .word target\n"
            )
            main = root / "main.s"
            main.write_text(
                '.include "library.s"\ntarget: .word 7\nentry: emit library_value\n'
            )

            data, labels = subleq_compile_files([main])

            np.testing.assert_array_equal(data, np.array([1, 7, 0], dtype=np.uint16))
            self.assertEqual(labels, {"library_value": 0, "target": 1, "entry": 2})

    def test_multiple_inputs_link_in_command_line_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.s"
            second = root / "second.s"
            first.write_text("first: .word second\n")
            second.write_text("second: .word first\n")

            data, labels = subleq_compile_files([first, second])

            np.testing.assert_array_equal(data, np.array([1, 0], dtype=np.uint16))
            self.assertEqual(labels, {"first": 0, "second": 1})

    def test_nested_relative_includes_use_the_including_file_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            modules = root / "modules"
            modules.mkdir()
            (root / "value.s").write_text("value: .word 12\n")
            (modules / "middle.s").write_text('.include "../value.s"\n')
            main = root / "main.s"
            main.write_text('.include "modules/middle.s"\n.word value\n')

            data, _ = subleq_compile_files([main])

            np.testing.assert_array_equal(data, np.array([12, 0], dtype=np.uint16))

    def test_include_cycle_reports_the_dependency_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.s"
            second = root / "second.s"
            first.write_text('.include "second.s"\n')
            second.write_text('.include "first.s"\n')

            with self.assertRaisesRegex(LinkError, "Include cycle"):
                link_sources([first])

    def test_missing_include_reports_the_including_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / "main.s"
            main.write_text('\n.include "missing.s"\n')

            with self.assertRaisesRegex(LinkError, r"main\.s:2: Source file not found"):
                link_sources([main])

    def test_duplicate_macro_across_modules_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.s"
            second = root / "second.s"
            macro = ".macro stop\n    subleq 0, 0, 0\n.endm\n"
            first.write_text(macro)
            second.write_text(macro)

            with self.assertRaisesRegex(
                CompilationError, "Macro 'stop' is defined twice"
            ):
                subleq_compile_files([first, second])


class StandardLibraryTests(unittest.TestCase):
    """The packaged core library should provide usable, zero-cost macros."""

    def test_core_macros_compile_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / "main.s"
            main.write_text(
                """\
.include <core.s>
start:
    clr result
    add input, result
    jmp halt
halt:
    subleq z, z, 0
z:      .word 0
p1:     .word 1
m1:     .word -1
input:  .word 7
result: .word 99
"""
            )

            data, labels = subleq_compile_files([main])
            memory = data.copy()
            previous_debug = run.DEBUG
            run.DEBUG = False
            try:
                instruction_count = run.subleq(memory, labels)
            finally:
                run.DEBUG = previous_debug

            self.assertEqual(memory[labels["result"]], 7)
            self.assertEqual(memory[labels["z"]], 0)
            self.assertEqual(instruction_count, 6)

    def test_subroutine_calling_convention_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / "main.s"
            main.write_text(
                """\
.include <subroutine.s>
jmp main

double:
    rts
    pop argument
    dbl argument
    psh argument
    jmp double

main:
    psh input
    jsr double
    pop output
    jmp halt
halt:
    subleq z, z, 0

z:         .word 0
p1:        .word 1
m1:        .word -1
input:     .word 21
output:    .word 0
argument:  .word 0
stack:     .res 16
stack_ptr: .word stack
"""
            )

            data, labels = subleq_compile_files([main])
            memory = data.copy()
            previous_debug = run.DEBUG
            run.DEBUG = False
            try:
                run.subleq(memory, labels)
            finally:
                run.DEBUG = previous_debug

            self.assertEqual(memory[labels["output"]], 42)
            self.assertEqual(memory[labels["stack_ptr"]], labels["stack"])

    def test_standard_modules_are_imported_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / "main.s"
            main.write_text(
                ".include <core.s>\n"
                ".include <subroutine.s>\n"
                ".include <memory.s>\n"
                ".include <io.s>\n"
                ".include <math.s>\n"
                ".literals\n"
                ".word 0\n"
            )

            data, _ = subleq_compile_files([main])

            np.testing.assert_array_equal(data, np.array([0], dtype=np.uint16))


if __name__ == "__main__":
    unittest.main()
