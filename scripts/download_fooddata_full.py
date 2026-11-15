#!/usr/bin/env python3
"""Download the USDA FoodData Central full CSV release (October 2026)."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_csv_2026-10-29.zip"
REQUIRED_TABLES = {"food.csv", "food_nutrient.csv", "nutrient.csv", "foundation_food.csv"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_archive(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise RuntimeError(f"Not a ZIP archive: {path}")
    with zipfile.ZipFile(path) as archive:
        names = {Path(name.replace("\\", "/")).name.casefold()
                 for name in archive.namelist()}
        missing = REQUIRED_TABLES - names
        if missing:
            raise RuntimeError(f"Full FoodData Central archive is missing tables: {sorted(missing)}")


def main() -> int:
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "data/source/FoodData_Central_csv_2026-10-29.zip"
    )
    checksum_path = destination.with_suffix(destination.suffix + ".sha256")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        validate_archive(destination)
        actual = sha256(destination)
        if checksum_path.exists():
            expected = checksum_path.read_text(encoding="ascii").split()[0]
            if actual != expected:
                raise RuntimeError(f"SHA-256 mismatch for existing archive: {destination}")
            print(f"Verified full FoodData Central archive: {destination} ({actual})")
            return 0
        checksum_path.write_text(f"{actual}  {destination.name}\n", encoding="ascii")
        print(f"Recorded SHA-256 for existing archive: {actual}")
        return 0

    fd, temp_name = tempfile.mkstemp(prefix="fooddata-full-", suffix=".zip",
                                     dir=destination.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        print(f"Downloading USDA FoodData Central October 2026 full CSV archive to {destination}")
        urllib.request.urlretrieve(URL, temp_path)
        validate_archive(temp_path)
        actual = sha256(temp_path)
        temp_path.replace(destination)
        checksum_path.write_text(f"{actual}  {destination.name}\n", encoding="ascii")
    finally:
        temp_path.unlink(missing_ok=True)
    print(f"Downloaded archive; SHA-256 {actual} recorded in {checksum_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
