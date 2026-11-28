"""Validation locale P155 : deux sous-onglets SearXNG dans /fm.

Usage : .venv313/bin/python3 scripts/test_p155.py

La page « Service » doit rester identique à la version antérieure ; la page
« Moteur de recherche » doit intégrer l'interface web de SearXNG (iframe sur
http://127.0.0.1:8888) quand le service est actif, et proposer son démarrage
sinon. Le rendu est vérifié en appelant directement la route /fm (port 8090
uniquement pour les sondes réseau : aucun serveur n'est ouvert ici).
"""
import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p155-', dir='/tmp/opencode'))
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p155',
    HOME=str(TMP),
    DATA_DIR=str(TMP / 'data'),
    UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'),
    DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
(TMP / 'tmp').mkdir(parents=True, exist_ok=True)
for cle in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    os.environ.pop(cle, None)
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P155 — sous-onglets SearXNG de /fm ===')

src = (PROJ / 'src/open_webui/android_fm.py').read_text(encoding='utf-8')
for marqueur in ('P155 : /fm SearXNG expose deux sous-onglets',
                 'P156 : le test de recherche', 'P157 : le sous-onglet Moteur',
                 'class="subtabs"', 'class="subtab', 'class="sxframe"',
                 'class="sxcfg"', 'http://127.0.0.1:8888/"',
                 "sub not in ('service', 'engine')"):
    assert marqueur in src, f'marqueur absent : {marqueur}'
print('OK  source : sous-onglets, iframe locale et repli service présents')

# android_main n'existe que dans l'APK : on simule les deux valeurs nécessaires.
etat = {'searxng': 'actif'}
am = types.ModuleType('android_main')
am.service_status = lambda: {'openwebui': 'actif', 'searxng': etat['searxng']}
am.searxng_settings_load = lambda: {'formats': ['json'], 'limiter': False}
am.searxng_settings_save = lambda *_a, **_k: 'réglages enregistrés'
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
    id = 'p155-utilisateur-test'
    role = 'admin'
    email = 'p155@example.invalid'


def rendre(query: bytes) -> str:
    scope = {
        'type': 'http', 'method': 'GET', 'path': '/fm',
        'query_string': query, 'headers': [], 'scheme': 'http',
        'server': ('testserver', 80),
    }
    reponse = asyncio.run(route.endpoint(Request(scope), Utilisateur()))
    assert reponse.status_code == 200, reponse.status_code
    return reponse.body.decode('utf-8')


base = b'folder=settings&tab=searxng'
html_service = rendre(base)
assert 'Paramètres &mdash; SearXNG' in html_service
assert 'SX_json' in html_service and 'Enregistrer les réglages' in html_service
assert 'Moteur : <code>searxng</code>' in html_service
assert 'embedded-searxng' in html_service
assert 'http://127.0.0.1:8888/search?q=&lt;query&gt;' in html_service
assert 'subtab on' in html_service and 'sub=service' in html_service
assert 'sub=engine' in html_service
assert '<iframe' not in html_service
# R162 — le bouton « Tester la recherche » est supprimé : aucune URL de test
# ne doit rester dans la vue Service (P156 avait corrigé sa cible, le bouton
# n'est plus voulu du tout).
assert 'Tester la recherche' not in html_service
assert 'search?q=test' not in html_service
assert 'href="/search?q=test' not in html_service
# P157 — tout le reste (état, boutons, messages) est bien côté Service.
for present in ('Redémarrer',
                'svc(&quot;searxng&quot;,&quot;restart&quot;,&quot;SearXNG&quot;)',
                'svcmsg', 'État :'):
    assert present in html_service, f'élément Service absent : {present}'
print('OK  /fm sans sub : Service actif, lien SearXNG corrigé, actions conservées')

assert rendre(base + b'&sub=service') == html_service, 'sub=service doit être idempotent'
print('OK  /fm?sub=service identique au défaut')

html_engine = rendre(base + b'&sub=engine')
assert '<iframe class="sxframe" src="http://127.0.0.1:8888/"' in html_engine
assert html_engine.count('<iframe') == 1, 'une seule iframe autorisée'
assert 'subtab on' in html_engine and 'sub=engine' in html_engine
# P157 — aucune autre carte ni action dans la vue Moteur.
for absent in ('SX_json', 'Paramètres &mdash; SearXNG', 'État :', 'Redémarrer',
               'svc(', 'id="svcmsg"', 'Ouvrir dans un nouvel onglet',
               'Tester la recherche'):
    assert absent not in html_engine, f'élément Service présent dans Moteur : {absent}'
print('OK  /fm?sub=engine : uniquement l’iframe (les barres d’onglets restent)')

etat['searxng'] = 'arrêt'
html_arret = rendre(base + b'&sub=engine')
assert '<iframe class="sxframe" src="http://127.0.0.1:8888/"' in html_arret
assert 'Service arrêté' not in html_arret and 'Démarrer le service' not in html_arret
html_service_arret = rendre(base + b'&sub=service')
assert '<b>arrêt</b>' in html_service_arret and 'Démarrer' in html_service_arret
print('OK  service arrêté : l’iframe reste seule, l’état est dans Service')

etat['searxng'] = 'actif'
html_bizarre = rendre(base + b'&sub=inconnu')
assert html_bizarre == html_service, 'une valeur inconnue doit revenir au Service'
print('OK  sous-onglet inconnu -> repli sur Service')

print('\nTous les cas P155 sont valides.')
