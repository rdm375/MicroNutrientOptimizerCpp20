#!/usr/bin/env python3
"""Regression-check one optimizer CLI profile and its independent OSQP audit."""

from __future__ import annotations

import re
import subprocess
import sys


def value(pattern: str, output: str, label: str) -> float:
    match = re.search(pattern, output, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"missing {label} in optimizer output")
    return float(match.group(1))


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in {"--sparse", "--diverse"}:
        print("usage: verify_optimizer_output.py EXECUTABLE --sparse|--diverse", file=sys.stderr)
        return 2
    result = subprocess.run([sys.argv[1], sys.argv[2]], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    output = result.stdout
    if result.returncode != 0:
        raise AssertionError(f"optimizer returned {result.returncode}:\n{output}")
    for expected in (
        r"^Final feasibility .*: PASS$",
        r"^Ingredient bounds: PASS",
        r"^OSQP status: solved \(1\)$",
        r"^Solution classification: feasible(?: and converged|; optimality not confirmed)$",
    ):
        if not re.search(expected, output, flags=re.MULTILINE):
            raise AssertionError(f"output failed required regression check {expected!r}:\n{output}")

    tolerances = (
        (r"^OSQP primal residual: ([+\-0-9.eE]+)$", 1e-7, "OSQP primal residual"),
        (r"^OSQP dual residual: ([+\-0-9.eE]+)$", 1e-7, "OSQP dual residual"),
        (r"^OSQP relative KKT error: ([+\-0-9.eE]+)$", 1e-7, "OSQP relative KKT error"),
        (r"^Maximum NLopt/OSQP ingredient difference: ([+\-0-9.eE]+) g$", 1e-5,
         "NLopt/OSQP ingredient difference"),
    )
    for pattern, limit, label in tolerances:
        actual = value(pattern, output, label)
        if actual > limit:
            raise AssertionError(f"{label}={actual:g} exceeds regression tolerance {limit:g}")

    print(f"PASS: {sys.argv[2]} feasible; OSQP KKT and NLopt agreement are within tolerance")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
