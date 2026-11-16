#!/usr/bin/env python3
"""Globally minimize salad mass using identity-reviewed plant-food candidates."""

from __future__ import annotations

import argparse
import csv
import io
import re
import zipfile
from pathlib import Path

import numpy as np
from scipy.optimize import linprog


NUTRIENT_TARGETS = [
    ("Calcium", 1000.0, "mg", "calcium_mg_100g", 1.0),
    ("Copper", 0.9, "mg", "copper_mg_100g", 1.0),
    ("Iron", 8.0, "mg", "iron_mg_100g", 1.0),
    ("Magnesium", 350.0, "mg", "magnesium_mg_100g", 1.0),
    ("Manganese", 2.3, "mg", "manganese_mg_100g", 1.0),
    ("Phosphorus", 700.0, "mg", "phosphorus_mg_100g", 1.0),
    ("Potassium", 3400.0, "mg", "potassium_mg_100g", 1.0),
    ("Selenium", 0.055, "µg", "selenium_ug_100g", 0.001),
    ("Sodium", 0.0, "mg", "sodium_mg_100g", 1.0),
    ("Zinc", 11.0, "mg", "zinc_mg_100g", 1.0),
    ("Vitamin B1", 1.2, "mg", "vitamin_b1_mg_100g", 1.0),
    ("Vitamin B2", 1.3, "mg", "vitamin_b2_mg_100g", 1.0),
    ("Vitamin B3", 16.0, "mg", "vitamin_b3_mg_100g", 1.0),
    ("Vitamin B6", 1.3, "mg", "vitamin_b6_mg_100g", 1.0),
    ("Vitamin B12", 0.0024, "µg", "vitamin_b12_ug_100g", 0.001),
    ("Vitamin A", 0.9, "µg RAE", "vitamin_a_ug_rae_100g", 0.001),
    ("Vitamin C", 90.0, "mg", "vitamin_c_mg_100g", 1.0),
    ("Vitamin D", 0.015, "µg", "vitamin_d_ug_100g", 0.001),
    ("Vitamin E", 15.0, "mg", "vitamin_e_mg_100g", 1.0),
    ("Vitamin K", 0.12, "µg", "vitamin_k_ug_100g", 0.001),
]
MACROS = [
    ("calories_kcal_100g", {"208", "1008"}, {"2047", "2048"}),
    ("protein_g_100g", {"203"}, set()),
    ("fat_g_100g", {"204"}, set()),
    ("carbohydrate_g_100g", {"205"}, set()),
    ("fiber_g_100g", {"291"}, set()),
]
REQUIRED = [i for i, row in enumerate(NUTRIENT_TARGETS) if i != 8]


def normalize_nutrient_number(value: str) -> str:
    """Normalize USDA nutrient_nbr values such as 203, 203.0, or whitespace."""
    text = (value or "").strip()
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


def rows_from(source: Path, filename: str):
    if source.is_dir():
        matches = list(source.rglob(filename))
        if not matches:
            raise FileNotFoundError(f"{filename} not found under {source}")
        with min(matches, key=lambda p: len(p.parts)).open(encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f)
        return
    with zipfile.ZipFile(source) as archive:
        members = [n for n in archive.namelist()
                   if Path(n.replace("\\", "/")).name.casefold() == filename.casefold()]
        if not members:
            raise FileNotFoundError(f"{filename} not found in {source}")
        member = min(members, key=lambda n: n.count("/") + n.count("\\"))
        with io.TextIOWrapper(archive.open(member), encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f)


def read_base_model(repo: Path):
    food_text = (repo / "include/diet/food_data.hpp").read_text(encoding="utf-8")
    foods = []
    pattern = re.compile(
        r'Food\{"([^\"]+)",\s*IngredientGroup::(\w+),\s*\{([^}]*)\},\s*'
        r'([0-9.eE+-]+),\s*([0-9.eE+-]+),\s*([0-9.eE+-]+)\}'
    )
    for match in pattern.finditer(food_text):
        name, group, raw, lo, hi, diverse_lo = match.groups()
        values = [float(v.strip()) for v in raw.split(",")]
        if len(values) != 26:
            raise ValueError(f"Unexpected source row count for {name}")
        portion = values[0]
        foods.append({
            "name": name, "group": group, "cal": values[1] / portion,
            "macros": [v / portion for v in values[2:6]],
            "nutrients": [v / portion for v in values[6:26]],
            "lo": float(diverse_lo), "sparse_lo": float(lo), "hi": float(hi),
            "source": "legacy project table",
        })
    if not foods:
        raise ValueError("Could not parse project food table")

    model_text = (repo / "src/model.cpp").read_text(encoding="utf-8")
    def cpp_array(marker: str) -> list[float]:
        m = re.search(re.escape(marker) + r"\s*\{\{(.*?)\}\}", model_text, re.S)
        if not m:
            raise ValueError(f"Could not find {marker} in src/model.cpp")
        return [float(x.strip()) for x in m.group(1).split(",") if x.strip()]
    chicken = cpp_array("chicken_per_100g")
    chicken_macros = cpp_array("chicken_macros_per_100g")
    portion_m = re.search(r"fixed_chicken_grams\s*=\s*([0-9.]+)",
                          (repo / "include/diet/model.hpp").read_text(encoding="utf-8"))
    calories_m = re.search(
        r"model\.fixed_calories\s*=\s*([0-9.]+)\s*\*\s*model\.fixed_chicken_grams\s*/\s*100\.0",
        model_text,
    )
    if len(chicken) != 20 or len(chicken_macros) != 4 or not portion_m or not calories_m:
        raise ValueError("Unexpected fixed chicken model layout")
    portion = float(portion_m.group(1))
    fixed = {
        "nutrients": np.array(chicken) * portion / 100.0,
        "macros": np.array(chicken_macros) * portion / 100.0,
        "calories": float(calories_m.group(1)) * portion / 100.0,
    }
    return foods, fixed


def candidate_rows(review_path: Path, sr_path: Path):
    with review_path.open(encoding="utf-8-sig", newline="") as f:
        selected = [r for r in csv.DictReader(f)
                    if r.get("candidate_include", "").strip().casefold() in {"yes", "y", "1", "true"}]
    if not selected:
        raise ValueError("No rows marked candidate_include=yes in the review CSV")
    for row in selected:
        if row.get("identity_review", "").strip().casefold() != "confirmed":
            raise ValueError(f"FDC {row.get('fdc_id')}: set identity_review=confirmed after review")
        try:
            row["_min"] = float(row["portion_min_g"] or 0.0)
            row["_max"] = float(row["portion_max_g"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"FDC {row.get('fdc_id')}: provide portion_min_g and portion_max_g") from exc
        if row["_min"] < 0 or row["_max"] <= row["_min"]:
            raise ValueError(f"FDC {row.get('fdc_id')}: invalid reviewed portion bounds")

    # Load exactly the SR Legacy records selected by the reviewer. No fuzzy
    # identity matching is performed here.
    sr_ids = {r.get("sr_legacy_fdc_id", "").strip() for r in selected
              if r.get("sr_legacy_fdc_id", "").strip()}
    sr_profiles = {}
    sr_descriptions = {}
    if sr_ids:
        for food in rows_from(sr_path, "food.csv"):
            if food.get("fdc_id") in sr_ids:
                sr_descriptions[food["fdc_id"]] = food.get("description", "")
                sr_profiles[food["fdc_id"]] = {}
        if set(sr_ids) != set(sr_profiles):
            raise ValueError(f"SR Legacy FDC IDs missing from archive: {sorted(set(sr_ids)-set(sr_profiles))}")
        nutrients = {r["id"]: normalize_nutrient_number(r.get("nutrient_nbr", ""))
                     for r in rows_from(sr_path, "nutrient.csv")}
        number_to_fields = {}
        for field, numbers, energy_ids in MACROS:
            for number in numbers:
                number_to_fields[number] = field
            for item in energy_ids:
                # SR Legacy uses the regular Energy nutrient row; its ID is not
                # used as a Foundation Atwater energy value.
                if item in nutrients and nutrients[item] in numbers:
                    number_to_fields[nutrients[item]] = field
        for _, numbers, _, field, _ in NUTRIENT_TARGETS:
            for number in numbers:
                number_to_fields[number] = field
        for row in rows_from(sr_path, "food_nutrient.csv"):
            fdc_id = row.get("fdc_id", "")
            if fdc_id not in sr_profiles or row.get("amount", "") == "":
                continue
            field = number_to_fields.get(nutrients.get(row.get("nutrient_id", ""), ""))
            if field and field not in sr_profiles[fdc_id]:
                sr_profiles[fdc_id][field] = float(row["amount"])

    converted = []
    for row in selected:
        fallback_id = row.get("sr_legacy_fdc_id", "").strip()
        if fallback_id:
            expected = row.get("sr_legacy_description", "").strip()
            if expected and sr_descriptions[fallback_id] != expected:
                raise ValueError(f"SR Legacy description mismatch for FDC {fallback_id}")
        sr = sr_profiles.get(fallback_id, {})
        fields = ["calories_kcal_100g", "protein_g_100g", "fat_g_100g",
                  "carbohydrate_g_100g", "fiber_g_100g"]
        fields += [r[3] for r in NUTRIENT_TARGETS]
        profile = {}
        source_counts = {"Foundation": 0, "SR Legacy fallback": 0}
        for field in fields:
            raw = row.get(field, "").strip()
            if raw:
                profile[field] = float(raw)
                source_counts["Foundation"] += 1
            elif field in sr:
                profile[field] = sr[field]
                source_counts["SR Legacy fallback"] += 1
            else:
                raise ValueError(
                    f"FDC {row.get('fdc_id')}: {field} is missing in Foundation and selected SR Legacy record"
                )
        if fallback_id and not row.get("sr_legacy_description", "").strip():
            raise ValueError(f"FDC {fallback_id}: record its exact SR Legacy description in review CSV")
        micro_fields = {r[3]: r[4] for r in NUTRIENT_TARGETS}
        nutrients = [profile[r[3]] * micro_fields[r[3]] for r in NUTRIENT_TARGETS]
        converted.append({
            "name": f"{row.get('description', '').strip()} [FDC {row.get('fdc_id')}]",
            "group": row.get("ingredient_group", "Other"),
            "cal": profile["calories_kcal_100g"] / 100.0,
            "macros": [profile["protein_g_100g"], profile["fat_g_100g"],
                       profile["carbohydrate_g_100g"], profile["fiber_g_100g"]],
            "nutrients": nutrients,
            "lo": row["_min"], "hi": row["_max"],
            "source": f"Foundation {source_counts['Foundation']}; SR fallback {source_counts['SR Legacy fallback']}",
        })
    return converted


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path,
                        default=repo / "data/reports/plant_candidate_review.csv")
    parser.add_argument("--sr-legacy", type=Path,
                        default=repo / "data/source/FoodData_Central_sr_legacy_food_csv_2018-04.zip")
    parser.add_argument("--profile", choices=("sparse", "diverse"), default="sparse")
    parser.add_argument("--calorie-cap", type=float, default=700.0)
    parser.add_argument("--nutrient-cap-multiple", type=float, default=3.0)
    args = parser.parse_args()
    try:
        base, fixed = read_base_model(repo)
        added = candidate_rows(args.review.expanduser().resolve(), args.sr_legacy.expanduser().resolve())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    foods = base + added
    targets = np.array([r[1] for r in NUTRIENT_TARGETS])
    calorie = np.array([f["cal"] for f in foods])
    nutrient = np.array([f["nutrients"] for f in foods], dtype=float).T
    lower = np.array([
        (f["lo"] if args.profile == "diverse" else f["sparse_lo"])
        if i < len(base) else f["lo"]
        for i, f in enumerate(foods)
    ])
    upper = np.array([f["hi"] for f in foods])
    constraints = []
    limits = []
    for i in REQUIRED:
        # Normalize each row by its project target for consistent LP scaling.
        constraints.extend([-nutrient[i] / targets[i], nutrient[i] / targets[i]])
        limits.extend([fixed["nutrients"][i] / targets[i] - 1.0,
                       args.nutrient_cap_multiple - fixed["nutrients"][i] / targets[i]])
    constraints.append(calorie / args.calorie_cap)
    limits.append(1.0)
    result = linprog(np.ones(n), A_ub=np.array(constraints), b_ub=np.array(limits),
                     bounds=list(zip(lower, upper)), method="highs")
    if not result.success:
        print(f"Exploration infeasible for {args.profile}: {result.message}")
        return 2
    x = result.x
    totals = nutrient @ x + fixed["nutrients"]
    salad_calories = float(calorie @ x)
    macros = np.array([f["macros"] for f in foods]).T @ x
    chicken_macros = fixed["macros"]
    whole_macros = macros + chicken_macros
    sodium = totals[8]

    print(f"Exploration profile: {args.profile}")
    print("Solver: HiGHS linear program; status: optimal")
    print(f"Reviewed candidates included: {len(added)}")
    print(f"Required nutrient band: 100% to {args.nutrient_cap_multiple * 100:.0f}% of project targets")
    print(f"Salad: {x.sum():.2f} g, {salad_calories:.2f} kcal")
    print(f"Whole plate: {salad_calories + fixed['calories']:.2f} kcal")
    print("\nSelected ingredients (grams)")
    for i, amount in enumerate(x):
        if amount > 1e-5:
            print(f"  {foods[i]['group']:<23} {foods[i]['name']:<56} {amount:8.2f}  [{foods[i]['source']}]")
    print("\nMacronutrient profile (g; net carbs = total carbohydrate - fiber)")
    print(f"  {'Macro':<18} {'Salad':>10} {'Chicken':>10} {'Whole plate':>13}")
    for index, name in enumerate(("Protein", "Fat", "Carbohydrate", "Fiber")):
        print(f"  {name:<18} {macros[index]:10.2f} {chicken_macros[index]:10.2f} {whole_macros[index]:13.2f}")
    print(f"  {'Net carbs':<18} {max(0.0, macros[2] - macros[3]):10.2f} "
          f"{max(0.0, chicken_macros[2] - chicken_macros[3]):10.2f} "
          f"{max(0.0, whole_macros[2] - whole_macros[3]):13.2f}")
    print("\nNutrient coverage for salad + chicken")
    print(f"  {'Nutrient':<14} {'Total':>10} {'Target':>10} {'Coverage':>10} {'Band':>10}")
    for i, (name, target, unit, _, display_factor) in enumerate(NUTRIENT_TARGETS):
        total_display = totals[i] / display_factor
        target_display = "—" if i == 8 else f"{target / display_factor:.2f}"
        coverage = "tracked" if i == 8 else f"{totals[i] / target * 100.0:.2f}%"
        band = "tracked" if i == 8 else (
            "PASS" if 1.0 - 1e-7 <= totals[i] / target <= args.nutrient_cap_multiple + 1e-7
            else "OUT")
        print(f"  {name:<14} {total_display:10.2f} {target_display:>10} {unit:<7} {coverage:>9} {band:>7}")
    print("\nSodium reference points (tracked, not constrained)")
    print(f"  Total, salad + chicken: {sodium:.2f} mg")
    print(f"  Adequate Intake (AI): 1,500.00 mg ({sodium / 1500 * 100:.2f}%; "
          f"{abs(1500 - sodium):.2f} mg {'below' if sodium < 1500 else 'above'})")
    print(f"  Chronic Disease Risk Reduction (CDRR): 2,300.00 mg ({sodium / 2300 * 100:.2f}%; "
          f"{abs(2300 - sodium):.2f} mg {'below' if sodium < 2300 else 'above'})")
    print(f"  Position: {'below the AI reference point' if sodium < 1500 else 'at or above the AI reference point'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
