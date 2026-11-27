"""Validation locale P158 : `embedded-searxng` dans le menu « Moteur de recherche web ».

Usage : /opt/opencode-venv/bin/python3 scripts/test_p158.py

Le correctif P10 (liste des moteurs du dropdown) avait été appliqué autrefois
sur les chunks JS précompilés. Depuis que la CI recompile le frontend depuis
les sources Svelte, l'option a disparu : ce test vérifie que le patch source
`09-WebSearch.svelte.patch` l'ajoute bien à `webSearchEngines`, que le backend
sait traiter la valeur et qu'aucun nouveau libellé n'est inventé.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
SUB = PROJ / 'vendor/open-webui'
PATCH = PROJ / 'patches/frontend/09-WebSearch.svelte.patch'
CIBLE = 'src/lib/components/admin/Settings/WebSearch.svelte'

print('=== P158 — embedded-searxng dans le dropdown web search ===')
assert PATCH.exists(), f'patch absent : {PATCH}'
contenu_patch = PATCH.read_text(encoding='utf-8')
assert '+		\'embedded-searxng\',' in contenu_patch, 'option absente du patch'
assert contenu_patch.count("'embedded-searxng'") == 1, 'option dupliquée dans le patch'
assert 'a/lib/components/admin/Settings/WebSearch.svelte' in contenu_patch
print('OK  patch source présent, une seule occurrence de embedded-searxng')

pristine = subprocess.run(['git', '-C', str(SUB), 'show', f'HEAD:{CIBLE}'],
                          capture_output=True, text=True, check=True).stdout
assert "'embedded-searxng'" not in pristine, "l'amont contient déjà l'option"

with tempfile.TemporaryDirectory(dir='/tmp/opencode', prefix='p158-') as tmp:
    racine = Path(tmp) / 'src'
    destination = racine / Path(CIBLE).relative_to('src')
    destination.parent.mkdir(parents=True)
    destination.write_text(pristine, encoding='utf-8')
    appli = subprocess.run(['patch', '-p1', '--forward'], cwd=racine,
                           input=contenu_patch, capture_output=True, text=True)
    assert appli.returncode == 0, appli.stdout + appli.stderr
    modifie = destination.read_text(encoding='utf-8')

liste = modifie.split('let webSearchEngines = [', 1)[1].split('];', 1)[0]
options = [l.strip().strip("',") for l in liste.splitlines() if l.strip()]
assert options.count('embedded-searxng') == 1
assert options[options.index('searxng') + 1] == 'embedded-searxng', \
    "l'option doit être voisine de searxng"
assert len(options) == len(set(options)), 'liste du dropdown avec doublons'
assert 'searngx_local' not in modifie, 'libellé inexistant inventé'
print('OK  dropdown : embedded-searxng ajouté une fois, juste après searxng')

retrieval = (PROJ / 'src/open_webui/routers/retrieval.py').read_text(encoding='utf-8')
assert "engine in ('embedded-searxng', 'embeded-searxng')" in retrieval
android = (PROJ / 'app/src/main/python/android_main.py').read_text(encoding='utf-8')
assert '"embedded-searxng"' in android
print('OK  backend et android_main.py connaissent déjà la valeur')

garde = (PROJ / 'scripts/check_apk.py').read_text(encoding='utf-8')
assert 'embedded-searxng' in garde and 'js_immuable' in garde, \
    'garde-fou APK absent'
print('OK  garde-fou APK : marqueur embedded-searxng contrôlé dans le frontend')

print('\nTous les cas P158 sont valides.')
