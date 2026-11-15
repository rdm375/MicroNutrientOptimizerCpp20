# Diet Optimizer (C++20)

This project turns the selected ingredients from `salad2.py` into a constrained
recipe optimizer. It provides a sparse profile and a diverse profile so the
results can be compared under the same nutrient targets and calorie cap.

## Current model

- Salad ingredients are decision variables in grams, bounded by the table in
  `include/diet/food_data.hpp`.
- Salad calories are limited to 700 kcal. Chicken is a fixed 199 g cooked
  edible portion and its calories are reported separately and in the whole
  plate total.
- Each configured minimum is enforced on the combined salad and chicken
  nutrients. Vitamin B12 remains a target.
- Sodium is included in the reported totals but has no minimum constraint and
  does not affect the objective.
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
audit prints the chosen amount and configured lower and upper bound for every
ingredient, plus the maximum bound violation. A `ROUNDOFF_LIMITED` feasible
point is reported, but explicitly marked as not having confirmed optimality.

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

## Feasible recipes from the current data

Independent linear programs against the current table found these minimum-mass
reference recipes. The C++ optimizer starts from a generic 20 g per-ingredient
guess (raised to any diverse-profile minimums), so its output can be compared
with these references instead of being seeded with the answer.

| Ingredient | Sparse | Diverse |
|---|---:|---:|
| Romaine lettuce | — | 30 g |
| Collard greens | — | 20 g |
| Spinach | 466 g | 416 g |
| Roma tomatoes | — | 30 g |
| Cucumber | — | 20 g |
| Red onion | — | 10 g |
| Pine nuts | — | 5 g |
| Pumpkin seeds | 16 g | 6 g |
| Chia seeds | — | 5 g |
| Sunflower seeds | 26 g | 24 g |
| Shiitake mushrooms | — | 10 g |
| White button mushrooms | — | 10 g |
| Broccoli | — | 20 g |
| Bell pepper | 33 g | 20 g |
| Egg | 121 g | 122 g |
| Cheddar | 35 g | 33 g |
| UV-exposed portabella mushrooms | 42 g | 42 g |
| Cooked chicken leg meat, served alongside | 199 g | 199 g |

| Result | Sparse | Diverse |
|---|---:|---:|
| Salad weight | 740 g | 822 g |
| Salad calories | 700 kcal | 700 kcal |
| Whole plate calories | 1,046 kcal | 1,046 kcal |
| Sodium, tracked only | 896 mg | 868 mg |

Estimated macronutrient profile:

| Macro (g) | Sparse salad | Diverse salad | Chicken | Sparse plate | Diverse plate |
|---|---:|---:|---:|---:|---:|
| Protein | 49.73 | 47.91 | 48.20 | 97.93 | 96.11 |
| Fat | 47.19 | 45.28 | 15.52 | 62.71 | 60.80 |
| Carbohydrate | 29.69 | 36.24 | 0.00 | 29.69 | 36.24 |
| Fiber | 15.53 | 17.88 | 0.00 | 15.53 | 17.88 |
| Net carbs | 14.16 | 18.36 | 0.00 | 14.16 | 18.36 |

Both profiles meet all 19 enforced minimums in the current composition table,
including 2.4 µg B12 and 15 µg vitamin D. The diverse profile includes every
original salad ingredient; the sparse profile omits ingredients when the
optimizer assigns them zero. These recipes depend on UV-treated mushrooms and
the assumed chicken and egg portions; ordinary button mushrooms do not have
the modeled vitamin D content.

After correcting the plant-food vitamin A conversion, the current sparse and
diverse profiles provide about 2,787 and 2,739 µg RAE, respectively (about
310% and 304% of the model's 900 µg RAE target). The large spinach portions
are the main contributor.

## Data caveats

The original script's nutrient table and units have not been independently
audited. In particular, the target array is a simple fixed set and does not
vary by age, sex, pregnancy, or medical needs. This is an exploratory recipe
model, not a clinical diet plan.

Vitamin A is reported as retinol activity equivalents (RAE). The legacy
plant-food IU values were previously converted with the retinol factor; they
now use 0.05 µg RAE per IU for dietary beta-carotene, while the egg and cheddar
entries retain the retinol-based conversion from the source table. This is a
source-class approximation; USDA RAE values should replace the legacy IU data
as the broader food table is audited.

The chicken values are based on USDA SR Legacy chicken leg, meat only, cooked,
roasted, scaled to 199 g edible portion. A bone-in leg quarter weighs more;
the portion here is the estimated edible meat amount. The UV mushroom vitamin D
value is from USDA SR28 portabella mushrooms exposed to ultraviolet light.

Sources:

- [NIH ODS: Vitamin A IU-to-RAE conversion factors](https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/)
- [USDA SR20: RAE conversion methods for plant and animal foods](https://www.ars.usda.gov/ARSUserFiles/80400525/Data/SR20/SR20_doc.pdf)
- [USDA SR28: chicken leg, meat only, cooked, roasted](https://www.ars.usda.gov/ARSUserFiles/80400535/Data/SR/SR28/reports/sr28fg05.pdf)
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
