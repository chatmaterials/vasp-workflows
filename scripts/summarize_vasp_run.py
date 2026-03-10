#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dft_parsers import parse_vasp_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize a VASP run directory.")
    parser.add_argument("directory", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    record = parse_vasp_dir(Path(args.directory).expanduser().resolve())
    if args.json:
        print(json.dumps(record, indent=2))
        return
    print(f"Path: {record['path']}")
    print(f"Task: {record['task']}")
    print(f"State: {record['state']}")
    if record.get("final_energy_eV") is not None:
        print(f"Final energy: {record['final_energy_eV']:.6f} eV")
    if record.get("max_force_eV_A") is not None:
        print(f"Max force: {record['max_force_eV_A']:.4f} eV/Ang")
    if record.get("last_electronic_steps") is not None:
        print(f"Last electronic steps: {record['last_electronic_steps']}")
    print(f"Ionic converged: {bool(record.get('ionic_converged'))}")
    if record.get("missing_inputs"):
        print("Missing inputs: " + ", ".join(record["missing_inputs"]))
    if record.get("warnings"):
        print("Warnings: " + "; ".join(record["warnings"]))


if __name__ == "__main__":
    main()
