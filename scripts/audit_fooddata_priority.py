#!/usr/bin/env python3
"""Compare the hand-entered table with Foundation Foods, falling back by nutrient to SR Legacy."""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import zipfile
from pathlib import Path


SR_EXPECTED = {
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
FOUNDATION_NUMBERS = {name: ({"208", "1008"} if name == "Energy" else {spec[0]})
                      for name, spec in SR_EXPECTED.items()}


def iter_rows(source: Path, filename: str):
    if source.is_dir():
        matches = list(source.rglob(filename))
        if not matches:
            raise FileNotFoundError(f"{filename} not found beneath {source}")
        with matches[0].open(encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)
        return
    with zipfile.ZipFile(source) as archive:
        # USDA archives vary between root-level table files and a release-named
        # enclosing directory. Match the table basename in either layout.
        members = [name for name in archive.namelist()
                   if Path(name.replace("\\", "/")).name.casefold() == filename.casefold()]
        if not members:
            raise FileNotFoundError(f"{filename} not found in {source}")
        # Full FDC archives carry one copy of each table. If an extracted tree
        # or future archive has duplicates, prefer the shallowest member.
        member = min(members, key=lambda name: name.count("/") + name.count("\\"))
        with io.TextIOWrapper(archive.open(member), encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)


def cpp_array(text: str, marker: str) -> list[float]:
    match = re.search(re.escape(marker) + r"\s*\{\{(.*?)\}\}", text, re.S)
    if not match:
        raise ValueError(f"Could not find C++ array {marker}")
    return [float(x.strip()) for x in match.group(1).split(",") if x.strip()]


def legacy_foods(header: Path) -> dict[str, list[float]]:
    text = header.read_text(encoding="utf-8")
    foods = {m.group(1): [float(x.strip()) for x in m.group(2).split(",")]
             for m in re.finditer(
                 r'Food\{"([^\"]+)",\s*IngredientGroup::\w+,\s*\{([^}]*)\}', text
             )}
    if not foods:
        raise ValueError(f"No food rows parsed from {header}")
    return foods


def read_dataset(path: Path, wanted_food_ids: set[int], foundation: bool):
    foods = {}
    for row in iter_rows(path, "food.csv"):
        food_id = int(row["fdc_id"])
        if food_id not in wanted_food_ids:
            continue
        if foundation and "foundation" not in row.get("data_type", "").casefold():
            continue
        foods[food_id] = row
    nutrient_table = list(iter_rows(path, "nutrient.csv"))
    nutrient_by_id = {r["id"]: r for r in nutrient_table}
    wanted_numbers = set().union(*(FOUNDATION_NUMBERS.values() if foundation else
                                   ({spec[0]} for spec in SR_EXPECTED.values())))
    selected_nutrients = {r["id"]: r for r in nutrient_table
                          if r.get("nutrient_nbr") in wanted_numbers or
                          (foundation and r.get("id") in {"2047", "2048"})}
    values = {}
    energy_priority = {}
    # Stream the very large food_nutrient table from the ZIP and retain values
    # only for IDs selected in the crosswalk. Never extract or load it whole.
    if wanted_food_ids:
        for row in iter_rows(path, "food_nutrient.csv"):
            fdc_id = int(row["fdc_id"])
            nutrient = selected_nutrients.get(row.get("nutrient_id", ""))
            if fdc_id not in wanted_food_ids or not nutrient:
                continue
            nbr = nutrient["nutrient_nbr"]
            nutrient_id = nutrient["id"]
            for name, numbers in FOUNDATION_NUMBERS.items():
                if name == "Energy" and foundation and nutrient_id in {"2047", "2048"}:
                    # Prefer Atwater-specific energy, then general factors; both
                    # are Foundation Foods' published kcal values.
                    priority = 2 if nutrient_id == "2048" else 1
                    if priority >= energy_priority.get(fdc_id, -1):
                        row["_nutrient_name"] = nutrient["name"]
                        values.setdefault(fdc_id, {})[name] = row
                        energy_priority[fdc_id] = priority
                    break
                if nbr in numbers:
                    if name == "Energy" and foundation:
                        priority = 0 if nbr == "1008" else -1
                        if priority < energy_priority.get(fdc_id, -1):
                            break
                        energy_priority[fdc_id] = priority
                    row["_nutrient_name"] = nutrient["name"]
                    values.setdefault(fdc_id, {})[name] = row
                    break
    derivations = {r["id"]: r for r in iter_rows(path, "food_nutrient_derivation.csv")}
    sources = {r["id"]: r for r in iter_rows(path, "food_nutrient_source.csv")}
    ndb = {}
    try:
        ndb = {int(r["fdc_id"]): r.get("NDB_number", "")
               for r in iter_rows(path, "sr_legacy_food.csv") if int(r["fdc_id"]) in wanted_food_ids}
    except FileNotFoundError:
        pass
    return foods, values, derivations, sources, ndb


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foundation", type=Path, required=True)
    parser.add_argument("--sr-legacy", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=repo / "data/reports/fooddata_priority_audit.csv")
    args = parser.parse_args()

    crosswalk_path = repo / "data/fooddata_central_sr_legacy_crosswalk.csv"
    with crosswalk_path.open(encoding="utf-8", newline="") as f:
        crosswalk = list(csv.DictReader(f))
    legacy = legacy_foods(repo / "include/diet/food_data.hpp")
    model_text = (repo / "src/model.cpp").read_text(encoding="utf-8")
    chicken_nutrients = cpp_array(model_text, "chicken_per_100g")
    chicken_macros = cpp_array(model_text, "chicken_macros_per_100g")
    calorie = re.search(r"model\.fixed_calories\s*=\s*([0-9.]+)", model_text)
    if not calorie or len(chicken_nutrients) != 20 or len(chicken_macros) != 4:
        raise ValueError("Unexpected chicken nutrition arrays in src/model.cpp")
    chicken_values = [0.0] * 26
    chicken_values[1] = float(calorie.group(1))
    for i, value in enumerate(chicken_macros):
        chicken_values[i + 2] = value
    for i, value in enumerate(chicken_nutrients):
        chicken_values[i + 6] = value

    foundation_ids = {int(token) for row in crosswalk
                      for token in row.get("foundation_fdc_ids", "").split(";") if token.strip()}
    sr_ids = {int(row["fdc_id"]) for row in crosswalk}
    foundation_path = args.foundation.expanduser().resolve()
    sr_path = args.sr_legacy.expanduser().resolve()
    if not foundation_path.exists() or not sr_path.exists():
        parser.error("Both FoodData Central archives or extracted directories must exist")
    ff, fn, fd, fs, _ = read_dataset(foundation_path, foundation_ids, True)
    sf, sn, sd, ss, ndb = read_dataset(sr_path, sr_ids, False)
    output_rows = []
    errors = []
    for cross in crosswalk:
        key = cross["ingredient_key"]
        sr_id = int(cross["fdc_id"])
        if sr_id not in sf or sf[sr_id].get("description") != cross["fdc_description"]:
            errors.append(f"SR Legacy crosswalk mismatch for {key} (FDC {sr_id})")
            continue
        sample_ids = [int(token) for token in cross.get("foundation_fdc_ids", "").split(";") if token.strip()]
        expected_description = cross.get("foundation_description", "").strip()
        for fid in sample_ids:
            if fid not in ff:
                errors.append(f"Foundation FDC {fid} for {key} is absent from selected archive")
            elif expected_description and ff[fid].get("description") != expected_description:
                errors.append(f"Foundation description mismatch for {key}, FDC {fid}")
        if errors:
            continue
        if key == "roasted chicken leg quarter":
            values, portion_g = chicken_values, 100.0
        else:
            values, portion_g = legacy[key], legacy[key][0]
        for nutrient, (sr_nbr, unit, index, factor) in SR_EXPECTED.items():
            legacy_per_100g = values[index] / portion_g * 100.0 * factor
            f_samples = []
            for fid in sample_ids:
                row = fn.get(fid, {}).get(nutrient)
                if row and row.get("amount", "") != "":
                    f_samples.append((fid, float(row["amount"]), row))
            fallback_reason = ""
            if f_samples:
                selected_value = sum(x[1] for x in f_samples) / len(f_samples)
                selected_source = "foundation_foods_mean"
                source_ids = ";".join(str(x[0]) for x in f_samples)
                min_value, max_value = min(x[1] for x in f_samples), max(x[1] for x in f_samples)
                derivation_rows, source_rows = fd, fs
                derivation_ids = {x[2].get("derivation_id", "") for x in f_samples}
                data_points = ";".join(x[2].get("data_points", "") for x in f_samples)
            else:
                sr_row = sn.get(sr_id, {}).get(nutrient)
                if sr_row and sr_row.get("amount", "") != "":
                    selected_value = float(sr_row["amount"])
                    selected_source = "sr_legacy_fallback"
                    source_ids = str(sr_id)
                    min_value = max_value = selected_value
                    derivation_rows, source_rows = sd, ss
                    derivation_ids = {sr_row.get("derivation_id", "")}
                    data_points = sr_row.get("data_points", "")
                    fallback_reason = ("no Foundation record mapped" if not sample_ids else
                                       "Foundation record(s) do not report this nutrient")
                else:
                    selected_value = min_value = max_value = None
                    selected_source = "not_reported"
                    source_ids = ""
                    derivation_rows, source_rows, derivation_ids, data_points = {}, {}, set(), ""
                    fallback_reason = "neither dataset reports this nutrient"
            derivations = sorted({derivation_rows.get(i, {}).get("description", "")
                                  for i in derivation_ids if i})
            source_ids_text = sorted({derivation_rows.get(i, {}).get("source_id", "")
                                      for i in derivation_ids if i})
            source_descriptions = sorted({source_rows.get(i, {}).get("description", "")
                                          for i in source_ids_text if i})
            output_rows.append({
                "ingredient_key": key,
                "nutrient": nutrient,
                "unit": unit,
                "legacy_table_per_100g": f"{legacy_per_100g:.12g}",
                "selected_fdc_per_100g": "" if selected_value is None else f"{selected_value:.12g}",
                "selected_minus_legacy": "" if selected_value is None else f"{selected_value - legacy_per_100g:.12g}",
                "difference_pct_of_selected": "" if selected_value in (None, 0) else f"{(selected_value - legacy_per_100g) / abs(selected_value) * 100:.8g}",
                "selected_source": selected_source,
                "selected_fdc_ids": source_ids,
                "foundation_sample_count": len(f_samples),
                "foundation_min_per_100g": "" if not f_samples else f"{min_value:.12g}",
                "foundation_max_per_100g": "" if not f_samples else f"{max_value:.12g}",
                "foundation_release": "October 2026" if f_samples else "",
                "sr_legacy_fdc_id": sr_id,
                "sr_legacy_ndb_number": ndb.get(sr_id, ""),
                "sr_legacy_description": sf[sr_id].get("description", ""),
                "sr_legacy_release": "April 2018" if selected_source == "sr_legacy_fallback" else "",
                "identity_match": cross.get("foundation_identity_match", "") if f_samples else cross["identity_match"],
                "selection_note": cross.get("foundation_selection_note", "") if f_samples else cross.get("selection_note", ""),
                "fdc_derivation": "; ".join(x for x in derivations if x),
                "fdc_source": "; ".join(x for x in source_descriptions if x),
                "fdc_nutrient_names": "; ".join(sorted({
                    x[2].get("_nutrient_name", "") for x in f_samples
                })) if f_samples else (sr_row.get("_nutrient_name", "") if selected_source == "sr_legacy_fallback" else ""),
                "fdc_data_points": data_points,
                "fallback_reason": fallback_reason,
            })
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Wrote {len(output_rows)} comparisons to {args.output}")
    print(f"Foundation Foods values used: {sum(r['selected_source'] == 'foundation_foods_mean' for r in output_rows)}")
    print(f"SR Legacy fallback values used: {sum(r['selected_source'] == 'sr_legacy_fallback' for r in output_rows)}")
    print(f"Nutrients unreported by both sources: {sum(r['selected_source'] == 'not_reported' for r in output_rows)}")
    print(f"Unmapped Foundation crosswalk ingredients: {sum(not r.get('foundation_fdc_ids', '').strip() for r in crosswalk)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
