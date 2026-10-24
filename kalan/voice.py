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


def record_until_silence(silence_s: float = 1.2, max_s: float = 15.0, block_s: float = 0.05) -> np.ndarray:
    """Mains libres : commence quand l'élève parle, s'arrête après `silence_s` de silence.

    Le seuil s'adapte au bruit de la pièce, mesuré pendant une demi-seconde au départ.
    """
    import sounddevice as sd

    block = int(config.SAMPLE_RATE_IN * block_s)
    rms = lambda x: float(np.sqrt(np.mean(x ** 2)))
    with sd.InputStream(samplerate=config.SAMPLE_RATE_IN, channels=1, dtype="float32", blocksize=block) as stream:
        noise = np.median([rms(stream.read(block)[0]) for _ in range(int(0.5 / block_s))])
        seuil = max(3 * noise, 0.01)
        print("🎤 Je t'écoute… pose ta question.")
        pre: list[np.ndarray] = []
        while True:  # attendre la parole, en gardant 0,3 s avant pour ne pas couper le début
            x = stream.read(block)[0].ravel()
            pre = (pre + [x])[-int(0.3 / block_s):]
            if rms(x) > seuil:
                break
        frames, calme = list(pre), 0.0
        while calme < silence_s and len(frames) * block_s < max_s:
            x = stream.read(block)[0].ravel()
            frames.append(x)
            calme = calme + block_s if rms(x) < seuil else 0.0
    return np.concatenate(frames)


class Transcriber:
    def __init__(self, model: str = config.WHISPER_MODEL, titres: list[str] | None = None):
        """`titres` : chapitres et leçons indexés, donnés à Whisper comme contexte.

        Le vocabulaire de la leçon améliore nettement la transcription des mots techniques.
        """
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model, device="cpu", compute_type="int8",
                                  download_root=str(config.MODELS_DIR / "whisper"))
        self.prompt = ("Question d'un élève sur sa leçon : " + " ; ".join(titres) + ".") if titres else None

    def __call__(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(audio, language="fr", vad_filter=True, beam_size=5,
                                            initial_prompt=self.prompt)
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
