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
- Protein, fat, carbohydrate, and fiber are reported for the salad, chicken,
  and whole plate. They are not optimization constraints.
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
choice stable when several mixes have similar mass. `ROUNDOFF_LIMITED` is
accepted only if the returned recipe passes an explicit feasibility check.

## Feasible recipes from the current data

Independent linear feasibility solves against the same table found these
recipes. The C++ optimizer uses them as feasible starting points and may adjust
amounts slightly.

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

Both profiles meet all 19 enforced minimums in the current composition table,
including 2.4 µg B12 and 15 µg vitamin D. The diverse profile includes every
original salad ingredient; the sparse profile omits ingredients when the
optimizer assigns them zero. These recipes depend on UV-treated mushrooms and
the assumed chicken and egg portions; ordinary button mushrooms do not have
the modeled vitamin D content.

## Data caveats

The original script's nutrient table and units have not been independently
audited. In particular, the target array is a simple fixed set and does not
vary by age, sex, pregnancy, or medical needs. This is an exploratory recipe
model, not a clinical diet plan.

The chicken values are based on USDA SR Legacy chicken leg, meat only, cooked,
roasted, scaled to 199 g edible portion. A bone-in leg quarter weighs more;
the portion here is the estimated edible meat amount. The UV mushroom vitamin D
value is from USDA SR28 portabella mushrooms exposed to ultraviolet light.

Sources:

- [USDA SR28: chicken leg, meat only, cooked, roasted](https://www.ars.usda.gov/ARSUserFiles/80400535/Data/SR/SR28/reports/sr28fg05.pdf)
- [USDA SR28: UV-exposed portabella mushrooms](https://www.ars.usda.gov/ARSUserFiles/80400535/Data/SR/SR28/reports/sr28fg11.pdf)
- [NIH ODS: Vitamin D food sources and adult recommended amounts](https://ods.od.nih.gov/factsheets/VitaminD-Consumer/)
- [NIH ODS: Vitamin B12 sources, including poultry, eggs, and dairy](https://ods.od.nih.gov/factsheets/VitaminB12-Consumer/)

## Build

Requires a C++20 compiler, CMake 3.20+, pkg-config, and NLopt with its C++
interface. On Debian or Ubuntu:

```sh
make install-dependencies
make compare
```

`make install-dependencies` uses `sudo apt-get` to install system packages.
`make compare` builds and runs both profiles. Use `make run-sparse` or
`make run-diverse` to run one profile. The CMake project discovers
Ubuntu/Debian's `nlopt_cxx` pkg-config module.
