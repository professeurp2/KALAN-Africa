"""Écran de classe : Kalan fait cours dans une page web locale.

    python -m kalan.web                 # ouvre http://localhost:8765
    python -m kalan.web --port 9000 --sans-navigateur

La voix, le micro et le cours tournent en Python, comme en ligne de commande. La
page affiche l'avatar qui parle, la diapositive qui avance toute seule, le schéma
pointé et les sous-titres, et peut observer l'élève par la caméra (désactivée par
défaut). Tout est servi en local : aucune ressource Internet n'est chargée.
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
from pathlib import Path

from . import config
from .cours import Observation
from .voice import ClasseVocale, enveloppe

WEB_DIR = config.ROOT / "web"
SCHEMAS_DIR = config.ROOT / "data" / "schemas"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml",
         ".bin": "application/octet-stream", ".png": "image/png"}


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
    """La classe vocale, avec chaque geste de Kalan envoyé à l'écran."""

    def __init__(self, transcrire, speaker, micro, diffusion: Diffusion):
        super().__init__(transcrire, speaker, micro)
        self.d = diffusion
        self.obs, self.obs_t = Observation(), 0.0

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

    def observation(self) -> Observation:
        # Caméra coupée ou page fermée : on fait comme si l'élève était là, attentif.
        return self.obs if time.time() - self.obs_t < 3 else Observation()


def _reponse_fichier(connection, base: Path, rel: str):
    from websockets.datastructures import Headers
    from websockets.http11 import Response

    chemin = (base / rel).resolve()
    if not chemin.is_relative_to(base.resolve()) or not chemin.is_file():
        return connection.respond(404, "Introuvable\n")
    corps = chemin.read_bytes()
    type_ = TYPES.get(chemin.suffix) or mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    return Response(200, "OK", Headers([("Content-Type", type_), ("Content-Length", str(len(corps))),
                                       ("Cache-Control", "no-store")]), corps)


async def servir(args, preparer):
    from websockets.asyncio.server import serve

    loop = asyncio.get_running_loop()
    d = Diffusion(loop)
    seance = await asyncio.to_thread(preparer, d)  # chargement des modèles : quelques secondes
    fil: list[threading.Thread] = []

    def routes(connection, request):
        path = request.path.split("?")[0]
        if path == "/ws":
            return None  # poignée de main WebSocket
        if path == "/":
            return _reponse_fichier(connection, WEB_DIR, "index.html")
        if path.startswith("/web/"):
            return _reponse_fichier(connection, WEB_DIR, path[5:])
        if path.startswith("/schemas/"):
            return _reponse_fichier(connection, SCHEMAS_DIR, path[9:])
        return connection.respond(404, "Introuvable\n")

    async def page(ws):
        d.clients.add(ws)
        try:
            for msg in d.etat.values():
                await ws.send(msg)
            async for brut in ws:
                msg = json.loads(brut)
                if msg.get("type") == "commencer" and not (fil and fil[0].is_alive()):
                    fil[:] = [threading.Thread(target=seance["lancer"], daemon=True)]
                    fil[0].start()
                elif msg.get("type") == "observation":
                    seance["classe"].obs = Observation(bool(msg.get("present", True)),
                                                       bool(msg.get("attentif", True)),
                                                       bool(msg.get("perplexe", False)))
                    seance["classe"].obs_t = time.time()
        finally:
            d.clients.discard(ws)

    async with serve(page, "127.0.0.1", args.port, process_request=routes, max_size=2 ** 20):
        url = f"http://localhost:{args.port}/"
        print(f"\nÉcran de classe prêt : {url}  (Ctrl+C pour quitter)")
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
                  elements=schema.elements if schema else {})

        def lancer():
            try:
                faire_cours(le_cours, assistant, classe)
                d.emettre("fin")
            except Exception as e:  # le LLM arrêté, par exemple : le dire à l'écran plutôt que mourir en silence
                print(f"Erreur pendant le cours : {e!r}")
                d.emettre("erreur", texte=f"{type(e).__name__} : {e}")
        return {"classe": classe, "lancer": lancer}

    try:
        asyncio.run(servir(args, preparer))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
