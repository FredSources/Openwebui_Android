"""Validation locale P168 : retour visuel des boutons de service et self-heal proot.

Usage : .venv313/bin/python3 scripts/test_p168.py

Couvre deux points remontés sur appareil :
- le bouton « Démarrer / Arrêter / Redémarrer » ne renvoyait qu'un « ok » muet,
  et « Redémarrer l'application » ne renvoyait rien du tout ;
- le bit exécutable de `proot`, posé à la première extraction, n'était plus
  réappliqué quand le marqueur de version correspondait ( Errno 13 sur le
  volume interne, alors même que le chemin était le bon ).

Aucun serveur n'est ouvert : les pages sont rendues directement via ASGI.
"""
import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p168-', dir='/tmp/opencode'))
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p168', HOME=str(TMP),
    DATA_DIR=str(TMP / 'data'), UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'), DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
for sous in ('tmp', 'data'):
    (TMP / sous).mkdir(parents=True, exist_ok=True)
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P168 — retour des boutons et exécutabilité proot ===')

am = types.ModuleType('android_main')
am.service_status = lambda: {'openwebui': 'actif', 'searxng': 'actif',
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


def rendre(query: bytes) -> str:
    route = next(r for r in app.routes if getattr(r, 'path', None) == '/fm')

    class Utilisateur:
        id = 'p168-utilisateur-test'
        role = 'admin'
        email = 'p168@example.invalid'

    scope = {'type': 'http', 'method': 'GET', 'path': '/fm',
             'query_string': query, 'headers': [], 'scheme': 'http',
             'server': ('testserver', 80)}
    reponse = asyncio.run(route.endpoint(Request(scope), Utilisateur()))
    assert reponse.status_code == 200
    return reponse.body.decode('utf-8')


pages = {
    'owui': rendre(b'folder=settings&tab=owui'),
    'searxng': rendre(b'folder=settings&tab=searxng'),
    'ot': rendre(b'folder=settings&tab=ot_service'),
}
for nom, html in pages.items():
    assert 'function svcMsg(' in html, f'{nom} : fonction de message absente'
    assert 'function svc(' in html, f'{nom} : fonction svc absente'
    assert '⏳ "+v+" de "+lib+"…' in html, \
        f'{nom} : message « en cours » absent'
    assert 'setTimeout(function(){' in html, \
        f'{nom} : le message « en cours » ne peut pas être affiché avant le pont Java'
    assert 'role="status" aria-live="polite"' in html, \
        f'{nom} : zone de message non annoncée'
    assert 'svcbar.busy' in (PROJ / 'src/open_webui/android_fm.py').read_text(
        encoding='utf-8'), 'style de bouton occupé absent'
    assert 'pont système indisponible' in html, f'{nom} : gestion d’erreur absente'
print('OK  trois onglets : message immédiat + résultat + gestion d’erreur')

assert 'function svcRestart()' in pages['owui']
assert 'onclick="svcRestart()"' in pages['owui']
assert 'onclick="AndroidSystem.restartApp()"' not in pages['owui'], \
    'le bouton Redémarrer contourne encore le retour visuel'
print('OK  Redémarrer l’application : confirmation avant extinction')

node = shutil.which('node')
assert node, 'node requis pour valider la syntaxe JavaScript'
blocs = 0
for nom, html in pages.items():
    for i, bloc in enumerate(re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>', html)):
        if not bloc.strip():
            continue
        fichier = TMP / f'{nom}-{i}.js'
        fichier.write_text(bloc, encoding='utf-8')
        resultat = subprocess.run([node, '--check', str(fichier)],
                                  capture_output=True, text=True)
        assert resultat.returncode == 0, f'{nom} : JS invalide — {resultat.stderr}'
        blocs += 1
assert blocs >= 3, f'seulement {blocs} blocs JS contrôlés'
print(f'OK  node --check : {blocs} blocs JavaScript valides')

java = (PROJ / 'app/src/main/java/org/openwebui/android/MainActivity.java').read_text(
    encoding='utf-8')
assert 'callAttr("service_control", name, action).toString()' in java, \
    'le pont Java ne renvoie pas le résultat réel de service_control'
assert 'if (deja.exists() && !deja.setExecutable(true, false))' in java, \
    'le bit exécutable n’est pas réappliqué sur le chemin rapide'
print('OK  Java : résultat réel renvoyé, chmod proot réappliqué au démarrage')

runner = (PROJ / 'src/open_terminal/utils/runner.py').read_text(encoding='utf-8')
assert 'if not os.access(_ANDROID_PROOT, os.X_OK):' in runner
assert 'os.chmod(_ANDROID_PROOT, 0o700)' in runner
print('OK  runner.py : self-heal du bit exécutable avant ouverture du shell')

main_py = (PROJ / 'src/open_terminal/main.py').read_text(encoding='utf-8')
assert 'P168 exécution refusée' in main_py
assert 'mode=%s' in main_py and 'X_OK=%s' in main_py
assert '"externe(noexec)" if "Android/data" in cmd[0] else "interne"' in main_py
fm_py = (PROJ / 'src/open_webui/android_fm.py').read_text(encoding='utf-8')
assert 'proot présent dans getFilesDir() (stockage interne)' in fm_py, \
    'le diagnostic P167 trompeur est encore présent'
print('OK  diagnostic :errno et racine distingués, message interne honnête')

print('Tous les cas P168 sont valides.')
