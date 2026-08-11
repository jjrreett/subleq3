"""The standard library should exercise itself through source harnesses."""

import unittest
from pathlib import Path

from subleq.testing import run_source_tests


class StandardLibraryHarnessTests(unittest.TestCase):
    def test_all_embedded_standard_library_cases_pass(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "subleq"
            / "stdlib"
            / "stdlib_tests.s"
        )

        results = run_source_tests([source])

        self.assertEqual(len(results), 6)
        self.assertTrue(
            all(result.passed for result in results),
            {result.name: result.failures for result in results if not result.passed},
        )


if __name__ == "__main__":
    unittest.main()
