#!/usr/bin/env python3
"""List Foundation Foods records for manual ingredient identity review."""

from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path


SEARCH_TERMS = {
    "romaine lettuce": ("romaine", "cos lettuce"),
    "collard greens": ("collard",),
    "spinach": ("spinach",),
    "roma tomatoes": ("tomato",),
    "cucumbers": ("cucumber",),
    "red onion": ("onion",),
    "pine nuts": ("pine nut",),
    "pumpkin seeds": ("pumpkin seed", "squash seed"),
    "chia seeds": ("chia",),
    "sunflower seeds": ("sunflower seed",),
    "shiitake mushrms": ("shiitake",),
    "wht btn mushrms": ("white mushroom", "white button"),
    "brocoli": ("broccoli",),
    "bell pepper": ("bell pepper", "sweet pepper"),
    "egg": ("egg, whole", "egg, yolk", "egg, white"),
    "chedar cheese": ("cheddar",),
    "UV-exposed portabella mushrooms": ("portabella", "portobello"),
    "roasted chicken leg quarter": ("chicken",),
}


def food_rows(source: Path):
    if source.is_dir():
        matches = list(source.rglob("food.csv"))
        if not matches:
            raise FileNotFoundError(f"food.csv not found under {source}")
        with matches[0].open(encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)
    else:
        with zipfile.ZipFile(source) as archive:
            # Match the FDC table by basename; the full archive nests tables in
            # a release-named directory.
            members = [name for name in archive.namelist()
                       if Path(name.replace("\\", "/")).name.casefold() == "food.csv"]
            if not members:
                raise FileNotFoundError(f"food.csv not found in {source}")
            with io.TextIOWrapper(archive.open(members[0]), encoding="utf-8-sig", newline="") as stream:
                yield from csv.DictReader(stream)


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foundation", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=repo / "data/reports/foundation_food_candidates.csv")
    args = parser.parse_args()
    matches = []
    for food in food_rows(args.foundation.expanduser().resolve()):
        if "foundation" not in food.get("data_type", "").casefold():
            continue
        description = food.get("description", "")
        lowered = description.casefold()
        for ingredient, terms in SEARCH_TERMS.items():
            for term in terms:
                if term.casefold() in lowered:
                    matches.append({
                        "ingredient_key": ingredient,
                        "search_term": term,
                        "fdc_id": food.get("fdc_id", ""),
                        "description": description,
                        "publication_date": food.get("publication_date", ""),
                    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(matches[0]) if matches else
                                ["ingredient_key", "search_term", "fdc_id", "description", "publication_date"])
        writer.writeheader()
        writer.writerows(matches)
    print(f"Wrote {len(matches)} candidate matches to {args.output}")
    print("Review food form and identity before copying FDC IDs into the crosswalk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
