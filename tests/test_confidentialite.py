"""Les règles de docs/CONFIDENTIALITE.md, vérifiées dans le code.

Si un de ces tests échoue, ce n'est pas un détail : c'est une promesse faite aux
familles qui n'est plus tenue.
"""
import re
import time
from pathlib import Path

import pytest

from kalan import config, web
from kalan.cours import Observation

ROOT = Path(__file__).resolve().parent.parent


class FausseDiffusion:
    def __init__(self):
        self.evenements = []

    def emettre(self, type_, **data):
        self.evenements.append((type_, data))


@pytest.fixture
def classe(monkeypatch):
    monkeypatch.setattr(config, "CAMERA_AUTORISEE", True)
    return web.ClasseWeb(None, None, None, FausseDiffusion())


PAGE, AUTRE_PAGE = object(), object()


def test_sans_consentement_la_camera_est_ignoree(classe):
    classe.recevoir_observation(PAGE, {"present": False})
    classe.recevoir_geste(PAGE, "main_levee")
    assert classe.observation() == Observation() and not classe.geste_en_attente()


def test_seule_la_page_qui_a_donne_l_accord_compte(classe):
    classe.donner_consentement(PAGE)
    classe.recevoir_observation(AUTRE_PAGE, {"present": False})
    assert classe.observation().present
    classe.recevoir_observation(PAGE, {"present": False})
    assert not classe.observation().present


def test_retirer_l_accord_efface_tout(classe):
    classe.donner_consentement(PAGE)
    classe.recevoir_observation(PAGE, {"fatigue": True})
    classe.recevoir_geste(PAGE, "main_levee")
    classe.retirer_consentement()
    assert classe.observation() == Observation() and not classe.geste_en_attente()


def test_camera_interdite_par_l_etablissement(classe, monkeypatch):
    monkeypatch.setattr(config, "CAMERA_AUTORISEE", False)
    classe.donner_consentement(PAGE)
    classe.recevoir_observation(PAGE, {"present": False})
    classe.recevoir_geste(PAGE, "main_levee")
    assert classe.observation().present and not classe.geste_en_attente()


def test_seuls_des_signaux_oui_non_connus_passent():
    obs = web.lire_observation({"present": False, "fatigue": "très", "visage": "base64…",
                                "emotion": "triste", "identite": "Awa", "perplexe": True})
    assert obs == Observation(present=False, perplexe=True)


def test_gestes_inconnus_refuses(classe):
    classe.donner_consentement(PAGE)
    classe.recevoir_geste(PAGE, "photo")
    assert not classe.geste_en_attente()


def test_un_signal_perime_ne_compte_plus(classe):
    classe.donner_consentement(PAGE)
    classe.recevoir_observation(PAGE, {"present": False})
    classe.obs_t = time.time() - 10
    assert classe.observation().present


def test_la_page_ne_peut_rien_charger_hors_de_l_appareil():
    csp = dict(web.entetes_securite(8765))["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "'unsafe-eval'" not in csp
    hotes = set(re.findall(r"(?:https?|wss?)://([^\s;:]+)", csp))
    assert hotes <= {"localhost", "127.0.0.1"}
    assert "microphone=()" in dict(web.entetes_securite(8765))["Permissions-Policy"]


def test_aucune_adresse_internet_dans_la_page():
    """Les fichiers de l'écran (hors bibliothèques tierces) ne citent aucun site."""
    for f in (ROOT / "web").glob("*.*"):
        texte = f.read_text(encoding="utf-8")
        assert not re.search(r"https?://(?!localhost)", texte), f.name


def test_rien_de_la_camera_n_est_ecrit_sur_disque():
    """Ni le serveur ni le cours n'ouvrent de fichier en écriture."""
    for f in ("web.py", "cours.py", "voice.py"):
        code = (ROOT / "kalan" / f).read_text(encoding="utf-8")
        assert not re.search(r"open\([^)]*['\"][wa]", code), f
        assert "write_bytes" not in code, f
    # La seule écriture de cours.py est le texte du cours (contenu pédagogique, pas l'élève).
    assert (ROOT / "kalan" / "cours.py").read_text(encoding="utf-8").count("write_text") == 1
