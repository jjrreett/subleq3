"""Tests for editor-oriented SUBLEQ source analysis."""

import unittest
from pathlib import Path

from subleq.analysis import DocumentAnalysis
from subleq.lsp import included_symbols, index_to_utf16, utf16_to_index

SOURCE = """\
; Add source to destination.
.macro add source, destination
    subleq source, zero, ?
    subleq zero, destination, ?
    subleq zero, zero, ?
.endm

; Invoke another macro twice.
.macro add_twice source, destination
@again:
    add source, destination
    add source, destination
.endm

zero: .word 0
main:
    add_twice zero, @result
@result: .word 0
"""


class AnalysisTests(unittest.TestCase):
    """The editor model should mirror compiler label and macro semantics."""

    def setUp(self) -> None:
        self.analysis = DocumentAnalysis.parse(SOURCE)

    def test_macro_instruction_counts_are_recursive(self) -> None:
        self.assertEqual(self.analysis.macros["add"].instruction_count, 3)
        self.assertEqual(self.analysis.macros["add_twice"].instruction_count, 6)

        hints = self.analysis.inlay_hints()
        invocation_hint = next(hint for hint in hints if hint.line == 16)
        self.assertEqual(invocation_hint.label, ": 6 instructions")

    def test_hover_uses_preceding_comments_and_instruction_count(self) -> None:
        hover = self.analysis.hover_at(16, 6)

        self.assertIsNotNone(hover)
        assert hover is not None
        self.assertIn("add_twice source, destination", hover.markdown)
        self.assertIn("Invoke another macro twice.", hover.markdown)
        self.assertIn("6 SUBLEQ instructions", hover.markdown)

    def test_hover_preserves_comment_lines_and_blank_paragraphs(self) -> None:
        analysis = DocumentAnalysis.parse(
            "; First line.\n"
            "; Second line.\n"
            ";\n"
            ";     indented detail\n"
            ".macro documented value\n"
            "    subleq value, value, ?\n"
            ".endm\n"
        )

        hover = analysis.hover_at(4, 8)

        self.assertIsNotNone(hover)
        assert hover is not None
        self.assertIn("First line.  \nSecond line.", hover.markdown)
        self.assertIn("Second line.\n\n    indented detail", hover.markdown)

    def test_legacy_macro_declaration_is_still_understood(self) -> None:
        analysis = DocumentAnalysis.parse(
            ".macro legacy, source, destination\n"
            "    subleq source, destination, ?\n"
            ".endm\n"
        )

        self.assertEqual(
            analysis.macros["legacy"].parameters,
            ("source", "destination"),
        )

    def test_go_to_macro_and_local_label_definitions(self) -> None:
        macro = self.analysis.definition_at(16, 6)
        local = self.analysis.definition_at(16, 22)

        self.assertIsNotNone(macro)
        self.assertIsNotNone(local)
        assert macro is not None and local is not None
        self.assertEqual(macro.span.line, 8)
        self.assertEqual(local.span.line, 17)

    def test_data_values_are_not_treated_as_opcodes(self) -> None:
        analysis = DocumentAnalysis.parse(
            ".data\n    destination\n    @target\n.endd\n"
        )

        self.assertEqual(analysis.invocations, [])
        self.assertEqual(analysis.diagnostics, [])

    def test_literal_pool_directive_has_hover_documentation(self) -> None:
        analysis = DocumentAnalysis.parse(".literals\n")

        hover = analysis.hover_at(0, 2)

        self.assertIsNotNone(hover)
        assert hover is not None
        self.assertIn("#number", hover.markdown)

    def test_bad_invocation_reports_diagnostic(self) -> None:
        analysis = DocumentAnalysis.parse("main:\n    missing 1\n")

        self.assertEqual(len(analysis.diagnostics), 1)
        self.assertIn("Unknown opcode or macro", analysis.diagnostics[0].message)

    def test_embedded_test_fixtures_do_not_pollute_production_symbols(self) -> None:
        analysis = DocumentAnalysis.parse(
            """\
main: .word 0
.test "first"
fixture: .word 1
.endt
.test "second"
fixture: .word 2
.endt
"""
        )

        self.assertEqual(analysis.diagnostics, [])
        self.assertEqual(set(analysis.global_labels), {"main"})
        hover = analysis.hover_at(1, 2)
        self.assertIsNotNone(hover)
        assert hover is not None
        self.assertIn("embedded source test", hover.markdown)

    def test_recursive_macro_has_no_misleading_size(self) -> None:
        analysis = DocumentAnalysis.parse(
            ".macro forever\n    forever\n.endm\nmain:\n    forever\n"
        )

        self.assertIsNone(analysis.macros["forever"].instruction_count)
        self.assertEqual(analysis.inlay_hints(), [])
        self.assertTrue(
            any(diagnostic.severity == "warning" for diagnostic in analysis.diagnostics)
        )

    def test_utf16_position_conversion(self) -> None:
        line = "😀 add"

        self.assertEqual(index_to_utf16(line, 2), 3)
        self.assertEqual(utf16_to_index(line, 3), 2)

    def test_standard_library_include_supplies_editor_metadata(self) -> None:
        source = ".include <core.s>\nmain:\n    add input, total\n"
        macros, labels = included_symbols(source, Path.cwd(), set())

        analysis = DocumentAnalysis.parse(
            source,
            uri=(Path.cwd() / "main.s").as_uri(),
            external_macros=macros,
            external_global_labels=labels,
        )

        self.assertEqual(analysis.diagnostics, [])
        self.assertEqual(analysis.inlay_hints()[0].label, ": 3 instructions")
        definition = analysis.definition_at(2, 6)
        self.assertIsNotNone(definition)
        assert definition is not None
        self.assertEqual(definition.name, "add")
        self.assertTrue(definition.uri and definition.uri.endswith("/core.s"))

        expected_counts = {
            "jmp": 1,
            "clr": 1,
            "sub": 1,
            "add": 3,
            "cpy": 4,
            "dec": 1,
            "inc": 1,
            "dbl": 3,
            "bleq": 1,
            "bgt": 2,
            "beq": 9,
            "bne": 10,
            "bpl": 11,
            "bmi": 10,
        }
        self.assertEqual(
            {name: macros[name].instruction_count for name in expected_counts},
            expected_counts,
        )

    def test_pointer_macro_hovers_explain_destructive_difference(self) -> None:
        source = (
            ".include <subroutine.s>\n"
            "main:\n"
            "    rpt pointer, destination\n"
            "    read_word pointer, destination\n"
        )
        macros, labels = included_symbols(source, Path.cwd(), set())
        analysis = DocumentAnalysis.parse(
            source,
            external_macros=macros,
            external_global_labels=labels,
        )

        rpt_hover = analysis.hover_at(2, 6)
        read_hover = analysis.hover_at(3, 8)

        self.assertIsNotNone(rpt_hover)
        self.assertIsNotNone(read_hover)
        assert rpt_hover is not None and read_hover is not None
        self.assertIn("destructive", rpt_hover.markdown)
        self.assertIn("read_word", rpt_hover.markdown)
        self.assertIn("non-destructive", read_hover.markdown)
        self.assertIn("`rpt`", read_hover.markdown)
        self.assertEqual(read_hover.markdown.count("read_word pointer, destination"), 1)


if __name__ == "__main__":
    unittest.main()
