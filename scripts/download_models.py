# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lamine SACKO
"""Télécharge une fois, avec réseau, tous les modèles dans models/.

Après ce script, Kalan fonctionne sans aucune connexion (R6).
    python scripts/download_models.py
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kalan import config  # noqa: E402

config.MODELS_DIR.mkdir(parents=True, exist_ok=True)

print("1/3 Embeddings :", config.EMBEDDING_MODEL)
from sentence_transformers import SentenceTransformer  # noqa: E402
SentenceTransformer(config.EMBEDDING_MODEL, cache_folder=str(config.MODELS_DIR / "hf"))

print("2/3 Whisper :", config.WHISPER_MODEL)
from faster_whisper import WhisperModel  # noqa: E402
WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8",
             download_root=str(config.MODELS_DIR / "whisper"))

print("3/3 Voix Piper :", config.PIPER_VOICE)
piper_dir = config.MODELS_DIR / "piper"
piper_dir.mkdir(exist_ok=True)
subprocess.run([sys.executable, "-m", "piper.download_voices", "--download-dir", str(piper_dir),
                config.PIPER_VOICE], check=True)

print(f"\nLLM : vérifier que `ollama list` contient {config.LLM_MODEL} (sinon `ollama pull {config.LLM_MODEL}`).")
print("Modèles prêts dans", config.MODELS_DIR)
