# VASP Reference

Load this file when the request is VASP-specific or when you need code-specific guardrails.

## Minimum file sets

### Relax or static

- Required to run: `INCAR`, `POSCAR`, `KPOINTS`, `POTCAR`
- Inspect during review: `OUTCAR`, `OSZICAR`, `CONTCAR`, `vasprun.xml`

### DOS

- Parent calculation: converged `static` or dense `scf`-style step on a uniform mesh
- Child calculation: typically reuse `CHGCAR`; add DOS-specific output tags such as `NEDOS` or `LORBIT`
- Use denser k-point sampling than a loose geometry optimization

### Band structure

- Parent calculation: converged uniform-mesh SCF or static run
- Child calculation: line-mode `KPOINTS` generated from a real symmetry path
- Do not guess the path for a low-symmetry, distorted, magnetic, or slab structure

## Conservative defaults

These are workflow defaults, not universal truths.

### Cutoff and k-points

- `ENCUT` should never be lower than the relevant PAW recommendation for the chosen `POTCAR` set.
- For convergence studies, vary one knob at a time and keep structure, smearing, and spin treatment fixed.
- Slabs and molecules need anisotropic k-point meshes; do not copy a cubic bulk mesh into a vacuum cell.

### Smearing

- Metals: use a finite smearing method for relaxation and SCF-like steps; tighten for production numbers if needed.
- Semiconductors and insulators: use conservative smearing during relaxation when needed, but prefer tetrahedron-style DOS only after the charge density is trustworthy.
- Do not compare total energies across different smearing conventions without a deliberate reason.

### Spin and correlation

- Seed `MAGMOM` explicitly when the material might be magnetic.
- Do not invent `LDAU*` parameters. Use project conventions or literature-backed values.
- SOC, hybrids, and vdW corrections change cost and convergence behavior substantially; surface the tradeoff instead of hiding it.

## Workflow patterns

### Relax

Typical intent:

- move atoms to low forces
- optionally relax cell shape and volume

Watch for:

- `POTIM` too aggressive for fragile structures
- oscillatory ionic steps
- magnetic collapse caused by poor initialization

### Static

Typical intent:

- compute a final energy, charge density, DOS precursor, or comparison point on a fixed geometry

Watch for:

- geometry not actually converged
- k-point mesh inherited from a cheap relaxation
- accidental reuse of loose electronic thresholds

### DOS

Typical intent:

- reuse a converged charge density with denser sampling and output tags

Watch for:

- missing `CHGCAR`
- metal treated with tetrahedron settings meant for a gapful system
- too coarse a k-mesh producing jagged DOS

### Band

Typical intent:

- perform a read-only path calculation after a uniform-mesh parent

Watch for:

- line-mode path created from the wrong conventional cell
- accidental charge-density updates in the child step
- comparing bands from a structure that was never converged

## Restart guidance

- Prefer restarting from the smallest trustworthy artifact: `WAVECAR`, `CHGCAR`, or both.
- If the run failed because the charge density is suspect, reusing `CHGCAR` can preserve the problem.
- If a relaxation wandered into an unphysical geometry, inspect the structure before blindly restarting.
- Preserve a copy of the failing inputs before making recovery edits.

## Files worth reading first

- `INCAR` for intent and numerical settings
- `OSZICAR` for electronic-iteration counts and energy drift
- `OUTCAR` for completion, warnings, forces, stress, and error signatures
- `CONTCAR` versus `POSCAR` for geometry drift

## Common judgment calls

- If the system might be metallic, say so and explain why the smearing choice matters.
- If the user is comparing energies between polymorphs, insist on a consistent convergence protocol.
- If the request involves defects, surfaces, or charged cells, note that finite-size and electrostatic corrections may dominate the error budget.
