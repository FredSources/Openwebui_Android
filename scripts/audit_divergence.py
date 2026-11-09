# audit_divergence.py — compare src/open_webui (généré) à vendor/unpacked/open_webui (amont).
import pathlib
import subprocess

PROJ = pathlib.Path('/root/openwebui-android')
AMONT = PROJ / 'vendor' / 'unpacked' / 'open_webui'
GEN = PROJ / 'src' / 'open_webui'

modifies, ajoutes = [], []
for p in sorted(GEN.rglob('*.py')):
    rel = p.relative_to(GEN)
    src = AMONT / rel
    if not src.exists():
        ajoutes.append(str(rel))
        continue
    out = subprocess.run(['diff', '-u', str(src), str(p)], capture_output=True, text=True).stdout
    hunks = out.count('\n@@')
    lignes = sum(1 for l in out.splitlines() if l[:1] in '+-' and l[:3] not in ('+++', '---'))
    if hunks:
        modifies.append((str(rel), hunks, lignes))

print('=== AMONT MODIFIÉ (%d fichiers) ===' % len(modifies))
total_h = total_l = 0
for rel, h, l in modifies:
    print('  %-46s %2d hunk(s)  %4d ligne(s)' % (rel, h, l))
    total_h += h
    total_l += l
print('  TOTAL : %d hunks, %d lignes modifiées dans %d fichiers amont' % (total_h, total_l, len(modifies)))
print()
print('=== MODULES AJOUTÉS hors amont (%d fichiers) ===' % len(ajoutes))
for rel in ajoutes:
    print('  ' + rel)
