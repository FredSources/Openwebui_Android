"""P93 — garde-fou avant publication : le versionName de build.gradle DOIT
égaler le nom du tag (l'APK et ses assets portent ce numéro — arrivé en
v0.0.44 : assets nommés 0.0.43 sous le tag v0.0.44). Exécuté AVANT chaque tag."""
import os, subprocess, pathlib

racine = pathlib.Path(__file__).resolve().parent.parent
tag = os.environ.get('TAG') or (subprocess.run(
    ['git', 'describe', '--tags', '--exact-match'], capture_output=True, text=True,
    cwd=racine).stdout.strip() if os.environ.get('TAG') is None else os.environ['TAG'])
grad = (racine / 'app' / 'build.gradle').read_text(encoding='utf-8')
version = (grad.split("versionName '", 1)[1].split("'", 1)[0]) if "versionName '" in grad else '?'
attendu = tag.lstrip('v') if tag.startswith('v') else tag
if not tag:
    print('aucun tag local — vérification ignorée')
    raise SystemExit(0)
if version != attendu:
    print(f'ÉCHEC : versionName={version} ≠ tag {tag} — corriger puis retagger')
    raise SystemExit(1)
print(f'✓ tag {tag} == versionName {version}')
