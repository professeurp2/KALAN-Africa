# KALAN

**Assistant pédagogique IA, hors ligne, ancré sur le programme scolaire malien.**

L'IA ne remplace pas le professeur. Elle donne à chaque élève ce que le professeur n'a pas le temps de donner : quelqu'un à qui poser une question bête, dans sa langue, sans honte devant la classe.

## Lancer Kalan : une seule commande

**Windows** : double-cliquer sur `kalan.cmd`, ou dans un terminal ouvert dans le dossier du projet :

```bash
.\kalan
```

**Linux, macOS** :

```bash
./kalan.sh
```

La commande vérifie et prépare tout, puis ouvre l'écran de classe dans le navigateur. La première fois, avec Internet, elle installe Python et les modèles (voix, transcription, recherche ≈ 1 Go ; Gemma 3n ≈ 7 Go s'il manque). Ensuite, **tout fonctionne sans Internet**. Seul prérequis : [Ollama](https://ollama.com) installé ; Kalan le démarre lui-même s'il ne tourne pas.

Options : `kalan --chapitre "Chapitre 3"`, `kalan --port 9000`, `kalan --regenerer` (réécrire le texte du cours).

## Ce que fait Kalan

- **Il fait cours** : un avatar parle (bouche synchronisée sur la voix, bras qui pointe le tableau), la diapositive avance toute seule, les points s'allument au fil de la parole, le schéma s'éclaire sur l'élément dont il parle (R7), les sous-titres suivent la voix mot à mot.
- **On l'interrompt quand on veut**, à la voix : il répond avec le programme et cite sa source, réexplique autrement si on n'a pas compris, se souvient de la séance (« tu as dit quoi tout à l'heure ? »), puis reprend la phrase coupée. « Répète », « continue », « arrête » sont compris. Hors programme : il refuse poliment, sans inventer.
- **Caméra** (facultative, éteinte par défaut, accord demandé à chaque séance) :
  - ✋ **lever la main** coupe Kalan, qui répond « Oui ? Je t'écoute » ; 👍 j'ai compris ; 👎 réexplique ;
  - 📒 **« regarde mon cahier »** : après un compte à rebours, Kalan lit l'exercice avec Gemma 3n et aide l'élève à le résoudre, sans donner la réponse toute faite ;
  - il voit aussi si l'élève est absent, distrait, en difficulté, fatigué, trop près de l'écran, si la pièce est sombre ou s'ils sont plusieurs, et réagit comme un enseignant.

  Tout est analysé sur l'appareil ; aucune image n'est enregistrée ni envoyée. Un établissement peut interdire la caméra : `KALAN_CAMERA=0`.

```
🎤 micro ─► Whisper ─► programme indexé ─► Gemma 3n (Ollama) ─► 🔊 Piper + 📺 avatar, diapositive, schéma
📷 caméra ─► face-api, MediaPipe (dans le navigateur) ─► signaux oui/non, gestes ─┘
```

## 🔒 Vie privée

[docs/CONFIDENTIALITE.md](docs/CONFIDENTIALITE.md) — appliquée par le code et vérifiée par `tests/test_confidentialite.py` : la page ne peut rien charger ni envoyer hors de l'appareil, aucun autre site ne peut se connecter à Kalan, la caméra ne sert qu'avec un accord donné pour la séance, et rien de l'élève n'est écrit sur disque.

## Autres modes (terminal)

```bash
.venv\Scripts\python -m kalan.cli                 # questions tapées au clavier
.venv\Scripts\python -m kalan.cli --voix          # micro : Entrée pour parler, Entrée pour finir
.venv\Scripts\python -m kalan.cli --cours         # le cours, sans écran
```

## Programme et contenus

- Ajouter un chapitre officiel (PDF) : `.venv\Scripts\python -m kalan.ingest manuel_ch3.pdf --chapitre "Chapitre 3 — Le circuit électrique simple" --premiere-page 40`
- Le texte oral de chaque cours est écrit une fois par le LLM et gardé dans `data/cours/*.json` : **un enseignant doit le relire et le corriger** avant la classe.
- ⚠️ Le chapitre de `data/programme/` est un **exemple**, pas un extrait officiel.

## Pour les développeurs

| Dossier | Contenu |
|---|---|
| `kalan/` | Découpage, index, assistant, cours, voix, serveur de l'écran, lanceur |
| `web/` | Écran de classe : avatar, tableau, caméra (`web/vendor/` : bibliothèques tierces locales) |
| `data/` | Programme, schémas pointables, textes de cours |
| `docs/` | Cahier des charges, décisions, confidentialité, licences |
| `tests/` | `pytest` |

Ajouter une fonctionnalité à l'écran : un nouvel évènement dans `kalan/web.py` et un module dans `web/` (voir `GESTES` dans `web/app.js`). Décisions techniques : [docs/decisions.md](docs/decisions.md). Cahier des charges : [docs/cahier_des_charges.md](docs/cahier_des_charges.md).

## Licence

Kalan est un **logiciel libre** : © 2026 Lamine SACKO, sous **licence GNU GPL version 3 ou ultérieure** ([LICENSE](LICENSE)), fourni **sans aucune garantie**. Le **nom « Kalan »** est réservé aux versions qui respectent la politique de confidentialité ([docs/MARQUE.md](docs/MARQUE.md)). Composants tiers : [docs/TIERS.md](docs/TIERS.md).
