#include "diet/model.hpp"
#include "diet/osqp_solver.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <string_view>
#include <tuple>
#include <vector>

namespace {

double objective_value(const std::array<double, diet::kFoodCount>& recipe) {
    double scaled_mass = 0.0;
    double scaled_square_sum = 0.0;
    for (const double grams : recipe) {
        const double scaled = grams / 1000.0;
        scaled_mass += scaled;
        scaled_square_sum += scaled * scaled;
    }
    return scaled_mass + 1.0e-5 * scaled_square_sum;
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
        if (violation > kBoundToleranceGrams) check.valid = false;
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

    // Start from a generic 20 g portion of each ingredient. OSQP receives this
    // as a warm start; it is not a precomputed solution.
    std::vector<double> x(diet::kFoodCount, 20.0);
    std::vector<double> lower_bounds(diet::kFoodCount);
    std::vector<double> upper_bounds(diet::kFoodCount);
    std::array<double, diet::kFoodCount> initial_recipe{};
    std::array<double, diet::kFoodCount> lower_array{};
    std::array<double, diet::kFoodCount> upper_array{};
    for (std::size_t i = 0; i < diet::kFoodCount; ++i) {
        lower_bounds[i] = diverse_recipe ? diet::kFoods[i].diverse_minimum_grams
                                         : diet::kFoods[i].minimum_grams;
        upper_bounds[i] = diet::kFoods[i].maximum_grams;
        x[i] = std::clamp(x[i], lower_bounds[i], upper_bounds[i]);
        initial_recipe[i] = x[i];
        lower_array[i] = lower_bounds[i];
        upper_array[i] = upper_bounds[i];
    }

    const double starting_objective = objective_value(initial_recipe);
    const double starting_salad_mass =
        std::accumulate(initial_recipe.begin(), initial_recipe.end(), 0.0);
    const auto starting_bounds = check_bounds(x, lower_bounds, upper_bounds);
    const bool starting_feasible =
        starting_bounds.valid && meets_targets(model, initial_recipe);

    const auto qp = diet::solve_with_osqp(model, initial_recipe, lower_array, upper_array);
    std::cout << std::fixed << std::setprecision(10);
    std::cout << "Recipe profile: " << (diverse_recipe ? "diverse" : "sparse") << '\n';
    std::cout << "Starting point feasible: " << (starting_feasible ? "yes" : "no") << '\n';
    std::cout << "OSQP status: " << (qp.status.empty() ? "unavailable" : qp.status)
              << " (" << qp.status_value << ")\n";
    if (!qp.error.empty()) std::cout << "OSQP error: " << qp.error << '\n';
    if (!qp.solved) {
        std::cout << std::scientific << std::setprecision(3)
                  << "OSQP objective: " << qp.objective << " kg-equivalent\n"
                  << "OSQP iterations: " << qp.iterations << " iterations\n"
                  << "OSQP primal residual (row units vary): " << qp.primal_residual << '\n'
                  << "OSQP dual residual (kg-eq/kg): " << qp.dual_residual << '\n'
                  << "OSQP duality gap (kg-equivalent): " << qp.duality_gap << '\n'
                  << "OSQP relative KKT error (dimensionless): "
                  << qp.relative_kkt_error << '\n'
                  << "  Primal row units: target fractions for nutrients, kcal for calories, kg for portions.\n";
        return 2;
    }

    std::copy(qp.recipe_grams.begin(), qp.recipe_grams.end(), x.begin());
    const auto& recipe = qp.recipe_grams;
    const double final_objective = objective_value(recipe);
    const double final_salad_mass =
        std::accumulate(recipe.begin(), recipe.end(), 0.0);
    const double raw_objective_change = final_objective - starting_objective;
    const double objective_change = std::abs(raw_objective_change) < 5e-11
        ? 0.0 : raw_objective_change;
    const double objective_change_percent = starting_objective != 0.0
        ? 100.0 * objective_change / std::abs(starting_objective) : 0.0;
    const double raw_mass_change = final_salad_mass - starting_salad_mass;
    const double mass_change = std::abs(raw_mass_change) < 5e-11 ? 0.0 : raw_mass_change;
    const auto final_bounds = check_bounds(x, lower_bounds, upper_bounds);
    const bool feasible = meets_targets(model, recipe) && final_bounds.valid;

    std::cout << "Final feasibility (nutrient minimums, calorie cap, ingredient bounds): "
              << (feasible ? "PASS" : "FAIL") << '\n';
    std::cout << "Ingredient bounds: " << (final_bounds.valid ? "PASS" : "FAIL")
              << "; maximum violation = " << final_bounds.maximum_violation_grams
              << " g (tolerance 0.0000001 g)\n";
    std::cout << "OSQP convergence: yes\n";
    std::cout << "Solution classification: "
              << (feasible ? "feasible and converged"
                           : "converged status, but final point is infeasible") << '\n';
    std::cout << "Objective (kg-equivalent; scaled mass + tie-breaker): start " << starting_objective
              << ", final " << final_objective << ", change " << std::showpos
              << objective_change << std::noshowpos << " (" << std::showpos
              << objective_change_percent << std::noshowpos << "% relative change)\n";
    std::cout << "Salad mass change: " << starting_salad_mass << " g -> "
              << final_salad_mass << " g (" << std::showpos
              << mass_change << std::noshowpos << " g)\n";

    std::cout << "\nOSQP KKT diagnostics\n"
              << "OSQP objective: " << qp.objective << " kg-equivalent\n"
              << "OSQP iterations: " << qp.iterations << " iterations\n"
              << std::scientific << std::setprecision(3)
              << "OSQP primal residual (row units vary): " << qp.primal_residual << '\n'
              << "OSQP dual residual (kg-eq/kg): " << qp.dual_residual << '\n'
              << "OSQP duality gap (kg-equivalent): " << qp.duality_gap << '\n'
              << "OSQP relative KKT error (dimensionless): " << qp.relative_kkt_error << '\n'
              << "  Primal row units: target fractions for nutrients, kcal for calories, kg for portions.\n";
    std::cout << std::fixed << std::setprecision(10);
    std::cout << "\nOSQP constraint dual multipliers (signed; see row units)\n";
    std::cout << "  " << std::left << std::setw(38) << "Constraint"
              << std::right << std::setw(18) << "Multiplier"
              << "  Unit (objective / row)" << '\n';
    for (const auto& dual : qp.duals) {
        std::cout << "  " << std::left << std::setw(38) << dual.label
                  << std::right << std::setw(18) << dual.value
                  << "  " << dual.unit << '\n';
    }

    std::cout << std::setprecision(2);
    std::cout << "\nIngredient bound audit (grams)\n";
    std::cout << "  " << std::left << std::setw(24) << "Group"
              << std::setw(37) << "Ingredient"
              << std::right << std::setw(11) << "Chosen"
              << std::setw(11) << "Minimum"
              << std::setw(11) << "Maximum" << '\n';
    double salad_weight = 0.0;
    for (std::size_t i = 0; i < diet::kFoodCount; ++i) {
        std::cout << "  " << std::left << std::setw(24)
                  << diet::ingredient_group_name(diet::kFoods[i].group)
                  << std::setw(37) << diet::kFoods[i].name
                  << std::right << std::setw(11) << x[i]
                  << std::setw(11) << lower_bounds[i]
                  << std::setw(11) << upper_bounds[i] << '\n';
        salad_weight += x[i];
    }
    const double salad_calories = diet::total_calories(model, recipe);
    std::cout << "\nSalad: " << salad_weight << " g, " << salad_calories << " kcal\n";
    std::cout << "Fixed accompaniment: roasted chicken leg quarter, meat and skin, "
              << model.fixed_chicken_grams
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

    std::cout << "Nutrient coverage for salad + chicken (nutrient-specific units)\n";
    std::cout << "  " << std::left << std::setw(18) << "Nutrient"
              << std::setw(9) << "Unit"
              << std::right << std::setw(12) << "Total"
              << std::setw(12) << "Target"
              << std::setw(12) << "Coverage"
              << std::setw(12) << "Margin" << '\n';
    for (std::size_t i = 0; i < diet::kNutrientCount; ++i) {
        const double total = diet::total_nutrient(model, recipe, i);
        const auto& target = diet::kNutrientTargets[i];
        std::cout << "  " << std::left << std::setw(18) << target.name
                  << std::setw(9) << target.unit
                  << std::right << std::setw(12) << total * target.display_scale;
        if (diet::kNutrientTargets[i].required) {
            const double coverage = total / model.lower[i] * 100.0;
            const double raw_margin = total - model.lower[i];
            const double margin = (std::abs(raw_margin) < model.lower[i] * 1e-10
                                       ? 0.0
                                       : raw_margin) * target.display_scale;
            std::cout << std::setw(12) << model.lower[i] * target.display_scale
                      << std::setw(11) << coverage << "%"
                      << std::setw(12) << std::showpos << margin << std::noshowpos
                      << "  " << (raw_margin >= -model.lower[i] * 1e-8 ? "met" : "SHORT");
        } else {
            std::cout << std::setw(12) << "—" << std::setw(12) << "—"
                      << std::setw(12) << "tracked";
        }
        std::cout << '\n';
    }

    const double sodium_mg = diet::total_nutrient(
        model, recipe, diet::kSodiumNutrientIndex);
    const double sodium_ai_difference = diet::kSodiumAdequateIntakeMg - sodium_mg;
    const double sodium_cdrr_difference = diet::kSodiumCdrrMg - sodium_mg;
    std::cout << "\nSodium reference points (tracked; not optimized)\n"
              << "  Total, salad + chicken: " << sodium_mg << " mg\n"
              << "  Adequate Intake (AI): " << diet::kSodiumAdequateIntakeMg
              << " mg (" << sodium_mg / diet::kSodiumAdequateIntakeMg * 100.0
              << "%; " << std::abs(sodium_ai_difference) << " mg "
              << (sodium_ai_difference >= 0.0 ? "below" : "above") << ")\n"
              << "  Chronic Disease Risk Reduction (CDRR): " << diet::kSodiumCdrrMg
              << " mg (" << sodium_mg / diet::kSodiumCdrrMg * 100.0
              << "%; " << std::abs(sodium_cdrr_difference) << " mg "
              << (sodium_cdrr_difference >= 0.0 ? "below" : "above") << ")\n"
              << "  Position: "
              << (sodium_mg < diet::kSodiumAdequateIntakeMg
                      ? "below the AI reference point"
                      : (sodium_mg <= diet::kSodiumCdrrMg
                             ? "between the AI and CDRR reference points"
                             : "above the CDRR reference point"))
              << "\n  These are dietary reference points, not a deficiency test or a sodium constraint.\n";

    return feasible ? 0 : 3;
}
