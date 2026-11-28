"""Validation locale P165 : ouverture du Shell root à la demande.

Usage : .venv313/bin/python3 scripts/test_p165.py

Régression couverte : quand le service Open Terminal local n'a pas été lancé
au boot (ou a été arrêté depuis l'onglet Service), l'iframe du Shell root
restait sur une erreur de relais. La route /fm/ot/session tente désormais un
démarrage à la demande puis réessaie, sans ajouter de bouton au Shell root.
"""
import asyncio
import json
import os
import sys
import tempfile
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p165-', dir='/tmp/opencode'))
DATA = TMP / 'data'
DATA.mkdir(parents=True, exist_ok=True)
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p165', HOME=str(TMP),
    DATA_DIR=str(DATA), UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'), DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
(TMP / 'tmp').mkdir(parents=True, exist_ok=True)
key = DATA / 'open-terminal-api.key'
key.write_text('p165-key', encoding='utf-8')
key.chmod(0o600)
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P165 — démarrage du shell à la demande ===')

etat = {'actif': False, 'appels': [], 'sessions': 0}


class _Handler(BaseHTTPRequestHandler):
    def _repondre(self, corps, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        if ('/api/terminals/user/output' in self.path
                and etat['actif'] and etat['sessions']):
            self._repondre(b'{"output":"root@localhost:~# "}')
        else:
            self._repondre(b'{"detail":"service arrete"}', 503)

    def do_POST(self):
        if self.path == '/api/terminals' and etat['actif']:
            etat['sessions'] += 1
            self._repondre(b'{"status":"ok","id":"p165-session"}')
        else:
            self._repondre(b'{"detail":"service arrete"}', 503)

    def log_message(self, *_a):
        pass


PORT = 8891  # 8889 peut être occupé sur la machine de test
httpd = ThreadingHTTPServer(('127.0.0.1', PORT), _Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()


def service_control(name: str, action: str) -> str:
    etat['appels'].append((name, action))
    etat['actif'] = True
    return 'Open Terminal (re)démarré'


am = types.ModuleType('android_main')
am.service_status = lambda: {'openwebui': 'actif', 'searxng': 'arrêt',
                             'open_terminal': 'arrêt'}
am.searxng_settings_load = lambda: {'formats': ['json'], 'limiter': False}
am.searxng_settings_save = lambda *_a, **_k: 'ok'
am.env_read = lambda: ''
am.env_save = lambda *_a, **_k: 'ok'
am.service_control = service_control
sys.modules['android_main'] = am

from fastapi import FastAPI  # noqa: E402
from open_webui.models.files import Files  # noqa: E402
from open_webui.utils.auth import get_verified_user  # noqa: E402

# Le port du relais est figé dans android_fm.py ; on charge une copie du module
# avec ce port remplacé pour isoler le test du service réel de la machine.
source = (PROJ / 'src/open_webui/android_fm.py').read_text(encoding='utf-8')
assert "'http://127.0.0.1:8889'" in source
source = source.replace("'http://127.0.0.1:8889'",
                        "'http://127.0.0.1:%d'" % PORT)
module_test = types.ModuleType('open_webui.android_fm_p165')
module_test.__file__ = str(PROJ / 'src/open_webui/android_fm.py')
exec(compile(source, module_test.__file__, 'exec'), module_test.__dict__)
register_fm = module_test.register_fm


class _ListeVide:
    items: list = []


async def _fausse_liste(*_a, **_k):
    return _ListeVide()


Files.get_file_list = _fausse_liste


class Utilisateur:
    id = 'p165-utilisateur-test'
    role = 'admin'
    email = 'p165@example.invalid'


app = FastAPI()
app.dependency_overrides[get_verified_user] = lambda: Utilisateur()
register_fm(app)

from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

try:
    reponse = client.post('/fm/ot/session')
    assert reponse.status_code == 200, reponse.text
    resultat = reponse.json()
    assert resultat.get('status') == 'ok', resultat
    assert etat['appels'] == [('open_terminal', 'run')], etat['appels']
    assert etat['sessions'] == 1, etat['sessions']
    print('OK  service arrêté : démarrage à la demande et session ouverte')

    # Second appel : le shell existant est réutilisé — aucun nouveau PTY,
    # aucun redémarrage (garde-fou contre « Out of PTY devices »).
    etat['appels'].clear()
    reponse = client.post('/fm/ot/session')
    resultat = reponse.json()
    assert resultat.get('status') == 'ok', resultat
    assert resultat.get('reuse') is True, resultat
    assert etat['appels'] == [], etat['appels']
    assert etat['sessions'] == 1, etat['sessions']
    print('OK  shell existant réutilisé : aucun PTY supplémentaire')
finally:
    httpd.shutdown()
    httpd.server_close()

print('\nTous les cas P165 sont valides.')
