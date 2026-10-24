# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lamine SACKO
"""Lance Kalan en une commande : vérifie et prépare tout, puis ouvre l'écran de classe.

    kalan                     (Windows : kalan.cmd ; Linux, macOS : ./kalan.sh)
    kalan --chapitre "Chapitre 3" --port 9000

Étapes, chacune sautée si elle est déjà faite :
1. modèles locaux (voix, transcription, recherche) — téléchargés une fois, avec Internet ;
2. Ollama — démarré s'il ne tourne pas ;
3. Gemma 3n — téléchargé une fois s'il manque ;
4. index du programme — construit s'il est vide ;
5. écran de classe.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

import requests

from . import config


def etape(texte: str):
    print(f"• {texte}", flush=True)


def modeles_presents() -> bool:
    m = config.MODELS_DIR
    return ((m / "piper" / f"{config.PIPER_VOICE}.onnx").exists()
            and any((m / "whisper").glob("*")) and any((m / "hf").glob("models--*")))


def ollama_repond() -> bool:
    try:
        return requests.get(f"{config.OLLAMA_URL}/api/version", timeout=2).ok
    except requests.RequestException:
        return False


def demarrer_ollama():
    exe = shutil.which("ollama")
    if not exe:
        raise SystemExit("Ollama n'est pas installé : https://ollama.com (une seule fois), puis relancer Kalan.")
    etape("Démarrage d'Ollama…")
    options = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS} if os.name == "nt" else {
        "start_new_session": True}
    subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
    for _ in range(30):
        if ollama_repond():
            return
        time.sleep(1)
    raise SystemExit("Ollama ne démarre pas. Lancer `ollama serve` dans un autre terminal pour voir l'erreur.")


def modele_llm_present() -> bool:
    noms = {m["name"] for m in requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).json().get("models", [])}
    voulu = config.LLM_MODEL
    return voulu in noms or f"{voulu}:latest" in noms


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("Kalan — préparation\n")

    if not modeles_presents():
        etape("Premier lancement : téléchargement des modèles de voix et de recherche (Internet requis, ~1 Go)…")
        subprocess.run([sys.executable, str(config.ROOT / "scripts" / "download_models.py")], check=True)
    else:
        etape("Modèles locaux : présents")

    if not ollama_repond():
        demarrer_ollama()
    etape("Ollama : prêt")

    if not modele_llm_present():
        etape(f"Téléchargement de {config.LLM_MODEL} (une seule fois, Internet requis, plusieurs Go)…")
        subprocess.run(["ollama", "pull", config.LLM_MODEL], check=True)
    etape(f"LLM : {config.LLM_MODEL}")

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from .index import Index
    if Index().count() == 0:
        etape("Indexation du programme…")
        from . import ingest
        ingest.main([str(config.ROOT / "data" / "programme")])
    etape("Programme : indexé")

    print()
    from . import web
    web.main(argv)


if __name__ == "__main__":
    main()
