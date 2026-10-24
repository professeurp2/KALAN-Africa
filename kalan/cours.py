"""Mode cours : Kalan déroule la leçon comme un enseignant, et l'élève peut
l'interrompre à tout moment. Kalan réagit, puis reprend là où il s'était arrêté.

Le texte oral du cours est généré une fois par le LLM, leçon par leçon, à partir
des seuls passages du programme, puis mis en cache dans data/cours/. Un
enseignant peut relire et corriger ce fichier avant usage en classe : en mode
cours, Kalan ne dit que ce qui est écrit dedans, plus ses réactions ancrées.

Quand l'élève parle, Kalan comprend en contexte, comme un enseignant : la leçon
en cours et la dernière phrase dite. « C'est quoi ça ? » porte sur ce qui vient
d'être dit, et un mot mal transcrit (« gératère ») se devine avec le vocabulaire
de la leçon.
"""
from __future__ import annotations

import json
import random
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from . import config
from .assistant import Assistant, Reponse, Segment, ask_llm
from .index import Index
from .schemas import Schema, schema_for

COURS_DIR = config.ROOT / "data" / "cours"

SYSTEM_COURS = """Tu es Kalan, un enseignant chaleureux qui fait cours à voix haute à un élève malien.
À partir UNIQUEMENT du TEXTE DE LA LEÇON, écris ce que tu dis en classe pour l'expliquer :
- commence par une question d'accroche qui fait réfléchir l'élève, puis explique ;
- 4 à 8 phrases courtes et simples, dans l'ordre logique de la leçon ; tutoie l'élève ;
- parle comme à l'oral, avec des tournures variées, pas comme un manuel ;
- ne répète pas le titre de la leçon ; n'ajoute AUCUNE connaissance absente du texte ;
- chaque phrase est un segment. Si un SCHÉMA est fourni et qu'une phrase parle d'un de ses éléments,
  mets l'identifiant de cet élément dans "pointe" ; sinon null.
Réponds en JSON strict : {"segments": [{"texte": "...", "pointe": "id_ou_null"}]}"""

SYSTEM_CLASSE = """Tu es Kalan, un enseignant chaleureux et patient. Tu fais cours à un élève malien et il vient de te parler.
Ce qu'il a dit vient d'une transcription automatique de sa voix : des mots peuvent être mal reconnus.
Devine le sens avec le vocabulaire de la leçon (exemple : « gératère » veut dire « générateur »).

Choisis le "type" de ce qu'il a dit, puis réagis :
- "question" : une question sur la leçon ou le programme. Réponds UNIQUEMENT avec les EXTRAITS DU PROGRAMME,
  en 1 à 3 phrases courtes et simples, en le tutoyant. Tu peux reprendre son mot (« Le générateur ? C'est… »).
- "pas_compris" : il dit qu'il n'a pas compris (même si le reste de sa phrase est confus), ou demande
  d'expliquer autrement. Réexplique l'idée de la DERNIÈRE PHRASE DITE AVEC D'AUTRES MOTS, plus simples
  (ne la répète jamais telle quelle), en t'appuyant sur les extraits, en 1 à 3 phrases.
- "bavardage" : salutation, remerciement, « qui es-tu », « écoute », encouragement… Réponds en une phrase
  courte et gentille. Tu es Kalan, l'assistant qui l'aide à comprendre son programme.
- "hors_programme" : une vraie question, mais les extraits ne permettent pas d'y répondre. "segments" vide.
- "incompris" : même en devinant, ce qu'il a dit n'a pas de sens. "segments" vide.
N'ajoute jamais de connaissance absente des extraits. Si un SCHÉMA est fourni et qu'une phrase parle d'un
de ses éléments, mets son identifiant dans "pointe", sinon null.
JSON strict : {"type": "...", "segments": [{"texte": "...", "pointe": null}], "sources": [numéros des extraits utilisés]}"""

# Ce que Kalan dit autour du cours. Varier évite l'effet machine.
INTRO = ("Bonjour ! Aujourd'hui, on étudie ensemble {chapitre}. "
         "Si tu ne comprends pas quelque chose, arrête-moi quand tu veux et pose ta question.")
REFUS = ["Ça, ce n'est pas dans notre leçon. Je ne veux pas te dire de bêtises : demande à ton professeur, il saura t'expliquer.",
         "Bonne curiosité ! Mais ce n'est pas dans ton programme, alors je préfère ne pas inventer. Pose la question à ton professeur.",
         "Je n'ai pas cette réponse dans ton manuel. Ton professeur pourra t'aider là-dessus."]
INCOMPRIS = ["Pardon, je n'ai pas bien entendu. Tu peux répéter ta question ?",
             "Excuse-moi, je n'ai pas compris. Redis-le moi, un peu plus près du micro.",
             "Hmm, je n'ai pas saisi. Tu peux reformuler ?"]
REPRISES = ["Bien, on reprend.", "D'accord, je continue.", "Très bien. Revenons à la leçon.", "Bon, on continue."]
CLAIR = ["Est-ce que c'est clair ? Si tu as une question, c'est le moment.",
         "Tu as bien suivi ? Pose-moi une question si quelque chose n'est pas clair.",
         "Ça va jusque-là ? Je t'écoute si tu veux que je réexplique quelque chose."]
AU_REVOIR = "D'accord, on s'arrête là. À bientôt !"
FIN = "C'est la fin du chapitre. Bravo, tu as bien travaillé !"


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


def oral(titre: str) -> str:
    """« Chapitre 3 — Le circuit » se dit « le chapitre 3 : le circuit »."""
    t = titre.replace(" — ", " : ")
    return "le c" + t[1:] if t.startswith("Chapitre") else t


def _schema_prompt(schema: Schema | None) -> str:
    if not schema:
        return ""
    elems = "\n".join(f"- {eid} : {desc}" for eid, desc in schema.elements.items())
    return f"\n\nSCHÉMA « {schema.titre} », éléments pointables :\n{elems}"


def generer(chapitre: str, index: Index, llm=ask_llm) -> Cours:
    """Écrit le cours oral d'un chapitre, une leçon à la fois."""
    schema = schema_for(chapitre)
    lecons: dict[str, list] = {}
    for c in index.chunks():
        if c.chapitre == chapitre:
            lecons.setdefault(c.lecon, []).append(c)
    out = []
    for titre, chunks in lecons.items():
        prompt = f"TEXTE DE LA LEÇON « {titre} » :\n" + " ".join(c.text for c in chunks) + _schema_prompt(schema)
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
_REPETE = re.compile(r"\b(repete[sz]?|repeter|redis|redire|reprends?|recommence[sz]?|encore une fois|pas entendu)\b")
_STOP = re.compile(r"\b(arrete[sz]?|stop|on s arrete|termine|fin du cours)\b")
# Phrases que Whisper invente sur du bruit ou du silence (fins de vidéos YouTube).
_HALLUCINATIONS = re.compile(r"amara|sous titr|abonnez|regarde cette video|merci d avoir regarde")


def _normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def intention(texte: str | None) -> str:
    """Tri rapide, sans LLM : 'rien', 'stop', 'repete', 'suite' ou 'parole' (à comprendre par le LLM)."""
    t = _normaliser(texte or "")
    if not t or _HALLUCINATIONS.search(t):
        return "rien"
    if _STOP.search(t):
        return "stop"
    if len(t.split()) <= 8 and _REPETE.search(t):
        return "repete"
    if len(t.split()) <= 4 and _SUITE.match(t):
        return "suite"
    return "parole"


@dataclass
class Reaction:
    type: str  # question, pas_compris, bavardage, hors_programme, incompris
    reponse: Reponse


TYPES = {"question", "pas_compris", "bavardage", "hors_programme", "incompris"}


def reagir(parole: str, chapitre: str, lecon: str, derniere: str, assistant: Assistant) -> Reaction:
    """Comprend ce que l'élève a dit dans le contexte de la leçon, et prépare la réaction de Kalan."""
    extraits, vus = [], set()
    proches = [h.chunk for h in assistant.index.search(assistant.embed([parole])[0])
               if h.score >= config.MIN_SIMILARITY]
    for c in [c for c in assistant.index.chunks() if c.chapitre == chapitre and c.lecon == lecon] + proches:
        if c.text not in vus:
            vus.add(c.text)
            extraits.append(c)
    schema = schema_for(chapitre)
    prompt = ("EXTRAITS DU PROGRAMME :\n"
              + "\n\n".join(f"[{i + 1}] ({c.citation()})\n{c.text}" for i, c in enumerate(extraits))
              + _schema_prompt(schema)
              + f"\n\nLEÇON EN COURS : {lecon}\nDERNIÈRE PHRASE DITE : {derniere}\nL'ÉLÈVE A DIT : {parole}")
    raw = assistant.llm(prompt, SYSTEM_CLASSE)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return Reaction("incompris", Reponse([]))
    typ = data.get("type") if data.get("type") in TYPES else "incompris"
    segments = parse_segments(raw, schema)
    if typ in ("question", "pas_compris", "bavardage") and not segments:
        typ = "hors_programme" if typ != "bavardage" else "incompris"
    if typ in ("hors_programme", "incompris"):
        return Reaction(typ, Reponse([], hors_programme=True))
    citations = []
    if typ != "bavardage":
        used = [int(n) for n in data.get("sources") or [] if str(n).isdigit() and 1 <= int(n) <= len(extraits)]
        citations = list(dict.fromkeys(extraits[n - 1].citation() for n in used)) or [extraits[0].citation()]
    return Reaction(typ, Reponse(segments, citations))


class Classe(Protocol):
    def dire(self, seg: Segment) -> str | None:
        """Dit la phrase. Si l'élève parle par-dessus, s'arrête et renvoie ce qu'il a dit."""

    def ecouter(self, attente: float) -> str | None:
        """Laisse `attente` secondes à l'élève pour parler ; renvoie ce qu'il a dit."""

    def afficher(self, texte: str): ...


def faire_cours(cours: Cours, assistant: Assistant, classe: Classe,
                pause: float = 0.8, pause_fin_lecon: float = 3.0, rng: random.Random | None = None):
    rng = rng or random.Random()
    dire = lambda texte: classe.dire(Segment(texte))

    def echange(parole: str | None, lecon: str, derniere: str) -> str | None:
        """Réagit à l'élève jusqu'à ce qu'il laisse Kalan reprendre. Renvoie 'stop' ou 'repete' s'il le demande."""
        while True:
            action = intention(parole)
            if action in ("stop", "repete"):
                return action
            if action != "parole":
                return None
            r = reagir(parole, cours.chapitre, lecon, derniere, assistant)
            if r.type == "incompris":
                segments = [Segment(rng.choice(INCOMPRIS))]
            elif r.type == "hors_programme":
                segments = [Segment(rng.choice(REFUS))]
            else:
                segments = r.reponse.segments
            parole = None
            for seg in segments:
                parole = classe.dire(seg)
                if parole:
                    break
                derniere = seg.texte
            if parole:
                continue
            if r.reponse.citations:
                classe.afficher("📖 Source : " + " | ".join(r.reponse.citations))
            parole = classe.ecouter(5.0 if r.type == "incompris" else pause_fin_lecon)
            if parole is None:
                parole = dire(rng.choice(REPRISES))
                if parole is None:
                    return None

    premiere = cours.lecons[0].titre if cours.lecons else ""
    intro = INTRO.format(chapitre=oral(cours.chapitre))
    if echange(dire(intro) or classe.ecouter(pause), premiere, intro) == "stop":
        return dire(AU_REVOIR)

    for lecon in cours.lecons:
        classe.afficher(f"\n📘 {lecon.titre}   ({lecon.citation})")
        segments = [Segment(f"{oral(lecon.titre)}.")] + lecon.segments + [Segment(rng.choice(CLAIR))]
        i = 0
        while i < len(segments):
            dernier = i == len(segments) - 1
            parole = classe.dire(segments[i])
            coupe = parole is not None  # interrompu au milieu de la phrase
            if not coupe:
                parole = classe.ecouter(pause_fin_lecon if dernier else pause)
            action = echange(parole, lecon.titre, segments[i].texte)
            if action == "stop":
                return dire(AU_REVOIR)
            if action == "repete" or coupe:
                continue  # redire la même phrase
            i += 1

    dire(FIN)
