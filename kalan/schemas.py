"""Schémas pointables (R7).

Un schéma = un SVG dont certains éléments portent un id, plus un manifeste JSON
qui décrit ces éléments au LLM et le relie à un chapitre :

    data/schemas/circuit_simple.json
    {"titre": "...", "svg": "circuit_simple.svg", "chapitre": "<titre exact du chapitre>",
     "elements": {"pile": "la pile, le générateur", "lampe": "la lampe, le récepteur"}}
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import config

SCHEMAS_DIR = config.ROOT / "data" / "schemas"


@dataclass
class Schema:
    titre: str
    svg: Path
    chapitre: str
    elements: dict[str, str]


def load_all(directory: Path = SCHEMAS_DIR) -> list[Schema]:
    out = []
    for f in sorted(directory.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out.append(Schema(d["titre"], f.parent / d["svg"], d["chapitre"], d["elements"]))
    return out


def schema_for(chapitre: str) -> Schema | None:
    for s in load_all():
        if chapitre == s.chapitre:
            return s
    return None
