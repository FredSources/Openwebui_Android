"""Validation locale P164 : JavaScript réellement exécutable dans /fm.

Usage : .venv313/bin/python3 scripts/test_p164.py

Deux régressions vues sur appareil sont couvertes :
- le `;` avant `.catch` du relais de reset (SyntaxError « Unexpected token . ») ;
- les addons xterm 6 dont l'UMD expose un espace de noms (FitAddon.FitAddon),
  pas directement un constructeur.
Les scripts inline des deux onglets sont soumis à `node --check`.
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
TMP = Path(tempfile.mkdtemp(prefix='p164-', dir='/tmp/opencode'))
os.environ.update(
    WEBUI_SECRET_KEY='test-local-p164', HOME=str(TMP),
    DATA_DIR=str(TMP / 'data'), UPLOAD_DIR=str(TMP / 'uploads'),
    TMPDIR=str(TMP / 'tmp'), DATABASE_URL=f"sqlite:///{TMP}/db.sqlite3",
)
(TMP / 'tmp').mkdir(parents=True, exist_ok=True)
(TMP / 'data').mkdir(parents=True, exist_ok=True)
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P164 — JavaScript des onglets Open Terminal ===')

am = types.ModuleType('android_main')
am.service_status = lambda: {'openwebui': 'actif', 'searxng': 'arrêt',
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
        id = 'p164-utilisateur-test'
        role = 'admin'
        email = 'p164@example.invalid'

    scope = {'type': 'http', 'method': 'GET', 'path': '/fm',
             'query_string': query, 'headers': [], 'scheme': 'http',
             'server': ('testserver', 80)}
    reponse = asyncio.run(route.endpoint(Request(scope), Utilisateur()))
    assert reponse.status_code == 200
    return reponse.body.decode('utf-8')


def rendre_route(chemin: str) -> str:
    route = next(r for r in app.routes if getattr(r, 'path', None) == chemin)

    class Utilisateur:
        id = 'p164-utilisateur-test'
        role = 'admin'
        email = 'p164@example.invalid'

    scope = {'type': 'http', 'method': 'GET', 'path': chemin,
             'query_string': b'', 'headers': [], 'scheme': 'http',
             'server': ('testserver', 80)}
    import inspect
    args = (Request(scope), Utilisateur()) if len(inspect.signature(route.endpoint).parameters) > 1 else (Request(scope),)
    reponse = asyncio.run(route.endpoint(*args))
    assert reponse.status_code == 200
    return reponse.body.decode('utf-8')


shell = rendre(b'folder=settings&tab=ot_shell')
service = rendre(b'folder=settings&tab=ot_service')
terminal = rendre_route('/fm/ot/terminal')
assert 'src="/fm/ot/terminal"' in shell and 'class="sxframe"' in shell
assert '/static/xterm/xterm.js' not in shell, 'l’iframe doit isoler xterm.js de /fm'
assert 'loading="lazy"' not in shell, 'l’iframe du shell doit charger immédiatement'
# P165 — « Shell root » ne figure plus dans la sidebar « Paramètres » :
# l’accès passe uniquement par le sous-onglet Open Terminal.
assert '"/fm?folder=settings&tab=ot_shell", "Shell root"' not in shell, \
    'l’entrée Shell root est revenue dans la sidebar'
assert 'class="subtab on" href="/fm?folder=settings&tab=ot_shell"' in shell, \
    'sous-onglet Shell root absent'
assert 'service arrêté — démarrez-le dans l’onglet Service' in terminal
assert 'service_control(\'open_terminal\', \'run\')' in Path(
    PROJ / 'src/open_webui/android_fm.py').read_text(encoding='utf-8')

# 1 — syntaxe JavaScript : tous les blocs inline passent `node --check`.
node = shutil.which('node')
assert node, 'node requis pour valider la syntaxe JavaScript'
blocs = 0
for nom, html in (('shell', shell), ('service', service), ('terminal', terminal)):
    for i, bloc in enumerate(re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>', html)):
        if not bloc.strip():
            continue
        fichier = TMP / f'{nom}-{i}.js'
        fichier.write_text(bloc, encoding='utf-8')
        res = subprocess.run([node, '--check', str(fichier)],
                             capture_output=True, text=True)
        assert res.returncode == 0, f'{nom} bloc {i} : {res.stderr[:300]}'
        blocs += 1
print(f'OK  syntaxe : {blocs} blocs inline validés par node --check')

# 2 — régression du relais de reset : chaîne .then(...).catch(...) sans ';'.
assert '})' + chr(10) in service or '}).catch(' in service or '})' in service
assert re.search(r'AndroidSystem\.restartApp\(\);\}\}\)\.catch\(', service), \
    'relais de reset rompu avant .catch'
assert '};.catch' not in service and '});.catch' not in service
print('OK  reset : .then(...).catch(...) chaîné, redémarrage AndroidSystem présent')

# 3 — addons xterm 6 : l'UMD expose un espace de noms, pas le constructeur.
assert 'ctor(window.FitAddon,"FitAddon")' in terminal
assert 'ctor(window.WebLinksAddon,"WebLinksAddon")' in terminal
assert 'new FA()' in terminal and 'new WL()' in terminal
assert 'new FitAddon()' not in terminal and 'new WebLinksAddon()' not in terminal
assert 'var fitAddon=new FA();' in terminal and 'fitAddon.fit();' in terminal
assert 'term.fit();' not in terminal, 'Terminal.fit() n’existe pas'
print('OK  addons : constructeurs UMD résolus, FitAddon.fit() utilisé')

js_vm = r'''
const fs = require('fs'), vm = require('vm');
const dir = process.argv[1];
const ctx = vm.createContext({console, setTimeout, window: {}, document: {},
  navigator: {}, URL, TextDecoder, Uint8Array, ArrayBuffer});
ctx.globalThis = ctx;
vm.runInContext(fs.readFileSync(dir + '/addon-fit.js', 'utf8'), ctx);
vm.runInContext(fs.readFileSync(dir + '/addon-web-links.js', 'utf8'), ctx);
function ctor(o, n) { return (o && o[n]) || o; }
const FA = ctor(ctx.FitAddon, 'FitAddon');
const WL = ctor(ctx.WebLinksAddon, 'WebLinksAddon');
if (typeof FA !== 'function' || typeof WL !== 'function') {
  throw new Error('constructeurs xterm introuvables dans les globals UMD');
}
const fa = new FA(); new WL();
if (typeof fa.fit !== 'function' || typeof fa.proposeDimensions !== 'function') {
  throw new Error('FitAddon.fit()/proposeDimensions() introuvables');
}
console.log('UMD OK');
'''
res = subprocess.run([node, '-e', js_vm, str(PROJ / 'static/xterm')],
                     capture_output=True, text=True)
assert res.returncode == 0 and 'UMD OK' in res.stdout, res.stderr[:400]
print('OK  UMD : FitAddon et WebLinksAddon instanciables depuis les fichiers livrés')

# 4 — répartition des boutons : pilotage dans Service, terminal isolé.
for bouton in ('Démarrer', 'Arrêter', 'Redémarrer'):
    assert bouton in service, f'{bouton} absent de Service'
    assert bouton not in shell and bouton not in terminal, \
        f'{bouton} présent à tort dans Shell root'
assert 'Rouvrir' in terminal and 'Effacer' in terminal
print('OK  interface : service/arrêt/restart dans Service, terminal en iframe')

print('\nTous les cas P164 sont valides.')
