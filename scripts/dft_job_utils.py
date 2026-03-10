#!/usr/bin/env python3

from __future__ import annotations

import shutil
from pathlib import Path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text.rstrip() + "\n")


def copy_file(src: str | None, dst: Path) -> bool:
    if not src:
        return False
    source = Path(src).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Source file does not exist: {source}")
    ensure_dir(dst.parent)
    shutil.copy2(source, dst)
    return True


def parse_mesh(raw: str, expected: int) -> list[int]:
    parts = raw.replace(",", " ").split()
    if len(parts) != expected:
        raise ValueError(f"Expected {expected} integers, got {len(parts)} from: {raw!r}")
    try:
        return [int(item) for item in parts]
    except ValueError as exc:
        raise ValueError(f"Mesh values must be integers: {raw!r}") from exc


def parse_modules(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def format_vasp_kpoints(mesh: list[int], gamma_centered: bool = True) -> str:
    style = "Gamma" if gamma_centered else "Monkhorst-Pack"
    return "\n".join(
        [
            "Automatic mesh",
            "0",
            style,
            f"{mesh[0]} {mesh[1]} {mesh[2]}",
            "0 0 0",
        ]
    )


def format_scheduler_script(
    scheduler: str,
    job_name: str,
    command: str,
    *,
    stdout_name: str,
    stderr_name: str,
    modules: list[str] | None = None,
    time_limit: str = "24:00:00",
    nodes: int = 1,
    ntasks_per_node: int = 32,
    cpus_per_task: int = 1,
    partition: str | None = None,
    account: str | None = None,
    launcher: str | None = None,
) -> str:
    modules = modules or []
    launcher = launcher or ("srun" if scheduler == "slurm" else "mpirun")
    run_line = f"{launcher} {command}".strip()
    module_block = ["module purge", "# module load <edit-for-your-cluster>"]
    module_block.extend(f"# module load {module}" for module in modules)

    if scheduler == "slurm":
        header = [
            "#!/bin/bash",
            f"#SBATCH --job-name={job_name}",
            f"#SBATCH --nodes={nodes}",
            f"#SBATCH --ntasks-per-node={ntasks_per_node}",
            f"#SBATCH --cpus-per-task={cpus_per_task}",
            f"#SBATCH --time={time_limit}",
            f"#SBATCH --output={stdout_name}",
            f"#SBATCH --error={stderr_name}",
        ]
        if partition:
            header.append(f"#SBATCH --partition={partition}")
        if account:
            header.append(f"#SBATCH --account={account}")
        body = [
            "set -euo pipefail",
            'cd "${SLURM_SUBMIT_DIR:-$PWD}"',
            *module_block,
            f"export OMP_NUM_THREADS=${{OMP_NUM_THREADS:-{cpus_per_task}}}",
            run_line,
        ]
        return "\n".join(header + [""] + body)

    if scheduler == "pbs":
        ncpus = ntasks_per_node * cpus_per_task
        header = [
            "#!/bin/bash",
            f"#PBS -N {job_name}",
            f"#PBS -l select={nodes}:ncpus={ncpus}:mpiprocs={ntasks_per_node}:ompthreads={cpus_per_task}",
            f"#PBS -l walltime={time_limit}",
            f"#PBS -o {stdout_name}",
            f"#PBS -e {stderr_name}",
        ]
        if account:
            header.append(f"#PBS -A {account}")
        if partition:
            header.append(f"#PBS -q {partition}")
        body = [
            "set -euo pipefail",
            'cd "${PBS_O_WORKDIR:-$PWD}"',
            *module_block,
            f"export OMP_NUM_THREADS=${{OMP_NUM_THREADS:-{cpus_per_task}}}",
            run_line,
        ]
        return "\n".join(header + [""] + body)

    raise ValueError(f"Unsupported scheduler: {scheduler}")


def render_key_value_block(items: list[tuple[str, str]]) -> str:
    return "\n".join(f"{key} = {value}" for key, value in items)
