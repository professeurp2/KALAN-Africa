# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lamine SACKO
"""Question → passages du programme → réponse ancrée, citée, découpée en segments.

Chaque segment porte une phrase à dire et, optionnellement, l'élément du schéma
à pointer pendant qu'elle est dite : c'est le contrat qui permet R7 (voix et
pointage synchronisés). Les citations viennent de l'index, jamais du LLM.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import requests

from . import config
from .index import Embedder, Hit, Index
from .schemas import Schema, schema_for

SYSTEM = """Tu es Kalan, un assistant qui aide des élèves maliens à comprendre leurs leçons.
Règles absolues :
- Réponds UNIQUEMENT à partir des EXTRAITS DU PROGRAMME fournis. N'ajoute aucune connaissance extérieure.
- Si les extraits ne permettent pas de répondre, mets "hors_programme": true et laisse "segments" vide.
- Parle simplement, en phrases courtes, comme un grand frère patient. 2 à 5 phrases au total.
- Chaque phrase est un segment. Si un SCHÉMA est fourni et qu'une phrase parle d'un de ses éléments,
  mets l'identifiant de cet élément dans "pointe" ; sinon mets null.
Réponds en JSON strict :
{"hors_programme": false, "segments": [{"texte": "...", "pointe": "id_ou_null"}], "sources": [numéros des extraits utilisés]}"""


@dataclass
class Segment:
    texte: str
    pointe: str | None = None


@dataclass
class Reponse:
    segments: list[Segment]
    citations: list[str] = field(default_factory=list)
    schema: Schema | None = None
    hors_programme: bool = False

    @property
    def texte(self) -> str:
        return " ".join(s.texte for s in self.segments)


def refus() -> Reponse:
    return Reponse([Segment(config.REFUS)], hors_programme=True)


def build_prompt(question: str, hits: list[Hit], schema: Schema | None) -> str:
    extraits = "\n\n".join(f"[{i + 1}] ({h.chunk.citation()})\n{h.chunk.text}" for i, h in enumerate(hits))
    parts = [f"EXTRAITS DU PROGRAMME :\n{extraits}"]
    if schema:
        elems = "\n".join(f"- {eid} : {desc}" for eid, desc in schema.elements.items())
        parts.append(f"SCHÉMA « {schema.titre} », éléments pointables :\n{elems}")
    parts.append(f"QUESTION DE L'ÉLÈVE : {question}")
    return "\n\n".join(parts)


def parse_llm(raw: str, hits: list[Hit], schema: Schema | None) -> Reponse:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return refus()
    segments = [Segment(str(s.get("texte", "")).strip(), s.get("pointe"))
                for s in data.get("segments") or [] if isinstance(s, dict) and s.get("texte")]
    if data.get("hors_programme") or not segments:
        return refus()
    valid = set(schema.elements) if schema else set()
    for s in segments:
        if s.pointe not in valid:
            s.pointe = None
    used = [int(n) for n in data.get("sources") or [] if str(n).isdigit() and 1 <= int(n) <= len(hits)]
    cited = [hits[n - 1] for n in used] or hits[:1]
    citations = list(dict.fromkeys(h.chunk.citation() for h in cited))
    return Reponse(segments, citations, schema if any(s.pointe for s in segments) else None)


def ask_llm(prompt: str, system: str = SYSTEM) -> str:
    r = requests.post(f"{config.OLLAMA_URL}/api/chat", timeout=120, json={
        "model": config.LLM_MODEL,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.1},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    })
    r.raise_for_status()
    return r.json()["message"]["content"]


class Assistant:
    def __init__(self, index: Index, embed: Embedder, llm=ask_llm):
        self.index, self.embed, self.llm = index, embed, llm

    def repondre(self, question: str) -> Reponse:
        hits = self.index.search(self.embed([question])[0])
        if not hits or hits[0].score < config.MIN_SIMILARITY:
            return refus()
        hits = [h for h in hits if h.score >= config.MIN_SIMILARITY]
        schema = schema_for(hits[0].chunk.chapitre)
        return parse_llm(self.llm(build_prompt(question, hits, schema)), hits, schema)
