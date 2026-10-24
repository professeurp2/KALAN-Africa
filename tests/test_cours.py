"""Mode cours, sans micro ni modèles : un élève scripté remplace la classe, un LLM scripté répond."""
import json
import random

from kalan.assistant import Assistant, Segment
from kalan.chunking import Chunk
from kalan.cours import (CLAIR, INCOMPRIS, REFUS, REPRISES, Cours, Lecon, faire_cours, generer,
                         intention, parse_segments, reagir)
from kalan.index import Index
from test_pipeline import DIM, fake_embed

CHAPITRE = "Chapitre 3 — Le circuit électrique simple"


def test_intention():
    assert intention(None) == "rien"
    assert intention("Sous-titres réalisés par la communauté d'Amara.org") == "rien"
    assert intention("Merci d'avoir regardé cette vidéo.") == "rien"
    assert intention("Arrête, s'il te plaît.") == "stop"
    assert intention("Tu peux répéter ?") == "repete"
    assert intention("Reprends ce que tu viens de dire.") == "repete"
    assert intention("D'accord, continue.") == "suite"
    assert intention("Oui") == "suite"
    assert intention("Oui mais pourquoi la lampe brille ?") == "parole"
    assert intention("C'est pas bien compris") == "parole"  # le LLM réexplique


def make_assistant(tmp_path, reactions):
    """`reactions` : ce que le LLM scripté renvoie, dans l'ordre."""
    idx = Index(tmp_path / "i.sqlite", model="fake", dim=DIM)
    chunks = [Chunk("x.md", CHAPITRE, "Leçon 1", 42, "La pile est un générateur. La lampe est un récepteur."),
              Chunk("x.md", CHAPITRE, "Leçon 2", 43, "Quand l'interrupteur est ouvert, le circuit est ouvert.")]
    idx.add(chunks, fake_embed([c.text for c in chunks]))
    prompts = []

    def llm(prompt, system=None):
        prompts.append(prompt)
        return json.dumps(reactions.pop(0))
    a = Assistant(idx, fake_embed, llm)
    a.prompts = prompts
    return a


class Eleve:
    """Joue un scénario : {nombre de phrases déjà dites par Kalan: ce que l'élève dit}."""

    def __init__(self, coupe=None, apres=None):
        self.coupe, self.apres = coupe or {}, apres or {}
        self.dit: list[str] = []

    def dire(self, seg):
        self.dit.append(seg.texte)
        return self.coupe.pop(len(self.dit), None)

    def ecouter(self, attente):
        return self.apres.pop(len(self.dit), None)

    def afficher(self, texte):
        pass


COURS = Cours(CHAPITRE, [Lecon("Leçon 1", "p. 42", [Segment("A."), Segment("B."), Segment("C.")])])
# Sans interruption : 1 intro, 2 « Leçon 1. », 3 A, 4 B, 5 C, 6 « c'est clair ? », 7 fin.
RNG = lambda: random.Random(0)


def test_cours_sans_interruption(tmp_path):
    e = Eleve()
    faire_cours(COURS, make_assistant(tmp_path, []), e, rng=RNG())
    assert e.dit[2:5] == ["A.", "B.", "C."] and len(e.dit) == 7
    assert e.dit[0].startswith("Bonjour ! Aujourd'hui, on étudie ensemble le chapitre 3 : Le circuit")
    assert e.dit[5] in CLAIR


def test_question_mal_transcrite_comprise_en_contexte(tmp_path):
    a = make_assistant(tmp_path, [{"type": "question", "sources": [1],
                                   "segments": [{"texte": "Le générateur ? C'est la pile.", "pointe": "pile"}]}])
    e = Eleve(coupe={4: "Ah, c'est quoi le gératère ?"})
    faire_cours(COURS, a, e, rng=RNG())
    # Kalan reçoit la leçon en cours et la phrase qu'il disait
    assert "LEÇON EN COURS : Leçon 1" in a.prompts[0] and "DERNIÈRE PHRASE DITE : B." in a.prompts[0]
    assert "La pile est un générateur" in a.prompts[0]
    # B coupée → réponse → reprise → B redite en entier → C
    assert e.dit[3:5] == ["B.", "Le générateur ? C'est la pile."]
    assert e.dit[5] in REPRISES and e.dit[6:8] == ["B.", "C."]


def test_question_pendant_la_pause_passe_a_la_suite(tmp_path):
    a = make_assistant(tmp_path, [{"type": "pas_compris", "sources": [1], "segments": [{"texte": "Autrement dit…"}]}])
    e = Eleve(apres={3: "J'ai pas bien compris"})
    faire_cours(COURS, a, e, rng=RNG())
    assert e.dit[2:4] == ["A.", "Autrement dit…"] and e.dit[4] in REPRISES and e.dit[5] == "B."


def test_hors_programme_et_incompris_ne_sont_pas_la_meme_phrase(tmp_path):
    a = make_assistant(tmp_path, [{"type": "hors_programme", "segments": []},
                                  {"type": "incompris", "segments": []}])
    e = Eleve(apres={3: "Qui a inventé la pile ?", 6: "grenadier bleu"})
    faire_cours(COURS, a, e, rng=RNG())
    assert e.dit[3] in REFUS and e.dit[4] in REPRISES and e.dit[5] == "B."
    assert e.dit[6] in INCOMPRIS


def test_bavardage(tmp_path):
    a = make_assistant(tmp_path, [{"type": "bavardage", "segments": [{"texte": "Salut ! Je suis Kalan."}]}])
    e = Eleve(apres={1: "Salut, qui es-tu ?"})
    faire_cours(COURS, a, e, rng=RNG())
    assert e.dit[1] == "Salut ! Je suis Kalan." and e.dit[2] in REPRISES


def test_repete_et_arrete(tmp_path):
    e = Eleve(apres={3: "Répète", 4: "Arrête"})
    faire_cours(COURS, make_assistant(tmp_path, []), e, rng=RNG())
    assert e.dit[2:] == ["A.", "A.", "D'accord, on s'arrête là. À bientôt !"]


def test_bruit_pendant_la_phrase_la_fait_redire_sans_appeler_le_llm(tmp_path):
    a = make_assistant(tmp_path, [])
    e = Eleve(coupe={3: "Merci."})
    faire_cours(COURS, a, e, rng=RNG())
    assert a.prompts == [] and e.dit[2:4] == ["A.", "A."]


def test_memoire_de_la_seance(tmp_path):
    """Kalan reçoit l'historique et les passages des leçons déjà vues."""
    cours = Cours(CHAPITRE, [Lecon("Leçon 1", "p. 42", [Segment("La pile est un générateur.")]),
                             Lecon("Leçon 2", "p. 43", [Segment("X.")])])
    a = make_assistant(tmp_path, [{"type": "question", "sources": [1], "segments": [{"texte": "J'ai dit…"}]}])
    e = Eleve(apres={6: "Tu as dit quoi sur la pile ?"})  # pendant la leçon 2
    faire_cours(cours, a, e, rng=RNG())
    prompt = a.prompts[0]
    assert "HISTORIQUE DE LA SÉANCE" in prompt and "Kalan : La pile est un générateur." in prompt
    assert "Élève : Tu as dit quoi sur la pile ?" in prompt
    assert "La pile est un générateur. La lampe est un récepteur." in prompt  # passage de la leçon 1


class EleveObserve(Eleve):
    def __init__(self, observations, **kw):
        super().__init__(**kw)
        self.observations = observations

    def observation(self):
        from kalan.cours import Observation
        return self.observations.pop(0) if self.observations else Observation()


def test_camera_eleve_absent_puis_perplexe(tmp_path):
    from kalan.cours import ABSENT, PERPLEXE, Observation
    e = EleveObserve([Observation(present=False), Observation(present=True),
                      Observation(perplexe=True), Observation(perplexe=True)])
    faire_cours(COURS, make_assistant(tmp_path, []), e, rng=RNG())
    # après « Leçon 1. » : absent → attend → revenu → A → perplexe
    assert e.dit[2] == ABSENT and e.dit[3] == "A." and e.dit[4] == PERPLEXE
    assert e.dit.count(PERPLEXE) == 1  # une seule remarque par leçon


def test_reagir_json_invalide_est_incompris(tmp_path):
    a = make_assistant(tmp_path, [])
    a.llm = lambda prompt, system=None: "pas du json"
    assert reagir("hein", CHAPITRE, "Leçon 1", "A.", a).type == "incompris"


def test_generer_un_cours_par_lecon(tmp_path):
    idx = Index(tmp_path / "i.sqlite", model="fake", dim=DIM)
    chunks = [Chunk("x.md", CHAPITRE, "Leçon 1", 42, "La pile est un générateur."),
              Chunk("x.md", CHAPITRE, "Leçon 2", 43, "Circuit fermé.")]
    idx.add(chunks, fake_embed([c.text for c in chunks]))
    llm = lambda prompt, system: json.dumps({"segments": [{"texte": "Voici la pile.", "pointe": "pile"},
                                                          {"texte": "Et un moteur.", "pointe": "moteur"}]})
    cours = generer(CHAPITRE, idx, llm)
    assert [l.titre for l in cours.lecons] == ["Leçon 1", "Leçon 2"]
    assert [s.pointe for s in cours.lecons[0].segments] == ["pile", None]


def test_parse_segments_json_invalide():
    assert parse_segments("pas du json", None) == []
