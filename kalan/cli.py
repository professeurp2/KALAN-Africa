"""Prototype en ligne de commande.

    python -m kalan.cli            # questions tapées au clavier
    python -m kalan.cli --voix     # micro → Whisper → réponse → Piper
"""
from __future__ import annotations

import argparse
import os
import time


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--voix", action="store_true", help="entrée micro et sortie vocale")
    p.add_argument("--muet", action="store_true", help="avec --voix : ne pas parler, seulement afficher")
    p.add_argument("--mains-libres", action="store_true",
                   help="avec --voix : écoute dès qu'on parle, sans appuyer sur Entrée (démo, salle calme)")
    args = p.parse_args(argv)

    # R6 : à l'exécution, aucun modèle n'est téléchargé. Lancer scripts/download_models.py une fois avant.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    import requests

    from . import config
    from .assistant import Assistant
    from .index import Index, load_embedder

    index = Index()
    if index.count() == 0:
        raise SystemExit("Index vide : lancer d'abord `python -m kalan.ingest data/programme`.")
    assistant = Assistant(index, load_embedder())

    listen = speaker = None
    if args.voix:
        from .voice import Speaker, Transcriber, record_push_to_talk, record_until_silence

        transcribe = Transcriber(titres=index.titres())
        record = record_until_silence if args.mains_libres else record_push_to_talk
        listen = lambda: transcribe(record())
        speaker = None if args.muet else Speaker()

    print("Kalan prêt. Ctrl+C pour quitter.\n")
    while True:
        try:
            question = listen() if listen else input("❓ ")
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if not question.strip():
            if listen:
                print("🤷 Je n'ai rien entendu. Rapproche-toi du micro et réessaie.\n")
            continue
        if listen:
            print(f"❓ {question}")

        t0 = time.perf_counter()
        try:
            rep = assistant.repondre(question)
        except requests.ConnectionError:
            raise SystemExit(f"Le LLM local ne répond pas sur {config.OLLAMA_URL} : lancer `ollama serve`.")
        print(f"   ({time.perf_counter() - t0:.1f} s)")
        for seg in rep.segments:
            print(f"💬 {seg.texte}" + (f"   [→ pointe : {seg.pointe}]" if seg.pointe else ""))
            if speaker:
                speaker.say(seg.texte)
        if rep.citations:
            print("📖 Source : " + " | ".join(rep.citations))
        print()


if __name__ == "__main__":
    main()
