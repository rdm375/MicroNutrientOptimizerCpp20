#!/usr/bin/env python3
"""Download and verify USDA FoodData Central SR Legacy CSV release (April 2018)."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


URL = (
    "https://fdc.nal.usda.gov/fdc-datasets/"
    "FoodData_Central_sr_legacy_food_csv_2018-04.zip"
)
SHA256 = "b80817294b8850530aaedf2e515c02593b1824f763a0ff356e5c2081643e6fd0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "data/source/FoodData_Central_sr_legacy_food_csv_2018-04.zip"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256(destination) == SHA256:
        print(f"Verified existing USDA archive: {destination}")
        return 0

    fd, temp_name = tempfile.mkstemp(prefix="fooddata-", suffix=".zip",
                                     dir=destination.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        print(f"Downloading USDA SR Legacy CSV archive to {destination}")
        urllib.request.urlretrieve(URL, temp_path)
        actual = sha256(temp_path)
        if actual != SHA256:
            raise RuntimeError(f"SHA-256 mismatch: expected {SHA256}, got {actual}")
        with zipfile.ZipFile(temp_path) as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise RuntimeError(f"Corrupt ZIP member: {bad_member}")
        temp_path.replace(destination)
    finally:
        temp_path.unlink(missing_ok=True)
    print(f"Downloaded and verified SHA-256 {SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
