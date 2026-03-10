#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from dft_job_utils import copy_file, format_scheduler_script, format_vasp_kpoints, parse_mesh, parse_modules, write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a conservative VASP workflow skeleton.")
    parser.add_argument("directory", help="Output directory for the workflow.")
    parser.add_argument("--task", choices=["relax", "static", "dos", "band", "optics"], required=True)
    parser.add_argument("--system", default="DFT workflow")
    parser.add_argument("--material", choices=["metal", "semiconductor", "insulator"], default="semiconductor")
    parser.add_argument("--encut", type=int, default=520)
    parser.add_argument("--ediff", type=float, default=1e-6)
    parser.add_argument("--ediffg", type=float, default=-0.02)
    parser.add_argument("--ispin", type=int, choices=[1, 2], default=1)
    parser.add_argument("--magmom", help="MAGMOM string, e.g. '4*5.0 8*0.6'")
    parser.add_argument("--ncore", type=int)
    parser.add_argument("--kmesh", default="6 6 6", help="Uniform mesh for relax/static/parent SCF.")
    parser.add_argument("--dense-kmesh", help="Denser mesh for DOS child stage.")
    parser.add_argument("--gamma-centered", action="store_true", help="Use Gamma-centered meshes.")
    parser.add_argument("--poscar", help="Optional POSCAR file to copy into generated stages.")
    parser.add_argument("--scheduler", choices=["none", "slurm", "pbs"], default="slurm")
    parser.add_argument("--job-name", default="vasp-job")
    parser.add_argument("--command", default="vasp_std")
    parser.add_argument("--modules", help="Comma-separated module names to leave in comments.")
    parser.add_argument("--time", default="24:00:00")
    parser.add_argument("--nodes", type=int, default=1)
    parser.add_argument("--ntasks-per-node", type=int, default=32)
    parser.add_argument("--cpus-per-task", type=int, default=1)
    parser.add_argument("--partition")
    parser.add_argument("--account")
    return parser.parse_args()


def material_smearing(task: str, material: str) -> tuple[int, float]:
    if task == "dos":
        if material == "metal":
            return 0, 0.05
        return -5, 0.05
    if material == "metal":
        return 1, 0.2
    return 0, 0.05


def ordered_incar_lines(settings: dict[str, object]) -> str:
    order = [
        "SYSTEM",
        "PREC",
        "ENCUT",
        "EDIFF",
        "EDIFFG",
        "ISPIN",
        "MAGMOM",
        "LASPH",
        "LREAL",
        "ADDGRID",
        "ISMEAR",
        "SIGMA",
        "NELM",
        "ALGO",
        "IBRION",
        "NSW",
        "ISIF",
        "ISTART",
        "ICHARG",
        "LCHARG",
        "LWAVE",
        "LORBIT",
        "NEDOS",
        "NCORE",
    ]
    lines: list[str] = []
    for key in order:
        value = settings.get(key)
        if value is None:
            continue
        lines.append(f"{key} = {value}")
    for key, value in settings.items():
        if key not in order and value is not None:
            lines.append(f"{key} = {value}")
    return "\n".join(lines)


def base_settings(args: argparse.Namespace, *, task: str, write_charge: bool, write_wave: bool) -> dict[str, object]:
    ismear, sigma = material_smearing(task, args.material)
    settings: dict[str, object] = {
        "SYSTEM": args.system,
        "PREC": "Accurate",
        "ENCUT": args.encut,
        "EDIFF": f"{args.ediff:.1e}",
        "ISPIN": args.ispin,
        "LASPH": ".TRUE.",
        "LREAL": "Auto",
        "ADDGRID": ".TRUE.",
        "ISMEAR": ismear,
        "SIGMA": f"{sigma:.3f}",
        "NELM": 120,
        "ALGO": "Normal",
        "LCHARG": ".TRUE." if write_charge else ".FALSE.",
        "LWAVE": ".TRUE." if write_wave else ".FALSE.",
    }
    if args.magmom:
        settings["MAGMOM"] = args.magmom
    if args.ncore:
        settings["NCORE"] = args.ncore
    return settings


def relax_settings(args: argparse.Namespace) -> dict[str, object]:
    settings = base_settings(args, task="relax", write_charge=True, write_wave=False)
    settings.update(
        {
            "IBRION": 2,
            "NSW": 120,
            "ISIF": 3,
            "EDIFFG": f"{args.ediffg:.3f}",
        }
    )
    return settings


def static_settings(args: argparse.Namespace, *, charge_mode: int = 2, write_charge: bool = True) -> dict[str, object]:
    settings = base_settings(args, task="static", write_charge=write_charge, write_wave=False)
    settings.update({"IBRION": -1, "NSW": 0, "ISTART": 0, "ICHARG": charge_mode})
    return settings


def dos_settings(args: argparse.Namespace) -> dict[str, object]:
    settings = base_settings(args, task="dos", write_charge=False, write_wave=False)
    settings.update(
        {
            "IBRION": -1,
            "NSW": 0,
            "ISTART": 0,
            "ICHARG": 11,
            "LORBIT": 11,
            "NEDOS": 2001,
        }
    )
    return settings


def band_settings(args: argparse.Namespace) -> dict[str, object]:
    settings = base_settings(args, task="static", write_charge=False, write_wave=False)
    settings.update({"IBRION": -1, "NSW": 0, "ISTART": 0, "ICHARG": 11, "ISMEAR": 0, "SIGMA": "0.050"})
    return settings


def optics_settings(args: argparse.Namespace) -> dict[str, object]:
    settings = base_settings(args, task="static", write_charge=False, write_wave=False)
    settings.update(
        {
            "IBRION": -1,
            "NSW": 0,
            "ISTART": 0,
            "ICHARG": 11,
            "ISMEAR": 0 if args.material != "metal" else 1,
            "SIGMA": "0.050" if args.material != "metal" else "0.200",
            "LOPTICS": ".TRUE.",
            "CSHIFT": "0.100",
            "NEDOS": 2001,
        }
    )
    return settings


def write_stage(
    stage_dir: Path,
    incar_text: str,
    *,
    kpoints_text: str | None,
    poscar: str | None,
    scheduler: str,
    job_name: str,
    command: str,
    modules: list[str],
    time_limit: str,
    nodes: int,
    ntasks_per_node: int,
    cpus_per_task: int,
    partition: str | None,
    account: str | None,
) -> None:
    write_text(stage_dir / "INCAR", incar_text)
    if kpoints_text:
        write_text(stage_dir / "KPOINTS", kpoints_text)
    if poscar:
        copy_file(poscar, stage_dir / "POSCAR")
    if scheduler != "none":
        extension = "slurm" if scheduler == "slurm" else "pbs"
        script = format_scheduler_script(
            scheduler,
            job_name,
            command,
            stdout_name=f"{job_name}.stdout",
            stderr_name=f"{job_name}.stderr",
            modules=modules,
            time_limit=time_limit,
            nodes=nodes,
            ntasks_per_node=ntasks_per_node,
            cpus_per_task=cpus_per_task,
            partition=partition,
            account=account,
        )
        write_text(stage_dir / f"run.{extension}", script)


def write_workflow_plan(root: Path, task: str, notes: list[str], stages: list[dict[str, object]]) -> None:
    lines = ["# Workflow Plan", "", f"- Task: `{task}`", "", "## Stages", ""]
    for stage in stages:
        lines.extend(
            [
                f"### {stage['name']}",
                f"- Directory: `{stage['directory']}`",
                f"- Purpose: {stage['purpose']}",
                f"- Depends on: {stage['depends_on']}",
                f"- Files: {', '.join(stage['files'])}",
                "",
            ]
        )
    lines.extend(["## Notes", ""])
    lines.extend(f"- {note}" for note in notes)
    write_text(root / "WORKFLOW_PLAN.md", "\n".join(lines))


def main() -> None:
    args = parse_args()
    root = Path(args.directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    modules = parse_modules(args.modules)
    mesh = parse_mesh(args.kmesh, 3)
    dense_mesh = parse_mesh(args.dense_kmesh, 3) if args.dense_kmesh else mesh

    notes: list[str] = [
        f"Task: {args.task}",
        f"Material class assumption: {args.material}",
        f"ENCUT: {args.encut} eV",
        "POTCAR is intentionally not generated; provide the correct PAW datasets manually.",
    ]
    if not args.poscar:
        notes.append("POSCAR is not present; copy a validated structure before running.")
    stages: list[dict[str, object]] = []

    if args.task == "relax":
        write_stage(
            root,
            ordered_incar_lines(relax_settings(args)),
            kpoints_text=format_vasp_kpoints(mesh, gamma_centered=args.gamma_centered),
            poscar=args.poscar,
            scheduler=args.scheduler,
            job_name=args.job_name,
            command=args.command,
            modules=modules,
            time_limit=args.time,
            nodes=args.nodes,
            ntasks_per_node=args.ntasks_per_node,
            cpus_per_task=args.cpus_per_task,
            partition=args.partition,
            account=args.account,
        )
        notes.append("Check the final forces in OUTCAR before using CONTCAR for production energies.")
        stages.append(
            {
                "name": "Relaxation",
                "directory": ".",
                "purpose": "Relax the structure and produce a converged geometry.",
                "depends_on": "None",
                "files": ["INCAR", "KPOINTS", "POSCAR", "POTCAR", "run.<scheduler>"],
            }
        )

    elif args.task == "static":
        write_stage(
            root,
            ordered_incar_lines(static_settings(args)),
            kpoints_text=format_vasp_kpoints(mesh, gamma_centered=args.gamma_centered),
            poscar=args.poscar,
            scheduler=args.scheduler,
            job_name=args.job_name,
            command=args.command,
            modules=modules,
            time_limit=args.time,
            nodes=args.nodes,
            ntasks_per_node=args.ntasks_per_node,
            cpus_per_task=args.cpus_per_task,
            partition=args.partition,
            account=args.account,
        )
        notes.append("Use a structure from a converged relaxation if this static energy is meant to be comparable.")
        stages.append(
            {
                "name": "Static",
                "directory": ".",
                "purpose": "Compute a fixed-geometry total energy and charge density.",
                "depends_on": "A converged structure",
                "files": ["INCAR", "KPOINTS", "POSCAR", "POTCAR", "run.<scheduler>"],
            }
        )

    elif args.task == "dos":
        scf_dir = root / "01-scf"
        dos_dir = root / "02-dos"
        write_stage(
            scf_dir,
            ordered_incar_lines(static_settings(args, charge_mode=2, write_charge=True)),
            kpoints_text=format_vasp_kpoints(mesh, gamma_centered=args.gamma_centered),
            poscar=args.poscar,
            scheduler=args.scheduler,
            job_name=f"{args.job_name}-scf",
            command=args.command,
            modules=modules,
            time_limit=args.time,
            nodes=args.nodes,
            ntasks_per_node=args.ntasks_per_node,
            cpus_per_task=args.cpus_per_task,
            partition=args.partition,
            account=args.account,
        )
        write_stage(
            dos_dir,
            ordered_incar_lines(dos_settings(args)),
            kpoints_text=format_vasp_kpoints(dense_mesh, gamma_centered=args.gamma_centered),
            poscar=args.poscar,
            scheduler=args.scheduler,
            job_name=f"{args.job_name}-dos",
            command=args.command,
            modules=modules,
            time_limit=args.time,
            nodes=args.nodes,
            ntasks_per_node=args.ntasks_per_node,
            cpus_per_task=args.cpus_per_task,
            partition=args.partition,
            account=args.account,
        )
        notes.extend(
            [
                "Run 01-scf first, then copy CHGCAR into 02-dos or point 02-dos to the saved charge density.",
                "Increase --dense-kmesh if the DOS remains jagged.",
            ]
        )
        stages.extend(
            [
                {
                    "name": "Parent SCF",
                    "directory": "01-scf",
                    "purpose": "Generate a converged charge density on a uniform mesh.",
                    "depends_on": "Validated POSCAR and POTCAR",
                    "files": ["INCAR", "KPOINTS", "POSCAR", "POTCAR", "run.<scheduler>"],
                },
                {
                    "name": "DOS",
                    "directory": "02-dos",
                    "purpose": "Reuse the parent charge density for denser DOS sampling.",
                    "depends_on": "CHGCAR from 01-scf",
                    "files": ["INCAR", "KPOINTS", "POSCAR", "POTCAR", "run.<scheduler>"],
                },
            ]
        )

    elif args.task == "band":
        scf_dir = root / "01-scf"
        band_dir = root / "02-band"
        write_stage(
            scf_dir,
            ordered_incar_lines(static_settings(args, charge_mode=2, write_charge=True)),
            kpoints_text=format_vasp_kpoints(mesh, gamma_centered=args.gamma_centered),
            poscar=args.poscar,
            scheduler=args.scheduler,
            job_name=f"{args.job_name}-scf",
            command=args.command,
            modules=modules,
            time_limit=args.time,
            nodes=args.nodes,
            ntasks_per_node=args.ntasks_per_node,
            cpus_per_task=args.cpus_per_task,
            partition=args.partition,
            account=args.account,
        )
        write_stage(
            band_dir,
            ordered_incar_lines(band_settings(args)),
            kpoints_text=None,
            poscar=args.poscar,
            scheduler=args.scheduler,
            job_name=f"{args.job_name}-band",
            command=args.command,
            modules=modules,
            time_limit=args.time,
            nodes=args.nodes,
            ntasks_per_node=args.ntasks_per_node,
            cpus_per_task=args.cpus_per_task,
            partition=args.partition,
            account=args.account,
        )
        write_text(
            band_dir / "KPOINTS.band.template",
            "\n".join(
                [
                    "Replace with a real line-mode path from SeeK-path or literature",
                    "40",
                    "Line-mode",
                    "Reciprocal",
                    "# Example only. Do not run until this file is replaced.",
                    "0.0 0.0 0.0 ! G",
                    "0.5 0.0 0.0 ! X",
                ]
            ),
        )
        notes.extend(
            [
                "Run 01-scf first, then copy CHGCAR into 02-band.",
                "Replace 02-band/KPOINTS.band.template with a real high-symmetry path before running the band step.",
            ]
        )
        stages.extend(
            [
                {
                    "name": "Parent SCF",
                    "directory": "01-scf",
                    "purpose": "Generate a converged charge density on a uniform mesh.",
                    "depends_on": "Validated POSCAR and POTCAR",
                    "files": ["INCAR", "KPOINTS", "POSCAR", "POTCAR", "run.<scheduler>"],
                },
                {
                    "name": "Band Path",
                    "directory": "02-band",
                    "purpose": "Run a read-only path calculation using a user-supplied band path.",
                    "depends_on": "CHGCAR from 01-scf and a finalized KPOINTS.band.template replacement",
                    "files": ["INCAR", "KPOINTS.band.template", "POSCAR", "POTCAR", "run.<scheduler>"],
                },
            ]
        )

    elif args.task == "optics":
        scf_dir = root / "01-scf"
        optics_dir = root / "02-optics"
        write_stage(
            scf_dir,
            ordered_incar_lines(static_settings(args, charge_mode=2, write_charge=True)),
            kpoints_text=format_vasp_kpoints(mesh, gamma_centered=args.gamma_centered),
            poscar=args.poscar,
            scheduler=args.scheduler,
            job_name=f"{args.job_name}-scf",
            command=args.command,
            modules=modules,
            time_limit=args.time,
            nodes=args.nodes,
            ntasks_per_node=args.ntasks_per_node,
            cpus_per_task=args.cpus_per_task,
            partition=args.partition,
            account=args.account,
        )
        write_stage(
            optics_dir,
            ordered_incar_lines(optics_settings(args)),
            kpoints_text=format_vasp_kpoints(dense_mesh, gamma_centered=args.gamma_centered),
            poscar=args.poscar,
            scheduler=args.scheduler,
            job_name=f"{args.job_name}-optics",
            command=args.command,
            modules=modules,
            time_limit=args.time,
            nodes=args.nodes,
            ntasks_per_node=args.ntasks_per_node,
            cpus_per_task=args.cpus_per_task,
            partition=args.partition,
            account=args.account,
        )
        notes.extend(
            [
                "Run 01-scf first, then copy CHGCAR into 02-optics before launching the optics stage.",
                "Use a denser k-mesh for 02-optics if the dielectric response remains jagged.",
            ]
        )
        stages.extend(
            [
                {
                    "name": "Parent SCF",
                    "directory": "01-scf",
                    "purpose": "Generate a converged charge density on a uniform mesh.",
                    "depends_on": "Validated POSCAR and POTCAR",
                    "files": ["INCAR", "KPOINTS", "POSCAR", "POTCAR", "run.<scheduler>"],
                },
                {
                    "name": "Optics",
                    "directory": "02-optics",
                    "purpose": "Evaluate optical response using the converged parent charge density.",
                    "depends_on": "CHGCAR from 01-scf",
                    "files": ["INCAR", "KPOINTS", "POSCAR", "POTCAR", "run.<scheduler>"],
                },
            ]
        )

    write_text(root / "README.next-steps", "\n".join(f"- {line}" for line in notes))
    write_workflow_plan(root, args.task, notes, stages)


if __name__ == "__main__":
    main()
