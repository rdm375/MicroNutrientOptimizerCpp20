#pragma once

#include "diet/food_data.hpp"

#include <array>
#include <limits>
#include <string_view>

namespace diet {

inline constexpr std::size_t kNutrientCount = 20;
inline constexpr std::size_t kMacronutrientCount = 4;
inline constexpr double kSodiumAdequateIntakeMg = 1500.0;
inline constexpr double kSodiumCdrrMg = 2300.0;
inline constexpr std::size_t kSodiumNutrientIndex = 8;

struct MacronutrientTotals {
    double protein_g = 0.0;
    double fat_g = 0.0;
    double carbohydrate_g = 0.0;
    double fiber_g = 0.0;
};

struct NutrientTarget {
    std::string_view name;
    std::string_view unit;
    double minimum;
    double display_scale;
    bool required;
};

struct OptimizationModel {
    std::array<std::array<double, kFoodCount>, kNutrientCount> nutrient_per_gram{};
    std::array<std::array<double, kFoodCount>, kMacronutrientCount> macronutrient_per_gram{};
    std::array<double, kFoodCount> calories_per_gram{};
    std::array<double, kNutrientCount> lower{};
    std::array<double, kNutrientCount> fixed_nutrients{};
    std::array<double, kMacronutrientCount> fixed_macronutrients{};
    double fixed_calories = 0.0;
    // USDA SR Legacy edible portion for one roasted leg with skin
    // (thigh + drumstick + back; bone excluded).
    double fixed_chicken_grams = 258.0;
    double calorie_limit = 700.0;
};

OptimizationModel make_model();
double total_nutrient(const OptimizationModel& model,
                      const std::array<double, kFoodCount>& recipe,
                      std::size_t nutrient_index);
double total_calories(const OptimizationModel& model,
                      const std::array<double, kFoodCount>& recipe);
MacronutrientTotals salad_macronutrients(
    const OptimizationModel& model,
    const std::array<double, kFoodCount>& recipe);
MacronutrientTotals whole_plate_macronutrients(
    const OptimizationModel& model,
    const std::array<double, kFoodCount>& recipe);

inline constexpr std::array<NutrientTarget, kNutrientCount> kNutrientTargets{{
    {"Calcium", "mg", 1000.0, 1.0, true}, {"Copper", "mg", 0.9, 1.0, true},
    {"Iron", "mg", 8.0, 1.0, true}, {"Magnesium", "mg", 350.0, 1.0, true},
    {"Manganese", "mg", 2.3, 1.0, true}, {"Phosphorus", "mg", 700.0, 1.0, true},
    {"Potassium", "mg", 3400.0, 1.0, true}, {"Selenium", "µg", 0.055, 1000.0, true},
    {"Sodium", "mg", 0.0, 1.0, false}, {"Zinc", "mg", 11.0, 1.0, true},
    {"Vitamin B1", "mg", 1.2, 1.0, true}, {"Vitamin B2", "mg", 1.3, 1.0, true},
    {"Vitamin B3", "mg", 16.0, 1.0, true}, {"Vitamin B6", "mg", 1.3, 1.0, true},
    {"Vitamin B12", "µg", 0.0024, 1000.0, true}, {"Vitamin A", "µg RAE", 0.9, 1000.0, true},
    {"Vitamin C", "mg", 90.0, 1.0, true}, {"Vitamin D", "µg", 0.015, 1000.0, true},
    {"Vitamin E", "mg", 15.0, 1.0, true}, {"Vitamin K", "µg", 0.12, 1000.0, true},
}};

} // namespace diet
