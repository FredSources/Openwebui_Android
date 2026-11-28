"""Validation locale R165 : aiohttp 3.14.5 sans patchs de compatibilité.

Usage : .venv313/bin/python3 scripts/test_p154.py

Anciennement P154 : l'amont v0.13.5 passe `middlewares=` aux `ClientSession`
aiohttp, paramètre ajouté en 3.11 alors que le fork épinglait 3.10.10. Quatre
patchs compensaient cet écart (`31`, `36`, `38` et un hunk de `20`). La montée
à aiohttp 3.14.5 (wheels cross-buildés, R165) les rend inutiles : ce test
vérifie qu'ils ont été retirés et que les pins, les wheels et la version de
livraison sont cohérents. Aucun serveur n'est démarré : les extensions Android
ne sont pas importables par le Python hôte.
"""
from pathlib import Path
import zipfile

PROJ = Path(__file__).resolve().parents[1]

print('=== R165 — montée aiohttp 3.14.5, retrait des patchs de compatibilité ===')

# 1. Pins : plus aucun plafond 3.10, toutes les dépendances natives épinglées.
req = (PROJ / 'requirements-min.txt').read_text(encoding='utf-8')
for pin in ('aiohttp==3.14.5', 'multidict==7.2.1', 'yarl==1.25.1',
            'frozenlist==1.8.0', 'propcache==0.5.4', 'aiohappyeyeballs==2.7.1',
            'attrs==26.1.0', 'idna==3.20'):
    assert pin in req, f'pin absent : {pin}'
assert 'aiohttp==3.10.10' not in req, 'ancien plafond aiohttp encore présent'
print('OK  requirements : aiohttp 3.14.5 et 7 dépendances épinglées')

# 2. Patchs supprimés, y compris le hunk de compatibilité de 20.
for ancien in ('31-utils__oauth.py.patch', '36-utils__aws.py.patch',
               '38-compat-aiohttp-middlewares.patch'):
    assert not (PROJ / 'patches/backend' / ancien).exists(), f'{ancien} encore présent'
auths_patch = (PROJ / 'patches/backend/20-routers__auths.py.patch').read_text()
assert 'BasicAuth(login, password, encoding)' not in auths_patch, \
    'repli P148 encore dans le patch 20'
assert 'P148' not in auths_patch and 'except ImportError' not in auths_patch
print('OK  patchs : 31/36/38 retirés, hunk P148 absent de 20')

# 3. Sources restaurées sur le comportement amont.
aws = (PROJ / 'src/open_webui/utils/aws.py').read_text(encoding='utf-8')
assert 'client_session_kwargs' not in aws, 'helper P154 encore présent'
assert 'aiohttp.ClientHandlerType' in aws, 'annotation amont perdue (patch 36)'
auths = (PROJ / 'src/open_webui/routers/auths.py').read_text(encoding='utf-8')
assert 'from aiohttp import ClientSession, encode_basic_auth' in auths
assert 'BasicAuth(login, password, encoding)' not in auths, 'repli P148 encore présent'
for rel in ('routers/openai.py', 'utils/session_pool.py'):
    source = (PROJ / 'src/open_webui' / rel).read_text(encoding='utf-8')
    assert 'middlewares=(sign_aws_request' in source, f'{rel} : middlewares= amont absent'
print('OK  sources : middlewares= amont, aucun helper ni repli de compatibilité')

# 4. Wheels Android : tag, suffixe .so et architecture embarquée.
nattifs = {
    'aiohttp-3.14.5': 4,
    'multidict-7.2.1': 3,
    'yarl-1.25.1': 1,
    'frozenlist-1.8.0': 1,
    'propcache-0.5.4': 1,
}
for paquet, nb_so in nattifs.items():
    whl = PROJ / 'wheels' / f'{paquet}-cp313-cp313-android_24_arm64_v8a.whl'
    assert whl.exists(), f'wheel absent : {whl.name}'
    with zipfile.ZipFile(whl) as z:
        sos = [n for n in z.namelist() if n.endswith('.so')]
        wheel_meta = z.read([n for n in z.namelist() if n.endswith('.dist-info/WHEEL')][0])
        record = z.read([n for n in z.namelist() if n.endswith('.dist-info/RECORD')][0])
        record_noms = {l.split(',')[0] for l in record.decode().splitlines()}
    assert len(sos) == nb_so, f'{whl.name} : {len(sos)} .so au lieu de {nb_so}'
    assert all(n.endswith('cpython-313-aarch64-linux-android.so') for n in sos), sos
    assert b'cp313-cp313-android_24_arm64_v8a' in wheel_meta, whl.name
    # R165-bis : un RECORD qui garde les noms linux-gnu fait ajouter par pip
    # une ligne vide pour le .so renommé → Chaquopy plante sur int('').
    assert record_noms >= set(sos), f'{whl.name} : .so absents du RECORD'
    for ligne in record.decode().splitlines():
        champs = ligne.split(',')
        assert len(champs) == 3, f'{whl.name} : RECORD mal formé : {ligne}'
        if not champs[0].endswith('.dist-info/RECORD'):
            assert champs[2].isdigit(), f'{whl.name} : taille vide dans RECORD : {ligne}'
for pur in ('aiohappyeyeballs-2.7.1', 'aiosignal-1.4.0', 'attrs-26.1.0', 'idna-3.20'):
    assert (PROJ / 'wheels' / f'{pur}-py3-none-any.whl').exists(), pur
print('OK  wheels : 5 natifs Android + 4 purs, tags et suffixes conformes')

# 5. Version de livraison : prerelease v0.0.82_ot_beta, stable v0.0.81 intacte.
gradle = (PROJ / 'app/build.gradle').read_text(encoding='utf-8')
assert "versionName '0.0.82_ot_beta'" in gradle, 'versionName pas en v0.0.82_ot_beta'
fm = (PROJ / 'patches/backend/02-android_fm.py.patch').read_text()
assert '_FM_VERSION = "0.0.82_ot_beta"' in fm
assert 'P101 version=0.0.82_ot_beta' in fm
print('OK  version : v0.0.82_ot_beta dans build.gradle et /fm')

print('\nTous les cas R165 sont valides.')
