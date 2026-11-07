#!/usr/bin/env python3
"""prepare_src.py — Génère src/open_webui à partir de vendor/unpacked/open_webui.

Copie pristine + patchs « sans RAG » et adaptateurs Android (idempotent, rejouable).
Chaque patch est documenté dans PATCHES.md et journal.md.

Usage : tools/python312/bin/python3.12 scripts/prepare_src.py [--with-native-pycrdt]
"""
from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
VENDOR = PROJ / "vendor" / "unpacked" / "open_webui"
SRC = PROJ / "src"
DST = SRC / "open_webui"

PATCHES: list[tuple[str, str]] = []  # (nom, résultat)


def log(msg: str) -> None:
    print(f"[prepare] {msg}")


def replace_once(path: Path, old: str, new: str, name: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        log(f"  {name}: déjà appliqué")
        PATCHES.append((name, "déjà appliqué"))
        return
    if old not in text:
        raise SystemExit(f"PATCH EN ÉCHEC [{name}] : motif introuvable dans {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    log(f"  {name}: appliqué")
    PATCHES.append((name, "appliqué"))


def patch_config() -> None:
    """P1 — VECTOR_DB='local' par défaut : base vectorielle LOCALE (embeddings distants)."""
    replace_once(
        DST / "config.py",
        "VECTOR_DB = os.getenv('VECTOR_DB', 'pgvector' if USE_SLIM else 'chroma')",
        "VECTOR_DB = os.getenv('VECTOR_DB', 'local')  # patch : stockage vectoriel LOCAL (embeddings distants uniquement)",
        "P1 config.py VECTOR_DB=local",
    )


def patch_type() -> None:
    """P2 — Nouveaux types de vector DB : 'none' et 'local'."""
    replace_once(
        DST / "retrieval" / "vector" / "type.py",
        "    OPENGAUSS = 'opengauss'\n    VALKEY = 'valkey'",
        "    OPENGAUSS = 'opengauss'\n    VALKEY = 'valkey'\n    NONE = 'none'\n    LOCAL = 'local'",
        "P2 type.py VectorType.NONE+LOCAL",
    )


def patch_factory() -> None:
    """P3 — factory : 'local' → LocalVectorDB, 'none' → NullVectorDB."""
    replace_once(
        DST / "retrieval" / "vector" / "factory.py",
        '        """\n        get vector db instance by vector type\n        """\n',
        '        """\n        get vector db instance by vector type\n        """\n'
        "        if vector_type in (VectorType.LOCAL, 'local'):\n"
        "            from open_webui.retrieval.vector.dbs.local import LocalVectorDB\n\n"
        "            return LocalVectorDB()\n"
        "        if vector_type in (VectorType.NONE, 'none', '', None):\n"
        "            from open_webui.retrieval.vector.dbs.none import NullVectorDB\n\n"
        "            return NullVectorDB()\n",
        "P3 factory.py cas LOCAL+NONE",
    )


def patch_re2() -> None:
    """P4 — google-re2 indisponible sur Android : repli sur `re`."""
    replace_once(
        DST / "tools" / "knowledge_fs.py",
        "import re2",
        "try:\n    import re2  # google-re2 (natif non dispo sur Android)\n"
        "except ImportError:\n    import re as re2  # repli : sémantique proche, non bornée",
        "P4 knowledge_fs.py repli re2→re",
    )


PATCH_NAME = "P5 audio/__init__.py pydub optionnel"

PYDUB_OLD = """# pydub needs stdlib audioop (gone in 3.13); keep requires-python capped < 3.13
if not USE_SLIM:
    from pydub import AudioSegment
    from pydub.silence import split_on_silence
    from pydub.utils import mediainfo"""

PYDUB_NEW = '''# pydub needs stdlib audioop (gone in 3.13); keep requires-python capped < 3.13
# patch Android : import optionnel — sans pydub, les traitements audio locaux
# (découpage, mediainfo) lèvent une erreur claire ; les API distantes (STT/TTS)
# et la dictée via la WebView restent utilisables.
try:
    from pydub import AudioSegment
    from pydub.silence import split_on_silence
    from pydub.utils import mediainfo
except Exception:

    class _PydubUnavailable:
        _MSG = (
            "pydub indisponible sur cet appareil (audioop absent de Python 3.13+) : "
            "traitement audio local désactivé"
        )

        def __getattr__(self, name):
            raise RuntimeError(self._MSG)

        def __call__(self, *args, **kwargs):
            raise RuntimeError(self._MSG)

    AudioSegment = _PydubUnavailable()
    split_on_silence = _PydubUnavailable()
    mediainfo = _PydubUnavailable()'''


def patch_pydub() -> None:
    """P5 — pydub/audioop absent de Python 3.13 : import optionnel."""
    replace_once(DST / "routers" / "audio" / "__init__.py", PYDUB_OLD, PYDUB_NEW, PATCH_NAME)


def patch_local_ai() -> None:
    """P7 — STT/TTS locaux (faster-whisper/transformers/torch) indisponibles sur
    Android : erreurs 503 explicites au lieu de ModuleNotFoundError."""

    def guard(body: str, msg: str) -> str:
        indented = "\n".join(("    " + ln if ln.strip() else ln) for ln in body.split("\n"))
        return (
            "    try:\n"
            f"{indented}\n"
            "    except ImportError:\n"
            f"        raise HTTPException(503, {msg!r})"
        )

    replace_once(
        DST / "routers" / "audio" / "__init__.py",
        "        from faster_whisper import WhisperModel",
        "        try:\n"
        "            from faster_whisper import WhisperModel\n"
        "        except ImportError:\n"
        "            raise HTTPException(\n"
        "                503,\n"
        "                'STT local (faster-whisper) indisponible sur cet appareil : '\n"
        "                'configurez un moteur STT distant (Réglages → Audio) ou le mode « web ».',\n"
        "            )",
        "P7a audio faster-whisper optionnel",
    )
    replace_once(
        DST / "routers" / "audio" / "__init__.py",
        "    from datasets import load_dataset\n    from transformers import pipeline",
        "    try:\n"
        "        from datasets import load_dataset\n"
        "        from transformers import pipeline\n"
        "    except ImportError:\n"
        "        raise HTTPException(\n"
        "            503,\n"
        "            'TTS local (transformers) indisponible sur cet appareil : '\n"
        "            'configurez un moteur TTS distant (Réglages → Audio).',\n"
        "        )",
        "P7b audio TTS transformers optionnel",
    )
    replace_once(
        DST / "routers" / "audio" / "__init__.py",
        "    import soundfile as sf\n    import torch",
        "    try:\n"
        "        import soundfile as sf\n"
        "        import torch\n"
        "    except ImportError:\n"
        "        raise HTTPException(\n"
        "            503,\n"
        "            'TTS local indisponible sur cet appareil : configurez un TTS distant.',\n"
        "        )",
        "P7c audio soundfile/torch optionnels",
    )


def patch_stt_default() -> None:
    """P8 — moteur STT par défaut « web » (dictée via SpeechRecognition natif)."""
    replace_once(
        DST / "config.py",
        "AUDIO_STT_ENGINE = os.getenv('AUDIO_STT_ENGINE', '')",
        "AUDIO_STT_ENGINE = os.getenv('AUDIO_STT_ENGINE', 'web')  # patch Android : dictée native",
        "P8 config.py AUDIO_STT_ENGINE=web",
    )


WEB_SEARCH_OLD = "            raise Exception('No SEARXNG_QUERY_URL found in environment variables')\n    elif engine == 'openserp':"

WEB_SEARCH_NEW = """            raise Exception('No SEARXNG_QUERY_URL found in environment variables')
    elif engine in ('embedded-searxng', 'embeded-searxng'):
        # SearXNG embarqué dans l'APK (Android) : instance locale, aucun réglage requis
        # (« embeded-searxng » = alias de l'ancienne typo, conservé pour les bases anciennes)
        return await search_searxng(
            'http://127.0.0.1:8888/search?q=<query>',
            query,
            config['web.search.result_count'],
            config['web.search.domain.filter_list'],
            language=config['web.search.searxng_language'],
        )
    elif engine == 'openserp':"""


WEB_TOOLS_OLD = """    # Add web search tools if builtin category enabled AND enabled globally AND model has web_search capability
    if (
        is_builtin_tool_enabled('web_search')
        and config.get('web.search.enable')
        and get_model_capability('web_search')
        and features.get('web_search')
        and await has_user_permission('web_search')
    ):
        builtin_functions.extend([search_web, fetch_url])"""

WEB_TOOLS_NEW = """    # Add web search tools if builtin category enabled AND enabled globally AND model has web_search capability
    # P12 : features.get('web_search') défaut True — un modèle qui ne déclare pas
    # explicitement la capacité dans ses métadonnées doit quand même obtenir les
    # outils internet (search_web = moteur embarqué embedded-searxng, fetch_url).
    if (
        is_builtin_tool_enabled('web_search')
        and config.get('web.search.enable')
        and get_model_capability('web_search')
        and features.get('web_search', True)
        and await has_user_permission('web_search')
    ):
        builtin_functions.extend([search_web, fetch_url])"""


def patch_web_tools() -> None:
    """P12 — outils internet (search_web/fetch_url) exposés par défaut."""
    replace_once(DST / "utils" / "tools.py", WEB_TOOLS_OLD, WEB_TOOLS_NEW,
                 "P12 tools.py outils web par défaut")


def patch_web_search() -> None:
    """P9 — provider « embedded-searxng » (SearXNG local) côté backend."""
    replace_once(DST / "routers" / "retrieval.py", WEB_SEARCH_OLD, WEB_SEARCH_NEW,
                 "P9 retrieval.py provider embedded-searxng")
    # message d'erreur qui révèle le moteur lu (diagnostic des mauvaises configs)
    replace_once(
        DST / "routers" / "retrieval.py",
        "        raise Exception('No search engine API key found in environment variables')",
        "        raise Exception(\n"
        "            f'No search engine API key found in environment variables (moteur configure : {engine!r})'\n"
        "        )",
        "P9b retrieval.py erreur = moteur lu",
    )


def patch_frontend_engines() -> None:
    """P10 — ajout de « embedded-searxng » dans la liste des providers (dropdown)."""
    js = DST / "frontend" / "_app" / "immutable" / "nodes" / "2.DwSK4ZlF.js"
    if not js.exists():
        # le nom du chunk est haché : rechercher le fichier porteur de la liste
        import glob
        candidates = []
        for f in glob.glob(str(DST / "frontend" / "_app" / "immutable" / "**" / "*.js"), recursive=True):
            if 'map' in f:
                continue
            try:
                if 'z=["ollama_cloud","perplexity_search","searxng"' in open(f, encoding='utf-8', errors='replace').read():
                    candidates.append(f)
            except OSError:
                pass
        if len(candidates) != 1:
            raise SystemExit(f"PATCH EN ÉCHEC [P10] : chunk de la liste moteurs introuvable ({candidates})")
        js = type(js)(candidates[0])
    replace_once(
        js,
        'z=["ollama_cloud","perplexity_search","searxng","yacy"',
        'z=["ollama_cloud","perplexity_search","searxng","embedded-searxng","yacy"',
        "P10 frontend liste providers +embedded-searxng",
    )


def copy_searxng() -> None:
    """Embarque SearXNG (vendor figé) dans les sources Python de l'app."""
    import shutil
    src = PROJ / "vendor" / "searxng" / "searx"
    if not src.is_dir():
        raise SystemExit(f"Sources SearXNG introuvables : {src}")
    dst = SRC / "searx"
    if dst.exists():
        shutil.rmtree(dst)
    # on exclut les tests et le .git éventuel
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    log(f"  SearXNG copié : {src} → {dst}")
    PATCHES.append(("SearXNG embarqué", "copié"))


TYPST_TOOL = '''

# ---- Typst -> PDF (outil embarqué, décision D14) ----


async def compile_typst(
    source: str = "",
    file_path: str = "",
    output_name: str = "",
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """Compile un document Typst (.typ) en PDF sauvegardé dans vos fichiers,
    affichable ensuite dans la conversation.

    Typst est un langage de mise en page (proche de LaTeX, plus simple).
    Exemple minimal :
    #set page(margin: 1.5cm)
    = Mon document
    Bonjour *le monde* !

    :param source: texte Typst à compiler (prioritaire sur file_path)
    :param file_path: chemin d'un fichier .typ de vos fichiers
      (ex. files/xxxx_mon_doc.typ) si source est vide
    :param output_name: nom du PDF (sans extension) ; par défaut celui du fichier
    :return: JSON avec l'identifiant du PDF (outil display_file pour l'afficher)
    """
    try:
        import io
        import time
        import uuid as uuidlib

        import typst as typst_lib

        from open_webui.models.files import FileModel, Files
        from open_webui.storage.provider import Storage

        user = __user__ or {}

        def _read_and_compile() -> bytes:
            text = source
            if not text:
                if not file_path:
                    raise ValueError("Fournir 'source' (texte Typst) ou 'file_path' (fichier .typ).")
                local = Storage.get_file(file_path)
                with open(local, encoding="utf-8") as handle:
                    text = handle.read()
            return typst_lib.compile(text)

        pdf_bytes = await asyncio.to_thread(_read_and_compile)

        base = output_name
        if not base:
            base = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0] if file_path else "document"
        base = "".join(c if (c.isalnum() or c in "-_. ") else "_" for c in base).strip()[:80] or "document"

        file_id = str(uuidlib.uuid4())
        filename = f"{file_id}_{base}.pdf"
        tags = {
            "OpenWebUI-User-Id": user.get("id", ""),
            "OpenWebUI-User-Name": user.get("name", ""),
            "OpenWebUI-File-Id": file_id,
        }
        _, stored_path = await asyncio.to_thread(Storage.upload_file, io.BytesIO(pdf_bytes), filename, tags)
        now = int(time.time())
        await Files.insert(
            FileModel(
                id=file_id,
                user_id=user.get("id", ""),
                filename=filename,
                path=stored_path,
                meta={"name": f"{base}.pdf", "content_type": "application/pdf", "size": len(pdf_bytes)},
                created_at=now,
                updated_at=now,
            )
        )
        return JSONCodec.dumps(
            {
                "file_id": file_id,
                "filename": f"{base}.pdf",
                "size": len(pdf_bytes),
                "hint": "PDF généré. Utilisez l'outil display_file avec ce file_id pour l'afficher.",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        log.exception(f"compile_typst error: {exc}")
        return JSONCodec.dumps({"error": str(exc)})
'''


def patch_typst_tool() -> None:
    """P11 — outil « compile_typst » (.typ → PDF) dans les outils embarqués."""
    builtin = DST / "tools" / "builtin.py"
    text = builtin.read_text(encoding="utf-8")
    if "async def compile_typst(" in text:
        log("  P11 compile_typst: déjà appliqué")
    else:
        builtin.write_text(text + TYPST_TOOL, encoding="utf-8")
        log("  P11 compile_typst: ajouté à tools/builtin.py")
        PATCHES.append(("outil compile_typst", "ajouté"))
    replace_once(
        DST / "utils" / "tools.py",
        "    calculate_timestamp,\n    create_automation,",
        "    calculate_timestamp,\n    compile_typst,\n    create_automation,",
        "P11a import compile_typst",
    )
    replace_once(
        DST / "utils" / "tools.py",
        "            builtin_functions.append(create_tool)",
        "            builtin_functions.append(create_tool)\n"
        "            builtin_functions.append(compile_typst)",
        "P11b registration compile_typst",
    )


STORAGE_OLD = """if not USE_SLIM:
    from azure.core.exceptions import ResourceNotFoundError
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient
    from google.cloud import storage
    from google.cloud.exceptions import GoogleCloudError, NotFound"""

STORAGE_NEW = '''# patch Android : SDK de stockage distant optionnels (google-cloud-storage tire
# protobuf/grpcio, natifs absents du dépôt Android). Sans eux, seuls les
# fournisseurs Azure/GCS sont indisponibles ; le stockage local fonctionne.
try:
    if not USE_SLIM:
        from azure.core.exceptions import ResourceNotFoundError
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
        from google.cloud import storage
        from google.cloud.exceptions import GoogleCloudError, NotFound
except Exception:

    class _StorageSdkUnavailable:
        _MSG = (
            "SDK de stockage distant indisponible sur cet appareil : "
            "utiliser STORAGE_PROVIDER=local"
        )

        def __getattr__(self, name):
            raise RuntimeError(self._MSG)

        def __call__(self, *args, **kwargs):
            raise RuntimeError(self._MSG)

    class ResourceNotFoundError(Exception):
        pass

    class GoogleCloudError(Exception):
        pass

    class NotFound(Exception):
        pass

    DefaultAzureCredential = _StorageSdkUnavailable()
    BlobServiceClient = _StorageSdkUnavailable()
    storage = _StorageSdkUnavailable()'''


def patch_storage() -> None:
    """P6 — imports Azure/GCS optionnels (protobuf indisponible sur Android)."""
    replace_once(DST / "storage" / "provider.py", STORAGE_OLD, STORAGE_NEW,
                 "P6 storage/provider.py SDK stockage optionnels")


NULL_VECTOR_DB = '''\
"""NullVectorDB — backend vectoriel « no-RAG » (patch Android).

Le RAG est volontairement désactivé sur cet appareil :
- les insertions/upserts sont ignorés (avec avertissement au log) ;
- les recherches retournent un résultat vide : la conversation continue
  simplement sans contexte issu de documents ;
- aucune dépendance lourde (chromadb, torch, sentence-transformers…).
"""
import logging
from typing import Dict, List, Optional, Union

from open_webui.retrieval.vector.main import (
    GetResult,
    SearchResult,
    VectorDBBase,
    VectorItem,
)

log = logging.getLogger(__name__)


class NullVectorDB(VectorDBBase):
    def has_collection(self, collection_name: str) -> bool:
        return False

    def delete_collection(self, collection_name: str) -> None:
        return None

    def insert(self, collection_name: str, items: List[VectorItem]) -> None:
        log.warning("RAG désactivé : %d vecteur(s) ignoré(s) [%s]", len(items), collection_name)

    def upsert(self, collection_name: str, items: List[VectorItem]) -> None:
        self.insert(collection_name, items)

    def search(
        self,
        collection_name: str,
        vectors: List[List[Union[float, int]]],
        filter: Optional[Dict] = None,
        limit: int = 10,
    ) -> Optional[SearchResult]:
        return SearchResult(ids=[[] for _ in vectors], documents=[[] for _ in vectors],
                            metadatas=[[] for _ in vectors], distances=[[] for _ in vectors])

    def query(self, collection_name: str, filter: Dict, limit: Optional[int] = None) -> Optional[GetResult]:
        return GetResult(ids=[[]], documents=[[]], metadatas=[[]])

    def get(self, collection_name: str) -> Optional[GetResult]:
        return GetResult(ids=[[]], documents=[[]], metadatas=[[]])

    def delete(self, collection_name: str, ids: Optional[List[str]] = None, filter: Optional[Dict] = None) -> None:
        return None

    def reset(self) -> None:
        return None
'''

TIKTOKEN_SHIM = '''\
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
        return "" if not tokens else "\\uFFFD" * len(tokens)

    def encode_ordinary(self, text: str) -> list[int]:
        return self.encode(text)


def get_encoding(name: str) -> _Encoding:
    return _Encoding(name)


def encoding_for_model(model: str) -> _Encoding:
    return _Encoding(model)
'''

PYCRDT_STUB = '''\
"""pycrdt — stub « collab dégradée » (natif non fourni sur Android).

Seule l'API utilisée par open_webui est implémentée : Doc, apply_update,
get_update. Les mises à jour sont accumulées en octets (pas de fusion CRDT
réelle) : l'édition collaborative reste fonctionnelle pour un seul appareil,
mais sans résolution de conflits entre participants distants.
"""


class Doc:
    def __init__(self, *args, **kwargs):
        self._updates: list[bytes] = []

    def apply_update(self, update: bytes, *args, **kwargs) -> None:
        if not isinstance(update, (bytes, bytearray)):
            raise TypeError("pycrdt stub: update doit être des octets")
        self._updates.append(bytes(update))

    def get_update(self, state: bytes | None = None) -> bytes:
        return b"".join(self._updates)

    def get_state(self) -> bytes:
        return b""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<pycrdt.Doc stub, {len(self._updates)} update(s)>"
'''


def write_stubs(with_native_pycrdt: bool) -> None:
    (SRC / "tiktoken.py").write_text(TIKTOKEN_SHIM, encoding="utf-8")
    log("  shim tiktoken.py écrit")
    PATCHES.append(("shim tiktoken", "écrit"))
    if with_native_pycrdt:
        log("  pycrdt natif demandé : pas de stub (le wheel local doit exister)")
    else:
        (SRC / "pycrdt.py").write_text(PYCRDT_STUB, encoding="utf-8")
        log("  stub pycrdt.py écrit")
        PATCHES.append(("stub pycrdt", "écrit"))


def write_null_vector_db() -> None:
    path = DST / "retrieval" / "vector" / "dbs" / "none.py"
    path.write_text(NULL_VECTOR_DB, encoding="utf-8")
    log("  NullVectorDB écrit (retrieval/vector/dbs/none.py)")
    PATCHES.append(("NullVectorDB", "écrit"))


def write_local_vector_db() -> None:
    """Copie le backend vectoriel LOCAL (SQLite + numpy) dans le paquet."""
    import shutil
    src = PROJ / "scripts" / "local_vector_db.py"
    path = DST / "retrieval" / "vector" / "dbs" / "local.py"
    shutil.copyfile(src, path)
    log("  LocalVectorDB écrit (retrieval/vector/dbs/local.py)")
    PATCHES.append(("LocalVectorDB (SQLite+numpy)", "écrit"))


def slim_frontend() -> None:
    """P13 — allège le frontend embarqué (gain de démarrage + taille APK).

    Supprimé : source maps (debug), pyodide (interpréteur Python DANS le
    navigateur), wasm (ONNX Runtime Web = ML navigateur). Ces deux derniers
    contredisent la règle « pas de calcul local » et pèsent ~82 Mo ; les
    source maps sont inutiles en production (~83 Mo).
    """
    import shutil

    front = DST / "frontend"
    if not front.is_dir():
        return
    freed = 0
    for f in front.rglob("*.map"):
        freed += f.stat().st_size
        f.unlink()
    for name in ("pyodide", "wasm"):
        d = front / name
        if d.is_dir():
            freed += sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            shutil.rmtree(d)
    log(f"  P13 frontend allégé : {freed / 1e6:.0f} Mo retirés (maps, pyodide, wasm)")
    PATCHES.append(("frontend allégé (maps/pyodide/wasm)", f"-{freed / 1e6:.0f} Mo"))


def frontend_out_of_python() -> None:
    """P15 — sort le frontend des assets Python (extraction Java unique).

    Les données du paquet `open_webui` (dont `frontend/`, ~85 Mo) sont
    extraites par Chaquopy *au moment de l'import du paquet* — donc pendant
    le démarrage du serveur, à chaque installation/mise à jour. En le
    déplaçant dans les assets Android (`src-assets/frontend/`), c'est
    `MainActivity` qui l'extrait UNE FOIS (versionné) AVANT de lancer Python,
    avec progression affichée. Bonus : les assets sont compressés dans l'APK.
    """
    import shutil

    src = DST / "frontend"
    if not src.is_dir():
        return
    dst = PROJ / "src-assets" / "frontend"
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(exist_ok=True)
    shutil.move(str(src), str(dst))
    log(f"  P15 frontend déplacé vers assets Android : {dst} "
        f"({sum(f.stat().st_size for f in dst.rglob('*') if f.is_file()) / 1e6:.0f} Mo)")
    PATCHES.append(("frontend → assets Android", "déplacé"))


def make_migrations_extractable() -> None:
    """P16 — rend `migrations/` extractible en fichiers réels (.py conservés).

    Chaquopy compile les .py en .pyc et RETIRE les sources de l'APK — mais
    Alembic doit *lire* `migrations/env.py` et `migrations/versions/*.py`
    comme des fichiers texte (load_python_file). Symptôme sur appareil :
    « Erreur au démarrage : … migrations/env.py ». extractPackages (build.gradle)
    ne conserve les .py que pour les PAQUETS : on marque donc les deux
    répertoires comme paquets.
    """
    import os as _os
    for rel in ("migrations", _os.path.join("migrations", "versions")):
        init = DST / rel / "__init__.py"
        if not init.exists():
            init.write_text('"""Paquet marqué pour extractPackages (Alembic lit les sources)."""\n',
                            encoding="utf-8")
    log("  P16 migrations/ marquées paquets (extractPackages conserve les .py)")
    PATCHES.append(("migrations extractibles (Alembic)", "P16"))


def patch_lazy_imports() -> None:
    """P14 — imports coûteux différés (ldap3, black, MCP/boto3 au besoin)."""
    # black : utilisé par un seul endpoint (format_code) → import local
    replace_once(
        DST / "routers" / "utils.py",
        "import black\n",
        "# P14 : black importé en lazy (utilisé par format_code uniquement)\n",
        "P14a black retiré du top-level",
    )
    replace_once(
        DST / "routers" / "utils.py",
        "async def format_code(form_data: CodeForm, user=Depends(get_admin_user)):",
        "async def format_code(form_data: CodeForm, user=Depends(get_admin_user)):\n"
        "    import black  # P14 : import lazy (évité au démarrage)",
        "P14b black importé dans format_code",
    )
    # MCP client (mcp_types/httpx2/jsonschema ~1-2 s) : importé par configs.py
    # mais utilisé dans une seule branche → import local
    replace_once(
        DST / "routers" / "configs.py",
        "from open_webui.utils.mcp.client import MCPClient\n",
        "# P14 : MCPClient importé en lazy (coûteux : mcp/httpx2/jsonschema)\n",
        "P14c MCPClient retiré du top-level",
    )
    replace_once(
        DST / "routers" / "configs.py",
        "                    client = MCPClient()",
        "                    from open_webui.utils.mcp.client import MCPClient  # P14\n"
        "                    client = MCPClient()",
        "P14d MCPClient importé à l'usage",
    )
    # ldap3 (~1,7 s) : uniquement dans extract_group_cn_from_dn / ldap_auth
    replace_once(
        DST / "routers" / "auths.py",
        "from ldap3 import NONE, Connection, Server, Tls\n"
        "from ldap3.utils.conv import escape_filter_chars\n"
        "from ldap3.utils.dn import parse_dn\n",
        "# P14 : ldap3 importé en lazy (authentification LDAP uniquement)\n",
        "P14e ldap3 retiré du top-level",
    )
    replace_once(
        DST / "routers" / "auths.py",
        "    for attr_type, attr_value, _ in parse_dn(group_dn):",
        "    from ldap3.utils.dn import parse_dn  # P14 : import lazy\n"
        "    for attr_type, attr_value, _ in parse_dn(group_dn):",
        "P14f parse_dn importé dans extract_group_cn_from_dn",
    )
    replace_once(
        DST / "routers" / "auths.py",
        "        raise HTTPException(400, detail='LDAP authentication is not enabled')\n",
        "        raise HTTPException(400, detail='LDAP authentication is not enabled')\n"
        "    from ldap3 import NONE, Connection, Server, Tls  # P14 : imports lazy\n"
        "    from ldap3.utils.conv import escape_filter_chars\n",
        "P14g ldap3 importé dans ldap_auth",
    )


def copy_tree() -> None:
    if not VENDOR.is_dir():
        raise SystemExit(f"Sources introuvables : {VENDOR} (lancer d'abord scripts/fetch_src.sh)")
    if DST.exists():
        shutil.rmtree(DST)
    log(f"copie {VENDOR} → {DST}")
    shutil.copytree(VENDOR, DST)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-native-pycrdt", action="store_true",
                    help="ne pas générer le stub pycrdt (wheel natif local attendu)")
    args = ap.parse_args()

    if not (PROJ / "AGENTS.md").exists():
        raise SystemExit("refus de tourner hors racine projet")
    SRC.mkdir(exist_ok=True)
    copy_tree()
    patch_config()
    patch_type()
    patch_factory()
    patch_re2()
    patch_pydub()
    patch_storage()
    patch_local_ai()
    patch_stt_default()
    patch_web_tools()
    patch_web_search()
    patch_frontend_engines()
    copy_searxng()
    patch_typst_tool()
    write_null_vector_db()
    write_local_vector_db()
    slim_frontend()
    frontend_out_of_python()
    make_migrations_extractable()
    patch_lazy_imports()
    write_stubs(args.with_native_pycrdt)
    log(f"terminé : {len(PATCHES)} opération(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
