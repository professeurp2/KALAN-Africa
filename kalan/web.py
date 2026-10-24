# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lamine SACKO
"""Écran de classe : Kalan fait cours dans une page web locale.

    python -m kalan.web                 # ouvre http://localhost:8765
    python -m kalan.web --port 9000 --sans-navigateur
    KALAN_CAMERA=0 python -m kalan.web  # caméra interdite par l'établissement

La voix, le micro et le cours tournent en Python, comme en ligne de commande. La
page affiche l'avatar qui parle, la diapositive qui avance toute seule, le schéma
pointé et les sous-titres, et peut observer l'élève par la caméra.

Les règles de docs/CONFIDENTIALITE.md sont appliquées ici, pas seulement écrites :
- la page ne peut rien charger ni envoyer hors de cet ordinateur (en-têtes CSP) ;
- seule une page servie par Kalan peut se connecter (contrôle d'origine) ;
- sans consentement donné pendant la séance, les signaux caméra sont ignorés ;
- seuls des signaux connus, de type oui/non, sont acceptés ; tout le reste est jeté ;
- rien de ce que voit la caméra n'est écrit, ni sur disque ni dans le journal.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import threading
import time
import webbrowser
from dataclasses import fields
from pathlib import Path

from . import config
from .assistant import Segment
from .cours import Observation
from .voice import ClasseVocale, enveloppe

WEB_DIR = config.ROOT / "web"
SCHEMAS_DIR = config.ROOT / "data" / "schemas"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json", ".svg": "image/svg+xml", ".wasm": "application/wasm",
         ".bin": "application/octet-stream", ".task": "application/octet-stream", ".png": "image/png"}

CHAMPS_OBSERVATION = {f.name for f in fields(Observation)}
GESTES = {"main_levee", "pouce_haut", "pouce_bas"}
OUI = "Oui ? Je t'écoute."


def entetes_securite(port: int) -> list[tuple[str, str]]:
    """Le navigateur lui-même refusera toute ressource ou connexion hors de cet ordinateur."""
    ws = f"ws://localhost:{port} ws://127.0.0.1:{port}"
    csp = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; "
           f"img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' {ws}; "
           "worker-src 'self' blob:; object-src 'none'; base-uri 'none'; form-action 'none'; "
           "frame-ancestors 'none'")
    return [("Content-Security-Policy", csp),
            ("Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=(), usb=()"),
            ("Referrer-Policy", "no-referrer"),
            ("X-Content-Type-Options", "nosniff"),
            ("Cache-Control", "no-store")]


def lire_observation(msg: dict) -> Observation:
    """Ne garde que les signaux connus, et seulement s'ils sont vrais ou faux."""
    return Observation(**{k: v for k, v in msg.items() if k in CHAMPS_OBSERVATION and isinstance(v, bool)})


class Diffusion:
    """Envoie les évènements du cours (fil Python) à toutes les pages ouvertes (boucle asyncio)."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop, self.clients = loop, set()
        self.etat: dict[str, str] = {}  # dernier « seance » et « lecon », rejoués à une page qui se connecte

    def emettre(self, type_: str, **data):
        msg = json.dumps({"type": type_, **data}, ensure_ascii=False)
        if type_ in ("seance", "lecon"):
            self.etat[type_] = msg
        self.loop.call_soon_threadsafe(self._envoyer, msg)

    def _envoyer(self, msg: str):
        from websockets.asyncio.server import broadcast
        broadcast(self.clients, msg)


class ClasseWeb(ClasseVocale):
    """La classe vocale, avec chaque geste de Kalan envoyé à l'écran, et les gestes de l'élève vus par la caméra."""

    def __init__(self, transcrire, speaker, micro, diffusion: Diffusion):
        super().__init__(transcrire, speaker, micro)
        self.d = diffusion
        self.obs, self.obs_t = Observation(), 0.0
        self.consentement = None  # la page qui a donné l'accord caméra pour cette séance
        self._geste: tuple[str, float] | None = None

    # --- Caméra : rien sans consentement ---

    def donner_consentement(self, page):
        self.consentement = page

    def retirer_consentement(self):
        self.consentement = None
        self.obs, self.obs_t, self._geste = Observation(), 0.0, None

    def recevoir_observation(self, page, msg: dict):
        if config.CAMERA_AUTORISEE and page is self.consentement:
            self.obs, self.obs_t = lire_observation(msg), time.time()

    def recevoir_geste(self, page, nom: str):
        if config.CAMERA_AUTORISEE and page is self.consentement and nom in GESTES:
            self._geste = (nom, time.time())

    def observation(self) -> Observation:
        # Caméra coupée, refusée ou page fermée : on fait comme si l'élève était là, attentif.
        return self.obs if self.consentement and time.time() - self.obs_t < 3 else Observation()

    def geste_en_attente(self) -> bool:
        return self._geste is not None and time.time() - self._geste[1] < 4

    def reagir_geste(self, pendant_phrase: bool) -> str | None:
        """Comme en classe : main levée → « Oui ? » ; pouce levé → on continue ; pouce baissé → on réexplique."""
        nom = self._geste[0] if self._geste else None
        self._geste = None
        self.d.emettre("geste", nom=nom)
        if nom == "pouce_haut":
            return "👍 continue"
        if nom == "pouce_bas":
            return "👎 Je n'ai pas compris, tu peux réexpliquer autrement ?"
        oui = Segment(OUI)
        pcm = self.speaker.synth(oui.texte)
        self.annoncer(oui, pcm)
        self.micro.jouer(pcm, self.speaker.rate)
        texte = self._texte(self.micro.ecouter(6.0))
        if texte:
            return texte
        return "répète" if pendant_phrase else None  # main baissée sans rien dire : on reprend la phrase coupée

    # --- Ce que l'écran montre ---

    def annoncer(self, seg, pcm):
        super().annoncer(seg, pcm)
        self.d.emettre("dit", texte=seg.texte, pointe=seg.pointe,
                       enveloppe=enveloppe(pcm, self.speaker.rate), pas=0.04)

    def interrompu(self):
        self.d.emettre("coupe")

    def entendu(self, texte: str):
        super().entendu(texte)
        self.d.emettre("eleve", texte=texte)

    def afficher(self, texte: str):
        super().afficher(texte)
        if texte.startswith("📖 Source : "):
            self.d.emettre("source", texte=texte.removeprefix("📖 Source : "))

    def nouvelle_lecon(self, lecon, numero: int, total: int):
        self.afficher(f"\n📘 {lecon.titre}   ({lecon.citation})")
        self.d.emettre("lecon", numero=numero, total=total, titre=lecon.titre,
                       citation=lecon.citation, points=[s.texte for s in lecon.segments])


def _reponse_fichier(connection, base: Path, rel: str, entetes: list[tuple[str, str]]):
    from websockets.datastructures import Headers
    from websockets.http11 import Response

    chemin = (base / rel).resolve()
    if not chemin.is_relative_to(base.resolve()) or not chemin.is_file():
        return connection.respond(404, "Introuvable\n")
    corps = chemin.read_bytes()
    type_ = (TYPES.get(chemin.suffix) or mimetypes.guess_type(chemin.name)[0]
             or ("text/plain; charset=utf-8" if not chemin.suffix else "application/octet-stream"))
    return Response(200, "OK", Headers([("Content-Type", type_), ("Content-Length", str(len(corps)))] + entetes),
                    corps)


async def servir(args, preparer):
    from websockets.asyncio.server import serve

    loop = asyncio.get_running_loop()
    d = Diffusion(loop)
    seance = await asyncio.to_thread(preparer, d)  # chargement des modèles : quelques secondes
    classe: ClasseWeb = seance["classe"]
    fil: list[threading.Thread] = []
    entetes = entetes_securite(args.port)

    def routes(connection, request):
        path = request.path.split("?")[0]
        if path == "/ws":
            return None  # poignée de main WebSocket
        if path == "/":
            return _reponse_fichier(connection, WEB_DIR, "index.html", entetes)
        if path == "/licence":  # GPL, article 5 d : l'interface permet de lire la licence
            return _reponse_fichier(connection, config.ROOT, "LICENSE", entetes)
        if path.startswith("/web/"):
            return _reponse_fichier(connection, WEB_DIR, path[5:], entetes)
        if path.startswith("/schemas/"):
            return _reponse_fichier(connection, SCHEMAS_DIR, path[9:], entetes)
        return connection.respond(404, "Introuvable\n")

    async def page(ws):
        d.clients.add(ws)
        try:
            for msg in d.etat.values():
                await ws.send(msg)
            async for brut in ws:
                try:
                    msg = json.loads(brut)
                except json.JSONDecodeError:
                    continue
                type_ = msg.get("type") if isinstance(msg, dict) else None
                if type_ == "commencer" and not (fil and fil[0].is_alive()):
                    fil[:] = [threading.Thread(target=seance["lancer"], daemon=True)]
                    fil[0].start()
                elif type_ == "consentement_camera" and config.CAMERA_AUTORISEE:
                    if msg.get("accord") is True:
                        classe.donner_consentement(ws)
                    else:
                        classe.retirer_consentement()
                elif type_ == "observation":
                    classe.recevoir_observation(ws, msg)
                elif type_ == "geste":
                    classe.recevoir_geste(ws, msg.get("nom"))
        finally:
            d.clients.discard(ws)
            if classe.consentement is ws:  # page fermée : l'accord ne survit pas à la page
                classe.retirer_consentement()

    origines = [f"http://localhost:{args.port}", f"http://127.0.0.1:{args.port}"]
    async with serve(page, "127.0.0.1", args.port, process_request=routes, origins=origines, max_size=2 ** 16):
        url = f"http://localhost:{args.port}/"
        print(f"\nÉcran de classe prêt : {url}  (Ctrl+C pour quitter)")
        if not config.CAMERA_AUTORISEE:
            print("Caméra désactivée par la configuration (KALAN_CAMERA=0).")
        if not args.sans_navigateur:
            webbrowser.open(url)
        await asyncio.Future()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chapitre", default="", help="partie du titre du chapitre (le premier indexé par défaut)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--regenerer", action="store_true", help="réécrire le texte du cours")
    p.add_argument("--sans-navigateur", action="store_true")
    args = p.parse_args(argv)

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    def preparer(d: Diffusion) -> dict:
        from .assistant import Assistant
        from .cours import charger, faire_cours
        from .index import Index, load_embedder
        from .schemas import schema_for
        from .voice import Micro, Speaker, Transcriber

        index = Index()
        if index.count() == 0:
            raise SystemExit("Index vide : lancer d'abord `python -m kalan.ingest data/programme`.")
        chapitres = list(dict.fromkeys(c.chapitre for c in index.chunks()))
        chapitre = next((c for c in chapitres if args.chapitre.lower() in c.lower()), None)
        if chapitre is None:
            raise SystemExit("Chapitre introuvable. Chapitres indexés :\n- " + "\n- ".join(chapitres))
        print(f"Préparation du cours : {chapitre}…")
        assistant = Assistant(index, load_embedder())
        le_cours = charger(chapitre, index, regenerer=args.regenerer)
        classe = ClasseWeb(Transcriber(titres=index.titres()), Speaker(), Micro(), d)
        schema = schema_for(chapitre)
        d.emettre("seance", chapitre=chapitre, lecons=[l.titre for l in le_cours.lecons],
                  schema=f"/schemas/{schema.svg.name}" if schema else None,
                  elements=schema.elements if schema else {}, camera_autorisee=config.CAMERA_AUTORISEE)

        def lancer():
            try:
                faire_cours(le_cours, assistant, classe)
                d.emettre("fin")
            except Exception as e:  # le LLM arrêté, par exemple : le dire à l'écran plutôt que mourir en silence
                print(f"Erreur pendant le cours : {e!r}")
                d.emettre("erreur", texte=f"{type(e).__name__} : {e}")
            finally:
                classe.retirer_consentement()  # l'accord caméra vaut pour une séance, pas plus
        return {"classe": classe, "lancer": lancer}

    try:
        asyncio.run(servir(args, preparer))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
