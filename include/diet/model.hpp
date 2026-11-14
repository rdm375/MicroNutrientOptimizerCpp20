#pragma once

#include "diet/food_data.hpp"

#include <array>
#include <limits>
#include <string_view>

namespace diet {

inline constexpr std::size_t kNutrientCount = 20;

struct NutrientTarget {
    std::string_view name;
    double minimum;
    double maximum;
};

struct OptimizationModel {
    std::array<std::array<double, kFoodCount>, kNutrientCount> nutrient_per_gram{};
    std::array<double, kFoodCount> calories_per_gram{};
    std::array<double, kNutrientCount> lower{};
    std::array<double, kNutrientCount> upper{};
    std::array<double, kNutrientCount> target{};
    double calorie_limit = 700.0;
};

OptimizationModel make_model();
double total_nutrient(const OptimizationModel& model,
                      const std::array<double, kFoodCount>& recipe,
                      std::size_t nutrient_index);
double total_calories(const OptimizationModel& model,
                      const std::array<double, kFoodCount>& recipe);

inline constexpr std::array<NutrientTarget, kNutrientCount> kNutrientTargets{{
    {"Ca (mg)", 1000.0, 2500.0}, {"Cu (mg)", 0.9, 10.0},
    {"Fe (mg)", 8.0, 45.0}, {"Mg (mg)", 350.0, 420.0},
    {"Mn (mg)", 2.3, 11.0}, {"P (mg)", 700.0, 4000.0},
    {"K (mg)", 3400.0, std::numeric_limits<double>::infinity()}, {"Se (mg)", 0.055, 0.4},
    {"Na (mg)", 1500.0, 2300.0}, {"Zn (mg)", 11.0, 40.0},
    {"B1 (mg)", 1.2, std::numeric_limits<double>::infinity()}, {"B2 (mg)", 1.3, std::numeric_limits<double>::infinity()},
    {"B3 (mg)", 16.0, 35.0}, {"B6 (mg)", 1.3, 100.0},
    {"B12 (mg)", 0.0024, std::numeric_limits<double>::infinity()}, {"A (mg)", 0.9, 3.0},
    {"C (mg)", 90.0, 2000.0}, {"D (mg)", 0.015, 0.1},
    {"E (mg)", 15.0, 1000.0}, {"K (mg)", 0.12, std::numeric_limits<double>::infinity()},
}};

} // namespace diet
