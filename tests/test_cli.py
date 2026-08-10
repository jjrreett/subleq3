"""Tests for the unified SUBLEQ command-line interface."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from subleq import cli


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
        for command in ("compile", "run", "gen-grammar", "lsp"):
            self.assertIn(command, output.getvalue())

    def test_compile_and_run_subcommands(self) -> None:
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
                cli.main(["run", str(image_path)])

            self.assertTrue(image_path.exists())
            np.testing.assert_array_equal(
                np.load(image_path), np.array([5, 5, 0, 0, 0, 0], dtype=np.uint16)
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

    def test_lsp_accepts_language_client_stdio_flag(self) -> None:
        with mock.patch.object(cli.lsp, "main") as lsp_main:
            cli.main(["lsp", "--stdio"])

        lsp_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
