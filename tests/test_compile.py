"""Compiler behavior tests."""

import unittest

import numpy as np

from subleq import run
from subleq.compile import CompilationError, subleq_compile


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
.macro branch, target
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
.macro inner, flag, target
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
.macro emit_pointer, target
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


if __name__ == "__main__":
    unittest.main()
