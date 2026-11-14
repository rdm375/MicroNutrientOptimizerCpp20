#include "diet/model.hpp"

#include <nlopt.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <exception>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

namespace {

struct SolverContext {
    const diet::OptimizationModel& model;
};

double objective(const std::vector<double>& x, std::vector<double>& gradient, void* data) {
    const auto& model = static_cast<SolverContext*>(data)->model;
    double value = 0.0;
    if (!gradient.empty()) {
        std::fill(gradient.begin(), gradient.end(), 0.0);
    }

    for (std::size_t nutrient = 0; nutrient < diet::kNutrientCount; ++nutrient) {
        double residual = -model.target[nutrient];
        for (std::size_t food = 0; food < diet::kFoodCount; ++food) {
            residual += model.nutrient_per_gram[nutrient][food] * x[food];
        }
        value += residual * residual;
        if (!gradient.empty()) {
            for (std::size_t food = 0; food < diet::kFoodCount; ++food) {
                gradient[food] += 2.0 * residual * model.nutrient_per_gram[nutrient][food];
            }
        }
    }
    return value;
}

void constraints(unsigned count, double* result, unsigned variable_count,
                 const double* x, double* gradient, void* data) {
    const auto& model = static_cast<SolverContext*>(data)->model;
    const std::size_t n = variable_count;
    const std::size_t nutrient_constraints = 2 * diet::kNutrientCount;
    (void)count;

    for (std::size_t nutrient = 0; nutrient < diet::kNutrientCount; ++nutrient) {
        double total = 0.0;
        for (std::size_t food = 0; food < diet::kFoodCount; ++food) {
            total += model.nutrient_per_gram[nutrient][food] * x[food];
        }

        const std::size_t lower_row = 2 * nutrient;
        const std::size_t upper_row = lower_row + 1;
        result[lower_row] = model.lower[nutrient] - total;
        result[upper_row] = total - model.upper[nutrient];

        if (gradient != nullptr) {
            for (std::size_t food = 0; food < n; ++food) {
                const double coefficient = model.nutrient_per_gram[nutrient][food];
                gradient[lower_row * n + food] = -coefficient;
                gradient[upper_row * n + food] = coefficient;
            }
        }
    }

    double calories = 0.0;
    for (std::size_t food = 0; food < n; ++food) {
        calories += model.calories_per_gram[food] * x[food];
    }
    result[nutrient_constraints] = calories - model.calorie_limit;
    if (gradient != nullptr) {
        for (std::size_t food = 0; food < n; ++food) {
            gradient[nutrient_constraints * n + food] = model.calories_per_gram[food];
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
    default: return "failure";
    }
}

bool converged(nlopt::result result) {
    return result == nlopt::SUCCESS || result == nlopt::STOPVAL_REACHED ||
           result == nlopt::FTOL_REACHED || result == nlopt::XTOL_REACHED;
}

} // namespace

int main() {
    const auto model = diet::make_model();
    SolverContext context{model};

    std::vector<double> x(diet::kFoodCount, 20.0);
    std::vector<double> lower_bounds(diet::kFoodCount);
    std::vector<double> upper_bounds(diet::kFoodCount);
    for (std::size_t i = 0; i < diet::kFoodCount; ++i) {
        lower_bounds[i] = diet::kFoods[i].minimum_grams;
        upper_bounds[i] = diet::kFoods[i].maximum_grams;
    }

    constexpr unsigned constraint_count = 2 * diet::kNutrientCount + 1;
    std::vector<double> tolerances(constraint_count, 1e-8);
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
    } catch (const std::exception& error) {
        std::cerr << "Optimization failed: " << error.what() << '\n';
        return 2;
    }

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "Solver status: " << result_name(status) << " (" << status << ")\n";
    std::cout << "Objective (sum of squared nutrient errors): " << minimum << "\n\n";
    std::cout << "Ingredient amounts\n";
    double total_weight = 0.0;
    for (std::size_t i = 0; i < diet::kFoodCount; ++i) {
        std::cout << "  " << diet::kFoods[i].name << ": " << x[i] << " g\n";
        total_weight += x[i];
    }

    std::cout << "\nTotal weight: " << total_weight << " g\n";
    std::cout << "Total calories: " << diet::total_calories(model, x) << " kcal\n\n";
    std::cout << "Nutrient totals\n";
    for (std::size_t i = 0; i < diet::kNutrientCount; ++i) {
        const double total = diet::total_nutrient(model, x, i);
        std::cout << "  " << std::left << std::setw(10) << diet::kNutrientTargets[i].name
                  << std::right << std::setw(11) << total
                  << "  allowed [" << model.lower[i] << ", " << model.upper[i] << "]\n";
    }

    return converged(status) ? 0 : 3;
}
