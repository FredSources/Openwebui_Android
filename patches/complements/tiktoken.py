"""tiktoken — shim pure-Python (RAG désactivé sur cet appareil).

Le vrai tiktoken (natif Rust) n'est pas fourni sur Android. Comme le RAG est
désactivé, le comptage de tokens n'est utilisé que pour le découpage de
documents : une approximation lui suffit. API couverte : get_encoding,
encoding_for_model, encode/decode.
"""
from __future__ import annotations


class _Encoding:
    def __init__(self, name: str = "shim"):
        self.name = name

    def encode(self, text: str, **kwargs) -> list[int]:
        # approximation : 1 token ≈ 4 caractères, bornée à la longueur réelle
        if not text:
            return []
        return list(range(max(1, min(len(text), (len(text) + 3) // 4))))

    def decode(self, tokens, **kwargs) -> str:
        return "" if not tokens else "\uFFFD" * len(tokens)

    def encode_ordinary(self, text: str) -> list[int]:
        return self.encode(text)


def get_encoding(name: str) -> _Encoding:
    return _Encoding(name)


def encoding_for_model(model: str) -> _Encoding:
    return _Encoding(model)
