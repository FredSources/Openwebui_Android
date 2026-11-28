"""Validation locale P162 : Shell root xterm.js et relais HTTP sécurisé.

Usage : .venv313/bin/python3 scripts/test_p162.py

La clé API du service reste côté serveur : aucun secret dans le HTML rendu,
aucun WebSocket navigateur, uniquement /fm/ot/{session,output,input,resize}.
"""
import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p162-', dir='/tmp/opencode'))
KEY = 'cle-de-test-p162-ne-pas-publier'
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p162', HOME=str(TMP),
    DATA_DIR=str(TMP / 'data'), UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'), DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
(TMP / 'tmp').mkdir(parents=True, exist_ok=True)
(TMP / 'data').mkdir(parents=True, exist_ok=True)
(TMP / 'data' / 'open-terminal-api.key').write_text(KEY, encoding='utf-8')
for cle in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    os.environ.pop(cle, None)
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P162 — Shell root via relais HTTP ===')
am = types.ModuleType('android_main')
am.service_status = lambda: {'openwebui': 'arrêt', 'searxng': 'arrêt',
                             'open_terminal': 'actif'}
am.searxng_settings_load = lambda: {'formats': ['json'], 'limiter': False}
am.searxng_settings_save = lambda *_a, **_k: 'ok'
am.env_read = lambda: ''
am.env_save = lambda *_a, **_k: 'ok'
sys.modules['android_main'] = am

from fastapi import FastAPI  # noqa: E402
from open_webui.android_fm import register_fm  # noqa: E402
from open_webui.models.files import Files  # noqa: E402
from starlette.requests import Request  # noqa: E402


class _ListeVide:
    items: list = []


async def _fausse_liste(*_a, **_k):
    return _ListeVide()


Files.get_file_list = _fausse_liste
app = FastAPI()
register_fm(app)
chemins = {getattr(r, 'path', None) for r in app.routes}
for route in ('/fm/ot/session', '/fm/ot/output', '/fm/ot/input',
              '/fm/ot/resize', '/fm/ot/reset', '/fm/ot/terminal'):
    assert route in chemins, route
print('OK  routes : session, output, input, resize, reset, terminal')


def rendre(query: bytes) -> str:
    route = next(r for r in app.routes if getattr(r, 'path', None) == '/fm')

    class Utilisateur:
        id = 'p162-utilisateur-test'
        role = 'admin'
        email = 'p162@example.invalid'

    scope = {'type': 'http', 'method': 'GET', 'path': '/fm',
             'query_string': query, 'headers': [], 'scheme': 'http',
             'server': ('testserver', 80)}
    reponse = asyncio.run(route.endpoint(Request(scope), Utilisateur()))
    assert reponse.status_code == 200, reponse.status_code
    return reponse.body.decode('utf-8')


html = rendre(b'folder=settings&tab=ot_shell')
assert 'Shell root' in html
assert 'src="/fm/ot/terminal"' in html and 'class="sxframe"' in html
assert '/static/xterm/xterm.js' not in html, 'xterm.js doit rester dans l’iframe'
assert KEY not in html, 'clé API présente dans le HTML'
print('OK  onglet : iframe isolée, comme le moteur de recherche SearXNG')

# Page autonome chargée dans l'iframe.
def rendre_route(chemin: str) -> str:
    route = next(r for r in app.routes if getattr(r, 'path', None) == chemin)

    class Utilisateur:
        id = 'p162-utilisateur-test'
        role = 'admin'
        email = 'p162@example.invalid'

    scope = {'type': 'http', 'method': 'GET', 'path': chemin,
             'query_string': b'', 'headers': [], 'scheme': 'http',
             'server': ('testserver', 80)}
    import inspect
    args = (Request(scope), Utilisateur()) if len(inspect.signature(route.endpoint).parameters) > 1 else (Request(scope),)
    reponse = asyncio.run(route.endpoint(*args))
    assert reponse.status_code == 200, reponse.status_code
    return reponse.body.decode('utf-8')


terminal = rendre_route('/fm/ot/terminal')
assert '/static/xterm/xterm.js' in terminal
assert '/static/xterm/addon-fit.js' in terminal
assert '/static/xterm/addon-web-links.js' in terminal
assert 'new FA()' in terminal and 'new WL()' in terminal
assert '/fm/ot/output' in terminal and '/fm/ot/input' in terminal
assert 'window.otSession' in terminal
assert 'term.onResize(function(sz)' in terminal and '"/fm/ot/resize"' in terminal, \
    'FitAddon non relié à la route de redimensionnement'
assert 'var fitAddon=new FA();' in terminal and 'fitAddon.fit();' in terminal
assert 'term.fit();' not in terminal, 'Terminal.fit() n’existe pas : utiliser FitAddon.fit()'
assert KEY not in terminal, 'clé API présente dans le HTML'
assert 'WebSocket(' not in terminal, 'WebSocket navigateur interdit'
print('OK  terminal : xterm.js réel, polling HTTP, aucune clé dans le HTML')

service = rendre(b'folder=settings&tab=ot_service')
assert '127.0.0.1:8889' in service
assert 'Réinitialiser l’environnement' in service
assert 'Tout effacer' in service
assert KEY not in service
print('OK  service : état, port local et deux actions de réinitialisation')

src = (PROJ / 'src/open_webui/android_fm.py').read_text(encoding='utf-8')
assert "'Authorization': 'Bearer ' + cle" in src
assert "'x-user-id': 'embedded'" in src and "'x-session-id': 'fm'" in src
assert 'trust_env=False' in src
assert 'return rep.json()' in src
print('OK  relais : clé ajoutée côté serveur, en-têtes de session figés')

print('\nTous les cas P162 sont valides.')
