"""Audit every model_type used across the catalog against what's importable.

Run after bumping any akgentic-* package to find every catalog entry whose
model_type no longer resolves, in one pass, instead of discovering them one
at a time via repeated `ak-catalog validate` cycles.

Usage:
    python3 scripts/audit_model_types.py
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import yaml

CATALOG_DIR = Path(__file__).parent.parent / "data" / "catalog"


def import_class(class_path: str) -> None:
    module_path, class_name = class_path.rsplit(".", 1)
    module = import_module(module_path)
    getattr(module, class_name)


def main() -> None:
    model_types: dict[str, list[Path]] = {}
    for yaml_file in sorted(CATALOG_DIR.glob("*/*/*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        model_type = data.get("model_type")
        if isinstance(model_type, str):
            model_types.setdefault(model_type, []).append(yaml_file)

    broken: dict[str, tuple[Exception, list[Path]]] = {}
    for model_type, files in sorted(model_types.items()):
        try:
            import_class(model_type)
        except Exception as exc:  # noqa: BLE001
            broken[model_type] = (exc, files)

    print(f"Checked {len(model_types)} distinct model_type values.\n")
    if not broken:
        print("All model_type values resolve cleanly.")
        return

    print(f"{len(broken)} BROKEN model_type value(s):\n")
    for model_type, (exc, files) in broken.items():
        print(f"  {model_type}")
        print(f"    -> {type(exc).__name__}: {exc}")
        for f in files:
            print(f"       used in {f.relative_to(CATALOG_DIR)}")
        print()


if __name__ == "__main__":
    main()
