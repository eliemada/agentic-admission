# EPFL-internal prompt fix: before vs after

_28 EPFL-internal candidates from Spring 2025-26, 5 runs each, before vs after the prompt change clarifying that MTE applies the section-switcher 4.0 threshold (not 4.5)._

## Aggregate counts on the 28 EPFL-internals

| Source | accept | reject | waitlist | agree with committee |
| --- | --- | --- | --- | --- |
| Committee | 27 | 1 | 0 | — |
| System BEFORE (mode) | 13 | 8 | 7 | **14/28** (50%) |
| System AFTER (mode) | 19 | 4 | 5 | **19/28** (68%) |

## Per-candidate before / after

| Name | Committee | Before | Comp B | Comp A | After | Δcomp | Δdecision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Wieloch Sebastian | accept | accept ✓ | 9.85 | 9.85 | accept ✓ | +0.00 | → |
| Dällenbach Nolan Peter John | accept | accept ✓ | 9.11 | 9.38 | accept ✓ | +0.27 | → |
| Wakkach Khaoula | accept | accept ✓ | 9.03 | 9.10 | accept ✓ | +0.07 | → |
| Tiedra Mateo | accept | accept ✓ | 9.22 | 8.98 | accept ✓ | -0.24 | → |
| Al Hachem Marc | accept | accept ✓ | 8.89 | 8.95 | accept ✓ | +0.06 | → |
| Bruttin Marine | accept | accept ✓ | 8.21 | 8.95 | accept ✓ | +0.74 | → |
| Zaanouni Mélik | accept | accept ✓ | 8.89 | 8.88 | accept ✓ | -0.01 | → |
| Chambon Mazarine Marie | accept | accept ✓ | 8.53 | 8.65 | accept ✓ | +0.12 | → |
| Kim Seyoung | accept | accept ✓ | 8.88 | 8.59 | accept ✓ | -0.29 | → |
| Brunschwick Lucas Hugo | accept | accept ✓ | 8.37 | 8.57 | accept ✓ | +0.20 | → |
| Arseven Mehmet Riza | accept | accept ✓ | 8.23 | 8.50 | accept ✓ | +0.27 | → |
| Gousset Antoine Thomas Théophile | accept | accept ✓ | 8.40 | 8.09 | accept ✓ | -0.30 | → |
| Jacot Arthur | accept | accept ✓ | 8.12 | 7.94 | accept ✓ | -0.18 | → |
| Croisier Noé | accept | reject   | 7.18 | 7.92 | waitlist   | +0.74 | **FLIP** |
| Hegi Sébastien | accept | reject   | 7.59 | 7.90 | waitlist   | +0.31 | **FLIP** |
| Maillard Etienne Franck Jean | accept | reject   | 6.77 | 7.60 | waitlist   | +0.83 | **FLIP** |
| Kvedarauskaite Ieva | accept | reject   | 6.96 | 7.44 | reject   | +0.48 | → |
| Gruber Max Mann | accept | reject   | 7.08 | 7.31 | reject   | +0.24 | → |
| Nguyen Thi Thu Tra | accept | reject   | 5.92 | 7.20 | reject   | +1.28 | → |
| Holtz Sophie Thu Thuy | accept | reject   | 5.56 | 7.17 | reject   | +1.61 | → |
| Décréau Mathis Pablo | accept | waitlist   | 7.84 | 8.47 | accept ✓ | +0.64 | **FLIP** |
| Ta Ngoc Minh Chau Alice | accept | waitlist   | 8.03 | 8.47 | accept ✓ | +0.44 | **FLIP** |
| Tirot Clémence Marie Henriette | accept | waitlist   | 7.78 | 8.42 | accept ✓ | +0.64 | **FLIP** |
| Jariod Jeremy | accept | waitlist   | 7.46 | 8.11 | accept ✓ | +0.65 | **FLIP** |
| Tekaya Ismael | accept | waitlist   | 7.69 | 8.05 | accept ✓ | +0.36 | **FLIP** |
| Cunningham Sophie Louise | accept | waitlist   | 7.66 | 7.93 | accept ✓ | +0.27 | **FLIP** |
| Haenni Clement Guillaume | accept | waitlist   | 7.41 | 7.75 | waitlist   | +0.34 | → |
| Biersohn Timothy Karl | reject | reject ✓ | 7.07 | 7.64 | waitlist   | +0.57 | **FLIP** |

## Outcome

- **Disagreements fixed by the prompt change:** 6
  - Jariod Jeremy: waitlist → accept (committee=accept)
  - Cunningham Sophie Louise: waitlist → accept (committee=accept)
  - Ta Ngoc Minh Chau Alice: waitlist → accept (committee=accept)
  - Tirot Clémence Marie Henriette: waitlist → accept (committee=accept)
  - Décréau Mathis Pablo: waitlist → accept (committee=accept)
  - Tekaya Ismael: waitlist → accept (committee=accept)
- **Newly introduced disagreements (regressions):** 1
  - Biersohn Timothy Karl: reject → waitlist (committee=reject)
- **Still disagreeing after fix:** 8
  - Nguyen Thi Thu Tra: reject → reject (committee=accept)
  - Hegi Sébastien: reject → waitlist (committee=accept)
  - Croisier Noé: reject → waitlist (committee=accept)
  - Maillard Etienne Franck Jean: reject → waitlist (committee=accept)
  - Gruber Max Mann: reject → reject (committee=accept)
  - Holtz Sophie Thu Thuy: reject → reject (committee=accept)
  - Kvedarauskaite Ieva: reject → reject (committee=accept)
  - Haenni Clement Guillaume: waitlist → waitlist (committee=accept)