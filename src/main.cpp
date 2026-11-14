#include "diet/model.hpp"

#include <nlopt.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <exception>
#include <iomanip>
#include <iostream>
#include <string_view>
#include <tuple>
#include <vector>

namespace {

constexpr std::size_t kConstraintCount = diet::kNutrientCount; // 19 targets + calories

struct SolverContext {
    const diet::OptimizationModel& model;
};

double objective(const std::vector<double>& x, std::vector<double>& gradient, void*) {
    // Minimize salad mass. A small, smooth quadratic term gives SLSQP a stable
    // tie-breaker when several ingredient mixes have nearly equal mass.
    double scaled_mass = 0.0;
    double scaled_square_sum = 0.0;
    if (!gradient.empty()) {
        std::fill(gradient.begin(), gradient.end(), 0.0);
    }
    for (std::size_t food = 0; food < x.size(); ++food) {
        const double scaled = x[food] / 1000.0;
        scaled_mass += scaled;
        scaled_square_sum += scaled * scaled;
        if (!gradient.empty()) {
            gradient[food] = 0.001 + 2.0e-5 * scaled / 1000.0;
        }
    }
    return scaled_mass + 1.0e-5 * scaled_square_sum;
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
            diet::total_nutrient(model, recipe, i) + 1e-6 < model.lower[i]) {
            return false;
        }
    }
    return diet::total_calories(model, recipe) <= model.calorie_limit + 1e-5;
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

    // Feasible warm starts avoid asking SLSQP to discover feasibility from an
    // arbitrary guess. The diverse profile has a positive floor for every food.
    std::vector<double> x(diet::kFoodCount, 0.0);
    const auto set_ingredient = [&x](std::string_view name, double grams) {
        for (std::size_t i = 0; i < diet::kFoodCount; ++i) {
            if (diet::kFoods[i].name == name) {
                x[i] = grams;
                return;
            }
        }
    };
    if (diverse_recipe) {
        set_ingredient("romaine lettuce", 30.0);
        set_ingredient("collard greens", 20.0);
        set_ingredient("spinach", 416.460617259367);
        set_ingredient("roma tomatoes", 30.0);
        set_ingredient("cucumbers", 20.0);
        set_ingredient("red onion", 10.0);
        set_ingredient("pine nuts", 5.0);
        set_ingredient("pumpkin seeds", 5.549623997933);
        set_ingredient("chia seeds", 5.0);
        set_ingredient("sunflower seeds", 23.505970571981);
        set_ingredient("shiitake mushrms", 10.0);
        set_ingredient("wht btn mushrms", 10.0);
        set_ingredient("brocoli", 20.0);
        set_ingredient("bell pepper", 20.0);
        set_ingredient("egg", 122.265492652492);
        set_ingredient("chedar cheese", 33.012583730673);
        set_ingredient("UV-exposed portabella mushrooms", 41.518323231137);
    } else {
        set_ingredient("spinach", 466.170369546159);
        set_ingredient("pumpkin seeds", 16.203578784470);
        set_ingredient("sunflower seeds", 26.454192892562);
        set_ingredient("bell pepper", 33.482847835694);
        set_ingredient("egg", 120.945824272317);
        set_ingredient("chedar cheese", 34.730352072201);
        set_ingredient("UV-exposed portabella mushrooms", 42.015137019240);
    }
    std::vector<double> lower_bounds(diet::kFoodCount);
    std::vector<double> upper_bounds(diet::kFoodCount);
    for (std::size_t i = 0; i < diet::kFoodCount; ++i) {
        lower_bounds[i] = diverse_recipe ? diet::kFoods[i].diverse_minimum_grams
                                         : diet::kFoods[i].minimum_grams;
        upper_bounds[i] = diet::kFoods[i].maximum_grams;
    }

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
    const bool feasible = meets_targets(model, recipe);

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "Recipe profile: " << (diverse_recipe ? "diverse" : "sparse") << '\n';
    std::cout << "Solver status: " << result_name(status) << " (" << status << ")\n";
    std::cout << "Feasible for all required minimums: " << (feasible ? "yes" : "no") << "\n\n";
    std::cout << "Salad ingredients\n";
    double salad_weight = 0.0;
    for (std::size_t i = 0; i < diet::kFoodCount; ++i) {
        if (x[i] < 0.5) continue;
        std::cout << "  " << diet::kFoods[i].name << ": " << x[i] << " g\n";
        salad_weight += x[i];
    }
    const double salad_calories = diet::total_calories(model, recipe);
    std::cout << "\nSalad: " << salad_weight << " g, " << salad_calories << " kcal\n";
    std::cout << "Fixed accompaniment: cooked chicken leg meat, " << model.fixed_chicken_grams
              << " g edible portion, " << model.fixed_calories << " kcal\n";
    std::cout << "Whole plate: " << salad_calories + model.fixed_calories << " kcal\n\n";

    const auto salad_macros = diet::salad_macronutrients(model, recipe);
    const auto plate_macros = diet::whole_plate_macronutrients(model, recipe);
    std::cout << "Macronutrient profile (g)\n";
    std::cout << "  " << std::left << std::setw(18) << "Macro"
              << std::right << std::setw(11) << "Salad"
              << std::setw(11) << "Chicken"
              << std::setw(13) << "Whole plate" << '\n';
    const std::array<std::tuple<std::string_view, double, double, double>, 4> macro_rows{{
        {"Protein", salad_macros.protein_g, model.fixed_macronutrients[0], plate_macros.protein_g},
        {"Fat", salad_macros.fat_g, model.fixed_macronutrients[1], plate_macros.fat_g},
        {"Carbohydrate", salad_macros.carbohydrate_g, model.fixed_macronutrients[2], plate_macros.carbohydrate_g},
        {"Fiber", salad_macros.fiber_g, model.fixed_macronutrients[3], plate_macros.fiber_g},
    }};
    for (const auto& [name, salad, chicken, plate] : macro_rows) {
        std::cout << "  " << std::left << std::setw(18) << name
                  << std::right << std::setw(11) << salad
                  << std::setw(11) << chicken
                  << std::setw(13) << plate << '\n';
    }
    std::cout << '\n';

    std::cout << "Nutrient totals for salad + chicken\n";
    for (std::size_t i = 0; i < diet::kNutrientCount; ++i) {
        const double total = diet::total_nutrient(model, recipe, i);
        std::cout << "  " << std::left << std::setw(10) << diet::kNutrientTargets[i].name
                  << std::right << std::setw(11) << total;
        if (diet::kNutrientTargets[i].required) {
            std::cout << "  target " << model.lower[i]
                      << "  " << (total + 1e-6 >= model.lower[i] ? "met" : "SHORT");
        } else {
            std::cout << "  tracked only";
        }
        std::cout << '\n';
    }

    return feasible ? 0 : 3;
}
