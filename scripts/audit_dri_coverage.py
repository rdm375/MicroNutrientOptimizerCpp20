#!/usr/bin/env python3
"""Audit DRI reference nutrients against FoodData Central definitions and records.

This is a coverage inventory, not a nutrient-value crosswalk. It counts
nonblank food_nutrient records and distinct foods by FDC data type, plus the
number of manually reviewed plant candidates that have any matching record.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


def table_rows(source: Path, filename: str):
    """Yield rows from an extracted FoodData Central tree or nested ZIP."""
    if source.is_dir():
        matches = list(source.rglob(filename))
        if not matches:
            raise FileNotFoundError(f"{filename} not found under {source}")
        path = min(matches, key=lambda p: len(p.parts))
        with path.open(encoding="utf-8-sig", newline="") as stream:
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


def normalized_name(value: str) -> str:
    """Normalize punctuation and spacing for exact-name alias matching."""
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def read_reference(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "key", "category", "display_name", "dri_unit", "project_status",
        "project_key", "fdc_exact_name_aliases", "mapping_note",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Reference CSV must include columns: {', '.join(sorted(required))}")
    return rows


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", type=Path, required=True,
                        help="Full FoodData Central CSV ZIP or extracted directory")
    parser.add_argument("--review", type=Path,
                        default=repo / "data/reports/plant_candidate_review.csv",
                        help="Candidate review CSV; used for candidate coverage only")
    parser.add_argument("--reference", type=Path,
                        default=repo / "data/dri_micronutrient_reference.csv")
    parser.add_argument("--output", type=Path,
                        default=repo / "data/reports/dri_fooddata_coverage.csv")
    args = parser.parse_args()
    source = args.full.expanduser().resolve()
    reference = read_reference(args.reference.expanduser().resolve())

    if not args.review.exists():
        raise FileNotFoundError(
            f"Candidate review file not found: {args.review}. Run make ingredient-candidates first."
        )
    with args.review.open(encoding="utf-8-sig", newline="") as stream:
        candidate_ids = {row.get("fdc_id", "").strip()
                         for row in csv.DictReader(stream)
                         if row.get("fdc_id", "").strip()}

    alias_to_keys: dict[str, set[str]] = defaultdict(set)
    row_by_key = {row["key"]: row for row in reference}
    for row in reference:
        for alias in row["fdc_exact_name_aliases"].split("|"):
            alias = normalized_name(alias)
            if alias:
                alias_to_keys[alias].add(row["key"])

    definitions: dict[str, list[dict[str, str]]] = defaultdict(list)
    for nutrient in table_rows(source, "nutrient.csv"):
        for key in alias_to_keys.get(normalized_name(nutrient.get("name", "")), ()):
            definitions[key].append(nutrient)

    nutrient_id_to_keys: dict[str, set[str]] = defaultdict(set)
    for key, matches in definitions.items():
        for nutrient in matches:
            nutrient_id_to_keys[nutrient["id"]].add(key)

    food_types = {
        row.get("fdc_id", ""): row.get("data_type", "unknown") or "unknown"
        for row in table_rows(source, "food.csv")
    }
    record_counts: dict[str, Counter[str]] = defaultdict(Counter)
    food_sets: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    candidate_sets: dict[str, set[str]] = defaultdict(set)
    for nutrient in table_rows(source, "food_nutrient.csv"):
        nutrient_id = nutrient.get("nutrient_id", "")
        fdc_id = nutrient.get("fdc_id", "")
        amount = nutrient.get("amount", "").strip()
        if not amount or nutrient_id not in nutrient_id_to_keys:
            continue
        data_type = food_types.get(fdc_id, "unknown")
        for key in nutrient_id_to_keys[nutrient_id]:
            record_counts[key][data_type] += 1
            food_sets[key][data_type].add(fdc_id)
            if fdc_id in candidate_ids:
                candidate_sets[key].add(fdc_id)

    all_types = sorted({kind for counts in record_counts.values() for kind in counts})
    output_rows = []
    for row in reference:
        key = row["key"]
        matched = sorted(definitions.get(key, []), key=lambda item: (item.get("name", ""), item.get("id", "")))
        output = {
            "key": key,
            "category": row["category"],
            "display_name": row["display_name"],
            "dri_unit": row["dri_unit"],
            "project_status": row["project_status"],
            "project_key": row["project_key"],
            "matched_fdc_definitions": " | ".join(
                f'{item.get("name", "")} [id={item.get("id", "")}; '
                f'unit={item.get("unit_name", "")}; '
                f'nutrient_nbr={item.get("nutrient_nbr", "")}]'
                for item in matched
            ),
            "candidate_count": len(candidate_ids),
            "candidate_foods_with_value": len(candidate_sets[key]),
            "candidate_coverage_percent": (
                f"{100.0 * len(candidate_sets[key]) / len(candidate_ids):.2f}"
                if candidate_ids else ""
            ),
            "mapping_note": row["mapping_note"],
        }
        for data_type in all_types:
            safe_type = re.sub(r"[^a-z0-9]+", "_", data_type.casefold()).strip("_") or "unknown"
            output[f"records_{safe_type}"] = record_counts[key][data_type]
            output[f"foods_{safe_type}"] = len(food_sets[key][data_type])
        output_rows.append(output)

    fixed_fields = [
        "key", "category", "display_name", "dri_unit", "project_status", "project_key",
        "matched_fdc_definitions", "candidate_count", "candidate_foods_with_value",
        "candidate_coverage_percent",
    ]
    dynamic_fields = []
    for data_type in all_types:
        safe_type = re.sub(r"[^a-z0-9]+", "_", data_type.casefold()).strip("_") or "unknown"
        dynamic_fields.extend((f"records_{safe_type}", f"foods_{safe_type}"))
    fields = fixed_fields + dynamic_fields + ["mapping_note"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Wrote DRI/FoodData Central coverage report: {args.output.resolve()}")
    print(f"Reference nutrients: {len(reference)}; candidate foods checked: {len(candidate_ids)}")
    missing = [row["display_name"] for row in reference if not definitions.get(row["key"])]
    if missing:
        print("No exact FDC nutrient definition matched: " + ", ".join(missing))
    print("Counts are nonblank food_nutrient records and distinct foods, not nutrient amounts or completeness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
