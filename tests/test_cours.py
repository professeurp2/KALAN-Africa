"""Mode cours, sans micro ni modèles : un élève scripté remplace la classe."""
import json

from kalan.assistant import Reponse, Segment
from kalan.cours import Cours, Lecon, faire_cours, generer, intention, parse_segments
from kalan.index import Index
from kalan.chunking import Chunk
from test_pipeline import DIM, fake_embed


def test_intention():
    assert intention(None) == "rien"
    assert intention("Sous-titres réalisés par la communauté d'Amara.org") == "rien"
    assert intention("Arrête, s'il te plaît.") == "stop"
    assert intention("Tu peux répéter ?") == "repete"
    assert intention("D'accord, continue.") == "suite"
    assert intention("Oui") == "suite"
    assert intention("Oui mais pourquoi la lampe brille ?") == "question"
    assert intention("C'est quoi une pile ?") == "question"


class Eleve:
    """Joue un scénario : {numéro de la phrase dite: ce que l'élève dit par-dessus}."""

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


class FakeAssistant:
    def __init__(self):
        self.questions = []

    def repondre(self, q):
        self.questions.append(q)
        return Reponse([Segment("Réponse.")], ["Leçon 1 · p. 42"])


COURS = Cours("Chapitre 3", [Lecon("Leçon 1", "p. 42", [Segment("A."), Segment("B."), Segment("C.")])])
# Phrases dites sans interruption : 1 intro, 2 « Leçon 1. », 3 A, 4 B, 5 C, 6 « c'est clair ? », 7 fin.


def test_cours_sans_interruption():
    e = Eleve()
    faire_cours(COURS, FakeAssistant(), e)
    assert e.dit[2:5] == ["A.", "B.", "C."] and len(e.dit) == 7


def test_question_au_milieu_puis_reprise_de_la_phrase_coupee():
    e, a = Eleve(coupe={4: "Pourquoi la lampe brille ?"}), FakeAssistant()
    faire_cours(COURS, a, e)
    assert a.questions == ["Pourquoi la lampe brille ?"]
    # B coupée → réponse → « On reprend » → B redite en entier → C
    assert e.dit[3:8] == ["B.", "Réponse.", "Bien. On reprend.", "B.", "C."]


def test_question_pendant_la_pause_passe_a_la_suite():
    e, a = Eleve(apres={3: "C'est quoi un générateur ?"}), FakeAssistant()
    faire_cours(COURS, a, e)
    assert e.dit[2:6] == ["A.", "Réponse.", "Bien. On reprend.", "B."]


def test_repete_et_arrete():
    e = Eleve(apres={3: "Répète", 4: "Arrête"})
    faire_cours(COURS, FakeAssistant(), e)
    assert e.dit[2:] == ["A.", "A.", "D'accord, on s'arrête là. À bientôt !"]


def test_bruit_pendant_la_phrase_la_fait_redire_sans_appeler_le_llm():
    e, a = Eleve(coupe={3: "Merci."}), FakeAssistant()
    faire_cours(COURS, a, e)
    assert a.questions == [] and e.dit[2:4] == ["A.", "A."]


def test_generer_un_cours_par_lecon(tmp_path):
    idx = Index(tmp_path / "i.sqlite", model="fake", dim=DIM)
    chunks = [Chunk("x.md", "Chapitre 3 — Le circuit électrique simple", "Leçon 1", 42, "La pile est un générateur."),
              Chunk("x.md", "Chapitre 3 — Le circuit électrique simple", "Leçon 2", 43, "Circuit fermé.")]
    idx.add(chunks, fake_embed([c.text for c in chunks]))
    llm = lambda prompt, system: json.dumps({"segments": [{"texte": "Voici la pile.", "pointe": "pile"},
                                                          {"texte": "Et un moteur.", "pointe": "moteur"}]})
    cours = generer("Chapitre 3 — Le circuit électrique simple", idx, llm)
    assert [l.titre for l in cours.lecons] == ["Leçon 1", "Leçon 2"]
    assert [s.pointe for s in cours.lecons[0].segments] == ["pile", None]


def test_parse_segments_json_invalide():
    assert parse_segments("pas du json", None) == []
