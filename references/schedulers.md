# Scheduler Guidance

Load this file when the task involves Slurm, PBS, walltime planning, or restart-safe job scripts.

## Principles

- Keep the scheduler layer separate from the physics choices.
- Log stdout and stderr to stable filenames.
- Stage restart-relevant files deliberately if the cluster uses scratch storage.
- Preserve a clear mapping between workflow stage and scheduler job name.

## Slurm checks

Before submitting, verify:

- `--nodes`, `--ntasks-per-node`, and `--cpus-per-task` match the code and MPI/OpenMP launch strategy
- `--time`, `--partition`, and `--account` are valid on the cluster
- the launcher matches the site convention, usually `srun` or `mpirun`
- module loading or environment activation is explicit

## PBS checks

Before submitting, verify:

- `select`, `ncpus`, `mpiprocs`, and walltime match the code's parallel layout
- the script changes into the submission directory or intended work directory
- the launcher matches the site convention

## Restart-safe habits

- Write scheduler output into the calculation directory, not a transient working directory.
- Avoid deleting `WAVECAR`, `CHGCAR`, or QE scratch trees until the dependent stage is complete.
- For multi-stage workflows, keep stage-specific directories such as `01-scf`, `02-dos`, or `02-band`.
- If the site uses node-local scratch, copy restart-relevant artifacts back before the job ends.

## What the bundled generators do

- generate plain Slurm or PBS scripts with explicit resource requests
- leave module lines editable rather than guessing the cluster's module names
- keep the execution command visible and easy to patch

The generated scripts are safe starting points, not cluster-specific truth.
