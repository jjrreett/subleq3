"""Compile and execute test harnesses embedded in SUBLEQ source."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rich import print

from . import run
from .compile import CompilationError, subleq_compile
from .harness import HarnessSyntaxError, SourceTest, parse_test_harness
from .link import link_sources


@dataclass(frozen=True)
class TestResult:
    """Outcome from one embedded source test."""

    name: str
    passed: bool
    instruction_count: int | None
    failures: tuple[str, ...]


def _unknown_label(test: SourceTest, label: str) -> str:
    return f"{test.name}: unknown global label {label!r}"


def _resolve_value(test: SourceTest, value: int | str, labels: dict[str, int]) -> int:
    if isinstance(value, int):
        return value
    if value not in labels:
        raise KeyError(_unknown_label(test, value))
    return labels[value]


def run_source_tests(
    inputs: Sequence[Path], *, max_instructions: int = 1_000_000
) -> list[TestResult]:
    """Link source inputs and run every embedded test independently."""
    harness = parse_test_harness(link_sources(list(inputs)))
    results: list[TestResult] = []

    for test in harness.tests:
        try:
            data, labels = subleq_compile(harness.production_source + test.body)
            memory = data.copy()
            failures: list[str] = []
            for assignment in test.initial_values:
                if assignment.label not in labels:
                    failures.append(_unknown_label(test, assignment.label))
                    continue
                try:
                    value = _resolve_value(test, assignment.value, labels)
                except KeyError as error:
                    failures.append(error.args[0])
                    continue
                memory[labels[assignment.label]] = np.uint16(value)

            output = bytearray()
            instruction_count: int | None = None
            if not failures:
                previous_debug = run.DEBUG
                run.DEBUG = False
                try:
                    instruction_count = run.subleq(
                        memory,
                        labels,
                        max_instructions=max_instructions,
                        output_handler=output.extend,
                    )
                finally:
                    run.DEBUG = previous_debug

            for assertion in test.assertions:
                if assertion.label not in labels:
                    failures.append(_unknown_label(test, assertion.label))
                    continue
                try:
                    expected = _resolve_value(test, assertion.value, labels)
                except KeyError as error:
                    failures.append(error.args[0])
                    continue
                actual = int(memory[labels[assertion.label]])
                if actual != expected:
                    failures.append(
                        f"{assertion.label}: expected {expected} "
                        f"(0x{expected:04x}), got {actual} (0x{actual:04x})"
                    )
            if test.expected_output is not None and bytes(output) != test.expected_output:
                failures.append(
                    f"output: expected {test.expected_output!r}, got {bytes(output)!r}"
                )
        except (CompilationError, HarnessSyntaxError, run.ExecutionLimitError) as error:
            instruction_count = None
            failures = [str(error)]

        results.append(
            TestResult(
                name=test.name,
                passed=not failures,
                instruction_count=instruction_count,
                failures=tuple(failures),
            )
        )

    return results


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Add source-test arguments to the unified CLI parser."""
    parser.add_argument("input", type=Path, nargs="+", help="Source files to test")
    parser.add_argument(
        "--max-instructions",
        type=int,
        default=1_000_000,
        help="Maximum instructions per test before failure (default: 1000000)",
    )
    parser.set_defaults(command_handler=execute)


def execute(args: argparse.Namespace) -> None:
    """Run embedded tests and report a compact pass/fail summary."""
    results = run_source_tests(args.input, max_instructions=args.max_instructions)
    if not results:
        print("[yellow]No embedded tests found.[/yellow]")
        return

    for result in results:
        if result.passed:
            print(f"[green]PASS[/green] {result.name} ({result.instruction_count} instructions)")
            continue
        print(f"[red]FAIL[/red] {result.name}")
        for failure in result.failures:
            print(f"  {failure}")

    passed = sum(result.passed for result in results)
    print(f"{passed}/{len(results)} tests passed")
    if passed != len(results):
        raise SystemExit(1)
