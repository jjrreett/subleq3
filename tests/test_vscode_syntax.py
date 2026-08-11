"""Tests for the VS Code TextMate grammar."""

import json
import re
import unittest
from pathlib import Path


class TextMateGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        grammar_path = (
            Path(__file__).parents[1]
            / "editors"
            / "vscode"
            / "syntaxes"
            / "subleq.tmLanguage.json"
        )
        cls.grammar = json.loads(grammar_path.read_text())

    def test_local_and_global_label_definitions_receive_colored_scopes(self) -> None:
        patterns = self.grammar["repository"]["labels"]["patterns"]
        by_name = {pattern["name"]: pattern["match"] for pattern in patterns}

        self.assertIsNotNone(
            re.search(
                by_name["entity.name.function.label.local.subleq"],
                "@again:",
            )
        )
        self.assertIsNotNone(
            re.search(
                by_name["entity.name.function.label.global.subleq"],
                "main:",
            )
        )

    def test_macro_definition_accepts_canonical_declaration(self) -> None:
        pattern = self.grammar["repository"]["macroDefinitions"]["patterns"][0]

        match = re.search(pattern["begin"], ".macro add source, destination")

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.group(4), "add")

    def test_plain_label_inside_macro_is_colored_as_private(self) -> None:
        patterns = self.grammar["repository"]["macroLabels"]["patterns"]

        match = re.search(patterns[0]["match"], "again:")

        self.assertIsNotNone(match)
        self.assertEqual(
            patterns[0]["name"],
            "entity.name.function.label.local.subleq",
        )

    def test_embedded_test_keywords_are_directives(self) -> None:
        pattern = self.grammar["repository"]["directives"]["patterns"][0]["match"]

        for directive in (".test", ".set", ".assert", ".assert-output", ".endt"):
            with self.subTest(directive=directive):
                self.assertIsNotNone(re.search(pattern, directive))


if __name__ == "__main__":
    unittest.main()
