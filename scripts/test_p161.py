"""Validation locale P161 : compatibilité Chaquopy des sources embarquées.

Usage : .venv313/bin/python3 scripts/test_p161.py

Chaquopy n'offre ni module `grp`/`pwd`, ni watcher `watchfiles` natif, ni
`dist-info` pour Open Terminal (copié comme source). Les patchs doivent
fournir un repli sans faux module Python global.
"""
import os
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p161-', dir='/tmp/opencode'))
os.environ.update(HOME=str(TMP), DATA_DIR=str(TMP / 'data'))
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P161 — compatibilité Chaquopy ===')

rootfs = (PROJ / 'src/proot_distro/helpers/rootfs.py').read_text(encoding='utf-8')
assert 'try:' in rootfs and 'import grp' in rootfs and 'except ImportError' in rootfs
assert 'pwd = None' in rootfs and 'grp = None' in rootfs
assert "f\"gid_{g}\"" in rootfs, 'repli gid manquant'
assert 'def _getgrgid' in rootfs or 'gid_' in rootfs
assert not (PROJ / 'src/grp.py').exists(), 'faux module global grp interdit'
print('OK  proot-distro : grp/pwd optionnels, repli gid_<n>, aucun faux module')

events = (PROJ / 'src/open_terminal/utils/events.py').read_text(encoding='utf-8')
assert 'try:' in events and 'import watchfiles' in events
assert 'watchfiles = None' in events
assert 'surveillance de fichiers indisponible' in events
print('OK  Open Terminal : watchfiles optionnel, erreur explicite si utilisé')

main = (PROJ / 'src/open_terminal/main.py').read_text(encoding='utf-8')
assert 'def _pkg_version(nom)' in main
assert 'PackageNotFoundError' in main or 'except Exception' in main
assert 'return "0.18.8"' in main
print('OK  Open Terminal : version 0.18.8 sans dist-info')

runner = (PROJ / 'src/open_terminal/utils/runner.py').read_text(encoding='utf-8')
assert 'OPENWEBUI_ANDROID_PROOT_LIB' in runner
assert 'LD_LIBRARY_PATH' in runner
am = (PROJ / 'app/src/main/python/android_main.py').read_text(encoding='utf-8')
assert 'OPENWEBUI_ANDROID_PROOT_LIB' in am
print('OK  proot : répertoire des bibliothèques bionic et LD_LIBRARY_PATH sous Android')

source = '\n'.join(
    (PROJ / f).read_text(encoding='utf-8')
    for f in ('app/src/main/python/android_main.py', 'scripts/check_apk.py')
)
assert 'websockets' not in (PROJ / 'requirements-min.txt').read_text(encoding='utf-8')
assert 'ws="none"' in source
print('OK  service : aucun WebSocket et aucune dépendance websockets')

print('\nTous les cas P161 sont valides.')
