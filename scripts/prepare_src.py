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
    # P18 : outils internet TOUJOURS exposés quand la recherche web est active.
    # Les filtres amont (capacités modèle, builtinTools, toggle `features` de la
    # requête) valent souvent « false » explicite pour les API tierces ou quand le
    # globe n'est pas actionné — ils ne doivent pas masquer search_web/fetch_url
    # (moteur embarqué embedded-searxng) : c'est au modèle de décider de les appeler.
    if config.get('web.search.enable') and await has_user_permission('web_search'):
        builtin_functions.extend([search_web, fetch_url])"""


def patch_web_tools() -> None:
    """P18 — outils internet (search_web/fetch_url) exposés sans condition de modèle."""
    replace_once(DST / "utils" / "tools.py", WEB_TOOLS_OLD, WEB_TOOLS_NEW,
                 "P18 tools.py outils web forcés")


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


SEARXNG_VERSION_FROZEN = '''\
"""searx.version_frozen — généré par prepare_src.py (build sans git : Android).

searx/version.py exécute `git show` au démarrage ; sans binaire git, l'import
échoue (FileNotFoundError) et le thread SearXNG meurt. Ce module figé est le
mécanisme amont qui court-circuite les appels git.
"""
VERSION_STRING = "1.0.0+a30b2d4"
VERSION_TAG = "1.0.0+a30b2d4"
DOCKER_TAG = "1.0.0-a30b2d4"
GIT_URL = "https://github.com/searxng/searxng"
GIT_BRANCH = "a30b2d47492ab46ae82ce25ee62a31626565cf67"
'''


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
    write_searxng_version_frozen()


def write_searxng_version_frozen() -> None:
    """P24 — searx/version.py appelle `git` au démarrage (absent d'Android :
    FileNotFoundError → le thread SearXNG meurt). Le module `version_frozen`
    est le mécanisme amont prévu pour les builds sans git."""
    (SRC / "searx" / "version_frozen.py").write_text(SEARXNG_VERSION_FROZEN, encoding="utf-8")
    log("  searx/version_frozen.py écrit")
    PATCHES.append(("searx version_frozen (sans git)", "écrit"))


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

        from open_webui.models.files import FileForm, Files
        from open_webui.storage.provider import Storage

        user = __user__ or {}

        def _read_and_compile() -> bytes:
            # typst.compile : une chaîne (str) est interprétée comme un CHEMIN de
            # fichier (→ « os error 2 » si absent) ; le code source doit passer en
            # OCTETS, et un fichier doit passer par son vrai chemin (contexte des
            # #include et images relatifs).
            if source:
                return typst_lib.compile(source.encode("utf-8"))
            if not file_path:
                raise ValueError("Fournir 'source' (texte Typst) ou 'file_path' (fichier .typ).")
            local = Storage.get_file(file_path)
            return typst_lib.compile(local)

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
        await Files.insert_new_file(
            user.get("id", ""),
            FileForm(
                id=file_id,
                filename=filename,
                path=stored_path,
                data={},
                meta={"name": f"{base}.pdf", "content_type": "application/pdf", "size": len(pdf_bytes)},
            ),
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


def patch_recurrence_thread() -> None:
    """P21 — anyio.to_process (sous-processus) est impossible sur Android :
    les calculs de récurrence passent en thread local."""
    replace_once(
        DST / "utils" / "recurrence.py",
        "            return await to_process.run_sync(_next_occurrences, s, now, n, cancellable=True)",
        "            # P21 : to_process (sous-processus) interdit sur Android — thread local.\n"
        "            return await to_thread.run_sync(_next_occurrences, s, now, n)",
        "P21 recurrence to_thread",
    )


def patch_search_error_log() -> None:
    """P22 — l'échec de recherche web inclut la fin du journal SearXNG
    (diagnostic du démarrage de l'instance embarquée)."""
    replace_once(
        DST / "tools" / "builtin.py",
        "    except Exception as e:\n"
        "        log.exception(f'search_web error: {e}')\n"
        "        return JSONCodec.dumps({'error': str(e)})",
        "    except Exception as e:\n"
        "        log.exception(f'search_web error: {e}')\n"
        "        detail = str(e)\n"
        "        try:\n"
        "            import os as _os\n"
        "            from open_webui.config import DATA_DIR as _DD\n"
        "            _lp = _os.path.join(str(_DD), 'searxng.log')\n"
        "            if _os.path.exists(_lp):\n"
        "                with open(_lp, encoding='utf-8', errors='replace') as _f:\n"
        "                    detail += '\\n--- journal SearXNG ---\\n' + _f.read()[-600:]\n"
        "        except Exception:\n"
        "            pass\n"
        "        return JSONCodec.dumps({'error': detail})",
        "P22 search_web journal searxng",
    )


def patch_searx_git_oserror() -> None:
    """P24b — garde-fou : si version_frozen est absent, les appels `git` doivent
    dégrader proprement (OSError) au lieu de tuer l'import de SearXNG."""
    for label, err in (
        ("version", "Error while getting the version: %s"),
        ("URL", "Error while getting the git URL & branch: %s"),
    ):
        replace_once(
            SRC / "searx" / "version.py",
            f'    except subprocess.CalledProcessError as ex:\n        logger.error("{err}", ex.stderr)',
            f'    except (subprocess.CalledProcessError, OSError) as ex:\n'
            f'        logger.error("{err}", getattr(ex, "stderr", ex))',
            f"P24b searx version.py OSError ({label})",
        )


FM_CODE = '''
import html as _html
import traceback as _tb
from datetime import datetime as _dt
from urllib.parse import quote as _quote

from fastapi.responses import HTMLResponse as _HTMLResponse, RedirectResponse as _Redirect

_FM_STYLE = """
  body { font-family: system-ui, sans-serif; margin: 0; background: #171717; color: #e7e7e7; }
  a { color: #7db7ff; text-decoration: none; }
  .wrap { display: flex; min-height: 100vh; }
  .side { width: 180px; padding: 14px 10px; background: #1f1f1f; }
  .side a { display: block; padding: 8px 10px; border-radius: 8px; margin-bottom: 4px; color: #ddd; }
  .side a.on { background: #3b82f6; color: #fff; }
  .main { flex: 1; padding: 16px; min-width: 0; }
  h1 { font-size: 1.15rem; margin: 0 0 12px; }
  .bar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  input[type=search] { background: #262626; border: 1px solid #444; color: #eee; padding: 8px 10px; border-radius: 8px; min-width: 200px; }
  button, .btn { background: #3b82f6; color: #fff; border: 0; padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: .85rem; }
  .del { background: #b91c1c; }
  table { width: 100%; border-collapse: collapse; font-size: .88rem; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid #2e2e2e; }
  th { color: #9a9a9a; font-weight: 600; }
  .ico { font-size: 1.2rem; }
  .nav { margin: 14px 0; display: flex; gap: 14px; }
  .empty { color: #999; padding: 30px 0; }
  .err { background: #3b1111; border: 1px solid #7f1d1d; padding: 12px; border-radius: 8px; white-space: pre-wrap; }
"""


def _fm_page(inner: str, title: str = "Fichiers") -> str:
    back = (
        "<a href=\\"/\\" title=\\"Retour \\u00e0 Open WebUI\\" "
        "style=\\"position:fixed;right:12px;top:12px;z-index:10;background:#3b82f6;color:#fff;"
        "padding:10px 16px;border-radius:24px;text-decoration:none;font-weight:600;"
        "box-shadow:0 2px 8px rgba(0,0,0,.4)\\">\\u2190 Open WebUI</a>"
    )
    return (
        "<!doctype html><html lang=\\"fr\\"><head><meta charset=\\"utf-8\\">"
        "<meta name=\\"viewport\\" content=\\"width=device-width, initial-scale=1\\">"
        f"<title>{_html.escape(title)}</title><style>{_FM_STYLE}</style></head>"
        f"<body>{back}{inner}</body></html>"
    )


def _fm_get(meta, key):
    """meta est un dict OU un objet FileMeta (reponse API) selon les chemins."""
    if isinstance(meta, dict):
        return meta.get(key)
    return getattr(meta, key, None)


def _fm_kind(name: str, ctype: str) -> str:
    n = (name or "").lower()
    c = (ctype or "").lower()
    if c == "application/pdf" or n.endswith(".pdf"):
        return "pdf"
    if c.startswith("image/") or n.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return "img"
    if c.startswith("text/") or n.endswith((".txt", ".md", ".csv", ".docx", ".xlsx", ".pptx", ".json", ".yaml", ".yml", ".typ")):
        return "doc"
    return "other"


_FM_ICO = {"pdf": "\\U0001f4c4", "img": "\\U0001f5bc", "doc": "\\U0001f4c3", "other": "\\U0001f4e6"}


def _fm_size(n) -> str:
    """Taille lisible en français : « 1,9 Mo » ; « — » si inconnue."""
    try:
        if n is None:
            return "\\u2014"
        n = float(n)
    except Exception:
        return "\\u2014"
    if n >= 1 << 30:
        return f"{n / (1 << 30):.1f}".replace(".", ",") + " Go"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.1f}".replace(".", ",") + " Mo"
    if n >= 1000:
        return f"{n / 1000:.1f}".replace(".", ",") + " Ko"
    return f"{int(n)} o"


def _fm_real_size(f, meta) -> object:
    """Taille reelle du fichier sur disque, sinon celle du metadonnees."""
    try:
        import os as _os

        from open_webui.storage.provider import Storage

        return _os.path.getsize(Storage.get_file(f.path))
    except Exception:
        return _fm_get(meta, "size")


def _fm_row(f) -> str:
    meta = f.meta or {}
    name = str(_fm_get(meta, "name") or f.filename or f.id)
    size = _fm_size(_fm_real_size(f, meta))
    ctype = str(_fm_get(meta, "content_type") or "")

    def _fmt(ts) -> str:
        try:
            if isinstance(ts, _dt):
                return ts.strftime("%Y-%m-%d %H:%M")
            if isinstance(ts, (int, float)):
                return _dt.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            return str(ts or "")
        except Exception:
            return ""

    when = _fmt(f.updated_at) or _fmt(f.created_at)
    kind = _fm_kind(name, ctype)
    return (
        f"<tr><td class=\\"ico\\">{_FM_ICO[kind]}</td>"
        f"<td><a href=\\"/fm/preview?id={f.id}\\">{_html.escape(name)}</a></td>"
        f"<td>{size}</td><td>{when}</td><td>{_html.escape(ctype)}</td><td>"
        f"<a class=\\"btn\\" href=\\"/api/v1/files/{f.id}/content\\" download>T\\u00e9l\\u00e9charger</a> "
        f"<a class=\\"btn\\" href=\\"/fm/preview?id={f.id}\\">Voir</a> "
        f"<form style=\\"display:inline\\" method=\\"post\\" action=\\"/fm/delete\\" "
        f"onsubmit=\\"return confirm('Supprimer ce fichier ?')\\">"
        f"<input type=\\"hidden\\" name=\\"id\\" value=\\"{f.id}\\">"
        f"<button class=\\"del\\">Suppr.</button></form></td></tr>"
    )


def _fm_error(exc: Exception) -> str:
    return _fm_page(
        "<h1>Erreur du gestionnaire de fichiers</h1><div class=\\"err\\">"
        + _html.escape("".join(_tb.format_exception(exc)))
        + "</div><div class=\\"nav\\"><a href=\\"/fm\\">\\u2190 r\\u00e9essayer</a>"
        " \\u00b7 <a href=\\"/\\">\\u2190 assistant</a></div>"
    )


@app.get('/fm')
async def fm_browser(request: Request, user=Depends(get_verified_user)):
    """P27 — navigateur de fichiers (dossiers par type, recherche, actions)."""
    try:
        from open_webui.models.files import Files

        q = (request.query_params.get('q') or '').strip().lower()
        folder = request.query_params.get('folder') or 'all'
        page = max(1, int(request.query_params.get('page') or 1))
        per_page = 50
        uid = None if user.role == 'admin' else user.id
        result = await Files.get_file_list(user_id=uid, skip=0, limit=10000)
        items = []
        for f in result.items:
            meta = f.meta or {}
            name = str(_fm_get(meta, 'name') or f.filename or f.id)
            if folder != 'all' and _fm_kind(name, str(_fm_get(meta, 'content_type') or '')) != folder:
                continue
            if q and q not in name.lower():
                continue
            items.append(f)
        def _key(f):
            v = f.updated_at or f.created_at or 0
            try:
                return v.timestamp() if isinstance(v, _dt) else float(v)
            except Exception:
                return 0.0

        items.sort(key=_key, reverse=True)
        total = len(items)
        page_items = items[(page - 1) * per_page: page * per_page]
        body = "".join(_fm_row(f) for f in page_items) or "<tr><td colspan=\\"6\\" class=\\"empty\\">Aucun fichier ici pour le moment.</td></tr>"
        tabs = [("all", "\\U0001f4c1 Tous"), ("pdf", "\\U0001f4c4 PDF"), ("img", "\\U0001f5bc Images"),
                ("doc", "\\U0001f4c3 Documents"), ("other", "\\U0001f4e6 Autres")]
        side = "".join(
            f"<a href=\\"/fm?folder={k}&q={_quote(q)}\\" class=\\"{'on' if k == folder else ''}\\">{label}</a>"
            for k, label in tabs
        )
        prev_link = f"<a href=\\"/fm?folder={folder}&q={_quote(q)}&page={page-1}\\">\\u2190 pr\\u00e9c\\u00e9dent</a>" if page > 1 else ""
        next_link = f"<a href=\\"/fm?folder={folder}&q={_quote(q)}&page={page+1}\\">suivant \\u2192</a>" if page * per_page < total else ""
        inner = (
            "<div class=\\"wrap\\"><div class=\\"side\\">" + side + "</div><div class=\\"main\\">"
            "<h1>Navigateur de fichiers</h1>"
            f"<div class=\\"bar\\"><form method=\\"get\\" action=\\"/fm\\">"
            f"<input type=\\"hidden\\" name=\\"folder\\" value=\\"{folder}\\">"
            f"<input type=\\"search\\" name=\\"q\\" value=\\"{_html.escape(q)}\\" placeholder=\\"Rechercher un fichier\\">"
            "<button>Chercher</button></form>"
            "<a class=\\"btn\\" href=\\"/\\">\\u2190 assistant</a></div>"
            f"<table><thead><tr><th></th><th>Nom ({total})</th><th>Taille</th><th>Modifi\\u00e9</th>"
            f"<th>Type</th><th>Actions</th></tr></thead><tbody>{body}</tbody></table>"
            f"<div class=\\"nav\\">{prev_link}{next_link}</div>"
            "</div></div>"
        )
        return _HTMLResponse(_fm_page(inner))
    except Exception as exc:
        return _HTMLResponse(_fm_error(exc), status_code=500)


@app.get('/fm/preview')
async def fm_preview(request: Request, user=Depends(get_verified_user)):
    """Apercu d'un fichier (image, PDF, texte) + telechargement."""
    try:
        from open_webui.models.files import Files

        f = await Files.get_file_by_id(request.query_params.get('id') or '')
        if f is None:
            return _HTMLResponse(_fm_page("<h1>Fichier introuvable</h1><a href=\\"/fm\\">\\u2190 retour</a>"), status_code=404)
        if user.role != 'admin' and f.user_id != user.id:
            return _HTMLResponse(_fm_page("<h1>Acc\\u00e8s refus\\u00e9</h1><a href=\\"/fm\\">\\u2190 retour</a>"), status_code=403)
        meta = f.meta or {}
        name = str(_fm_get(meta, 'name') or f.filename or f.id)
        kind = _fm_kind(name, str(_fm_get(meta, 'content_type') or ''))
        url = f'/api/v1/files/{f.id}/content'
        if kind == 'img':
            view = f"<img src=\\"{url}\\" style=\\"max-width:100%\\">"
        elif kind == 'pdf':
            view = f"<embed src=\\"{url}\\" type=\\"application/pdf\\" style=\\"width:100%;height:75vh\\">"
        else:
            view = (
                "<pre id=\\"c\\" style=\\"white-space:pre-wrap;background:#101010;padding:12px;"
                "border-radius:8px;max-height:70vh;overflow:auto\\">Chargement\\u2026</pre>"
                f"<script>fetch('{url}').then(r=>r.text()).then(t=>document.getElementById('c').textContent=t)"
                ".catch(e=>document.getElementById('c').textContent='Erreur : '+e);</script>"
            )
        inner = (
            f"<div class=\\"main\\"><h1>{_FM_ICO[kind]} {_html.escape(name)}</h1>"
            f"<div class=\\"bar\\"><a class=\\"btn\\" href=\\"{url}\\" download>T\\u00e9l\\u00e9charger</a>"
            "<a class=\\"btn\\" href=\\"/fm\\">\\u2190 navigateur</a></div>" + view + "</div>"
        )
        return _HTMLResponse(_fm_page(inner, name))
    except Exception as exc:
        return _HTMLResponse(_fm_error(exc), status_code=500)


@app.post('/fm/delete')
async def fm_delete(request: Request, user=Depends(get_verified_user)):
    """Supprime un fichier (proprietaire ou admin) puis revient au navigateur."""
    try:
        from open_webui.models.files import Files

        form = await request.form()
        f = await Files.get_file_by_id(str(form.get('id') or ''))
        if f is not None and (user.role == 'admin' or f.user_id == user.id):
            try:
                from open_webui.storage.provider import Storage
                await Storage.delete_file(f.path)
            except Exception:
                pass
            await Files.delete_file_by_id(f.id)
    except Exception:
        pass
    return _Redirect('/fm', status_code=303)

'''


def patch_files_manager() -> None:
    """P26/P27 — navigateur de fichiers : le Workspace 0.13 n'a aucune section
    « Fichiers ». Routes /fm (dossiers par type, recherche, actions), /fm/preview
    (aperçu) et /fm/delete (suppression) — toute erreur est rendue lisible dans
    la page au lieu d'un « internal error » muet."""
    replace_once(
        DST / "main.py",
        "@app.get('/cache/{path:path}')",
        FM_CODE + "\n@app.get('/cache/{path:path}')",
        "P27 navigateur de fichiers /fm",
    )


def patch_files_button() -> None:
    """P26b — bouton flottant « Fichiers » dans index.html (le menu du Workspace
    n'a aucune entrée Fichiers ; le bouton rend /fm découvrable partout)."""
    btn = (
        '<a href="/fm" title="Fichiers : PDF générés et téléversements" '
        'style="position:fixed;right:12px;bottom:72px;z-index:2147483000;'
        'width:42px;height:42px;border-radius:50%;background:#3b82f6;color:#fff;'
        'display:flex;align-items:center;justify-content:center;font-size:20px;'
        'text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,.4)">&#128206;</a>\n</body>'
    )
    replace_once(
        DST / "frontend" / "index.html",
        "</body>",
        btn,
        "P26b bouton flottant Fichiers (index.html)",
    )


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
        "    # Task management - break down complex work into trackable steps",
        "    # P28 : compile_typst — outil documentaire, TOUJOURS disponible\n"
        "    # (auparavant greffé sur le bloc create_tool/workspace.tools : il\n"
        "    # disparaissait selon les permissions de création d'outils).\n"
        "    builtin_functions.append(compile_typst)\n"
        "\n"
        "    # Task management - break down complex work into trackable steps",
        "P28 registration compile_typst (indépendant)",
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


RE2_SHIM = '''\
"""re2 — shim sur `re` (google-re2 est natif et non fourni sur Android).

API utilisée par open_webui (knowledge_fs) : Options(), compile(pattern,
options=...), error. Les attributs max_mem/log_errors de Options sont acceptés
et ignorés : `re` (backtracking) remplace RE2, suffisant pour la recherche
dans les fichiers de connaissances et les skills.
"""
import re as _re
from re import error, escape, match, search, split, sub, findall, finditer  # noqa: F401


class Options:
    case_sensitive: bool = True
    literal: bool = False
    max_mem: int = 0
    log_errors: bool = True


def compile(pattern, options=None, flags=0):  # noqa: A001
    if options is not None:
        if not getattr(options, "case_sensitive", True):
            flags |= _re.IGNORECASE
        if getattr(options, "literal", False):
            pattern = _re.escape(pattern)
    return _re.compile(pattern, flags)
'''


def write_stubs(with_native_pycrdt: bool) -> None:
    (SRC / "tiktoken.py").write_text(TIKTOKEN_SHIM, encoding="utf-8")
    log("  shim tiktoken.py écrit")
    PATCHES.append(("shim tiktoken", "écrit"))
    (SRC / "re2.py").write_text(RE2_SHIM, encoding="utf-8")
    log("  shim re2.py écrit")
    PATCHES.append(("shim re2", "écrit"))
    if with_native_pycrdt:
        stale = SRC / "pycrdt.py"
        if stale.exists():
            stale.unlink()  # un stub périmé masquerait le module natif
        log("  pycrdt natif : stub retiré (le wheel local fournit le module)")
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

    Supprimé : source maps (debug, ~83 Mo) et wasm (ONNX Runtime Web = ML
    navigateur, inutile ici). P23 : `pyodide/` est CONSERVÉ (61 Mo) — c'est le
    runtime de l'outil execute_code (analyse CSV/Excel/PDF, calculs, graphiques
    dans le navigateur) ; il est restauré contre la règle « pas de calcul
    local » qui ne vise que les embeddings (D15).
    """
    import shutil

    front = DST / "frontend"
    if not front.is_dir():
        return
    freed = 0
    for f in front.rglob("*.map"):
        freed += f.stat().st_size
        f.unlink()
    for name in ("wasm",):
        d = front / name
        if d.is_dir():
            freed += sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            shutil.rmtree(d)
    log(f"  P13 frontend allégé : {freed / 1e6:.0f} Mo retirés (maps, wasm) — pyodide conservé (P23)")
    PATCHES.append(("frontend allégé (maps/wasm, pyodide conservé)", f"-{freed / 1e6:.0f} Mo"))


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
    ap.add_argument("--with-native-pycrdt", action="store_true", default=True,
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
    patch_searx_git_oserror()
    patch_files_manager()
    patch_files_button()
    patch_typst_tool()
    patch_recurrence_thread()
    patch_search_error_log()
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
