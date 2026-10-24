# KALAN

**Assistant pédagogique IA, hors ligne, ancré sur le programme scolaire malien.**

L'IA ne remplace pas le professeur. Elle donne à chaque élève ce que le professeur n'a pas le temps de donner : quelqu'un à qui poser une question bête, dans sa langue, sans honte devant la classe.

- Cahier des charges : [docs/cahier_des_charges.md](docs/cahier_des_charges.md)
- Décisions techniques : [docs/decisions.md](docs/decisions.md)

## Prototype ordinateur (J3–J6)

```
🎤 micro ─► Whisper (local) ─► recherche dans le programme ─► LLM local (Ollama)
                                                                   │
                       🔊 Piper (local) ◄── segments + élément à pointer ──► 📺 schéma
```

### Installation (une fois, avec réseau)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_models.py
ollama pull qwen2.5:7b
```

### Utilisation (sans réseau)

```bash
python -m kalan.ingest data/programme --reset   # indexer les chapitres
python -m kalan.cli                              # questions au clavier
python -m kalan.cli --voix                       # micro : Entrée pour parler, Entrée pour finir
python -m kalan.cli --voix --mains-libres        # micro : écoute dès qu'on parle (démo, salle calme)
python -m kalan.cli --cours                      # Kalan fait cours ; on l'interrompt à la voix
```

**Mode cours.** Kalan déroule le chapitre leçon par leçon, en pointant le schéma, et laisse
une courte pause après chaque phrase. L'élève peut parler à tout moment, même pendant que
Kalan parle : Kalan s'arrête, répond (réponse ancrée et citée), dit « On reprend » et redit la
phrase coupée. « Répète », « continue » et « arrête » sont compris.

Le texte oral du cours est écrit une fois par le LLM et gardé dans `data/cours/*.json` :
**un enseignant peut le relire et le corriger** ; `--regenerer` le réécrit. Sans casque, il
faut parler un peu plus fort que Kalan pour le couper (réglage : `KALAN_FACTEUR_ECHO`).

Ollama doit tourner (`ollama serve`).

Ajouter un chapitre officiel en PDF :

```bash
python -m kalan.ingest manuel_ch3.pdf --chapitre "Chapitre 3 — Le circuit électrique simple" --premiere-page 40
```

### Tests

```bash
pytest
```

## Structure

| Dossier | Contenu |
|---|---|
| `kalan/` | Pipeline : découpage, index, assistant, voix, CLI |
| `data/programme/` | Chapitres du programme (Markdown ou PDF). ⚠️ Le chapitre actuel est un **exemple**, pas un extrait officiel |
| `data/schemas/` | Schémas SVG pointables + manifestes JSON (R7) |
| `models/` | Modèles téléchargés (non versionnés) |
| `docs/` | Cahier des charges, décisions |
