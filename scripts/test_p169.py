"""Validation locale P169 : bouton Actualiser, restauration /fm et storage.

Usage : .venv313/bin/python3 scripts/test_p169.py

Couvre trois points remontés sur appareil après P168 :
- le sous-onglet « Moteur de recherche » n'avait aucun moyen de recharger la
  page après un redémarrage de l'application ;
- « Redémarrer l'application » retombait sur le chat et l'état du service
  pouvait rester affiché « arrêté » alors que le port 8889 répondait ;
- aucun dossier « storage » n'était créé pour le mini-Debian.

Aucun serveur n'est ouvert : les pages sont rendues directement via ASGI.
"""
import asyncio
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p169-', dir='/tmp/opencode'))
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p169', HOME=str(TMP),
    DATA_DIR=str(TMP / 'data'), UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'), DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
for sous in ('tmp', 'data'):
    (TMP / sous).mkdir(parents=True, exist_ok=True)
sys.path = [
    str(PROJ / 'src'),
    str(PROJ / 'app/src/main/python'),
] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P169 — Actualiser, redémarrage et storage mini-Debian ===')

import android_main as am  # noqa: E402
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
        id = 'p169-utilisateur-test'
        role = 'admin'
        email = 'p169@example.invalid'

    scope = {'type': 'http', 'method': 'GET', 'path': '/fm',
             'query_string': query, 'headers': [], 'scheme': 'http',
             'server': ('testserver', 80)}
    reponse = asyncio.run(route.endpoint(Request(scope), Utilisateur()))
    assert reponse.status_code == 200
    return reponse.body.decode('utf-8')


pages = {
    'owui': rendre(b'folder=settings&tab=owui'),
    'searxng': rendre(b'folder=settings&tab=searxng'),
    'engine': rendre(b'folder=settings&tab=searxng&sub=engine'),
    'ot': rendre(b'folder=settings&tab=ot_service'),
}

moteur = pages['engine']
assert 'id="sx-frame"' in moteur, 'iframe du moteur sans identifiant : Actualiser ne peut pas la recharger'
assert 'id="sx-refresh"' in moteur
assert 'onclick="fmRefreshSx()"' in moteur
assert 'function fmRefreshSx()' in moteur
assert 'f.src="http://127.0.0.1:8888/?_="+Date.now();' in moteur, \
    'rechargement sans cache-buster : la page resterait figée'
assert '⏳ Actualisation…' in moteur
assert 'sx-refresh-msg' in moteur, 'aucun retour visuel du rechargement'
assert '<iframe class="sxframe" src=' not in moteur, \
    'ancienne iframe non identifiée encore présente'
print('OK  Moteur de recherche : bouton Actualiser + retour visuel + cache-buster')

assert '/root/storage' in pages['ot']
assert 'data/minidebian/storage' in pages['ot'], \
    'le storage créé n’est pas documenté dans l’onglet Service'
print('OK  Service Open Terminal : chemin du storage visible')

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
assert 'last_fm_url' in java, 'la page /fm n’est pas restaurée après redémarrage'
assert 'ensureMiniDebianStorage()' in java
assert 'new java.io.File(dataHome, "minidebian")' in java, \
    'le storage n’est pas créé sous le répertoire visible de l’application'
assert 'android.system.Os.chmod(binaire.getAbsolutePath(), 0700)' in java, \
    'les droits ne suivent pas la méthode Termux (Os.chmod 0700)'
assert 'chmodProot(deja)' in java and 'chmodProot(proot)' in java, \
    'le chmod n’est pas réappliqué sur les deux chemins (rapide et extraction)'
print('OK  Java : restauration /fm + storage + chmod Termux 0700 sur les deux chemins')

source = (PROJ / 'app/src/main/python/android_main.py').read_text(encoding='utf-8')
assert 'def _port_actif(' in source
assert "'open_terminal': 'actif' if _port_actif(OPEN_TERMINAL_PORT) else 'arrêt'" in source, \
    'l’état du service affiché ne vient pas du port réel'
assert 'os.environ["OPENWEBUI_ANDROID_STORAGE"] = str(storage)' in source
assert 'data_dir / "minidebian" / "storage"' in source
assert '_ot_actif = False' in source
print('OK  android_main : état mesuré sur le port, storage et reset du thread')

# Comportement réel du sondage : port ouvert puis fermé.
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serveur:
    serveur.bind(('127.0.0.1', 0))
    serveur.listen(1)
    port = serveur.getsockname()[1]
    assert am._port_actif(port) is True, 'un port à l’écoute est déclaré arrêté'
assert am._port_actif(port) is False, 'un port fermé est déclaré actif'
print('OK  _port_actif : vrai si le port répond, faux après fermeture')

runner = (PROJ / 'src/open_terminal/utils/runner.py').read_text(encoding='utf-8')
assert '_ANDROID_STORAGE = os.environ.get("OPENWEBUI_ANDROID_STORAGE", "")' in runner
assert 'prefix[4:4] = ["-b", f"{_ANDROID_STORAGE}:/root/storage"]' in runner
assert 'P169 proot non exécutable après chmod' in runner
assert '_allog.journal("open_terminal", _detail, "ERROR")' in runner
print('OK  runner : bind /root/storage + journal direct du refus d’exécution')

patch = (PROJ / 'patches/backend/08-android_fm-p169.patch').read_text(encoding='utf-8')
assert 'fmRefreshSx' in patch and 'data/minidebian/storage' in patch, \
    'le patch P169 n’est pas versionné (reconstruction perdue)'
print('OK  patch 08-android_fm-p169.patch versionné')

print('Tous les cas P169 sont valides.')
