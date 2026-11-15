#include "diet/model.hpp"
#include "diet/osqp_audit.hpp"

#include <nlopt.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <string_view>
#include <tuple>
#include <vector>

namespace {

constexpr std::size_t kConstraintCount = diet::kNutrientCount; // 19 targets + calories

struct SolverContext {
    const diet::OptimizationModel& model;
};

double objective_value(const std::vector<double>& x) {
    // Minimize salad mass. A small, smooth quadratic term gives SLSQP a stable
    // tie-breaker when several ingredient mixes have nearly equal mass.
    double scaled_mass = 0.0;
    double scaled_square_sum = 0.0;
    for (const double grams : x) {
        const double scaled = grams / 1000.0;
        scaled_mass += scaled;
        scaled_square_sum += scaled * scaled;
    }
    return scaled_mass + 1.0e-5 * scaled_square_sum;
}

double objective(const std::vector<double>& x, std::vector<double>& gradient, void*) {
    if (!gradient.empty()) {
        std::fill(gradient.begin(), gradient.end(), 0.0);
    }
    for (std::size_t food = 0; food < x.size(); ++food) {
        const double scaled = x[food] / 1000.0;
        if (!gradient.empty()) {
            gradient[food] = 0.001 + 2.0e-5 * scaled / 1000.0;
        }
    }
    return objective_value(x);
}

void constraints(unsigned, double* result, unsigned variable_count,
                 const double* x, double* gradient, void* data) {
    const auto& model = static_cast<SolverContext*>(data)->model;
    const std::size_t n = variable_count;
    std::size_t row = 0;

    for (std::size_t nutrient = 0; nutrient < diet::kNutrientCount; ++nutrient) {
        if (!diet::kNutrientTargets[nutrient].required) {
            continue; // Sodium is calculated and reported, but not optimized.
        }
        double total = model.fixed_nutrients[nutrient];
        for (std::size_t food = 0; food < n; ++food) {
            total += model.nutrient_per_gram[nutrient][food] * x[food];
        }
        const double target = model.lower[nutrient];
        result[row] = (target - total) / target; // NLopt requires g(x) <= 0.
        if (gradient != nullptr) {
            for (std::size_t food = 0; food < n; ++food) {
                gradient[row * n + food] = -model.nutrient_per_gram[nutrient][food] / target;
            }
        }
        ++row;
    }

    double salad_calories = 0.0;
    for (std::size_t food = 0; food < n; ++food) {
        salad_calories += model.calories_per_gram[food] * x[food];
    }
    result[row] = (salad_calories - model.calorie_limit) / model.calorie_limit;
    if (gradient != nullptr) {
        for (std::size_t food = 0; food < n; ++food) {
            gradient[row * n + food] = model.calories_per_gram[food] / model.calorie_limit;
        }
    }
}

const char* result_name(nlopt::result result) {
    switch (result) {
    case nlopt::SUCCESS: return "success";
    case nlopt::STOPVAL_REACHED: return "stop value reached";
    case nlopt::FTOL_REACHED: return "function tolerance reached";
    case nlopt::XTOL_REACHED: return "parameter tolerance reached";
    case nlopt::MAXEVAL_REACHED: return "maximum evaluations reached";
    case nlopt::MAXTIME_REACHED: return "maximum time reached";
    case nlopt::ROUNDOFF_LIMITED: return "roundoff-limited (feasibility checked)";
    default: return "failure";
    }
}

bool meets_targets(const diet::OptimizationModel& model,
                   const std::array<double, diet::kFoodCount>& recipe) {
    for (std::size_t i = 0; i < diet::kNutrientCount; ++i) {
        if (diet::kNutrientTargets[i].required &&
            diet::total_nutrient(model, recipe, i) + model.lower[i] * 1e-8 < model.lower[i]) {
            return false;
        }
    }
    return diet::total_calories(model, recipe) <= model.calorie_limit + 1e-5;
}

bool converged(nlopt::result status) {
    return status == nlopt::SUCCESS || status == nlopt::STOPVAL_REACHED ||
           status == nlopt::FTOL_REACHED || status == nlopt::XTOL_REACHED;
}

struct BoundCheck {
    bool valid = true;
    double maximum_violation_grams = 0.0;
};

BoundCheck check_bounds(const std::vector<double>& x,
                        const std::vector<double>& lower,
                        const std::vector<double>& upper) {
    constexpr double kBoundToleranceGrams = 1e-7;
    BoundCheck check;
    for (std::size_t i = 0; i < x.size(); ++i) {
        if (!std::isfinite(x[i])) {
            check.valid = false;
            check.maximum_violation_grams = std::numeric_limits<double>::infinity();
            continue;
        }
        const double violation = std::max({lower[i] - x[i], x[i] - upper[i], 0.0});
        check.maximum_violation_grams = std::max(check.maximum_violation_grams, violation);
        if (violation > kBoundToleranceGrams) {
            check.valid = false;
        }
    }
    return check;
}

} // namespace

int main(int argc, char** argv) {
    bool diverse_recipe = false;
    if (argc == 2 && std::string_view(argv[1]) == "--diverse") {
        diverse_recipe = true;
    } else if (argc == 2 && std::string_view(argv[1]) == "--sparse") {
        diverse_recipe = false;
    } else if (argc != 1) {
        std::cerr << "Usage: diet_optimizer [--sparse|--diverse]\n";
        return 1;
    }

    const auto model = diet::make_model();
    SolverContext context{model};

    // Start from a generic 20 g portion of each ingredient, matching the
    // original script's style. This is not a precomputed solution; the diverse
    // profile raises any portion needed to satisfy its minimum bound.
    std::vector<double> x(diet::kFoodCount, 20.0);
    std::vector<double> lower_bounds(diet::kFoodCount);
    std::vector<double> upper_bounds(diet::kFoodCount);
    for (std::size_t i = 0; i < diet::kFoodCount; ++i) {
        lower_bounds[i] = diverse_recipe ? diet::kFoods[i].diverse_minimum_grams
                                         : diet::kFoods[i].minimum_grams;
        upper_bounds[i] = diet::kFoods[i].maximum_grams;
        x[i] = std::clamp(x[i], lower_bounds[i], upper_bounds[i]);
    }
    const double starting_objective = objective_value(x);
    const double starting_salad_mass = std::accumulate(x.begin(), x.end(), 0.0);
    const auto starting_bounds = check_bounds(x, lower_bounds, upper_bounds);
    std::array<double, diet::kFoodCount> starting_recipe{};
    std::copy(x.begin(), x.end(), starting_recipe.begin());
    const bool starting_feasible = starting_bounds.valid && meets_targets(model, starting_recipe);

    std::vector<double> tolerances(kConstraintCount, 1e-8);
    nlopt::opt optimizer(nlopt::LD_SLSQP, static_cast<unsigned>(diet::kFoodCount));
    optimizer.set_lower_bounds(lower_bounds);
    optimizer.set_upper_bounds(upper_bounds);
    optimizer.set_min_objective(objective, &context);
    optimizer.add_inequality_mconstraint(constraints, &context, tolerances);
    optimizer.set_ftol_rel(1e-10);
    optimizer.set_maxeval(4000);

    double minimum = 0.0;
    nlopt::result status = nlopt::FAILURE;
    try {
        status = optimizer.optimize(x, minimum);
    } catch (const nlopt::roundoff_limited&) {
        // SLSQP can report roundoff at a constrained optimum. Validate the
        // returned point below instead of discarding a feasible recipe.
        status = nlopt::ROUNDOFF_LIMITED;
    } catch (const std::exception& error) {
        std::cerr << "Optimization failed: " << error.what() << '\n';
        return 2;
    }

    std::array<double, diet::kFoodCount> recipe{};
    std::copy(x.begin(), x.end(), recipe.begin());
    const double final_objective = objective_value(x);
    const double final_salad_mass = std::accumulate(x.begin(), x.end(), 0.0);
    const double raw_objective_change = final_objective - starting_objective;
    const double objective_change = std::abs(raw_objective_change) < 5e-11
        ? 0.0
        : raw_objective_change;
    const double objective_change_percent = starting_objective != 0.0
        ? 100.0 * objective_change / std::abs(starting_objective)
        : 0.0;
    const double raw_mass_change = final_salad_mass - starting_salad_mass;
    const double mass_change = std::abs(raw_mass_change) < 5e-11 ? 0.0 : raw_mass_change;
    const auto final_bounds = check_bounds(x, lower_bounds, upper_bounds);
    const bool feasible = meets_targets(model, recipe) && final_bounds.valid;
    const bool status_acceptable = converged(status) ||
        (status == nlopt::ROUNDOFF_LIMITED && feasible);

    std::cout << std::fixed << std::setprecision(10);
    std::cout << "Recipe profile: " << (diverse_recipe ? "diverse" : "sparse") << '\n';
    std::cout << "Solver status: " << result_name(status) << " (" << status << ")\n";
    std::cout << "Starting point feasible: " << (starting_feasible ? "yes" : "no") << '\n';
    std::cout << "Final feasibility (nutrient minimums, calorie cap, ingredient bounds): "
              << (feasible ? "PASS" : "FAIL") << '\n';
    std::cout << "Ingredient bounds: " << (final_bounds.valid ? "PASS" : "FAIL")
              << "; maximum violation = " << final_bounds.maximum_violation_grams
              << " g (tolerance 0.0000001 g)\n";
    std::cout << "Optimizer convergence: " << (converged(status) ? "yes" : "no") << '\n';
    std::cout << "Solution classification: "
              << (feasible && converged(status) ? "feasible and converged"
                  : feasible ? "feasible; optimality not confirmed"
                  : converged(status) ? "converged status, but final point is infeasible"
                                      : "infeasible and not converged") << '\n';
    std::cout << "Objective (recomputed; scaled mass + tie-breaker): start " << starting_objective
              << ", final " << final_objective << ", change " << std::showpos
              << objective_change << std::noshowpos << " (" << std::showpos
              << objective_change_percent << std::noshowpos << "% relative change)\n";
    std::cout << "Salad mass change: " << starting_salad_mass << " g -> "
              << final_salad_mass << " g (" << std::showpos
              << mass_change << std::noshowpos << " g)\n";

    std::array<double, diet::kFoodCount> lower_array{};
    std::array<double, diet::kFoodCount> upper_array{};
    std::copy(lower_bounds.begin(), lower_bounds.end(), lower_array.begin());
    std::copy(upper_bounds.begin(), upper_bounds.end(), upper_array.begin());
    const auto qp = diet::solve_with_osqp(model, lower_array, upper_array);
    std::cout << "\nIndependent OSQP QP audit\n";
    if (!qp.error.empty()) {
        std::cout << "OSQP audit error: " << qp.error << '\n';
    }
    std::cout << "OSQP status: " << (qp.status.empty() ? "unavailable" : qp.status)
              << " (" << qp.status_value << ")\n";
    if (qp.solved) {
        double max_recipe_difference = 0.0;
        for (std::size_t food = 0; food < diet::kFoodCount; ++food) {
            max_recipe_difference = std::max(
                max_recipe_difference, std::abs(qp.recipe_grams[food] - x[food]));
        }
        std::cout << "OSQP objective: " << qp.objective << '\n'
                  << "OSQP iterations: " << qp.iterations << '\n'
                  << std::scientific << std::setprecision(3)
                  << "Maximum NLopt/OSQP ingredient difference: "
                  << max_recipe_difference << " g\n"
                  << "OSQP primal residual: " << qp.primal_residual << '\n'
                  << "OSQP dual residual: " << qp.dual_residual << '\n'
                  << "OSQP duality gap: " << qp.duality_gap << '\n'
                  << "OSQP relative KKT error: " << qp.relative_kkt_error << '\n';
        std::cout << std::fixed << std::setprecision(10);
        std::cout << "\nOSQP constraint dual multipliers (signed; normalized model rows)\n";
        std::cout << "  " << std::left << std::setw(38) << "Constraint"
                  << std::right << std::setw(18) << "Dual multiplier" << '\n';
        for (const auto& dual : qp.duals) {
            std::cout << "  " << std::left << std::setw(38) << dual.label
                      << std::right << std::setw(18) << dual.value << '\n';
        }
    }

    std::cout << std::setprecision(2);
    if (status == nlopt::ROUNDOFF_LIMITED && feasible) {
        std::cout << "The feasible point is retained, but optimality is not confirmed by NLopt.\n";
    }
    std::cout << "\nIngredient bound audit (grams)\n";
    std::cout << "  " << std::left << std::setw(37) << "Ingredient"
              << std::right << std::setw(11) << "Chosen"
              << std::setw(11) << "Minimum"
              << std::setw(11) << "Maximum" << '\n';
    double salad_weight = 0.0;
    for (std::size_t i = 0; i < diet::kFoodCount; ++i) {
        std::cout << "  " << std::left << std::setw(37) << diet::kFoods[i].name
                  << std::right << std::setw(11) << x[i]
                  << std::setw(11) << lower_bounds[i]
                  << std::setw(11) << upper_bounds[i] << '\n';
        salad_weight += x[i];
    }
    const double salad_calories = diet::total_calories(model, recipe);
    std::cout << "\nSalad: " << salad_weight << " g, " << salad_calories << " kcal\n";
    std::cout << "Fixed accompaniment: cooked chicken leg meat, " << model.fixed_chicken_grams
              << " g edible portion, " << model.fixed_calories << " kcal\n";
    std::cout << "Whole plate: " << salad_calories + model.fixed_calories << " kcal\n\n";

    const auto salad_macros = diet::salad_macronutrients(model, recipe);
    const auto plate_macros = diet::whole_plate_macronutrients(model, recipe);
    std::cout << "Macronutrient profile (g; net carbs = total carbohydrate - fiber)\n";
    std::cout << "  " << std::left << std::setw(18) << "Macro"
              << std::right << std::setw(11) << "Salad"
              << std::setw(11) << "Chicken"
              << std::setw(13) << "Whole plate" << '\n';
    const std::array<std::tuple<std::string_view, double, double, double>, 5> macro_rows{{
        {"Protein", salad_macros.protein_g, model.fixed_macronutrients[0], plate_macros.protein_g},
        {"Fat", salad_macros.fat_g, model.fixed_macronutrients[1], plate_macros.fat_g},
        {"Carbohydrate", salad_macros.carbohydrate_g, model.fixed_macronutrients[2], plate_macros.carbohydrate_g},
        {"Fiber", salad_macros.fiber_g, model.fixed_macronutrients[3], plate_macros.fiber_g},
        {"Net carbs", std::max(0.0, salad_macros.carbohydrate_g - salad_macros.fiber_g),
         std::max(0.0, model.fixed_macronutrients[2] - model.fixed_macronutrients[3]),
         std::max(0.0, plate_macros.carbohydrate_g - plate_macros.fiber_g)},
    }};
    for (const auto& [name, salad, chicken, plate] : macro_rows) {
        std::cout << "  " << std::left << std::setw(18) << name
                  << std::right << std::setw(11) << salad
                  << std::setw(11) << chicken
                  << std::setw(13) << plate << '\n';
    }
    std::cout << '\n';

    std::cout << "Nutrient coverage for salad + chicken\n";
    std::cout << "  " << std::left << std::setw(18) << "Nutrient"
              << std::right << std::setw(13) << "Total"
              << std::setw(13) << "Target"
              << std::setw(13) << "Coverage"
              << std::setw(18) << "Margin" << '\n';
    for (std::size_t i = 0; i < diet::kNutrientCount; ++i) {
        const double total = diet::total_nutrient(model, recipe, i);
        const auto& target = diet::kNutrientTargets[i];
        std::cout << "  " << std::left << std::setw(18) << target.name
                  << std::right << std::setw(13) << total * target.display_scale;
        if (diet::kNutrientTargets[i].required) {
            const double coverage = total / model.lower[i] * 100.0;
            const double raw_margin = total - model.lower[i];
            const double margin = (std::abs(raw_margin) < model.lower[i] * 1e-10
                                       ? 0.0
                                       : raw_margin) * target.display_scale;
            std::cout << std::setw(13) << model.lower[i] * target.display_scale
                      << std::setw(12) << coverage << "%"
                      << std::setw(13) << std::showpos << margin << std::noshowpos
                      << " " << target.unit
                      << "  " << (raw_margin >= -model.lower[i] * 1e-8 ? "met" : "SHORT");
        } else {
            std::cout << std::setw(13) << "—" << std::setw(13) << "—"
                      << std::setw(13) << "tracked" << " " << target.unit;
        }
        std::cout << '\n';
    }

    return feasible && status_acceptable ? 0 : 3;
}
