# Composants tiers et leurs licences

Relevé du 24 octobre 2026 (versions installées dans `.venv` et copiées dans `web/vendor/`).

Kalan est publié sous **GNU GPL version 3 ou ultérieure** (`LICENSE`). Tous les composants ci-dessous ont une licence **compatible** avec la GPL-3.0 : leur code peut être combiné à celui de Kalan, chacun gardant sa propre licence et ses mentions d'auteur.

## Bibliothèques Python

| Composant | Version | Licence | Compatible GPL-3.0 |
|---|---|---|---|
| piper-tts (voix de Kalan) | 1.8.0 | GPL-3.0-or-later | ✅ même licence |
| faster-whisper | 1.2.1 | MIT | ✅ |
| CTranslate2 | 4.8.3 | MIT | ✅ |
| sentence-transformers | 6.2.0 | Apache-2.0 | ✅ |
| transformers | 5.20.2 | Apache-2.0 | ✅ |
| PyTorch (CPU) | 2.14.1 | BSD-3-Clause et licences associées | ✅ |
| onnxruntime | 1.31.0 | MIT | ✅ |
| websockets | 17.3 | BSD-3-Clause | ✅ |
| sounddevice | 0.5.6 | MIT | ✅ |
| numpy | 2.5.4 | BSD-3-Clause et licences associées | ✅ |
| pypdf | 6.21.2 | BSD-3-Clause | ✅ |
| requests | 2.34.2 | Apache-2.0 | ✅ |

## Écran de classe (`web/vendor/`, livré avec Kalan)

| Composant | Version | Licence | Fichier de licence |
|---|---|---|---|
| @vladmandic/face-api (et TensorFlow.js inclus) | 1.7.15 | MIT | `web/vendor/face-api/LICENSE` |
| @mediapipe/tasks-vision + modèle `gesture_recognizer` | 0.10.21 | Apache-2.0 | `web/vendor/mediapipe/LICENSE` |

## Modèles (téléchargés à l'installation, pas dans le dépôt)

| Modèle | Usage | Licence | Remarque |
|---|---|---|---|
| Whisper `small` (OpenAI, via faster-whisper) | Transcription de la voix | MIT | |
| paraphrase-multilingual-MiniLM-L12-v2 | Recherche dans le programme | Apache-2.0 | |
| Qwen2.5-7B (via Ollama, facultatif : `KALAN_LLM=qwen2.5:7b`) | LLM de remplacement, texte seulement | Apache-2.0 | |
| Voix Piper **fr_FR-siwis-medium** | Voix française | Selon le corpus SIWIS | ⚠️ **À vérifier** avant distribution (mention de l'auteur, usage commercial) |
| **Gemma 3n** (via Ollama ; LiteRT sur tablette) | **LLM par défaut** : cours, réponses, lecture du cahier | Conditions d'utilisation Gemma | ⚠️ Pas une licence libre. Un modèle est un fichier séparé de Kalan, ce qui n'empêche pas la GPL ; mais une tablette livrée avec Gemma doit respecter ses conditions (dont sa politique d'usage interdit). |

## Contenus

| Contenu | Licence |
|---|---|
| Code, page, avatar, schémas, chapitre d'exemple, textes de cours générés | GPL-3.0-or-later (comme Kalan) |
| **Manuels et chapitres officiels du programme malien** | **Ceux de leurs auteurs.** Ils ne sont pas dans le dépôt (`data/programme/*.pdf` est ignoré par git) et ne sont pas couverts par la GPL de Kalan. Droits d'indexation à obtenir (cahier des charges §13.5). |
