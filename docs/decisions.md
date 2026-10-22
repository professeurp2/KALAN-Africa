# Décisions techniques

Chaque décision : ce qui est choisi, pourquoi, ce que ça coûte de la changer.

## D1 — Modèle d'embedding verrouillé (22 oct. 2026)

- **Choix :** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, **dimension 384**, vecteurs normalisés, similarité cosinus.
- **Pourquoi :** multilingue (prépare le bambara, §8), petit (~470 Mo, tourne sur CPU), bon en français.
- **Coût du changement :** réindexer tout le programme. L'index enregistre modèle et dimension et **refuse de s'ouvrir** s'ils ne correspondent pas à `kalan/config.py`.

## D2 — Index : SQLite + recherche numpy exhaustive

- **Choix :** un fichier `data/index.sqlite`, vecteurs en BLOB, produit scalaire en numpy.
- **Pourquoi :** un programme scolaire = quelques milliers de passages ; la recherche exhaustive prend quelques millisecondes. Pas d'extension native à compiler pour Android. Un seul fichier → mise à jour par clé USB (R11).
- **À revoir si :** plus de ~100 000 passages.

## D3 — LLM : Ollama sur ordinateur, Gemma 3n sur tablette

- **Prototype (J3–J6) :** `qwen2.5:7b` via Ollama, déjà installé sur la machine de dev. Changeable via `KALAN_LLM`.
- **Cible :** Gemma 3n via MediaPipe/LiteRT sur tablette Android.
- **Contrat stable entre les deux :** le LLM renvoie du JSON `{hors_programme, segments:[{texte, pointe}], sources}`. Le reste du pipeline ne dépend que de ce contrat.
- **À faire :** mesurer `gemma3n` dans Ollama dès que possible pour connaître la qualité réelle du modèle cible.

## D4 — Ancrage et refus (R4, R5)

- Refus **avant** le LLM si le meilleur passage a un score < `MIN_SIMILARITY` (0,45 — à calibrer sur de vraies questions).
- Refus si le LLM déclare `hors_programme`, renvoie un JSON invalide ou aucune phrase.
- **Les citations viennent de l'index**, jamais du texte du LLM : il ne peut citer que des numéros d'extraits qu'on lui a donnés.

## D5 — Pointage synchronisé (R7)

- La réponse est découpée en **segments** (une phrase chacun). Chaque segment peut nommer un élément du schéma (`id` SVG).
- L'affichage met en évidence l'élément pendant que le TTS dit la phrase : la synchronisation se fait par segment, pas par mot.
- Un `pointe` qui n'existe pas dans le manifeste du schéma est ignoré.

## D6 — Vie privée (§10)

- L'audio de l'élève reste en mémoire, jamais écrit sur disque.
- Au lancement, `HF_HUB_OFFLINE=1` : aucun téléchargement silencieux à l'exécution.
