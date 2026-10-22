"""Tests sans modèles : un embedder factice par sac de mots remplace MiniLM."""
import json

import numpy as np

from kalan import config
from kalan.assistant import Assistant, parse_llm
from kalan.chunking import chunk_markdown, split_words
from kalan.index import Index

VOCAB = ["pile", "lampe", "interrupteur", "courant", "circuit", "fermé", "ouvert", "borne", "football"]
DIM = len(VOCAB)


def fake_embed(texts):
    out = []
    for t in texts:
        v = np.array([t.lower().count(w) for w in VOCAB], dtype=np.float32)
        out.append(v / (np.linalg.norm(v) or 1))
    return np.stack(out)


def make_index(tmp_path, programme):
    idx = Index(tmp_path / "i.sqlite", model="fake", dim=DIM)
    chunks = chunk_markdown(programme)
    idx.add(chunks, fake_embed([c.text for c in chunks]))
    return idx


def write_chapter(tmp_path):
    f = tmp_path / "ch.md"
    f.write_text(
        "> avertissement ignoré\n# Chapitre 3 — Le circuit électrique simple\n"
        "## Leçon 2 — Circuit ouvert et circuit fermé\n<!-- page: 43 -->\n"
        "Quand l'interrupteur est fermé, le circuit est fermé et le courant circule dans la lampe.\n",
        encoding="utf-8")
    return f


def test_split_words_overlap():
    pieces = split_words(" ".join(str(i) for i in range(250)), size=100, overlap=20)
    assert len(pieces) == 3
    assert pieces[1].split()[0] == "80"


def test_chunk_markdown_metadata(tmp_path):
    [c] = chunk_markdown(write_chapter(tmp_path))
    assert c.citation() == "Chapitre 3 — Le circuit électrique simple · Leçon 2 — Circuit ouvert et circuit fermé · p. 43"
    assert "avertissement" not in c.text


def test_index_refuses_other_embedding_model(tmp_path):
    Index(tmp_path / "i.sqlite", model="a", dim=DIM)
    try:
        Index(tmp_path / "i.sqlite", model="b", dim=DIM)
    except RuntimeError:
        return
    raise AssertionError("l'index aurait dû refuser un autre modèle")


def test_hors_programme_refused_without_llm(tmp_path):
    def llm(_):
        raise AssertionError("le LLM ne doit pas être appelé")
    rep = Assistant(make_index(tmp_path, write_chapter(tmp_path)), fake_embed, llm).repondre("football")
    assert rep.hors_programme and rep.texte == config.REFUS


def test_answer_is_cited_from_index_not_llm(tmp_path):
    llm_out = json.dumps({"hors_programme": False, "sources": [1, 99],
                          "segments": [{"texte": "La lampe brille.", "pointe": "lampe"},
                                       {"texte": "Inventé.", "pointe": "moteur"}]})
    rep = Assistant(make_index(tmp_path, write_chapter(tmp_path)), fake_embed,
                    lambda _: llm_out).repondre("pourquoi la lampe brille quand le circuit est fermé")
    assert not rep.hors_programme
    assert rep.citations == ["Chapitre 3 — Le circuit électrique simple · Leçon 2 — Circuit ouvert et circuit fermé · p. 43"]
    assert [s.pointe for s in rep.segments] == ["lampe", None]  # « moteur » n'existe pas dans le schéma


def test_invalid_json_is_a_refusal():
    assert parse_llm("pas du json", [], None).hors_programme
