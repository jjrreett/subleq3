"""Embedded source-test harness behavior."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np

from subleq import cli
from subleq.compile import CompilationError, subleq_compile
from subleq.testing import run_source_tests


PROGRAM = """\
.macro jmp target
    subleq z, z, target
.endm
.macro clr target
    subleq target, target, ?
.endm
.macro sub source, destination
    subleq source, destination, ?
.endm
.macro add source, destination
    sub source, z
    sub z, destination
    clr z
.endm
.macro cpy source, destination
    clr destination
    add source, destination
.endm
jmp start
IO:      .word 0
INSPECT: .word 0
start:
    cpy input, result
    add increment, result
    jmp halt
halt:
    subleq z, z, 0
z:         .word 0
p1:        .word 1
m1:        .word -1
input:     .word 0
increment: .word 1
result:    .word 0
"""


class EmbeddedHarnessTests(unittest.TestCase):
    def write_source(self, source: str, directory: str) -> Path:
        path = Path(directory) / "quick_test.s"
        path.write_text(source)
        return path

    def test_normal_compile_strips_test_fixtures(self) -> None:
        source = PROGRAM + """\
.test "not emitted"
fixture_only: .word 99
    .assert result, 1
.endt
"""

        data, labels = subleq_compile(source)

        self.assertNotIn("fixture_only", labels)
        self.assertEqual(data[labels["result"]], 0)

    def test_cases_set_initial_memory_and_assert_final_memory(self) -> None:
        source = PROGRAM + """\
.test "zero plus one"
    .set input, 0
    .assert result, 1
.endt
.test "forty one plus one"
    .set input, 41
    .assert result, 42
.endt
"""
        with tempfile.TemporaryDirectory() as directory:
            results = run_source_tests([self.write_source(source, directory)])

        self.assertEqual([result.name for result in results], ["zero plus one", "forty one plus one"])
        self.assertTrue(all(result.passed for result in results))

    def test_fixture_can_define_a_complete_program_and_assert_output(self) -> None:
        source = """\
.test "prints A"
    subleq zero, zero, start
IO:        .word 0
INSPECT:   .word 0
start:
    subleq character, IO, halt
halt:
    subleq zero, zero, 0
character: .word 65
zero:      .word 0
    .assert-output "A"
.endt
"""
        with tempfile.TemporaryDirectory() as directory:
            results = run_source_tests([self.write_source(source, directory)])

        self.assertTrue(results[0].passed, results[0].failures)

    def test_failed_assertion_and_instruction_limit_are_reported(self) -> None:
        failing = PROGRAM + """\
.test wrong
    .assert result, 2
.endt
"""
        looping = """\
.test loop
    subleq zero, zero, start
IO:      .word 0
INSPECT: .word 0
start:   subleq zero, zero, start
zero:    .word 0
.endt
"""
        with tempfile.TemporaryDirectory() as directory:
            failure = run_source_tests([self.write_source(failing, directory)])[0]
            loop_path = Path(directory) / "loop.s"
            loop_path.write_text(looping)
            loop = run_source_tests([loop_path], max_instructions=5)[0]

        self.assertFalse(failure.passed)
        self.assertIn("expected 2", failure.failures[0])
        self.assertFalse(loop.passed)
        self.assertIn("within 5 instructions", loop.failures[0])

    def test_malformed_harness_is_a_compilation_error(self) -> None:
        with self.assertRaisesRegex(CompilationError, "missing .endt"):
            subleq_compile('.test "unfinished"\n.word 0\n')

    def test_cli_test_command_reports_results(self) -> None:
        source = PROGRAM + """\
.test smoke
    .assert result, 1
.endt
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_source(source, directory)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                cli.main(["test", str(path)])

        self.assertIn("PASS smoke", output.getvalue())
        self.assertIn("1/1 tests passed", output.getvalue())

    def test_production_image_is_unchanged_by_tests(self) -> None:
        plain, _ = subleq_compile(PROGRAM)
        tested, _ = subleq_compile(
            PROGRAM + '.test same\n    .set input, 7\n    .assert result, 8\n.endt\n'
        )

        np.testing.assert_array_equal(tested, plain)


if __name__ == "__main__":
    unittest.main()
