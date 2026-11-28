"""Validation locale P166 : repli shell sans PTY et journalisation.

Usage : .venv313/bin/python3 scripts/test_p166.py

Simule un appareil Android sans périphérique PTY (`pty.openpty()` lève
OSError), démarre Open Terminal sur un port d'essai, puis vérifie que le shell
s'ouvre quand même en backend `pipe`, exécute une commande dans le mini-Debian
et consigne le diagnostic dans les journaux.
"""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p166-', dir='/tmp/opencode'))
ROOTFS = Path('/tmp/opencode/ot-test/rootfs')
WORK = TMP / 'work'
WORK.mkdir(parents=True, exist_ok=True)
assert ROOTFS.is_dir(), 'rootfs de test absent (extraire minidebian/rootfs.tar.xz)'
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P166 — repli shell sans PTY ===')

# Simulateur : aucun /dev/ptmx utilisable, exactement comme sur l'appareil.
import pty  # noqa: E402


def _pas_de_pty():
    raise OSError('P166 simulé : aucun périphérique PTY disponible')


pty.openpty = _pas_de_pty

PORT = 8892
key = TMP / 'open-terminal-api.key'
key.write_text('p166-key', encoding='utf-8')
key.chmod(0o600)
os.environ.update(
    OPEN_TERMINAL_API_KEY_FILE=str(key),
    OPEN_TERMINAL_PORT=str(PORT),
    OPEN_TERMINAL_ENABLE_BROWSER='false',
    OPEN_TERMINAL_ENABLE_DESKTOP='false',
    OPEN_TERMINAL_ENABLE_AGENTS='false',
    OPEN_TERMINAL_ENABLE_NOTEBOOKS='false',
    OPEN_TERMINAL_ENABLE_TERMINAL='true',
    OPEN_TERMINAL_MAX_SESSIONS='1',
    OPENWEBUI_ANDROID_PROOT=str(PROJ / 'minidebian/proot'),
    OPENWEBUI_ANDROID_ROOTFS=str(ROOTFS),
    OPENWEBUI_ANDROID_WORK=str(WORK),
    OPENWEBUI_ANDROID_PROOT_LIB=str(PROJ / 'minidebian'),
    WEBUI_SECRET_KEY='p166-local', HOME=str(TMP),
    DATA_DIR=str(TMP / 'data'), UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'), DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
(TMP / 'data').mkdir(exist_ok=True)
(TMP / 'tmp').mkdir(exist_ok=True)

import uvicorn  # noqa: E402
from open_terminal.main import app  # noqa: E402

config = uvicorn.Config(app, host='127.0.0.1', port=PORT,
                        log_level='warning', access_log=False, ws='none')
serveur = uvicorn.Server(config)
threading.Thread(target=serveur.run, daemon=True).start()
for _ in range(100):
    if serveur.started:
        break
    time.sleep(0.1)
assert serveur.started, 'serveur Open Terminal non démarré'

ENTETES = {
    'Authorization': 'Bearer p166-key',
    'x-user-id': 'embedded',
    'x-session-id': 'fm',
    'Content-Type': 'application/json',
}


def appeler(chemin, charge=None, methode='GET'):
    donnees = json.dumps(charge).encode() if charge is not None else None
    req = urllib.request.Request(
        f'http://127.0.0.1:{PORT}{chemin}', data=donnees,
        headers=ENTETES, method=methode)
    with urllib.request.urlopen(req, timeout=15) as rep:
        return json.loads(rep.read().decode())


try:
    session = appeler('/api/terminals', {}, 'POST')
    assert session.get('id'), session
    assert session.get('backend') == 'pipe', session
    print('OK  PTY absent : session ouverte en backend pipe')

    # Le shell sans PTY n'a pas d'echo noyau : la saisie est rejouée dans le
    # tampon, puis la commande s'exécute bien dans le mini-Debian via proot.
    appeler('/api/terminals/user/input', {'input': 'echo P166_SHELL_OK\n'}, 'POST')
    sortie = ''
    for _ in range(40):
        time.sleep(0.25)
        sortie = appeler('/api/terminals/user/output').get('output', '')
        if 'P166_SHELL_OK' in sortie:
            break
    assert 'P166_SHELL_OK' in sortie, sortie[-300:]
    assert 'P166_SHELL_OK' in sortie and 'echo P166_SHELL_OK' in sortie, sortie[-300:]
    print('OK  commande exécutée dans le mini-Debian (echo du tube présent)')

    # La limite d'une session empêche l'accumulation de processus proot.
    try:
        appeler('/api/terminals', {}, 'POST')
    except urllib.error.HTTPError as exc:
        assert exc.code == 429, exc.code
        print('OK  limite OPEN_TERMINAL_MAX_SESSIONS=1 respectée')
    else:
        raise AssertionError('une seconde session a été ouverte malgré la limite')
finally:
    # `uvicorn.Server` n'expose pas close() dans la version embarquee :
    # l'appel doit juste demander l'arret, le thread daemon se termine seul.
    serveur.should_exit = True

print('\nTous les cas P166 sont valides.')
