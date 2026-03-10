#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_vasp_job import discover_dirs
from dft_parsers import parse_vasp_dir


def build_recommendation(record: dict[str, object]) -> dict[str, object]:
    warnings = list(record.get("warnings") or [])
    missing_inputs = list(record.get("missing_inputs") or [])
    actions: list[str] = []
    issues: list[str] = []
    severity = "info"
    safe_restart = False
    restart_strategy = "No recovery action is needed yet."

    if missing_inputs:
        severity = "error"
        issues.append("The directory is missing required VASP inputs.")
        actions.append("Provide the missing input files before attempting a restart.")

    if record.get("state") == "template":
        issues.append("This stage is still a template and is not ready to run.")
        actions.append("Replace the placeholder band-path KPOINTS template with a real path before running.")
        restart_strategy = "Do not restart this stage yet; finish the template setup first."

    if any("CHGCAR" in warning for warning in warnings):
        severity = "error"
        issues.append("This child stage depends on a converged parent charge density.")
        actions.append("Copy CHGCAR from a converged parent stage or rerun the parent calculation first.")
        restart_strategy = "Do not restart this stage standalone; complete the parent stage and supply CHGCAR."

    if any("Charge mixing appears unstable." == warning for warning in warnings):
        severity = "warning" if severity == "info" else severity
        issues.append("Electronic mixing looks unstable.")
        actions.append("Inspect whether metallicity, smearing, spin initialization, or the structure itself is the real problem.")
        actions.append("If the physics model is sound, retry with more conservative mixing or a safer preconvergence setup.")
        restart_strategy = "Adjust the electronic mixing strategy first, then restart from WAVECAR and CHGCAR only if the existing density still looks sane."
        safe_restart = True

    if any("NELM" in warning for warning in warnings):
        severity = "warning" if severity == "info" else severity
        issues.append("The last ionic step exhausted the allowed electronic iterations.")
        actions.append("Inspect the last ionic step, the structure, and the smearing choice before only increasing NELM.")
        if record.get("task") == "relax":
            actions.append("Do not trust the current relaxation as converged until the electronic loop stabilizes.")
        restart_strategy = "Change the unstable electronic settings first, then reuse existing WAVECAR only if the wavefunctions are still reasonable."
        safe_restart = True

    if any("Diagonalization failed." == warning or "Subspace diagonalization failed." == warning for warning in warnings):
        severity = "error"
        issues.append("Diagonalization failed and the current state is likely not trustworthy.")
        actions.append("Inspect the geometry for overlaps or corrupted structures before rerunning.")
        actions.append("Restart from corrected inputs rather than blindly reusing CHGCAR or WAVECAR.")
        restart_strategy = "Prefer a clean restart from corrected inputs; do not trust the current restart artifacts."
        safe_restart = False

    if record.get("task") == "relax" and record.get("max_force_eV_A") not in (None, 0) and not record.get("ionic_converged"):
        issues.append("The relaxation is not yet ionically converged.")
        actions.append("Do not compare final energies from this directory as if the relaxation were finished.")

    if record.get("state") == "incomplete" and not issues:
        severity = "warning"
        issues.append("The calculation stopped before completion.")
        actions.append("Check walltime, scheduler logs, and whether restart files are present before resubmitting.")
        restart_strategy = "Reuse existing WAVECAR and CHGCAR only if the physics model is unchanged and the previous run stopped cleanly."
        safe_restart = True

    if not issues:
        issues.append("No critical recovery issues were detected.")
        actions.append("Proceed with the next planned stage or post-processing step.")

    return {
        "path": record["path"],
        "task": record["task"],
        "state": record["state"],
        "severity": severity,
        "issues": issues,
        "recommended_actions": actions,
        "restart_strategy": restart_strategy,
        "safe_to_reuse_existing_state": safe_restart,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend VASP recovery or restart actions from a run directory.")
    parser.add_argument("directory", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    records = [build_recommendation(parse_vasp_dir(directory)) for directory in discover_dirs(root)]
    if args.json:
        print(json.dumps(records if len(records) > 1 else records[0], indent=2))
        return
    for index, record in enumerate(records):
        if index:
            print()
        print(f"[{Path(str(record['path'])).name}] {record['severity']} {record['task']} {record['state']}")
        print("Issues: " + "; ".join(record["issues"]))
        for action in record["recommended_actions"]:
            print("- " + action)
        print("Restart strategy: " + record["restart_strategy"])


if __name__ == "__main__":
    main()
