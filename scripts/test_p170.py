"""Validation P170 : plus de `already_exists` lors de la publication d'un tag recréé.

Usage : .venv313/bin/python3 scripts/test_p170.py

Le workflow doit nettoyer la release du tag ET le brouillon `untagged-*`
qu GitHub laisse quand on supprime un tag avant de le recréer. Sans cela,
`softprops/action-gh-release` finalise deux objets avec le même `tag_name`
et échoue avec `Too many retries`.
"""
import json
import os
import sys
import types
from pathlib import Path

import yaml

PROJ = Path(__file__).resolve().parents[1]
print('=== P170 — publication idempotente des tags recréés ===')

workflow = yaml.safe_load(
    (PROJ / '.github/workflows/build-apk-submodule.yml').read_text(encoding='utf-8'))
steps = workflow['jobs']['build']['steps']
noms = [s.get('name', '') for s in steps]
assert any(n.startswith('Nettoyage des releases fantômes') for n in noms), \
    'aucune étape de nettoyage des releases fantômes'
assert noms.index(next(n for n in noms if n.startswith('Nettoyage'))) < noms.index(
    'Release GitHub (tags v*)'), 'le nettoyage doit précéder la publication'

nettoyage = next(s for s in steps if str(s.get('name', '')).startswith('Nettoyage'))
assert nettoyage['if'] == "startsWith(github.ref, 'refs/tags/v')"
assert nettoyage['env']['TAG'] == '${{ github.ref_name }}'
assert nettoyage['env']['REPO'] == '${{ github.repository }}'
assert nettoyage['env']['GH_TOKEN'] == '${{ secrets.GITHUB_TOKEN }}'
print('OK  étape de nettoyage présente, avant la publication, avec le bon tag')

publication = next(s for s in steps if s.get('name') == 'Release GitHub (tags v*)')
assert publication['uses'] == 'softprops/action-gh-release@v2'
assert publication['with']['overwrite_files'] is True, \
    'les assets d une release existante ne sont pas remplacés'
assert publication['with']['prerelease'] == "${{ contains(github.ref_name, '_beta') }}"
assert publication['with']['make_latest'] == "${{ !contains(github.ref_name, '_beta') }}"
print('OK  publication : overwrite_files + prerelease/make_latest inchangés')

TAG = 'v0.0.82_ot_beta'
RELEASES = [
    {'id': 1, 'tag_name': TAG, 'draft': False,
     'assets': [{'name': f'OpenWebUI_Android-{TAG}-release.apk'}]},
    {'id': 2, 'tag_name': 'untagged-bf31e5d751dcbf2f7799', 'draft': True,
     'assets': [{'name': f'OpenWebUI_Android-{TAG}-debug.apk'}]},
    {'id': 3, 'tag_name': 'untagged-autre', 'draft': True,
     'assets': [{'name': 'autre-projet.apk'}]},
    {'id': 4, 'tag_name': 'v0.0.81', 'draft': False,
     'assets': [{'name': 'OpenWebUI_Android-0.0.81-release.apk'}]},
]
supprimes = []


class _FauxSubprocess(types.ModuleType):
    @staticmethod
    def check_output(*_a, **_k):
        return ''.join(json.dumps(r) + '\n' for r in RELEASES)

    @staticmethod
    def run(args, **_k):
        assert args[:3] == ['gh', 'api', '-X']
        assert args[3] == 'DELETE'
        supprimes.append(args[4].rsplit('/', 1)[-1])


script = nettoyage['run']
assert "<<'PY'\n" in script and "\nPY\n" in script, \
    'le nettoyage n utilise pas un here-doc Python'
code = script.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]

os.environ['TAG'] = TAG
os.environ['REPO'] = 'FredSources/Openwebui_Android'
sys.modules['subprocess'] = _FauxSubprocess('subprocess')
exec(compile(code, '<nettoyage>', 'exec'), {'__name__': '__main__'})

assert sorted(supprimes) == ['1', '2'], \
    f'nettoyage incorrect : {supprimes} (attendu 1 et 2 uniquement)'
print('OK  seuls la release du tag et le brouillon orphelin sont supprimés')

print('Tous les cas P170 sont valides.')
