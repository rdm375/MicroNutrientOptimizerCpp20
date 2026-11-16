#pragma once

#include <array>
#include <cstddef>
#include <string_view>

namespace diet {
inline constexpr std::size_t kFoodCount = 17;
inline constexpr std::size_t kSourceRows = 26;

enum class IngredientGroup {
    LeafyGreens,
    Seeds,
    Nuts,
    PreferredVegetables,
    Olives,
    Mushrooms,
    EggsAndDairy,
};

constexpr std::string_view ingredient_group_name(IngredientGroup group) {
    switch (group) {
    case IngredientGroup::LeafyGreens: return "Leafy greens";
    case IngredientGroup::Seeds: return "Seeds";
    case IngredientGroup::Nuts: return "Nuts";
    case IngredientGroup::PreferredVegetables: return "Preferred vegetables";
    case IngredientGroup::Olives: return "Olives";
    case IngredientGroup::Mushrooms: return "Mushrooms";
    case IngredientGroup::EggsAndDairy: return "Eggs and dairy";
    }
    return "Other";
}

// Vitamin A values in source_values[21] are mg RAE. Legacy plant-food IU
// values use 0.00005 mg RAE/IU; egg and cheese values use 0.0003 mg RAE/IU.

struct Food {
    std::string_view name;
    IngredientGroup group;
    std::array<double, kSourceRows> source_values;
    double minimum_grams;
    double maximum_grams;
    double diverse_minimum_grams;
};

inline constexpr std::array<Food, kFoodCount> kFoods{{
Food{"romaine lettuce", IngredientGroup::LeafyGreens, {94, 15.98, 1.1562, 0.282, 3.0926, 1.974, 31.02, 0.04512, 0.9118, 13.16, 0.1457, 28.2, 232.18, 0.000376, 7.52, 0.2162, 0.06768, 0.06298, 0.29422, 0.06956, 0, 0.40984, 3.76, 0, 0.1222, 0.09635}, 0, 1000, 30},
Food{"collard greens", IngredientGroup::LeafyGreens, {190, 60.8, 5.738, 1.159, 10.298, 7.6, 440.8, 0.0874, 0.893, 51.3, 1.2502, 47.5, 404.7, 0.00247, 32.3, 0.399, 0.1026, 0.247, 1.4098, 0.3135, 0, 0.4769, 67.07, 0, 4.294, 0.83049}, 0, 1000, 20},
Food{"spinach", IngredientGroup::LeafyGreens, {180, 41.4, 5.148, 0.702, 6.534, 3.96, 178.2, 0.234, 4.878, 142.2, 1.6146, 88.2, 1004.4, 0.0018, 142.2, 0.954, 0.1404, 0.3402, 1.3032, 0.351, 0, 0.8442, 50.58, 0, 3.654, 0.86922}, 0, 1000, 30},
Food{"roma tomatoes", IngredientGroup::PreferredVegetables, {180, 32.4, 1.58, 0.36, 7, 2.16, 18, 0.11, 0.49, 19.8, 0.21, 43.2, 426.6, 0, 9, 0.31, 0.07, 0.03, 1.07, 0.14, 0, 0.07497, 24.66, 0, 0.97, 0.01422}, 0, 80, 30},
Food{"cucumbers", IngredientGroup::PreferredVegetables, {104, 15.6, 0.676, 0.1144, 3.7752, 0.52, 16.64, 0.04264, 0.2912, 13.52, 0.08216, 24.96, 152.88, 0.000312, 2.08, 0.208, 0.02808, 0.03432, 0.10192, 0.0416, 0, 0.0052, 2.912, 0, 0.0312, 0.017056}, 0, 40, 20},
Food{"red onion", IngredientGroup::PreferredVegetables, {210, 92.4, 2.86, 0.4, 21.31, 2.94, 46.2, 0.14, 0.5, 23.1, 0.32, 73.5, 348.6, 0.00126, 6.3, 0.44, 0.09, 0.05, 0.35, 0.27, 0, 0.00021, 10.92, 0, 0.04, 0.00105}, 0, 1000, 10},
Food{"pine nuts", IngredientGroup::Nuts, {100, 673, 13.69, 68.37, 13.08, 3.7, 16, 1.324, 5.53, 251, 8.802, 575, 597, 0.0007, 2, 6.45, 0.364, 0.227, 4.387, 0.094, 0, 0.001, 0.8, 0, 9.33, 0.0539}, 0, 1000, 5},
Food{"pumpkin seeds", IngredientGroup::Seeds, {32.25, 180.2775, 9.749175, 15.818625, 3.453975, 1.935, 14.835, 0.4331175, 2.84445, 190.92, 1.4651175, 397.6425, 260.9025, 0.0030315, 2.2575, 2.518725, 0.0880425, 0.0493425, 1.6083075, 0.0461175, 0, 0.0003225, 0.61275, 0, 0.70305, 0.00235425}, 0, 1000, 5},
Food{"chia seeds", IngredientGroup::Seeds, {100, 486, 16.54, 30.74, 42.12, 34.4, 631, 0.924, 7.72, 335, 2.723, 860, 407, 0.0552, 16, 4.58, 0.62, 0.17, 8.83, 0, 0, 0.0027, 1.6, 0, 0.5, 0}, 0, 1000, 5},
Food{"sunflower seeds", IngredientGroup::Seeds, {100, 584, 20.78, 51.46, 20, 8.6, 78, 1.8, 5.25, 325, 1.95, 660, 645, 0.053, 9, 5, 1.48, 0.355, 8.335, 1.345, 0, 0.003, 1.4, 0, 35.17, 0}, 0, 1000, 5},
Food{"shiitake mushrms", IngredientGroup::Mushrooms, {72.5, 24.65, 1.624, 0.35525, 4.92275, 1.8125, 1.45, 0.10295, 0.29725, 14.5, 0.16675, 81.2, 220.4, 0.0041325, 6.525, 0.74675, 0.010875, 0.157325, 2.810825, 0.212425, 0, 0, 0.22, 0.00029, 0, 0}, 0, 30, 10},
Food{"wht btn mushrms", IngredientGroup::Mushrooms, {100, 22, 3.09, 0.34, 3.26, 1, 3, 0.318, 0.5, 9, 0.047, 86, 318, 0.0093, 5, 0.52, 0.081, 0.402, 3.607, 0.104, 4e-05, 0, 2.1, 0.0002, 0.01, 0}, 0, 30, 10},
Food{"brocoli", IngredientGroup::PreferredVegetables, {156, 53.04, 4.3992, 0.5772, 10.3584, 4.056, 73.32, 0.07644, 1.1388, 32.76, 0.3276, 102.96, 492.96, 0.0039, 51.48, 0.6396, 0.11076, 0.18252, 0.99684, 0.273, 0, 0.04836, 139.152, 0, 1.2168, 0.158496}, 0, 80, 20},
Food{"bell pepper", IngredientGroup::PreferredVegetables, {92, 23.92, 0.9108, 0.276, 5.5476, 1.932, 6.44, 0.01564, 0.3956, 11.04, 0.10304, 23.92, 194.12, 9.2e-05, 3.68, 0.23, 0.04968, 0.0782, 0.90068, 0.26772, 0, 0.14444, 117.484, 0, 1.4536, 0.004508}, 0, 1000, 20},
Food{"egg", IngredientGroup::EggsAndDairy, {50, 77.5, 6.29, 5.305, 0.56, 0, 25, 0.0065, 0.595, 5, 0.013, 86, 63, 0.0154, 62, 0.525, 0.033, 0.2565, 0.032, 0.0605, 0.000555, 0.0745, 0, 0.0011, 0.515, 0.00015}, 0, 150, 50},
Food{"chedar cheese", IngredientGroup::EggsAndDairy, {28.4, 114, 7.06, 9.23, 0.36, 0, 204.4, 0.01, 0.19, 7.94, 0, 145.15, 27.78, 0.00394, 176.05, 0.88, 0.01, 0.11, 0.02, 0.02, 0.00024, 0.072435, 0, 0.00017, 0.12, 0.00079}, 0, 40, 10},
    // USDA SR28 UV-exposed portabella D value is used as the vitamin D
    // value; the remaining composition follows the raw white mushroom row.
Food{"UV-exposed portabella mushrooms", IngredientGroup::Mushrooms, {100, 22, 2.11, 0.35, 3.87, 1.3, 3, 0.286, 0.31, 10, 0.069, 108, 364, 0.0186, 9, 0.53, 0.059, 0.13, 4.494, 0.148, 5e-05, 0, 0, 0.0284, 0.02, 0}, 0, 100, 15},
}};

inline constexpr std::array<std::string_view, kSourceRows> kSourceRowNames{{
    "wt (g)", "cal (kCal)",
    "protein (g)", "fat (g)",
    "carb (g)", "fiber (g)",
    "Ca (mg)", "Cu (mg)",
    "Fe (mg)", "Mg (mg)",
    "Mn (mg)", "P  (mg)",
    "K  (mg)", "Se (mg)",
    "Na (mg)", "Zn (mg)",
    "B1 (mg)", "B2 (mg)",
    "B3 (mg)", "B6 (mg)",
    "B12(mg)", "Vitamin A (mg RAE)",
    "C  (mg)", "D  (mg)",
    "E  (mg)", "K  (mg)"
}};
} // namespace diet
