#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dft_parsers import parse_vasp_dir


def looks_like_vasp_dir(path: Path) -> bool:
    names = {item.name for item in path.iterdir()} if path.is_dir() else set()
    return any(name in names for name in ("INCAR", "POSCAR", "KPOINTS", "OUTCAR", "OSZICAR", "POTCAR"))


def discover_dirs(root: Path) -> list[Path]:
    children = sorted(path for path in root.iterdir() if path.is_dir() and looks_like_vasp_dir(path))
    if children:
        return children
    return [root]


def summarize(record: dict[str, object]) -> list[str]:
    lines = [f"[{Path(str(record['path'])).name}] vasp {record['task']}"]
    lines.append(f"State: {record['state']}")
    missing = record.get("missing_inputs") or []
    if missing:
        lines.append("Missing inputs: " + ", ".join(str(item) for item in missing))
    warnings = record.get("warnings") or []
    if warnings:
        lines.append("Warnings: " + "; ".join(str(item) for item in warnings))
    if record.get("final_energy_eV") is not None:
        lines.append(f"Final energy: {record['final_energy_eV']:.6f} eV")
    if record.get("max_force_eV_A") is not None:
        lines.append(f"Max force: {record['max_force_eV_A']:.4f} eV/Ang")
    if record.get("last_electronic_steps") is not None:
        lines.append(f"Last electronic steps: {record['last_electronic_steps']}")
    lines.append(f"Ionic converged: {bool(record.get('ionic_converged'))}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a VASP calculation directory or staged workflow root.")
    parser.add_argument("directory", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    records = [parse_vasp_dir(directory) for directory in discover_dirs(root)]
    if args.json:
        print(json.dumps(records if len(records) > 1 else records[0], indent=2))
        return
    for index, record in enumerate(records):
        if index:
            print()
        print("\n".join(summarize(record)))


if __name__ == "__main__":
    main()
