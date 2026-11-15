# Diet Optimizer (C++20)

This project turns the selected ingredients from `salad2.py` into a constrained
recipe optimizer. It provides a sparse profile and a diverse profile so the
results can be compared under the same nutrient targets and calorie cap.

## Current model

- Salad ingredients are decision variables in grams, bounded by the table in
  `include/diet/food_data.hpp`.
- Salad calories are limited to 700 kcal. The fixed accompaniment is one USDA
  cooked roasted chicken leg portion with skin: 258 g edible (bone excluded).
  Its calories are reported separately and in the whole plate total.
- Each configured minimum is enforced on the combined salad and chicken
  nutrients. Vitamin B12 remains a target.
- Sodium is included in the reported totals but has no optimization constraint
  and does not affect the objective. The report compares the whole-plate total
  with the adult sodium Adequate Intake (AI, 1,500 mg/day) and Chronic Disease
  Risk Reduction (CDRR, 2,300 mg/day). These are reference points, not a
  deficiency test or a sodium upper limit; the National Academies did not set a
  sodium UL in its 2019 update.
- Protein, fat, total carbohydrate, fiber, and net carbs are reported for the
  salad, chicken, and whole plate. Net carbs are calculated as total
  carbohydrate minus fiber. These are not optimization constraints.
- Required micronutrient output includes target coverage percentage and signed
  margin from target. Selenium, B12, D, and K are displayed in micrograms so the
  small source values are readable.
- There are no blanket nutrient upper limits. The original `3 * rda_min`
  ceilings were arbitrary and made feasible recipes impossible. The program
  reports how far the recipe exceeds each minimum.
- The ingredient list adds UV-exposed mushrooms as a distinct candidate. Its
  vitamin D value is 28.4 µg/100 g; its other nutrient values currently reuse
  the raw white-mushroom row, so treat those values as an approximation.
- Egg bounds allow up to 150 g (about three large eggs) so the chicken and egg
  combination can reach the B12 target in this modeled plate.
- `--sparse` permits zero portions, so ingredients that do not help the
  minimum-mass objective may be omitted. `--diverse` requires at least a small
  portion of each of the original 16 salad ingredients, including chia, pine
  nuts, both original mushroom types, and a 50 g egg portion. UV-exposed
  portabella mushrooms remain an additional vitamin D source.

The program minimizes salad mass, with a small smooth term to make the solver's
choice stable when several mixes have similar mass. Each run reports the
objective value at the initial and final recipes, its absolute change and
relative change, final-minus-initial salad mass, and the solver status. It
separately classifies feasibility and optimizer convergence. The ingredient
audit prints each ingredient's group, chosen amount, and configured lower and
upper bound, plus the maximum bound violation. Current groups are leafy greens,
seeds, nuts, preferred vegetables, mushrooms, and eggs and dairy. An olives
group is reserved for candidate ingredients; no olive is currently in either
base recipe. The nutrient report compares sodium with the AI and CDRR reference
points. A `ROUNDOFF_LIMITED` feasible point is reported, but explicitly marked
as not having confirmed optimality.

Each run also solves the same convex quadratic program independently with
OSQP. Its recipe and objective are compared with NLopt's result. The OSQP audit
prints its solver status, primal and dual residuals, duality gap, relative KKT
error, iteration count, and the signed Lagrange multiplier for every nutrient,
calorie, and ingredient-bound row. Numerical residuals and the NLopt/OSQP
recipe difference are printed in scientific notation. Nutrient rows are
normalized by their targets, calorie rows by the salad calorie limit, and
ingredient variables are in kilograms; dual values therefore correspond to
those normalized rows. Under OSQP's convention, a negative multiplier
corresponds to an active lower bound and a positive multiplier to an active
upper bound.
Because the objective is strictly convex and all constraints are linear, an
exact primal-dual KKT point is a global optimum. OSQP reports numerical
residuals, so these diagnostics provide a numerical optimality check rather
than an exact symbolic proof. NLopt remains the primary recipe reported below.

## Optimizer results

`make compare` was run after changing the fixed accompaniment to one 258 g
cooked edible portion of roasted chicken leg with skin. The USDA measure
includes thigh, drumstick, and back meat with skin; bone is excluded. The run
used the generic 20 g per-ingredient initial guess, raised to diverse-profile
minimums where applicable. Those starting recipes were infeasible; both final
recipes passed the nutrient, calorie, and ingredient-bound checks.

| Ingredient (g) | Sparse | Diverse |
|---|---:|---:|
| Romaine lettuce | 0.00 | 30.00 |
| Collard greens | 0.00 | 20.00 |
| Spinach | 431.56 | 382.65 |
| Roma tomatoes | 0.00 | 30.00 |
| Cucumbers | 0.00 | 20.00 |
| Red onion | 0.00 | 10.00 |
| Pine nuts | 0.00 | 5.00 |
| Pumpkin seeds | 20.55 | 10.01 |
| Chia seeds | 2.05 | 5.00 |
| Sunflower seeds | 24.18 | 22.05 |
| Shiitake mushrooms | 0.00 | 10.00 |
| White button mushrooms | 0.00 | 10.00 |
| Broccoli | 0.00 | 20.00 |
| Bell pepper | 36.05 | 21.72 |
| Egg | 98.32 | 98.38 |
| Cheddar | 40.00 | 39.93 |
| UV-exposed portabella mushrooms | 43.45 | 43.02 |
| Roasted chicken leg with skin, edible portion | 258.00 | 258.00 |

| Result | Sparse | Diverse |
|---|---:|---:|
| Salad mass | 696.16 g | 777.75 g |
| Salad calories | 700 kcal | 700 kcal |
| Whole plate calories | 1,174.72 kcal | 1,174.72 kcal |
| Sodium (tracked; AI / CDRR) | 932.37 mg (62.2% / 40.5%) | 913.50 mg (60.9% / 39.7%) |

Whole-plate macronutrients:

| Macro (g) | Sparse | Diverse |
|---|---:|---:|
| Protein | 110.42 | 108.72 |
| Fat | 71.20 | 69.54 |
| Carbohydrate | 29.28 | 35.13 |
| Fiber | 15.54 | 17.26 |
| Net carbs | 13.74 | 17.87 |

Both profiles met all 19 enforced minimums, including 2.4 µg B12 and 15 µg
vitamin D. Calcium, potassium, B1, B12, C, and D are at their minimum targets.
The sparse recipe reaches the configured 40 g cheddar upper bound. Vitamin A
coverage is 291.76% (sparse) and 286.97% (diverse); vitamin K coverage remains
high at 1,787.42% and 1,706.72%, respectively, largely because both profiles
use substantial spinach. Nutrient upper limits are not part of this model.

| Solver diagnostic | Sparse | Diverse |
|---|---:|---:|
| NLopt status | Function tolerance reached (3) | Function tolerance reached (3) |
| Final feasibility | PASS | PASS |
| OSQP status | Solved (1) | Solved (1) |
| OSQP objective | 0.6961655055 | 0.7777515304 |
| Maximum NLopt/OSQP ingredient difference | 5.684e-14 g | 2.665e-13 g |
| OSQP primal residual | 1.567e-16 | 1.933e-16 |
| OSQP dual residual | 8.533e-15 | 1.311e-14 |
| OSQP relative KKT error | 8.533e-15 | 1.311e-14 |

The initial points were infeasible, so the objective increased while the
optimizer moved to feasible recipes. OSQP independently solved the same convex
quadratic program; the small residuals and close recipe match provide a strong
numerical optimality check for this model, not a formal exact-arithmetic proof.

## Data caveats

The original script's nutrient table and units have not been independently
audited. In particular, the target array is a simple fixed set and does not
vary by age, sex, pregnancy, or medical needs. This is an exploratory recipe
model, not a clinical diet plan.

The sodium reference points follow the National Academies' 2019 sodium and
potassium DRI update: adult sodium AI 1,500 mg/day and adult CDRR
2,300 mg/day. Sodium has no RDA and no UL under this update. See the
[National Academies sodium DRI summary](https://nap.nationalacademies.org/resource/25353/030519DRISodiumPotassium.pdf).

### USDA FoodData Central audit

The optimizer's hand-entered food table is preserved. `make audit-fooddata`
downloads the October 2026 full USDA FoodData Central CSV archive and April
2018 SR Legacy CSV archive, then compares every legacy calorie, macro, and
micronutrient value against the crosswalked records. It uses downloadable CSVs
only; no API key or API call is needed. The full archive is about 463 MB
compressed and contains the food descriptions and nutrient tables missing from
the small Foundation-only archive. The audit streams the needed tables from the
ZIP without unpacking the roughly 3.1 GB dataset. The archives are ignored by
Git. Download scripts validate required table members and record local SHA-256
checksums beside the archives; SR Legacy is checked against its pinned SHA-256.

The selection policy is **Foundation Foods first, SR Legacy fallback per
nutrient**. Foundation Foods is based on individual analytical samples and can
show sample variability; where multiple suitable samples are selected in the
crosswalk, the audit reports their arithmetic mean, sample count, minimum, and
maximum. If those samples do not report a nutrient, the audit uses the mapped
SR Legacy value for that nutrient. If neither source reports it, the result is
`not_reported`, never zero. Every output row records which source supplied the
value, FDC IDs, release, derivation/source metadata, and the reason for any
fallback. The report is written to
`data/reports/fooddata_priority_audit.csv`. The audit never updates the
optimizer's data table automatically.

Foundation Foods IDs are deliberately blank in the checked-in crosswalk until
the matching records have been reviewed. Start with `make foundation-candidates`;
this downloads the full archive and writes a keyword-generated candidate list
of Foundation records to `data/reports/foundation_food_candidates.csv`. These
are suggestions, not asserted matches. Review the food form and description, then fill
`foundation_fdc_ids`, `foundation_description`, `foundation_identity_match`,
and `foundation_selection_note` in
`data/fooddata_central_sr_legacy_crosswalk.csv`. Use semicolon-separated IDs
when deliberately selecting several samples of the same food description.
Until a reviewed Foundation mapping is entered, the report will use SR Legacy
fallback values and say why.

The SR Legacy crosswalk is retained as the fallback and historical comparison.
Some SR records are approximate identity matches: generic raw tomato for Roma
tomatoes, generic raw onion for red onion, and sharp sliced cheddar for
unspecified cheddar. The UV-exposed portabella record is an exact food match,
but the optimizer's old row reuses white-mushroom values for most nutrients.
The earlier audit also found a large pine-nut vitamin K discrepancy (0.54 vs
53.9 µg/100 g) and substantial shiitake differences. These should be reviewed
at the ingredient/nutrient level before changing optimizer values.

Foundation Foods is updated regularly and SR Legacy is a frozen April 2018
release. A newer record is not automatically a better match: the food form,
sample selection, nutrient coverage, and units still need review. The
crosswalk and release information make each comparison reproducible.

Vitamin A is reported as retinol activity equivalents (RAE). The legacy
plant-food IU values were previously converted with the retinol factor; they
now use 0.05 µg RAE per IU for dietary beta-carotene, while the egg and cheddar
entries retain the retinol-based conversion from the source table. This is a
source-class approximation; USDA RAE values should replace the legacy IU data
as the broader food table is audited.

The chicken values use USDA SR Legacy chicken leg, meat and skin, cooked,
roasted (FDC ID 173617; NDB 05078). The fixed 258 g is USDA's edible-portion
measure for one leg with skin, including thigh, drumstick, and back; bone is
excluded. A physical bone-in leg quarter's scale weight will be higher. This is
the closest USDA serving match to the stated accompaniment, rather than an
assumption that the 199 g meat-only portion also includes skin. The UV
mushroom vitamin D value is from USDA SR28 portabella mushrooms exposed to
ultraviolet light.

Sources:

- [NIH ODS: Vitamin A IU-to-RAE conversion factors](https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/)
- [USDA SR20: RAE conversion methods for plant and animal foods](https://www.ars.usda.gov/ARSUserFiles/80400525/Data/SR20/SR20_doc.pdf)
- [USDA SR28: chicken leg, meat and skin, cooked, roasted](https://www.ars.usda.gov/ARSUserFiles/80400535/Data/SR/SR28/reports/sr28fg05.pdf)
- [USDA SR28: UV-exposed portabella mushrooms](https://www.ars.usda.gov/ARSUserFiles/80400535/Data/SR/SR28/reports/sr28fg11.pdf)
- [NIH ODS: Vitamin D food sources and adult recommended amounts](https://ods.od.nih.gov/factsheets/VitaminD-Consumer/)
- [NIH ODS: Vitamin B12 sources, including poultry, eggs, and dairy](https://ods.od.nih.gov/factsheets/VitaminB12-Consumer/)

## Build

Requires a C++20 compiler, CMake 3.20+, pkg-config, NLopt with its C++
interface, and OSQP 1.x. On Debian or Ubuntu, install the system packages and
clone OSQP as in the setup commands below:

```sh
make install-dependencies
mkdir -p ~/src
git clone https://github.com/osqp/osqp.git ~/src/osqp
make install-osqp
make compare
```

`make install-dependencies` uses `sudo apt-get` to install system packages.
`make install-osqp` installs OSQP under `~/.local` and can be rerun after
updating the checkout. Override `OSQP_SOURCE` or `OSQP_PREFIX` when using
different paths. `make compare` builds and runs both profiles. Use `make run-sparse` or
`make run-diverse` to run one profile. The CMake project discovers
Ubuntu/Debian's `nlopt_cxx` pkg-config module and the OSQP CMake config package.
