# Composants tiers et leurs licences

Relevé du 24 octobre 2026 (versions installées dans `.venv` et copiées dans `web/vendor/`).

## ⚠️ À régler avant toute distribution

| Composant | Licence | Problème |
|---|---|---|
| **piper-tts 1.8.0** (voix de Kalan, importé par `kalan/voice.py`) | **GPL-3.0-or-later** | Un programme qui *importe* une bibliothèque GPL et qui est distribué doit lui-même être distribué sous GPL. Incompatible avec la licence propriétaire de `LICENSE` dès que Kalan est remis à une école. |
| Voix **fr_FR-siwis-medium** (modèle Piper) | Dépend du corpus SIWIS | Licence du corpus à vérifier (mention de l'auteur, usage commercial). |

**Options** (décision du porteur) :
1. **Garder la licence propriétaire** : appeler Piper comme **programme séparé** (le moteur `piper` en ligne de commande de rhasspy, publié sous licence MIT) au lieu de l'importer, ou passer à un moteur de voix sous licence permissive (ex. sherpa-onnx, Apache-2.0, qui sait lire les voix Piper).
2. **Publier Kalan en logiciel libre (GPL-3.0)** : compatible tel quel ; argument fort auprès des bailleurs (« bien public numérique »), mais le code devient réutilisable par d'autres.

Aucune donnée n'est concernée : c'est une question de droit d'auteur, pas de vie privée.

## Bibliothèques Python

| Composant | Version | Licence |
|---|---|---|
| faster-whisper | 1.2.1 | MIT |
| CTranslate2 | 4.8.3 | MIT |
| sentence-transformers | 6.2.0 | Apache-2.0 |
| transformers | 5.20.2 | Apache-2.0 |
| PyTorch (CPU) | 2.14.1 | BSD-3-Clause et licences associées |
| onnxruntime | 1.31.0 | MIT |
| websockets | 17.3 | BSD-3-Clause |
| sounddevice | 0.5.6 | MIT |
| numpy | 2.5.4 | BSD-3-Clause et licences associées |
| pypdf | 6.21.2 | BSD-3-Clause |
| requests | 2.34.2 | Apache-2.0 |

## Modèles

| Modèle | Usage | Licence |
|---|---|---|
| Whisper `small` (OpenAI, via faster-whisper) | Transcription de la voix | MIT |
| paraphrase-multilingual-MiniLM-L12-v2 | Recherche dans le programme | Apache-2.0 |
| Qwen2.5-7B (via Ollama) | LLM du prototype ordinateur | Apache-2.0 |
| Gemma 3n *(cible tablette)* | LLM embarqué | Conditions d'utilisation Gemma (à relire avant déploiement) |

## Écran de classe (`web/vendor/`)

| Composant | Version | Licence | Fichier de licence |
|---|---|---|---|
| @vladmandic/face-api (et TensorFlow.js inclus) | 1.7.15 | MIT | `web/vendor/face-api/LICENSE` |
| @mediapipe/tasks-vision + modèle `gesture_recognizer` | 0.10.21 | Apache-2.0 | `web/vendor/mediapipe/LICENSE` |
