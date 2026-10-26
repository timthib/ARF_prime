"""Scan run-side files for the vault canary and for vault score keys."""

from __future__ import annotations

from pathlib import Path

from smoke.materialise import CANARY, SHIFT

NEEDLES = (CANARY, f"{SHIFT:.9f}", '"s0"', '"j0"', '"j_0"')


def find_leaks(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for root in paths:
        if not root.exists():
            continue
        files = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in files:
            blob = path.read_bytes()
            for needle in NEEDLES:
                if needle.encode("utf-8") in blob:
                    hits.append(str(path))
                    break
    return hits
