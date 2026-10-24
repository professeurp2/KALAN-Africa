"""Mode cours : Kalan déroule la leçon comme un enseignant, et l'élève peut
l'interrompre à tout moment. Kalan répond, puis reprend là où il s'était arrêté.

Le texte oral du cours est généré une fois par le LLM, leçon par leçon, à partir
des seuls passages du programme, puis mis en cache dans data/cours/. Un
enseignant peut relire et corriger ce fichier avant usage en classe : en mode
cours, Kalan ne dit que ce qui est écrit dedans, plus les réponses ancrées.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from . import config
from .assistant import Assistant, Segment, ask_llm
from .index import Index
from .schemas import Schema, schema_for

COURS_DIR = config.ROOT / "data" / "cours"

SYSTEM_COURS = """Tu es Kalan, un enseignant patient qui fait cours à voix haute à un élève malien.
À partir UNIQUEMENT du TEXTE DE LA LEÇON, écris ce que tu dis en classe pour l'expliquer :
- 4 à 8 phrases courtes et simples, dans l'ordre logique de la leçon ;
- tu peux poser une question à l'élève pour le faire réfléchir, puis y répondre toi-même ;
- n'ajoute AUCUNE connaissance absente du texte ;
- chaque phrase est un segment. Si un SCHÉMA est fourni et qu'une phrase parle d'un de ses éléments,
  mets l'identifiant de cet élément dans "pointe" ; sinon null.
Réponds en JSON strict : {"segments": [{"texte": "...", "pointe": "id_ou_null"}]}"""


@dataclass
class Lecon:
    titre: str
    citation: str
    segments: list[Segment] = field(default_factory=list)


@dataclass
class Cours:
    chapitre: str
    lecons: list[Lecon]

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Cours":
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(d["chapitre"], [Lecon(l["titre"], l["citation"], [Segment(**s) for s in l["segments"]])
                                   for l in d["lecons"]])


def slug(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def generer(chapitre: str, index: Index, llm=ask_llm) -> Cours:
    """Écrit le cours oral d'un chapitre, une leçon à la fois."""
    schema = schema_for(chapitre)
    lecons: dict[str, list] = {}
    for c in index.chunks():
        if c.chapitre == chapitre:
            lecons.setdefault(c.lecon, []).append(c)
    out = []
    for titre, chunks in lecons.items():
        texte = " ".join(c.text for c in chunks)
        prompt = f"TEXTE DE LA LEÇON « {titre} » :\n{texte}"
        if schema:
            elems = "\n".join(f"- {eid} : {desc}" for eid, desc in schema.elements.items())
            prompt += f"\n\nSCHÉMA « {schema.titre} », éléments pointables :\n{elems}"
        out.append(Lecon(titre, chunks[0].citation(), parse_segments(llm(prompt, SYSTEM_COURS), schema)))
    return Cours(chapitre, out)


def parse_segments(raw: str, schema: Schema | None) -> list[Segment]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    valid = set(schema.elements) if schema else set()
    return [Segment(str(s["texte"]).strip(), s.get("pointe") if s.get("pointe") in valid else None)
            for s in data.get("segments") or [] if isinstance(s, dict) and s.get("texte")]


def charger(chapitre: str, index: Index, regenerer: bool = False, llm=ask_llm) -> Cours:
    path = COURS_DIR / f"{slug(chapitre)}.json"
    if path.exists() and not regenerer:
        return Cours.load(path)
    cours = generer(chapitre, index, llm)
    cours.save(path)
    return cours


# --- Ce que l'élève dit pendant le cours ---

_SUITE = re.compile(r"^(oui|non|ok|okay|d accord|continue[sz]?|vas y|allez y|c est clair|c est bon|ca va|"
                    r"j ai compris|compris|merci|non merci|pas de question)\b")
_REPETE = re.compile(r"\b(repete[sz]?|repeter|redis|redire|encore une fois|pas entendu)\b")
_STOP = re.compile(r"\b(arrete[sz]?|stop|on s arrete|termine|fin du cours)\b")
# Phrases que Whisper invente sur du bruit ou du silence.
_HALLUCINATIONS = re.compile(r"amara|sous[ -]titr|abonnez")


def _normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def intention(texte: str | None) -> str:
    """'rien', 'stop', 'repete', 'suite' ou 'question'."""
    t = _normaliser(texte or "")
    if not t or _HALLUCINATIONS.search(t):
        return "rien"
    if _STOP.search(t):
        return "stop"
    if _REPETE.search(t):
        return "repete"
    if len(t.split()) <= 4 and _SUITE.match(t):
        return "suite"
    return "question"


class Classe(Protocol):
    def dire(self, seg: Segment) -> str | None:
        """Dit la phrase. Si l'élève parle par-dessus, s'arrête et renvoie ce qu'il a dit."""

    def ecouter(self, attente: float) -> str | None:
        """Laisse `attente` secondes à l'élève pour parler ; renvoie ce qu'il a dit."""

    def afficher(self, texte: str): ...


def faire_cours(cours: Cours, assistant: Assistant, classe: Classe,
                pause: float = 0.8, pause_fin_lecon: float = 3.0):
    dire = lambda texte: classe.dire(Segment(texte))

    def echange(question: str | None) -> str | None:
        """Répond aux questions jusqu'à ce que l'élève n'en ait plus. Renvoie 'stop' ou 'repete' s'il le demande."""
        while True:
            action = intention(question)
            if action in ("stop", "repete"):
                return action
            if action != "question":
                return None
            rep = assistant.repondre(question)
            question = None
            for seg in rep.segments:
                question = classe.dire(seg)
                if question:
                    break
            if question:
                continue
            if rep.citations:
                classe.afficher("📖 Source : " + " | ".join(rep.citations))
            question = classe.ecouter(pause_fin_lecon)
            if question is None:
                question = dire("Bien. On reprend.")
                if question is None:
                    return None

    question = dire(f"Aujourd'hui, on étudie : {cours.chapitre}. "
                    "Si tu as une question, pose-la quand tu veux : je t'écoute.")
    if echange(question) == "stop":
        return dire("D'accord, on s'arrête là. À bientôt !")

    for lecon in cours.lecons:
        classe.afficher(f"\n📘 {lecon.titre}   ({lecon.citation})")
        segments = [Segment(f"{lecon.titre}.")] + lecon.segments + [
            Segment("Est-ce que c'est clair ? Si tu as une question, c'est le moment.")]
        i = 0
        while i < len(segments):
            dernier = i == len(segments) - 1
            question = classe.dire(segments[i])
            coupe = question is not None  # interrompu au milieu de la phrase
            if not coupe:
                question = classe.ecouter(pause_fin_lecon if dernier else pause)
            action = echange(question)
            if action == "stop":
                return dire("D'accord, on s'arrête là. À bientôt !")
            if action == "repete" or coupe:
                continue  # redire la même phrase
            i += 1

    dire(f"C'est la fin du chapitre : {cours.chapitre}. Bravo, tu as bien travaillé !")
