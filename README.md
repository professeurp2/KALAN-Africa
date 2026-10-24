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

**Écran de classe** (le mode cours, en image) :

```bash
python -m kalan.web                              # ouvre http://localhost:8765
```

Kalan apparaît sous forme d'avatar qui parle (bouche synchronisée sur la voix, bras qui pointe le
tableau). La diapositive avance toute seule avec le cours, les points s'allument au fil de la parole,
le schéma s'éclaire sur l'élément dont Kalan parle (R7), les sous-titres suivent la voix mot à mot.
Option **caméra** (éteinte par défaut, accord demandé à chaque séance) : **lever la main** coupe
Kalan, qui répond « Oui ? Je t'écoute » ; **pouce levé** = j'ai compris, **pouce baissé** = réexplique.
Kalan voit aussi si l'élève est absent, distrait, en difficulté, fatigué, trop près de l'écran, si
la pièce est trop sombre ou si plusieurs élèves sont là. Tout est calculé dans le navigateur avec des
modèles locaux (face-api, MediaPipe). Aucune image n'est enregistrée ni envoyée, et la page ne peut
techniquement rien charger hors de l'appareil. Un établissement peut interdire la caméra :
`KALAN_CAMERA=0`.

🔒 **Vie privée : [docs/CONFIDENTIALITE.md](docs/CONFIDENTIALITE.md)**, appliquée par le code et
vérifiée par `tests/test_confidentialite.py`.

## Licence

Kalan est un **logiciel libre** : © 2026 Lamine SACKO, publié sous la **licence GNU GPL version 3
ou ultérieure** ([LICENSE](LICENSE)). Vous pouvez l'utiliser, l'étudier, le modifier et le
redistribuer, sous la même licence. Il est fourni **sans aucune garantie**.

Le **nom « Kalan »** est réservé aux versions qui respectent la politique de confidentialité :
[docs/MARQUE.md](docs/MARQUE.md). Composants tiers et leurs licences : [docs/TIERS.md](docs/TIERS.md). Pour ajouter une fonctionnalité : un nouvel évènement dans `kalan/web.py`
et un module dans `web/` (voir `GESTES` dans `web/app.js`).

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
