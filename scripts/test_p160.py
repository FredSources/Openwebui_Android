"""Validation locale P160 : Open Terminal + mini-Debian embarqués dans l'APK.

Usage : .venv313/bin/python3 scripts/test_p160.py

Contrôles sans appareil : sources figées, patchs appliqués, rootfs et xterm
versionnés, absence de websockets, extraction Java et service Python local.
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix='p160-', dir='/tmp/opencode'))
os.environ.update(HOME=str(TMP), DATA_DIR=str(TMP / 'data'))
sys.path = [str(PROJ / 'src')] + [p for p in sys.path if p not in ('', str(PROJ))]

print('=== P160 — Open Terminal embarqué ===')

# 1 — sources figées.
gm = (PROJ / '.gitmodules').read_text(encoding='utf-8')
assert 'vendor/open-terminal' in gm and 'vendor/proot-distro' in gm
ot = PROJ / 'vendor/open-terminal'
pd = PROJ / 'vendor/proot-distro'
assert ot.is_dir() and pd.is_dir(), 'submodules absents'
import subprocess
def rev(path):
    return subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'],
                          capture_output=True, text=True, check=True).stdout.strip()
assert rev(ot) == '1413e9be11677266a400744480dc2e8c0de69916', rev(ot)
assert rev(pd) == '737306f53fc86213db0ce0ac3e76aa3fda8dcb90', rev(pd)
assert rev(PROJ / 'vendor/open-webui').startswith('926f826ea'), 'open-webui non figé'
print('OK  submodules : open-terminal v0.18.8, proot-distro v5.10.3, open-webui inchangé')

# 2 — patchs source (vérifiés APRÈS apply_patches.sh).
runner = (PROJ / 'src/open_terminal/utils/runner.py').read_text(encoding='utf-8')
assert 'def android_proot_prefix()' in runner
assert '"/bin/bash", "-lc", command' in runner
assert '"-b", f"{_ANDROID_WORK}:/root/work"' in runner
assert '"-R"' not in runner and '"-S"' not in runner, 'bind $HOME interdit'
main = (PROJ / 'src/open_terminal/main.py').read_text(encoding='utf-8')
assert '/bin/bash", "-l"' in main
assert 'return "0.18.8"' in main, 'fallback dist-info absent'
events = (PROJ / 'src/open_terminal/utils/events.py').read_text(encoding='utf-8')
assert 'watchfiles = None' in events and 'surveillance de fichiers indisponible' in events
rootfs_py = (PROJ / 'src/proot_distro/helpers/rootfs.py').read_text(encoding='utf-8')
assert 'grp = None' in rootfs_py and 'f"gid_{g}"' in rootfs_py
print('OK  patchs : proot sans -R/-S, shell /bin/bash -l, grp/watchfiles/version optionnels')

# 3 — service Python : clé secrète, port et pilotage.
am_src = (PROJ / 'app/src/main/python/android_main.py').read_text(encoding='utf-8')
assert 'OPEN_TERMINAL_PORT = 8889' in am_src
assert 'OPEN_TERMINAL_API_KEY_FILE' in am_src
assert 'secrets.token_urlsafe(48)' in am_src
assert "_force_machine_connection(data_dir, key)" in am_src
assert 'name == \'open_terminal\'' in am_src
assert "'open_terminal': 'actif' if _ot_actif" in am_src
assert 'ws="none"' in am_src, 'WebSocket navigateur non désactivé'
assert 'websockets' not in (PROJ / 'requirements-min.txt').read_text(encoding='utf-8')
gradle = (PROJ / 'app/build.gradle').read_text(encoding='utf-8')
assert "versionName '0.0.82_ot_beta'" in gradle
print('OK  service : 8889, clé fichier 600, pas de websockets, pilotage /fm')

# 4 — extraction Android.
java = (PROJ / 'app/src/main/java/org/openwebui/android/MainActivity.java').read_text(encoding='utf-8')
assert 'prepareMiniDebian();' in java
assert 'private void prepareMiniDebian()' in java
assert 'proot.setExecutable(true, false)' in java
assert 'minidebian.version' in java
apply = (PROJ / 'scripts/apply_patches.sh').read_text(encoding='utf-8')
assert 'vendor/open-terminal/open_terminal:src/open_terminal' in apply
assert 'vendor/proot-distro/proot_distro:src/proot_distro' in apply
assert 'static/xterm -> src/open_webui/static/xterm' in apply
print('OK  assets : extraction Java avec bit exécutable et copie par apply_patches.sh')

# 5 — rootfs et xterm versionnés, empreintes cohérentes.
mini = PROJ / 'minidebian'
manifest_path = mini / 'manifest.json'
assert manifest_path.is_file(), 'minidebian/manifest.json absent (build rootfs en cours ?)'
man = json.loads(manifest_path.read_text(encoding='utf-8'))
assert man['suite'] == 'trixie' and man['arch'] == 'arm64'
rootfs = mini / 'rootfs.tar.xz'
assert rootfs.is_file() and rootfs.stat().st_size < 100_000_000
digest = hashlib.sha256(rootfs.read_bytes()).hexdigest()
assert man['sha256'] == digest, 'sha256 manifest ≠ rootfs'
assert man['taille_octets'] == rootfs.stat().st_size
for binaire in ('proot', 'libtalloc.so.2', 'libandroid-shmem.so'):
    assert (mini / binaire).is_file(), binaire
    assert hashlib.sha256((mini / binaire).read_bytes()).hexdigest() == \
        man['binaires'][binaire]['sha256'], binaire
for paquet in ('git', 'apt', 'bash', 'ca-certificates'):
    assert any(p.startswith(paquet + '=') for p in man['paquets']), paquet
xterm = PROJ / 'static/xterm'
xm = json.loads((xterm / 'manifest.json').read_text(encoding='utf-8'))
for nom, meta in xm['files'].items():
    assert (xterm / nom).is_file(), nom
    assert hashlib.sha256((xterm / nom).read_bytes()).hexdigest() == meta['sha256'], nom
print('OK  empreintes : rootfs < 100 Mo, binaires et xterm conformes aux manifests')

print('\nTous les cas P160 sont valides.')
