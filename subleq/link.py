"""Resolve project and packaged-standard-library source includes."""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

INCLUDE_RE = re.compile(
    r'^\s*\.include\s+(?:"(?P<relative>[^"]+)"|<(?P<stdlib>[^>]+)>)'
    r"\s*(?:;[^\n]*)?(?:\n)?$"
)


class LinkError(Exception):
    """A source module could not be linked."""


class SourceLinker:
    """Expand includes while detecting recursive dependency cycles."""

    def __init__(self) -> None:
        self._stack: list[tuple[str, str]] = []
        self._linked_stdlib: set[tuple[str, str]] = set()
        self.origins: list[tuple[str, int] | None] = []

    def link(self, inputs: list[Path]) -> str:
        """Link input files in command-line order into one assembly source."""
        if not inputs:
            raise LinkError("At least one input file is required")

        modules = [self._expand_project_file(path.resolve()) for path in inputs]
        return "\n".join(module.rstrip("\n") for module in modules) + "\n"

    def _expand_project_file(self, path: Path) -> str:
        key = ("file", str(path))
        if not path.is_file():
            raise LinkError(f"Source file not found: {path}")
        return self._expand(key, str(path), path.read_text(), path.parent)

    def _expand_stdlib_file(self, name: str) -> str:
        normalized = Path(name)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise LinkError(f"Invalid standard-library include: <{name}>")

        resource = resources.files("subleq.stdlib").joinpath(name)
        if not resource.is_file():
            raise LinkError(f"Standard-library module not found: <{name}>")
        key = ("stdlib", normalized.as_posix())
        source = resource.read_text()
        if key in self._stack:
            return self._expand(key, f"<{name}>", source, None)
        if key in self._linked_stdlib:
            return ""

        self._linked_stdlib.add(key)
        try:
            return self._expand(key, f"<{name}>", source, None)
        except Exception:
            self._linked_stdlib.discard(key)
            raise

    def _expand(
        self,
        key: tuple[str, str],
        display_name: str,
        source: str,
        directory: Path | None,
    ) -> str:
        if key in self._stack:
            start = self._stack.index(key)
            cycle = [name for _, name in self._stack[start:]] + [display_name]
            raise LinkError(f"Include cycle: {' -> '.join(cycle)}")

        self._stack.append(key)
        try:
            output: list[str] = []
            for line_number, line in enumerate(source.splitlines(keepends=True), 1):
                match = INCLUDE_RE.fullmatch(line)
                if match is None:
                    output.append(line)
                    self.origins.append((display_name, line_number))
                    continue

                relative_name = match.group("relative")
                try:
                    if relative_name is not None:
                        if directory is None:
                            raise LinkError(
                                "Standard-library modules cannot use relative includes"
                            )
                        included = self._expand_project_file(
                            (directory / relative_name).resolve()
                        )
                    else:
                        included = self._expand_stdlib_file(match.group("stdlib"))
                except LinkError as error:
                    raise LinkError(f"{display_name}:{line_number}: {error}") from error

                output.append(included)
                if included and not included.endswith("\n"):
                    output.append("\n")
            return "".join(output)
        finally:
            self._stack.pop()


def link_sources(inputs: list[Path]) -> str:
    """Resolve and concatenate source modules for compilation."""
    return SourceLinker().link(inputs)


def link_sources_with_origins(
    inputs: list[Path],
) -> tuple[str, list[tuple[str, int] | None]]:
    """Link sources and map each resulting line to its original file and line."""
    linker = SourceLinker()
    source = linker.link(inputs)
    # SourceLinker normalizes module separators. Pad rare synthetic blank lines.
    line_count = len(source.splitlines())
    origins = linker.origins[:line_count]
    origins.extend([None] * (line_count - len(origins)))
    return source, origins
