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
# Calibré le 24 oct. 2026 sur 12 questions (chapitre d'exemple) : les questions
# hors sujet total tombent sous 0,35 ; les voisines du sujet (0,6) sont refusées par le LLM.
# À recalibrer sur de vraies questions d'élèves et le chapitre officiel.
MIN_SIMILARITY = 0.35

# --- LLM local ---
# Prototype ordinateur : Ollama. Cible tablette : Gemma 3n via LiteRT.
OLLAMA_URL = os.environ.get("KALAN_OLLAMA_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.environ.get("KALAN_LLM", "qwen2.5:7b")

# --- Voix ---
WHISPER_MODEL = os.environ.get("KALAN_WHISPER", "small")
PIPER_VOICE = "fr_FR-siwis-medium"
SAMPLE_RATE_IN = 16000
# Mode cours : pour couper Kalan, l'élève doit parler FACTEUR_ECHO fois plus fort que
# l'écho de Kalan dans le micro. Mesure du 24 oct. 2026 (PC portable, sans casque) :
# écho ≈ 0,027, pas d'auto-interruption à 2,5. Baisser si l'élève n'arrive pas à couper ;
# avec un casque, l'écho disparaît et 1,5 suffit.
FACTEUR_ECHO = float(os.environ.get("KALAN_FACTEUR_ECHO", "2.5"))

REFUS = "Ce n'est pas dans ton programme. Je préfère ne pas inventer : demande à ton professeur."
