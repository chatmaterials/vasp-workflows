# VASP Failure Modes and Restarts

Load this file when a VASP run failed, stalled, or produced suspicious output.

## Recovery sequence

1. confirm whether the issue is physical, numerical, or scheduler-related
2. preserve the original inputs and key outputs before editing anything
3. change the fewest variables that plausibly address the failure
4. say explicitly whether the restart reuses `WAVECAR`, `CHGCAR`, geometry, or none of them

## Common patterns

### Electronic loop hits `NELM`

- inspect whether the structure, spin guess, or smearing choice is the real problem
- use more conservative mixing only after ruling out a bad starting model

### `BRMIX` or severe charge sloshing

- check whether the system is metallic, magnetic, or poorly initialized
- reduce aggressive mixing rather than piling on unrelated changes

### `ZHEGV`, diagonalization, or subspace failures

- inspect the geometry for atom overlap or corruption
- do not blindly reuse suspect restart data

### Ionic relaxation oscillates or diverges

- reduce ionic step aggressiveness
- inspect whether the structure or magnetic initialization is the real source of instability

## When to recommend a clean rerun

Recommend a fresh parent run when:

- the structure is obviously corrupted or unphysical
- the restart data itself is likely inconsistent or broken
- too many interacting settings changed at once to trust the current state
