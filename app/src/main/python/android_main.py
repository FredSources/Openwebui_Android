"""android_main.py — point d'entrée Python de l'APK (appelé par MainActivity).

Prépare l'environnement (données dans le stockage privé de l'app, clé secrète
persistée, chemins du frontend embarqué) puis lance le serveur Open WebUI dans
un thread daemon sur 127.0.0.1. Idempotent : plusieurs appels ne lancent
qu'un seul serveur.
"""
from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from pathlib import Path

log = logging.getLogger("android_main")

_lock = threading.Lock()
_started = False

APP_PORT = 8080


_uvicorn_server = None
_searx_httpd = None


def _load_env_file(data_dir: Path, override: bool = False) -> None:
    """Charge `data/openwebui.env` (KEY=VALUE) AVANT l'import d'open_webui.

    Sert à configurer le RAG par services distants sans rebuilder l'APK, ex. :
        VECTOR_DB=qdrant
        QDRANT_URI=https://xxx.cloud.qdrant.io
        QDRANT_API_KEY=...
        RAG_EMBEDDING_ENGINE=openai
        RAG_OPENAI_API_BASE_URL=https://api.openai.com/v1
        RAG_OPENAI_API_KEY=sk-...
    Les valeurs déjà présentes dans l'environnement ne sont pas écrasées.
    """
    env_file = data_dir / "openwebui.env"
    if not env_file.exists():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key in ("DATA_DIR", "HOME"):
                continue  # pilotés par l'application, jamais par le fichier
            if override:
                os.environ[key] = value.strip()
            else:
                os.environ.setdefault(key, value.strip())
        log.info("variables chargées depuis %s", env_file)
    except Exception as exc:
        log.warning("lecture de %s impossible : %s", env_file, exc)


def _set_status(data_dir: Path, message: str, progress: int | None = None) -> None:
    """Écrit l'étape courante au format « PCT|message » (barre de progression UI)."""
    try:
        (data_dir / 'startup-status.txt').write_text(
            f'{progress if progress is not None else "?"}|{message}', encoding='utf-8'
        )
    except Exception:
        pass


def _prepare_env(files_dir: str | None = None) -> Path:
    """Variables d'environnement Open WebUI pour Android (avant tout import du package).

    Garantie d'isolation : TOUT fichier (base, uploads, cache, temporaires) est
    écrit dans l'espace privé de l'application — <files>/data, <files>/tmp,
    <files>/cache — où <files> est getFilesDir() fourni par MainActivity.
    """
    import open_webui  # noqa: F401  (le paquet doit être localisable)
    pkg_dir = Path(open_webui.__file__).parent

    # files_dir (getFilesDir()) est prioritaire sur HOME : aucune écriture ne
    # doit dépendre d'un HOME implicite du runtime.
    home = Path(files_dir or os.environ.get("HOME") or pkg_dir.parent).resolve()
    home.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(home)  # forcé (et non setdefault) pour tous les importeurs
    for sub, var in (("tmp", "TMPDIR"), ("cache", "XDG_CACHE_HOME")):
        d = home / sub
        d.mkdir(parents=True, exist_ok=True)
        os.environ[var] = str(d)

    data_dir = home / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Réinitialisation complète demandée depuis /fm : efface TOUTES les données
    # (base, uploads, vecteurs, cache) puis repart de zéro.
    if (data_dir / "reset-requested").exists():
        import shutil as _sh

        log.warning("réinitialisation complète demandée : effacement des données…")
        for enfant in data_dir.iterdir():
            try:
                if enfant.is_dir():
                    _sh.rmtree(enfant)
                else:
                    enfant.unlink()
            except Exception:
                pass

    # configuration utilisateur (RAG distant, etc.) — avant toute lecture d'env
    _load_env_file(data_dir)

    os.environ.setdefault("DATA_DIR", str(data_dir))
    # P44 — le bac à sable Pyodide DOIT passer par le worker (et non l'iframe
    # par défaut) : seul le worker embarque les paquets scientifiques au boot
    # (P38), la persistance /mnt/uploads (IDBFS) et la remontée des fichiers
    # (P41). Sans ça : ModuleNotFoundError systématiques côté appareil.
    os.environ.setdefault("ENABLE_PYODIDE_FILE_PERSISTENCE", "true")
    log.warning("espace applicatif : HOME=%s DATA_DIR=%s", home, data_dir)
    # Frontend : extrait par MainActivity dans $HOME/frontend (assets, versionné) ;
    # repli sur le paquet Python pour les tests hôte.
    extracted = Path(home) / "frontend"
    os.environ.setdefault(
        "FRONTEND_BUILD_DIR",
        str(extracted if extracted.is_dir() else pkg_dir / "frontend"),
    )
    os.environ.setdefault("STATIC_DIR", str(pkg_dir / "static"))
    os.environ.setdefault("USE_CUDA_DOCKER", "false")
    os.environ.setdefault("ENABLE_OTEL", "false")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
    os.environ.setdefault("DO_NOT_TRACK", "true")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    # Clé secrète : générée une fois, persistée (sessions, chiffrement OAuth)
    secret_file = data_dir / "webui_secret_key"
    if not secret_file.exists() or secret_file.stat().st_size == 0:
        secret_file.write_text(secrets.token_urlsafe(48))
    os.environ.setdefault("WEBUI_SECRET_KEY", secret_file.read_text().strip())

    # Dictée : moteur STT « web » par défaut (→ SpeechRecognition, branché sur le
    # moteur vocal natif Android par le shim JS de MainActivity). L'utilisateur
    # peut basculer sur un STT distant dans Réglages → Audio.
    os.environ.setdefault("AUDIO_STT_ENGINE", "web")
    _force_config_value(data_dir, "audio.stt.engine", "web")

    # Recherche web : provider « embedded-searxng » (SearXNG local embarqué).
    # also_replace : migration de l'ancienne typo « embeded-searxng ».
    os.environ.setdefault("WEB_SEARCH_ENGINE", "embedded-searxng")
    _force_config_value(
        data_dir, "web.search.engine", "embedded-searxng",
        also_replace=("embeded-searxng",),
    )

    # Outils internet : ENABLE_WEB_SEARCH défaut à 'False' en amont, ce qui masque
    # les outils search_web/fetch_url ET coupe le pipeline de recherche du chat.
    # Forcé à true : la recherche web est une fonctionnalité centrale de l'app.
    os.environ.setdefault("ENABLE_WEB_SEARCH", "true")
    _force_config_value(
        data_dir, "web.search.enable", True,
        also_replace=("false", "False", "0"),
    )

    # Interpréteur de code : Pyodide (WASM) restauré dans le frontend (P23) —
    # execute_code exécute le Python dans le navigateur (analyse CSV/Excel/PDF,
    # calculs, graphiques). Activé par défaut.
    os.environ.setdefault("ENABLE_CODE_INTERPRETER", "true")
    _force_config_value(
        data_dir, "code_interpreter.enable", True,
        also_replace=("false", "False"),
    )

    # SearXNG embarqué : réglages locaux (clé secrète propre à l'appareil)
    _ensure_searxng_settings(data_dir)
    return data_dir

    # Point d'entrée LLM distant — modifiable via l'appli (Réglages → Connexions)
    os.environ.setdefault("OLLAMA_BASE_URL", os.environ.get("OLLAMA_BASE_URL", ""))
    os.environ.setdefault("ENABLE_OLLAMA_API", os.environ.get("ENABLE_OLLAMA_API", "true"))


def _force_config_value(data_dir: Path, key: str, value, also_replace: tuple = ()) -> None:
    """Force une valeur de config en base si la clé est absente, vide, ou obsolète.

    `value` est sérialisé en JSON (`str` → chaîne, `bool` → vrai booléen JSON).
    Les réglages sont stockés dans la table `config` (JSON) : les valeurs déjà
    semées ('') ne sont pas remplacées par la simple variable d'environnement.
    `also_replace` liste les anciennes valeurs à migrer (ex. typo « embeded »).
    Écrit en SQLite direct, avant le démarrage du serveur (pas de course).
    """
    import json
    import sqlite3
    import time

    db_path = data_dir / "webui.db"
    if not db_path.exists():
        return  # premier lancement : la seed prendra la valeur d'env
    try:
        con = sqlite3.connect(db_path, timeout=5)
        try:
            row = con.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
            current = None
            if row is not None:
                try:
                    current = json.loads(row[0])
                except Exception:
                    current = row[0]
            if not current or current in also_replace:
                now = int(time.time())
                if row is None:
                    con.execute(
                        "INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                        (key, json.dumps(value), now),
                    )
                else:
                    con.execute(
                        "UPDATE config SET value=?, updated_at=? WHERE key=?",
                        (json.dumps(value), now, key),
                    )
                con.commit()
                if current in also_replace:
                    log.info("config %s migré : %r → %r", key, current, value)
                else:
                    log.info("config %s forcé à %r", key, value)
        finally:
            con.close()
    except Exception as exc:  # table absente, DB verrouillée… : non bloquant
        log.warning("force config %s impossible : %s", key, exc)


SEARXNG_PORT = 8888

SEARXNG_SETTINGS_TEMPLATE = """\
# Généré par android_main.py — instance SearXNG embarquée (locale, privée).
use_default_settings: true
server:
  secret_key: "{secret}"
  bind_address: "127.0.0.1"
  port: {port}
  limiter: false
  public_instance: false
search:
  formats:
    - html
    - json
"""


def _ensure_searxng_settings(data_dir: Path) -> Path:
    """Écrit les réglages SearXNG de l'appareil (clé secrète propre à l'app)."""
    import secrets as _secrets

    path = data_dir / "searxng-settings.yml"
    if not path.exists():
        path.write_text(
            SEARXNG_SETTINGS_TEMPLATE.format(secret=_secrets.token_urlsafe(32), port=SEARXNG_PORT),
            encoding="utf-8",
        )
        log.info("réglages SearXNG générés : %s", path)
    os.environ.setdefault("SEARXNG_SETTINGS_PATH", str(path))
    return path


def _start_searxng() -> None:
    """Lance l'instance SearXNG embarquée sur 127.0.0.1:8888 (thread daemon)."""

    def run() -> None:
        try:
            from socketserver import ThreadingMixIn
            from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

            class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
                daemon_threads = True

            from searx.webapp import application

            httpd = make_server(
                "127.0.0.1",
                SEARXNG_PORT,
                application,
                server_class=ThreadingWSGIServer,
                handler_class=WSGIRequestHandler,
            )
            log.info("SearXNG embarqué sur http://127.0.0.1:%s", SEARXNG_PORT)
            global _searx_httpd
            _searx_httpd = httpd
            httpd.serve_forever()
        except Exception as exc:
            log.exception("SearXNG embarqué indisponible : %s", exc)
            # P22 : la trace complète est conservée dans le journal — l'outil
            # search_web l'annexe à son message d'erreur (diagnostic direct).
            try:
                import traceback as _tb
                _log = Path(os.environ.get("DATA_DIR", ".")) / "searxng.log"
                _log.write_text(_tb.format_exc(), encoding="utf-8")
            except Exception:
                pass

    threading.Thread(target=run, name="searxng", daemon=True).start()


def _warm_up_then_searxng(data_dir: Path, port: int) -> None:
    """Attend qu'Open WebUI réponde, puis lance SearXNG (recherche web).

    SearXNG est lourd à importer (tous ses moteurs) : le démarrer en parallèle
    d'Open WebUI rallongeait l'écran de chargement (contention CPU). On le lance
    donc APRÈS que le serveur principal a répondu — la recherche web est prête
    en quelques secondes, sans bloquer l'ouverture de l'UI.
    """
    import urllib.request

    url = f'http://127.0.0.1:{port}/health'
    for _ in range(120):
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            pass
        time.sleep(1)
    _set_status(data_dir, 'Préparation de la recherche web…', 85)
    try:
        _start_searxng()
        _set_status(data_dir, 'Prêt', 100)
    except Exception as exc:
        log.warning('SearXNG non démarré : %s', exc)
        _set_status(data_dir, 'Prêt (sans recherche web)', 100)


def service_control(name: str, action: str) -> str:
    """P89 — pilotage des services depuis /fm (pont Java → Python).

    name: 'openwebui' | 'searxng' ; action: 'run' | 'stop' | 'restart'.
    Les boutons passent par le pont Java : utilisables même serveur arrêté.
    """
    global _started
    name = (name or '').lower()
    action = (action or '').lower()
    try:
        if name == 'searxng':
            if action == 'stop':
                if _searx_httpd is not None:
                    threading.Thread(target=_searx_httpd.shutdown, daemon=True).start()
                return 'SearXNG arrêté'
            if action in ('run', 'restart'):
                if _searx_httpd is not None:
                    try:
                        _searx_httpd.shutdown()
                    except Exception:
                        pass
                _start_searxng()
                return 'SearXNG (re)démarré'
            return f'action inconnue : {action}'
        if name == 'openwebui':
            if action == 'stop':
                if _uvicorn_server is not None:
                    _uvicorn_server.should_exit = True
                _started = False
                return 'serveur Open WebUI arrêté'
            if action == 'run':
                if _started:
                    return 'serveur déjà actif'
                threading.Thread(
                    target=start_server,
                    args=(APP_PORT, os.environ.get('HOME')),
                    name='owui-run', daemon=True,
                ).start()
                return 'serveur Open WebUI lancé'
            return f'action inconnue : {action}'
        return f'service inconnu : {name}'
    except Exception as exc:
        log.exception('service_control')
        return f'erreur : {exc}'


def env_read() -> str:
    """Contenu de data/openwebui.env (configuration par variables)."""
    try:
        return (Path(os.environ.get('HOME', '.')) / 'data' / 'openwebui.env').read_text(encoding='utf-8')
    except Exception:
        return ''


def env_save(text: str) -> str:
    """Écrit data/openwebui.env — appliqué au prochain démarrage/redémarrage."""
    try:
        path = Path(os.environ.get('HOME', '.')) / 'data' / 'openwebui.env'
        path.parent.mkdir(parents=True, exist_ok=True)
        lignes = []
        for ligne in (text or '').splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith('#') and '=' in ligne:
                if ligne.partition('=')[0].strip() in ('DATA_DIR', 'HOME'):
                    continue  # pilotés par l'application
            lignes.append(ligne)
        path.write_text('\n'.join(lignes) + '\n', encoding='utf-8')
        return 'enregistré — appliqué au prochain démarrage/redémarrage'
    except Exception as exc:
        return f'erreur : {exc}'


def start_server(port: int = APP_PORT, files_dir: str | None = None) -> int:
    """Lance uvicorn dans un thread daemon. Retourne le port. Idempotent."""
    global _started
    with _lock:
        if _started:
            return port
        data_dir = _prepare_env(files_dir)
        _set_status(data_dir, "Démarrage du serveur Open WebUI…", 45)

        def run() -> None:
            try:
                import uvicorn
                from open_webui.main import app

                # Diagnostic : répertoire(s) réellement monté(s) pour l'UI
                try:
                    import inspect
                    import open_webui.main as _m
                    from starlette.routing import Mount
                    log.warning("main.py chargé depuis : %s", _m.__file__)
                    for route in app.routes:
                        if isinstance(route, Mount) and type(route.app).__name__ == 'SPAStaticFiles':
                            log.warning("SPA configurée (frontend : %s)", dirs)
                    for route in app.routes:
                        if isinstance(route, Mount) and type(route.app).__name__ == 'SPAStaticFiles':
                            dirs = getattr(route.app, 'all_directories', None)
                            log.warning("SPA montée sur %r -> %s", route.path, dirs)
                            for d in dirs or []:
                                p = Path(str(d))
                                log.warning("  %s existe=%s probe=%s nb_fichiers=%s",
                                            p, p.is_dir(), (p / 'probe.txt').exists(),
                                            len(list(p.rglob('*'))) if p.is_dir() else -1)
                                sa = route.app
                                fake = {'type': 'http', 'method': 'GET', 'path': '/probe.txt',
                                        'root_path': '', 'headers': [], 'query_string': b''}
                                gp = sa.get_path(fake)
                                lp = sa.lookup_path(gp)
                                log.warning("  get_path=%r lookup=%s", gp, lp[1] is not None)
                except Exception:
                    pass

                config = uvicorn.Config(
                    app,
                    host="127.0.0.1",
                    port=port,
                    log_level="warning",
                    access_log=False,
                )
                global _uvicorn_server
                _uvicorn_server = uvicorn.Server(config)
                _uvicorn_server.run()
            except BaseException as exc:  # visible sur l'écran de démarrage
                log.exception("échec du démarrage du serveur")
                _set_status(data_dir, f"Erreur au démarrage : {type(exc).__name__}: {exc}", 100)

        t = threading.Thread(target=run, name="openwebui-server", daemon=True)
        t.start()
        _started = True

        # Recherche web : démarrée une fois Open WebUI prêt (cf. _warm_up_then_searxng)
        threading.Thread(
            target=_warm_up_then_searxng,
            args=(data_dir, port),
            name="openwebui-warmup",
            daemon=True,
        ).start()

        log.info("serveur Open WebUI lancé sur 127.0.0.1:%s", port)
        return port
