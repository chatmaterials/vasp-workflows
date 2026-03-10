#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path


VASP_WARNING_PATTERNS = {
    "BRMIX": "Charge mixing appears unstable.",
    "ZHEGV": "Diagonalization failed.",
    "EDDDAV": "Subspace diagonalization failed.",
    "TOO FEW BANDS": "The number of bands is likely insufficient.",
    "Sub-Space-Matrix": "Subspace matrix warnings were reported.",
    "VERY BAD NEWS!": "VASP reported a severe internal warning.",
}

QE_WARNING_PATTERNS = {
    "convergence NOT achieved": "SCF did not reach the requested threshold.",
    "Maximum CPU time exceeded": "The job ran out of walltime.",
    "error in routine cdiaghg": "A diagonalization routine failed.",
    "error in routine rdiaghg": "A diagonalization routine failed.",
    "S matrix not positive definite": "The overlap matrix became ill-conditioned.",
    "Error in routine electrons": "QE reported an electronic minimization failure.",
}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="ignore")


def _to_int(value: str | None, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return default


def _to_float(value: str | None, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(str(value).replace("d", "e").replace("D", "e").strip())
    except ValueError:
        return default


def detect_engine(path: Path) -> str | None:
    names = {item.name for item in path.iterdir()} if path.is_dir() else set()
    if {"INCAR", "POSCAR"} & names or {"OUTCAR", "OSZICAR"} & names:
        return "vasp"
    qe_inputs = [item for item in path.glob("*.in")] + [item for item in path.glob("*.in.template")]
    qe_outputs = [item for item in path.glob("*.out")]
    if qe_inputs or qe_outputs:
        for candidate in qe_inputs + qe_outputs:
            text = _read_text(candidate)
            if (
                "&CONTROL" in text
                or "&DOS" in text
                or "&BANDS" in text
                or "Program PWSCF" in text
                or "Quantum ESPRESSO" in text
            ):
                return "qe"
    return None


def looks_like_calc_dir(path: Path) -> bool:
    names = {item.name for item in path.iterdir()} if path.is_dir() else set()
    return any(
        name in names
        for name in ("INCAR", "POSCAR", "KPOINTS", "OUTCAR", "OSZICAR", "POTCAR")
    ) or any(path.glob("*.in")) or any(path.glob("*.in.template")) or any(path.glob("*.out"))


def parse_vasp_incar(path: Path) -> dict[str, str]:
    settings: dict[str, str] = {}
    for raw_line in _read_text(path).splitlines():
        line = raw_line.split("!", 1)[0].split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip().upper()] = value.strip()
    return settings


def infer_vasp_task(settings: dict[str, str], path: Path | None = None) -> str:
    nsw = _to_int(settings.get("NSW"), 0) or 0
    icharg = _to_int(settings.get("ICHARG"))
    nedos = settings.get("NEDOS")
    loptics = settings.get("LOPTICS", "").strip().upper() in {".TRUE.", "TRUE", "T"}
    if nsw > 0:
        return "relax"
    if loptics:
        return "optics"
    if icharg == 11 and nedos:
        return "dos"
    if icharg == 11 and path and (path / "KPOINTS.band.template").exists():
        return "band"
    if icharg == 11:
        return "postprocess"
    if nedos:
        return "dos"
    return "static"


def parse_vasp_oszicar(path: Path) -> dict[str, object]:
    ionic_steps: list[dict[str, object]] = []
    electronic_steps = 0
    for raw_line in _read_text(path).splitlines():
        line = raw_line.strip()
        if re.match(r"^(DAV|RMM|CG|EDWAV):", line):
            electronic_steps += 1
            continue
        if " F=" in raw_line:
            step_match = re.match(r"^\s*(\d+)", raw_line)
            energy_match = re.search(r"F=\s*([\-0-9.Ee+]+)", raw_line)
            ionic_steps.append(
                {
                    "ionic_step": _to_int(step_match.group(1)) if step_match else len(ionic_steps) + 1,
                    "electronic_steps": electronic_steps,
                    "free_energy_eV": _to_float(energy_match.group(1)) if energy_match else None,
                }
            )
            electronic_steps = 0
    last_step = ionic_steps[-1] if ionic_steps else {}
    return {
        "ionic_steps": ionic_steps,
        "last_ionic_step": last_step.get("ionic_step"),
        "last_electronic_steps": last_step.get("electronic_steps"),
        "last_free_energy_eV": last_step.get("free_energy_eV"),
    }


def _extract_last_vasp_force_block(text: str) -> float | None:
    lines = text.splitlines()
    last_max_force: float | None = None
    for index, line in enumerate(lines):
        if "TOTAL-FORCE (eV/Angst)" not in line:
            continue
        forces: list[float] = []
        seen_data = False
        for candidate in lines[index + 1 :]:
            stripped = candidate.strip()
            if not stripped:
                continue
            if stripped.startswith("-"):
                if seen_data:
                    break
                continue
            parts = candidate.split()
            if len(parts) < 6:
                if seen_data:
                    break
                continue
            try:
                fx, fy, fz = map(float, parts[-3:])
            except ValueError:
                if seen_data:
                    break
                continue
            seen_data = True
            forces.append((fx * fx + fy * fy + fz * fz) ** 0.5)
        if forces:
            last_max_force = max(forces)
    return last_max_force


def parse_vasp_outcar(path: Path) -> dict[str, object]:
    text = _read_text(path)
    energies = re.findall(r"TOTEN\s*=\s*([\-0-9.Ee+]+)", text)
    warnings = [message for pattern, message in VASP_WARNING_PATTERNS.items() if pattern in text]
    return {
        "completed": "General timing and accounting informations for this job" in text,
        "ionic_converged": "reached required accuracy - stopping structural energy minimisation" in text,
        "final_energy_eV": _to_float(energies[-1]) if energies else None,
        "max_force_eV_A": _extract_last_vasp_force_block(text),
        "warnings": warnings,
    }


def parse_vasp_dir(path: Path) -> dict[str, object]:
    incar_path = path / "INCAR"
    settings = parse_vasp_incar(incar_path)
    oszicar = parse_vasp_oszicar(path / "OSZICAR")
    outcar = parse_vasp_outcar(path / "OUTCAR")
    required_inputs = ["INCAR", "POSCAR", "KPOINTS", "POTCAR"]
    missing_inputs = [name for name in required_inputs if not (path / name).exists()]
    warnings = list(outcar["warnings"])
    nelm = _to_int(settings.get("NELM"))
    last_electronic_steps = oszicar.get("last_electronic_steps")
    if nelm and isinstance(last_electronic_steps, int) and last_electronic_steps >= nelm:
        warnings.append("The last ionic step appears to have hit NELM.")
    icharg = _to_int(settings.get("ICHARG"))
    if icharg == 11 and not (path / "CHGCAR").exists():
        warnings.append("ICHARG=11 stage needs CHGCAR from a converged parent before running.")
    state = "not-started"
    if (path / "OUTCAR").exists() or (path / "OSZICAR").exists():
        state = "finished" if outcar["completed"] else "incomplete"
    elif (path / "KPOINTS.band.template").exists() and not (path / "KPOINTS").exists():
        state = "template"
    return {
        "engine": "vasp",
        "task": infer_vasp_task(settings, path),
        "path": str(path),
        "state": state,
        "settings": settings,
        "missing_inputs": missing_inputs,
        "warnings": warnings,
        "completed": outcar["completed"],
        "ionic_converged": outcar["ionic_converged"],
        "final_energy_eV": outcar["final_energy_eV"] or oszicar.get("last_free_energy_eV"),
        "max_force_eV_A": outcar["max_force_eV_A"],
        "last_ionic_step": oszicar.get("last_ionic_step"),
        "last_electronic_steps": last_electronic_steps,
        "nelm": nelm,
    }


def _find_qe_input(path: Path) -> tuple[Path | None, bool]:
    preferred = [
        "scf.in",
        "relax.in",
        "nscf.in",
        "bands.in",
        "pw.in",
        "scf.in.template",
        "relax.in.template",
        "nscf.in.template",
        "bands.in.template",
    ]
    for name in preferred:
        candidate = path / name
        if candidate.exists():
            return candidate, candidate.suffix == ".template"
    all_inputs = sorted(path.glob("*.in")) + sorted(path.glob("*.in.template"))
    if not all_inputs:
        return None, False
    candidate = all_inputs[0]
    return candidate, candidate.suffix == ".template"


def parse_qe_input(path: Path) -> dict[str, object]:
    text = _read_text(path)
    get_string = lambda pattern: re.search(pattern, text, re.IGNORECASE)
    calc_match = get_string(r"calculation\s*=\s*'([^']+)'")
    prefix_match = get_string(r"prefix\s*=\s*'([^']+)'")
    pseudo_dir_match = get_string(r"pseudo_dir\s*=\s*'([^']+)'")
    outdir_match = get_string(r"outdir\s*=\s*'([^']+)'")
    ecutwfc_match = get_string(r"ecutwfc\s*=\s*([\-0-9.DdEe+]+)")
    ecutrho_match = get_string(r"ecutrho\s*=\s*([\-0-9.DdEe+]+)")
    occupations_match = get_string(r"occupations\s*=\s*'([^']+)'")
    species_files: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().upper().startswith("ATOMIC_SPECIES"):
            for candidate in lines[index + 1 :]:
                stripped = candidate.strip()
                if not stripped:
                    break
                if stripped.upper().startswith(("ATOMIC_POSITIONS", "CELL_PARAMETERS", "K_POINTS")):
                    break
                parts = stripped.split()
                if len(parts) >= 3:
                    species_files.append(parts[2])
            break
    return {
        "calculation": calc_match.group(1) if calc_match else None,
        "prefix": prefix_match.group(1) if prefix_match else None,
        "pseudo_dir": pseudo_dir_match.group(1) if pseudo_dir_match else None,
        "outdir": outdir_match.group(1) if outdir_match else None,
        "ecutwfc": _to_float(ecutwfc_match.group(1)) if ecutwfc_match else None,
        "ecutrho": _to_float(ecutrho_match.group(1)) if ecutrho_match else None,
        "occupations": occupations_match.group(1) if occupations_match else None,
        "species_files": species_files,
    }


def _find_qe_output(path: Path, input_path: Path | None) -> Path | None:
    candidates: list[Path] = []
    if input_path:
        candidates.append(path / f"{input_path.stem}.out")
    candidates.extend(sorted(path.glob("*.out")))
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        text = _read_text(candidate)
        if "Program PWSCF" in text or "Quantum ESPRESSO" in text:
            return candidate
    return None


def parse_qe_output(path: Path) -> dict[str, object]:
    text = _read_text(path)
    energies = re.findall(r"!\s+total energy\s+=\s+([\-0-9.DdEe+]+)\s+Ry", text)
    forces = re.findall(r"Total force\s*=\s*([\-0-9.DdEe+]+)", text)
    warnings = [message for pattern, message in QE_WARNING_PATTERNS.items() if pattern in text]
    return {
        "completed": "JOB DONE." in text,
        "scf_converged": "convergence has been achieved" in text,
        "ionic_converged": "End of BFGS Geometry Optimization" in text or "bfgs converged" in text.lower(),
        "final_energy_Ry": _to_float(energies[-1]) if energies else None,
        "total_force_Ry_bohr": _to_float(forces[-1]) if forces else None,
        "warnings": warnings,
    }


def parse_qe_dir(path: Path) -> dict[str, object]:
    input_path, is_template = _find_qe_input(path)
    input_data = parse_qe_input(input_path) if input_path else {}
    output_path = _find_qe_output(path, input_path)
    output_data = parse_qe_output(output_path) if output_path else {
        "completed": False,
        "scf_converged": False,
        "ionic_converged": False,
        "final_energy_Ry": None,
        "total_force_Ry_bohr": None,
        "warnings": [],
    }
    warnings = list(output_data["warnings"])
    missing_inputs: list[str] = []
    if input_path is None:
        missing_inputs.append("pw.x input")
    pseudo_dir = input_data.get("pseudo_dir")
    if input_path and pseudo_dir:
        pseudo_root = (path / str(pseudo_dir)).resolve() if not Path(str(pseudo_dir)).is_absolute() else Path(str(pseudo_dir))
        for pseudo in input_data.get("species_files", []):
            if not (pseudo_root / pseudo).exists():
                warnings.append(f"Referenced pseudopotential not found: {pseudo}")
    inferred_task = input_data.get("calculation")
    if not inferred_task and input_path:
        stem = input_path.stem.lower()
        if stem == "dos":
            inferred_task = "dos.x"
        elif stem in {"bands_pp", "bands"}:
            inferred_task = "bands.x" if stem == "bands_pp" else "bands"
        else:
            inferred_task = stem
    state = "template" if is_template else "not-started"
    if output_path:
        state = "finished" if output_data["completed"] else "incomplete"
    elif input_path and not is_template:
        state = "not-started"
    return {
        "engine": "qe",
        "task": inferred_task or "unknown",
        "path": str(path),
        "state": state,
        "input_file": str(input_path) if input_path else None,
        "output_file": str(output_path) if output_path else None,
        "missing_inputs": missing_inputs,
        "warnings": warnings,
        "completed": output_data["completed"],
        "scf_converged": output_data["scf_converged"],
        "ionic_converged": output_data["ionic_converged"],
        "final_energy_Ry": output_data["final_energy_Ry"],
        "total_force_Ry_bohr": output_data["total_force_Ry_bohr"],
        "prefix": input_data.get("prefix"),
        "pseudo_dir": input_data.get("pseudo_dir"),
        "outdir": input_data.get("outdir"),
        "ecutwfc": input_data.get("ecutwfc"),
        "ecutrho": input_data.get("ecutrho"),
        "occupations": input_data.get("occupations"),
    }
