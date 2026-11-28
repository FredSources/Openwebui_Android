"""Validation locale P167 : volume exécutable interne et diagnostic proot.

Usage : .venv313/bin/python3 scripts/test_p167.py

Deux régressions couvertes :
  1. Android monte ``Android/data/...`` en ``noexec`` : ``proot``, ses libs et
     le rootfs doivent vivre dans ``getFilesDir()`` (mémoire interne), comme
     le fait Termux. Ce volume est effacé à la désinstallation.
  2. Une erreur d'exécution de ``proot`` (Errno 13) n'est PAS une panne du
     service : le relais /fm/ot/session ne doit pas relancer 20 fois.
"""
import importlib.util
import inspect
import os
import sys
import tempfile
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p167-', dir='/tmp/opencode'))
HOME = TMP / 'home'
EXEC = TMP / 'internal-files'   # simule getFilesDir()
DATA = HOME / 'data'
WORK = DATA / 'work'
ROOTFS = EXEC / 'proot-distro/containers/minidebian/rootfs'
for p in (HOME, EXEC, DATA, WORK, ROOTFS, TMP / 'tmp'):
    p.mkdir(parents=True, exist_ok=True)
key = DATA / 'open-terminal-api.key'
key.write_text('p167-key', encoding='utf-8')
key.chmod(0o600)
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p167', HOME=str(HOME),
    DATA_DIR=str(DATA), UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'), DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

spec = importlib.util.spec_from_file_location(
    'android_main_test_p167', PROJ / 'app/src/main/python/android_main.py')
am = importlib.util.module_from_spec(spec)
spec.loader.exec_module(am)

print('=== P167 — volume exécutable à la Termux ===')

java = (PROJ / 'app/src/main/java/org/openwebui/android/MainActivity.java').read_text(encoding='utf-8')
assert 'new java.io.File(getFilesDir(), "minidebian")' in java, 'extraction hors du volume interne'
assert 'dataHome.getAbsolutePath(), getFilesDir().getAbsolutePath()' in java, 'exec_dir non transmis'
assert 'deleteRecursive(new java.io.File(dataHome, "minidebian"))' in java, 'ancienne copie noexec conservée'
print('OK  Java : extraction dans getFilesDir(), ancienne copie externe purgée')

# 1 — séparation des racines via start_server()/_prepare_env().
sign = inspect.signature(am.start_server)
assert 'exec_dir' in sign.parameters, 'start_server() ne reçoit pas le volume interne'
am._prepare_env(str(HOME), str(EXEC))
assert os.environ['OPENWEBUI_ANDROID_EXEC_HOME'] == str(EXEC)
assert os.environ['XDG_DATA_HOME'] == str(EXEC), 'proot-distro resterait dans Android/data'
assert os.environ['OPENWEBUI_ANDROID_PROOT'] == str(EXEC / 'minidebian/proot')
assert os.environ['OPENWEBUI_ANDROID_ROOTFS'] == str(ROOTFS)
assert os.environ['OPENWEBUI_ANDROID_WORK'] == str(WORK)
assert os.environ['DATA_DIR'] == str(DATA), 'données utilisateur déplacées à tort'
print('OK  Python : proot/rootfs dans le volume interne, données inchangées')

# 2 — reset : le conteneur interne est reconstruit, /root/work obéit au mode.
def preparer(mode):
    ROOTFS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    (ROOTFS / 'marqueur-rootfs').write_text('ancien', encoding='utf-8')
    (WORK / 'conservez-moi.txt').write_text('données utilisateur', encoding='utf-8')
    (DATA / 'open-terminal-api.key').write_text('ancienne-cle', encoding='utf-8')
    (DATA / 'open-terminal-reset-requested').write_text(mode, encoding='utf-8')


preparer('environment')
am._apply_open_terminal_reset(HOME, DATA, EXEC)
assert not ROOTFS.exists(), 'conteneur interne non reconstruit'
assert (WORK / 'conservez-moi.txt').is_file(), '/root/work perdu en mode environment'
assert not (DATA / 'open-terminal-api.key').exists(), 'clé non régénérée'
print('OK  reset environment : rootfs interne effacé, /root/work conservé')

preparer('wipe-work')
am._apply_open_terminal_reset(HOME, DATA, EXEC)
assert not ROOTFS.exists() and not WORK.exists(), 'wipe-work incomplet'
print('OK  reset wipe-work : rootfs interne et /root/work effacés')

key.write_text('p167-key', encoding='utf-8')

# 3 — erreur d'exécution proot : diagnostic immédiat, aucune relance.
print('=== P167 — plus de 20 relances sur Errno 13 ===')

etat = {'post': 0, 'appels': []}
message_erreur = ("[Errno 13] Permission denied: '"
                  "/storage/emulated/0/Android/data/org.openwebui.android/files/minidebian/proot'")


class _Handler(BaseHTTPRequestHandler):
    def _repondre(self, corps, code=500):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        self._repondre(('{"detail": %r}' % message_erreur).encode())

    def do_POST(self):
        etat['post'] += 1
        self._repondre(('{"detail": %r}' % message_erreur).encode())

    def log_message(self, *_a):
        pass


PORT = 8893
httpd = ThreadingHTTPServer(('127.0.0.1', PORT), _Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()


def service_control(name, action):
    etat['appels'].append((name, action))
    return 'Open Terminal (re)démarré'


fake_am = types.ModuleType('android_main')
fake_am.service_status = lambda: {'openwebui': 'actif', 'searxng': 'arrêt',
                                  'open_terminal': 'arrêt'}
fake_am.searxng_settings_load = lambda: {'formats': ['json'], 'limiter': False}
fake_am.searxng_settings_save = lambda *_a, **_k: 'ok'
fake_am.env_read = lambda: ''
fake_am.env_save = lambda *_a, **_k: 'ok'
fake_am.service_control = service_control
sys.modules['android_main'] = fake_am

from fastapi import FastAPI  # noqa: E402
from open_webui.models.files import Files  # noqa: E402
from open_webui.utils.auth import get_verified_user  # noqa: E402

source = (PROJ / 'src/open_webui/android_fm.py').read_text(encoding='utf-8')
assert "'http://127.0.0.1:8889'" in source
source = source.replace("'http://127.0.0.1:8889'", "'http://127.0.0.1:%d'" % PORT)
module_test = types.ModuleType('open_webui.android_fm_p167')
module_test.__file__ = str(PROJ / 'src/open_webui/android_fm.py')
exec(compile(source, module_test.__file__, 'exec'), module_test.__dict__)


class _ListeVide:
    items: list = []


async def _fausse_liste(*_a, **_k):
    return _ListeVide()


Files.get_file_list = _fausse_liste


class Utilisateur:
    id = 'p167-utilisateur-test'
    role = 'admin'
    email = 'p167@example.invalid'


app = FastAPI()
app.dependency_overrides[get_verified_user] = lambda: Utilisateur()
module_test.register_fm(app)

from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)
try:
    reponse = client.post('/fm/ot/session')
    assert reponse.status_code == 200, reponse.text
    resultat = reponse.json()
    assert resultat.get('status') == 'error', resultat
    assert 'proot non exécutable' in resultat.get('detail', ''), resultat
    assert 'getFilesDir()' in resultat['detail'], resultat
    assert etat['post'] == 1, 'relances inutiles : %d POST' % etat['post']
    assert etat['appels'] == [], 'service relancé pour une erreur applicative'
    print('OK  Errno 13 : diagnostic explicite, 1 seul POST, aucun restart')
finally:
    httpd.shutdown()
    httpd.server_close()

# 4 — traçabilité des sources figées.
journal = (PROJ / 'journal.md').read_text(encoding='utf-8')
assert 'P167' in journal, 'décision P167 non journalisée'
main_ot = (PROJ / 'src/open_terminal/main.py').read_text(encoding='utf-8')
assert 'P167 proot non exécutable depuis' in main_ot
print('OK  traçabilité : journal et diagnostic Open Terminal')

print('\nTous les cas P167 sont valides.')
