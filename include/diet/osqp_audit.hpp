#pragma once

#include "diet/model.hpp"

#include <array>
#include <string>
#include <vector>

namespace diet {

struct QpDual {
    std::string label;
    double value = 0.0;
};

struct QpAuditResult {
    bool solved = false;
    int status_value = 0;
    std::string status;
    std::string error;
    std::array<double, kFoodCount> recipe_grams{};
    std::vector<QpDual> duals;
    double objective = 0.0;
    double primal_residual = 0.0;
    double dual_residual = 0.0;
    double duality_gap = 0.0;
    double relative_kkt_error = 0.0;
    int iterations = 0;
};

// Solve the same scaled-mass QP with OSQP from the shared NLopt primal start.
QpAuditResult solve_with_osqp(const OptimizationModel& model,
                              const std::array<double, kFoodCount>& initial_grams,
                              const std::array<double, kFoodCount>& lower_grams,
                              const std::array<double, kFoodCount>& upper_grams);

} // namespace diet
