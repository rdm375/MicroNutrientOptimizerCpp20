#include "diet/model.hpp"

namespace diet {

OptimizationModel make_model() {
    OptimizationModel model;
    for (std::size_t food_index = 0; food_index < kFoodCount; ++food_index) {
        const auto& food = kFoods[food_index];
        const double serving_grams = food.source_values[0];
        model.calories_per_gram[food_index] = food.source_values[1] / serving_grams;
        for (std::size_t macro_index = 0; macro_index < kMacronutrientCount; ++macro_index) {
            const std::size_t source_row = macro_index + 2;
            model.macronutrient_per_gram[macro_index][food_index] =
                food.source_values[source_row] / serving_grams;
        }
        for (std::size_t nutrient_index = 0; nutrient_index < kNutrientCount;
             ++nutrient_index) {
            const std::size_t source_row = nutrient_index + 6;
            model.nutrient_per_gram[nutrient_index][food_index] =
                food.source_values[source_row] / serving_grams;
        }
    }

    for (std::size_t i = 0; i < kNutrientCount; ++i) {
        model.lower[i] = kNutrientTargets[i].minimum;
    }

    // Fixed accompaniment: one USDA SR28 cooked leg measure with skin, 258 g
    // edible portion (thigh + drumstick + back; bone excluded). Values below
    // are per 100 g edible portion.
    constexpr std::array<double, kNutrientCount> chicken_per_100g{{
        12.0, 0.061, 1.09, 23.0, 0.020, 202.0, 264.0, 0.0257, 98.0, 2.07,
        0.090, 0.187, 6.034, 0.413, 0.00038, 0.020, 0.0, 0.0001, 0.190, 0.0039,
    }};
    for (std::size_t i = 0; i < kNutrientCount; ++i) {
        model.fixed_nutrients[i] = chicken_per_100g[i] * model.fixed_chicken_grams / 100.0;
    }
    model.fixed_calories = 184.0 * model.fixed_chicken_grams / 100.0;
    constexpr std::array<double, kMacronutrientCount> chicken_macros_per_100g{{
        24.03, 8.99, 0.0, 0.0,
    }};
    for (std::size_t i = 0; i < kMacronutrientCount; ++i) {
        model.fixed_macronutrients[i] = chicken_macros_per_100g[i] * model.fixed_chicken_grams / 100.0;
    }
    return model;
}

double total_nutrient(const OptimizationModel& model,
                      const std::array<double, kFoodCount>& recipe,
                      std::size_t nutrient_index) {
    double total = 0.0;
    total += model.fixed_nutrients[nutrient_index];
    for (std::size_t food_index = 0; food_index < kFoodCount; ++food_index) {
        total += model.nutrient_per_gram[nutrient_index][food_index] * recipe[food_index];
    }
    return total;
}

double total_calories(const OptimizationModel& model,
                      const std::array<double, kFoodCount>& recipe) {
    double total = 0.0;
    for (std::size_t food_index = 0; food_index < kFoodCount; ++food_index) {
        total += model.calories_per_gram[food_index] * recipe[food_index];
    }
    return total;
}

MacronutrientTotals salad_macronutrients(
    const OptimizationModel& model,
    const std::array<double, kFoodCount>& recipe) {
    std::array<double, kMacronutrientCount> totals{};
    for (std::size_t macro = 0; macro < kMacronutrientCount; ++macro) {
        for (std::size_t food = 0; food < kFoodCount; ++food) {
            totals[macro] += model.macronutrient_per_gram[macro][food] * recipe[food];
        }
    }
    return {totals[0], totals[1], totals[2], totals[3]};
}

MacronutrientTotals whole_plate_macronutrients(
    const OptimizationModel& model,
    const std::array<double, kFoodCount>& recipe) {
    auto totals = salad_macronutrients(model, recipe);
    totals.protein_g += model.fixed_macronutrients[0];
    totals.fat_g += model.fixed_macronutrients[1];
    totals.carbohydrate_g += model.fixed_macronutrients[2];
    totals.fiber_g += model.fixed_macronutrients[3];
    return totals;
}

} // namespace diet
