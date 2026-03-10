#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from check_vasp_job import discover_dirs
from dft_parsers import parse_vasp_dir
from recommend_vasp_recovery import build_recommendation


def render_markdown(records: list[dict[str, object]], source: Path) -> str:
    lines = ["# Recovery Plan", "", f"Source: `{source}`", ""]
    for index, record in enumerate(records):
        name = Path(str(record["path"])).name
        lines.extend(
            [
                f"## {name}",
                "",
                f"- Severity: `{record['severity']}`",
                f"- State reuse allowed: `{str(record['safe_to_reuse_existing_state']).lower()}`",
                "",
                "### Issues",
            ]
        )
        lines.extend(f"- {issue}" for issue in record["issues"])
        lines.extend(["", "### Recommended Actions"])
        lines.extend(f"- {action}" for action in record["recommended_actions"])
        lines.extend(["", "### Restart Strategy", record["restart_strategy"], ""])
        if index != len(records) - 1:
            lines.append("---")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def default_output(source: Path) -> Path:
    if source.is_file():
        return source.parent / f"{source.stem}.RESTART_PLAN.md"
    return source / "RESTART_PLAN.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a markdown recovery plan for a VASP run or staged workflow.")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    source = Path(args.path).expanduser().resolve()
    records = [build_recommendation(parse_vasp_dir(directory)) for directory in discover_dirs(source)]
    output = Path(args.output).expanduser().resolve() if args.output else default_output(source)
    output.write_text(render_markdown(records, source))
    print(output)


if __name__ == "__main__":
    main()
