"""Tests for the unified SUBLEQ command-line interface."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from rich.console import Console

from subleq import cli, run
from subleq.compile import subleq_compile_files


class CommandLineTests(unittest.TestCase):
    """Each tool should be available through one top-level command."""

    def test_help_lists_all_subcommands(self) -> None:
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            cli.main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        for command in (
            "compile",
            "run",
            "test",
            "fmt",
            "emulate",
            "gen-grammar",
            "gen-syntax",
            "lsp",
        ):
            self.assertIn(command, output.getvalue())

    def test_compile_and_emulate_subcommands(self) -> None:
        source = """\
start:
    subleq value, value, 0
IO: .word 0
INSPECT: .word 0
value: .word 0
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "halt.s"
            image_path = root / "halt.npy"
            source_path.write_text(source)

            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["compile", str(source_path), "-o", str(image_path)])
                cli.main(["emulate", str(image_path)])

            self.assertTrue(image_path.exists())
            np.testing.assert_array_equal(
                np.load(image_path), np.array([5, 5, 0, 0, 0, 0], dtype=np.uint16)
            )

    def test_run_compiles_source_without_writing_an_image(self) -> None:
        source = """\
start:
    subleq value, value, 0
IO: .word 0
INSPECT: .word 0
value: .word 0
"""
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "halt.s"
            source_path.write_text(source)

            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["run", str(source_path)])

            self.assertFalse(source_path.with_suffix(".npy").exists())

    def test_emulator_stops_cleanly_when_input_is_interrupted(self) -> None:
        for error, message in (
            (KeyboardInterrupt(), "interrupted by user"),
            (EOFError(), "input was closed"),
        ):
            with (
                self.subTest(error=type(error).__name__),
                mock.patch.object(run, "subleq", side_effect=error),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                run.execute_data(
                    np.zeros(3, dtype=np.uint16),
                    {},
                    debug_enabled=False,
                    display_name="test.s",
                )

            self.assertIn(message, output.getvalue())

    def test_debug_execution_fault_prints_machine_trace_without_python_traceback(
        self,
    ) -> None:
        data = np.zeros(1802, dtype=np.uint16)
        data[2] = 1528
        data[1528:1531] = [0, 0, 1796]
        data[1796:1799] = [0, 0, 65535]

        with (
            contextlib.redirect_stdout(io.StringIO()) as output,
            contextlib.redirect_stderr(io.StringIO()) as errors,
        ):
            run.execute_data(
                data,
                {"z": 1796},
                debug_enabled=True,
                display_name="trace-test",
            )

        report = errors.getvalue() + output.getvalue()
        self.assertIn("Execution traceback", report)
        self.assertIn("PC= 1528", report)
        self.assertIn("PC= 1796", report)
        self.assertIn("cannot fetch three-word instruction at PC=65535", report)
        self.assertNotIn("Traceback (most recent call last)", report)

    def test_invalid_character_output_reports_subleq_source_and_trace(self) -> None:
        data = np.array([4, 3, 0, 0, 0xFF00], dtype=np.uint16)

        with (
            contextlib.redirect_stdout(io.StringIO()) as output,
            contextlib.redirect_stderr(io.StringIO()) as errors,
        ):
            run.execute_data(
                data,
                {"bad_character": 4},
                debug_enabled=False,
                display_name="bad-output.s",
                source_map={0: ("bad-output.s", 12)},
            )

        report = errors.getvalue() + output.getvalue()
        self.assertIn("attempted character output of 65280", report)
        self.assertIn("-256 signed, 0xFF00", report)
        self.assertIn("address 4 (bad_character)", report)
        self.assertIn("bad-output.s:12", report)
        self.assertIn("Execution traceback", report)
        self.assertNotIn("Traceback (most recent call last)", report)

    def test_echo_program_prompts_before_reading_input(self) -> None:
        root = Path(__file__).parents[1]
        data, labels = subleq_compile_files(
            [root / "programs" / "program" / "program.s"]
        )

        with (
            mock.patch("builtins.input", side_effect=EOFError()),
            mock.patch.object(run.os, "write") as write_output,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            run.execute_data(
                data,
                labels,
                debug_enabled=False,
                display_name="program.s",
            )

        emitted = b"".join(call.args[1] for call in write_output.call_args_list)
        self.assertEqual(emitted, b"Welcome to the Subleq CPU Emulator!\n> ")

    def test_compile_links_multiple_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library_path = root / "library.s"
            source_path = root / "main.s"
            image_path = root / "linked.npy"
            library_path.write_text("library: .word main\n")
            source_path.write_text("main: .word library\n")

            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(
                    [
                        "compile",
                        str(library_path),
                        str(source_path),
                        "-o",
                        str(image_path),
                    ]
                )

            np.testing.assert_array_equal(
                np.load(image_path), np.array([1, 0], dtype=np.uint16)
            )

    def test_version_uses_package_version(self) -> None:
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            cli.main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), "subleq 0.1.0")

    def test_syntax_error_shows_location_context_and_no_traceback(self) -> None:
        source = ".data\n    1\n    .res 2\n.endd\n"
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "broken.s"
            source_path.write_text(source)
            output = io.StringIO()

            with (
                mock.patch(
                    "subleq.cli.Console",
                    return_value=Console(file=output, color_system=None, width=100),
                ),
                self.assertRaises(SystemExit) as raised,
            ):
                cli.main(["run", str(source_path)])

            diagnostic = output.getvalue()
            self.assertEqual(raised.exception.code, 1)
            self.assertIn(f"{source_path}:3:5", diagnostic)
            self.assertIn("unexpected '.res'", diagnostic)
            self.assertIn("1", diagnostic)
            self.assertIn(".res 2", diagnostic)
            self.assertIn("^", diagnostic)
            self.assertNotIn("Traceback", diagnostic)

    def test_lsp_accepts_language_client_stdio_flag(self) -> None:
        with mock.patch.object(cli.lsp, "main") as lsp_main:
            cli.main(["lsp", "--stdio"])

        lsp_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
