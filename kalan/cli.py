"""Prototype en ligne de commande.

    python -m kalan.cli                        # questions tapées au clavier
    python -m kalan.cli --voix                 # micro → Whisper → réponse → Piper
    python -m kalan.cli --cours                # Kalan fait cours ; on l'interrompt à la voix
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
    p.add_argument("--cours", nargs="?", const="", metavar="CHAPITRE",
                   help="Kalan déroule le chapitre (le premier indexé par défaut) ; l'élève l'interrompt à la voix")
    p.add_argument("--regenerer", action="store_true", help="avec --cours : réécrire le texte du cours")
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

    try:
        if args.cours is not None:
            return cours(args, index, assistant)
        questions(args, index, assistant)
    except requests.ConnectionError:
        raise SystemExit(f"Le LLM local ne répond pas sur {config.OLLAMA_URL} : lancer `ollama serve`.")
    except KeyboardInterrupt:
        print()


def cours(args, index, assistant):
    from .cours import charger, faire_cours
    from .voice import ClasseVocale, Micro, Speaker, Transcriber

    chapitres = list(dict.fromkeys(c.chapitre for c in index.chunks()))
    chapitre = next((c for c in chapitres if args.cours.lower() in c.lower()), None)
    if chapitre is None:
        raise SystemExit("Chapitre introuvable. Chapitres indexés :\n- " + "\n- ".join(chapitres))
    print(f"Préparation du cours : {chapitre}…")
    le_cours = charger(chapitre, index, regenerer=args.regenerer)
    classe = ClasseVocale(Transcriber(titres=index.titres()), Speaker(), Micro())
    print("Kalan fait cours. Parle quand tu veux pour poser une question "
          "(« répète », « continue », « arrête » marchent aussi). Ctrl+C pour quitter.\n")
    faire_cours(le_cours, assistant, classe)


def questions(args, index, assistant):
    listen = speaker = None
    if args.voix:
        from .voice import Micro, Speaker, Transcriber, record_push_to_talk

        transcribe = Transcriber(titres=index.titres())
        if args.mains_libres:
            micro = Micro()

            def record():
                print("🎤 Je t'écoute… pose ta question.")
                return micro.ecouter()
        else:
            record = record_push_to_talk
        listen = lambda: transcribe(record())
        speaker = None if args.muet else Speaker()

    print("Kalan prêt. Ctrl+C pour quitter.\n")
    while True:
        try:
            question = listen() if listen else input("❓ ")
        except EOFError:
            print()
            return
        if not question.strip():
            if listen:
                print("🤷 Je n'ai rien entendu. Rapproche-toi du micro et réessaie.\n")
            continue
        if listen:
            print(f"❓ {question}")

        t0 = time.perf_counter()
        rep = assistant.repondre(question)
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
