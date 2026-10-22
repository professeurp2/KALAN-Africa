"""Entrée et sortie vocales locales.

STT : faster-whisper. TTS : Piper. L'audio de l'élève reste en mémoire et n'est
jamais écrit sur disque (protection des mineurs, §10).
"""
from __future__ import annotations

import numpy as np

from . import config


def record_push_to_talk() -> np.ndarray:
    """Appuyer sur Entrée pour parler, Entrée pour arrêter (R1 : pas d'écoute permanente)."""
    import sounddevice as sd

    frames: list[np.ndarray] = []
    input("🎤 Appuie sur Entrée puis pose ta question…")
    with sd.InputStream(samplerate=config.SAMPLE_RATE_IN, channels=1, dtype="float32",
                        callback=lambda data, *_: frames.append(data.copy())):
        input("   … parle, puis Entrée pour terminer.")
    return np.concatenate(frames).ravel() if frames else np.zeros(0, dtype=np.float32)


class Transcriber:
    def __init__(self, model: str = config.WHISPER_MODEL):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model, device="cpu", compute_type="int8",
                                  download_root=str(config.MODELS_DIR / "whisper"))

    def __call__(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(audio, language="fr", vad_filter=True, beam_size=1)
        return " ".join(s.text.strip() for s in segments).strip()


class Speaker:
    def __init__(self, voice: str = config.PIPER_VOICE):
        from piper import PiperVoice

        self.voice = PiperVoice.load(str(config.MODELS_DIR / "piper" / f"{voice}.onnx"))
        self.rate = self.voice.config.sample_rate

    def synth(self, text: str) -> np.ndarray:
        pcm = b"".join(chunk.audio_int16_bytes for chunk in self.voice.synthesize(text))
        return np.frombuffer(pcm, dtype=np.int16)

    def say(self, text: str):
        import sounddevice as sd

        sd.play(self.synth(text), self.rate)
        sd.wait()
