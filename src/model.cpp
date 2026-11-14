#include "diet/model.hpp"

namespace diet {

OptimizationModel make_model() {
    OptimizationModel model;
    for (std::size_t food_index = 0; food_index < kFoodCount; ++food_index) {
        const auto& food = kFoods[food_index];
        const double serving_grams = food.source_values[0];
        model.calories_per_gram[food_index] = food.source_values[1] / serving_grams;
        for (std::size_t nutrient_index = 0; nutrient_index < kNutrientCount;
             ++nutrient_index) {
            const std::size_t source_row = nutrient_index + 6;
            model.nutrient_per_gram[nutrient_index][food_index] =
                food.source_values[source_row] / serving_grams;
        }
    }

    for (std::size_t i = 0; i < kNutrientCount; ++i) {
        model.lower[i] = kNutrientTargets[i].minimum;
        // The original script used 3 * rda_min for every upper constraint.
        model.upper[i] = 3.0 * model.lower[i];
        model.target[i] = 2.0 * model.lower[i];
    }
    return model;
}

double total_nutrient(const OptimizationModel& model,
                      const std::array<double, kFoodCount>& recipe,
                      std::size_t nutrient_index) {
    double total = 0.0;
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

} // namespace diet
