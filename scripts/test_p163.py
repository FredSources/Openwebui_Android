"""Validation locale P163 : réinitialisation Open Terminal en deux actions.

Usage : .venv313/bin/python3 scripts/test_p163.py

Le mode « environment » conserve /root/work ; le mode « wipe-work » l'efface.
Dans les deux cas, clé, conteneur proot et marqueur sont reconstruits.
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p163-', dir='/tmp/opencode'))
HOME = TMP / 'home'
DATA = HOME / 'data'
WORK = DATA / 'work'
CONTAINER = DATA / 'proot-distro/containers/minidebian/rootfs'
os.environ.update(HOME=str(HOME), DATA_DIR=str(DATA))
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

spec = importlib.util.spec_from_file_location(
    'android_main_test', PROJ / 'app/src/main/python/android_main.py')
am = importlib.util.module_from_spec(spec)
spec.loader.exec_module(am)

print('=== P163 — réinitialisation ciblée ===')


def preparer(mode):
    for p in (HOME, DATA, WORK, CONTAINER,
              DATA / 'proot-distro/cache', DATA / 'proot-distro/locks',
              DATA / 'proot-distro/sessions'):
        p.mkdir(parents=True, exist_ok=True)
    (WORK / 'conservez-moi.txt').write_text('données utilisateur', encoding='utf-8')
    (CONTAINER / 'marqueur-rootfs').write_text('ancien', encoding='utf-8')
    old_key = DATA / 'open-terminal-api.key'
    old_key.write_text('ancienne-cle', encoding='utf-8')
    (DATA / 'open-terminal.log').write_text('journal avant reset', encoding='utf-8')
    (DATA / 'open-terminal-reset-requested').write_text(mode, encoding='utf-8')
    return old_key


# 1 — environnement seul : /root/work préservé.
old_key = preparer('environment')
am._apply_open_terminal_reset(HOME, DATA)
assert not (DATA / 'open-terminal-reset-requested').exists(), 'marqueur non consommé'
assert not old_key.exists(), 'clé non régénérée'
assert not CONTAINER.exists(), 'conteneur proot non reconstruit'
assert not (DATA / 'open-terminal.log').exists(), 'log non tronqué'
assert (WORK / 'conservez-moi.txt').read_text(encoding='utf-8') == 'données utilisateur'
print('OK  environment : clé/rootfs/log recréés, work conservé, marqueur consommé')

# 2 — tout effacer : /root/work supprimé aussi.
old_key = preparer('wipe-work')
am._apply_open_terminal_reset(HOME, DATA)
assert not (DATA / 'open-terminal-reset-requested').exists()
assert not old_key.exists() and not CONTAINER.exists()
assert not WORK.exists(), '/root/work non effacé en mode wipe-work'
print('OK  wipe-work : /root/work supprimé')

# 3 — demande depuis /fm : deux modes distincts.
assert callable(am.open_terminal_reset_request)
res = am.open_terminal_reset_request('environment')
assert 'Réinitialisation programmée' in res
assert (DATA / 'open-terminal-reset-requested').read_text(encoding='utf-8') == 'environment'
res = am.open_terminal_reset_request('wipe-work')
assert (DATA / 'open-terminal-reset-requested').read_text(encoding='utf-8') == 'wipe-work'
print('OK  demande : marqueur environment / wipe-work distincts')

# 4 — traçabilité et absence de régression des garde-fous.
journal = (PROJ / 'journal.md').read_text(encoding='utf-8')
assert 'P163' in journal, 'décision P163 non journalisée'
src = (PROJ / 'src/open_webui/android_fm.py').read_text(encoding='utf-8')
assert 'fm_ot_reset' in src and "'wipe-work' if forme.get('mode')" in src
java = (PROJ / 'app/src/main/java/org/openwebui/android/MainActivity.java').read_text(encoding='utf-8')
assert 'public void restartApp()' in java and '"AndroidSystem"' in java
assert 'AndroidSystem.restartApp()' in src, 'boutons de reset sans redémarrage'
assert 'fetch("/fm/ot/reset"' in src, 'reset sans appel serveur'
assert 'action="/fm/ot/reset"' not in src, 'formulaire de reset sans redémarrage'
print('OK  traçabilité : journal P163, route /fm/ot/reset, redémarrage via AndroidSystem')

# 5 — P164 : un restart attend la libération du port avant de relancer uvicorn.
class _Serveur:
    def __init__(self):
        self.started = True
        self._exit = False

    @property
    def should_exit(self):
        return self._exit

    @should_exit.setter
    def should_exit(self, value):
        self._exit = bool(value)
        self.started = False


serveur = _Serveur()
am._ot_server = serveur
am._ot_actif = True
appels = []
am._start_open_terminal = lambda: appels.append(not serveur.started)
assert am.service_control('open_terminal', 'restart') == 'Open Terminal (re)démarré'
assert appels == [True], 'nouveau service lancé avant la libération du port'
print('OK  restart : port libéré avant le relancement du service')

print('\nTous les cas P163 sont valides.')
