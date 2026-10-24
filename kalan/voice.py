"""Entrée et sortie vocales locales.

STT : faster-whisper. TTS : Piper. L'audio de l'élève reste en mémoire et n'est
jamais écrit sur disque (protection des mineurs, §10).
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from . import config

# Renvoyé par le micro quand un geste (main levée…) a interrompu Kalan, au lieu d'audio.
GESTE = np.zeros(0, dtype=np.float32)


def record_push_to_talk() -> np.ndarray:
    """Appuyer sur Entrée pour parler, Entrée pour arrêter (R1 : pas d'écoute permanente)."""
    import sounddevice as sd

    frames: list[np.ndarray] = []
    input("🎤 Appuie sur Entrée puis pose ta question…")
    with sd.InputStream(samplerate=config.SAMPLE_RATE_IN, channels=1, dtype="float32",
                        callback=lambda data, *_: frames.append(data.copy())):
        input("   … parle, puis Entrée pour terminer.")
    return np.concatenate(frames).ravel() if frames else np.zeros(0, dtype=np.float32)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2)))


class Micro:
    """Micro ouvert en continu : détecte quand l'élève parle, y compris pendant que Kalan parle.

    Sans annulation d'écho, le micro entend aussi la voix de Kalan. Pendant que
    Kalan parle, on ne coupe donc que si le micro capte nettement plus fort que
    l'écho habituel (FACTEUR_ECHO), mesuré sur les phrases précédentes. Avec un
    casque, il n'y a plus d'écho et l'élève peut couper à voix normale.
    """
    BLOCK_S = 0.05
    PRE_S = 0.3        # garder le début du mot qui a déclenché la détection
    SILENCE_S = 1.2    # fin de la question
    MAX_S = 15.0
    FACTEUR_ECHO = config.FACTEUR_ECHO
    DUREE_COUPURE = 0.25  # voix forte soutenue avant de couper Kalan

    def __init__(self):
        import sounddevice as sd

        self.block = int(config.SAMPLE_RATE_IN * self.BLOCK_S)
        self.stream = sd.InputStream(samplerate=config.SAMPLE_RATE_IN, channels=1,
                                     dtype="float32", blocksize=self.block)
        self.stream.start()
        self.echo: float | None = None
        self.calibrer()

    def _lire(self) -> np.ndarray:
        return self.stream.read(self.block)[0].ravel()

    def _vider(self):
        """Jeter l'audio accumulé pendant que Kalan réfléchissait."""
        n = self.stream.read_available
        if n:
            self.stream.read(n)

    def calibrer(self, duree: float = 0.5):
        self._vider()
        self.bruit = float(np.median([_rms(self._lire()) for _ in range(int(duree / self.BLOCK_S))]))
        self.seuil = max(3 * self.bruit, 0.01)

    def _jusqu_au_silence(self, pre: list[np.ndarray]) -> np.ndarray:
        frames, calme = list(pre), 0.0
        while calme < self.SILENCE_S and len(frames) * self.BLOCK_S < self.MAX_S:
            x = self._lire()
            frames.append(x)
            calme = calme + self.BLOCK_S if _rms(x) < self.seuil else 0.0
        return np.concatenate(frames)

    def ecouter(self, attente: float | None = None, arret: Callable[[], bool] | None = None) -> np.ndarray | None:
        """Attend que l'élève parle (au plus `attente` s, sinon sans limite), puis enregistre jusqu'au silence."""
        self._vider()
        pre: list[np.ndarray] = []
        n = int(self.PRE_S / self.BLOCK_S)
        t = 0.0
        while attente is None or t < attente:
            if arret and arret():
                return GESTE
            x = self._lire()
            t += self.BLOCK_S
            pre = (pre + [x])[-n:]
            if _rms(x) > self.seuil:
                return self._jusqu_au_silence(pre)
        return None

    def jouer(self, pcm: np.ndarray, rate: int, arret: Callable[[], bool] | None = None) -> np.ndarray | None:
        """Joue la voix de Kalan en écoutant. Si l'élève parle par-dessus, coupe et renvoie ce qu'il dit.

        `arret` : interroge un autre signal (un geste vu par la caméra) ; s'il répond vrai,
        Kalan se tait aussitôt et on renvoie GESTE.
        """
        import sounddevice as sd

        self._vider()
        sd.play(pcm, rate)
        # Première phrase : écho encore inconnu, on ne coupe pas.
        seuil = float("inf") if self.echo is None else max(self.seuil, self.FACTEUR_ECHO * self.echo)
        niveaux, pre, fort, t = [], [], 0, 0.0
        n_pre, n_fort = int(self.PRE_S / self.BLOCK_S), int(self.DUREE_COUPURE / self.BLOCK_S)
        while t < len(pcm) / rate + 0.1:
            if arret and arret():
                sd.stop()
                return GESTE
            x = self._lire()
            t += self.BLOCK_S
            r = _rms(x)
            niveaux.append(r)
            pre = (pre + [x])[-n_pre:]
            fort = fort + 1 if r > seuil else 0
            if fort >= n_fort:
                sd.stop()
                return self._jusqu_au_silence(pre)
        sd.wait()
        p90 = float(np.percentile(niveaux, 90))
        self.echo = p90 if self.echo is None else 0.7 * self.echo + 0.3 * p90
        return None


def enveloppe(pcm: np.ndarray, rate: int, pas_s: float = 0.04) -> list[float]:
    """Volume de la voix toutes les 40 ms, entre 0 et 1 : de quoi animer la bouche de l'avatar."""
    n = max(1, int(rate * pas_s))
    x = pcm.astype(np.float32) / 32768
    niveaux = [_rms(x[i:i + n]) for i in range(0, len(x), n)]
    haut = max(niveaux, default=0) or 1
    return [round(min(1.0, v / haut), 2) for v in niveaux]


class ClasseVocale:
    """La classe réelle pour kalan.cours : haut-parleur, micro, Whisper, écran texte.

    Les méthodes annoncer, interrompu, entendu et afficher sont les points
    d'affichage : la page web (kalan.web) les redéfinit.
    """

    def __init__(self, transcrire: "Transcriber", speaker: "Speaker", micro: Micro):
        self.transcrire, self.speaker, self.micro = transcrire, speaker, micro
        self.recent: list[str] = []  # dernières phrases de Kalan, contexte pour Whisper

    def dire(self, seg) -> str | None:
        pcm = self.speaker.synth(seg.texte)
        self.recent = (self.recent + [seg.texte])[-2:]
        self.annoncer(seg, pcm)
        audio = self.micro.jouer(pcm, self.speaker.rate, arret=self.geste_en_attente)
        if audio is not None:
            self.interrompu()
        return self.reagir_geste(pendant_phrase=True) if audio is GESTE else self._texte(audio)

    def ecouter(self, attente: float) -> str | None:
        audio = self.micro.ecouter(attente, arret=self.geste_en_attente)
        return self.reagir_geste(pendant_phrase=False) if audio is GESTE else self._texte(audio)

    def geste_en_attente(self) -> bool:
        """Sans caméra, aucun geste : la page web (kalan.web) redéfinit ceci."""
        return False

    def reagir_geste(self, pendant_phrase: bool) -> str | None:
        return None

    def annoncer(self, seg, pcm: np.ndarray):
        print(f"💬 {seg.texte}" + (f"   [→ pointe : {seg.pointe}]" if seg.pointe else ""))

    def interrompu(self):
        pass

    def entendu(self, texte: str):
        print(f"🙋 {texte}")

    def afficher(self, texte: str):
        print(texte)

    def _texte(self, audio: np.ndarray | None) -> str | None:
        if audio is None:
            return None
        texte = self.transcrire(audio, " ".join(self.recent)).strip()
        if texte:
            self.entendu(texte)
        return texte or None


class Transcriber:
    def __init__(self, model: str = config.WHISPER_MODEL, titres: list[str] | None = None):
        """`titres` : chapitres et leçons indexés, donnés à Whisper comme contexte.

        Le vocabulaire de la leçon améliore nettement la transcription des mots techniques.
        """
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model, device="cpu", compute_type="int8",
                                  download_root=str(config.MODELS_DIR / "whisper"))
        self.prompt = ("Question d'un élève sur sa leçon : " + " ; ".join(titres) + ".") if titres else None

    def __call__(self, audio: np.ndarray, contexte: str = "") -> str:
        """`contexte` : ce que Kalan vient de dire ; l'élève en reprend souvent les mots."""
        prompt = " ".join(p for p in (self.prompt, contexte) if p) or None
        segments, _ = self.model.transcribe(audio, language="fr", vad_filter=True, beam_size=5,
                                            initial_prompt=prompt)
        # Segments que Whisper juge être du silence ou du bruit : on les écarte.
        return " ".join(s.text.strip() for s in segments
                        if not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0)).strip()


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
