"""Compiler behavior tests."""

import unittest
import tempfile
import time
from pathlib import Path
from unittest import mock

import numpy as np

from subleq import run
from subleq.compile import (
    CompilationError,
    macro_tradeoffs,
    subleq_compile,
    subleq_compile_files_with_source_map,
)


class SourceMapTests(unittest.TestCase):
    def test_included_macro_invocation_maps_to_calling_file_and_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lib.s").write_text(
                ".macro jump target\n    subleq 0, 0, target\n.endm\n"
            )
            main = root / "main.s"
            main.write_text(
                '.include "lib.s"\nmain:\n    jump done\ndone:\n    subleq 0, 0, 0\n'
            )

            _, _, source_map = subleq_compile_files_with_source_map([main])

            self.assertEqual(source_map[0], (str(main), 3))
            self.assertEqual(source_map[3], (str(main), 5))


class EmulatorTimingTests(unittest.TestCase):
    def test_emulator_limits_instruction_rate(self) -> None:
        data = np.zeros(30, dtype=np.uint16)
        for pc in range(0, 27, 3):
            data[pc + 2] = pc + 3

        started = time.perf_counter()
        count = run.subleq(data, {}, instructions_per_second=1_000)
        elapsed = time.perf_counter() - started

        self.assertEqual(count, 10)
        self.assertGreaterEqual(elapsed, 0.009)


class MacroDeclarationSyntaxTests(unittest.TestCase):
    def test_name_is_separated_from_arguments_by_whitespace(self) -> None:
        source = """\
.macro stop target
    subleq target, target, target
.endm
main:
    stop main
"""

        data, labels = subleq_compile(source)

        self.assertEqual(data.tolist(), [0, 0, 0])
        self.assertEqual(labels, {"main": 0})

    def test_comma_after_name_remains_compatible(self) -> None:
        source = """\
.macro stop, target
    subleq target, target, target
.endm
main:
    stop main
"""

        data, _ = subleq_compile(source)

        self.assertEqual(data.tolist(), [0, 0, 0])


class LocalLabelTests(unittest.TestCase):
    """Scoped labels should resolve without leaking between scopes or calls."""

    def assert_compiles_to(self, source: str, expected: list[int]) -> None:
        data, _ = subleq_compile(source)
        np.testing.assert_array_equal(data, np.array(expected, dtype=np.uint16))

    def test_same_local_name_in_different_global_scopes(self) -> None:
        source = """\
first:
@loop:
    subleq @loop, @loop, @loop
second:
@loop:
    subleq @loop, @loop, @loop
"""
        data, labels = subleq_compile(source)

        np.testing.assert_array_equal(
            data, np.array([0, 0, 0, 3, 3, 3], dtype=np.uint16)
        )
        self.assertEqual(labels, {"first": 0, "second": 3})

    def test_local_reference_can_be_forward_or_backward(self) -> None:
        source = """\
function:
    subleq @later, @earlier, @later
@earlier:
    .word 0
@later:
    .word 0
"""
        self.assert_compiles_to(source, [4, 3, 4, 0, 0])

    def test_repeated_macro_calls_get_private_labels(self) -> None:
        source = """\
.macro spin
@loop:
    subleq @loop, @loop, @done
@done:
    .word 0
.endm

root:
    spin
    spin
"""
        self.assert_compiles_to(source, [0, 0, 3, 0, 4, 4, 7, 0])

    def test_macro_argument_can_reference_callers_local_label(self) -> None:
        source = """\
.macro branch target
    subleq zero, zero, target
.endm

zero: .word 0
root:
    branch @done
@done:
    .word 0
"""
        self.assert_compiles_to(source, [0, 0, 0, 4, 0])

    def test_nested_macro_labels_stay_in_outer_call_scope(self) -> None:
        source = """\
.macro inner flag, target
@again:
    subleq flag, flag, target
.endm

.macro outer
    inner @flag, @done
@flag:
    .word 0
@done:
    .word 0
.endm

root:
    outer
    outer
"""
        self.assert_compiles_to(source, [3, 3, 4, 0, 0, 8, 8, 9, 0, 0])

    def test_word_accepts_symbols_local_labels_next_and_macro_arguments(self) -> None:
        source = """\
.macro emit_pointer target
@slot: .word target
.endm

target: .word 0
root:
    emit_pointer target
    emit_pointer @end
@end: .word @end
    .word ?
"""
        self.assert_compiles_to(source, [0, 0, 3, 3, 5])

    def test_string_directives_decode_escapes(self) -> None:
        source = '.ascii "A\\n\\t\\"\\\\"\n.asciiz "B\\r\\0"\n'

        self.assert_compiles_to(
            source,
            [ord("A"), 10, 9, ord('"'), ord("\\"), ord("B"), 13, 0, 0],
        )

    def test_char_directive_emits_character_code_point(self) -> None:
        self.assert_compiles_to(
            ".char 'A'\n.char '\\n'\n.char '\\''\n",
            [ord("A"), 10, ord("'")],
        )

    def test_character_immediate_is_hoisted_and_deduplicated(self) -> None:
        source = """\
.literals 2
subleq 'A, '\\n, ?
subleq 'A, '\\n, ?
"""

        self.assert_compiles_to(source, [65, 10, 0, 1, 5, 0, 1, 8])

    def test_string_directives_preserve_spaces_and_tabs(self) -> None:
        self.assert_compiles_to(
            '.ascii "Hello world\t!"\n',
            [*map(ord, "Hello world\t!")],
        )

    def test_literal_pool_hoists_and_deduplicates_immediate_values(self) -> None:
        source = """\
.macro subtract source, destination
    subleq source, destination, ?
.endm

start:
    subtract #7, target
    subtract #$0007, target
    subleq zero, zero, done
done:
    subleq zero, zero, 0
.literals 1
target: .word 0
zero: .word 0
"""

        self.assert_compiles_to(
            source,
            [12, 13, 3, 12, 13, 6, 14, 14, 9, 14, 14, 0, 7, 0, 0],
        )

    def test_immediate_literal_requires_a_pool(self) -> None:
        with self.assertRaisesRegex(
            CompilationError, "Immediate literals require a .literals count directive"
        ):
            subleq_compile("subleq #1, 0, 0\n")

    def test_literal_pool_deduplicates_equivalent_16_bit_values(self) -> None:
        self.assert_compiles_to(
            "subleq #-1, #$ffff, 0\n.literals 1\n",
            [3, 3, 0, 0xFFFF],
        )

    def test_literal_pool_reserves_its_declared_capacity(self) -> None:
        self.assert_compiles_to(
            "subleq #7, #7, 0\n.literals 3\n",
            [3, 3, 0, 7, 0, 0],
        )

    def test_literal_pool_rejects_insufficient_capacity(self) -> None:
        with self.assertRaisesRegex(
            CompilationError, "reserves 1 words, but 2 unique literals are required"
        ):
            subleq_compile("subleq #1, #2, 0\n.literals 1\n")

    def test_literal_pool_rejects_negative_capacity(self) -> None:
        with self.assertRaisesRegex(CompilationError, "capacity cannot be negative"):
            subleq_compile(".literals -1\n")

    def test_literal_pool_requires_a_capacity(self) -> None:
        with self.assertRaises(CompilationError):
            subleq_compile(".literals\n")

    def test_literal_pool_may_appear_only_once(self) -> None:
        with self.assertRaisesRegex(
            CompilationError, "The .literals directive may appear only once"
        ):
            subleq_compile(".literals 0\n.literals 0\n")

    def test_undefined_local_label_has_clear_error(self) -> None:
        with self.assertRaisesRegex(
            CompilationError,
            "Local label '@missing' is not defined in scope 'root'",
        ):
            subleq_compile("root:\nsubleq @missing, 0, 0\n")

    def test_duplicate_local_label_is_rejected_within_scope(self) -> None:
        source = """\
root:
@same:
@same:
    .word 0
"""
        with self.assertRaisesRegex(CompilationError, "defined twice"):
            subleq_compile(source)

    def test_compiled_local_label_program_runs(self) -> None:
        source = """\
start:
    subleq zero, zero, @halt
@halt:
    subleq zero, zero, 0
zero:
    .word 0
"""
        data, labels = subleq_compile(source)
        previous_debug = run.DEBUG
        run.DEBUG = False
        try:
            instruction_count = run.subleq(data.copy(), labels)
        finally:
            run.DEBUG = previous_debug

        self.assertEqual(instruction_count, 2)

    def test_bootstrap_defines_entrypoint_and_device_cells(self) -> None:
        source = """\
.bootstrap
main:
    subleq z, z, 0
z: .word 0
"""

        data, labels = subleq_compile(source)

        self.assertEqual(labels["IO"], 3)
        self.assertEqual(labels["INSPECT"], 4)
        self.assertEqual(labels["main"], 6)
        self.assertEqual(data.tolist(), [5, 5, 6, 0, 0, 0, 9, 9, 0, 0])

    def test_bootstrap_must_be_first_emitted_construct(self) -> None:
        with self.assertRaisesRegex(CompilationError, "must emit at address 0"):
            subleq_compile(
                ".word 0\n.bootstrap\nmain: .word 0\nz: .word 0\n"
            )

    def test_bootstrap_requires_main(self) -> None:
        with self.assertRaisesRegex(CompilationError, "Global label 'main'"):
            subleq_compile(".bootstrap\nz: .word 0\n")


class RuntimeInputTests(unittest.TestCase):
    def test_io_read_does_not_add_a_host_prompt(self) -> None:
        data = np.array([3, 5, 0, 0, 0, 0], dtype=np.uint16)

        previous_debug = run.DEBUG
        run.DEBUG = False
        try:
            with mock.patch("builtins.input", return_value="-7") as read_input:
                instruction_count = run.subleq(data, {})
        finally:
            run.DEBUG = previous_debug

        read_input.assert_called_once_with()
        self.assertEqual(instruction_count, 1)


class MacroTradeoffTests(unittest.TestCase):
    def test_repeated_large_macro_reports_space_and_cycle_tradeoff(self) -> None:
        body = "".join("    subleq z, z, ?\n" for _ in range(20))
        source = f"""\
.macro psh value
    subleq z, z, ?
.endm
.macro pop value
    subleq z, z, ?
.endm
.macro jsr target
    subleq z, z, ?
.endm
.macro rts
    subleq z, z, ?
.endm
.macro large
{body}.endm

start:
    large
    large
z: .word 0
"""

        warnings: list[str] = []
        subleq_compile(source, warning_handler=warnings.append)
        tradeoffs = macro_tradeoffs(source)

        self.assertEqual(len(tradeoffs), 1)
        self.assertEqual(tradeoffs[0].macro, "large")
        self.assertEqual(tradeoffs[0].saved_instructions, 16)
        self.assertEqual(tradeoffs[0].extra_cycles_per_call, 3)
        self.assertIn("saving about 16 instructions (48 words)", warnings[0])
        self.assertIn("3 instructions", warnings[0])


if __name__ == "__main__":
    unittest.main()
