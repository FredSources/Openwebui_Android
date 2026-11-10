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


ANDROID_TOOLS_HEADER = '''"""OpenWebUI Android — outils et helpers AJOUTÉS (hors amont).

Audit de divergence 2026-11-09 : pour rester au plus proche de l'origine
Open WebUI, tout le code AJOUTÉ par le portage vit dans ce module —
tools/builtin.py se contente de l'importer. Les corrections de COMPORTEMENT
des outils amont, elles, restent greffées dans builtin.py et sont justifiées
une à une dans journal.md.

Contenu : compile_typst (P11), delete_note/delete_skill/delete_tool (P29),
delete_file/list_tools (P58/P59), _probe_fetch_url (P33), _pyodide_packages
(P46), _uploads_pour_sable (P51), SANDBOX_NET_BOOTSTRAP (P52).
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import Request

from open_webui.utils.json_codec import JSONCodec

log = logging.getLogger(__name__)
'''


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

        try:
            import typst as typst_lib
        except Exception as _exc:
            import os as _os
            import sys as _sys
            paquets = []
            for base in list(_sys.path)[:8]:
                try:
                    d = _os.path.join(base, 'typst')
                    if _os.path.isdir(d):
                        paquets.append(d + ' -> ' + str(sorted(_os.listdir(d))[:6]))
                except Exception:
                    pass
            try:
                libre = _os.statvfs(_os.environ.get('HOME', '/')).f_bavail * 4096
            except Exception:
                libre = -1
            raise RuntimeError(
                f"import typst impossible : {_exc} | python={_sys.version.split()[0]} | "
                f"HOM"
                f"E={_os.environ.get('HOME', '')} | libres={libre}o | paquets={paquets}"
            ) from _exc

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


def patch_files_mnt_alias() -> None:
    """P30 — la convention `/mnt/uploads/` (prompt système, Docker) n'existe pas
    sur Android : alias vers le dossier uploads réel + messages orientés."""
    replace_once(
        DST / "storage" / "provider.py",
        '    @staticmethod\n'
        '    def get_file(file_path: str) -> str:\n'
        '        """Handles downloading of the file from local storage."""\n'
        '        return file_path',
        '    @staticmethod\n'
        '    def get_file(file_path: str) -> str:\n'
        '        """Handles downloading of the file from local storage."""\n'
        '        # P30 : convention Docker /mnt/uploads/ → dossier uploads réel\n'
        '        if str(file_path).startswith("/mnt/uploads/"):\n'
        '            file_path = os.path.join(UPLOAD_DIR, os.path.basename(file_path))\n'
        '        return file_path',
        "P30a alias /mnt/uploads (Storage.get_file)",
    )
    replace_once(
        DST / "tools" / "builtin.py",
        "        if '/' not in path:\n"
        "            path = f'/api/v1/files/{path}/content'\n"
        "        parts = path.split('/')\n"
        "        if len(parts) != 6 or parts[:4] != ['', 'api', 'v1', 'files'] or parts[-1] != 'content':\n"
        "            return JSONCodec.dumps(\n"
        "                {'error': 'Use file_id or /api/v1/files/<file_id>/content for an uploaded file.', 'exists': False}\n"
        "            )",
        "        # P30 : fichiers ecrits via la convention /mnt/uploads → uploads reel\n"
        "        import os as _os\n"
        "        from urllib.parse import quote as _q\n"
        "        from open_webui.config import UPLOAD_DIR as _UP\n"
        "        if path.startswith('/mnt/uploads/'):\n"
        "            nom = _os.path.basename(path)\n"
        "            if (_UP / nom).is_file():\n"
        "                return JSONCodec.dumps({\n"
        "                    'type': 'file', 'source': 'open_webui', 'exists': True, 'displayed': True,\n"
        "                    'path': f'/fm/raw?name={_q(nom)}', 'full_path': f'/fm/raw?name={_q(nom)}',\n"
        "                    'name': nom, 'content_type': 'application/octet-stream',\n"
        "                    'mime_type': 'application/octet-stream',\n"
        "                }, ensure_ascii=False)\n"
        "            return JSONCodec.dumps(\n"
        "                {'error': f'Fichier introuvable : {nom} (attendu dans /mnt/uploads)', 'exists': False})\n"
        "        if '/' not in path:\n"
        "            path = f'/api/v1/files/{path}/content'\n"
        "        parts = path.split('/')\n"
        "        if len(parts) != 6 or parts[:4] != ['', 'api', 'v1', 'files'] or parts[-1] != 'content':\n"
        "            return JSONCodec.dumps(\n"
        "                {'error': 'Use file_id or /api/v1/files/<file_id>/content for an uploaded file.', 'exists': False}\n"
        "            )",
        "P30b display_file : alias /mnt/uploads",
    )
    replace_once(
        DST / "tools" / "builtin.py",
        "        file = await Files.get_file_by_id(parts[4])\n"
        "        if not file:\n"
        "            return JSONCodec.dumps({'error': 'File not found', 'exists': False})",
        "        file = await Files.get_file_by_id(parts[4])\n"
        "        if not file:\n"
        "            try:\n"
        "                note = await Notes.get_note_by_id(parts[4])\n"
        "            except Exception:\n"
        "                note = None\n"
        "            if note is not None:\n"
        "                return JSONCodec.dumps({\n"
        "                    'error': \"C'est une note : utilisez view_note (pas display_file).\",\n"
        "                    'exists': False})\n"
        "            return JSONCodec.dumps({'error': 'File not found', 'exists': False})",
        "P30c display_file : orientation vers view_note",
    )


FM_CODE = '''
# P94 : capture des journaux Python (data/logs/serveur.log) dès le démarrage
# du noyau — consultables/téléchargeables depuis /fm → Journaux.
try:
    from open_webui import android_logs as _allog
    _allog.install()
    import os as _osv
    _allog.journal_exec("P101 version=@@VERSION@@ ping_timeout=%s" % _osv.environ.get('WEBSOCKET_SERVER_PING_TIMEOUT', '?'))
except Exception:
    pass

_FM_VERSION = "@@VERSION@@"
import html as _html
import os as _osj
import traceback as _tb
from datetime import datetime as _dt
from urllib.parse import quote as _quote

from fastapi.responses import HTMLResponse as _HTMLResponse, RedirectResponse as _Redirect

_FM_STYLE = """
  :root {
    --font: -apple-system, BlinkMacSystemFont, "Inter", "Vazirmatn", ui-sans-serif, system-ui, "Segoe UI", Roboto, Ubuntu, Cantarell, "Noto Sans", sans-serif;
    --bg: #ffffff; --fg: #000000;
    --side: #f9fafb; --panel: #ffffff;
    --border: #e5e7eb; --muted: #6b7280; --hover: #f3f4f6;
    --accent: #3b82f6; --accent-fg: #ffffff;
    --btn-primary: #000000; --btn-primary-fg: #ffffff;
    --btn2: #f3f4f6; --btn2-fg: #111827;
    --danger: #dc2626;
  }
  html.dark {
    --bg: #171717; --fg: #eeeeee;
    --side: #1f1f1f; --panel: #1f1f1f;
    --border: #2e2e2e; --muted: #9a9a9a; --hover: #262626;
    --btn-primary: #eeeeee; --btn-primary-fg: #171717;
    --btn2: #262626; --btn2-fg: #e7e7e7;
  }
  html.oled-dark { --bg: #000000; --side: #0a0a0a; --panel: #0a0a0a; }
  * { box-sizing: border-box; }
  body { font-family: var(--font); margin: 0; background: var(--bg); color: var(--fg); font-size: 14px; }
  a { color: var(--fg); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .wrap { display: flex; min-height: 100vh; }
  .side { width: 180px; padding: 14px 10px; background: var(--side); border-right: 1px solid var(--border); }
  .side a { display: block; padding: 8px 10px; border-radius: 8px; margin-bottom: 4px; color: var(--fg); opacity: .85; }
  .side a:hover { background: var(--hover); text-decoration: none; }
  .side a.on { background: var(--hover); color: var(--fg); opacity: 1; font-weight: 500; }
  .main { flex: 1; padding: 18px 20px; min-width: 0; }
  h1 { font-size: 1.15rem; margin: 0 0 14px; font-weight: 600; }
  .bar { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }
  input[type=search] { background: var(--panel); border: 1px solid var(--border); color: var(--fg); padding: 8px 12px; border-radius: 10px; min-width: 200px; font: inherit; }
  button, .btn { background: var(--btn-primary); color: var(--btn-primary-fg); border: 0; padding: 8px 14px; border-radius: 8px; cursor: pointer; font-size: .85rem; font-weight: 500; font-family: inherit; }
  button:hover, .btn:hover { opacity: .9; text-decoration: none; }
  .btn2 { background: var(--btn2); color: var(--btn2-fg); }
  .del { background: transparent; color: var(--danger); border: 1px solid var(--danger); }
  .del:hover { background: rgba(220, 38, 38, .12); opacity: 1; }
  td:last-child { white-space: nowrap; }
  td .btn, td button, td form button { padding: 6px 10px; font-size: .8rem; margin: 2px 4px 2px 0; display: inline-block; }
  table { width: 100%; border-collapse: collapse; font-size: .88rem; }
  th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; font-size: .8rem; text-transform: uppercase; letter-spacing: .02em; }
  tr:hover td { background: var(--hover); }
  .ico { font-size: 1.2rem; }
  .nav { margin: 16px 0; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .nav a { padding: 6px 12px; border: 1px solid var(--border); border-radius: 10px; color: var(--fg); background: var(--panel); }
  .nav a:hover { background: var(--hover); text-decoration: none; }
  .empty { color: var(--muted); padding: 30px 0; }
  .err { background: rgba(220, 38, 38, .1); border: 1px solid var(--danger); padding: 12px; border-radius: 10px; white-space: pre-wrap; }
  .ver { position: fixed; left: 10px; bottom: 6px; color: var(--muted); font-size: 10px; opacity: .7; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; vertical-align: middle; }
  .srv { font-size: 13.5px; margin: 0 0 6px; }
  .logbox { background: var(--side); border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; font: 12px/1.5 ui-monospace, "SF Mono", Consolas, monospace; white-space: pre-wrap; word-break: break-word; max-height: 60vh; overflow-y: auto; }
  .err { color: var(--danger); font-weight: 600; }
  .logtable td:nth-child(4), .logtable th:nth-child(4) { display: table-cell; }
  .settings { max-width: 780px; margin: 0 auto; padding-bottom: 60px; }
  .card { border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; margin: 14px 0; background: var(--panel); }
  .card h2 { font-size: .95rem; margin: 0 0 2px; font-weight: 600; }
  .sub { color: var(--muted); font-size: 12.5px; margin: 2px 0 10px; line-height: 1.5; }
  .card label { display: block; font-size: 11.5px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; margin: 12px 0 5px; }
  .card input { width: 100%; padding: 9px 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--bg); color: var(--fg); font-size: 13.5px; }
  .card input:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
  .envbox { width: 100%; min-height: 180px; font-family: ui-monospace, monospace; font-size: 12px; padding: 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--bg); color: var(--fg); resize: vertical; }
  .primary { background: var(--btn-primary); color: var(--btn-primary-fg); }
  .ghost { background: var(--btn2); color: var(--btn2-fg); }
  .danger { background: var(--danger); color: #fff; }
  .ghost:hover, .primary:hover, .danger:hover { opacity: .9; }
  img, iframe, embed, video { max-width: 100%; height: auto; }
  @media (max-width: 820px) {
    .wrap { display: block; }
    .side { width: auto; display: flex; overflow-x: auto; padding: 8px 10px; gap: 4px; border-right: 0; border-bottom: 1px solid var(--border); }
    .side a { white-space: nowrap; margin-bottom: 0; padding: 7px 12px; }
    .main { padding: 12px; }
    h1 { font-size: 1.05rem; }
    table { font-size: .82rem; }
    th:nth-child(4), td:nth-child(4), th:nth-child(5), td:nth-child(5) { display: none; }
    td:last-child { white-space: nowrap; }
    td .btn, td button, td form button { padding: 6px 10px; font-size: .78rem; }
    input[type=search] { min-width: 0; flex: 1 1 140px; }
  }
  @media (max-width: 480px) {
    th:nth-child(3), td:nth-child(3) { display: none; }
    th, td { padding: 8px 4px; }
    button, .btn, .nav a { padding: 10px 14px; font-size: .95rem; }
    .ver { display: none; }
  }
"""


def _fm_page(inner: str, title: str = "Fichiers") -> str:
    # P37 — habillage aligné sur Open WebUI : police Inter, palette claire
    # (#fff/#000), sombre (#171717/#eee) et oled-dark (noir pur) ; le thème est
    # lu dans localStorage["theme"] comme le fait le frontend. Plus de bouton
    # « retour assistant » : la navigation Android/back d'Open WebUI suffit.
    theme_js = (
        '<script>(function(){var t=null;try{t=localStorage.getItem("theme");}catch(e){}'
        'var dark=(t==="dark"||t==="oled-dark")'
        '||(t!=="light"&&window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches);'
        'var c=document.documentElement.classList;'
        'if(dark){c.add("dark");if(t==="oled-dark"){c.add("oled-dark");}}else{c.add("light");}'
        '})();</script>'
    )
    # P40 — FAB retour vers Open WebUI : jumeau du bouton 📂 du SPA (même
    # style, autre icône 💬), présent sur TOUTES les pages /fm.
    retour = (
        '<a href="/" id="fab-fm" title="Retour à Open WebUI — glisser pour déplacer" '
        'style="position:fixed;right:12px;bottom:72px;z-index:2147483000;'
        'width:42px;height:42px;border-radius:50%;background:#3b82f6;color:#fff;'
        'display:flex;align-items:center;justify-content:center;font-size:20px;'
        'text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,.4);cursor:grab;touch-action:none">'
        '&#128172;</a>'
        '<script>(function(){var el=document.getElementById("fab-fm");if(!el)return;'
        'try{var s=JSON.parse(localStorage.getItem("fabPosFm")||"null");'
        'if(s){el.style.left=s.l+"px";el.style.top=s.t+"px";el.style.right="auto";el.style.bottom="auto";}}catch(e){}'
        'var sx,sy,ox,oy,drag=0,moved=0;'
        'el.addEventListener("pointerdown",function(e){drag=1;moved=0;sx=e.clientX;sy=e.clientY;'
        'var r=el.getBoundingClientRect();ox=r.left;oy=r.top;});'
        'el.addEventListener("pointermove",function(e){if(!drag)return;'
        'var dx=e.clientX-sx,dy=e.clientY-sy;if(!moved&&Math.abs(dx)+Math.abs(dy)<6)return;'
        'moved=1;el.style.left=(ox+dx)+"px";el.style.top=(oy+dy)+"px";'
        'el.style.right="auto";el.style.bottom="auto";e.preventDefault();});'
        'el.addEventListener("pointerup",function(){if(!drag)return;drag=0;if(moved){'
        'try{localStorage.setItem("fabPosFm",JSON.stringify({l:parseInt(el.style.left)||0,t:parseInt(el.style.top)||0}));}catch(e){}}});'
        'el.addEventListener("click",function(e){if(moved){e.preventDefault();e.stopPropagation();moved=0;}});'
        '})();</script>'
    )
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{_html.escape(title)}</title>{theme_js}<style>{_FM_STYLE}</style></head>'
        f'<body>{inner}{retour}<footer class="ver">OpenWebUI Android {_FM_VERSION}</footer></body></html>'
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


def _fm_real_size(f, meta):
    """Taille du fichier : maximum des sources disponibles (disque, metadonnees,
    contenu en base) — jamais 0 si une source connait la taille reelle."""
    candidats = []
    try:
        import os as _os

        from open_webui.storage.provider import Storage

        candidats.append((_os.path.getsize(Storage.get_file(getattr(f, "path", None))), "disque"))
    except Exception:
        pass
    try:
        v = _fm_get(meta, "size")
        if v:
            candidats.append((int(v), "meta"))
    except Exception:
        pass
    try:
        contenu = (f.data or {}).get("content")
        if contenu:
            candidats.append((len(contenu), "contenu"))
    except Exception:
        pass
    if not candidats:
        return None
    return max(candidats)[0]


def _fm_chemin_local(nom: str):
    """Fichier du dossier uploads (alias /mnt/uploads) — nom de base uniquement."""
    import os as _os

    from open_webui.config import UPLOAD_DIR as _UP

    nom = _os.path.basename(nom)
    p = _UP / nom
    return p if p.is_file() else None


def _fm_orphelins(deja_references) -> list:
    """Fichiers presents dans le dossier uploads mais absents de la base
    (ecrits par des outils/skills via /mnt/uploads ou Storage direct)."""
    import os as _os

    from open_webui.config import UPLOAD_DIR as _UP

    if not _UP.is_dir():
        return []
    orphelins = []
    for p in _UP.iterdir():
        try:
            if p.is_file() and _os.path.realpath(p) not in deja_references:
                orphelins.append(p)
        except Exception:
            continue
    return sorted(orphelins, key=lambda p: p.stat().st_mtime, reverse=True)


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
        f"<form style=\\"display:inline\\" method=\\"post\\" action=\\"/fm/delete\\" "
        f"onsubmit=\\"return confirm('Supprimer ce fichier ?')\\">"
        f"<input type=\\"hidden\\" name=\\"id\\" value=\\"{f.id}\\">"
        f"<button class=\\"del\\">Suppr.</button></form></td></tr>"
    )


def _fm_error(exc: Exception) -> str:
    return _fm_page(
        "<h1>Erreur du gestionnaire de fichiers</h1><div class=\\"err\\">"
        + _html.escape("".join(_tb.format_exception(exc)))
        + "</div><div class=\\"nav\\"><a href=\\"/fm\\">\\u2190 r\\u00e9essayer</a></div>"
    )


def _journaux_actifs() -> bool:
    """P95 — les journaux sont-ils actifs ? (réglage OWUI_LOGS, défaut on)."""
    return _osj.environ.get('OWUI_LOGS', 'on').strip().lower() not in (
        'off', 'non', '0', 'false', 'desactive', 'aucun')


@app.get('/fm')
async def fm_browser(request: Request, user=Depends(get_verified_user)):
    """P27 — navigateur de fichiers (dossiers par type, recherche, actions)."""
    try:
        from open_webui.models.files import Files

        q = (request.query_params.get('q') or '').strip().lower()
        folder = request.query_params.get('folder') or 'all'
        # P95 : les journaux sont coupables à l'exécution (réglage
        # OWUI_LOGS=off dans les Paramètres, appliqué au redémarrage).
        _journaux_on = _journaux_actifs()
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
        refs = set()
        for f in result.items:
            try:
                import os as _os2
                from open_webui.storage.provider import Storage as _St
                refs.add(_os2.path.realpath(_St.get_file(f.path)))
            except Exception:
                pass
        orph = []
        import re as _re
        for p in _fm_orphelins(refs):
            nom_aff = _re.sub(r'^[0-9a-fA-F-]{36}_', '', p.name)
            if folder != 'all' and _fm_kind(nom_aff, '') != folder:
                continue
            if q and q not in nom_aff.lower():
                continue
            orph.append((p, nom_aff))
        total = len(items) + len(orph)
        page_items = items[(page - 1) * per_page: page * per_page]
        rows_l = [_fm_row(f) for f in page_items]
        for p, nom_aff in orph:
            try:
                st = p.stat()
                taille = _fm_size(st.st_size)
                quand = _dt.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:
                taille, quand = "\\u2014", ""
            kind_o = _fm_kind(nom_aff, '')
            rows_l.append(
                f"<tr><td class=\\"ico\\">{_FM_ICO[kind_o]}</td>"
                f"<td><a href=\\"/fm/raw?name={_quote(p.name)}\\">{_html.escape(nom_aff)}</a></td>"
                f"<td>{taille}</td><td>{quand}</td><td>sur disque</td><td>"
                f"<a class=\\"btn\\" href=\\"/fm/raw?name={_quote(p.name)}\\" download>T\\u00e9l\\u00e9charger</a> "
                f"<form style=\\"display:inline\\" method=\\"post\\" action=\\"/fm/delete-raw\\" "
                f"onsubmit=\\"return confirm('Supprimer ce fichier ?')\\">"
                f"<input type=\\"hidden\\" name=\\"name\\" value=\\"{_html.escape(p.name)}\\">"
                f"<button class=\\"del\\">Suppr.</button></form></td></tr>"
            )
        body = "".join(rows_l) or "<tr><td colspan=\\"6\\" class=\\"empty\\">Aucun fichier ici pour le moment.</td></tr>"
        tabs = [("all", "\\U0001f4c1 Tous"), ("pdf", "\\U0001f4c4 PDF"), ("img", "\\U0001f5bc Images"),
                ("doc", "\\U0001f4c3 Documents"), ("other", "\\U0001f4e6 Autres"),
                ("settings", "\\u2699\\ufe0f Param\\u00e8tres"),
                ("maintenance", "\\U0001f6e0\\ufe0f Maintenance"),
                ("logs", "&#128220; Journaux")]
        if not _journaux_on:
            tabs = [t for t in tabs if t[0] != 'logs']
        side = "".join(
            f"<a href=\\"/fm?folder={k}&q={_quote(q)}\\" class=\\"{'on' if k == folder else ''}\\">{label}</a>"
            for k, label in tabs
        )
        if folder == 'settings':
            import android_main as _am
            brut = _am.env_read()
            vals = {}
            for _l in brut.splitlines():
                _s = _l.strip()
                if _s and not _s.startswith('#') and '=' in _s:
                    _k, _, _v = _s.partition('=')
                    vals[_k.strip()] = _v.strip()
            connus = ('OLLAMA_BASE_URL', 'OPENAI_API_BASE_URL', 'OPENAI_API_KEY',
                      'RAG_EMBEDDING_ENGINE', 'RAG_OPENAI_API_BASE_URL',
                      'RAG_OPENAI_API_KEY', 'RAG_OPENAI_EMBEDDING_MODEL',
                      'WEBUI_AUTH', 'ENABLE_SIGNUP', 'DEFAULT_LOCALE', 'OWUI_LOGS')
            aides = {
                'OLLAMA_BASE_URL': 'ex. http://100.64.0.2:11434',
                'OPENAI_API_BASE_URL': 'ex. https://api.openai.com/v1',
                'OPENAI_API_KEY': 'clé API du modèle',
                'RAG_EMBEDDING_ENGINE': 'openai / ollama / azure',
                'RAG_OPENAI_API_BASE_URL': 'ex. https://api.openai.com/v1',
                'RAG_OPENAI_API_KEY': 'clé API embeddings',
                'RAG_OPENAI_EMBEDDING_MODEL': 'ex. text-embedding-3-small',
                'WEBUI_AUTH': 'true / false',
                'ENABLE_SIGNUP': 'true / false',
                'DEFAULT_LOCALE': 'ex. fr-FR',
                'OWUI_LOGS': 'on / off (journaux)',
            }
            reste = chr(10).join(
                _l for _l in brut.splitlines()
                if not (_l.strip() and not _l.strip().startswith('#') and '=' in _l
                        and _l.partition('=')[0].strip() in connus))

            def _champ(nom):
                type_ = 'password' if 'KEY' in nom else 'text'
                return (
                    '<label>' + nom.replace('_', ' ').lower() + '</label>'
                    '<input type="' + type_ + '" name="VAR_' + nom + '" value="'
                    + _html.escape(vals.get(nom, '')) + '" placeholder="'
                    + _html.escape(aides.get(nom, '')) + '">'
                )

            page = """<div class="bar" style="margin-bottom:16px"><a class="btn" href="/fm">&#8592; Retour au navigateur</a></div>
<p class="srv"><span class="dot" style="background:@@DOT_OW@@"></span> Open WebUI&nbsp;: <b>@@ST_OW@@</b>
<span class="dot" style="background:@@DOT_SX@@;margin-left:24px"></span> SearXNG&nbsp;: <b>@@ST_SX@@</b></p>
<form method="post" action="/fm/settings"><div class="settings">
<h1>&#9881; Paramètres</h1>
<p class="sub">Réglages écrits dans <code>data/openwebui.env</code> — appliqués à chaque démarrage ou redémarrage de l'application.</p>
<div class="card"><h2>&#129302; Modèles (LLM)</h2>
<p class="sub">Connexion à Ollama ou à une API OpenAI-compatible.</p>
@@OLLAMA_BASE_URL@@
@@OPENAI_API_BASE_URL@@
@@OPENAI_API_KEY@@
</div>
<div class="card"><h2>&#128218; Recherche &amp; RAG</h2>
<p class="sub">Embeddings distants pour la recherche dans vos documents.</p>
@@RAG_EMBEDDING_ENGINE@@
@@RAG_OPENAI_API_BASE_URL@@
@@RAG_OPENAI_API_KEY@@
@@RAG_OPENAI_EMBEDDING_MODEL@@
</div>
<div class="card"><h2>&#128274; Sécurité &amp; préférences</h2>
@@WEBUI_AUTH@@
@@ENABLE_SIGNUP@@
@@DEFAULT_LOCALE@@
@@OWUI_LOGS@@
</div>
<div class="card"><h2>&#128295; Variables avancées</h2>
<p class="sub">Toute autre variable, une par ligne au format KEY=VALUE.</p>
<textarea name="extras" spellcheck="false" class="envbox">@@RESTE@@</textarea>
</div>
<div class="card"><h2>&#128220; Journaux</h2>
<p class="sub">Activité du serveur, erreurs <code>execute_code</code> et autres — à consulter ou télécharger pour analyse.</p>
<a class="btn" href="/fm?folder=logs">Consulter les journaux</a>
</div>
<div class="bar" style="margin-top:18px">
<button class="primary">&#128190; Enregistrer les réglages</button>
<button type="button" class="ghost" onclick="svc(&quot;openwebui&quot;,&quot;run&quot;)">&#9654; Open WebUI</button>
<button type="button" class="ghost" onclick="svc(&quot;openwebui&quot;,&quot;stop&quot;)">&#9208; Arrêter</button>
<button type="button" class="ghost" onclick="svc(&quot;searxng&quot;,&quot;run&quot;)">&#9654; SearXNG</button>
<button type="button" class="ghost" onclick="svc(&quot;searxng&quot;,&quot;stop&quot;)">&#9208; Arrêter</button>
<button type="button" class="ghost" onclick="svc(&quot;searxng&quot;,&quot;restart&quot;)">&#8635; SearXNG</button>
<button type="button" class="danger" onclick="AndroidSystem.restartApp()">&#8635; Redémarrer l'application</button>
</div>
</div></form>
<p id="svcmsg" class="sub"></p>
<script>function svc(n,a){try{document.getElementById("svcmsg").textContent=AndroidSystem.serverAction(n,a)}catch(e){document.getElementById("svcmsg").textContent="pont système indisponible : "+e}}</script>"""
            for _nom in connus:
                page = page.replace('@@' + _nom + '@@', _champ(_nom))
            page = page.replace('@@RESTE@@', _html.escape(reste))
            st = _am.service_status()
            page = page.replace('@@ST_OW@@', st.get('openwebui', 'arrêt'))
            page = page.replace('@@ST_SX@@', st.get('searxng', 'arrêt'))
            page = page.replace('@@DOT_OW@@', '#22c55e' if st.get('openwebui') == 'actif' else 'var(--muted)')
            page = page.replace('@@DOT_SX@@', '#22c55e' if st.get('searxng') == 'actif' else 'var(--muted)')
            return _HTMLResponse(_fm_page(page, 'Paramètres'))
        if folder == 'logs':
            if not _journaux_on:
                return _HTMLResponse(_fm_page("<h1>Journaux d&eacute;sactiv&eacute;s</h1><p>La capture est coup&eacute;e &mdash; r&eacute;glage <code>owui logs</code> dans les Param&egrave;tres (appliqu&eacute; au red&eacute;marrage).</p>"))
            from open_webui import android_logs as _al
            sel = (request.query_params.get('log') or '').strip() or 'serveur.log'
            try:
                limite = max(20, min(int(request.query_params.get('n') or 300), 1000))
            except Exception:
                limite = 300
            journaux = _al.fichiers()
            rows_log = "".join(
                "<tr><td>" + _html.escape(f['nom']) + "</td><td>" + _fm_size(f['taille']) + "</td>"
                "<td>" + _html.escape(f['modifie']) + "</td><td style='white-space:nowrap'>"
                "<a class='btn2 btn' href='/fm?folder=logs&log=" + _quote(f['nom']) + "'>Voir</a> "
                "<a class='btn' href='/fm/logs/download?name=" + _quote(f['nom']) + "'>Télécharger</a>"
                "</td></tr>"
                for f in journaux
            ) or "<tr><td colspan='4' class='empty'>Aucun journal pour l'instant.</td></tr>"
            contenu = _al.lecture(sel, limite)
            jl = []
            for _l in (contenu.splitlines() or ["(journal vide)"]):
                _e = _html.escape(_l)
                if any(m in _l for m in (' ERROR ', 'CRITICAL', 'Traceback (most recent', 'EXCEPTION ')):
                    _e = "<span class='err'>" + _e + "</span>"
                jl.append(_e)
            inner = (
                "<div class='wrap'><div class='side'>" + side + "</div><div class='main'>"
                "<h1>&#128220; Journaux</h1>"
                "<div class='bar'><a class='btn' href='/fm?folder=settings'>&#8592; Paramètres</a>"
                "<a class='btn2 btn' href='/fm?folder=logs&log=" + _quote(sel) + "'>&#8635; Rafraîchir</a>"
                "<a class='btn2 btn' href='/fm/logs/live?hist=100'>&#9654; Live</a>"
                "<a class='btn' href='/fm/logs/download?all=1'>&#128229; Tout télécharger (zip)</a>"
                "<form method='post' action='/fm/logs/clear' style='display:inline'><button class='del'>&#128465; Vider</button></form></div>"
                "<table class='logtable'><thead><tr><th>Nom</th><th>Taille</th><th>Modifié</th><th>Actions</th></tr></thead><tbody>"
                + rows_log + "</tbody></table>"
                "<h2 style='font-size:1rem;margin:16px 0 8px'>" + _html.escape(sel) + " — dernières "
                + str(limite) + " lignes</h2>"
                "<pre class='logbox'>" + "<br>".join(jl) + "</pre>"
                "<p class='sub'>Journaux complets téléchargeables ci-dessus : tracebacks Python "
                "(dont les erreurs <code>execute_code</code>), erreurs uvicorn et activité des services.</p>"
                "</div></div>"
            )
            return _HTMLResponse(_fm_page(inner, "Journaux"))
        if folder == 'maintenance':
            import os as _os3
            from open_webui.config import DATA_DIR as _DD
            taille_db = 0
            for nom_db in ('webui.db', 'webui.db-wal', 'webui.db-shm'):
                p_db = _DD / nom_db
                if p_db.is_file():
                    taille_db += p_db.stat().st_size
            inner = (
                "<div class='wrap'><div class='side'>" + side + "</div><div class='main'>"
                "<h1>\u2699\ufe0f Maintenance</h1>"
                f"<p>Donnees de l'appli : <code>{_html.escape(str(_DD))}</code></p>"
                f"<p>Base de donnees : {_fm_size(taille_db)} &mdash; Fichiers : {total} &mdash; "
                f"<a href='/fm/raw?name=webui.db'>telecharger une sauvegarde de la base</a></p>"
                "<form method='post' action='/fm/fix-index'>"
                "<button>&#128465; Nettoyer l'index des documents disparus</button></form>"
                "<p><i>La configuration ne provient jamais de l'APK ; elle vit uniquement ici. "
                "Si elle reapparait apres effacement, c'est Android qui l'a restauree "
                "(sauvegarde automatique desactivee depuis v0.0.15).</i></p>"
                "<form method='post' action='/fm/reset'>"
                "<button class='del'>&#9888; Tout effacer et reinitialiser</button></form>"
                "<p style='color:#bbb'>Cette action est definitive : comptes, conversations, "
                "fichiers et reglages.</p>"
                "<p style='color:#999'>L'effacement s'applique au prochain demarrage (forcez l'arret "
                "de l'appli puis relancez). Les donnees sont aussi visibles et supprimables depuis "
                "votre gestionnaire de fichiers : <code>Android/data/org.openwebui.android/</code>.</p>"
                "<div class='nav'><a href='/fm'>&#8592; navigateur</a></div></div></div>"
            )
            return _HTMLResponse(_fm_page(inner, "Maintenance"))
        prev_link = f"<a href=\\"/fm?folder={folder}&q={_quote(q)}&page={page-1}\\">\\u2190 pr\\u00e9c\\u00e9dent</a>" if page > 1 else ""
        next_link = f"<a href=\\"/fm?folder={folder}&q={_quote(q)}&page={page+1}\\">suivant \\u2192</a>" if page * per_page < total else ""
        inner = (
            "<div class=\\"wrap\\"><div class=\\"side\\">" + side + "</div><div class=\\"main\\">"
            "<h1>Navigateur de fichiers</h1>"
            f"<div class=\\"bar\\"><form method=\\"get\\" action=\\"/fm\\">"
            f"<input type=\\"hidden\\" name=\\"folder\\" value=\\"{folder}\\">"
            f"<input type=\\"search\\" name=\\"q\\" value=\\"{_html.escape(q)}\\" placeholder=\\"Rechercher un fichier\\">"
            "<button>Chercher</button></form></div>"
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
                await asyncio.to_thread(Storage.delete_file, f.path)
            except Exception:
                pass
            # P31 : purger aussi l'index vectoriel (sinon l'index cite des
            # fichiers disparus — incohérence signalée en audit)
            try:
                from open_webui.retrieval.vector.async_client import ASYNC_VECTOR_DB_CLIENT
                await ASYNC_VECTOR_DB_CLIENT.delete(collection_name=f'file-{f.id}')
            except Exception:
                pass
            await Files.delete_file_by_id(f.id)
    except Exception:
        pass
    return _Redirect('/fm', status_code=303)


@app.post('/fm/reset')
async def fm_reset(request: Request, user=Depends(get_verified_user)):
    """Demande une reinitialisation complete : appliquee au prochain demarrage."""
    try:
        from open_webui.config import DATA_DIR as _DD
        (_DD / 'reset-requested').write_text('1', encoding='utf-8')
    except Exception:
        pass
    return _HTMLResponse(_fm_page(
        "<h1>&#9989; Reinitialisation demandee</h1>"
        "<p>Forcez l'arret de l'appli puis relancez-la : comptes, conversations, "
        "fichiers et reglages seront effaces.</p>"))


@app.post('/fm/fix-index')
async def fm_fix_index(request: Request, user=Depends(get_verified_user)):
    """P31 : supprime les collections orphelines de l'index vectoriel
    (fichiers supprimés dont les chunks restent indexés)."""
    try:
        from open_webui.models.files import Files
        from open_webui.retrieval.vector.async_client import ASYNC_VECTOR_DB_CLIENT

        result = await Files.get_file_list(user_id=None, skip=0, limit=100000)
        connus = {"file-" + f.id for f in result.items}
        orphelins = []
        # P36 : get_collections() n'existe ni sur le wrapper async ni sur tous
        # les backends — on passe par le client synchrone, avec repli propre.
        client = ASYNC_VECTOR_DB_CLIENT.sync
        inspectable = hasattr(client, "get_collections")
        noms = []
        if inspectable:
            try:
                noms = list(client.get_collections() or [])
            except Exception:
                inspectable = False
        if not inspectable:
            return _HTMLResponse(_fm_page(
                "<h1>&#9888; Index non inspectable</h1>"
                "<p>Le backend vectoriel en cours ne permet pas d'énumérer les "
                "collections : aucun nettoyage d'orphelin n'est possible.</p>"
                "<div class='nav'><a href='/fm?folder=maintenance'>&#8592; maintenance</a></div>"))
        for nom in noms:
            if str(nom).startswith("file-") and str(nom) not in connus:
                try:
                    await ASYNC_VECTOR_DB_CLIENT.delete(collection_name=str(nom))
                    orphelins.append(str(nom))
                except Exception:
                    pass
        msg = (str(len(orphelins)) + " collection(s) orpheline(s) supprimée(s)." if orphelins
               else "Aucune collection orpheline : l'index est cohérent.")
        return _HTMLResponse(_fm_page(
            "<h1>&#9989; Index v\u00e9rifi\u00e9</h1><p>" + _html.escape(msg) + "</p>"
            "<div class='nav'><a href='/fm?folder=maintenance'>&#8592; maintenance</a></div>"))
    except Exception as exc:
        return _HTMLResponse(_fm_error(exc), status_code=500)


@app.post('/fm/settings')
async def fm_settings_save(request: Request, user=Depends(get_verified_user)):
    """P89 — enregistre les variables d'environnement (data/openwebui.env),
    appliquées au prochain démarrage/redémarrage de l'application."""
    try:
        form = await request.form()
        import android_main as _am
        lignes = []
        for _k in form.keys():
            if _k.startswith('VAR_'):
                _v = str(form.get(_k) or '').strip()
                if _v:
                    lignes.append(_k[4:] + '=' + _v)
        _extras = str(form.get('extras') or '').strip()
        if _extras:
            lignes.append(_extras)
        msg = _am.env_save(chr(10).join(lignes))
        return _HTMLResponse(_fm_page(
            "<h1>&#9989; R\u00e9glages</h1><p>" + _html.escape(msg) + "</p>"
            "<div class='nav'><a href='/fm?folder=settings'>&#8592; param\u00e8tres</a></div>"))
    except Exception as exc:
        return _HTMLResponse(_fm_error(exc), status_code=500)


@app.get('/fm/raw')
async def fm_raw(request: Request, user=Depends(get_verified_user)):
    """Telechargement/apercu direct d'un fichier du dossier uploads (nom de base)."""
    from fastapi.responses import FileResponse as _FR

    nom = (request.query_params.get('name') or '').strip()
    p = _fm_chemin_local(nom)
    if p is None:
        return _HTMLResponse(_fm_page("<h1>Fichier introuvable</h1><a href=\\"/fm\\">\\u2190 retour</a>"), status_code=404)
    return _FR(p, filename=p.name)


@app.post('/fm/delete-raw')
async def fm_delete_raw(request: Request, user=Depends(get_verified_user)):
    """Supprime un fichier orphelin du dossier uploads."""
    try:
        form = await request.form()
        p = _fm_chemin_local(str(form.get('name') or ''))
        if p is not None:
            p.unlink()
    except Exception:
        pass
    return _Redirect('/fm', status_code=303)


@app.get('/fm/logs/download')
async def fm_logs_download(request: Request, user=Depends(get_verified_user)):
    """P94 — telecharge un journal (nom de base) ou tous les journaux (zip)."""
    from open_webui import android_logs as _al
    from fastapi.responses import FileResponse as _FR, Response as _Resp

    if not _journaux_actifs():
        return _HTMLResponse("journaux desactives", status_code=404)
    if (request.query_params.get('all') or '').strip():
        import io as _io
        import zipfile as _zip
        tampon = _io.BytesIO()
        with _zip.ZipFile(tampon, 'w', _zip.ZIP_DEFLATED) as zf:
            for f in _al.fichiers():
                p = _al.chemin(f['nom'])
                if p is not None:
                    zf.write(p, f['nom'])
        return _Resp(tampon.getvalue(), media_type='application/zip',
                     headers={'Content-Disposition': 'attachment; filename="journaux-openwebui-android.zip"'})
    p = _al.chemin((request.query_params.get('name') or '').strip())
    if p is None:
        return _HTMLResponse(_fm_page("<h1>Journal introuvable</h1><a href='/fm?folder=logs'>&#8592; journaux</a>"), status_code=404)
    return _FR(p, filename=p.name, media_type='text/plain')


@app.get('/fm/logs/live')
async def fm_logs_live(request: Request):
    """P95 — flux EN DIRECT des journaux de l'application (texte brut, suivi
    de fichier) : les memes lignes que serveur.log / exec.log, rien du
    systeme. Acces limite a la boucle locale (le serveur n'ecoute que
    127.0.0.1) — lisible au curl -N ou dans le navigateur de l'appareil."""
    from fastapi.responses import StreamingResponse as _SR
    from open_webui import android_logs as _al

    hote = (request.client.host if request.client else '')
    if hote not in ('127.0.0.1', '::1', 'localhost'):
        return _HTMLResponse(_fm_page("<h1>Accès refusé</h1>"), status_code=403)
    if not _journaux_actifs():
        return _HTMLResponse("journaux desactives", status_code=404)
    sel = (request.query_params.get('log') or '').strip()
    try:
        hist = max(0, min(int(request.query_params.get('hist') or 0), 2000))
    except Exception:
        hist = 0

    async def _flux():
        etats = {}
        for f in _al.fichiers():
            etats[f['nom']] = f['taille']
        if hist:
            for f in _al.fichiers():
                if sel and f['nom'] != sel:
                    continue
                for l in _al.lecture(f['nom'], hist).splitlines():
                    yield f['nom'] + " | " + l + chr(10)
        while True:
            for nom_f, l in _al.suite(etats):
                if sel and nom_f != sel:
                    continue
                yield nom_f + " | " + l + chr(10)
            await asyncio.sleep(1)

    return _SR(_flux(), media_type='text/plain; charset=utf-8')


@app.post('/fm/logs/clear')
async def fm_logs_clear(request: Request, user=Depends(get_verified_user)):
    """P101 — vide tous les journaux (après analyse)."""
    from open_webui import android_logs as _al
    from fastapi.responses import RedirectResponse as _Red

    if not _journaux_actifs():
        return _HTMLResponse("journaux desactives", status_code=404)
    _al.vider()
    return _Red('/fm?folder=logs', status_code=303)


@app.get('/fm/diag/eventcall')
async def fm_diag_eventcall(request: Request, user=Depends(get_verified_user)):
    """P104 — auto-test de la livraison des appels outils : l'app s'envoie à
    elle-même execute:python sur la session vivante de l'administrateur et
    renvoie la réponse (ou l'échec + l'état interne du gestionnaire de
    sessions). Diagnostic complet de la chaîne execute_code à la demande."""
    import asyncio as _aio
    import json as _j
    import time as _t
    if user.role != 'admin':
        return _HTMLResponse("reserve aux administrateurs", status_code=403)
    hote = (request.client.host if request.client else '')
    if hote not in ('127.0.0.1', '::1', 'localhost'):
        return _HTMLResponse(_fm_page("<h1>Acces refuse</h1>"), status_code=403)
    try:
        from open_webui.socket.main import (
            sio as _sio, SESSION_POOL as _pool,
            get_session_ids_by_user_ids as _gids)
        cibles = [s for s in _gids([user.id]) if s in _pool]
        etat = {
            'sessions_vivantes': [str(s)[-8:] for s in cibles],
            'pool': [str(k)[-8:] for k in _pool.keys()],
        }
        if not cibles:
            return _HTMLResponse("<pre>" + _j.dumps(
                {'erreur': 'aucune session vivante', **etat}, indent=1) + "</pre>")
        cible = cibles[-1]
        try:
            etat['participants'] = [
                (str(a)[-8:], str(b)[-8:])
                for a, b in _sio.manager.get_participants('/', cible)]
        except Exception as e:
            etat['participants'] = ['err: %s' % e]
        payload = {'type': 'execute:python', 'data': {
            'id': 'diag-%s' % int(_t.time()), 'code': 'print(2+3)',
            'packages': [], 'exec_timeout': 30, 'session_id': cible, 'files': []}}
        debut = _t.time()
        try:
            rep = await _aio.wait_for(
                _sio.call('events',
                          {'chat_id': 'diag', 'message_id': 'diag', 'data': payload},
                          to=cible, timeout=None),
                timeout=45)
            etat['reponse'] = rep
        except Exception as e:
            etat['reponse'] = '%s: %s' % (type(e).__name__, e)
        etat['duree_s'] = round(_t.time() - debut, 1)
        return _HTMLResponse("<pre>" + _j.dumps(
            etat, indent=1, ensure_ascii=False, default=str) + "</pre>")
    except Exception as exc:
        return _fm_error(exc)

'''


def _fm_lire_version() -> str:
    """Version courante (versionName de build.gradle) affichée dans le pied de
    page /fm — permet de diagnostiquer instantanément la version installée."""
    try:
        g = (PROJ / "app" / "build.gradle").read_text(encoding="utf-8")
        for ligne in g.splitlines():
            if "versionName" in ligne:
                return ligne.split("'")[1]
    except Exception:
        pass
    return "?"


def write_android_tools() -> None:
    """Audit de divergence 2026-11-09 (phase 2) : tout le code AJOUTÉ quitte
    tools/builtin.py pour tools/android_tools.py (module hors amont).
    builtin.py ne garde que les corrections de COMPORTEMENT des outils amont
    (justifiées au journal) et une ligne d'import."""
    dst = DST / "tools" / "android_tools.py"
    corps = "\n\n".join([
        TYPST_TOOL.strip(),
        DELETE_TOOLS.strip(),
        EXTRA_TOOLS_2.strip(),
        PROBE_HELPER.strip(),
        PYODIDE_PKGS_HELPER.strip(),
        UPLOADS_SABLE_HELPER.strip(),
        REPRISE_HELPER.strip(),
        EXEC_LOG_HELPER.strip(),
        "SANDBOX_NET_BOOTSTRAP = " + repr(SANDBOX_NET_BOOTSTRAP),
    ])
    dst.write_text(ANDROID_TOOLS_HEADER + corps + "\n", encoding="utf-8")
    log("  P0 module tools/android_tools.py écrit (code ajouté sorti de builtin.py)")
    PATCHES.append(("code ajouté → tools/android_tools.py", "écrit"))
    replace_once(
        DST / "tools" / "builtin.py",
        "from open_webui.utils.json_codec import JSONCodec",
        "from open_webui.utils.json_codec import JSONCodec\n"
        "# P0 : code ajouté Android isolé dans un module hors amont (audit de\n"
        "# divergence 2026-11-09) — importé ici pour les appels internes et les\n"
        "# enregistrements d'outils.\n"
        "from open_webui.tools.android_tools import (  # noqa: F401\n"
        "    SANDBOX_NET_BOOTSTRAP, _probe_fetch_url, _pyodide_packages, _uploads_pour_sable,\n"
        "    compile_typst, delete_file, delete_note, delete_skill, delete_tool, list_files, list_tools,\n"
        "    journal_exec_appel, journal_exec_exception, journal_exec_ligne, remonte_fichiers_sable,\n"
        ")",
        "P0 builtin : import android_tools",
    )


LOG_CODE = '''"""OpenWebUI Android — journaux d'activité (P94).

Module AJOUTÉ hors amont : capture les journaux Python (uvicorn, open_webui,
android_main, execute_code) dans data/logs/*.log pour les consulter et les
télécharger depuis /fm → Journaux. Stdlib seule, rotation par taille.
"""

import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()
_dir_cache = None
_taille_max = 1_200_000
_installe = False
_VALID = re.compile(r"^(serveur|exec)\\.log(\\.\\d)?$")


def _dir() -> Path:
    global _dir_cache
    if _dir_cache is None:
        d = os.environ.get("OWUI_LOGS_DIR")
        if not d:
            from open_webui.config import DATA_DIR
            d = Path(DATA_DIR) / "logs"
        d = Path(d)
        d.mkdir(parents=True, exist_ok=True)
        _dir_cache = d
    return _dir_cache


def chemin(nom: str):
    """Chemin sur d'un journal (nom de base accepte, sinon None)."""
    nom = os.path.basename((nom or "").strip())
    if not _VALID.match(nom):
        return None
    p = _dir() / nom
    return p if p.is_file() else None


def _rotation(chemin_f) -> None:
    try:
        if chemin_f.exists() and chemin_f.stat().st_size >= _taille_max:
            a1 = chemin_f.parent / (chemin_f.name + ".1")
            a2 = chemin_f.parent / (chemin_f.name + ".2")
            if a1.exists():
                a1.replace(a2)
            chemin_f.replace(a1)
    except Exception:
        pass


def suite(etats: dict) -> list:
    """P95 — flux EN DIRECT des journaux de l'application : nouvelles lignes
    depuis les offsets connus (etats = {nom: offset}, mis a jour en place).
    Une rotation de fichier repart du debut. Alimente /fm/logs/live — ce sont
    exactement les lignes de serveur.log / exec.log, rien du systeme."""
    sorties = []
    try:
        for p in sorted(_dir().iterdir()):
            if not _VALID.match(p.name):
                continue
            off = int(etats.get(p.name, 0))
            taille = p.stat().st_size
            if taille < off:
                off = 0
            if taille == off:
                continue
            with open(p, "rb") as f:
                f.seek(off)
                brut = f.read(256 * 1024)
            etats[p.name] = off + len(brut)
            for l in brut.decode("utf-8", "replace").splitlines():
                sorties.append((p.name, l))
    except Exception:
        pass
    return sorties


def _ecrire(nom: str, ligne: str) -> None:
    try:
        p = _dir() / nom
        with _lock:
            _rotation(p)
            with open(p, "a", encoding="utf-8") as f:
                f.write(ligne)
    except Exception:
        pass


def journal(source: str, message: str, niveau: str = "INFO") -> None:
    """Ligne horodatee dans serveur.log (evenements hors logging)."""
    _ecrire("serveur.log", "[%s] %s %s: %s\\n" % (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), niveau, source, message))


def journal_exec(message: str) -> None:
    """Ligne horodatee dans exec.log (journal des executions execute_code)."""
    _ecrire("exec.log", "[%s] %s\\n" % (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message))


class _Handler(logging.Handler):
    """Handler fichier : message formate (traceback inclus) dans serveur.log."""

    def emit(self, record):
        try:
            texte = self.format(record)
        except Exception:
            texte = record.getMessage()
        _ecrire("serveur.log", "[%s] %s %s: %s\\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            record.levelname, record.name, texte))


def install() -> None:
    """Branche la capture fichier sur les loggeurs de l'app (idempotent).
    Aucun niveau n'est change : seul un handler supplementaire est ajoute."""
    global _installe
    if _installe:
        return
    _installe = True
    try:
        h = _Handler()
        h.setFormatter(logging.Formatter("%(message)s"))
        for nom in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "android_main",
                    "open_webui", "socketio", "engineio"):
            logging.getLogger(nom).addHandler(h)
    except Exception:
        pass


def fichiers() -> list:
    """Liste des journaux (nom, taille, date) — rotations comprises."""
    sortie = []
    try:
        for p in sorted(_dir().iterdir()):
            if not _VALID.match(p.name):
                continue
            st = p.stat()
            sortie.append({
                "nom": p.name,
                "taille": st.st_size,
                "modifie": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
        sortie.sort(key=lambda f: f["nom"])
    except Exception:
        pass
    return sortie


def lecture(nom: str, lignes: int = 300) -> str:
    """Dernieres lignes d'un journal (lecture tronquee a ~400 Ko)."""
    p = chemin(nom)
    if p is None:
        return ""
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 400_000))
            brut = f.read()
        return "\\n".join(brut.splitlines()[-max(1, lignes):])
    except Exception:
        return ""


def supprimer(nom: str) -> bool:
    p = chemin(nom)
    if p is None:
        return False
    try:
        p.unlink()
        return True
    except Exception:
        return False


def vider() -> int:
    """P101 — vide tous les journaux (après analyse). Retourne le nombre de
    fichiers supprimés."""
    n = 0
    try:
        for p in list(_dir().iterdir()):
            if _VALID.match(p.name):
                try:
                    p.unlink()
                    n += 1
                except Exception:
                    pass
    except Exception:
        pass
    return n
'''


def write_android_logs() -> None:
    """P94 — journaux d'activité (demande utilisateur : « voir les log de ce
    qui se passe et les télécharger pour analyser l'erreur execute_code et
    autre »). Module ajouté hors amont : data/logs/serveur.log (logging
    complet, tracebacks compris) + data/logs/exec.log (journal des exécutions),
    consultables et téléchargeables depuis /fm → Journaux."""
    (DST / "android_logs.py").write_text(LOG_CODE, encoding="utf-8")
    log("  P94 module android_logs.py écrit (journaux serveur/exec)")
    PATCHES.append(("module journaux → android_logs.py", "écrit"))


def write_android_fm() -> None:
    """P27 — audit de divergence 2026-11-09 (phase 1) : les routes /fm vivent
    désormais dans un module AJOUTÉ (android_fm.py) au lieu d'être greffées
    dans main.py — main.py redevient quasi identique à l'amont."""
    version = _fm_lire_version()
    corps = "\n".join(
        ("    " + ligne if ligne.strip() else ligne)
        for ligne in FM_CODE.replace("@@VERSION@@", version).splitlines()
    )
    entete = (
        '"""OpenWebUI Android — navigateur de fichiers /fm + maintenance (P27/P31/P36).\n'
        "\n"
        "Module AJOUTÉ hors amont (audit de divergence 2026-11-09) : ces routes\n"
        "vivent ici pour garder main.py identique à l'origine Open WebUI.\n"
        '"""\n\n'
        "import asyncio\n\n"
        "from fastapi import Depends, Request\n\n"
        "from open_webui.utils.auth import get_verified_user\n\n\n"
        "def register_fm(app) -> None:\n"
    )
    (DST / "android_fm.py").write_text(entete + corps + "\n", encoding="utf-8")
    log("  P0 module android_fm.py écrit (routes /fm sorties de main.py)")
    PATCHES.append(("routes /fm → android_fm.py", "écrit"))
    replace_once(
        DST / "main.py",
        "@app.get('/cache/{path:path}')",
        "# P27 : navigateur de fichiers + maintenance — module ajouté (hors amont)\n"
        "from open_webui.android_fm import register_fm as _register_fm_android\n"
        "_register_fm_android(app)\n\n@app.get('/cache/{path:path}')",
        "P27 navigateur /fm (module android_fm)",
    )


def patch_files_manager() -> None:
    """P26/P27 — voir write_android_fm (routes déplacées hors amont)."""
    write_android_fm()


def patch_files_button() -> None:
    """P26b — bouton flottant « Fichiers » dans index.html (le menu du Workspace
    n'a aucune entrée Fichiers ; le bouton rend /fm découvrable partout).
    P32 : capture du Blob à la source (les URL blob: ne sont pas fetchables
    depuis le pont natif — « TypeError: Failed to fetch »).
    P35 : shim window.Notification → pont natif AndroidNotify (l'API web
    Notification n'existe pas dans une WebView Android : le réglage
    « Notifications » d'Open WebUI ne pouvait pas s'activer)."""
    notif_shim = (
        '<script>(function(){if(window.__notifShim){return;}window.__notifShim=1;'
        'var b=(typeof AndroidNotify!=="undefined")?AndroidNotify:null;'
        'function N(t,o){this.title=t;this.body=(o&&o.body)||"";'
        'try{if(b){b.show(String(t),String(this.body));}}catch(e){}}'
        'N.prototype.close=function(){};'
        'Object.defineProperty(N,"permission",{get:function(){'
        'try{return b?b.permissionState():"denied";}catch(e){return "denied";}}});'
        'N.requestPermission=function(cb){var p=new Promise(function(res){'
        'try{if(!b){res("denied");return;}'
        'var s=b.permissionState();'
        'if(s!=="default"){res(s);return;}'
        'window.__notifPermResolve=function(r){window.__notifPermResolve=null;res(r);};'
        'b.requestPermission();}catch(e){res("denied");}});'
        'if(cb){p.then(cb);}return p;};'
        'window.Notification=N;})();</script>\n'
    )
    btn = (
        '<script>(function(){var o=URL.createObjectURL.bind(URL);'
        'URL.createObjectURL=function(b){try{window.__dlBlob=b;}catch(e){}return o(b);};'
        '})();</script>\n'
        + notif_shim +
        '<a href="/fm" id="fab-spa" title="Fichiers : PDF générés et téléversements — glisser pour déplacer" '
        'style="position:fixed;right:12px;bottom:72px;z-index:2147483000;'
        'width:42px;height:42px;border-radius:50%;background:#3b82f6;color:#fff;'
        'display:flex;align-items:center;justify-content:center;font-size:20px;'
        'text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,.4);cursor:grab;touch-action:none">'
        '&#128206;</a>'
        '<script>(function(){var el=document.getElementById("fab-spa");if(!el)return;'
        'try{var s=JSON.parse(localStorage.getItem("fabPosSpa")||"null");'
        'if(s){el.style.left=s.l+"px";el.style.top=s.t+"px";el.style.right="auto";el.style.bottom="auto";}}catch(e){}'
        'var sx,sy,ox,oy,drag=0,moved=0;'
        'el.addEventListener("pointerdown",function(e){drag=1;moved=0;sx=e.clientX;sy=e.clientY;'
        'var r=el.getBoundingClientRect();ox=r.left;oy=r.top;});'
        'el.addEventListener("pointermove",function(e){if(!drag)return;'
        'var dx=e.clientX-sx,dy=e.clientY-sy;if(!moved&&Math.abs(dx)+Math.abs(dy)<6)return;'
        'moved=1;el.style.left=(ox+dx)+"px";el.style.top=(oy+dy)+"px";'
        'el.style.right="auto";el.style.bottom="auto";e.preventDefault();});'
        'el.addEventListener("pointerup",function(){if(!drag)return;drag=0;if(moved){'
        'try{localStorage.setItem("fabPosSpa",JSON.stringify({l:parseInt(el.style.left)||0,t:parseInt(el.style.top)||0}));}catch(e){}}});'
        'el.addEventListener("click",function(e){if(moved){e.preventDefault();e.stopPropagation();moved=0;}});'
        '})();</script>\n</body>'
    )
    replace_once(
        DST / "frontend" / "index.html",
        "</body>",
        btn,
        "P26b/P32/P35 bouton Fichiers + capture du Blob + shim Notification",
    )


def patch_delete_tools() -> None:
    """P29 — outils de suppression définitive : delete_note, delete_skill,
    delete_tool (aucun n'existait : toute sonde d'écriture était irréversible)."""
    builtin = DST / "tools" / "builtin.py"
    text = builtin.read_text(encoding="utf-8")
    if "async def delete_note(" in text:
        log("  P29 delete_* : déjà appliqué")
    else:
        builtin.write_text(text, encoding="utf-8")  # code fourni par tools/android_tools.py
        log("  P29 outils delete_note/delete_skill/delete_tool ajoutés")
        PATCHES.append(("outils delete_note/delete_skill/delete_tool", "ajoutés"))
    replace_once(DST / "utils" / "tools.py",
        "    create_tool,",
        "    create_tool,\n    delete_file,\n    delete_note,\n    delete_skill,\n    delete_tool,\n    list_files,\n    list_tools,",
        "P29a imports delete_*/list_*")
    replace_once(DST / "utils" / "tools.py",
        "builtin_functions.extend([search_notes, view_note, write_note, replace_note_content])",
        "builtin_functions.extend([search_notes, view_note, write_note, replace_note_content, delete_note, delete_file, list_files])",
        "P29b registrement delete_note/delete_file/list_files")
    replace_once(DST / "utils" / "tools.py",
        "            builtin_functions.append(create_tool)",
        "            builtin_functions.append(create_tool)\n            builtin_functions.append(delete_tool)\n            builtin_functions.append(list_tools)",
        "P29c registrement delete_tool/list_tools")
    replace_once(DST / "utils" / "tools.py",
        "        builtin_functions.append(create_skill)",
        "        builtin_functions.append(create_skill)\n        builtin_functions.append(delete_skill)",
        "P29d registrement delete_skill")
    replace_once(builtin,
        '''    :param id: Unique lowercase Python identifier for the toolkit.''',
        '''    :param id: Unique identifier — lowercase letters, digits and underscores ONLY (a-z, 0-9, _), e.g. "diag_test_tool" NOT "diag-test-tool" (hyphens/spaces are rejected).''',
        "P96 create_tool : contrainte d'id documentée")
    replace_once(builtin,
        '''    Update an existing calendar event. Only provided fields are changed;
    omitted fields stay the same.''',
        '''    Update an existing calendar event. Only provided fields are changed;
    omitted fields stay the same. To MOVE an event, pass BOTH start and end
    together (changing only start leaves end unchanged, which can make the
    interval incoherent).''',
        "P96 update_calendar_event : start/end à passer ensemble")


def patch_tool_status() -> None:
    """P33/P34 — honnêteté des outils (audit 2026-11-08) : fetch_url expose le
    statut HTTP réel (redirections suivies avec ré-validation SSRF, pages
    anti-bot signalées) ; execute_code reflète l'échec réel ('status: error'
    quand stderr porte une exception, au lieu du 'success' codé en dur)."""
    builtin = DST / "tools" / "builtin.py"
    text = builtin.read_text(encoding="utf-8")
    if "_probe_fetch_url" in text:
        log("  P33 sonde HTTP fetch_url : déjà appliqué")
    else:
        log("  P33/P46/P51/P52 helpers : fournis par tools/android_tools.py")
        log("  P33 sonde HTTP de fetch_url ajoutée")
    replace_once(
        builtin,
        """    try:
        content, _ = await get_content_from_url(__request__, url)""",
        """    try:
        # P33 : sonde HTTP préalable — sans statut visible, fetch_url renvoyait
        # du contenu faux sans le signaler (404 → page d'accueil ou vide,
        # 302 → corps de la redirection, anti-bot → « Just a moment... »).
        verify_ssl = await Config.get('web.loader.ssl_verification')
        statut, url_finale, chaine = await asyncio.to_thread(
            _probe_fetch_url, url, verify_ssl)
        if statut in (301, 302, 303, 307, 308):
            return JSONCodec.dumps({
                'error': f'Redirection HTTP {statut} non suivie (trop de sauts) : {url_finale}',
                'status_code': statut,
                'chain': chaine,
            }, ensure_ascii=False)
        if statut == 0 or statut >= 400:
            return JSONCodec.dumps({
                'error': f'Échec HTTP {statut if statut else "réseau"} pour {url}',
                'status_code': statut,
                'chain': chaine,
            }, ensure_ascii=False)

        content, _ = await get_content_from_url(__request__, url_finale)""",
        "P33a fetch_url : statut HTTP préalable",
    )
    replace_once(
        builtin,
        """        return content
    except Exception as e:
        log.warning(f'fetch_url error: {e}')""",
        """        # P33 : provenance exacte + signalement des pages anti-bot
        content = __import__('re').sub(r'\\n{3,}', '\\n\\n', content or '')
        entete = f'[HTTP {statut} — {url_finale}]'
        if len(chaine) > 1:
            entete += f' (redirections : {" -> ".join(chaine)})'
        bas = (content or '').lower()
        if any(m in bas for m in ('just a moment', 'cf-browser-verification',
                                  'checking your browser', 'attention required',
                                  'enable javascript and cookies', 'g-recaptcha')):
            entete += '\\n[AVERTISSEMENT : page anti-bot / interstitielle — contenu probablement incomplet]'
        return f'{entete}\\n\\n{content or ""}'
    except Exception as e:
        log.warning(f'fetch_url error: {e}')""",
        "P33b fetch_url : entête + anti-bot",
    )
    replace_once(
        builtin,
        """        response = {
            'status': 'success',
            'stdout': stdout,
            'stderr': stderr,
            'result': result,
        }""",
        """        # P34 : « success » codé en dur même sur exception (le traceback
        # restait caché dans stderr) — refléter l'échec réel de l'exécution.
        echec = bool((stderr or '').strip())
        response = {
            'status': 'error' if echec else 'success',
            'stdout': stdout,
            'stderr': stderr,
            'result': result,
        }""",
        "P34 execute_code : status réel",
    )
    replace_once(
        builtin,
        """        return JSONCodec.dumps(response, ensure_ascii=False)
    except Exception as e:
        log.exception(f'execute_code error: {e}')
        return JSONCodec.dumps({'error': str(e)})""",
        """        # P94 : journal des exécutions — consultable/téléchargeable dans /fm →
        # Journaux (analyse des erreurs execute_code et autres).
        journal_exec_appel(engine, response, delai_exec, stdout, stderr, fichiers_sortie, echec)
        return JSONCodec.dumps(response, ensure_ascii=False)
    except Exception as e:
        log.exception(f'execute_code error: {e}')
        journal_exec_exception(e)
        return JSONCodec.dumps({'error': str(e)})""",
        "P94 execute_code : journal exec.log",
    )


def patch_memory_search() -> None:
    """P39a — search_memories : la recherche de contenu promette par la
    description cassait en français (apostrophe typographique vs droite — testé :
    « sonde d'audit » ne trouvait pas « Sonde d'audit ») et refusait les
    requêtes multi-mots. Normalisation apostrophes + casse ignorée + tous les
    mots requis (dans contenu ou chemin). Comportement de parcours (requête
    vide) inchangé."""
    replace_once(
        DST / "utils" / "memory.py",
        '''def _memory_matches_query(memory, query: str) -> bool:
    value = query.strip().lower()
    if not value:
        return True
    return value in (memory.content or '').lower() or value in (memory.path or '').lower()''',
        '''def _norm_memory_text(value: str) -> str:
    """P39a : apostrophes/quotes typographiques normalisées, casse ignorée."""
    table = {0x2019: 39, 0x2018: 39, 0x02BC: 39, 0x0060: 39, 0x00B4: 39}
    return (value or '').translate(table).casefold()


def _memory_matches_query(memory, query: str) -> bool:
    value = _norm_memory_text(query).strip()
    if not value:
        return True
    haystack = _norm_memory_text(f'{memory.content or ""}\\n{memory.path or ""}')
    return all(word in haystack for word in value.split())''',
        "P39a recherche mémoires normalisée",
    )


def patch_memory_recall() -> None:
    """P43 — search_memories, rappel (audit 2026-11-08 22:20) : une formulation
    voisine renvoyait [] alors que la mémoire existait. Deux paliers : tous les
    mots (précision) puis au moins la moitié (rappel). Le tri reste inchangé."""
    replace_once(
        DST / "utils" / "memory.py",
        """    if query:
        rows = [memory for memory in rows if _memory_matches_query(memory, query)]""",
        r'''    if query:
        # P43 : rappel en deux paliers — tous les mots d'abord (précision),
        # puis au moins la moitié des mots (rappel : une formulation voisine
        # renvoyait [] — audit 2026-11-08 22:20). Le tri reste inchangé.
        _mots = _norm_memory_text(query).split()

        def _score(m):
            _hay = _norm_memory_text(f'{m.content or ""}\n{m.path or ""}')
            return sum(1 for w in _mots if w in _hay)

        _exactes = [memory for memory in rows if _score(memory) == len(_mots)]
        if _exactes:
            rows = _exactes
        else:
            _seuil = max(1, (len(_mots) + 1) // 2)
            rows = [memory for memory in rows if _score(memory) >= _seuil]''',
        "P43 search_memories : rappel à deux paliers",
    )


def patch_kb_backfill() -> None:
    """P39b — query_knowledge_bases : l'index sémantique des bases n'est rempli
    qu'à la création/édition (embed_knowledge_base_metadata) ; toute base créée
    pendant une panne d'embedding restait invisible alors que la description
    promet une recherche sémantique sur les noms/descriptions. On répare
    l'index au fil des pages avant de chercher."""
    replace_once(
        DST / "tools" / "builtin.py",
        "            accessible_ids = [kb.id for kb in accessible_knowledge_bases.items]",
        '''            accessible_ids = [kb.id for kb in accessible_knowledge_bases.items]

            # P39b : réparer l'index sémantique des bases au fil des pages —
            # toute base non indexée (créée pendant une panne d'embedding) le
            # devient maintenant, puis la recherche sémantique s'applique.
            from open_webui.routers.knowledge import embed_knowledge_base_metadata

            try:
                _existants = await ASYNC_VECTOR_DB_CLIENT.get(
                    collection_name=KNOWLEDGE_BASES_COLLECTION)
                _ids_indexees = set(_existants.ids[0]) if _existants and _existants.ids else set()
            except Exception:
                _ids_indexees = set()
            for _kb in accessible_knowledge_bases.items:
                if _kb.id not in _ids_indexees:
                    await embed_knowledge_base_metadata(
                        __request__, _kb.id, _kb.name, _kb.description or '')''',
        "P39b query_knowledge_bases : auto-réparation d'index",
    )


WORKER_HARVEST_JS = (
    'self.postMessage({id:e,result:self.result,stdout:self.stdout,stderr:self.stderr,'
    "files:(()=>{try{const out=[];let tot=0;const dir='/mnt/uploads';"
    "for(const n of self.pyodide.FS.readdir(dir)){if(n==='.'||n==='..')continue;"
    "if(self.__inNames&&self.__inNames.includes(n))continue;"
    "const p=dir+'/'+n;const st=self.pyodide.FS.stat(p);"
    "if(!self.pyodide.FS.isFile(st.mode))continue;"
    "if(self.__snap&&self.__snap[n]!==undefined&&self.__snap[n]===String(st.size)+'@'+String(Math.floor(st.mtimeMs)))continue;"
    "const d=self.pyodide.FS.readFile(p,{encoding:'binary'});"
    'if(d.length>8388608)continue;if((tot+=d.length)>16777216)continue;'
    "let s='';const CH=32768;for(let i=0;i<d.length;i+=CH)"
    's+=String.fromCharCode.apply(null,d.subarray(i,i+CH));'
    "out.push({name:n,data:btoa(s),size:d.length});}"
    "return out;}catch(err){return [];}})()});if(String(self.stderr).includes(\"Execution timeout\"))setTimeout(()=>{try{self.close()}catch(x){}},50)}self.onmessage="
)


def _patch_first_match(pattern: str, old: str, new: str, name: str) -> None:
    """Fichiers à nom haché : on repère celui qui porte l'ancre et on le patche
    (idempotent via replace_once)."""
    import glob as _glob

    for cible in sorted(_glob.glob(pattern)):
        text = Path(cible).read_text(encoding="utf-8", errors="ignore")
        if new in text and old not in text:
            log(f"  {name}: déjà appliqué")
            PATCHES.append((name, "déjà appliqué"))
            return
        if old in text:
            replace_once(Path(cible), old, new, name)
            return
    raise SystemExit(f"PATCH EN ÉCHEC [{name}] : aucune ancre dans {pattern}")


def patch_upload_harvest() -> None:
    """P41 — contrat /mnt/uploads (audit 2026-11-08 22:20) : le prompt système
    promet « écrivez dans /mnt/uploads/ pour retrouver vos fichiers dans le
    navigateur de fichiers » ; côté Pyodide ce dossier vit dans l'IndexedDB du
    navigateur et n'atteignait jamais le dossier uploads de l'app
    (getExternalFilesDir()/files/data/uploads). Chaîne : le worker renvoie les
    fichiers produits → le frontend les transmet → execute_code les enregistre
    dans UPLOAD_DIR. Les fichiers d'entrée déjà présents sont ignorés (même
    taille)."""
    root = DST / "frontend" / "_app" / "immutable"
    _patch_first_match(
        str(root / "workers" / "pyodide.worker-*.js"),
        'self.postMessage({id:e,result:self.result,stdout:self.stdout,stderr:self.stderr})}self.onmessage=',
        WORKER_HARVEST_JS,
        "P41a worker : fichiers /mnt/uploads renvoyés",
    )
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        'F&&F(JSON.parse(JSON.stringify({stdout:u,stderr:M,result:h},(be,Ge)=>typeof Ge=="bigint"?Ge.toString():Ge)))',
        'F&&F(JSON.parse(JSON.stringify({stdout:u,stderr:M,result:h,files:ge.files||[]},(be,Ge)=>typeof Ge=="bigint"?Ge.toString():Ge)))',
        "P41b frontend : fichiers transmis au backend",
    )
    replace_once(
        DST / "tools" / "builtin.py",
        "        else:\n            return JSONCodec.dumps({'error': f'Unknown code interpreter engine: {engine}'})\n\n        # Handle image outputs",
        '''        else:
            return JSONCodec.dumps({'error': f'Unknown code interpreter engine: {engine}'})

        # P41 : remontée des fichiers écrits dans /mnt/uploads vers le dossier
        # uploads de l'app — le prompt système promet « écrivez dans
        # /mnt/uploads/ pour les retrouver dans le navigateur de fichiers ».
        fichiers_sortie = remonte_fichiers_sable(output)

        # Handle image outputs''',
        "P41c execute_code : enregistrement des fichiers produits",
    )
    replace_once(
        DST / "tools" / "builtin.py",
        """        echec = bool((stderr or '').strip())
        response = {
            'status': 'error' if echec else 'success',
            'stdout': stdout,
            'stderr': stderr,
            'result': result,
        }""",
        """        echec = bool((stderr or '').strip())
        response = {
            'status': 'error' if echec else 'success',
            'stdout': stdout,
            'stderr': stderr,
            'result': result,
            'files': fichiers_sortie,
        }""",
        "P41d execute_code : fichiers signalés au modèle",
    )


def patch_note_newlines() -> None:
    """P42 — \\n littéraux dans write_note / replace_note_content (audit
    2026-11-08 22:20, reproductible) : les LLM écrivent souvent des séquences
    \\n visibles au lieu de sauts de ligne. Conversion uniquement quand le
    texte ne contient aucun saut réel — jamais de mélange contenu/échappements."""
    norm = r'''        # P42 : \n littéraux → vrais sauts de ligne (uniquement si le texte
        # n'en contient aucun : jamais de mélange contenu réel / échappements).
        if '\n' not in content and '\\n' in content:
            content = content.replace('\\n', '\n').replace('\\t', '\t')
'''
    replace_once(
        DST / "tools" / "builtin.py",
        "        form = NoteForm(\n            title=title,\n            data={'content': {'md': content}},",
        norm + "\n        form = NoteForm(\n            title=title,\n            data={'content': {'md': content}},",
        "P42a write_note : \\n littéraux convertis",
    )
    replace_once(
        DST / "tools" / "builtin.py",
        "        if operations is not None:\n            if not isinstance(operations, list)",
        r'''        # P42 : idem write_note — \n littéraux → vrais sauts de ligne
        if content is not None and '\n' not in content and '\\n' in content:
            content = content.replace('\\n', '\n').replace('\\t', '\t')
        if operations:
            for _op in operations:
                if isinstance(_op, dict):
                    _c = _op.get('content')
                    if isinstance(_c, str) and '\n' not in _c and '\\n' in _c:
                        _op['content'] = _c.replace('\\n', '\n').replace('\\t', '\t')
        if operations is not None:
            if not isinstance(operations, list)''',
        "P42b replace_note_content : \\n littéraux convertis",
    )


def patch_pyodide_universel() -> None:
    """P44b — filet de sécurité : même si le flag ENABLE_PYODIDE_FILE_PERSISTENCE
    est désactivé (l'iframe est alors utilisée), le bac à sable embarque
    numpy/pandas/sympy au boot. Sans ça, seul le worker portait les paquets de
    boot (P38) et l'iframe retombait en ModuleNotFoundError."""
    root = DST / "frontend" / "_app" / "immutable"
    _patch_first_match(
        str(root / "chunks" / "*.js"),
        "packages: ['micropip']",
        # P102 : numpy/pandas/sympy au boot = ~115 Mo de wasm d'un coup → le
        # lowmemorykiller Android tuait le worker (« disconnected before
        # answering »). pandas/sympy passent en chargement à la demande.
        "packages: ['micropip','numpy']",
        "P44b/P102 pyodide : boot allégé (pandas/sympy à la demande)",
    )
    # P98 — le gestionnaire n'exécutait execute:python que si
    # u.session_id === n().id ; après reconnexion n().id change mais
    # metadata['session_id'] reste l'ancien → le frontend ignorait l'appel
    # SANS répondre → sio.call attendait puis « Client session disconnected ».
    # La livraison sio.call(to=session_id) est déjà ciblée : on accepte
    # execute:python même si l'id porté est périmé.
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        'if(u?.session_id===n().id){if(h==="execute:python")',
        'if(u?.session_id===n().id||h==="execute:python"){if(h==="execute:python")',
        "P98 frontend : execute:python accepté même si session_id périmé",
    )
    # P99b — le worker n'émettait AUCUNE réponse si le chargement Pyodide (j)
    # échouait ou rame : `await j(...), await He(...)` sans try/catch → He jamais
    # atteint, pas de postMessage → le frontend attendait indéfiniment puis la
    # session tombait (« Client session disconnected »). On borne le chargement
    # et on répond TOUJOURS (erreur visible au lieu d'un blocage muet).
    _patch_first_match(
        str(root / "workers" / "pyodide.worker-*.js"),
        'await j(self.packages),await He(r,n,o);return',
        'try{await Promise.race([j(self.packages),new Promise((_r,_j)=>setTimeout(()=>_j(new Error("chargement Pyodide timeout")),90000))]),await He(r,n,o)}catch(err){self.postMessage({id:r,result:null,stdout:"",stderr:"ERREUR WORKER: "+(err&&err.message||String(err)),files:[]})}return',
        "P99b worker : répond toujours (try/catch + bornage Pyodide)",
    )


def patch_automation_rrule() -> None:
    """P45 — create/update_automation : la docstring elle-même montre « \\n »
    littéral entre DTSTART et RRULE ; les LLM la copient telle quelle et le
    parseur refuse (« Unknown string format »). Conversion inconditionnelle :
    un \\n littéral n'a aucun sens dans un RRULE."""
    norm = r'''        # P45 : \n littéraux convertis (la docstring les montre ainsi — les
        # LLM la copient ; le parseur RRULE exige de vrais sauts de ligne)
        if rrule:
            rrule = rrule.replace('\\r', '').replace('\\n', '\n').replace('\\t', ' ')
'''
    replace_once(
        DST / "tools" / "builtin.py",
        "        # Validate the RRULE",
        norm + "        # Validate the RRULE",
        "P45a create_automation : rrule normalisé",
    )
    replace_once(
        DST / "tools" / "builtin.py",
        "        new_rrule = rrule if rrule is not None else automation.data.get('rrule', '')",
        r'''        # P45 : idem create_automation — \n littéraux convertis
        if rrule is not None:
            rrule = rrule.replace('\\r', '').replace('\\n', '\n').replace('\\t', ' ')
        new_rrule = rrule if rrule is not None else automation.data.get('rrule', '')''',
        "P45b update_automation : rrule normalisé",
    )


REPRISE_HELPER = '''
async def appel_avec_reprise(event_call, payload, tentatives: int = 16, pause: float = 10.0):
    """P95 — appel événementiel avec reprise après « Client session disconnected ».
    Cause prouvée : la WebView gelée en arrière-plan fige le heartbeat ; le
    réaper (120 s) ferme la session et l'appel échoue alors que le code n'avait
    même pas tourné. Au lieu d'échouer, on réessaie jusqu'au retour du client
    (le socket se reconnecte dès que l'application revient au premier plan) ;
    la fenêtre globale reste bornée par l'appelant (wait_for 320 s)."""
    out = None
    for i in range(max(1, tentatives)):
        journal_exec_ligne("P97 event_call essai %s/%s" % (i + 1, tentatives))
        out = await event_call(payload)
        journal_exec_ligne("P97 essai %s -> %s" % (i + 1, (out or {}).get('error', 'ok') if isinstance(out, dict) else '?'))
        err = out.get('error') if isinstance(out, dict) else None
        if err and 'Client session disconnected' in err and i < tentatives - 1:
            await asyncio.sleep(pause)
            continue
        break
    if isinstance(out, dict) and out.get('error') and 'Client session disconnected' in out['error']:
        out = {**out, 'error': (
            'Client session disconnected — application restée en arrière-plan '
            'trop longtemps : rouvrez l application puis relancez (le code '
            'n a pas été exécuté).')}
    return out
'''


EXEC_LOG_HELPER = '''
def journal_exec_ligne(msg) -> None:
    """P96 — trace d'exécution (entrée, timeout, erreur) dans exec.log.
    Ne lève JAMAIS : le journal ne doit pas casser l'outil."""
    try:
        from open_webui.android_logs import journal_exec
        journal_exec(str(msg))
    except Exception:
        pass


def remonte_fichiers_sable(output) -> list:
    """P41 — remontée des fichiers écrits dans /mnt/uploads vers le dossier
    uploads de l'app (le prompt système promet « écrivez dans /mnt/uploads/
    pour les retrouver dans le navigateur de fichiers »). Retourne les noms
    produits ; ne lève pas sur un fichier invalide."""
    produits = []
    if isinstance(output, dict):
        for _f in (output.get('files') or []):
            try:
                import base64 as _b64
                import os as _os2
                from open_webui.config import UPLOAD_DIR as _UD

                _nom = _os2.path.basename(str(_f.get('name') or ''))
                _don = _f.get('data')
                if not _nom or not _don:
                    continue
                _brut = _b64.b64decode(_don)
                _dest = _UD / _nom
                if _dest.exists() and _dest.stat().st_size == len(_brut):
                    continue  # déjà présent à l'identique (fichier d'entrée)
                _UD.mkdir(parents=True, exist_ok=True)
                _dest.write_bytes(_brut)
                produits.append(_nom)
            except Exception:
                pass
    return produits


def journal_exec_appel(engine, response, delai_exec, stdout, stderr, fichiers_sortie, echec) -> None:
    """P94 — journalise une exécution execute_code (statut, tailles, extrait
    stderr sur échec) dans data/logs/exec.log (consultable/téléchargeable dans
    /fm → Journaux). Ne lève JAMAIS : le journal ne doit pas casser l'outil."""
    try:
        from open_webui.android_logs import journal_exec
        _r = "%s %s delai=%ss out=%sB err=%sB files=%s" % (
            engine, response.get("status"), delai_exec,
            len(stdout or ""), len(stderr or ""), len(fichiers_sortie or []))
        if echec:
            _r += " | " + (stderr or "").strip()[-1500:]
        journal_exec(_r)
    except Exception:
        pass


def journal_exec_exception(e) -> None:
    """P94 — journalise une exception execute_code (nom + message)."""
    try:
        from open_webui.android_logs import journal_exec
        journal_exec("EXCEPTION %s: %s" % (type(e).__name__, e))
    except Exception:
        pass
'''


PYODIDE_PKGS_HELPER = '''
def _pyodide_packages(code: str) -> list:
    """P46a — paquets Pyodide à installer avant exécution. Détection par
    simple PRÉSENCE du nom du module dans le code (import littéral, boucle,
    importlib, littéral de chaîne — peu importe le style), pour être
    insensible à la façon d'importer. Seuls les wheels embarqués dans l'APK
    sont proposés (installation hors ligne)."""
    noms = {
        'numpy': 'numpy', 'pandas': 'pandas', 'matplotlib': 'matplotlib',
        'scipy': 'scipy', 'sklearn': 'scikit-learn', 'PIL': 'pillow',
        'seaborn': 'seaborn', 'sympy': 'sympy', 'mpmath': 'mpmath',
        'bs4': 'beautifulsoup4', 'requests': 'requests', 'lxml': 'lxml',
        'docx': 'python-docx', 'pptx': 'python-pptx', 'openpyxl': 'openpyxl',
        'pytz': 'pytz', 'regex': 'regex',
        'dateutil': 'python-dateutil', 'six': 'six', 'packaging': 'packaging',
        'pymupdf': 'pymupdf', 'fitz': 'pymupdf', 'statsmodels': 'statsmodels',
    }
    texte = code or ''
    import re as _re
    trouves = set()
    for nom, paquet in noms.items():
        if _re.search(r'\\b' + _re.escape(nom) + r'\\b', texte):
            trouves.add(paquet)
    return sorted(trouves)
'''


def patch_pyodide_detection() -> None:
    """P46 — les paquets à la demande ne dépendaient que de la détection regex
    d'imports littéraux côté frontend : un code qui importe par boucle ou
    importlib ne déclenchait rien (audit : numpy/pandas/sympy OK au boot,
    tout le reste absent). La liste est désormais calculée côté SERVEUR (par
    présence du nom dans le code) et transmise au bac à sable."""
    builtin = DST / "tools" / "builtin.py"
    text = builtin.read_text(encoding="utf-8")
    if "_pyodide_packages(" in text:
        log("  P46a détection paquets : déjà appliqué")
    else:
        log("  P46a détection paquets : fournie par tools/android_tools.py")
        log("  P46a détection serveur des paquets ajoutée")
    replace_once(
        builtin,
        """                    'data': {
                        'id': str(uuid4()),
                        'code': code,""",
        """                    'data': {
                        'id': str(uuid4()),
                        'code': code,
                        'packages': _pyodide_packages(code),
                        'exec_timeout': delai_exec,""",
        "P46b execute_code : paquets calculés côté serveur",
    )
    root = DST / "frontend" / "_app" / "immutable"
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        "Me(u.id,u.code,i,u.files||[])",
        "Me(u.id,u.code,i,u.files||[],u.packages||[])",
        "P46c frontend : transit des paquets serveur",
    )
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        'Me(u.id,u.code,i,u.files||[],u.packages||[]);return}',
        'Me(u.id,u.code,i,u.files||[],u.packages||[],u.exec_timeout||120).catch(e=>{try{i&&i({error:"execute_code frontend: "+(e&&e.message||e)})}catch(x){}});return}',
        "P85a frontend : échec de Me acquitté (plus d'attente infinie)",
    )
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        "!pe().has(t.chat_id)))return;",
        '!pe().has(t.chat_id))){try{i&&i({error:"event dropped: conversation non active dans cet onglet"})}catch(e){}return;}',
        "P85b frontend : événement écarté acquitté explicitement",
    )
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        "Me=async(t,i,F,P=[])",
        "Me=async(t,i,F,P=[],X=[])",
        "P46d frontend : signature Me étendue",
    )
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        "packages:ue,files:k.length>0?k:void 0}",
        "packages:[...new Set([...ue,...X])],files:k.length>0?k:void 0,exec_timeout:TO}",
        "P46e frontend : fusion regex + serveur",
    )
    replace_once(
        DST / "config.py",
        "- This Python environment runs via Pyodide in the browser. **Do not install packages** — `pip install`, `subprocess`, and `micropip.install()` are not available.",
        "- This Python environment runs via Pyodide in the browser. **Do not install packages** — `pip install`, `subprocess`, and `micropip.install()` are not available.\n- Libraries bundled and available on demand: numpy, pandas, matplotlib, scipy, scikit-learn, seaborn, sympy, mpmath, pillow (PIL), requests, beautifulsoup4 (bs4), lxml, python-docx (docx), python-pptx (pptx), openpyxl, pytz, pymupdf (fitz), statsmodels. No other third-party library (no plotly, pypdf, tiktoken).\n- Network: the sandbox has no TCP. socket.create_connection always raises OSError. Outbound HTTP goes through the browser and is filtered by CORS: a request fails with ConnectionError whenever the target site does not send CORS headers — this does NOT mean the site is down. To probe a URL reliably, use fetch_url; for an API, try fetch_url first and fall back to requests here (or the reverse) — the two paths have different egresses. Each code run is limited to 120 seconds by default (timeout parameter, max 600) — an infinite loop is interrupted and reported. Check the `network_available` flag (set on first run) before trying.\n- Files: everything in /mnt/uploads/ is saved to the app file browser; the app's uploads are also visible there.",
        "P46f prompt : bibliothèques disponibles documentées",
    )


def patch_extra_wheels() -> None:
    """P47 — wheels supplémentaires embarqués depuis wheels-extra/ (VERSIONNÉS,
    comme les 53 wheels amont de src-assets/) : statsmodels et pymupdf existent
    en wasm dans la distribution Pyodide (sha256 conformes au lock
    pyodide-lock.json) mais l'amont n'en embarquait que 53 pour garder l'APK
    léger. Copiés dans pyodide/, ils deviennent installables hors ligne par le
    bac à sable (détection P46)."""
    import glob as _glob
    import shutil as _shutil

    srcs = sorted(_glob.glob(str(PROJ / "wheels-extra" / "*.whl")))
    if not srcs:
        log("  P47 wheels supplémentaires : aucun wheel dans wheels-extra/")
        return
    dest_dir = DST / "frontend" / "pyodide"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in srcs:
        _shutil.copy2(src, dest_dir / Path(src).name)
    noms = ", ".join(Path(s).name.split("-")[0] for s in srcs)
    log(f"  P47 wheels supplémentaires embarqués : {noms}")
    PATCHES.append((f"wheels extra ({noms})", f"{len(srcs)} copié(s)"))


UPLOADS_SABLE_HELPER = '''
def _uploads_pour_sable(code: str = '', max_par: int = 8 * 1024 * 1024, max_total: int = 256 * 1024) -> list:
    """P51/P77 — alignement des deux magasins : le dossier uploads de l'app est
    injecté dans le /mnt/uploads du bac à sable (les fichiers déjà injectés y
    PERSISTENT via IndexedDB).
    P77 : seuls les fichiers CITÉS dans le code partent systématiquement ; les
    petits fichiers (≤ 64 Ko, budget 256 Ko) suivent pour la découvrabilité —
    au-delà, rien ne part : l'expédition totale faisait de CHAQUE appel un
    transfert de mégaoctets (print('hello') mettait des secondes)."""
    from open_webui.config import UPLOAD_DIR as _UD

    texte = code or ''
    sortie = []
    total = 0
    try:
        for ent in (sorted(_UD.iterdir()) if _UD.is_dir() else []):
            if not ent.is_file():
                continue
            taille = ent.stat().st_size
            if taille > max_par:
                continue
            mentionne = ent.name in texte or ent.stem in texte
            if not mentionne and (taille > 64 * 1024 or total + taille > max_total):
                continue
            sortie.append({'name': ent.name, 'data': ent.read_bytes()})
            total += taille
    except Exception:
        pass
    return sortie
'''

SANDBOX_NET_BOOTSTRAP = '''
# --- P52/P88 : réseau du bac à sable ---
try:
    network_available
except NameError:
    network_available = None  # renseigné par une sonde JS bornée (AbortSignal)
try:
    _sock_indispo
except NameError:
    import socket as _sock

    def _sock_indispo(*a, **k):
        raise OSError('pas de TCP dans le bac à sable (wasm) : utilisez urllib/requests en HTTP')
    _sock.create_connection = _sock_indispo
    _sock.socket = _sock_indispo
# --- fin P52/P88 ---
'''


def patch_sandbox_hardening() -> None:
    """P49/P51/P52 — durcissement du bac à sable (audit 22:59) :
    P49 : noyau récupérable — un OOM/kill condamnait toute la session ;
    P51 : les deux magasins de fichiers sont alignés (uploads injectés dans
    /mnt/uploads avant exécution) ;
    P52 : les sockets ne mentent plus + flag network_available ;
    P50 : tiktoken retiré de la liste (tables BPE non embarquées → réseau)."""
    builtin = DST / "tools" / "builtin.py"
    text = builtin.read_text(encoding="utf-8")
    if "_uploads_pour_sable(" in text:
        log("  P51/P52 helpers bac à sable : déjà appliqués")
    else:
        decl = "SANDBOX_NET_BOOTSTRAP = " + repr(SANDBOX_NET_BOOTSTRAP) + "\n"
        log("  P51/P52 helpers bac à sable : fournis par tools/android_tools.py")
        log("  P51/P52 helpers bac à sable ajoutés")
    replace_once(
        builtin,
        """                        'session_id': (__metadata__.get('session_id') if __metadata__ else None),
                        'files': (__metadata__.get('files', []) if __metadata__ else []),""",
        """                        'session_id': (__metadata__.get('session_id') if __metadata__ else None),
                        'files': ((__metadata__.get('files') or []) if __metadata__ else []) + _uploads_pour_sable(code),""",
        "P51a execute_code : uploads injectés dans /mnt/uploads",
    )
    replace_once(
        builtin,
        """        # Sanitize code (strips ANSI codes and markdown fences)
        code = sanitize_code(code)""",
        """        # Sanitize code (strips ANSI codes and markdown fences)
        code = sanitize_code(code)

        # P52 : vérité réseau (bootstrap placé en tête de code)
        code = SANDBOX_NET_BOOTSTRAP + code

        # P87 : délai d'exécution paramétrable (défaut 120 s, plafond 600 s)
        try:
            delai_exec = max(10, min(int(timeout or 120), 600))
        except Exception:
            delai_exec = 120
        journal_exec_ligne("DEBUT execute_code delai=%ss" % delai_exec)""",
        "P52a execute_code : bootstrap réseau",
    )
    replace_once(
        builtin,
        """async def execute_code(
    code: str,""",
        """async def execute_code(
    code: str,
    timeout: int = None,""",
        "P87 execute_code : paramètre timeout exposé (sinon NameError → 120 s)",
    )
    replace_once(
        builtin,
        "        engine = await Config.get('code_interpreter.engine', 'pyodide')",
        "        engine = await Config.get('code_interpreter.engine', 'pyodide')\n        journal_exec_ligne(\"P97 engine=%s\" % engine)",
        "P97 trace engine execute_code",
    )
    root = DST / "frontend" / "_app" / "immutable"
    _patch_first_match(
        str(root / "workers" / "pyodide.worker-*.js"),
        'async function j(e=[]){L||(L=$e(e)),await L,e.length>0&&self.pyodide&&await self.pyodide.pyimport("micropip").install(e)}',
        'async function j(e=[]){if(!L){L=$e(e);L.catch(()=>{L=null})}await L,e.length>0&&self.pyodide&&(e=e.filter(x=>!(x in self.pyodide.loadedPackages)),e.length>0&&await self.pyodide.pyimport("micropip").install(e))}',
        "P49a worker : init réinitialisée après échec",
    )
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        'Pe=v=>{clearTimeout(me),U.removeEventListener("message",_e),U.removeEventListener("error",Pe),F&&F(',
        'Pe=v=>{clearTimeout(me),U.removeEventListener("message",_e),U.removeEventListener("error",Pe),(()=>{try{U.terminate()}catch(e){}})(),Xt.set(null),(()=>{try{const w=rt();w.postMessage({type:"fs:sync",id:"__rewarm"})}catch(e){}})(),F&&F(',
        "P49b frontend : worker mort remplacé (onerror)",
    )
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        'F&&F(JSON.parse(JSON.stringify({stdout:u,stderr:M,result:h,files:ge.files||[]},(be,Ge)=>typeof Ge=="bigint"?Ge.toString():Ge)))',
        'ge.stderr&&/(memory access out of bounds|out of memory|null function|unreachable|wasm corrupt|Execution timeout)/i.test(ge.stderr)&&(Xt.set(null),(()=>{try{U.terminate()}catch(e){}})(),(()=>{try{const w=rt();w.postMessage({type:"fs:sync",id:"__rewarm"})}catch(e){}})()),F&&F(JSON.parse(JSON.stringify({stdout:u,stderr:M,result:h,files:ge.files||[]},(be,Ge)=>typeof Ge=="bigint"?Ge.toString():Ge)))',
        "P83 frontend : kill uniquement crash wasm + re-préchauffage",
    )
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        "if(E){const be=await Ra(E);be&&k.push({name:ge,data:be})}",
        "if(v?.data){k.push({name:ge,data:v.data})}else if(E){const be=await Ra(E);be&&k.push({name:ge,data:be})}",
        "P51b frontend : fichiers inline acceptés",
    )
    # P87 — délai d'exécution paramétrable (défaut 120 s) : une boucle infinie
    # tenait jusqu'au plafond global ; la course s'arrête proprement et le
    # noyau recyclé (stderr « Execution timeout » → P83 re-préchauffage).
    import glob as _glob2
    _cibles = sorted(_glob2.glob(str(root / "workers" / "pyodide.worker-*.js")))
    replace_once(
        Path(_cibles[0]),
        "self.result=await self.pyodide.runPythonAsync(t),self.result=R(self.result),self.result,A()",
        'self.result=await Promise.race([self.pyodide.runPythonAsync(t),new Promise((_rej)=>{'
        'self.__eto=setTimeout(()=>_rej(new Error("Execution timeout apres "+(self.exec_timeout||120)'
        '+ " s — boucle infinie ?")),Math.max(5,(self.exec_timeout||120))*1e3)})]),'
        'clearTimeout(self.__eto),self.result=R(self.result),self.result,A()',
        "P87 worker : délai d'exécution paramétrable",
    )


FALLBACK_P54 = '''        # P54 : découverte par le CONTENU — une KB mal nommée était invisible
        # (« sécurité IA open source » ne trouvait rien sur une KB « Test »).
        if query and not knowledge_bases:
            tous = await Knowledges.search_knowledge_bases(
                user_id,
                filter={'user_id': user_id, 'group_ids': user_group_ids},
                skip=0,
                limit=50,
            )
            for kb in tous.items:
                r = await Knowledges.search_files_by_id(
                    knowledge_id=kb.id, user_id=user_id,
                    filter={'query': query, 'include_content': True}, skip=0, limit=5)
                if r and r.items:
                    knowledge_bases.append({
                        'id': kb.id, 'name': kb.name,
                        'description': kb.description or '',
                        'file_count': len(r.items), 'updated_at': kb.updated_at,
                        'matched_files': len(r.items), 'source': 'content',
                    })
'''


EXTRA_TOOLS_2 = '''
async def list_files(
    query: Optional[str] = None,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    List the user's stored files (uploads, chat files, knowledge files) with their file_id —
    the missing companion of delete_file: without it, residual files cannot be found.

    :param query: Optional substring filter on file names (case-insensitive)
    :return: JSON list of files with id, filename, size, updated_at
    """
    try:
        from open_webui.models.files import Files

        user = __user__ or {}
        result = await Files.get_file_list(
            user_id=(None if user.get('role') == 'admin' else user.get('id')),
            skip=0,
            limit=200,
        )
        out = []
        q = (query or '').strip().lower()
        for f in (result.items if result else []):
            if q and q not in (f.filename or '').lower():
                continue
            meta = getattr(f, 'meta', None)
            out.append({
                'id': f.id,
                'filename': f.filename,
                'size': getattr(meta, 'size', None),
                'updated_at': f.updated_at,
            })
        return JSONCodec.dumps(out, ensure_ascii=False)
    except Exception as e:
        log.exception(f'list_files error: {e}')
        return JSONCodec.dumps({'error': str(e)})


async def delete_file(
    file_id: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Delete a file permanently by file_id (uploads, chat files, knowledge files) — irreversible.

    :param file_id: id of the file to delete
    :return: JSON confirmation of the deletion
    """
    try:
        from open_webui.models.files import Files

        f = await Files.get_file_by_id(file_id)
        if f is None:
            return JSONCodec.dumps({'error': f'Fichier introuvable : {file_id}'})
        user = __user__ or {}
        if user.get('role') != 'admin' and getattr(f, 'user_id', None) not in (None, user.get('id')):
            return JSONCodec.dumps({'error': 'Accès refusé'})
        try:
            from open_webui.storage.provider import Storage
            await asyncio.to_thread(Storage.delete_file, f.path)
        except Exception:
            pass
        try:
            from open_webui.retrieval.vector.async_client import ASYNC_VECTOR_DB_CLIENT
            await ASYNC_VECTOR_DB_CLIENT.delete(collection_name=f'file-{f.id}')
        except Exception:
            pass
        await Files.delete_file_by_id(f.id)
        return JSONCodec.dumps({'status': 'supprimé', 'id': f.id}, ensure_ascii=False)
    except Exception as e:
        log.exception(f'delete_file error: {e}')
        return JSONCodec.dumps({'error': str(e)})


async def list_tools(
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    List workspace tools and the functions they expose — to verify a creation or a deletion.

    :return: JSON list of tools with id, name, and exposed public function names (private names starting with _ are hidden)
    """
    try:
        import re as _re
        from open_webui.models.tools import Tools

        out = []
        for t in await Tools.get_tools():
            contenu = getattr(t, 'content', '') or ''
            fns = sorted(set(n for n in _re.findall(r'^\\s*(?:async )?def ([A-Za-z_]\\w*)\\s*\\(', contenu, _re.M) if not n.startswith('_')))
            out.append({'id': t.id, 'name': t.name, 'functions': fns})
        return JSONCodec.dumps(out, ensure_ascii=False)
    except Exception as e:
        log.exception(f'list_tools error: {e}')
        return JSONCodec.dumps({'error': str(e)})
'''


def patch_audit_suite() -> None:
    """P54–P59 — rapport utilisateur (outils) :
    P54 : découverte des KB par le CONTENU (une KB mal nommée était invisible ;
    fallback lexical sur les fichiers nom+contenu) ;
    P55 : search_knowledge_files cherche désormais le contenu aussi (le nom de
    l'outil promet une recherche plein texte) — même moteur normalisé que P48 ;
    P57 : write_note enregistre la lecture — « créer puis ajuster » sans
    relecture imposée ;
    P58/P59 : delete_file + list_tools (vérifiables) — rien ne permettait
    d'effacer un fichier ni de contrôler un tool créé."""
    builtin = DST / "tools" / "builtin.py"
    text = builtin.read_text(encoding="utf-8")
    if "async def delete_file(" in text:
        log("  P58/P59 delete_file/list_tools : déjà appliqué")
    else:
        log("  P58/P59 delete_file/list_tools : fournis par tools/android_tools.py")
        log("  P58/P59 outils delete_file/list_tools ajoutés")
    # P55 — moteur du modèle normalisé (search_knowledge_files agrégé)
    replace_once(
        DST / "models" / "knowledge.py",
        """                # Apply filename / content search
                search_filter = None
                if filter:
                    q = filter.get('query')
                    if q:
                        if filter.get('include_content'):
                            # Use ->> (as_string) instead of CAST(-> AS TEXT)
                            # to avoid PostgreSQL \"invalid memory alloc request
                            # size\" on large extracted-content rows (#24670).
                            content_text = File.data['content'].as_string()
                            content_text = func.substr(content_text, 1, RAG_FILE_CONTENT_SEARCH_MAX_CHARS)
                            search_filter = or_(
                                File.filename.ilike(f'%{q}%'),
                                content_text.ilike(f'%{q}%'),
                            )
                        else:
                            search_filter = File.filename.ilike(f'%{q}%')
                        stmt = stmt.filter(search_filter)""",
        '''                # Apply filename / content search
                search_filter = None
                if filter:
                    q = filter.get('query')
                    if q:
                        # P55 : normalisation espace/tiret/underscore + jetons
                        # (même moteur que search_files_by_id — P48)
                        from sqlalchemy import and_ as _and
                        import re as _re

                        def _norm(s):
                            import unicodedata
                            s = _re.sub(r'[\\s_\\-]+', ' ', (s or '').lower()).strip()
                            s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
                            return s.replace('œ', 'oe').replace('æ', 'ae')

                        def _fold_sql(expr):
                            for _src, _dst in (
                                ('é', 'e'), ('è', 'e'), ('ê', 'e'), ('ë', 'e'),
                                ('É', 'e'), ('È', 'e'), ('Ê', 'e'),
                                ('à', 'a'), ('â', 'a'), ('À', 'a'), ('Â', 'a'),
                                ('ù', 'u'), ('û', 'u'), ('ü', 'u'), ('Ù', 'u'), ('Û', 'u'),
                                ('ô', 'o'), ('Ô', 'o'), ('î', 'i'), ('ï', 'i'), ('Î', 'i'), ('Ï', 'i'),
                                ('ç', 'c'), ('Ç', 'c'), ('œ', 'oe'), ('Œ', 'oe'), ('æ', 'ae'), ('Æ', 'ae'),
                            ):
                                expr = func.replace(expr, _src, _dst)
                            return expr

                        nom_norm = _fold_sql(func.replace(func.replace(func.lower(File.filename), '-', ' '), '_', ' '))
                        jetons = [j for j in _norm(q).split(' ') if j]
                        if filter.get('include_content'):
                            # Use ->> (as_string) instead of CAST(-> AS TEXT)
                            # to avoid PostgreSQL "invalid memory alloc request
                            # size" on large extracted-content rows (#24670).
                            content_text = File.data['content'].as_string()
                            content_text = func.substr(content_text, 1, RAG_FILE_CONTENT_SEARCH_MAX_CHARS)
                            cont_norm = _fold_sql(func.replace(func.replace(func.lower(content_text), '-', ' '), '_', ' '))
                            search_filter = _and(*[
                                or_(nom_norm.like(f'%{j}%'), cont_norm.like(f'%{j}%'))
                                for j in jetons
                            ]) if jetons else True
                        else:
                            search_filter = _and(*[nom_norm.like(f'%{j}%') for j in jetons]) if jetons else True
                        stmt = stmt.filter(search_filter)''',
        "P55a search_knowledge_files (modèle) : jetons normalisés",
    )
    # P55 — les deux autres appels cherchent le contenu
    replace_once(
        builtin,
        """            result = await Knowledges.search_files_by_id(
                knowledge_id=knowledge_id,
                user_id=user_id,
                filter={'query': query},
                skip=skip,
                limit=count,
            )""",
        """            result = await Knowledges.search_files_by_id(
                knowledge_id=knowledge_id,
                user_id=user_id,
                filter={'query': query, 'include_content': True},
                skip=skip,
                limit=count,
            )""",
        "P55b search_knowledge_files : contenu recherché",
    )
    replace_once(
        builtin,
        """            result = await Knowledges.search_knowledge_files(
                filter={
                    'query': query,
                    'user_id': user_id,
                    'group_ids': user_group_ids,
                },""",
        """            result = await Knowledges.search_knowledge_files(
                filter={
                    'query': query,
                    'include_content': True,
                    'user_id': user_id,
                    'group_ids': user_group_ids,
                },""",
        "P55c search_knowledge_files : contenu (agrégé)",
    )
    # P54 — search_knowledge_bases : fallback par le contenu des fichiers.
    # ATTENTION (leçon v0.0.30) : la queue de list_knowledge_bases est
    # IDENTIQUE — un replace_once y avait injecté le fallback (variable `query`
    # non définie → crash) en laissant search_knowledge_bases sans fallback.
    # Remplacement donc CIBLÉ dans la fonction.
    text = builtin.read_text(encoding="utf-8")
    i = text.index('async def search_knowledge_bases(')
    j = text.index('\nasync def ', i + 10)
    bloc = text[i:j]
    if '# P54 : découverte par le CONTENU' in bloc:
        log("  P54a search_knowledge_bases : fallback contenu — déjà appliqué")
        PATCHES.append(("P54a search_knowledge_bases : fallback contenu", "déjà appliqué"))
    else:
        old_ret = "\n        return JSONCodec.dumps(knowledge_bases, ensure_ascii=False)"
        if bloc.count(old_ret) != 1:
            raise SystemExit("PATCH EN ÉCHEC [P54a] : queue de search_knowledge_bases ambiguë")
        bloc = bloc.replace(old_ret, "\n" + FALLBACK_P54 + old_ret, 1)
        builtin.write_text(text[:i] + bloc + text[j:], encoding="utf-8")
        log("  P54a search_knowledge_bases : fallback contenu (ciblé)")
        PATCHES.append(("P54a search_knowledge_bases : fallback contenu", "appliqué"))
    # P54 — query_knowledge_bases : idem
    replace_once(
        builtin,
        """                        'similarity': round(distance, 4),
                    }
                )

        return JSONCodec.dumps(matching_knowledge_bases, ensure_ascii=False)""",
        """                        'similarity': round(distance, 4),
                    }
                )

        # P54 : idem search_knowledge_bases — découverte par le contenu des
        # fichiers quand l'index sémantique des noms/descriptions reste muet.
        if query and not matching_knowledge_bases:
            tous = await Knowledges.search_knowledge_bases(
                user_id,
                filter={'user_id': user_id, 'group_ids': user_group_ids},
                skip=0,
                limit=50,
            )
            for kb in tous.items:
                r = await Knowledges.search_files_by_id(
                    knowledge_id=kb.id, user_id=user_id,
                    filter={'query': query, 'include_content': True}, skip=0, limit=5)
                if r and r.items:
                    matching_knowledge_bases.append({
                        'id': kb.id, 'name': kb.name,
                        'description': kb.description or '',
                        'similarity': None, 'matched_files': len(r.items),
                        'source': 'content',
                    })

        return JSONCodec.dumps(matching_knowledge_bases, ensure_ascii=False)""",
        "P54b query_knowledge_bases : fallback contenu",
    )
    # P57 — write_note : la page vient d'être écrite, on enregistre la lecture
    replace_once(
        builtin,
        """        if not new_note:
            return JSONCodec.dumps({'error': 'Failed to create note'})""",
        """        if not new_note:
            return JSONCodec.dumps({'error': 'Failed to create note'})

        # P57 : la note vient d'être écrite par l'agent — on enregistre la
        # lecture de sa page pour permettre une édition immédiate (le garde-fou
        # anti-conflit exigeait une relecture même juste après création).
        try:
            _page = get_page(new_note.data, None)
            if not hasattr(__request__.state, 'note_page_revisions'):
                __request__.state.note_page_revisions = {}
            __request__.state.note_page_revisions[(user_id, new_note.id, _page['id'])] = _page.get('revision', 0)
        except Exception:
            pass""",
        "P57 write_note : page marquée comme lue",
    )


def patch_event_timeout() -> None:
    import glob as _glob
    from pathlib import Path
    """P65/P66 — « Génération en cours… » qui ne s'arrête jamais (rapport
    utilisateur) : un appel execute_code sans réponse du bac à sable (session
    perdue, événement ignoré, démarrage interminable) laissait la conversation
    suspendue indéfiniment. P65 : délai garanti côté serveur (200 s) — l'outil
    REND TOUJOURS la main. P66 : délai frontend relevé de 60 s à 180 s (le
    premier démarrage charge numpy/pandas/sympy : 60 s tuaient les appels
    légitimes)."""
    builtin = DST / "tools" / "builtin.py"
    replace_once(
        builtin,
        "            output = await __event_call__(",
        """            # P65 : délai garanti — sans réponse du bac à sable, cet outil ne
            # rendait JAMAIS la main et la génération restait suspendue.
            # P95 : reprise après « Client session disconnected » (le réaper de
            # session, ex. WebView en arrière-plan, ne doit pas tuer l'exécution
            # — le code n'avait même pas tourné) : on ré-essaie jusqu'au retour
            # du client, dans la fenêtre garantie de 320 s.
            from open_webui.tools.android_tools import appel_avec_reprise as _appel_reprise
            try:
                output = await asyncio.wait_for(_appel_reprise(__event_call__,""",
        "P65a execute_code : wait_for + reprise (P95)",
    )
    replace_once(
        builtin,
        """            )

            # Parse the output - pyodide returns dict with stdout, stderr, result""",
        """            ), timeout=320)
            except asyncio.TimeoutError:
                journal_exec_ligne("TIMEOUT 320s : bac a sable muet")
                return JSONCodec.dumps(
                    {'error': "Délai dépassé (320 s) : le bac à sable n'a pas répondu "
                              "(démarrage ou session perdue) — réessayez, le noyau se relance."},
                    ensure_ascii=False)

            # Parse the output - pyodide returns dict with stdout, stderr, result""",
        "P65b execute_code : retour garanti après délai",
    )
    root = DST / "frontend" / "_app" / "immutable"
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        ',Xt.set(null),F&&F(JSON.parse(JSON.stringify({stdout:u,stderr:M,result:h},(v,E)=>typeof E=="bigint"?E.toString():E))))},6e4);',
        ',Xt.set(null),F&&F(JSON.parse(JSON.stringify({stdout:u,stderr:M,result:h},(v,E)=>typeof E=="bigint"?E.toString():E))))},Math.max(5,TO||120)*1e3);',
        "P87 frontend : délai d'exécution paramétré (TO)",
    )
    replace_once(
        Path(sorted(_glob.glob(str(root / "nodes" / "0.*.js")))[0]),
        'M="Execution Time Limit Exceeded"',
        'M="Execution timeout apres "+(TO||120)+" s — boucle infinie ?"',
        "P87 frontend : message de délai explicite",
    )


def patch_prewarm() -> None:
    """P70/P71 — execute_code « bloquait » : le PREMIER appel monte le runtime
    wasm (numpy/pandas/sympy au boot) et paie les transferts de fichiers.
    P70 : le worker est créé et booté AU CHARGEMENT DE LA PAGE (message fs:sync
    qui déclenche l'init en tâche de fond) — au moment de l'appel, le bac à
    sable est déjà chaud.
    P71 : le worker ne renvoie plus les fichiers d'ENTRÉE (déjà côté serveur)
    et plafonne la remontée (8 Mo/fichier, 16 Mo total)."""
    root = DST / "frontend" / "_app" / "immutable"
    _patch_first_match(
        str(root / "nodes" / "0.*.js"),
        ",Me=async(t,i,F,P=[],X=[])=>{",
        ',__prewarm=(()=>{try{const w=rt();w.postMessage({type:"fs:sync",id:"__prewarm"})}catch(e){}})(),Me=async(t,i,F,P=[],X=[],TO=120)=>{',
        "P70 préchauffage du bac à sable au démarrage",
    )
    _patch_first_match(
        str(root / "workers" / "pyodide.worker-*.js"),
        "async function He(e,t,r){self.stdout=null",
        "async function He(e,t,r){self.__inNames=(r||[]).map(x=>x.name);self.__snap={};try{for(const n of self.pyodide.FS.readdir('/mnt/uploads')){if(n==='.'||n==='..')continue;const st=self.pyodide.FS.stat('/mnt/uploads/'+n);self.__snap[n]=String(st.size)+'@'+String(Math.floor(st.mtimeMs))}}catch(x){}self.stdout=null",
        "P71a worker : entrées + instantané avant exécution",
    )


def patch_execute_code_gate() -> None:
    """P72 — RÉVOQUÉ (utilisateur 2026-11-09) : le toggle « capacités » de la
    requête est le mécanisme CORRECT et voulu (activé → outils visibles) ;
    forcer l'exposition s'écartait de l'origine. Rien à patcher ici."""
    log("  P72 : révoqué — le toggle de la requête est le mécanisme voulu")
    # P76 — create_tool : documenter le comportement amont (tool_ids envoyé par
    # le client à chaque complétion : un tool créé doit être ATTACHÉ à la
    # conversation pour être invocable — audit 2026-11-09, A4).
    replace_once(
        DST / "tools" / "builtin.py",
        "    Use Valves or UserValves for credentials; do not embed secrets. Saving executes the Python module on the server.",
        "    Use Valves or UserValves for credentials; do not embed secrets. Saving executes the Python module on the server.\n    Its functions become callable only where the tool is ATTACHED (chat or model tools) — attach it to this chat to invoke it now, or use a new chat.",
        "P76 create_tool : invocation documentée",
    )


def patch_sandbox_boot() -> None:
    """P82 — le bootstrap (network_available, sockets qui échouent proprement)
    s'exécutait au PREMIER appel : la sonde réseau y ajoutait son coût. Il est
    désormais lancé AU BOOT du bac à sable — donc pendant le préchauffage —
    et le prepend par appel devient un no-op."""
    import glob as _glob
    import json as _json

    cibles = sorted(_glob.glob(str(DST / "frontend" / "_app" / "immutable" / "workers" / "pyodide.worker-*.js")))
    if not cibles:
        raise SystemExit("PATCH EN ÉCHEC [P82] : worker pyodide introuvable")
    boot_js = _json.dumps(SANDBOX_NET_BOOTSTRAP)
    Q = chr(34)  # guillemet double pour les littéraux JS
    replace_once(
        Path(cibles[0]),
        'pyimport("micropip").install(e)}async function j(',
        'pyimport("micropip").install(e);try{await self.pyodide.runPythonAsync(' + boot_js + ');let _n=false;try{const _r=await fetch(' + Q + 'https://httpbin.org/get' + Q + ',{signal:AbortSignal.timeout(3000)});_n=_r.status>0}catch(_x){}self.pyodide.globals.set("network_available",_n)}catch(x){}}async function j(',
        "P82 worker : bootstrap réseau au boot",
    )


def patch_search_timeout() -> None:
    """P68 — « les outils semblent bloqués » (rapport utilisateur) : la requête
    de search_searxng n'avait AUCUN timeout — si l'instance SearXNG embarquée
    traîne (ses moteurs interrogent le web), search_web attendait le défaut
    d'aiohttp (5 min) voire indéfiniment. Délai explicite : 30 s."""
    replace_once(
        DST / "retrieval" / "web" / "searxng.py",
        """    async with session.get(
        query_url,
        headers=_SEARXNG_HEADERS,
        params=params,
        ssl=_get_ssl_context(),
    ) as response:""",
        """    async with session.get(
        query_url,
        headers=_SEARXNG_HEADERS,
        params=params,
        ssl=_get_ssl_context(),
        timeout=30,
    ) as response:""",
        "P68 search_searxng : timeout 30s",
    )


def patch_web_main_content() -> None:
    """P74 — fetch_url renvoyait la page BRUTE (menus, navigation) alors que le
    contrat promet « le contenu principal » (audit 2026-11-09, A3). Quand la
    page expose des balises sémantiques (<main>, <article>, [role=main]) avec
    du contenu réel, on extrait celles-ci ; sinon comportement amont inchangé."""
    replace_once(
        DST / "retrieval" / "web" / "utils.py",
        """        soup = BeautifulSoup(html, parser, **self.bs_kwargs)
        return Document(
            page_content=soup.get_text(**self.bs_get_text_kwargs),""",
        """        soup = BeautifulSoup(html, parser, **self.bs_kwargs)
        # P74 : contenu principal quand la page est balisée sémantiquement
        for _sel in ('main', 'article', '[role="main"]'):
            _bloc = soup.select_one(_sel)
            if _bloc and len(_bloc.get_text(strip=True)) > 50:
                soup = _bloc
                break
        return Document(
            page_content=soup.get_text(**self.bs_get_text_kwargs),""",
        "P74 fetch_url : extraction du contenu principal",
    )


def patch_event_session_fallback() -> None:
    """P84 — « Client session disconnected. » (audit 2026-11-09) : le réaper du
    SESSION_POOL supprime une session après 120 s sans heartbeat — les timers
    du WebView se figeant en arrière-plan (sous-agent long), la session du
    navigateur est effacée et TOUT execute_code devient impossible jusqu'au
    rechargement de la page. Repli : on vise la session VIVANTE de
    l'utilisateur (même mécanisme que la reprise) et on aligne l'identifiant
    porté par l'événement (exigé par le frontend)."""
    replace_once(
        DST / "socket" / "main.py",
        """        # session_id is client-supplied; only the requesting user's own live session may be targeted.
        session = SESSION_POOL.get(session_id)
        if session is None or session.get('id') != request_info.get('user_id'):
            log.warning(f'Event caller: session {session_id} not owned by requesting user or disconnected')
            return {'error': 'Client session disconnected.'}""",
        """        # session_id is client-supplied; only the requesting user's own live session may be targeted.
        session = SESSION_POOL.get(session_id)
        # P84 : session expirée (réaper après 120 s sans heartbeat, ex. WebView
        # en arrière-plan) ou synthétique (sous-agent) — au lieu de couper les
        # outils (execute_code « Client session disconnected »), on replie sur
        # la session VIVANTE de l'utilisateur et on aligne l'identifiant de
        # l'événement (le frontend l'exige pour traiter la réponse).
        if session is None or session.get('id') != request_info.get('user_id'):
            repli = await asyncio.to_thread(
                get_user_chat_session_id, request_info['user_id'], request_info['chat_id']
            )
            if not repli or get_user_id_from_session_pool(repli) != request_info['user_id']:
                for _sid in get_session_ids_by_user_ids([request_info['user_id']]):
                    if get_user_id_from_session_pool(_sid) == request_info['user_id']:
                        repli = _sid
                        break
            if repli and get_user_id_from_session_pool(repli) == request_info['user_id']:
                session_id = request_info['session_id'] = repli
                session = SESSION_POOL.get(session_id)
                if 'session_id' in (event_data.get('data') or {}):
                    event_data = {
                        **event_data,
                        'data': {**event_data['data'], 'session_id': session_id},
                    }
        if session is None or session.get('id') != request_info.get('user_id'):
            log.warning(f'Event caller: session {session_id} not owned by requesting user or disconnected')
            return {'error': 'Client session disconnected.'}""",
        "P84 event_call : repli sur la session vivante",
    )
    replace_once(
        DST / "socket" / "main.py",
        """    async def __event_caller__(event_data):
        session_id = request_info['session_id']""",
        """    async def __event_caller__(event_data):
        session_id = request_info['session_id']
        # P99 diagnostic session (écrit directement dans exec.log)
        try:
            from open_webui.android_logs import journal_exec as _jd
            _jd("P99 sid=%s uid=%s pool=%s" % (
                str(request_info.get('session_id'))[:10],
                str(request_info.get('user_id'))[:10],
                sorted(str(k)[:10] for k in SESSION_POOL.keys())))
        except Exception:
            pass""",
        "P99 diagnostic session event_call",
    )
    replace_once(
        DST / "env.py",
        """WEBSOCKET_SERVER_PING_TIMEOUT = os.getenv('WEBSOCKET_SERVER_PING_TIMEOUT', '20')
try:
    WEBSOCKET_SERVER_PING_TIMEOUT = int(WEBSOCKET_SERVER_PING_TIMEOUT)
except ValueError:
    WEBSOCKET_SERVER_PING_TIMEOUT = 20""",
        """# P100 : le ping_timeout=20 s déconnectait le client quand il chargeait
# Pyodide (> 20 s sans pong) → session supprimée → « Client session
# disconnected ». On tolère un client occupé pendant le chargement.
WEBSOCKET_SERVER_PING_TIMEOUT = os.getenv('WEBSOCKET_SERVER_PING_TIMEOUT', '300')
try:
    WEBSOCKET_SERVER_PING_TIMEOUT = int(WEBSOCKET_SERVER_PING_TIMEOUT)
except ValueError:
    WEBSOCKET_SERVER_PING_TIMEOUT = 300""",
        "P100 socket : ping_timeout tolérant au chargement Pyodide",
    )


def patch_search_files() -> None:
    """P48 — search_knowledge_files (audit 22:59) : le matching était un ILIKE
    SQL brut — « rapport vulnerabilites » ne trouvait jamais
    « rapport-vulnerabilites.json » (espace ≠ tiret), et le nom de la base
    n'était pas cherché. Normalisation espace/tiret/underscore + tous les
    jetons requis + recherche étendue au nom de la base."""
    replace_once(
        DST / "models" / "knowledge.py",
        """                if filter:
                    query_key = filter.get('query')
                    if query_key:
                        if filter.get('include_content'):""",
        """                if filter:
                    query_key = filter.get('query')
                    if query_key:
                        # P48 : normalisation espace/tiret/underscore + jetons
                        # (audit : « rapport vulnerabilites » ne trouvait pas
                        # « rapport-vulnerabilites.json » ; chaque jeton doit
                        # être présent, le tiret/espace/underscore sont équivalents)
                        from sqlalchemy import and_ as _and
                        import re as _re

                        def _norm(s):
                            import unicodedata
                            s = _re.sub(r'[\\s_\\-]+', ' ', (s or '').lower()).strip()
                            s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
                            return s.replace('œ', 'oe').replace('æ', 'ae')

                        def _fold_sql(expr):
                            # P73 : SQLite ignore les accents dans lower() —
                            # repli explicite des diacritiques français.
                            for _src, _dst in (
                                ('é', 'e'), ('è', 'e'), ('ê', 'e'), ('ë', 'e'),
                                ('É', 'e'), ('È', 'e'), ('Ê', 'e'),
                                ('à', 'a'), ('â', 'a'), ('À', 'a'), ('Â', 'a'),
                                ('ù', 'u'), ('û', 'u'), ('ü', 'u'), ('Ù', 'u'), ('Û', 'u'),
                                ('ô', 'o'), ('Ô', 'o'), ('î', 'i'), ('ï', 'i'), ('Î', 'i'), ('Ï', 'i'),
                                ('ç', 'c'), ('Ç', 'c'), ('œ', 'oe'), ('Œ', 'oe'), ('æ', 'ae'), ('Æ', 'ae'),
                            ):
                                expr = func.replace(expr, _src, _dst)
                            return expr

                        nom_norm = _fold_sql(func.replace(func.replace(func.lower(File.filename), '-', ' '), '_', ' '))
                        jetons = [j for j in _norm(query_key).split(' ') if j]
                        if filter.get('include_content'):""",
        "P48a search_files_by_id : normalisation des jetons",
    )
    replace_once(
        DST / "models" / "knowledge.py",
        """                            content_text = File.data['content'].as_string()
                            content_text = func.substr(content_text, 1, RAG_FILE_CONTENT_SEARCH_MAX_CHARS)
                            stmt = stmt.filter(
                                or_(
                                    File.filename.ilike(f'%{query_key}%'),
                                    content_text.ilike(f'%{query_key}%'),
                                )
                            )
                        else:
                            stmt = stmt.filter(File.filename.ilike(f'%{query_key}%'))""",
        """                            content_text = File.data['content'].as_string()
                            content_text = func.substr(content_text, 1, RAG_FILE_CONTENT_SEARCH_MAX_CHARS)
                            cont_norm = _fold_sql(func.replace(func.replace(func.lower(content_text), '-', ' '), '_', ' '))
                            stmt = stmt.filter(
                                _and(*[
                                    or_(nom_norm.like(f'%{j}%'), cont_norm.like(f'%{j}%'))
                                    for j in jetons
                                ]) if jetons else True
                            )
                        else:
                            stmt = stmt.filter(
                                _and(*[nom_norm.like(f'%{j}%') for j in jetons]) if jetons else True
                            )""",
        "P48b search_files_by_id : matching par jetons normalisés",
    )
    replace_once(
        DST / "tools" / "builtin.py",
        """                result = await Knowledges.search_files_by_id(
                    knowledge_id=kb_id,
                    user_id=user_id,
                    filter={'query': query},
                    skip=0,
                    limit=count + skip,
                )""",
        """                # P48 : si la requête correspond au NOM de la base, toute sa
                # liste est pertinente (la recherche ne visait que les noms de
                # fichiers — audit 2026-11-08).
                q_norm = ' '.join((query or '').lower().replace('-', ' ').replace('_', ' ').split())
                k_norm = ' '.join((knowledge.name or '').lower().replace('-', ' ').replace('_', ' ').split())
                result = await Knowledges.search_files_by_id(
                    knowledge_id=kb_id,
                    user_id=user_id,
                    filter={'query': '' if (q_norm and q_norm in k_norm) else query, 'include_content': True},
                    skip=0,
                    limit=count + skip,
                )""",
        "P48c search_knowledge_files : nom de la base recherché",
    )


def patch_pyodide_packages() -> None:
    """P38 — paquets scientifiques garantis au démarrage du bac à sable Pyodide.
    Le worker ne préinstallait que micropip : numpy/pandas/sympy (wheels déjà
    embarqués + lock offline) n'étaient disponibles que si la détection regex
    d'import réussissait — constat d'audit : ModuleNotFoundError systématiques.
    On les charge au boot via le mécanisme locké de loadPyodide."""
    import glob as _glob

    cibles = sorted(
        _glob.glob(str(DST / "frontend" / "_app" / "immutable" / "workers" / "pyodide.worker-*.js"))
    )
    if not cibles:
        raise SystemExit("PATCH EN ÉCHEC [P38] : worker pyodide introuvable")
    for cible in cibles:
        replace_once(
            Path(cible),
            'packages:["micropip"]',
            'packages:["micropip","numpy","pandas","sympy"]',
            "P38 pyodide : numpy/pandas/sympy au démarrage",
        )


def patch_pyodide_worker_boot() -> None:
    """P103 — boot ALLÉGÉ du worker Pyodide (la copie RÉELLEMENT exécutée).
    P38 préinstallait numpy/pandas/sympy au boot = ~115 Mo de wasm d'un coup →
    le lowmemorykiller Android tuait/bloquait le worker (« disconnected before
    answering »), et le thread saturé ne pouvait même pas exécuter le timer de
    secours P99b. P102 (v0.0.53) n'avait allégé que la copie de repli
    (chunks/*.js — patch_pyodide_universel) : le worker embarqué gardait le boot
    lourd. Correctif ciblant le worker : boot ['micropip','numpy'], pandas/sympy
    en chargement à la demande (j(self.packages) les installe si le code les
    importe)."""
    import glob as _glob

    cibles = sorted(
        _glob.glob(str(DST / "frontend" / "_app" / "immutable" / "workers" / "pyodide.worker-*.js"))
    )
    if not cibles:
        raise SystemExit("PATCH EN ÉCHEC [P103] : worker pyodide introuvable")
    for cible in cibles:
        replace_once(
            Path(cible),
            'packages:["micropip","numpy","pandas","sympy"]',
            'packages:["micropip","numpy"]',
            "P103 pyodide worker : boot allégé (pandas/sympy à la demande)",
        )


def patch_p104_diag() -> None:
    """P104 — diagnostic de la livraison des appels outils (« execute_code muet »).
    Constats (2026-11-10) : sio.call(to=sid) ne livre JAMAIS le paquet dans l'app
    (3 clients testés : navigateur, client python — les émissions de room arrivent,
    les ciblées par sid non) alors que le même module fonctionne hors Android.
    On instrumente : (1) tout paquet EVENT avec id d'ack remis à la couche
    transport + ses erreurs, (2) l'état réel des participants au moment de
    l'appel, (3) les raisons de déconnexion, (4) les échecs d'auth socket — et
    une route /fm/diag/eventcall exécute execute:python depuis l'app elle-même
    pour tester la chaîne complète à la demande."""
    # 1 — traçage des envois (après la création de sio)
    replace_once(
        DST / "socket" / "main.py",
        "# Timeout duration in seconds\nTIMEOUT_DURATION = 3",
        """# P104 — traçage des envois de paquets EVENT avec id d'ack (appels outils) :
# toute la chaîne est saine en analyse statique ; on voit enfin si le paquet est
# remis au transport et s'il l'est avec le bon eio_sid.
try:
    _p104_orig_send = sio._send_packet

    async def _p104_send_packet(eio_sid, pkt):
        try:
            if getattr(pkt, 'packet_type', None) == 2 and getattr(pkt, 'id', None) is not None:
                from open_webui.android_logs import journal_exec as _jd
                _jd("P104 SEND eio=%s id=%s" % (str(eio_sid)[-6:], pkt.id))
        except Exception:
            pass
        try:
            return await _p104_orig_send(eio_sid, pkt)
        except Exception as _e:
            try:
                from open_webui.android_logs import journal_exec as _jd
                _jd("P104 SEND-ERREUR eio=%s %s" % (str(eio_sid)[-6:], _e))
            except Exception:
                pass
            raise

    sio._send_packet = _p104_send_packet
except Exception:
    pass

# Timeout duration in seconds
TIMEOUT_DURATION = 3""",
        "P104 traçage des envois outils",
    )
    # 2 — raison de déconnexion
    replace_once(
        DST / "socket" / "main.py",
        """@sio.event
async def disconnect(sid, reason=None):
    await encryption.disconnect(sid)""",
        """@sio.event
async def disconnect(sid, reason=None):
    log.warning('P104 disconnect sid=%s reason=%s', str(sid)[-6:], reason)
    await encryption.disconnect(sid)""",
        "P104 raison de déconnexion",
    )
    # 3 — échec d'authentification socket (déconnecte la session)
    replace_once(
        DST / "socket" / "main.py",
        """    except Exception:
        log.debug('Socket authentication expired for %s', sid)
    LOCAL_AUTHENTICATED_SIDS.discard(sid)""",
        """    except Exception:
        log.warning('P104 auth socket echouee (exception) sid=%s', str(sid)[-6:])
        log.debug('Socket authentication expired for %s', sid)
    else:
        log.warning('P104 auth socket refusee sid=%s', str(sid)[-6:])
    LOCAL_AUTHENTICATED_SIDS.discard(sid)""",
        "P104 échec auth socket",
    )
    # 4 — état des participants au moment de l'appel (après la trace P99)
    replace_once(
        DST / "socket" / "main.py",
        """                sorted(str(k)[:10] for k in SESSION_POOL.keys())))
        except Exception:
            pass""",
        """                sorted(str(k)[:10] for k in SESSION_POOL.keys())))
        except Exception:
            pass
        # P104 — les participants RÉELS du manager au moment de l'appel
        try:
            from open_webui.android_logs import journal_exec as _jd
            _parts = []
            try:
                _parts = [(str(a)[-6:], str(b)[-6:]) for a, b in
                          sio.manager.get_participants('/', str(request_info.get('session_id')))]
            except Exception as _e:
                _parts = ['err:%s' % _e]
            _jd("P104 ETAT sid=%s participants=%s" % (
                str(request_info.get('session_id'))[-6:], _parts))
        except Exception:
            pass""",
        "P104 état des participants à l'appel",
    )


def patch_typst_tool() -> None:
    """P11 — outil « compile_typst » (.typ → PDF) dans les outils embarqués."""
    builtin = DST / "tools" / "builtin.py"
    text = builtin.read_text(encoding="utf-8")
    if "async def compile_typst(" in text:
        log("  P11 compile_typst: déjà appliqué")
    else:
        log("  P11 compile_typst : fourni par tools/android_tools.py")
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


DELETE_TOOLS = '''
async def delete_note(
    note_id: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Delete a note permanently (irreversible).

    :param note_id: id of the note to delete
    :return: JSON confirmation of the deletion
    """
    try:
        from open_webui.models.notes import Notes

        note = await Notes.get_note_by_id(note_id)
        if note is None:
            return JSONCodec.dumps({'error': f'Note introuvable : {note_id}'})
        user = __user__ or {}
        if user.get('role') != 'admin' and getattr(note, 'user_id', None) not in (None, user.get('id')):
            return JSONCodec.dumps({'error': 'Accès refusé'})
        ok = await Notes.delete_note_by_id(note_id)
        return JSONCodec.dumps(
            {'status': 'supprimée' if ok else 'erreur', 'id': note_id}, ensure_ascii=False)
    except Exception as e:
        log.exception(f'delete_note error: {e}')
        return JSONCodec.dumps({'error': str(e)})


async def delete_skill(
    skill_id: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Delete a private skill permanently (irreversible).

    :param skill_id: id of the skill to delete
    :return: JSON confirmation of the deletion
    """
    try:
        from open_webui.models.skills import Skills

        skill = await Skills.get_skill_by_id(skill_id)
        if skill is None:
            return JSONCodec.dumps({'error': f'Skill introuvable : {skill_id}'})
        user = __user__ or {}
        if user.get('role') != 'admin' and getattr(skill, 'user_id', None) not in (None, user.get('id')):
            return JSONCodec.dumps({'error': 'Accès refusé'})
        ok = await Skills.delete_skill_by_id(skill_id)
        return JSONCodec.dumps(
            {'status': 'supprimé' if ok else 'erreur', 'id': skill_id}, ensure_ascii=False)
    except Exception as e:
        log.exception(f'delete_skill error: {e}')
        return JSONCodec.dumps({'error': str(e)})


async def delete_tool(
    tool_id: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Delete a custom tool permanently, freeing its id (irreversible).

    :param tool_id: id of the tool to delete
    :return: JSON confirmation of the deletion
    """
    try:
        from open_webui.models.tools import Tools

        tool = await Tools.get_tool_by_id(tool_id)
        if tool is None:
            return JSONCodec.dumps({'error': f'Outil introuvable : {tool_id}'})
        user = __user__ or {}
        if user.get('role') != 'admin' and getattr(tool, 'user_id', None) not in (None, user.get('id')):
            return JSONCodec.dumps({'error': 'Accès refusé'})
        await Tools.delete_tool_by_id(tool_id)
        return JSONCodec.dumps(
            {'status': 'supprimé', 'id': tool_id}, ensure_ascii=False)
    except Exception as e:
        log.exception(f'delete_tool error: {e}')
        return JSONCodec.dumps({'error': str(e)})
'''

PROBE_HELPER = '''
def _probe_fetch_url(url: str, verify_ssl: bool = True, max_hops: int = 5):
    """P33 — sonde HTTP légère qui renvoie (statut final, URL finale, chaîne de
    redirections). Les redirections sont suivies saut par saut avec ré-validation
    SSRF (validate_url) — jamais de contournement de la garde anti-SSRF."""
    from urllib.parse import urljoin
    from open_webui.retrieval.web.utils import (
        WEB_LOADER_HEADERS, validate_url, get_ssrf_safe_requests_session,
    )

    chaine = [url]
    courante = url
    statut = 0
    for _ in range(max_hops):
        try:
            validate_url(courante)
            session = get_ssrf_safe_requests_session()
            session.headers = WEB_LOADER_HEADERS
            session.verify = True if verify_ssl is None else verify_ssl
            r = session.get(courante, stream=True, timeout=30, allow_redirects=False)
        except Exception as exc:
            return 0, courante, chaine + [f'ERREUR: {exc}']
        statut = r.status_code
        loc = r.headers.get('Location')
        r.close()
        if statut in (301, 302, 303, 307, 308) and loc:
            courante = urljoin(courante, loc)
            chaine.append(courante)
            continue
        return statut, courante, chaine
    return statut, courante, chaine + ['ERREUR: trop de redirections']
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
    patch_files_mnt_alias()
    patch_files_button()
    write_android_tools()
    write_android_logs()
    patch_typst_tool()
    patch_delete_tools()
    patch_tool_status()
    patch_memory_search()
    patch_memory_recall()
    patch_kb_backfill()
    patch_pyodide_packages()
    patch_pyodide_worker_boot()
    patch_pyodide_universel()
    patch_extra_wheels()
    patch_pyodide_detection()
    patch_automation_rrule()
    patch_upload_harvest()
    patch_note_newlines()
    patch_search_files()
    patch_search_timeout()
    patch_execute_code_gate()
    patch_web_main_content()
    patch_event_session_fallback()
    patch_p104_diag()
    patch_prewarm()
    patch_sandbox_boot()
    patch_audit_suite()
    patch_event_timeout()
    patch_sandbox_hardening()
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
    # Vérification finale : les patchs sont-ils bien appliqués dans le code généré ?
    import subprocess
    import sys as _sys

    verif = subprocess.run([_sys.executable, str(PROJ / "scripts" / "check_patches.py")])
    if verif.returncode != 0:
        raise SystemExit("check_patches.py : des patchs sont mal appliqués")
    return 0


if __name__ == "__main__":
    sys.exit(main())
