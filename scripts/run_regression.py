#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True, check=True)


def run_json(*args: str):
    return json.loads(run(*args).stdout)


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    fixture = ROOT / "fixtures" / "completed-relax"
    checked = run_json("scripts/check_vasp_job.py", str(fixture), "--json")
    ensure(checked["completed"] is True, "fixture should be marked completed")
    ensure(checked["ionic_converged"] is True, "fixture should be ionically converged")
    ensure(checked["missing_inputs"] == [], "fixture should not miss VASP inputs")
    ensure(abs(checked["final_energy_eV"] + 10.54321) < 1e-6, "fixture final energy should be parsed")

    summary = run_json("scripts/summarize_vasp_run.py", str(fixture), "--json")
    ensure(summary["task"] == "relax", "fixture task should be relax")
    ensure(summary["max_force_eV_A"] is not None, "fixture max force should be parsed")

    failure = ROOT / "fixtures" / "incomplete-nelm"
    checked_failure = run_json("scripts/check_vasp_job.py", str(failure), "--json")
    ensure(checked_failure["completed"] is False, "failure fixture should not be marked completed")
    ensure(checked_failure["state"] == "incomplete", "failure fixture should be incomplete")
    ensure(any("Charge mixing" in warning for warning in checked_failure["warnings"]), "failure fixture should report charge-mixing instability")
    ensure(any("NELM" in warning for warning in checked_failure["warnings"]), "failure fixture should report NELM saturation")
    recovery = run_json("scripts/recommend_vasp_recovery.py", str(failure), "--json")
    ensure(recovery["severity"] == "warning", "NELM-style VASP failure should be a warning-level recovery case")
    ensure(any("mixing" in action.lower() for action in recovery["recommended_actions"]), "recovery advice should mention mixing")
    ensure(recovery["safe_to_reuse_existing_state"] is True, "NELM-style VASP failure should allow conditional restart reuse")

    temp_dir = Path(tempfile.mkdtemp(prefix="vasp-regression-"))
    optics_dir = Path(tempfile.mkdtemp(prefix="vasp-optics-regression-"))
    try:
        run("scripts/make_vasp_inputs.py", str(temp_dir), "--task", "band", "--scheduler", "none")
        generated = run_json("scripts/check_vasp_job.py", str(temp_dir), "--json")
        ensure(isinstance(generated, list) and len(generated) == 2, "generated band workflow should have two stages")
        ensure(generated[0]["task"] == "static", "first generated stage should be static")
        ensure(generated[1]["task"] == "band", "second generated stage should be band")
        workflow_plan = (temp_dir / "WORKFLOW_PLAN.md").read_text()
        ensure("# Workflow Plan" in workflow_plan, "generated workflow should include WORKFLOW_PLAN.md")
        ensure("Band Path" in workflow_plan, "workflow plan should describe the band stage")
        plan_path = Path(run("scripts/export_recovery_plan.py", str(failure), "--output", str(temp_dir / "RESTART_PLAN.md")).stdout.strip())
        plan_text = plan_path.read_text()
        ensure("# Recovery Plan" in plan_text, "exported plan should have a recovery-plan heading")
        ensure("Charge mixing" in plan_text or "mixing" in plan_text, "exported plan should include recovery guidance")
        status_path = Path(run("scripts/export_status_report.py", str(failure), "--output", str(temp_dir / "STATUS_REPORT.md")).stdout.strip())
        status_text = status_path.read_text()
        ensure("# Status Report" in status_text, "exported status should have a status-report heading")
        ensure("Charge mixing appears unstable." in status_text, "status report should include parsed warnings")
        suggest_path = Path(run("scripts/export_input_suggestions.py", str(failure), "--output", str(temp_dir / "INPUT_SUGGESTIONS.md")).stdout.strip())
        suggest_text = suggest_path.read_text()
        ensure("# Input Suggestions" in suggest_text, "exported suggestions should have an input-suggestions heading")
        ensure("ALGO = Normal" in suggest_text, "VASP suggestions should include a conservative ALGO recommendation")
        ensure("NELM = 120" in suggest_text, "VASP suggestions should include a conservative NELM recommendation")
        run("scripts/make_vasp_inputs.py", str(optics_dir), "--task", "optics", "--scheduler", "none")
        optics = run_json("scripts/check_vasp_job.py", str(optics_dir), "--json")
        ensure(isinstance(optics, list) and len(optics) == 2, "generated optics workflow should have two stages")
        ensure(optics[1]["task"] == "optics", "second generated optics stage should be detected as optics")
        optics_plan = (optics_dir / "WORKFLOW_PLAN.md").read_text()
        ensure("Optics" in optics_plan, "workflow plan should describe the optics stage")
    finally:
        shutil.rmtree(temp_dir)
        shutil.rmtree(optics_dir)

    print("vasp-workflows regression passed")


if __name__ == "__main__":
    main()
