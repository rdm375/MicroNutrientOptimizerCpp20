#include "diet/model.hpp"

#include <array>
#include <cmath>
#include <iostream>
#include <string_view>

namespace {

bool near(double actual, double expected, double tolerance = 1e-10) {
    return std::abs(actual - expected) <= tolerance * (1.0 + std::abs(expected));
}

bool fail(std::string_view message) {
    std::cerr << "FAIL: " << message << '\n';
    return false;
}

} // namespace

int main() {
    bool ok = true;
    const auto model = diet::make_model();

    if (diet::kFoodCount != 17 || diet::kNutrientCount != 20 || diet::kSourceRows != 26) {
        ok = fail("model dimensions changed; review the source table and regression expectations") && ok;
    }

    std::size_t required_count = 0;
    for (const auto& target : diet::kNutrientTargets) {
        if (target.required) {
            ++required_count;
            if (!(target.minimum > 0.0)) {
                ok = fail("a required nutrient target must be positive") && ok;
            }
        }
    }
    if (required_count != 19 || diet::kNutrientTargets[diet::kSodiumNutrientIndex].required) {
        ok = fail("expected 19 required nutrients with sodium tracked only") && ok;
    }

    for (std::size_t food = 0; food < diet::kFoodCount; ++food) {
        const auto& entry = diet::kFoods[food];
        const double serving_g = entry.source_values[0];
        if (!(serving_g > 0.0) || entry.minimum_grams < 0.0 ||
            entry.diverse_minimum_grams < entry.minimum_grams ||
            entry.maximum_grams < entry.diverse_minimum_grams) {
            ok = fail("ingredient serving or portion bounds are inconsistent") && ok;
        }
        for (double value : entry.source_values) {
            if (!std::isfinite(value) || value < 0.0) {
                ok = fail("food source table contains a negative or non-finite value") && ok;
            }
        }
        if (!near(model.calories_per_gram[food] * serving_g, entry.source_values[1])) {
            ok = fail("calorie per-gram conversion no longer matches the source table") && ok;
        }
        for (std::size_t macro = 0; macro < diet::kMacronutrientCount; ++macro) {
            if (!near(model.macronutrient_per_gram[macro][food] * serving_g,
                      entry.source_values[macro + 2])) {
                ok = fail("macronutrient per-gram conversion no longer matches the source table") && ok;
            }
        }
        for (std::size_t nutrient = 0; nutrient < diet::kNutrientCount; ++nutrient) {
            if (!near(model.nutrient_per_gram[nutrient][food] * serving_g,
                      entry.source_values[nutrient + 6])) {
                ok = fail("micronutrient per-gram conversion no longer matches the source table") && ok;
            }
        }
    }

    constexpr std::array<double, diet::kFoodCount> no_salad{};
    if (!near(diet::total_calories(model, no_salad), 0.0)) {
        ok = fail("empty salad should have zero salad calories") && ok;
    }
    for (std::size_t nutrient = 0; nutrient < diet::kNutrientCount; ++nutrient) {
        if (!near(diet::total_nutrient(model, no_salad, nutrient), model.fixed_nutrients[nutrient])) {
            ok = fail("empty salad nutrient totals should equal fixed accompaniment totals") && ok;
        }
    }

    if (!near(model.fixed_calories, 474.72) || !near(model.fixed_chicken_grams, 258.0) ||
        !near(model.fixed_macronutrients[0], 61.9974) ||
        !near(model.fixed_macronutrients[1], 23.1942)) {
        ok = fail("fixed chicken portion regression changed") && ok;
    }

    if (!near(model.lower[7], 0.055) || !near(model.lower[14], 0.0024) ||
        !near(model.lower[15], 0.9) || !near(model.lower[17], 0.015) ||
        !near(model.lower[19], 0.12)) {
        ok = fail("microgram-based targets must remain stored in milligrams") && ok;
    }
    constexpr std::array<std::size_t, 5> microgram_indices{{7, 14, 15, 17, 19}};
    for (const auto index : microgram_indices) {
        if (!near(diet::kNutrientTargets[index].display_scale, 1000.0) ||
            (diet::kNutrientTargets[index].unit != "µg" && index != 15)) {
            ok = fail("microgram nutrients must be scaled and labeled consistently for display") && ok;
        }
    }
    if (diet::kNutrientTargets[15].unit != "µg RAE") {
        ok = fail("vitamin A must be reported in micrograms RAE") && ok;
    }

    if (!ok) {
        return 1;
    }
    std::cout << "PASS: model dimensions, bounds, per-gram conversions, fixed chicken, and target units\n";
    return 0;
}
