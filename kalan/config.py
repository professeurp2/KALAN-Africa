"""Configuration centrale de Kalan.

Les choix verrouillés (voir docs/decisions.md) sont ici. Changer EMBEDDING_MODEL
ou EMBEDDING_DIM impose de réindexer tout le programme : l'index refuse de
s'ouvrir si ces valeurs ne correspondent pas à celles enregistrées à l'indexation.
"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.environ.get("KALAN_MODELS_DIR", ROOT / "models"))
INDEX_PATH = Path(os.environ.get("KALAN_INDEX", ROOT / "data" / "index.sqlite"))

# --- Décision verrouillée (§6 du cahier des charges) ---
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

# --- Découpage du programme ---
CHUNK_WORDS = 120
CHUNK_OVERLAP = 30

# --- Recherche / ancrage (R4, R5) ---
TOP_K = 4
# En dessous de ce score cosinus, on refuse sans même interroger le LLM.
# À calibrer sur de vraies questions d'élèves.
MIN_SIMILARITY = 0.45

# --- LLM local ---
# Prototype ordinateur : Ollama. Cible tablette : Gemma 3n via LiteRT.
OLLAMA_URL = os.environ.get("KALAN_OLLAMA_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.environ.get("KALAN_LLM", "qwen2.5:7b")

# --- Voix ---
WHISPER_MODEL = os.environ.get("KALAN_WHISPER", "small")
PIPER_VOICE = "fr_FR-siwis-medium"
SAMPLE_RATE_IN = 16000

REFUS = "Ce n'est pas dans ton programme. Je préfère ne pas inventer : demande à ton professeur."
