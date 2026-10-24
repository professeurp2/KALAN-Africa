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

## D8 — Kalan comprend l'élève en contexte (24 oct. 2026)

- **Constat (premier essai réel du mode cours) :** toutes les interruptions recevaient le même refus. Whisper transcrit mal (« gératère » pour « générateur ») et chaque phrase était traitée comme une question isolée ; « écoute », « reprends », « pas compris » étaient refusés comme hors programme.
- **Choix :** pendant le cours, un seul appel LLM comprend et réagit, avec la **leçon en cours**, la **dernière phrase dite** et les passages proches. Types : `question`, `pas_compris` (réexpliquer autrement), `bavardage`, `hors_programme`, `incompris` (faire répéter). Tri rapide sans LLM pour « répète / continue / arrête » et les hallucinations de Whisper.
- **Whisper** reçoit aussi les deux dernières phrases de Kalan comme contexte, et ignore les segments qu'il juge être du silence.
- **Formules variées** (reprises, refus, « c'est clair ? ») pour éviter l'effet machine.
- **Constat important — relecture enseignante obligatoire :** avec la consigne « plus vivante », le LLM 7B a ajouté dans la leçon 3 des notions absentes du chapitre (électrons, « pas une réalité physique »). Justes en physique, mais hors programme. Corrigé à la main dans `data/cours/`. **Tout cours généré doit être relu par un enseignant avant la classe** ; c'est un argument à mettre en avant auprès du ministère, pas une faiblesse à cacher.

## D9 — Écran de classe et observation par caméra (24 oct. 2026)

- **Écran de classe :** page web servie en local par `kalan/web.py` (WebSocket). Le cours, la voix et le micro restent en Python ; la page reçoit les gestes de Kalan (phrase dite avec l'enveloppe de la voix, élément pointé, nouvelle leçon, parole de l'élève) et les met en scène : avatar, diapositive auto-pilotée, schéma pointé, sous-titres. Architecture par évènements : chaque future fonctionnalité du cahier des charges (révision R9, tableau de bord enseignant R10, simulations R8) est un nouvel évènement et un nouveau module, sans toucher au reste.
- **Hors ligne vérifié :** toutes les requêtes de la page vont vers `localhost` (contrôlé dans le navigateur). face-api et ses modèles (MIT, ~2 Mo) sont copiés dans `web/vendor/`.
- **Caméra — choix prudents, parce qu'il s'agit d'enfants :**
  - désactivée par défaut, activée par un geste explicite ; la page rappelle de demander l'accord de l'élève et de sa famille ;
  - analyse dans le navigateur ; aucune image, aucune émotion n'est enregistrée ni envoyée. Seuls trois signaux lissés sur 3 s partent vers Kalan : présent, regarde l'écran, en difficulté ;
  - usage limité à ce que ferait un enseignant qui lève les yeux : attendre un élève absent, proposer de réexpliquer, une remarque au plus par leçon. **Jamais de note, jamais de profil, jamais de rapport sur l'élève.**
- **Risque à connaître pour la candidature :** la reconnaissance des émotions est **interdite dans l'enseignement** dans l'Union européenne (AI Act, art. 5-1-f, en vigueur depuis février 2025). Le Mali n'y est pas soumis, mais des bailleurs internationaux peuvent y être sensibles. Présenter la fonction comme des « signaux d'attention » facultatifs, et pouvoir la retirer sans rien casser (c'est le cas : sans caméra, Kalan fonctionne à l'identique).
- **Limite technique :** l'expression du visage n'est pas la compréhension. « En difficulté » = expression soutenue de tristesse, colère, peur ou gêne pendant 3 s : un indice, pas un diagnostic.
