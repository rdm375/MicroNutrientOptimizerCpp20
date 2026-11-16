# Micronutrient Optimizer

A C++20 experiment in building a nutrient-dense salad that meets selected
micronutrient targets. The model compares a sparse recipe with a more diverse
one and reports the full plate with a fixed roasted chicken accompaniment.

## Why I built it

I originally did this work back in June 2020. The pandemic was just getting started and my wife and I were planting a garden. I was curious if there was a way to portion out salad ingredients, consistent a Mediterranean-style ketogenic diet, that met basic RDI vitamin requirements using basic foods and not relying on multivitamins.

This version improves that experiment with explicit portion bounds,
food-composition data, macro and net-carb reporting, and an independent
quadratic-program audit. The current program models one salad plus a fixed
chicken leg quarter. It reports net carbs, but it does not impose a ketogenic
carbohydrate ceiling; keto compatibility is visible in the results, not
guaranteed by the constraints.

## Historical context

The project belongs to a long tradition of resource-allocation models. In
1945, George Stigler published a least-cost subsistence diet study: choose food
quantities that meet nutrient requirements while minimizing cost. George
Dantzig later recounted how the simplex method was tested on Stigler's diet
problem in 1947. Dantzig's wider linear-programming work grew from military
planning problems. This project's connection is mathematical; it is not a
replication of military menu or ration planning.

The classic diet problem minimized cost. This model minimizes salad mass while
requiring the combined salad and chicken plate to meet selected nutrient
targets.

## Profiles and reports

- **Sparse:** ingredients may be omitted when they are not needed by the
  objective or constraints.
- **Diverse:** every selected salad ingredient has a positive minimum portion.

Both profiles use the same nutrient targets, 700 kcal salad limit, ingredient
maximums, and fixed 258 g edible portion of roasted chicken leg with skin.
Chicken calories and nutrients count toward the plate totals and nutrient
targets. The 700 kcal cap applies to the salad alone.

The program reports ingredient amounts and bounds, salad and plate calories,
protein, fat, carbohydrate, fiber, net carbs, micronutrient totals and
coverage, sodium reference points, and solver diagnostics. Net carbs are total
carbohydrate minus fiber. Macros and sodium are reported but not optimized.

## Mathematical model

Let \(x_i\) be grams of salad ingredient \(i\); \(a_{ji}\) its amount of
nutrient \(j\) per gram; and \(e_i\) its calories per gram. Let \(c_j\) be
the fixed chicken's amount of nutrient \(j\), \(r_j\) the configured nutrient
minimum, and \(K=700\) kcal the salad limit.

The objective is salad mass plus a small quadratic tie-breaker:

$$
\min_x\quad \sum_i \frac{x_i}{1000}
+10^{-5}\sum_i\left(\frac{x_i}{1000}\right)^2
$$

subject to nutrient minimums

$$
c_j+\sum_i a_{ji}x_i\ge r_j
\quad (j\text{ in the 19 constrained nutrients}),
$$

the salad calorie cap

$$
\sum_i e_i x_i\le K,
$$

and profile-specific portion bounds

$$
\ell_i\le x_i\le u_i.
$$

The sparse profile generally permits zero portions; the diverse profile raises
the lower bounds. Sodium is tracked but is not a constrained nutrient.

The objective is strictly convex and the constraints are linear, so this is a
convex quadratic program with a unique global minimizer. In exact arithmetic,
a point satisfying the KKT conditions is globally optimal. The solvers operate
in floating point, so the reported residuals are numerical checks, not a
symbolic proof.

## Why two solvers?

NLopt's SLSQP algorithm produces the primary recipe. OSQP independently solves
the same quadratic program from the same initial recipe. OSQP stands for
**Operator Splitting Quadratic Program**; it is a solver for convex QPs based
on an operator-splitting/ADMM method. Its primal and dual residuals, duality
gap, and constraint multipliers let us check the numerical solution and
inspect which constraints are active. Agreement checks the optimization
formulation and solver results; it does not validate the food data or nutrition
assumptions.

## Reference results

These values are from `make compare`. The salad is capped at 700 kcal. The
fixed chicken portion contributes 474.72 kcal, making each whole plate
1,174.72 kcal.

### Ingredient portions

Salad quantities are grams. Chicken is fixed and not optimized.

| Ingredient | Sparse | Diverse |
|---|---:|---:|
| Romaine lettuce | 0.00 | 30.00 |
| Collard greens | 32.97 | 144.14 |
| Spinach | 367.15 | 260.42 |
| Roma tomatoes | 0.00 | 30.00 |
| Cucumbers | 0.00 | 20.00 |
| Red onion | 0.00 | 10.00 |
| Pine nuts | 0.00 | 5.00 |
| Pumpkin seeds | 0.00 | 5.00 |
| Chia seeds | 27.17 | 5.00 |
| Sunflower seeds | 26.51 | 29.93 |
| Shiitake mushrooms | 0.00 | 10.00 |
| White button mushrooms | 0.00 | 10.00 |
| Broccoli | 0.00 | 20.00 |
| Bell pepper | 0.00 | 20.00 |
| Egg | 95.47 | 100.44 |
| Cheddar | 40.00 | 33.03 |
| UV-exposed portabella mushrooms | 43.67 | 43.22 |
| **Salad mass** | **632.94** | **776.18** |
| Fixed chicken portion | 258.00 | 258.00 |

### Macronutrients for the whole plate

| Macro | Sparse | Diverse |
|---|---:|---:|
| Calories | 1,174.72 kcal | 1,174.72 kcal |
| Protein | 106.37 g | 106.99 g |
| Fat | 70.10 g | 69.85 g |
| Carbohydrate | 35.13 g | 37.20 g |
| Fiber | 21.59 g | 19.36 g |
| **Net carbs** | **13.54 g** | **17.84 g** |

### Micronutrients for the whole plate

Coverage is relative to the configured target. Sodium is tracked, not
optimized, and has no target in the model.

| Nutrient | Target | Sparse total | Sparse coverage | Diverse total | Diverse coverage |
|---|---:|---:|---:|---:|---:|
| Calcium | 1,000 mg | 1,000.00 mg | 100.00% | 1,000.00 mg | 100.00% |
| Copper | 0.90 mg | 1.53 mg | 169.94% | 1.54 mg | 170.63% |
| Iron | 8.00 mg | 17.95 mg | 224.32% | 15.55 mg | 194.35% |
| Magnesium | 350 mg | 560.56 mg | 160.16% | 504.48 mg | 144.14% |
| Manganese | 2.30 mg | 4.87 mg | 211.90% | 4.98 mg | 216.68% |
| Phosphorus | 700 mg | 1,533.74 mg | 219.11% | 1,466.70 mg | 209.53% |
| Potassium | 3,400 mg | 3,400.00 mg | 100.00% | 3,400.00 mg | 100.00% |
| Selenium | 55 µg | 142.53 µg | 259.15% | 135.73 µg | 246.78% |
| Sodium (tracked) | — | 925.50 mg | — | 833.60 mg | — |
| Zinc | 11.00 mg | 12.40 mg | 112.72% | 12.24 mg | 111.25% |
| Vitamin B1 | 1.20 mg | 1.20 mg | 100.00% | 1.20 mg | 100.00% |
| Vitamin B2 | 1.30 mg | 2.06 mg | 158.54% | 2.13 mg | 163.97% |
| Vitamin B3 | 16.00 mg | 25.13 mg | 157.07% | 25.34 mg | 158.36% |
| Vitamin B6 | 1.30 mg | 2.40 mg | 184.67% | 2.63 mg | 202.59% |
| Vitamin B12 | 2.40 µg | 2.40 µg | 100.00% | 2.40 µg | 100.00% |
| Vitamin A | 900 µg RAE | 2,102.11 µg RAE | 233.57% | 2,051.70 µg RAE | 227.97% |
| Vitamin C | 90 mg | 115.61 mg | 128.46% | 174.70 mg | 194.11% |
| Vitamin D | 15 µg | 15.00 µg | 100.00% | 15.00 µg | 100.00% |
| Vitamin E | 15 mg | 19.31 mg | 128.72% | 22.03 mg | 146.84% |
| Vitamin K | 120 µg | 1,928.56 µg | 1,607.13% | 1,959.70 µg | 1,633.08% |

Both recipes met the 19 configured nutrient minimums. Vitamin K is far above
its target; nutrient upper limits are not part of this model. Sodium is
925.50 mg in the sparse plate and 833.60 mg in the diverse plate. Both values
are below the adult Adequate Intake reference of 1,500 mg and the Chronic
Disease Risk Reduction reference of 2,300 mg; these are reference points, not
optimization constraints.

### Numerical solver check

| Diagnostic | Sparse | Diverse |
|---|---:|---:|
| NLopt status | Function tolerance reached (3) | Function tolerance reached (3) |
| Final feasibility | Pass | Pass |
| OSQP status | Solved (1) | Solved (1) |
| OSQP objective | 0.6329456562 | 0.7761824281 |
| Maximum NLopt/OSQP ingredient difference | 6.253e-13 g | 2.842e-13 g |
| OSQP iterations | 4,375 | 1,975 |
| Primal residual | 1.546e-16 | 1.457e-13 |
| Dual residual | 6.798e-15 | 1.636e-14 |
| Duality gap | 9.821e-16 | -1.528e-15 |
| Relative KKT error | 6.798e-15 | 1.457e-13 |

These run-specific diagnostics show that both solvers found essentially the
same recipe and objective. Residuals are numerical quantities subject to
floating-point tolerances.

## Food data and scope

The model uses an embedded food-composition table based on selected USDA
FoodData Central records, including SR Legacy records. USDA provides
downloadable CSV and JSON data. Food records differ in food form, nutrient
coverage, and source method; some modeled values may be approximate or
unreported in the selected record. The optimizer treats its input coefficients
as given; it does not measure food or resolve source-data uncertainty.

The model enforces 19 selected micronutrient minimums. It does not cover every
nutrient in the Dietary Reference Intakes, and its configured targets are not
personalized by age, sex, pregnancy, or life stage. “Meets target” means the
modeled plate meets the values configured here, not that it is guaranteed to
be nutritionally complete for every person. This is an exploratory meal model,
not medical nutrition advice.

## Build and run

On Debian or Ubuntu, install system dependencies and build OSQP:

```sh
make install-dependencies

# Clone OSQP if ~/src/osqp does not already exist.
mkdir -p ~/src
git clone https://github.com/osqp/osqp.git ~/src/osqp
make install-osqp
```

Then build, run the tests, and compare both recipes:

```sh
make test
make compare
```

Run one profile directly:

```sh
./build/diet_optimizer --sparse
./build/diet_optimizer --diverse
```

The default OSQP prefix is `~/.local`. To use another installation prefix:

```sh
make compare OSQP_PREFIX=/opt/osqp
```

## References

- George J. Stigler, “[The Cost of Subsistence](https://onlinelibrary.wiley.com/doi/10.2307/1231810),” *Journal of Farm Economics*, 1945.
- George B. Dantzig, “[The Diet Problem](https://pubsonline.informs.org/doi/10.1287/inte.20.4.43),” *Interfaces*, 1990.
- INFORMS, “[George Dantzig oral history](https://www.informs.org/Explore/History-of-O.R.-Excellence/Oral-Histories/George-Dantzig),” including his recollections of military planning and the diet-problem computation.
- B. Stellato, G. Banjac, P. Goulart, A. Bemporad, and S. Boyd, “[OSQP: An Operator Splitting Solver for Quadratic Programs](https://web.stanford.edu/~boyd/papers/osqp.html),” *Mathematical Programming Computation*, 2020.
- USDA, “[FoodData Central downloadable datasets](https://fdc.nal.usda.gov/download-datasets/).”
