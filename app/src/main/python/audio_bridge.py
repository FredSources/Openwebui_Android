"""P130 — pont audio Android (découpage de fichiers audio).

`MainActivity` enregistre ici, au démarrage du serveur, une fonction Java de
découpage (MediaExtractor/MediaMuxer, sans transcodage) :
`register_split(fn)`. Elle est appelée par `split_audio()` (routers/audio)
pour les fichiers de plus de 20 Mo dont le format n'est pas couvert par le
découpage pur Python (WAV et MP3 le sont, cf. `_split_wav_python` /
`_split_mp3_python`). Hors appareil (tests hôte), aucun pont n'est
enregistré : le découpage pur Python suffit et les autres formats lèvent un
message clair.
"""
from __future__ import annotations

from typing import Callable, Optional

_SPLIT: Optional[Callable[[str], str]] = None


def register_split(fn: Callable[[str], str]) -> None:
    """Enregistre la fonction Java de découpage (appelée avec un JSON)."""
    global _SPLIT
    _SPLIT = fn


def get_split() -> Optional[Callable[[str], str]]:
    return _SPLIT
