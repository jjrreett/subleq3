"""Assembly source formatter behavior."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from subleq import cli
from subleq.formatter import format_source


class SourceFormatterTests(unittest.TestCase):
    def test_labels_instructions_and_comments_are_aligned(self) -> None:
        source = """\
main:
 @loop:
subleq one, counter, @done ; decrement
 @done:
subleq zero, zero, 0
"""

        formatted = format_source(source)

        self.assertEqual(
            formatted,
            """\
main:
    @loop:
        subleq one, counter, @done                    ; decrement
    @done:
        subleq zero, zero, 0
""",
        )
        comment_line = formatted.splitlines()[2]
        self.assertEqual(comment_line.index(";"), 54)

    def test_macro_and_data_bodies_gain_one_level(self) -> None:
        source = """\
.macro example value
subleq value, value, @done
@done:
.data
@scratch: 0
.endd
.endm
"""

        self.assertEqual(
            format_source(source),
            """\
.macro example value
    subleq value, value, @done
    @done:
        .data
            @scratch: 0
        .endd
.endm
""",
        )

    def test_formatting_is_idempotent(self) -> None:
        source = "main:\n    @loop:\n        subleq z, z, @loop\n"

        self.assertEqual(format_source(format_source(source)), format_source(source))

    def test_full_comments_and_top_level_directives_stay_at_column_one(self) -> None:
        source = ";   documented cell\nvalue: .word 0\n  .literals 1\n"

        self.assertEqual(
            format_source(source),
            ";   documented cell\nvalue: .word 0\n.literals 1\n",
        )

    def test_cli_formats_in_place_and_check_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.s"
            path.write_text("main:\nsubleq z,z,0\n")
            with (
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                cli.main(["fmt", "--check", str(path)])
            self.assertEqual(raised.exception.code, 1)

            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["fmt", str(path)])
                cli.main(["fmt", "--check", str(path)])

            self.assertEqual(path.read_text(), "main:\n    subleq z,z,0\n")


if __name__ == "__main__":
    unittest.main()
