# EPFL-internal prompt fix: before vs after

_28 EPFL-internal candidates from Spring 2025-26, 5 runs each, before vs after the prompt change clarifying that MTE applies the section-switcher 4.0 threshold (not 4.5)._

## Aggregate counts on the 28 EPFL-internals

| Source | accept | reject | waitlist | agree with committee |
| --- | --- | --- | --- | --- |
| Committee | 27 | 1 | 0 | — |
| System BEFORE (mode) | 13 | 8 | 7 | **14/28** (50%) |
| System AFTER (mode) | 15 | 7 | 6 | **15/28** (54%) |

## Per-candidate before / after

| Name | Committee | Before | Comp B | Comp A | After | Δcomp | Δdecision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Wieloch Sebastian | accept | accept ✓ | 9.85 | 9.85 | accept ✓ | +0.00 | → |
| Dällenbach Nolan Peter John | accept | accept ✓ | 9.11 | 9.32 | accept ✓ | +0.21 | → |
| Wakkach Khaoula | accept | accept ✓ | 9.03 | 9.03 | accept ✓ | +0.00 | → |
| Tiedra Mateo | accept | accept ✓ | 9.22 | 8.95 | accept ✓ | -0.27 | → |
| Al Hachem Marc | accept | accept ✓ | 8.89 | 8.88 | accept ✓ | -0.01 | → |
| Zaanouni Mélik | accept | accept ✓ | 8.89 | 8.88 | accept ✓ | -0.01 | → |
| Bruttin Marine | accept | accept ✓ | 8.21 | 8.88 | accept ✓ | +0.67 | → |
| Chambon Mazarine Marie | accept | accept ✓ | 8.53 | 8.57 | accept ✓ | +0.04 | → |
| Arseven Mehmet Riza | accept | accept ✓ | 8.23 | 8.50 | accept ✓ | +0.27 | → |
| Brunschwick Lucas Hugo | accept | accept ✓ | 8.37 | 8.43 | accept ✓ | +0.06 | → |
| Kim Seyoung | accept | accept ✓ | 8.88 | 8.35 | accept ✓ | -0.53 | → |
| Jacot Arthur | accept | accept ✓ | 8.12 | 8.12 | accept ✓ | +0.00 | → |
| Gousset Antoine Thomas Théophile | accept | accept ✓ | 8.40 | 7.90 | waitlist   | -0.50 | **FLIP** |
| Hegi Sébastien | accept | reject   | 7.59 | 7.83 | waitlist   | +0.24 | **FLIP** |
| Croisier Noé | accept | reject   | 7.18 | 7.45 | reject   | +0.27 | → |
| Maillard Etienne Franck Jean | accept | reject   | 6.77 | 7.45 | reject   | +0.68 | → |
| Kvedarauskaite Ieva | accept | reject   | 6.96 | 7.45 | reject   | +0.49 | → |
| Gruber Max Mann | accept | reject   | 7.08 | 7.22 | reject   | +0.14 | → |
| Nguyen Thi Thu Tra | accept | reject   | 5.92 | 6.92 | reject   | +1.00 | → |
| Holtz Sophie Thu Thuy | accept | reject   | 5.56 | 6.62 | reject   | +1.06 | → |
| Décréau Mathis Pablo | accept | waitlist   | 7.84 | 8.47 | accept ✓ | +0.63 | **FLIP** |
| Tirot Clémence Marie Henriette | accept | waitlist   | 7.78 | 8.42 | accept ✓ | +0.64 | **FLIP** |
| Ta Ngoc Minh Chau Alice | accept | waitlist   | 8.03 | 8.35 | accept ✓ | +0.32 | **FLIP** |
| Jariod Jeremy | accept | waitlist   | 7.46 | 7.97 | waitlist   | +0.51 | → |
| Tekaya Ismael | accept | waitlist   | 7.69 | 7.90 | waitlist   | +0.21 | → |
| Cunningham Sophie Louise | accept | waitlist   | 7.66 | 7.67 | waitlist   | +0.01 | → |
| Haenni Clement Guillaume | accept | waitlist   | 7.41 | 7.45 | reject   | +0.04 | **FLIP** |
| Biersohn Timothy Karl | reject | reject ✓ | 7.07 | 7.53 | waitlist   | +0.46 | **FLIP** |

## Outcome

- **Disagreements fixed by the prompt change:** 3
  - Ta Ngoc Minh Chau Alice: waitlist → accept (committee=accept)
  - Tirot Clémence Marie Henriette: waitlist → accept (committee=accept)
  - Décréau Mathis Pablo: waitlist → accept (committee=accept)
- **Newly introduced disagreements (regressions):** 2
  - Biersohn Timothy Karl: reject → waitlist (committee=reject)
  - Gousset Antoine Thomas Théophile: accept → waitlist (committee=accept)
- **Still disagreeing after fix:** 11
  - Nguyen Thi Thu Tra: reject → reject (committee=accept)
  - Hegi Sébastien: reject → waitlist (committee=accept)
  - Jariod Jeremy: waitlist → waitlist (committee=accept)
  - Cunningham Sophie Louise: waitlist → waitlist (committee=accept)
  - Croisier Noé: reject → reject (committee=accept)
  - Maillard Etienne Franck Jean: reject → reject (committee=accept)
  - Gruber Max Mann: reject → reject (committee=accept)
  - Holtz Sophie Thu Thuy: reject → reject (committee=accept)
  - Kvedarauskaite Ieva: reject → reject (committee=accept)
  - Tekaya Ismael: waitlist → waitlist (committee=accept)
  - Haenni Clement Guillaume: waitlist → reject (committee=accept)