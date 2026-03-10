# Convergence Planning

Load this file when the task is to design, review, or defend a convergence protocol.

## Order of operations

Change one high-impact choice at a time:

1. Fix the physics model: functional, pseudo family, spin treatment, `+U`, SOC, dispersion correction.
2. Converge basis controls: `ENCUT` or `ecutwfc` and the corresponding density cutoff.
3. Converge k-point sampling on the fixed basis.
4. Revisit smearing or occupation settings only after the system class is clear.
5. Tighten electronic and ionic thresholds for production runs.

Do not mix several moving targets in one convergence plot.

## What to keep fixed

For defensible comparisons, keep these fixed while testing one parameter:

- structure and cell
- pseudopotential family
- spin state and magnetic initialization
- parallel layout if it materially changes numerical noise
- post-processing method

## Practical stopping criteria

Use property-driven criteria, not arbitrary folklore:

- total energies: stable to the tolerance needed for the comparison being made
- forces: stable enough that the relaxed geometry stops changing meaningfully
- DOS or band edges: stable to the plotting or interpretation tolerance
- stress and lattice constants: stable enough for the target equation-of-state or elastic workflow

The tighter the target observable, the tighter the convergence requirement.

## Workflow-specific guidance

### Geometry optimization

- Start with a numerically sane but not maximal setup.
- Once the structure is close to converged, rerun a tighter static calculation if final energies matter.

### Relative energies

- Use the same protocol across all structures.
- Inconsistent smearing, k-point density, or spin treatment can dominate small energy differences.

### DOS and bands

- Converge the parent SCF calculation first.
- Then test denser k-point sampling in the child workflow if the spectra look jagged or shift visibly.

## High-risk cases

Be extra explicit when the system is:

- metallic or near-gapless
- magnetic or spin-state sensitive
- a surface, defect supercell, molecule in a box, or charged system
- strongly correlated or dependent on `+U`, hybrids, or SOC

In these cases, "default" convergence recipes are often not transferable.
