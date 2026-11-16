#!/usr/bin/env python3
"""List exact-description SR Legacy matches for Foundation candidate review.

The output is a manual review aid only. It never selects or approves a fallback.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import zipfile
from collections import defaultdict
from pathlib import Path


MACROS = {
    "calories_kcal_100g": {"208", "1008"},
    "protein_g_100g": {"203"},
    "fat_g_100g": {"204"},
    "carbohydrate_g_100g": {"205"},
    "fiber_g_100g": {"291"},
}
NUTRIENTS = {
    "calcium_mg_100g": {"301"}, "copper_mg_100g": {"312"},
    "iron_mg_100g": {"303"}, "magnesium_mg_100g": {"304"},
    "manganese_mg_100g": {"315"}, "phosphorus_mg_100g": {"305"},
    "potassium_mg_100g": {"306"}, "selenium_ug_100g": {"317"},
    "sodium_mg_100g": {"307"}, "zinc_mg_100g": {"309"},
    "vitamin_b1_mg_100g": {"404"}, "vitamin_b2_mg_100g": {"405"},
    "vitamin_b3_mg_100g": {"406"}, "vitamin_b6_mg_100g": {"415"},
    "vitamin_b12_ug_100g": {"418"}, "vitamin_a_ug_rae_100g": {"320"},
    "vitamin_c_mg_100g": {"401"}, "vitamin_d_ug_100g": {"328"},
    "vitamin_e_mg_100g": {"323"}, "vitamin_k_ug_100g": {"430"},
}
PROFILE_FIELDS = list(MACROS) + list(NUTRIENTS)


def rows_from(source: Path, filename: str):
    if source.is_dir():
        matches = list(source.rglob(filename))
        if not matches:
            raise FileNotFoundError(f"{filename} not found under {source}")
        with min(matches, key=lambda p: len(p.parts)).open(encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)
        return
    with zipfile.ZipFile(source) as archive:
        members = [name for name in archive.namelist()
                   if Path(name.replace("\\", "/")).name.casefold() == filename.casefold()]
        if not members:
            raise FileNotFoundError(f"{filename} not found in {source}")
        member = min(members, key=lambda name: name.count("/") + name.count("\\"))
        with io.TextIOWrapper(archive.open(member), encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)


def normalize_number(value: str) -> str:
    text = (value or "").strip()
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


def normalize_description(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", type=Path, required=True,
                        help="Full FoodData Central CSV ZIP or extracted directory")
    parser.add_argument("--review", type=Path,
                        default=repo / "data/reports/plant_candidate_review.csv")
    parser.add_argument("--output", type=Path,
                        default=repo / "data/reports/plant_candidate_sr_legacy_matches.csv")
    args = parser.parse_args()
    source = args.full.expanduser().resolve()

    with args.review.expanduser().resolve().open(encoding="utf-8-sig", newline="") as stream:
        candidates = list(csv.DictReader(stream))
    by_description = defaultdict(list)
    for row in candidates:
        key = normalize_description(row.get("description", ""))
        if key:
            by_description[key].append(row)

    matches = defaultdict(list)
    legacy_ids = set()
    legacy_food_count = 0
    for food in rows_from(source, "food.csv"):
        if "sr_legacy" not in food.get("data_type", "").casefold():
            continue
        legacy_food_count += 1
        key = normalize_description(food.get("description", ""))
        if key in by_description:
            fdc_id = food.get("fdc_id", "")
            item = {"fdc_id": fdc_id, "description": food.get("description", "")}
            matches[key].append(item)
            legacy_ids.add(fdc_id)
    if legacy_food_count == 0:
        parser.error("No SR Legacy food records found in the supplied full archive")

    nutrient_number = {
        row.get("id", ""): normalize_number(row.get("nutrient_nbr", ""))
        for row in rows_from(source, "nutrient.csv")
    }
    number_to_field = {}
    for field, numbers in {**MACROS, **NUTRIENTS}.items():
        for number in numbers:
            number_to_field[number] = field
    profile_by_id = defaultdict(dict)
    for row in rows_from(source, "food_nutrient.csv"):
        food_id = row.get("fdc_id", "")
        if food_id not in legacy_ids or not row.get("amount", "").strip():
            continue
        number = nutrient_number.get(row.get("nutrient_id", ""), "")
        field = number_to_field.get(number)
        if field and field not in profile_by_id[food_id]:
            profile_by_id[food_id][field] = row["amount"]

    output_rows = []
    for candidate in candidates:
        key = normalize_description(candidate.get("description", ""))
        found = matches.get(key, [])
        missing = [field for field in PROFILE_FIELDS if not candidate.get(field, "").strip()]
        if not found:
            output_rows.append({
                "foundation_fdc_id": candidate.get("fdc_id", ""),
                "foundation_description": candidate.get("description", ""),
                "foundation_missing_fields": ";".join(missing),
                "sr_legacy_fdc_id": "",
                "sr_legacy_description": "",
                "exact_description_match": "no",
                "fallback_covers_missing_fields": "",
                "still_missing_after_fallback": ";".join(missing),
                "review_status": "no exact description match",
            })
            continue
        for legacy in found:
            profile = profile_by_id[legacy["fdc_id"]]
            covered = [field for field in missing if field in profile]
            unresolved = [field for field in missing if field not in profile]
            output_rows.append({
                "foundation_fdc_id": candidate.get("fdc_id", ""),
                "foundation_description": candidate.get("description", ""),
                "foundation_missing_fields": ";".join(missing),
                "sr_legacy_fdc_id": legacy["fdc_id"],
                "sr_legacy_description": legacy["description"],
                "exact_description_match": "yes",
                "fallback_covers_missing_fields": ";".join(covered),
                "still_missing_after_fallback": ";".join(unresolved),
                "review_status": "manual identity and field review required",
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    columns = ["foundation_fdc_id", "foundation_description", "foundation_missing_fields",
               "sr_legacy_fdc_id", "sr_legacy_description", "exact_description_match",
               "fallback_covers_missing_fields", "still_missing_after_fallback", "review_status"]
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(output_rows)
    matched = sum(row["exact_description_match"] == "yes" for row in output_rows)
    full_coverage = sum(not row["still_missing_after_fallback"] for row in output_rows
                        if row["exact_description_match"] == "yes")
    print(f"Wrote {len(output_rows)} candidate/match rows to {args.output}")
    print(f"Exact-description SR Legacy matches: {matched}; matched profiles cover all missing fields: {full_coverage}")
    print("Matches are suggestions only; confirm food form and nutrient applicability before using a fallback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
