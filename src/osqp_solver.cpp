#include "diet/osqp_solver.hpp"

#include <osqp.h>

#include <algorithm>
#include <cmath>
#include <memory>
#include <sstream>
#include <utility>

namespace diet {
namespace {

constexpr double kQuadraticCoefficient = 1.0e-5;
constexpr double kOsqpInfinity = 1.0e30;

struct CscDeleter {
    void operator()(OSQPCscMatrix* matrix) const {
        if (matrix != nullptr) OSQPCscMatrix_free(matrix);
    }
};
struct SettingsDeleter {
    void operator()(OSQPSettings* settings) const {
        if (settings != nullptr) OSQPSettings_free(settings);
    }
};

using CscPtr = std::unique_ptr<OSQPCscMatrix, CscDeleter>;
using SettingsPtr = std::unique_ptr<OSQPSettings, SettingsDeleter>;

std::string row_name(std::size_t nutrient) {
    return std::string(diet::kNutrientTargets[nutrient].name) + " minimum";
}

} // namespace

QpResult solve_with_osqp(const OptimizationModel& model,
                         const std::array<double, kFoodCount>& initial_grams,
                         const std::array<double, kFoodCount>& lower_grams,
                         const std::array<double, kFoodCount>& upper_grams) {
    QpResult result;
    constexpr std::size_t n = kFoodCount;
    constexpr std::size_t required_count = [] {
        std::size_t count = 0;
        for (const auto& target : kNutrientTargets) count += target.required ? 1U : 0U;
        return count;
    }();
    constexpr std::size_t nutrient_row_count = required_count;
    constexpr std::size_t calorie_row = nutrient_row_count;
    constexpr std::size_t bounds_row_start = calorie_row + 1;
    constexpr std::size_t m = bounds_row_start + n;

    // Variables are kilograms. This is the scaled-mass
    // objective: sum(grams/1000) + 1e-5 * sum((grams/1000)^2).
    std::vector<OSQPFloat> p_values(n, 2.0 * kQuadraticCoefficient);
    std::vector<OSQPInt> p_indices(n);
    std::vector<OSQPInt> p_indptr(n + 1);
    for (std::size_t j = 0; j < n; ++j) {
        p_indices[j] = static_cast<OSQPInt>(j);
        p_indptr[j] = static_cast<OSQPInt>(j);
    }
    p_indptr[n] = static_cast<OSQPInt>(n);

    std::vector<OSQPFloat> q(n, 1.0);
    std::vector<OSQPFloat> lower(m, -kOsqpInfinity);
    std::vector<OSQPFloat> upper(m, kOsqpInfinity);
    std::vector<std::string> row_labels(m);

    for (std::size_t row = 0; row < nutrient_row_count; ++row) {
        std::size_t nutrient = 0;
        std::size_t seen = 0;
        for (; nutrient < kNutrientCount; ++nutrient) {
            if (!kNutrientTargets[nutrient].required) continue;
            if (seen++ == row) break;
        }
        const double target = model.lower[nutrient];
        lower[row] = (target - model.fixed_nutrients[nutrient]) / target;
        row_labels[row] = row_name(nutrient);
    }
    upper[calorie_row] = model.calorie_limit;
    row_labels[calorie_row] = "Salad calorie cap";
    for (std::size_t food = 0; food < n; ++food) {
        const std::size_t row = bounds_row_start + food;
        lower[row] = lower_grams[food] / 1000.0;
        upper[row] = upper_grams[food] / 1000.0;
        row_labels[row] = std::string(kFoods[food].name) + " portion bounds";
    }

    // Build A in CSC order. Each ingredient column has one coefficient for
    // every required nutrient, one calorie coefficient, and one bound 1.
    std::vector<OSQPFloat> a_values;
    std::vector<OSQPInt> a_indices;
    std::vector<OSQPInt> a_indptr(n + 1);
    a_values.reserve(n * (nutrient_row_count + 2));
    a_indices.reserve(n * (nutrient_row_count + 2));
    for (std::size_t food = 0; food < n; ++food) {
        a_indptr[food] = static_cast<OSQPInt>(a_values.size());
        std::size_t row = 0;
        for (std::size_t nutrient = 0; nutrient < kNutrientCount; ++nutrient) {
            if (!kNutrientTargets[nutrient].required) continue;
            a_indices.push_back(static_cast<OSQPInt>(row++));
            a_values.push_back(model.nutrient_per_gram[nutrient][food] * 1000.0 /
                               model.lower[nutrient]);
        }
        a_indices.push_back(static_cast<OSQPInt>(calorie_row));
        a_values.push_back(model.calories_per_gram[food] * 1000.0);
        a_indices.push_back(static_cast<OSQPInt>(bounds_row_start + food));
        a_values.push_back(1.0);
    }
    a_indptr[n] = static_cast<OSQPInt>(a_values.size());

    CscPtr p(OSQPCscMatrix_new(static_cast<OSQPInt>(n), static_cast<OSQPInt>(n),
                               static_cast<OSQPInt>(p_values.size()), p_values.data(),
                               p_indices.data(), p_indptr.data()));
    CscPtr a(OSQPCscMatrix_new(static_cast<OSQPInt>(m), static_cast<OSQPInt>(n),
                               static_cast<OSQPInt>(a_values.size()), a_values.data(),
                               a_indices.data(), a_indptr.data()));
    SettingsPtr settings(OSQPSettings_new());
    if (!p || !a || !settings) {
        result.error = "OSQP could not allocate its matrices or settings";
        return result;
    }

    settings->verbose = 0;
    settings->adaptive_rho = 0;
    settings->rho = 0.1;
    settings->eps_abs = 1e-9;
    settings->eps_rel = 1e-9;
    settings->max_iter = 200000;
    settings->polishing = 1;

    OSQPSolver* solver = nullptr;
    const OSQPInt setup_code = osqp_setup(&solver, p.get(), q.data(), a.get(),
                                          lower.data(), upper.data(),
                                          static_cast<OSQPInt>(m),
                                          static_cast<OSQPInt>(n), settings.get());
    if (setup_code != 0 || solver == nullptr) {
        std::ostringstream message;
        message << "osqp_setup failed with code " << setup_code;
        result.error = message.str();
        if (solver != nullptr) osqp_cleanup(solver);
        return result;
    }

    std::array<OSQPFloat, n> initial_x{};
    for (std::size_t food = 0; food < n; ++food) {
        initial_x[food] = static_cast<OSQPFloat>(initial_grams[food] / 1000.0);
    }
    const OSQPInt warm_start_code = osqp_warm_start(solver, initial_x.data(), nullptr);
    if (warm_start_code != 0) {
        std::ostringstream message;
        message << "osqp_warm_start failed with code " << warm_start_code;
        result.error = message.str();
        osqp_cleanup(solver);
        return result;
    }

    const OSQPInt solve_code = osqp_solve(solver);
    if (solver->info != nullptr) {
        result.status = solver->info->status;
        result.status_value = solver->info->status_val;
        result.objective = solver->info->obj_val;
        result.primal_residual = solver->info->prim_res;
        result.dual_residual = solver->info->dual_res;
        result.duality_gap = solver->info->duality_gap;
        result.relative_kkt_error = solver->info->rel_kkt_error;
        result.iterations = solver->info->iter;
    }
    result.solved = solve_code == 0 &&
        (result.status_value == OSQP_SOLVED || result.status_value == OSQP_SOLVED_INACCURATE);

    if (result.solved && solver->solution != nullptr && solver->solution->x != nullptr) {
        for (std::size_t food = 0; food < n; ++food) {
            result.recipe_grams[food] = solver->solution->x[food] * 1000.0;
        }
        if (solver->solution->y != nullptr) {
            result.duals.reserve(m);
            for (std::size_t row = 0; row < m; ++row) {
                const std::string multiplier_unit = row < nutrient_row_count
                    ? "kg-eq / target fraction"
                    : row == calorie_row ? "kg-eq / kcal" : "kg-eq / kg";
                result.duals.push_back(
                    {row_labels[row], solver->solution->y[row], multiplier_unit});
            }
        }
    } else {
        std::ostringstream message;
        if (solve_code != 0) {
            message << "osqp_solve returned code " << solve_code;
        } else {
            message << "OSQP stopped without a solved status";
        }
        result.error = message.str();
    }

    osqp_cleanup(solver);
    return result;
}

} // namespace diet
