# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lamine SACKO
"""Découpage du programme en passages citables (chapitre, leçon, page).

Format Markdown attendu pour un chapitre :

    # Chapitre 3 — Le circuit électrique
    ## Leçon 1 — Les éléments d'un circuit
    <!-- page: 42 -->
    Texte...

Les PDF sont découpés page par page ; chapitre et leçon sont alors fournis à la main.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config

_PAGE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")


@dataclass
class Chunk:
    source: str
    chapitre: str
    lecon: str
    page: int | None
    text: str

    def citation(self) -> str:
        parts = [self.chapitre]
        if self.lecon:
            parts.append(self.lecon)
        if self.page is not None:
            parts.append(f"p. {self.page}")
        return " · ".join(parts)


def split_words(text: str, size: int = config.CHUNK_WORDS, overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, size - overlap)
    out = []
    for start in range(0, len(words), step):
        out.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return out


def chunk_markdown(path: Path) -> list[Chunk]:
    chapitre, lecon, page = path.stem, "", None
    buffer: list[str] = []
    chunks: list[Chunk] = []

    def flush():
        text = " ".join(buffer).strip()
        buffer.clear()
        for piece in split_words(text):
            chunks.append(Chunk(path.name, chapitre, lecon, page, piece))

    for line in path.read_text(encoding="utf-8").splitlines():
        m = _PAGE.search(line)
        if m:
            flush()
            page = int(m.group(1))
        elif line.startswith("# "):
            flush()
            chapitre, lecon = line[2:].strip(), ""
        elif line.startswith("## "):
            flush()
            lecon = line[3:].strip()
        elif line.strip() and not line.lstrip().startswith(">"):
            buffer.append(line.strip())
    flush()
    return chunks


def chunk_pdf(path: Path, chapitre: str, lecon: str = "", first_page: int = 1) -> list[Chunk]:
    from pypdf import PdfReader

    chunks = []
    for i, page in enumerate(PdfReader(path).pages):
        for piece in split_words(page.extract_text() or ""):
            chunks.append(Chunk(path.name, chapitre, lecon, first_page + i, piece))
    return chunks
