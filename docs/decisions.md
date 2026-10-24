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

## D7 — Mode cours : Kalan enseigne, l'élève interrompt (24 oct. 2026)

- **Demande du porteur :** se rapprocher d'un enseignant humain. Kalan ne fait pas qu'attendre les questions : il **déroule la leçon**, et l'élève l'interrompt à la voix quand il veut.
- **Texte du cours pré-écrit :** généré une fois par le LLM, leçon par leçon, à partir des seuls passages du programme, puis gardé dans `data/cours/`. Un enseignant peut le relire avant la classe. C'est aussi le pré-calcul prévu contre la lenteur sur tablette (§11) : pendant le cours, le LLM ne sert qu'aux questions.
- **Interruption (barge-in) sans annulation d'écho :** le micro reste ouvert pendant que Kalan parle ; on coupe si le micro capte `FACTEUR_ECHO` (2,5) fois l'écho mesuré sur les phrases précédentes, pendant 0,25 s. Pause de 0,8 s après chaque phrase et de 3 s en fin de leçon pour laisser l'élève parler sans couper.
- **Après une question :** réponse ancrée (même pipeline que le mode questions), « On reprend », puis la phrase coupée est redite en entier.
- **Écart au cahier des charges :** §11 préconisait « appuyer pour parler » en classe bruyante. Le mode cours vise un élève seul ou un petit groupe, idéalement avec un casque. En classe pleine, garder `--voix` (Entrée).
- **Limite connue :** l'écho est mesuré, pas annulé. Une vraie annulation d'écho (AEC Android/WebRTC) sera à brancher sur tablette.
