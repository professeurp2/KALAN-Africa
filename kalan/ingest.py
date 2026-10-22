"""Indexe des chapitres du programme.

    python -m kalan.ingest data/programme                 # tous les .md
    python -m kalan.ingest manuel.pdf --chapitre "Chapitre 3 — ..." --premiere-page 40
    python -m kalan.ingest data/programme --reset         # repart d'un index vide
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .chunking import chunk_markdown, chunk_pdf
from .index import Index, load_embedder


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("chemins", nargs="+", type=Path)
    p.add_argument("--chapitre", help="Titre du chapitre (PDF uniquement)")
    p.add_argument("--lecon", default="")
    p.add_argument("--premiere-page", type=int, default=1, help="Numéro de page du manuel pour la 1re page du PDF")
    p.add_argument("--reset", action="store_true")
    args = p.parse_args(argv)

    if args.reset and config.INDEX_PATH.exists():
        config.INDEX_PATH.unlink()

    files = []
    for path in args.chemins:
        files += sorted(path.glob("*.md")) + sorted(path.glob("*.pdf")) if path.is_dir() else [path]

    index, embed = Index(), load_embedder()
    for f in files:
        if f.suffix == ".pdf":
            chunks = chunk_pdf(f, args.chapitre or f.stem, args.lecon, args.premiere_page)
        else:
            chunks = chunk_markdown(f)
        index.reset_source(f.name)
        if chunks:
            index.add(chunks, embed([c.text for c in chunks]))
        print(f"{f.name}: {len(chunks)} passages")
    print(f"Index : {index.count()} passages → {config.INDEX_PATH}")


if __name__ == "__main__":
    main()
