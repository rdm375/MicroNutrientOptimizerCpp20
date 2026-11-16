#!/usr/bin/env python3
"""Compare the current C++ legacy nutrient table with USDA SR Legacy CSV data."""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import zipfile
from pathlib import Path


DATASET_RELEASE = "FoodData Central SR Legacy, April 2018"
EXPECTED_NUTRIENTS = {
    "Energy": ("208", "kcal", 1, 1.0),
    "Protein": ("203", "g", 2, 1.0),
    "Total lipid (fat)": ("204", "g", 3, 1.0),
    "Carbohydrate, by difference": ("205", "g", 4, 1.0),
    "Fiber, total dietary": ("291", "g", 5, 1.0),
    "Calcium, Ca": ("301", "mg", 6, 1.0),
    "Copper, Cu": ("312", "mg", 7, 1.0),
    "Iron, Fe": ("303", "mg", 8, 1.0),
    "Magnesium, Mg": ("304", "mg", 9, 1.0),
    "Manganese, Mn": ("315", "mg", 10, 1.0),
    "Phosphorus, P": ("305", "mg", 11, 1.0),
    "Potassium, K": ("306", "mg", 12, 1.0),
    "Selenium, Se": ("317", "µg", 13, 1000.0),
    "Sodium, Na": ("307", "mg", 14, 1.0),
    "Zinc, Zn": ("309", "mg", 15, 1.0),
    "Thiamin": ("404", "mg", 16, 1.0),
    "Riboflavin": ("405", "mg", 17, 1.0),
    "Niacin": ("406", "mg", 18, 1.0),
    "Vitamin B-6": ("415", "mg", 19, 1.0),
    "Vitamin B-12": ("418", "µg", 20, 1000.0),
    "Vitamin A, RAE": ("320", "µg RAE", 21, 1000.0),
    "Vitamin C, total ascorbic acid": ("401", "mg", 22, 1.0),
    "Vitamin D (D2 + D3)": ("328", "µg", 23, 1000.0),
    "Vitamin E (alpha-tocopherol)": ("323", "mg", 24, 1.0),
    "Vitamin K (phylloquinone)": ("430", "µg", 25, 1000.0),
}

CHICKEN_NUTRIENT_ORDER = [
    "Calcium, Ca", "Copper, Cu", "Iron, Fe", "Magnesium, Mg",
    "Manganese, Mn", "Phosphorus, P", "Potassium, K", "Selenium, Se",
    "Sodium, Na", "Zinc, Zn", "Thiamin", "Riboflavin", "Niacin",
    "Vitamin B-6", "Vitamin B-12", "Vitamin A, RAE",
    "Vitamin C, total ascorbic acid", "Vitamin D (D2 + D3)",
    "Vitamin E (alpha-tocopherol)", "Vitamin K (phylloquinone)",
]
CHICKEN_MACRO_ORDER = [
    "Protein", "Total lipid (fat)", "Carbohydrate, by difference",
    "Fiber, total dietary",
]
FDC_ZIP_URL = (
    "https://fdc.nal.usda.gov/fdc-datasets/"
    "FoodData_Central_sr_legacy_food_csv_2018-04.zip"
)


def csv_rows(source: Path, filename: str):
    """Open one named CSV member from an SR Legacy zip or extracted directory."""
    if source.is_dir():
        matches = list(source.rglob(filename))
        if not matches:
            raise FileNotFoundError(f"{filename} not found beneath {source}")
        stream = matches[0].open("r", encoding="utf-8-sig", newline="")
        return csv.DictReader(stream), stream
    archive = zipfile.ZipFile(source)
    # USDA ZIPs may put CSV tables at the archive root or in a release folder.
    members = [name for name in archive.namelist()
               if Path(name).name.casefold() == filename.casefold()]
    if not members:
        archive.close()
        raise FileNotFoundError(f"{filename} not found in {source}")
    stream = io.TextIOWrapper(archive.open(members[0]), encoding="utf-8-sig", newline="")
    return csv.DictReader(stream), (stream, archive)


def collect_rows(source: Path, filename: str) -> list[dict[str, str]]:
    reader, owner = csv_rows(source, filename)
    try:
        return list(reader)
    finally:
        if isinstance(owner, tuple):
            owner[0].close()
            owner[1].close()
        else:
            owner.close()


def parse_cpp_array(text: str, marker: str) -> list[float]:
    match = re.search(re.escape(marker) + r"\s*\{\{(.*?)\}\}", text, re.S)
    if not match:
        raise ValueError(f"Could not find C++ array {marker}")
    return [float(token.strip()) for token in match.group(1).split(",") if token.strip()]


def parse_legacy_foods(header: Path) -> dict[str, list[float]]:
    text = header.read_text(encoding="utf-8")
    matches = re.finditer(
        r'Food\{"([^"]+)",\s*IngredientGroup::\w+,\s*\{([^}]*)\}', text
    )
    result = {}
    for match in matches:
        result[match.group(1)] = [float(token.strip()) for token in match.group(2).split(",")]
    if not result:
        raise ValueError(f"No Food rows parsed from {header}")
    return result


def add_comparison(output, ingredient, crosswalk, fdc_food, ndb_number, fdc_nutrients,
                   derivations, sources, portions, portion_grams, legacy_values):
    fdc_id = int(crosswalk["fdc_id"])
    nutrient_by_number = fdc_nutrients.get(fdc_id, {})
    for label, (number, unit, source_index, unit_factor) in EXPECTED_NUTRIENTS.items():
        source_value = legacy_values[source_index]
        legacy_per_100g = source_value / portion_grams * 100.0 * unit_factor
        legacy_source_unit = "mg" if unit_factor == 1000.0 else unit
        row = nutrient_by_number.get(number)
        if row is None or row["amount"] == "":
            fdc_per_100g = ""
            delta = ""
            relative_delta = ""
            derivation = ""
            source = ""
            points = ""
            comparison_status = "not_reported"
            review_status = "legacy value retained; SR Legacy not reported"
        else:
            fdc_per_100g = float(row["amount"])
            delta = fdc_per_100g - legacy_per_100g
            relative_delta = "" if fdc_per_100g == 0 else delta / abs(fdc_per_100g) * 100.0
            derivation_row = derivations.get(row.get("derivation_id", ""), {})
            source_row = sources.get(derivation_row.get("source_id", ""), {})
            derivation = derivation_row.get("description", "")
            source = source_row.get("description", "")
            points = row.get("data_points", "")
            comparison_status = "compared"
            if crosswalk.get("identity_match") != "exact":
                review_status = "approximate identity; legacy value retained"
            elif abs(delta) <= 1e-9:
                review_status = "matches exact SR Legacy fallback; review source quality"
            else:
                review_status = "manual review: exact SR Legacy value differs"
        portion_summary = "; ".join(
            f"{p.get('amount', '')} {p.get('portion_description') or p.get('modifier', '')} "
            f"({p.get('gram_weight', '')} g)"
            for p in portions.get(int(fdc_id), []) if p.get("gram_weight", "")
        )
        output.append({
            "ingredient_key": ingredient,
            "dataset_release": DATASET_RELEASE,
            "fdc_id": fdc_id,
            "ndb_number": ndb_number,
            "fdc_description": crosswalk["fdc_description"],
            "fdc_publication_date": fdc_food.get("publication_date", ""),
            "identity_match": crosswalk["identity_match"],
            "selection_note": crosswalk["selection_note"],
            "fdc_portions": portion_summary,
            "legacy_table_portion_g": f"{portion_grams:.8g}",
            "legacy_source_value_at_portion": f"{source_value:.12g}",
            "legacy_source_unit": legacy_source_unit,
            "legacy_unit_conversion_factor": f"{unit_factor:.8g}",
            "legacy_conversion_formula": (
                f"{source_value:.12g} {legacy_source_unit} / {portion_grams:.8g} g"
                f" * 100 g * {unit_factor:.8g} {unit}/{legacy_source_unit}"
            ),
            "nutrient": label,
            "unit": unit,
            "legacy_per_100g": f"{legacy_per_100g:.12g}",
            "fdc_per_100g": "" if fdc_per_100g == "" else f"{fdc_per_100g:.12g}",
            "fdc_minus_legacy": "" if delta == "" else f"{delta:.12g}",
            "difference_pct_of_fdc": "" if relative_delta == "" else f"{relative_delta:.8g}",
            "fdc_derivation": derivation,
            "fdc_source": source,
            "fdc_value_class": (
            "not reported" if comparison_status == "not_reported"
                else "analytical or derived from analytical"
                if "analytical" in f"{derivation} {source}".casefold()
                else "calculated or imputed"
                if "calculat" in f"{derivation} {source}".casefold()
                else "source metadata not specified"
            ),
            "fdc_data_points": points,
            "nutrient_review_status": review_status,
            "comparison_status": comparison_status,
        })


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sr-legacy", type=Path, required=True,
                        help="USDA SR Legacy CSV zip archive or extracted directory")
    parser.add_argument("--output", type=Path,
                        default=repo / "data/reports/sr_legacy_audit.csv")
    args = parser.parse_args()
    source_path = args.sr_legacy.expanduser().resolve()
    if not source_path.exists():
        parser.error(f"SR Legacy source not found: {source_path}")

    crosswalk_path = repo / "data/fooddata_central_sr_legacy_crosswalk.csv"
    crosswalk_rows = list(csv.DictReader(crosswalk_path.open(encoding="utf-8", newline="")))
    crosswalk = {row["ingredient_key"]: row for row in crosswalk_rows}

    legacy = parse_legacy_foods(repo / "include/diet/food_data.hpp")
    model_text = (repo / "src/model.cpp").read_text(encoding="utf-8")
    chicken_nutrients = parse_cpp_array(model_text, "chicken_per_100g")
    chicken_macros = parse_cpp_array(model_text, "chicken_macros_per_100g")
    calorie_match = re.search(r"model\.fixed_calories\s*=\s*([0-9.]+)", model_text)
    if not calorie_match:
        raise ValueError("Could not find fixed chicken calories in src/model.cpp")
    chicken_calories = float(calorie_match.group(1))
    if len(chicken_nutrients) != 20 or len(chicken_macros) != 4:
        raise ValueError("Unexpected chicken nutrient/macro array length in src/model.cpp")

    needed_ids = {int(row["fdc_id"]) for row in crosswalk_rows}
    fdc_foods = {int(row["fdc_id"]): row for row in collect_rows(source_path, "food.csv")
                 if int(row["fdc_id"]) in needed_ids}
    ndb_numbers = {int(row["fdc_id"]): row["NDB_number"]
                   for row in collect_rows(source_path, "sr_legacy_food.csv")
                   if int(row["fdc_id"]) in needed_ids}
    nutrient_rows = collect_rows(source_path, "nutrient.csv")
    nutrients_by_id = {row["id"]: row for row in nutrient_rows}
    fdc_nutrients = {}
    wanted_numbers = {spec[0] for spec in EXPECTED_NUTRIENTS.values()}
    wanted_nutrient_ids = {row["id"] for row in nutrient_rows
                           if row["nutrient_nbr"] in wanted_numbers}
    for row in collect_rows(source_path, "food_nutrient.csv"):
        if int(row["fdc_id"]) in needed_ids and row["nutrient_id"] in wanted_nutrient_ids:
            number = nutrients_by_id[row["nutrient_id"]]["nutrient_nbr"]
            fdc_nutrients.setdefault(int(row["fdc_id"]), {})[number] = row
    derivations = {row["id"]: row for row in collect_rows(source_path, "food_nutrient_derivation.csv")}
    sources = {row["id"]: row for row in collect_rows(source_path, "food_nutrient_source.csv")}
    portions = {}
    for row in collect_rows(source_path, "food_portion.csv"):
        if int(row["fdc_id"]) in needed_ids:
            portions.setdefault(int(row["fdc_id"]), []).append(row)

    errors = []
    audit_rows = []
    for ingredient, row in crosswalk.items():
        fdc_id = int(row["fdc_id"])
        if fdc_id not in fdc_foods:
            errors.append(f"FDC ID {fdc_id} ({ingredient}) is absent from the selected SR Legacy dataset")
            continue
        if fdc_foods[fdc_id]["description"] != row["fdc_description"]:
            errors.append(
                f"FDC ID {fdc_id} description mismatch: crosswalk says "
                f"{row['fdc_description']!r}, dataset says {fdc_foods[fdc_id]['description']!r}"
            )
            continue
        if ingredient == "roasted chicken leg quarter":
            legacy_values = [0.0] * 26
            legacy_values[1] = chicken_calories
            for index, macro in enumerate(chicken_macros):
                legacy_values[index + 2] = macro
            for index, nutrient in enumerate(chicken_nutrients):
                legacy_values[index + 6] = nutrient
            portion_grams = 100.0
        else:
            if ingredient not in legacy:
                errors.append(f"Crosswalk ingredient {ingredient!r} is not in food_data.hpp")
                continue
            legacy_values = legacy[ingredient]
            portion_grams = legacy_values[0]
        add_comparison(audit_rows, ingredient, row, fdc_foods[fdc_id],
                       ndb_numbers.get(fdc_id, ""),
                       fdc_nutrients=fdc_nutrients,
                       derivations=derivations, sources=sources, portions=portions,
                       portion_grams=portion_grams, legacy_values=legacy_values)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(audit_rows[0])
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)
    print(f"Wrote {len(audit_rows)} nutrient comparisons to {args.output}")
    print(f"Dataset: {DATASET_RELEASE}")
    missing = sum(row["comparison_status"] == "not_reported" for row in audit_rows)
    print(f"FDC nutrient values not reported for these rows: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
