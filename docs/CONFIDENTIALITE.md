# Kalan — Politique de confidentialité

> **Projet de document, version 1 du 24 octobre 2026.** À faire relire par un juriste et, avant tout déploiement, à présenter à l'Autorité de Protection des Données à caractère Personnel (APDP) du Mali.

Kalan est un assistant pédagogique qui fonctionne **entièrement sur l'appareil** (tablette ou ordinateur de l'établissement), **sans connexion Internet**. Ses utilisateurs sont des enfants. Cette politique est donc volontairement plus stricte que ce qu'exige la loi, et chacune de ses règles est **appliquée par le logiciel lui-même et vérifiée par des tests automatiques** (`tests/test_confidentialite.py`). Ce n'est pas seulement une promesse écrite.

---

## 1. Qui est responsable

- **L'établissement scolaire** qui installe Kalan est responsable du traitement : il décide de l'utiliser, de permettre ou non la caméra, et recueille les accords des familles.
- **L'éditeur de Kalan** (Lamine SACKO) **ne reçoit aucune donnée** : Kalan n'envoie rien, à personne, jamais.

## 2. Le principe : rien ne sort, rien ne reste

| Ce que Kalan utilise | Pourquoi | Où | Combien de temps |
|---|---|---|---|
| **La voix de l'élève** (son du micro) | Comprendre sa question | Mémoire vive de l'appareil | Le temps de la transcription (quelques secondes). **Jamais écrite sur disque.** |
| **Le texte de ce que dit l'élève** | Répondre en tenant compte de la séance (« tu as dit quoi tout à l'heure ? ») | Mémoire vive | La durée de la séance. **Effacé à la fin**, jamais écrit sur disque. |
| **Les images de la caméra** *(seulement si activée)* | Voir une main levée, un élève absent, fatigué ou en difficulté | Mémoire vive du navigateur, image par image | Une image est analysée puis oubliée. **Aucune image, aucune vidéo n'est enregistrée ni envoyée.** |
| **Les signaux de la caméra** : présent, regarde l'écran, en difficulté, fatigué, trop près, pièce sombre, plusieurs élèves, et les gestes (main levée, pouce levé, pouce baissé) | Faire réagir Kalan comme un enseignant | Mémoire vive | **3 secondes** : un signal plus ancien est ignoré. Jamais écrits. |
| **Le contenu du cours** (chapitres, textes du cours) | Enseigner | Fichiers de l'appareil | Ce sont des contenus pédagogiques, **pas des données sur l'élève**. |

Kalan **ne demande ni ne connaît** le nom, l'âge, la classe ou l'identité de l'élève.

## 3. Ce que Kalan ne fait jamais

1. **Envoyer quoi que ce soit sur Internet.** La page de l'écran est servie avec une politique de sécurité (CSP) qui interdit au navigateur tout chargement ou toute connexion hors de l'appareil.
2. **Enregistrer** la voix, l'image, la vidéo ou le visage de l'élève.
3. **Reconnaître qui est l'élève.** Kalan voit *qu'il y a* un visage, jamais *à qui* il appartient. Aucune empreinte de visage n'est calculée ni conservée.
4. **Noter, classer, comparer, surveiller ou sanctionner** un élève à partir de la caméra.
5. **Faire un rapport** sur un élève, à l'enseignant, à l'établissement, à la famille ou à quiconque.
6. **Garder un historique** d'une séance à l'autre.

## 4. La caméra : des règles plus strictes encore

La caméra est **facultative** et **éteinte par défaut**. Kalan fonctionne exactement de la même façon sans elle.

- **Accord à chaque séance.** Avant d'allumer la caméra, l'écran explique ce qu'elle fait et demande de confirmer que **l'élève est d'accord** et que **sa famille (ou l'établissement, pour elle) a donné son accord**. Cet accord **n'est jamais mémorisé** : il est redemandé à chaque séance.
- **Interdiction par l'établissement.** Avec le réglage `KALAN_CAMERA=0`, la caméra disparaît de l'écran et Kalan ignore tout signal caméra, même s'il en recevait.
- **Signal visible.** Quand la caméra est allumée, l'écran affiche « ● Caméra active » et un bouton **Couper**, utilisable à tout moment.
- **Extinction automatique** à la fin du cours, quand la page est fermée, et pas d'analyse quand l'onglet est caché.
- **Données minimales.** Seuls des signaux oui/non, dans une liste fixe, sont acceptés par Kalan ; tout autre champ (image, nom, émotion détaillée…) est rejeté.
- **Usage limité à ce que ferait un enseignant** qui lève les yeux vers la classe : répondre à une main levée, attendre un élève absent, proposer de réexpliquer, conseiller une pause ou de reculer de l'écran. Une remarque au plus par sujet et par leçon.
- **L'expression du visage n'est pas un diagnostic.** « En difficulté » signifie seulement qu'une expression de tristesse, de colère, de peur ou de gêne a duré 3 secondes. Kalan en tire une proposition (« veux-tu que je réexplique ? »), jamais une conclusion sur l'élève.

## 5. Garanties techniques (vérifiées par les tests)

| Garantie | Comment |
|---|---|
| Aucune ressource ni connexion hors de l'appareil | En-têtes `Content-Security-Policy` ; toutes les bibliothèques et modèles sont copiés localement |
| Aucun autre site ne peut se connecter à Kalan | Serveur lié à `127.0.0.1` ; contrôle de l'origine des connexions WebSocket |
| Pas de caméra sans accord | Les signaux d'une page sans accord, ou d'une autre page, sont ignorés |
| Données minimales | Liste fermée de signaux, de type oui/non uniquement |
| Rien n'est écrit sur disque | Le code du serveur, du cours et de la voix n'ouvre aucun fichier en écriture (hors texte du cours) |
| Le micro du navigateur n'est pas utilisé | `Permissions-Policy: microphone=()` ; le son est traité par Kalan, localement |

## 6. Cadre légal

- **Mali :** loi n° 2013-015 du 21 mai 2013 portant protection des données à caractère personnel, sous le contrôle de l'APDP. Les élèves étant mineurs, l'accord des parents ou tuteurs est requis. *Le fait qu'aucune donnée ne soit conservée ni transmise devra être présenté à l'APDP pour confirmer les formalités applicables.*
- **Union européenne (pour information) :** l'AI Act interdit la reconnaissance des émotions dans les établissements d'enseignement (article 5, paragraphe 1, f). Kalan n'est pas déployé dans l'UE ; mais pour un déploiement ou un financement qui y serait soumis, **la fonction d'expression peut être retirée** sans rien changer d'autre.

## 7. Droits des familles

Comme Kalan ne conserve rien, il n'y a aucune donnée à consulter, corriger ou effacer après la séance. Une famille peut à tout moment **refuser la caméra** : l'élève utilise alors Kalan sans elle, sans aucune différence de traitement.

## 8. Contact et modifications

Questions : l'établissement scolaire, ou l'éditeur (Lamine SACKO, Bamako). Toute modification de cette politique sera datée, et **aucune fonction qui l'affaiblirait ne pourra être ajoutée sans modifier d'abord ce document et les tests qui la vérifient.**
