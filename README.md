# Diet Optimizer (C++20)

A first C++20 port of the constrained food-mix optimizer in `salad2.py`.
It keeps the original food table and the effective optimization model, then
prints the optimizer status, ingredient amounts, calories, and nutrient totals.

## Model carried over from the Python script

- Decision variables are grams of each selected ingredient.
- The objective minimizes squared absolute error from a target of twice each
  `rda_min` value. Squaring the original Euclidean norm preserves its minimizer
  while giving the optimizer a smooth objective.
- Every modeled nutrient is constrained to `[rda_min, 3 * rda_min]`, matching
  the bounds that `salad2.py` actually used.
- Calories are capped at 700 kcal.
- Per-ingredient gram bounds are copied from `srv_bnd`.
- The source's `rda_max` table and `wt_max` variable were not active constraints
  in the Python optimizer, so they are documented but not applied here.

The nutrient figures and targets are transcribed from the supplied 2020 script.
The archive does not include their source citations or serving definitions.
Check those values, units, and constraints before using optimizer output to
make dietary decisions.

## Build

Requires a C++20 compiler, CMake 3.20+, pkg-config, and NLopt with its C++
interface. On Debian or Ubuntu, install the dependencies and run the example:

```sh
make install-dependencies
make run
```

`make install-dependencies` uses `sudo apt-get` to install system packages.
After that, the individual steps are also available as `make configure`,
`make build`, and `make run`. The CMake project discovers Ubuntu/Debian's
`nlopt_cxx` pkg-config module, which links the C++ NLopt interface.

The default solver is NLopt's SLSQP implementation. The program exits with a
nonzero status if the optimizer does not report a successful termination.
