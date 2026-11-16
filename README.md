# Micronutrient Optimizer

A C++20 experiment in building a nutrient-dense salad that meets selected
micronutrient targets. It compares a sparse recipe with a more diverse one
and reports each salad with a fixed amount of roasted chicken.

## Why I built it

I began this project in June 2020, when my wife and I were planting a garden
during the early pandemic. I wanted to see whether ordinary foods could be
portioned into a salad that met basic vitamin and mineral targets while fitting
a Mediterranean-style ketogenic diet, without relying on a multivitamin.

This version revisits that idea with an explicit mathematical model, selected
USDA FoodData Central data, and a quadratic-programming solver. It reports net
carbohydrates, but does not impose a keto carbohydrate limit. Keto compatibility
is visible in the results; it is not guaranteed by the constraints.

## Historical context

Diet optimization has a long history in operations research. In 1945, George
Stigler studied the least-cost diet problem: selecting food quantities that
meet nutrient requirements at minimum cost. George Dantzig later described the
diet problem as an early demonstration of the simplex method. His broader
linear-programming work grew out of military planning problems. This project
uses the same general resource-allocation idea, but minimizes salad mass rather
than food cost.

## Recipe profiles and reports

- **Sparse:** ingredients may be omitted when the model does not need them.
- **Diverse:** each selected salad ingredient has a positive minimum portion.

Both profiles use the same nutrient targets, ingredient maximums, 700 kcal
salad limit, and fixed 258 g edible portion of roasted chicken leg quarter
(meat and skin). The chicken contributes to plate nutrients and calories, but
the calorie limit applies to the salad alone.

The program reports ingredient portions and bounds, salad and plate calories,
macronutrients, net carbohydrates, micronutrient totals and coverage, sodium
reference points, and OSQP diagnostics. Net carbohydrates are total
carbohydrate minus fiber. Macronutrients and sodium are reported but are not
optimization targets.

## Mathematical model

Let \(x\in\mathbb{R}^n\) be the vector of salad ingredient portions in grams.
Let \(A_{ji}\) be the amount of nutrient \(j\) in one gram of ingredient \(i\),
\(c_j\) the fixed chicken's amount of nutrient \(j\), \(r_j\) the configured
minimum for nutrient \(j\), and \(k_i\) the calories per gram of ingredient
\(i\). The vector \(\ell^{(p)}\) contains profile-specific lower bounds, and
\(u\) contains ingredient upper bounds.

The model minimizes salad mass with a small quadratic tie-breaker:

$$
\min_x \quad
\mathbf{1}^{\mathsf T}\frac{x}{1000}
+10^{-5}\left\|\frac{x}{1000}\right\|_2^2
$$

subject to the selected nutrient minimums:

$$
Ax+c\ge r,
$$

the salad calorie cap:

$$
k^{\mathsf T}x\le700,
$$

and the profile-specific portion bounds:

$$
\ell^{(p)}\le x\le u.
$$

There are 19 constrained micronutrient minimums. Sodium is tracked but is not
constrained. The sparse profile generally permits zero portions; the diverse
profile raises the lower bounds.

The objective is strictly convex and the constraints are linear, so the model
has a unique global minimizer. In exact arithmetic, a primal-dual point
satisfying the Karush–Kuhn–Tucker (KKT) conditions is globally optimal. The
solver operates in floating point, so its residuals provide numerical evidence,
not a symbolic proof.

### OSQP form

OSQP solves quadratic programs in the form

$$
\min_z\quad \frac{1}{2}z^{\mathsf T}Pz+q^{\mathsf T}z
\quad\text{subject to}\quad l\le Gz\le u.
$$

Here \(z=x/1000\) is the ingredient vector in kilograms,
\(P=2\cdot10^{-5}I\), and \(q=\mathbf{1}\). The constraint matrix \(G\)
stacks the nutrient, calorie, and ingredient-bound rows. Nutrient rows are
normalized by their targets; the calorie row is in kcal, and the portion rows
are in kg.

## Why OSQP?

OSQP is the sole optimizer used by this project. We chose it because its
primal and dual solutions, residuals, duality gap, and constraint multipliers
make the KKT conditions checkable. The multipliers also show which nutrient,
calorie, and portion constraints are active at the solution.

For this strictly convex quadratic program with linear constraints, an exact
primal-dual KKT point is globally optimal. OSQP's finite-precision residuals
provide numerical evidence for optimality, not a symbolic proof. This check
applies to the mathematical model; it does not validate food data or nutrition
assumptions.

## Reference results

These values are from `make compare`. The salad is capped at 700 kcal. The
fixed chicken portion contributes 474.72 kcal, making each whole plate
1,174.72 kcal.

### Ingredient portions

Salad quantities are grams. The chicken portion is fixed and is not optimized.

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
| **Salad mass** | **632.94 g** | **776.18 g** |
| Fixed chicken portion | 258.00 g | 258.00 g |

### Macronutrients for the whole plate

| Measure | Sparse | Diverse |
|---|---:|---:|
| Calories | 1,174.72 kcal | 1,174.72 kcal |
| Protein | 106.37 g | 106.99 g |
| Fat | 70.10 g | 69.85 g |
| Carbohydrate | 35.13 g | 37.20 g |
| Fiber | 21.59 g | 19.36 g |
| **Net carbohydrates** | **13.54 g** | **17.84 g** |

### Micronutrients for the whole plate

Coverage is relative to the configured target. Sodium is tracked, not
optimized, and has no target in the model.

| Nutrient | Unit | Target | Sparse total | Sparse coverage | Diverse total | Diverse coverage |
|---|---|---:|---:|---:|---:|---:|
| Calcium | mg | 1,000 | 1,000.00 | 100.00% | 1,000.00 | 100.00% |
| Copper | mg | 0.90 | 1.53 | 169.94% | 1.54 | 170.63% |
| Iron | mg | 8.00 | 17.95 | 224.32% | 15.55 | 194.35% |
| Magnesium | mg | 350 | 560.56 | 160.16% | 504.48 | 144.14% |
| Manganese | mg | 2.30 | 4.87 | 211.90% | 4.98 | 216.68% |
| Phosphorus | mg | 700 | 1,533.74 | 219.11% | 1,466.70 | 209.53% |
| Potassium | mg | 3,400 | 3,400.00 | 100.00% | 3,400.00 | 100.00% |
| Selenium | µg | 55 | 142.53 | 259.15% | 135.73 | 246.78% |
| Sodium (tracked) | mg | — | 925.50 | — | 833.60 | — |
| Zinc | mg | 11.00 | 12.40 | 112.72% | 12.24 | 111.25% |
| Vitamin B1 | mg | 1.20 | 1.20 | 100.00% | 1.20 | 100.00% |
| Vitamin B2 | mg | 1.30 | 2.06 | 158.54% | 2.13 | 163.97% |
| Vitamin B3 | mg | 16.00 | 25.13 | 157.07% | 25.34 | 158.36% |
| Vitamin B6 | mg | 1.30 | 2.40 | 184.67% | 2.63 | 202.59% |
| Vitamin B12 | µg | 2.40 | 2.40 | 100.00% | 2.40 | 100.00% |
| Vitamin A | µg RAE | 900 | 2,102.11 | 233.57% | 2,051.70 | 227.97% |
| Vitamin C | mg | 90 | 115.61 | 128.46% | 174.70 | 194.11% |
| Vitamin D | µg | 15 | 15.00 | 100.00% | 15.00 | 100.00% |
| Vitamin E | mg | 15 | 19.31 | 128.72% | 22.03 | 146.84% |
| Vitamin K | µg | 120 | 1,928.56 | 1,607.13% | 1,959.70 | 1,633.08% |

Both recipes meet the 19 configured nutrient minimums. Vitamin K is far above
its target; the model does not include nutrient upper limits. Sodium is below
the adult Adequate Intake reference of 1,500 mg and the Chronic Disease Risk
Reduction reference of 2,300 mg in both plates. These are dietary reference
points, not optimization constraints or deficiency tests.

### OSQP diagnostics

| Diagnostic | Sparse | Diverse |
|---|---:|---:|
| OSQP status | Solved (1) | Solved (1) |
| Objective (kg-equivalent) | 0.6329456562 | 0.7761824281 |
| Iterations | 4,375 | 1,975 |
| Primal residual (mixed row units) | 1.546e-16 | 1.457e-13 |
| Dual residual (kg-equivalent/kg) | 6.798e-15 | 1.636e-14 |
| Duality gap (kg-equivalent) | 9.821e-16 | -1.528e-15 |
| Relative KKT error (dimensionless) | 6.798e-15 | 1.457e-13 |

The primal residual combines dimensionless nutrient-target fractions, kcal for
the calorie row, and kg for the portion rows. The dual residual is in
kg-equivalent per kg of decision variable. Dual multipliers are in
kg-equivalent per corresponding constraint-row unit. These diagnostics are
numerical quantities subject to floating-point tolerances.

## Food data and scope

The model uses an embedded food-composition table based on selected USDA
FoodData Central records. Food records differ in form, nutrient coverage, and
source method; some values may be approximate or unreported in the selected
record. The optimizer treats its input coefficients as given. It does not
measure nutrients in food or resolve source-data uncertainty.

The model does not cover every nutrient in the Dietary Reference Intakes. Its
targets are not personalized by age, sex, pregnancy, or life stage. “Meets
target” means the modeled plate meets the values configured here; it does not
mean the plate is guaranteed to be nutritionally complete for every person.
This is an exploratory meal model, not medical nutrition advice.

## Build and run

On Debian or Ubuntu, install the system dependencies and build OSQP:

```sh
make install-dependencies

# Clone OSQP if ~/src/osqp does not already exist.
mkdir -p ~/src
git clone https://github.com/osqp/osqp.git ~/src/osqp
make install-osqp
```

Then build, run the tests, and compare both recipe profiles:

```sh
make test
make compare
```

Run one profile directly:

```sh
./build/diet_optimizer --sparse
./build/diet_optimizer --diverse
```

The default OSQP install prefix is `~/.local`. To use another prefix:

```sh
make compare OSQP_PREFIX=/opt/osqp
```

## References

For some fun historical background:

- George J. Stigler, [“The Cost of Subsistence”](https://doi.org/10.2307/1231810), *Journal of Farm Economics*, 1945.
- George B. Dantzig, [“The Diet Problem”](https://pubsonline.informs.org/doi/10.1287/inte.20.4.43), *Interfaces*, 1990.
- INFORMS, [George Dantzig oral history](https://www.informs.org/Explore/History-of-O.R.-Excellence/Oral-Histories/George-Dantzig), including his recollections of military planning and the diet-problem computation.
- B. Stellato, G. Banjac, P. Goulart, A. Bemporad, and S. Boyd, [“OSQP: An Operator Splitting Solver for Quadratic Programs”](https://doi.org/10.1007/s12532-020-00179-2), *Mathematical Programming Computation*, 2020.
- USDA, [FoodData Central downloadable datasets](https://fdc.nal.usda.gov/download-datasets/).
