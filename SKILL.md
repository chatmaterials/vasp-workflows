---
name: "vasp-workflows"
description: "Use when the task involves VASP density-functional theory workflows, including INCAR, POSCAR, KPOINTS, and POTCAR preparation, relax, static, DOS, band, and optics setups, OUTCAR or OSZICAR review, restart handling, convergence checks, and Slurm or PBS job scripts."
---

# VASP Workflows

This skill handles practical VASP setup, review, and recovery. Use it when the request is clearly VASP-specific and needs auditable file choices rather than generic DFT commentary.

## When to use

Use this skill when the user mentions or implies:

- `VASP`, `INCAR`, `POSCAR`, `KPOINTS`, `POTCAR`, `OUTCAR`, `OSZICAR`, `vasprun.xml`
- structure relaxations, static energies, DOS, band structures, convergence tests, restarts, or scheduler scripts in VASP
- smearing choices, `MAGMOM`, `ICHARG`, `WAVECAR`, `CHGCAR`, `NELM`, or common VASP failure modes

## Operating stance

Prioritize missing information in this order:

1. task: `relax`, `static`, `dos`, `band`, or restart
2. material class: metal, semiconductor, insulator, magnetic system, correlated system, slab, or charged cell
3. reproducibility choices: PAW set, functional, `+U`, SOC, vdW treatment
4. runtime environment: scheduler, MPI launcher, scratch handling, and restart files

Never silently invent:

- `POTCAR` availability, version, or licensing
- `MAGMOM`, `LDAU*`, SOC, hybrid, or vdW settings
- whether a structure should be metallic or insulating when the evidence is weak
- a band path without a real source

## Workflow

### 1. Classify the request

- **Setup**: generate or edit VASP inputs and stage layout.
- **Review**: inspect an existing VASP directory and summarize status.
- **Recovery**: identify the likely failure mode and recommend the smallest safe restart.

### 2. Gather the minimum viable context

Before recommending settings, establish:

- structure source and whether the system is bulk, slab, or molecule-in-box
- target observable: relaxed geometry, total energy, DOS, or band structure
- pseudo policy and whether the project has a standard PAW set
- whether magnetism, correlation, SOC, or dispersion is relevant
- scheduler environment and expected walltime

### 3. Use the bundled helpers

- `scripts/make_vasp_inputs.py`
  Generate conservative `relax`, `static`, `dos`, `band`, or `optics` workflow skeletons.
- `scripts/check_vasp_job.py`
  Check one VASP directory or staged workflow root for missing files and restart dependencies.
- `scripts/summarize_vasp_run.py`
  Summarize a VASP run using `INCAR`, `OSZICAR`, and `OUTCAR`.
- `scripts/recommend_vasp_recovery.py`
  Turn incomplete or failed VASP runs into concrete restart and recovery guidance.
- `scripts/export_status_report.py`
  Export a shareable markdown status report from a VASP run or staged workflow.
- `scripts/export_input_suggestions.py`
  Export conservative VASP input snippets based on detected recovery patterns.

### 4. Load focused references only when needed

- VASP workflow and file guidance: `references/vasp.md`
- convergence planning: `references/convergence.md`
- VASP failures and restarts: `references/failure-modes.md`
- scheduler notes: `references/schedulers.md`

### 5. Deliver an auditable answer

Whenever you recommend edits or restarts, include:

- the assumed task and parent-child stage relationship
- unresolved physics choices the user must still confirm
- exact files changed or generated
- what output or artifact must exist before the next stage can run

## Guardrails

- Separate exploratory relaxation settings from production-quality final energies.
- DOS and band workflows are child calculations, not first calculations.
- If `ICHARG=11` or restart files are involved, say explicitly which parent artifacts are required.
- If the run is not reproducible because key metadata is missing, say so directly.

## Quality bar

- Prefer conservative defaults over flashy guesses.
- Distinguish VASP syntax advice from material-specific physics advice.
- Diagnose from the actual logs when logs are available.
