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
import socket
import threading
import time
from pathlib import Path

log = logging.getLogger("android_main")

_lock = threading.Lock()
_started = False

APP_PORT = 8080
OPEN_TERMINAL_PORT = 8889


_uvicorn_server = None
_searx_httpd = None
_searx_actif = False
# P160/P163 — service Open Terminal embarqué (mini-Debian sous proot).
_ot_server = None
_ot_actif = False


def _port_actif(port: int) -> bool:
    """P169 — état RÉEL d'un service local, indépendant des variables de thread.

    Les boutons peuvent être utilisés juste après un redémarrage de l'app :
    `_ot_actif` est alors faux alors que le service tourne déjà, ou vrai alors
    que le thread uvicorn est mort. Un connect TCP sur 127.0.0.1 ne coûte rien
    et dit la vérité sur le port attendu.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            return s.connect_ex(("127.0.0.1", int(port))) == 0
    except Exception:
        return False


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


def _prepare_env(files_dir: str | None = None, exec_dir: str | None = None) -> Path:
    """Variables d'environnement Open WebUI pour Android (avant tout import du package).

    Garantie d'isolation : TOUT fichier (base, uploads, cache, temporaires) est
    écrit dans l'espace privé de l'application — <files>/data, <files>/tmp,
    <files>/cache — où <files> est getExternalFilesDir() fourni par MainActivity.

    P167 — deux racines distinctes :
      * ``home`` (stockage externe de l'app) : base, configuration, /root/work ;
      * ``exec_home`` (``getFilesDir()``, mémoire INTERNE) : « volume » à la
        Termux. ``proot``, ses bibliothèques et le rootfs y sont extraits afin
        d'être exécutables — ``Android/data`` est monté en ``noexec`` sur Android.
        Ce volume est aussi **effacé automatiquement à la désinstallation**.
    """
    import open_webui  # noqa: F401  (le paquet doit être localisable)
    pkg_dir = Path(open_webui.__file__).parent

    # files_dir est prioritaire sur HOME : aucune écriture ne doit dépendre
    # d'un HOME implicite du runtime.
    home = Path(files_dir or os.environ.get("HOME") or pkg_dir.parent).resolve()
    home.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(home)  # forcé (et non setdefault) pour tous les importeurs

    # P167 — volume exécutable interne. Sur l'hôte (tests), repli sur ``home``
    # pour ne rien changer au comportement des scripts de validation.
    exec_home = Path(
        exec_dir or os.environ.get("OPENWEBUI_ANDROID_EXEC_HOME") or home
    ).resolve()
    exec_home.mkdir(parents=True, exist_ok=True)
    os.environ["OPENWEBUI_ANDROID_EXEC_HOME"] = str(exec_home)
    # proot-distro ancre ses conteneurs (rootfs, cache, locks, sessions) sous
    # XDG_DATA_HOME : le lui faire pointer vers le volume exécable interne.
    os.environ["XDG_DATA_HOME"] = str(exec_home)
    for sub, var in (("tmp", "TMPDIR"), ("cache", "XDG_CACHE_HOME")):
        d = home / sub
        d.mkdir(parents=True, exist_ok=True)
        os.environ[var] = str(d)

    # D14 (correctif accès fichiers) : ancrage EXPLICITE du cache Typst.
    # Sans variable dédiée, la bibliothèque le déduit de XDG_CACHE_HOME/HOME
    # selon le contexte d'appel → paquets @preview retéléchargés, échecs
    # intermittents hors ligne. Un seul chemin, dans l'espace privé de l'app.
    typst_cache = home / "cache" / "typst"
    typst_cache.mkdir(parents=True, exist_ok=True)
    os.environ["TYPST_CACHE_DIR"] = str(typst_cache)

    data_dir = home / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # P163 — réinitialisation ciblée de l'environnement Open Terminal.
    _apply_open_terminal_reset(home, data_dir, exec_home)

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
    log.warning("espace applicatif : HOME=%s DATA_DIR=%s EXEC=%s (effacé à la désinstallation)",
                home, data_dir, exec_home)
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

    # P160 — Open Terminal embarqué : clé privée, service local, connexion machine.
    _ensure_open_terminal(data_dir, home)
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


def searxng_settings_load() -> dict:
    """P109 — réglages SearXNG lisibles pour l'écran Paramètres."""
    import re
    path = Path(os.environ.get("SEARXNG_SETTINGS_PATH")
                or (Path(os.environ.get("DATA_DIR", ".")) / "searxng-settings.yml"))
    out = {"formats": ["html", "json"], "limiter": False, "secret": ""}
    try:
        texte = path.read_text(encoding="utf-8")
        out["secret"] = (re.search(r'secret_key:\s*"([^"]*)"', texte) or [None, ""])[1] \
            if re.search(r'secret_key:\s*"([^"]*)"', texte) else ""
        out["limiter"] = bool(re.search(r"limiter:\s*true", texte))
        bloc = re.search(r"formats:\s*\n((\s*-\s*\w+\s*\n)+)", texte)
        if bloc:
            out["formats"] = re.findall(r"-\s*(\w+)", bloc.group(1))
    except Exception as exc:
        log.warning("lecture réglages SearXNG : %s", exc)
    return out


def searxng_settings_save(formats, limiter: bool, rekey: bool = False) -> str:
    """P109 — réécrit les réglages SearXNG (formats, limiter, clé régénérée)."""
    import secrets as _secrets
    path = _ensure_searxng_settings(Path(os.environ.get("DATA_DIR", ".")))
    actuel = searxng_settings_load()
    cle = _secrets.token_urlsafe(32) if (rekey or not actuel.get("secret")) else actuel["secret"]
    formats = [f for f in ("html", "json") if f in (formats or [])]
    if not formats:
        formats = ["html"]
    path.write_text(
        SEARXNG_SETTINGS_TEMPLATE.format(secret=cle, port=SEARXNG_PORT).replace(
            "  formats:\n    - html\n    - json",
            "  formats:\n" + "".join(f"    - {f}\n" for f in formats)).replace(
            "  limiter: false", f"  limiter: {'true' if limiter else 'false'}"),
        encoding="utf-8",
    )
    log.info("réglages SearXNG écrits : %s (formats=%s limiter=%s)", path, formats, limiter)
    return "Réglages SearXNG enregistrés — appliqués au redémarrage du service."


# ---------------------------------------------------------------------------
# P160/P163 — Open Terminal embarqué dans le mini-Debian (proot)
# ---------------------------------------------------------------------------


def _apply_open_terminal_reset(home: Path, data_dir: Path, exec_home: Path | None = None) -> None:
    """P163/P167 — consomme le marqueur écrit depuis /fm puis reconstruit l'environnement.

    Deux modes : environnement seul (fichiers de /root/work conservés) ou
    `wipe-work` (effacement complet, état de première installation).

    P167 : le conteneur vit désormais dans le volume exécutable interne
    (``exec_home``). Les anciens emplacements externes restent dans la liste
    pour purger une installation issue d'une version antérieure.
    """
    marqueur = data_dir / "open-terminal-reset-requested"
    if not marqueur.exists():
        return
    try:
        mode = marqueur.read_text(encoding="utf-8").strip().lower()
    except Exception:
        mode = ""
    log.warning("P163/P167 réinitialisation Open Terminal demandée (mode=%s)", mode or "standard")
    exec_home = exec_home or Path(os.environ.get("OPENWEBUI_ANDROID_EXEC_HOME", str(home)))
    cibles = [
        data_dir / "open-terminal-api.key",
        data_dir / "open-terminal.log",
        data_dir / "proot-distro" / "containers" / "minidebian",
        data_dir / "proot-distro" / "cache",
        data_dir / "proot-distro" / "locks",
        data_dir / "proot-distro" / "sessions",
        exec_home / "proot-distro" / "containers" / "minidebian",
        exec_home / "proot-distro" / "cache",
        exec_home / "proot-distro" / "locks",
        exec_home / "proot-distro" / "sessions",
    ]
    if mode == "wipe-work":
        cibles.append(data_dir / "work")
    import shutil as _sh

    for cible in cibles:
        try:
            if cible.is_dir():
                _sh.rmtree(cible)
            elif cible.exists():
                cible.unlink()
        except Exception as exc:
            log.warning("P163 effacement impossible %s : %s", cible.name, exc)
    try:
        marqueur.unlink()
    except Exception:
        pass
    try:
        from open_webui import android_logs as _allog

        _allog.journal_exec("P163 open-terminal reset mode=%s" % (mode or "standard"))
    except Exception:
        pass


def _force_machine_connection(data_dir: Path, key: str) -> None:
    """P160 — connexion machine embarquée forcée, sans écraser les autres."""
    import json
    import sqlite3
    import time

    entree = {
        "id": "embedded-open-terminal",
        "name": "Mini Debian (local)",
        "enabled": True,
        "url": f"http://127.0.0.1:{OPEN_TERMINAL_PORT}",
        "path": "/openapi.json",
        "key": key,
        "auth_type": "bearer",
        "forward_cookies": False,
    }
    os.environ["MACHINE_CONNECTIONS"] = json.dumps([entree])
    db = data_dir / "webui.db"
    if not db.exists():
        return
    try:
        con = sqlite3.connect(db, timeout=5)
        try:
            row = con.execute(
                "SELECT value FROM config WHERE key='machines.connections'"
            ).fetchone()
            actuel = []
            if row is not None:
                try:
                    actuel = json.loads(row[0])
                except Exception:
                    actuel = []
            if not isinstance(actuel, list):
                actuel = []
            maj = [c for c in actuel if not (isinstance(c, dict) and c.get("id") == entree["id"])]
            maj.append(entree)
            if maj == actuel:
                return
            maintenant = int(time.time())
            if row is None:
                con.execute(
                    "INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                    ("machines.connections", json.dumps(maj), maintenant),
                )
            else:
                con.execute(
                    "UPDATE config SET value=?, updated_at=? WHERE key=?",
                    (json.dumps(maj), maintenant, "machines.connections"),
                )
            con.commit()
            log.info("connexion machine embarquée forcée (clé régénérée ou absente)")
        finally:
            con.close()
    except Exception as exc:
        log.warning("force machines.connections impossible : %s", exc)


def _install_minidebian(data_dir: Path, home: Path, exec_home: Path | None = None) -> None:
    """P160/P167 — installe le rootfs embarqué dans le conteneur proot-distro.

    Passe par le CLI proot-distro (fixups /etc, manifest) avec repli sur une
    extraction tar directe si l'outil est indisponible sur l'appareil.

    P167 : le binaire ``proot``, l'archive et le rootfs extrait résident dans
    ``exec_home`` (``getFilesDir()``), seul emplacement exécutable et effacé
    lors d'une désinstallation.
    """
    exec_home = exec_home or Path(os.environ.get("OPENWEBUI_ANDROID_EXEC_HOME", str(home)))
    rootfs = exec_home / "proot-distro" / "containers" / "minidebian" / "rootfs"
    # P169 — point de montage du storage dans le conteneur, même sur une
    # installation déjà présente (chemin rapide).
    try:
        (rootfs / "root" / "storage").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if rootfs.is_dir() and (rootfs / "usr" / "bin" / "git").exists():
        return
    archive = exec_home / "minidebian" / "rootfs.tar.xz"
    if not archive.is_file():
        # Installation antérieure : l'archive externe est encore présente.
        # On la COPIE dans le volume interne avant extraction, sinon les
        # exécutables du rootfs resteraient sous un montage noexec.
        ancienne = home / "minidebian" / "rootfs.tar.xz"
        if ancienne.is_file():
            try:
                (exec_home / "minidebian").mkdir(parents=True, exist_ok=True)
                import shutil as _sh

                _sh.copyfile(ancienne, archive)
                log.warning("P167 archive mini-Debian migrée vers le volume exécutable")
            except Exception as exc:
                log.warning("P167 migration archive impossible : %s", exc)
    if not archive.is_file():
        log.warning("mini-Debian absent : %s", archive)
        return
    _set_status(data_dir, "Préparation du mini Debian…", 88)
    proot = exec_home / "minidebian" / "proot"
    if not proot.is_file():
        ancien_proot = home / "minidebian" / "proot"
        if ancien_proot.is_file():
            try:
                (exec_home / "minidebian").mkdir(parents=True, exist_ok=True)
                import shutil as _sh

                _sh.copy2(ancien_proot, proot)
                os.chmod(proot, 0o700)
                log.warning("P167 binaire proot migré vers le volume exécutable")
            except Exception as exc:
                log.warning("P167 migration proot impossible : %s", exc)
    os.environ["PD_PROOT_BIN"] = str(proot)
    os.environ["XDG_DATA_HOME"] = str(exec_home)
    try:
        import sys as _sys

        from proot_distro.cli import main as _pd_main

        argv = _sys.argv
        try:
            _sys.argv = ["proot-distro", "install", "-n", "minidebian", "-q", str(archive)]
            _pd_main()
        finally:
            _sys.argv = argv
        log.info("mini-Debian installé via proot-distro : %s", rootfs)
        return
    except Exception as exc:
        log.warning("proot-distro install indisponible (%s) — extraction directe", exc)
    try:
        import tarfile

        rootfs.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "r:xz") as tar:
            tar.extractall(rootfs, filter="data")
        log.info("mini-Debian extrait directement : %s", rootfs)
    except Exception as exc:
        log.exception("extraction mini-Debian impossible : %s", exc)


def _ensure_open_terminal(data_dir: Path, home: Path, exec_home: Path | None = None) -> None:
    """P160/P167/P169 — clé privée, environnement proot, stockage et connexion machine."""
    key_path = data_dir / "open-terminal-api.key"
    if not key_path.exists() or key_path.stat().st_size == 0:
        key_path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        os.chmod(key_path, 0o600)
    key = key_path.read_text(encoding="utf-8").strip()
    os.environ["OPEN_TERMINAL_API_KEY_FILE"] = str(key_path)
    os.environ["OPEN_TERMINAL_PORT"] = str(OPEN_TERMINAL_PORT)
    os.environ["OPEN_TERMINAL_ENABLE_BROWSER"] = "false"
    os.environ["OPEN_TERMINAL_ENABLE_DESKTOP"] = "false"
    os.environ["OPEN_TERMINAL_ENABLE_AGENTS"] = "false"
    os.environ["OPEN_TERMINAL_ENABLE_NOTEBOOKS"] = "false"
    os.environ["OPEN_TERMINAL_ENABLE_TERMINAL"] = "true"
    # P166 — un seul shell interactif embarqué : chaque ouverture consomme un
    # PTY, et Android en expose très peu. Sans limite, les rechargements de
    # l'iframe finissent par `"Out of PTY devices"`.
    os.environ["OPEN_TERMINAL_MAX_SESSIONS"] = "1"
    os.environ["OPEN_TERMINAL_CORS_ALLOWED_ORIGINS"] = "http://127.0.0.1:8080"

    exec_home = exec_home or Path(os.environ.get("OPENWEBUI_ANDROID_EXEC_HOME", str(home)))
    mini = exec_home / "minidebian"
    work = data_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    # P169 — stockage de DONNÉES du mini-Debian, sous DATA_DIR (visible dans
    # le gestionnaire et dans /fm) ; les binaires restent dans exec_home
    # (getFilesDir(), seul volume exécutable). Le conteneur voit ce dossier
    # sous /root/storage via un bind explicite.
    storage = data_dir / "minidebian" / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    (storage / "work").mkdir(parents=True, exist_ok=True)
    os.environ["OPENWEBUI_ANDROID_STORAGE"] = str(storage)
    os.environ["OPEN_TERMINAL_FILE_BROWSER_ROOT"] = str(work)
    os.environ["OPEN_TERMINAL_START_DIR"] = str(work)
    os.environ["OPENWEBUI_ANDROID_PROOT"] = str(mini / "proot")
    os.environ["OPENWEBUI_ANDROID_ROOTFS"] = str(
        exec_home / "proot-distro" / "containers" / "minidebian" / "rootfs"
    )
    os.environ["OPENWEBUI_ANDROID_WORK"] = str(work)
    os.environ["OPENWEBUI_ANDROID_PROOT_LIB"] = str(mini)
    os.environ["OPENWEBUI_ANDROID_EXEC_HOME"] = str(exec_home)
    try:
        import shutil as _sh

        resolv = Path("/etc/resolv.conf")
        if resolv.is_file():
            _sh.copyfile(resolv, data_dir / "resolv.conf")
    except Exception:
        pass

    _install_minidebian(data_dir, home, exec_home)
    _force_machine_connection(data_dir, key)


def _start_open_terminal() -> None:
    """Lance Open Terminal sur 127.0.0.1:8889 (thread daemon, façon SearXNG)."""

    def run() -> None:
        global _ot_server, _ot_actif
        try:
            import uvicorn

            from open_terminal.main import app as ot_app

            config = uvicorn.Config(
                ot_app,
                host="127.0.0.1",
                port=OPEN_TERMINAL_PORT,
                log_level="warning",
                access_log=False,
                ws="none",  # l'UI /fm passe par le relais HTTP, pas par WebSocket
            )
            _ot_server = uvicorn.Server(config)
            _ot_actif = True
            log.info("Open Terminal embarqué sur http://127.0.0.1:%s", OPEN_TERMINAL_PORT)
            _ot_server.run()
        except Exception as exc:
            log.exception("Open Terminal indisponible : %s", exc)
            try:
                (Path(os.environ.get("DATA_DIR", ".")) / "open-terminal.log").write_text(
                    str(exc), encoding="utf-8"
                )
            except Exception:
                pass
        finally:
            # P169 — sans ce reset, un arrêt naturel du serveur laissait
            # `_ot_actif` à True et le bouton « Démarrer » répondait
            # « déjà actif » alors que le port était libre.
            _ot_actif = False

    if _port_actif(OPEN_TERMINAL_PORT):
        _ot_actif = True
        return
    threading.Thread(target=run, name="open-terminal", daemon=True).start()
    # P169 — attendre l'écoute effective : le pont Java est bloquant, le
    # message « (re)démarré » doit correspondre à un port réellement ouvert.
    for _ in range(40):
        if _port_actif(OPEN_TERMINAL_PORT):
            _ot_actif = True
            break
        time.sleep(0.1)


def _warm_up_then_open_terminal(data_dir: Path, port: int) -> None:
    """Démarre Open Terminal après Open WebUI (évite la contention au boot)."""
    import urllib.request

    url = f"http://127.0.0.1:{port}/health"
    for _ in range(120):
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            pass
        time.sleep(1)
    try:
        _start_open_terminal()
    except Exception as exc:
        log.warning("Open Terminal non démarré : %s", exc)


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
            global _searx_httpd, _searx_actif
            _searx_httpd = httpd
            _searx_actif = True
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

    name: 'openwebui' | 'searxng' | 'open_terminal' ; action: 'run' | 'stop' | 'restart'.
    Les boutons passent par le pont Java : utilisables même serveur arrêté.
    """
    global _started, _searx_actif, _ot_actif, _ot_server
    name = (name or '').lower()
    action = (action or '').lower()
    try:
        if name == 'open_terminal':
            if action in ('stop', 'restart') and (
                    _ot_server is not None or _port_actif(OPEN_TERMINAL_PORT)):
                serveur = _ot_server
                if serveur is not None:
                    try:
                        serveur.should_exit = True
                    except Exception:
                        pass
                # P164/P169 — attendre la libération EFFECTIVE du port 8889 :
                # `started` peut rester vrai et un restart immédiat échoue avec
                # « address already in use » sans jamais redémarrer le service.
                for _ in range(50):
                    if not _port_actif(OPEN_TERMINAL_PORT):
                        break
                    time.sleep(0.1)
                _ot_server = None
                _ot_actif = False
            if action == 'stop':
                return ('Open Terminal arrêté' if not _port_actif(OPEN_TERMINAL_PORT)
                        else 'Open Terminal encore actif (port 8889 occupé)')
            if action in ('run', 'restart'):
                if _port_actif(OPEN_TERMINAL_PORT):
                    _ot_actif = True
                    return 'Open Terminal déjà actif'
                _start_open_terminal()
                if _port_actif(OPEN_TERMINAL_PORT):
                    return 'Open Terminal (re)démarré'
                return 'Open Terminal : démarrage impossible (voir serveur.log)'
            return f'action inconnue : {action}'
        if name == 'searxng':
            if action == 'stop':
                if _searx_httpd is not None:
                    threading.Thread(target=_searx_httpd.shutdown, daemon=True).start()
                _searx_actif = False
                return 'SearXNG arrêté'
            if action in ('run', 'restart'):
                if _searx_httpd is not None:
                    try:
                        _searx_httpd.shutdown()
                    except Exception:
                        pass
                _start_searxng()
                _searx_actif = True
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


def service_status() -> dict:
    """P89 — état réel des services (pour l'onglet /fm Paramètres)."""
    return {
        'openwebui': 'actif' if _started else 'arrêt',
        'searxng': 'actif' if _searx_actif or _port_actif(SEARXNG_PORT) else 'arrêt',
        # P169 — l'état affiché dans /fm vient du port réel : après un
        # redémarrage de l'app ou un crash du thread, il ne ment plus.
        'open_terminal': 'actif' if _port_actif(OPEN_TERMINAL_PORT) else 'arrêt',
    }


def open_terminal_reset_request(mode: str = 'environment') -> str:
    """P163 — programme la réinitialisation au prochain démarrage de l'app."""
    try:
        home = Path(os.environ.get('HOME', '.'))
        data = home / 'data'
        data.mkdir(parents=True, exist_ok=True)
        (data / 'open-terminal-reset-requested').write_text(
            'wipe-work' if mode == 'wipe-work' else 'environment', encoding='utf-8'
        )
        return 'Réinitialisation programmée — redémarrage de l’application…'
    except Exception as exc:
        return f'erreur : {exc}'


def register_audio_split(fn) -> None:
    """P130 — MainActivity enregistre la fonction Java de découpage audio
    (MediaExtractor/MediaMuxer) ; elle est appelée par `split_audio()` pour
    les formats non couverts par le découpage pur Python (wav/mp3)."""
    try:
        import audio_bridge
        audio_bridge.register_split(fn)
    except Exception:
        logging.getLogger(__name__).warning("pont audio Android non enregistre", exc_info=True)


def start_server(port: int = APP_PORT, files_dir: str | None = None,
                 exec_dir: str | None = None) -> int:
    """Lance uvicorn dans un thread daemon. Retourne le port. Idempotent.

    ``files_dir`` est le stockage utilisateur (externe), ``exec_dir`` le volume
    exécutable interne (``getFilesDir()``) — voir P167.
    """
    global _started
    with _lock:
        if _started:
            return port
        data_dir = _prepare_env(files_dir, exec_dir)
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

        # P160 : Open Terminal démarre après Open WebUI, comme SearXNG.
        threading.Thread(
            target=_warm_up_then_open_terminal,
            args=(data_dir, port),
            name="open-terminal-warmup",
            daemon=True,
        ).start()

        log.info("serveur Open WebUI lancé sur 127.0.0.1:%s", port)
        return port
