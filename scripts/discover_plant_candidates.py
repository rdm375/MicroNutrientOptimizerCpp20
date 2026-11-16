#!/usr/bin/env python3
"""Create a reviewable catalog of Foundation Foods plant ingredients.

This is a discovery report, not an automatic crosswalk. Food identity and
portion limits must be reviewed before a row is used by the explorer.
"""

from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path


# Project-unit output columns. The internal optimizer stores the five
# microgram-based nutrients as milligrams; the review CSV keeps readable units.
NUTRIENTS = [
    ("calcium_mg_100g", {"301"}, False),
    ("copper_mg_100g", {"312"}, False),
    ("iron_mg_100g", {"303"}, False),
    ("magnesium_mg_100g", {"304"}, False),
    ("manganese_mg_100g", {"315"}, False),
    ("phosphorus_mg_100g", {"305"}, False),
    ("potassium_mg_100g", {"306"}, False),
    ("selenium_ug_100g", {"317"}, False),
    ("sodium_mg_100g", {"307"}, False),
    ("zinc_mg_100g", {"309"}, False),
    ("vitamin_b1_mg_100g", {"404"}, False),
    ("vitamin_b2_mg_100g", {"405"}, False),
    ("vitamin_b3_mg_100g", {"406"}, False),
    ("vitamin_b6_mg_100g", {"415"}, False),
    ("vitamin_b12_ug_100g", {"418"}, False),
    ("vitamin_a_ug_rae_100g", {"320"}, False),
    ("vitamin_c_mg_100g", {"401"}, False),
    ("vitamin_d_ug_100g", {"328"}, False),
    ("vitamin_e_mg_100g", {"323"}, False),
    ("vitamin_k_ug_100g", {"430"}, False),
]
MACROS = [
    ("calories_kcal_100g", {"208", "1008"}, {"2047", "2048"}),
    ("protein_g_100g", {"203"}, set()),
    ("fat_g_100g", {"204"}, set()),
    ("carbohydrate_g_100g", {"205"}, set()),
    ("fiber_g_100g", {"291"}, set()),
]
REQUIRED_COLUMNS = {name for name, _, _ in NUTRIENTS if name != "sodium_mg_100g"}
PLANT_CATEGORY_TERMS = (
    "vegetable", "fruit", "nut", "seed", "legume", "spice", "herb",
)
LEAF_TERMS = (
    "lettuce", "spinach", "collard", "kale", "chard", "arugula", "rocket",
    "endive", "escarole", "cress", "mustard green", "turnip green",
    "beet green", "radicchio", "bok choy", "cabbage", "leaf",
)
FORM_FLAGS = (
    "raw", "cooked", "boiled", "roasted", "grilled", "dried", "frozen",
    "canned", "pickled", "salted", "oil", "juice", "powder", "flour",
    "sauce", "puree", "with added",
)


def table_rows(source: Path, filename: str):
    if source.is_dir():
        matches = list(source.rglob(filename))
        if not matches:
            raise FileNotFoundError(f"{filename} not found under {source}")
        path = min(matches, key=lambda p: len(p.parts))
        with path.open(encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)
        return
    with zipfile.ZipFile(source) as archive:
        members = [n for n in archive.namelist()
                   if Path(n.replace("\\", "/")).name.casefold() == filename.casefold()]
        if not members:
            raise FileNotFoundError(f"{filename} not found in {source}")
        member = min(members, key=lambda n: n.count("/") + n.count("\\"))
        with io.TextIOWrapper(archive.open(member), encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)


def group_for(description: str, category: str) -> str:
    text = description.casefold()
    cat = category.casefold()
    if "olive" in text:
        return "Olives"
    if any(token in text or token in cat for token in ("mushroom", "fungus", "fungi")):
        return "Mushrooms"
    if any(token in text for token in LEAF_TERMS):
        return "Leafy greens"
    if any(token in text for token in ("seed", "pepita")):
        return "Seeds"
    if any(token in text for token in ("nut", "almond", "cashew", "pecan", "walnut", "pistachio")):
        return "Nuts"
    if "legume" in cat or "legume" in text or any(t in text for t in ("bean", "lentil", "pea,", "chickpea")):
        return "Legumes"
    if "fruit" in cat:
        return "Fruit"
    if "spice" in cat or "herb" in cat:
        return "Herbs and spices"
    return "Preferred vegetables"


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foundation", type=Path, required=True,
                        help="Full FoodData Central CSV ZIP or extracted directory")
    parser.add_argument("--output", type=Path,
                        default=repo / "data/reports/plant_candidate_review.csv")
    args = parser.parse_args()
    source = args.foundation.expanduser().resolve()

    categories = {row["id"]: row.get("description", "")
                  for row in table_rows(source, "food_category.csv")}
    candidates = {}
    for row in table_rows(source, "food.csv"):
        if "foundation" not in row.get("data_type", "").casefold():
            continue
        category = categories.get(row.get("food_category_id", ""), "")
        if not any(term in category.casefold() for term in PLANT_CATEGORY_TERMS):
            continue
        fdc_id = row.get("fdc_id", "")
        description = row.get("description", "")
        if not fdc_id or not description:
            continue
        desc = description.casefold()
        flags = ";".join(term for term in FORM_FLAGS if term in desc)
        candidates[fdc_id] = {
            "fdc_id": fdc_id,
            "description": description,
            "food_category": category,
            "ingredient_group": group_for(description, category),
            "publication_date": row.get("publication_date", ""),
            "form_flags_review": flags,
            "calories_kcal_100g": "",
            **{name: "" for name, _, _ in NUTRIENTS},
            "foundation_reported_count": 0,
            "foundation_missing_required": "",
            "foundation_solver_ready": "no",
            "candidate_include": "",
            "identity_review": "pending",
            "portion_min_g": "",
            "portion_max_g": "",
            "sr_legacy_fdc_id": "",
            "sr_legacy_description": "",
        }

    nutrient_meta = list(table_rows(source, "nutrient.csv"))
    by_id = {row["id"]: row for row in nutrient_meta}
    by_number = {row.get("nutrient_nbr", ""): row for row in nutrient_meta}
    selected = {}
    for name, numbers, energy_ids in MACROS:
        for number in numbers:
            if number in by_number:
                selected[by_number[number]["id"]] = (name, 1)
        for nutrient_id in energy_ids:
            if nutrient_id in by_id:
                # Energy-specific (2048) takes priority over general (2047),
                # both before the regular 208/1008 rows.
                priority = 3 if nutrient_id == "2048" else 2
                selected[nutrient_id] = (name, priority)
    for name, numbers, _ in NUTRIENTS:
        for number in numbers:
            if number in by_number:
                selected[by_number[number]["id"]] = (name, 1)

    priorities = {}
    for row in table_rows(source, "food_nutrient.csv"):
        fdc_id = row.get("fdc_id", "")
        nutrient_id = row.get("nutrient_id", "")
        if fdc_id not in candidates or nutrient_id not in selected or row.get("amount", "") == "":
            continue
        name, priority = selected[nutrient_id]
        key = (fdc_id, name)
        if priority >= priorities.get(key, 0):
            candidates[fdc_id][name] = row["amount"]
            priorities[key] = priority

    required_cols = ["calories_kcal_100g", "protein_g_100g", "fat_g_100g",
                     "carbohydrate_g_100g", "fiber_g_100g"]
    # Sodium is not an optimization constraint, but it is part of the report.
    required_cols += [name for name, _, _ in NUTRIENTS]
    for candidate in candidates.values():
        available = sum(candidate.get(col, "") != "" for col in required_cols)
        missing = [col for col in required_cols if candidate.get(col, "") == ""]
        candidate["foundation_reported_count"] = available
        candidate["foundation_missing_required"] = ";".join(missing)
        candidate["foundation_solver_ready"] = "yes" if not missing else "no"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(next(iter(candidates.values())).keys()) if candidates else [
        "fdc_id", "description", "food_category", "ingredient_group",
    ]
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(candidates.values(),
                                key=lambda r: (r["ingredient_group"], r["description"].casefold())))
    ready = sum(r["foundation_solver_ready"] == "yes" for r in candidates.values())
    print(f"Wrote {len(candidates)} plant-food records to {args.output}")
    print(f"Foundation-only complete profiles: {ready}; incomplete profiles: {len(candidates) - ready}")
    print("Rows remain unapproved; confirm food identity and portion bounds before optimization.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
