"""Validation locale P159 : plus de barre d'onglets de premier niveau dans /fm.

Usage : /opt/opencode-venv/bin/python3 scripts/test_p159.py

La liste « Paramètres » de la sidebar porte les points vert/rouge des services
Open WebUI et SearXNG. Le sélecteur d'origine des fichiers (P109) conserve ses
onglets propres, qui ne sont pas la barre redondante supprimée ici.
"""
import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p159-', dir='/tmp/opencode'))
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p159', HOME=str(TMP),
    DATA_DIR=str(TMP / 'data'), UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'), DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
(TMP / 'tmp').mkdir(parents=True, exist_ok=True)
for cle in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    os.environ.pop(cle, None)
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P159 — sidebar avec état, sans onglets de premier niveau ===')
src = (PROJ / 'src/open_webui/android_fm.py').read_text(encoding='utf-8')
assert 'P159 : premier niveau' in src
assert '_fm_onglets' not in src.replace(
    "# P159 — l'ancienne barre d'onglets de premier niveau (_fm_onglets) est", '')
assert '<div class="tabs">' not in src, 'barre de premier niveau encore construite'
assert 'P101 version=0.0.81' in src, 'trace P101 avec version obsolète'
assert '0.0.80_beta' not in src, 'ancienne version encore présente dans /fm'
assert 'st.get(\'openwebui\') == \'actif\'' in src
assert 'st.get(\'searxng\') == \'actif\'' in src
print('OK  source : fonction et constructions de la barre supprimées')

etat = {'openwebui': 'actif', 'searxng': 'arrêt'}
am = types.ModuleType('android_main')
am.service_status = lambda: dict(etat)
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
route = next(r for r in app.routes if getattr(r, 'path', None) == '/fm')


class Utilisateur:
    id = 'p159-utilisateur-test'
    role = 'admin'
    email = 'p159@example.invalid'


def rendre(query: bytes) -> str:
    scope = {'type': 'http', 'method': 'GET', 'path': '/fm',
             'query_string': query, 'headers': [], 'scheme': 'http',
             'server': ('testserver', 80)}
    reponse = asyncio.run(route.endpoint(Request(scope), Utilisateur()))
    assert reponse.status_code == 200, reponse.status_code
    return reponse.body.decode('utf-8')


html = rendre(b'folder=settings&tab=searxng&sub=service')
assert 'OpenWebUI Android 0.0.81</footer>' in html, 'pied de page /fm non à jour'
assert '0.0.80_beta' not in html
assert '<div class="tabs">' not in html, 'onglets de premier niveau rendus'
assert 'class="subtabs"' in html, 'les sous-onglets SearXNG doivent rester'
assert 'Paramètres &mdash; SearXNG' in html
print('OK  /fm Paramètres : pied de page 0.0.81, aucun onglet de premier niveau')

oui = 'title="Open WebUI"><span class="si">'
assert oui in html, 'entrée Open WebUI absente de la sidebar'
# Les points précèdent le libellé, dans le bon ordre et avec les bonnes couleurs.
pos_oui = html.index('title="Open WebUI"')
pos_sx = html.index('title="SearXNG"')
assert pos_oui < pos_sx < pos_oui + 1500, 'ordre des entrées Paramètres modifié'
assert 'background:#22c55e"></span> Open WebUI' in html, 'point vert Open WebUI manquant'
assert 'background:#ef4444"></span> SearXNG' in html, 'point rouge SearXNG manquant'
print('OK  sidebar : point vert Open WebUI, point rouge SearXNG')

etat['openwebui'] = 'arrêt'
etat['searxng'] = 'actif'
html2 = rendre(b'folder=settings&tab=searxng&sub=service')
assert 'background:#ef4444"></span> Open WebUI' in html2
assert 'background:#22c55e"></span> SearXNG' in html2
print('OK  les points suivent l’état du service (inversion vérifiée)')

html_fichiers = rendre(b'folder=all')
assert '<div class="tabs" style="margin:0 0 14px">' in html_fichiers
assert 'Les deux' in html_fichiers and 'En base' in html_fichiers
print('OK  sélecteur d’origine des fichiers (P109) intact')

garde = (PROJ / 'scripts/check_apk.py').read_text(encoding='utf-8')
assert 'P159 : premier niveau' in garde
assert "js_immuable" in garde and "embedded-searxng" in garde
print('OK  garde-fous APK P158/P159 présents')

print('\nTous les cas P159 sont valides.')
