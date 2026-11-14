#pragma once

#include "diet/food_data.hpp"

#include <array>
#include <limits>
#include <string_view>

namespace diet {

inline constexpr std::size_t kNutrientCount = 20;
inline constexpr std::size_t kMacronutrientCount = 4;

struct MacronutrientTotals {
    double protein_g = 0.0;
    double fat_g = 0.0;
    double carbohydrate_g = 0.0;
    double fiber_g = 0.0;
};

struct NutrientTarget {
    std::string_view name;
    double minimum;
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
    double fixed_chicken_grams = 199.0;
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
    {"Ca (mg)", 1000.0, true}, {"Cu (mg)", 0.9, true},
    {"Fe (mg)", 8.0, true}, {"Mg (mg)", 350.0, true},
    {"Mn (mg)", 2.3, true}, {"P (mg)", 700.0, true},
    {"Potassium (mg)", 3400.0, true}, {"Se (mg)", 0.055, true},
    {"Na (mg)", 0.0, false}, {"Zn (mg)", 11.0, true},
    {"B1 (mg)", 1.2, true}, {"B2 (mg)", 1.3, true},
    {"B3 (mg)", 16.0, true}, {"B6 (mg)", 1.3, true},
    {"B12 (mg)", 0.0024, true}, {"A (mg)", 0.9, true},
    {"C (mg)", 90.0, true}, {"D (mg)", 0.015, true},
    {"E (mg)", 15.0, true}, {"Vitamin K (mg)", 0.12, true},
}};

} // namespace diet
