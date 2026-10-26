from pathlib import Path

BANNED = ("d0vault", "d0_results", "8502")


def test_control_room_has_no_path_to_the_holdout_room():
    root = Path(__file__).resolve().parents[1] / "monitor"
    offenders = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {"node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.suffix not in {".py", ".js", ".jsx", ".css", ".html", ".sql", ".md"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in BANNED:
            if needle in text:
                offenders.append(f"{path.relative_to(root)} contains {needle}")
    assert offenders == []
