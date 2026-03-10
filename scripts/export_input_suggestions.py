#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from check_vasp_job import discover_dirs
from dft_parsers import parse_vasp_dir


def render_record(record: dict[str, object]) -> str:
    warnings = list(record.get("warnings") or [])
    name = Path(str(record["path"])).name
    lines = [f"## {name}", ""]

    if any("Charge mixing appears unstable." == warning for warning in warnings) or any("NELM" in warning for warning in warnings):
        lines.extend(
            [
                "Conservative INCAR snippet for electronic stabilization:",
                "",
                "```text",
                "ALGO = Normal",
                "NELM = 120",
                "# Review ISMEAR and SIGMA against the material class before rerunning.",
                "```",
                "",
            ]
        )

    if any("CHGCAR" in warning for warning in warnings):
        lines.extend(
            [
                "No safe direct INCAR patch is enough here.",
                "",
                "```text",
                "# This child stage needs CHGCAR from a converged parent calculation.",
                "# Restore or copy CHGCAR before rerunning.",
                "```",
                "",
            ]
        )

    if any("Diagonalization failed." == warning or "Subspace diagonalization failed." == warning for warning in warnings):
        lines.extend(
            [
                "Do not trust the current restart artifacts.",
                "",
                "```text",
                "# Inspect the geometry before rerunning.",
                "# Prefer a clean restart from corrected inputs.",
                "```",
                "",
            ]
        )

    if len(lines) == 2:
        lines.extend(["No conservative input snippet was required for this path.", ""])

    return "\n".join(lines)


def render_markdown(records: list[dict[str, object]], source: Path) -> str:
    lines = ["# Input Suggestions", "", f"Source: `{source}`", ""]
    for index, record in enumerate(records):
        lines.append(render_record(record).rstrip())
        if index != len(records) - 1:
            lines.extend(["", "---", ""])
    return "\n".join(lines).rstrip() + "\n"


def default_output(source: Path) -> Path:
    if source.is_file():
        return source.parent / f"{source.stem}.INPUT_SUGGESTIONS.md"
    return source / "INPUT_SUGGESTIONS.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export conservative VASP input suggestion snippets.")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    source = Path(args.path).expanduser().resolve()
    records = [parse_vasp_dir(directory) for directory in discover_dirs(source)]
    output = Path(args.output).expanduser().resolve() if args.output else default_output(source)
    output.write_text(render_markdown(records, source))
    print(output)


if __name__ == "__main__":
    main()
