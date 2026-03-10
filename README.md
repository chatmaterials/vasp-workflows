# vasp-workflows

[![CI](https://img.shields.io/github/actions/workflow/status/chatmaterials/vasp-workflows/ci.yml?branch=main&label=CI)](https://github.com/chatmaterials/vasp-workflows/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/chatmaterials/vasp-workflows?display_name=tag)](https://github.com/chatmaterials/vasp-workflows/releases)

Standalone skill for practical VASP workflow setup, review, convergence checks, and restart handling.

## What This Skill Covers

- `relax`, `static`, `dos`, `band`, and `optics` workflow skeletons
- directory checks for missing `POSCAR`, `POTCAR`, `KPOINTS`, `CHGCAR`, and staged dependencies
- quick summaries from `INCAR`, `OSZICAR`, and `OUTCAR`
- recovery recommendations for incomplete or unstable runs
- conservative scheduler-script generation for Slurm and PBS

## What It Does Not Do

- it does not generate `POTCAR`
- it does not guess `MAGMOM`, `LDAU*`, SOC, hybrid, or vdW settings without explicit context
- it does not fabricate a band path for unknown structures

## Install

```bash
npx skills add chatmaterials/vasp-workflows -g -y
```

## Local Validation

```bash
python3 -m py_compile scripts/*.py
npx skills add . --list
python3 scripts/make_vasp_inputs.py /tmp/vasp-test --task dos --scheduler none
python3 scripts/check_vasp_job.py /tmp/vasp-test
python3 scripts/recommend_vasp_recovery.py fixtures/incomplete-nelm
python3 scripts/export_recovery_plan.py fixtures/incomplete-nelm
python3 scripts/export_status_report.py fixtures/incomplete-nelm
python3 scripts/export_input_suggestions.py fixtures/incomplete-nelm
python3 scripts/run_regression.py
```

## First Release Checklist

1. Initialize a fresh repository from this directory.
2. Run the local validation commands from this directory.
3. Commit the repo root as the first release candidate.
4. Tag the first release, for example `v0.1.0`.

## Suggested First Commit

```bash
git init
git add .
git commit -m "Initial release of vasp-workflows"
git tag v0.1.0
```
