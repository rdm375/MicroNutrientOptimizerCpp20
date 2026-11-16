#!/usr/bin/env python3
"""Apply reviewed exact-identity SR Legacy values to the embedded food table.

Only exact crosswalk identities with no Foundation mapping are eligible. FDC
blank values and approximate identities remain unchanged. A row-by-row
migration ledger is written on every run; source files change only with --apply.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


# FDC audit report order and the corresponding source_values[] indices.
SOURCE_INDEX = {
    "Energy": 1,
    "Protein": 2,
    "Total lipid (fat)": 3,
    "Carbohydrate, by difference": 4,
    "Fiber, total dietary": 5,
    "Calcium, Ca": 6,
    "Copper, Cu": 7,
    "Iron, Fe": 8,
    "Magnesium, Mg": 9,
    "Manganese, Mn": 10,
    "Phosphorus, P": 11,
    "Potassium, K": 12,
    "Selenium, Se": 13,
    "Sodium, Na": 14,
    "Zinc, Zn": 15,
    "Thiamin": 16,
    "Riboflavin": 17,
    "Niacin": 18,
    "Vitamin B-6": 19,
    "Vitamin B-12": 20,
    "Vitamin A, RAE": 21,
    "Vitamin C, total ascorbic acid": 22,
    "Vitamin D (D2 + D3)": 23,
    "Vitamin E (alpha-tocopherol)": 24,
    "Vitamin K (phylloquinone)": 25,
}
CHICKEN_MACRO_INDEX = {
    "Protein": 0,
    "Total lipid (fat)": 1,
    "Carbohydrate, by difference": 2,
    "Fiber, total dietary": 3,
}


def number(value: str) -> float:
    return float(value.strip())


def formatted(value: float) -> str:
    return f"{value:.12g}"


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def exact_food_table_rows(text: str) -> tuple[dict[str, list[float]], dict[str, tuple[str, str]]]:
    rows: dict[str, list[float]] = {}
    locations: dict[str, tuple[str, str]] = {}
    pattern = re.compile(
        r'(?P<prefix>Food\{"(?P<name>[^"]+)",\s*IngredientGroup::(?P<group>\w+),\s*\{)'
        r'(?P<values>[^}]+)(?P<suffix>\}.+)$'
    )
    for line in text.splitlines(keepends=True):
        match = pattern.search(line.rstrip("\n"))
        if not match:
            continue
        name = match.group("name")
        values = [number(token) for token in match.group("values").split(",")]
        if len(values) != 26:
            raise ValueError(f"{name}: expected 26 source values, found {len(values)}")
        rows[name] = values
        locations[name] = (match.group("prefix"), match.group("suffix"))
    if not rows:
        raise ValueError("No grouped food rows found in include/diet/food_data.hpp")
    return rows, locations


def replace_food_table(text: str, values_by_food: dict[str, list[float]]) -> str:
    pattern = re.compile(
        r'(?P<prefix>Food\{"(?P<name>[^"]+)",\s*IngredientGroup::\w+,\s*\{)'
        r'(?P<values>[^}]+)(?P<suffix>\}.+)$'
    )
    output = []
    for line in text.splitlines(keepends=True):
        match = pattern.search(line.rstrip("\n"))
        if not match or match.group("name") not in values_by_food:
            output.append(line)
            continue
        values = ", ".join(formatted(value) for value in values_by_food[match.group("name")])
        replacement = match.group("prefix") + values + match.group("suffix")
        if line.endswith("\n"):
            replacement += "\n"
        output.append(replacement)
    return "".join(output)


def replace_cpp_array(text: str, name: str, values: list[float]) -> str:
    pattern = re.compile(rf"({re.escape(name)}\s*\{{\{{)(.*?)(\}}\}};)", re.S)
    chunks = [values[index:index + 10] for index in range(0, len(values), 10)]
    value_text = "\n        " + ",\n        ".join(
        ", ".join(formatted(value) for value in chunk) for chunk in chunks
    ) + "\n    "
    updated, count = pattern.subn(
        lambda match: match.group(1) + value_text + match.group(3), text, count=1
    )
    if count != 1:
        raise ValueError(f"Could not locate exactly one C++ array named {name}")
    return updated


def parse_cpp_array(text: str, name: str) -> list[float]:
    match = re.search(rf"{re.escape(name)}\s*\{{\{{(.*?)\}}\}};", text, re.S)
    if not match:
        raise ValueError(f"Could not read C++ array {name}")
    return [number(token) for token in match.group(1).split(",") if token.strip()]


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path,
                        default=repo / "data/reports/legacy_table_before_sr_legacy_update.csv",
                        help="Pre-update SR Legacy audit snapshot")
    parser.add_argument("--output", type=Path,
                        default=repo / "data/reports/sr_legacy_value_migration.csv")
    parser.add_argument("--apply", action="store_true",
                        help="write eligible values into food_data.hpp and model.cpp")
    args = parser.parse_args()

    audit_rows = load_csv(args.audit.expanduser().resolve())
    crosswalk_rows = load_csv(repo / "data/fooddata_central_sr_legacy_crosswalk.csv")
    crosswalk = {row["ingredient_key"]: row for row in crosswalk_rows}
    header_path = repo / "include/diet/food_data.hpp"
    model_path = repo / "src/model.cpp"
    header_text = header_path.read_text(encoding="utf-8")
    model_text = model_path.read_text(encoding="utf-8")
    food_values, _ = exact_food_table_rows(header_text)
    updates_by_food: dict[str, dict[int, float]] = {}
    chicken_nutrients: list[float | None] = [None] * 20
    chicken_macros: list[float | None] = [None] * 4
    chicken_calories: float | None = None
    current_chicken_nutrients = parse_cpp_array(model_text, "chicken_per_100g")
    current_chicken_macros = parse_cpp_array(model_text, "chicken_macros_per_100g")
    current_chicken_calories_match = re.search(
        r"model\.fixed_calories\s*=\s*([-+0-9.eE]+)", model_text
    )
    if not current_chicken_calories_match:
        raise ValueError("Could not read the fixed chicken calorie value")
    migration_rows = []

    for row in audit_rows:
        key = row["ingredient_key"]
        link = crosswalk.get(key)
        if link is None:
            raise ValueError(f"Audit row has no crosswalk entry: {key}")
        has_foundation_map = bool(link.get("foundation_fdc_ids", "").strip())
        is_exact = row.get("identity_match", "") == "exact"
        fdc_value = row.get("fdc_per_100g", "").strip()
        eligible = is_exact and not has_foundation_map and bool(fdc_value)
        action = (
            "apply exact SR Legacy fallback" if eligible
            else "retain: Foundation mapping present" if has_foundation_map
            else "retain: approximate food identity" if not is_exact
            else "retain: SR Legacy does not report value"
        )
        report_unit = row.get("unit", "")
        conversion = number(row.get("legacy_unit_conversion_factor", "1") or "1")
        portion_g = number(row.get("legacy_table_portion_g", "100") or "100")
        source_index = SOURCE_INDEX.get(row.get("nutrient", ""))
        proposed_source_value = ""
        current_source_value = row.get("legacy_source_value_at_portion", "")

        if eligible:
            if key == "roasted chicken leg quarter":
                per_100g_internal = number(fdc_value) / conversion
                if row["nutrient"] == "Energy":
                    chicken_calories = per_100g_internal
                elif row["nutrient"] in CHICKEN_MACRO_INDEX:
                    chicken_macros[CHICKEN_MACRO_INDEX[row["nutrient"]]] = per_100g_internal
                elif source_index is not None:
                    chicken_nutrients[source_index - 6] = per_100g_internal
                proposed_source_value = formatted(per_100g_internal)
            else:
                if key not in food_values:
                    raise ValueError(f"Exact food row not found in C++ table: {key}")
                if source_index is None:
                    raise ValueError(f"No source-array index for nutrient {row['nutrient']!r}")
                portion_value = number(fdc_value) / conversion * portion_g / 100.0
                updates_by_food.setdefault(key, {})[source_index] = portion_value
                proposed_source_value = formatted(portion_value)

        migration_rows.append({
            "ingredient_key": key,
            "nutrient": row["nutrient"],
            "unit": report_unit,
            "identity_match": row.get("identity_match", ""),
            "fdc_id": row.get("fdc_id", ""),
            "fdc_description": row.get("fdc_description", ""),
            "fdc_value_per_100g": fdc_value,
            "fdc_value_class": row.get("fdc_value_class", ""),
            "fdc_data_points": row.get("fdc_data_points", ""),
            "legacy_portion_g": formatted(portion_g),
            "legacy_value_at_portion_before": current_source_value,
            "legacy_value_at_portion_after": proposed_source_value or current_source_value,
            "legacy_source_unit": row.get("legacy_source_unit", ""),
            "unit_conversion_factor": formatted(conversion),
            "migration_action": action,
        })

    if args.apply:
        if not args.audit.expanduser().resolve().is_file():
            raise FileNotFoundError(f"SR Legacy audit not found: {args.audit}")
        updated_foods = {}
        for key, changes in updates_by_food.items():
            updated_foods[key] = food_values[key].copy()
            for index, value in changes.items():
                updated_foods[key][index] = value
        header_text = replace_food_table(header_text, updated_foods)
        if len(current_chicken_nutrients) != len(chicken_nutrients):
            raise ValueError("Unexpected chicken nutrient array length")
        if len(current_chicken_macros) != len(chicken_macros):
            raise ValueError("Unexpected chicken macro array length")
        model_text = replace_cpp_array(model_text, "chicken_per_100g", [
            value if value is not None else old
            for value, old in zip(chicken_nutrients, current_chicken_nutrients)
        ])
        model_text = replace_cpp_array(model_text, "chicken_macros_per_100g", [
            value if value is not None else old
            for value, old in zip(chicken_macros, current_chicken_macros)
        ])
        if chicken_calories is not None:
            model_text, count = re.subn(
                r"(model\.fixed_calories\s*=\s*)[-+0-9.eE]+",
                lambda match: match.group(1) + formatted(chicken_calories), model_text, count=1,
            )
            if count != 1:
                raise ValueError("Could not update the fixed chicken calorie value")
        header_path.write_text(header_text, encoding="utf-8")
        model_path.write_text(model_text, encoding="utf-8")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(migration_rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(migration_rows)

    applied_rows = sum(row["migration_action"] == "apply exact SR Legacy fallback"
                       for row in migration_rows)
    print(f"Wrote {len(migration_rows)} migration decisions to {args.output}")
    print(f"Exact, reported SR Legacy values eligible: {applied_rows}")
    print(f"Applied to C++ source: {'yes' if args.apply else 'no (dry run)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
