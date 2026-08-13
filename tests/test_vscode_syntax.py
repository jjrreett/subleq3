"""Tests for the VS Code TextMate grammar."""

import json
import re
import unittest
from pathlib import Path

from subleq.gen_syntax import generate_textmate_grammar


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
        cls.root = Path(__file__).parents[1]

    def test_checked_in_grammar_matches_generator(self) -> None:
        source = (self.root / "subleq.lark").read_text()

        self.assertEqual(self.grammar, generate_textmate_grammar(source))

    def test_local_and_global_label_definitions_receive_colored_scopes(self) -> None:
        patterns = self.grammar["repository"]["labels"]["patterns"]
        self.assertTrue(all(p["name"] == "variable.other.label.subleq" for p in patterns))
        self.assertIsNotNone(re.search(patterns[0]["match"], "@again:"))
        self.assertIsNotNone(re.search(patterns[1]["match"], "main:"))

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
            "variable.other.label.subleq",
        )

    def test_embedded_test_keywords_are_directives(self) -> None:
        pattern = self.grammar["repository"]["directives"]["patterns"][0]["match"]

        for directive in (
            ".bootstrap",
            ".test",
            ".set",
            ".assert",
            ".assert-output",
            ".endt",
        ):
            with self.subTest(directive=directive):
                self.assertIsNotNone(re.search(pattern, directive))

    def test_global_label_references_receive_a_colored_scope(self) -> None:
        patterns = self.grammar["repository"]["labelReferences"]["patterns"]
        self.assertTrue(all(p["name"] == "variable.other.label.subleq" for p in patterns))
        self.assertIsNotNone(re.search(patterns[1]["match"], "value"))

    def test_hoisted_immediate_is_one_numeric_token(self) -> None:
        pattern = self.grammar["repository"]["numbers"]["patterns"][0]

        match = re.search(pattern["match"], "subleq #2, target")

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.group(), "#2")
        self.assertEqual(pattern["name"], "constant.numeric.immediate.subleq")

    def test_character_directives_and_immediates_are_colored(self) -> None:
        pattern = self.grammar["repository"]["characters"]["patterns"][0]["match"]

        self.assertIsNotNone(re.fullmatch(pattern, "'A'"))
        self.assertIsNotNone(re.fullmatch(pattern, "'A"))
        self.assertIsNotNone(re.fullmatch(pattern, r"'\n"))

    def test_semantic_labels_fall_back_to_the_shared_textmate_scope(self) -> None:
        package_path = self.root / "editors" / "vscode" / "package.json"
        package = json.loads(package_path.read_text())
        mappings = package["contributes"]["semanticTokenScopes"]

        self.assertEqual(
            mappings[0]["scopes"]["label"],
            ["variable.other.label.subleq"],
        )


if __name__ == "__main__":
    unittest.main()
